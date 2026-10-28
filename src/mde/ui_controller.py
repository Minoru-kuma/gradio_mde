"""Application state and background observation; no Gradio or model imports.

There is one controller per application process. Tokens come from server-side
Gradio State, never from a client-supplied handle. No inference requests wait for
admission: the single slot is acquired without blocking or explicitly refused.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import tempfile
import threading
import time

from .contracts import ATTEMPT_ID, BackendBusy, JobHandle
from .registry import validate_parameters
from .storage import contained_path, inspect_png, read_json, run_path, sha256_file

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_PIXELS = 4 * 1024 * 1024
MAX_UPLOAD_EDGE = 4096


def validate_upload(image):
    """Validate format and fully decode a bounded PNG or JPEG upload."""
    if not image:
        raise ValueError("Upload one PNG or JPEG image")
    path = Path(image)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_UPLOAD_BYTES:
        raise ValueError("Image must be nonempty and at most 10 MiB")
    from PIL import Image
    try:
        with Image.open(path) as decoded:
            if decoded.format not in ("PNG", "JPEG") or getattr(decoded, "n_frames", 1) != 1:
                raise ValueError("Only single-frame PNG or JPEG is supported")
            width, height = decoded.size
            if width * height > MAX_UPLOAD_PIXELS or max(width, height) > MAX_UPLOAD_EDGE:
                raise ValueError("Image exceeds 4,194,304 pixels or 4096 pixels per edge")
            if decoded.format == "PNG":
                inspect_png(path)
            decoded.verify()
        with Image.open(path) as decoded:
            decoded.load()
    except Exception as error:
        raise ValueError(f"Invalid image: {error}") from error
    return path


def stage_upload(image, directory):
    """Snapshot first, then validate and convert that same immutable copy."""
    from PIL import Image, ImageOps, __version__ as pillow_version
    source = Path(directory) / "upload"
    if not image:
        raise ValueError("Upload one PNG or JPEG image")
    with Path(image).open("rb") as uploaded, source.open("wb") as owned:
        data = uploaded.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Image must be nonempty and at most 10 MiB")
        owned.write(data)
    validate_upload(source)
    target = Path(directory) / "image.png"
    with Image.open(source) as decoded:
        if decoded.format == "PNG":
            shutil.copyfile(source, target)
            return None
        size = list(decoded.size)
        orientation = decoded.getexif().get(274, 1)
        if type(orientation) is not int or orientation not in range(1, 9):
            raise ValueError("Invalid EXIF orientation")
        ImageOps.exif_transpose(decoded).convert("RGB").save(target, format="PNG")
    return {"format": "JPEG", "sha256": sha256_file(source), "size_bytes": source.stat().st_size,
            "original_size": size, "exif_orientation": orientation,
            "conversion": {"operation": "Pillow ImageOps.exif_transpose then convert RGB and save PNG",
                           "pillow_version": pillow_version}, "source_path": source}


@dataclass
class _Session:
    generation: int = 0
    active: bool = False
    cancel_pending: bool = False
    handle: JobHandle | None = None
    view: dict = field(default_factory=lambda: {
        "generation": 0, "status": "IDLE", "run_id": "", "cancel_requested": False,
        "progress": "unavailable (indeterminate while running)", "result": None})


class InferenceController:
    def __init__(self, runner, model_id, *, poll_interval=0.2):
        self.runner = runner
        self.model_id = model_id
        self.info = runner.registry.get_model(model_id)
        self.poll_interval = poll_interval
        self._lock = threading.RLock()
        self._admission = threading.Lock()
        self._sessions = {}

    def _session(self, token):
        if not isinstance(token, str) or not token:
            raise ValueError("Missing server session token")
        return self._sessions.setdefault(token, _Session())

    def forget(self, token):
        # Losing a browser never cancels a worker or deletes a saved Run.
        with self._lock:
            self._sessions.pop(token, None)

    def snapshot(self, token):
        with self._lock:
            return deepcopy(self._session(token).view)

    def _select(self, session, status):
        session.generation += 1
        session.view = {"generation": session.generation, "status": status,
                        "run_id": "", "cancel_requested": False,
                        "progress": "unavailable (indeterminate while running)", "result": None}
        return session.generation

    def _publish(self, token, session, generation, **values):
        with self._lock:
            if self._sessions.get(token) is session and session.generation == generation:
                session.view.update(values)

    def submit(self, token, image, variant_id, device, dtype, parameters, timeout, outputs):
        if not self._admission.acquire(blocking=False):
            raise BackendBusy("Local backend is busy; retry after the current job finishes. No job was queued.")
        staged = None
        try:
            self.info.variant(variant_id)
            if device not in self.info.data["supported_devices"] or dtype not in self.info.data["supported_dtypes"]:
                raise ValueError("Unsupported device or dtype")
            if not isinstance(parameters, dict):
                raise ValueError("Parameters must be a JSON object")
            parameters = validate_parameters(self.info.data.get("parameter_schema", {}), parameters)
            if timeout is not None and (type(timeout) is not int or timeout < 1):
                raise ValueError("Timeout must be a positive integer, or empty")
            from .contracts import normalize_outputs
            outputs = normalize_outputs(outputs)
            capabilities = self.info.variant(variant_id).get("capabilities", self.info.data["capabilities"])
            if any(capabilities.get(key, {}).get("status") not in ("supported", "conditional") for key in outputs):
                raise ValueError("Unsupported requested output")
            staged = tempfile.TemporaryDirectory(prefix="mde-ui-input-")
            provenance = stage_upload(image, staged.name)
            with self._lock:
                session = self._session(token)
                if session.active:
                    raise BackendBusy("This session already has an active job")
                generation = self._select(session, "SUBMITTING")
                session.active, session.cancel_pending, session.handle = True, False, None
            thread = threading.Thread(target=self._run, args=(token, session, generation, staged,
                dict(**({"input_provenance": provenance} if provenance else {}), variant_id=variant_id, device=device, dtype=dtype, parameters=parameters,
                     walltime_seconds=timeout, requested_outputs=tuple(outputs))), daemon=True)
            thread.start()
            return "Submission accepted; status will update automatically."
        except Exception:
            if staged is not None:
                staged.cleanup()
            self._admission.release()
            raise

    def _run(self, token, session, generation, staged, options):
        try:
            handle = self.runner.submit(self.model_id, Path(staged.name) / "image.png", **options)
            with self._lock:
                session.handle = handle
            self._publish(token, session, generation, run_id=handle.run_id)
            while True:
                # All Backend calls, including stop / integrity validation, happen
                # here. Browser polling only reads an in-memory snapshot.
                try:
                    with self._lock:
                        cancel = session.cancel_pending
                        session.cancel_pending = False
                    if cancel:
                        try:
                            receipt = self.runner.cancel(handle, "UI session requested cancellation")
                            self._publish(token, session, generation, cancel_receipt=receipt.to_dict(),
                                          action_error=None)
                        except Exception as error:
                            self._publish(token, session, generation, action_error=str(error))
                    snapshot = self.runner.status(handle)
                    with self._lock:
                        # A request may arrive while status() is in flight. Keep
                        # it visible until the next observation consumes it.
                        self._publish(token, session, generation, status=snapshot.status.value,
                                      cancel_requested=snapshot.cancel_requested or session.cancel_pending,
                                      reason=snapshot.reason, observation_error=None)
                except Exception as error:
                    self._publish(token, session, generation, status="UNKNOWN", observation_error=str(error))
                    time.sleep(self.poll_interval)
                    continue
                if snapshot.status.terminal:
                    try:
                        result = self.runner.collect(handle)
                    except Exception as error:
                        self._publish(token, session, generation, status="INTEGRITY_ERROR", error=str(error))
                    else:
                        self._publish(token, session, generation, status=result.status, result=result.to_dict())
                    break
                time.sleep(self.poll_interval)
        except Exception as error:
            self._publish(token, session, generation, status="ERROR", error=str(error))
        finally:
            staged.cleanup()
            with self._lock:
                session.active = False
            self._admission.release()

    def cancel(self, token, generation):
        with self._lock:
            session = self._session(token)
            if generation != session.generation:
                return "Stale cancel ignored; the selected job has changed."
            if not session.active or session.view.get("result") is not None:
                return "No active job in this session."
            session.cancel_pending = True
            session.view["cancel_requested"] = True
            return "cancel_requested; waiting for Backend confirmation."

    def open_run(self, token, run_id):
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("Enter a saved Run ID before opening a Run.")
        run_id = run_id.strip()
        try:
            location = run_path(self.runner.store.root, run_id)
        except (ValueError, AttributeError) as error:
            raise ValueError("Enter a valid saved Run ID (UUID), as shown after inference.") from error
        with self._lock:
            session = self._session(token)
            if session.active:
                raise BackendBusy("Wait for this session's job before selecting a saved Run")
            generation = self._select(session, "LOADING")
            session.view["load_notice"] = "Loading saved terminal Run; no inference is started."
        threading.Thread(target=self._load, args=(token, session, generation, location), daemon=True).start()
        return "Loading saved terminal Run; no inference is started."

    def load_error(self, token, error):
        with self._lock:
            self._session(token).view["load_notice"] = str(error)

    def _load(self, token, session, generation, location):
        try:
            data = read_json(contained_path(location, f"attempts/{ATTEMPT_ID}/handle.json"))
            handle = JobHandle(**{key: data[key] for key in JobHandle.__dataclass_fields__ if key in data})
            if handle.run_id != location.name:
                raise ValueError("Saved Run / handle identity mismatch")
            # Reading terminal Runs is part of the existing backend contract.
            # collect rejects active recovery and checks all paths and digests.
            result = self.runner.collect(handle)
            self._publish(token, session, generation, status=result.status, run_id=handle.run_id,
                          result=result.to_dict(), cancel_requested=result.status == "CANCELLED",
                          load_notice=f"Loaded saved Run {handle.run_id} · {result.status}.")
        except Exception as error:
            self._publish(token, session, generation, status="ERROR", error=str(error),
                          load_notice=f"Could not load saved Run: {error}")
