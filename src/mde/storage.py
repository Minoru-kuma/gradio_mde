"""Filesystem records and integrity checks, without numerical dependencies."""
import ast
import hashlib
import json
import os
import shutil
import struct
import uuid
import math
import re
from datetime import datetime
from pathlib import Path

from .contracts import ArtifactIntegrityError, ATTEMPT_ID, SCHEMA_VERSION, VIEW_ID, check_schema


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"Duplicate JSON key: {key}")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON scalar: {value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Non-finite JSON number")
        return number

    value = json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                       parse_constant=invalid_constant, parse_float=finite_float)
    if not isinstance(value, dict):
        raise ValueError("JSON record must be an object")
    return value


def run_path(root: Path, run_id: str) -> Path:
    # Accept only the canonical UUID created by Runner.
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("Invalid Run ID")
    return contained_path(Path(root), run_id)


def contained_path(run: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise ArtifactIntegrityError("Invalid relative reference")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ArtifactIntegrityError("Run references must be relative and contained")
    resolved = (run / path).resolve()
    if not resolved.is_relative_to(run.resolve()):
        raise ArtifactIntegrityError("Reference escapes Run Directory")
    return resolved


def artifact_ref(run: Path, path: Path, **metadata) -> dict:
    return {"path": path.relative_to(run).as_posix(), "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size, **metadata}


def inspect_png(path: Path) -> tuple[int, int]:
    with Path(path).open("rb") as stream:
        header = stream.read(33)
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("01A requires a PNG image; worker checks image decoding")
    width, height = struct.unpack(">II", header[16:24])
    if min(width, height) < 1:
        raise ValueError("Empty image")
    return width, height


def inspect_depth(path: Path) -> dict:
    """Read the NPY header with stdlib; do not import NumPy in control."""
    with path.open("rb") as stream:
        if stream.read(6) != b"\x93NUMPY":
            raise ArtifactIntegrityError("Invalid NPY magic")
        version = stream.read(2)
        if version not in (b"\x01\x00", b"\x02\x00"):
            raise ArtifactIntegrityError("Unsupported NPY version")
        length_size = 2 if version[0] == 1 else 4
        length = int.from_bytes(stream.read(length_size), "little")
        if length > 4096:
            raise ArtifactIntegrityError("Unexpected NPY header size")
        info = ast.literal_eval(stream.read(length).decode("latin1"))
        shape = info["shape"]
        if info["descr"] != "<f4" or info["fortran_order"] or len(shape) != 2 or min(shape) < 1:
            raise ArtifactIntegrityError("Depth must be C-contiguous float32 [H,W]")
        if path.stat().st_size != stream.tell() + shape[0] * shape[1] * 4:
            raise ArtifactIntegrityError("Depth payload size mismatch")
    return {"shape": list(shape), "dtype": "float32"}


def validate_outputs(run: Path, report: dict) -> None:
    outputs = report.get("outputs", [])
    if len(outputs) != 1 or outputs[0].get("view_id") != VIEW_ID:
        raise ArtifactIntegrityError("Expected exactly one output view")
    output = outputs[0]
    depth = output["depth"]
    artifacts = report.get("artifacts", [])
    paths = set()
    prefix = f"output/{ATTEMPT_ID}/"
    for ref in artifacts:
        validate_artifact(run, ref)
        if not ref["path"].startswith(prefix) or ref["path"] in paths:
            raise ArtifactIntegrityError("Wrong attempt or duplicate artifact path")
        paths.add(ref["path"])
    expected_depth = f"{prefix}views/{VIEW_ID}/depth.npy"
    expected_metadata = f"{prefix}metadata.json"
    if depth["path"] != expected_depth or expected_metadata not in paths:
        raise ArtifactIntegrityError("Missing required depth / metadata artifact reference")
    if depth not in artifacts:
        raise ArtifactIntegrityError("Depth reference missing or inconsistent with artifact list")
    path = contained_path(run, depth["path"])
    if sha256_file(path) != depth["sha256"] or path.stat().st_size != depth["size_bytes"]:
        raise ArtifactIntegrityError("Depth integrity mismatch")
    info = inspect_depth(path)
    if depth["shape"] != info["shape"] or depth["dtype"] != info["dtype"]:
        raise ArtifactIntegrityError("Depth manifest/header mismatch")
    metadata = output["metadata"]
    if metadata["shape"] != info["shape"] or metadata["dtype"] != info["dtype"]:
        raise ArtifactIntegrityError("Depth metadata/header mismatch")
    if metadata["depth_kind"] not in ("z_depth", "ray_distance"):
        raise ArtifactIntegrityError("Unknown depth kind")
    if metadata["scale_type"] not in ("metric", "relative", "unknown"):
        raise ArtifactIntegrityError("Unknown scale type")
    if depth["unit"] != metadata["depth_unit"]:
        raise ArtifactIntegrityError("Depth unit mismatch")
    units = {"metric": "m", "relative": "arbitrary", "unknown": "unknown"}
    if metadata["depth_unit"] != units[metadata["scale_type"]]:
        raise ArtifactIntegrityError("Scale / unit mismatch")
    if metadata.get("camera_frame") != "opencv_x_right_y_down_z_forward":
        raise ArtifactIntegrityError("Invalid camera frame")
    if metadata.get("output_size") != {"height": info["shape"][0], "width": info["shape"][1]}:
        raise ArtifactIntegrityError("Output dimensions mismatch")
    from .geometry import validate_geometry
    validate_geometry(run, report)
    document = read_json(contained_path(run, expected_metadata))
    check_schema(document)
    if document.get("run_id") != report["run_id"] or document.get("attempt_id") != report["attempt_id"]:
        raise ArtifactIntegrityError("Metadata identity mismatch")
    if document.get("views") != [metadata]:
        raise ArtifactIntegrityError("Metadata / output mismatch")
    worker_execution = dict(report["execution"])
    for key in ("backend_job_id", "exit_code", "manager_instance", "process_cleanup"):
        worker_execution.pop(key, None)
    if document.get("execution") != worker_execution:
        raise ArtifactIntegrityError("Runtime metadata mismatch")


def validate_artifact(run: Path, ref: dict) -> None:
    if not isinstance(ref, dict) or not isinstance(ref.get("media_type"), str):
        raise ArtifactIntegrityError("Malformed artifact reference")
    if type(ref.get("size_bytes")) is not int or ref["size_bytes"] < 0:
        raise ArtifactIntegrityError("Invalid artifact size")
    if not isinstance(ref.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
        raise ArtifactIntegrityError("Invalid artifact checksum")
    path = contained_path(run, ref.get("path"))
    if not path.is_file() or path.stat().st_size != ref["size_bytes"] or sha256_file(path) != ref["sha256"]:
        raise ArtifactIntegrityError(f"Artifact mismatch: {ref['path']}")


def validate_report(report: dict, run_id: str, attempt_id: str, *, terminal=False) -> None:
    check_schema(report)
    if report.get("run_id") != run_id or report.get("attempt_id") != attempt_id:
        raise ArtifactIntegrityError("Result identity mismatch")
    state = report.get("status" if terminal else "outcome")
    if state not in (("COMPLETED", "FAILED", "CANCELLED") if terminal else ("COMPLETED", "FAILED")):
        raise ArtifactIntegrityError("Invalid result state")
    for key, expected in (("outputs", list), ("artifacts", list), ("execution", dict),
                          ("warnings", list), ("metrics", dict)):
        if not isinstance(report.get(key, {} if key == "metrics" else None), expected):
            raise ArtifactIntegrityError(f"Invalid result field: {key}")
    if any(not isinstance(warning, str) for warning in report["warnings"]):
        raise ArtifactIntegrityError("Invalid warnings")
    for key in ("started_at", "finished_at"):
        value = report.get(key)
        if key == "started_at" and value is None and terminal:
            continue
        if not isinstance(value, str) or datetime.fromisoformat(value).tzinfo is None:
            raise ArtifactIntegrityError(f"Invalid timestamp: {key}")
    error = report.get("error")
    if state == "COMPLETED":
        if error is not None:
            raise ArtifactIntegrityError("Completed result contains an error")
    elif not isinstance(error, dict) or any(not isinstance(error.get(key), str) for key in ("code", "stage", "message")) or type(error.get("retryability")) is not bool:
        raise ArtifactIntegrityError("Malformed failure error")
    for metric in report.get("metrics", {}).values():
        if (not isinstance(metric, dict) or type(metric.get("value")) not in (int, float)
                or not math.isfinite(metric["value"]) or metric["value"] < 0
                or not isinstance(metric.get("unit"), str) or not isinstance(metric.get("scope"), str)):
            raise ArtifactIntegrityError("Malformed metric / unit / scope")


def validate_job_files(run: Path, spec) -> None:
    for relative in ("job.json", f"attempts/{spec.attempt_id}/job.json"):
        if read_json(contained_path(run, relative)) != spec.to_dict():
            raise ArtifactIntegrityError("Persisted JobSpec mismatch")
    source = spec.inputs[0]
    path = contained_path(run, source["path"])
    if sha256_file(path) != source["sha256"]:
        raise ArtifactIntegrityError("Input checksum mismatch")
    width, height = inspect_png(path)
    if source["original_size"] != {"width": width, "height": height}:
        raise ArtifactIntegrityError("Input dimensions mismatch")


class RunStore:
    def __init__(self, project_root: Path, root: str | Path | None = None):
        base = Path(project_root).resolve()
        chosen = Path(root if root is not None else os.environ.get("MDE_RUN_ROOT", "runs"))
        self.root = (chosen if chosen.is_absolute() else base / chosen).resolve()

    def prepare(self, run_id: str, image: Path) -> Path:
        run = run_path(self.root, run_id)
        run.mkdir(parents=True, exist_ok=False)
        for relative in (f"input/views/{VIEW_ID}", f"attempts/{ATTEMPT_ID}",
                         f"output/{ATTEMPT_ID}/views/{VIEW_ID}", f"logs/{ATTEMPT_ID}"):
            (run / relative).mkdir(parents=True)
        shutil.copyfile(image, run / "input" / "views" / VIEW_ID / "image.png")
        write_json(run / "run.json", {"schema_version": SCHEMA_VERSION, "run_id": run_id,
                   "selected_attempt_id": ATTEMPT_ID, "status": "QUEUED"})
        return run
