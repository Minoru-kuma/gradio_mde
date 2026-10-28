"""UI contracts without browser timing or model inference."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid

from mde.contracts import (BackendBusy, CancelReceipt, JobHandle, JobResult,
                           JobStatus, JobStatusSnapshot, utc_now)
from mde.registry import ModelRegistry
from mde.storage import RunStore, sha256_file, write_json
from mde.ui_controller import InferenceController, MAX_UPLOAD_BYTES, validate_upload, stage_upload

PROJECT = Path(__file__).resolve().parents[1]
IMAGE = PROJECT / "tests/assets/sample.png"
HAS_PIL = importlib.util.find_spec("PIL") is not None


class FakeRunner:
    def __init__(self, root):
        self.registry = ModelRegistry(PROJECT / "tests/fixtures/models")
        self.store = SimpleNamespace(root=root)
        self.entered, self.release = threading.Event(), threading.Event()
        self.handles, self.cancels, self.states = [], [], {}
        self.status_gate = None
        self.collect_error = False
        self.cancel_completes = False

    def submit(self, model, image, **options):
        self.entered.set()
        self.release.wait(5)
        handle = JobHandle(str(uuid.uuid4()), "attempt-0001", "local", str(uuid.uuid4()),
                           utc_now(), "key", "location", "local")
        self.handles.append(handle)
        self.states[handle.run_id] = JobStatus.RUNNING
        return handle

    def status(self, handle):
        if self.status_gate:
            self.status_gate.wait(5)
        return JobStatusSnapshot(self.states[handle.run_id], utc_now(), "fake", 1)

    def cancel(self, handle, reason):
        self.cancels.append(handle)
        state = JobStatus.COMPLETED if self.cancel_completes else JobStatus.CANCELLED
        self.states[handle.run_id] = state
        return CancelReceipt(not self.cancel_completes, utc_now(), state.value, self.cancel_completes)

    def collect(self, handle):
        if self.collect_error:
            raise ValueError("Digest mismatch")
        state = self.states[handle.run_id].value
        error = {"code": "TIMEOUT"} if state == "FAILED" else None
        return JobResult(handle.run_id, handle.attempt_id, "local", state, [], [], {}, None, utc_now(), error)


@unittest.skipUnless(HAS_PIL, "UI contract tests require the independent application environment")
class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner = FakeRunner(Path(self.temp.name))
        self.controller = InferenceController(self.runner, "fake", poll_interval=0.005)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.runner.release.set()
        if self.runner.status_gate:
            self.runner.status_gate.set()
        for session in list(self.controller._sessions.values()):
            if session.handle:
                self.runner.states[session.handle.run_id] = JobStatus.COMPLETED
        deadline = time.monotonic() + 5
        while self.controller._admission.locked() and time.monotonic() < deadline:
            for handle in self.runner.handles:
                self.runner.states[handle.run_id] = JobStatus.COMPLETED
            time.sleep(0.005)

    def submit(self, token="a", **options):
        request = dict(image=IMAGE, variant_id="fake-depth", device="cpu", dtype="float32",
                       parameters={}, timeout=30, outputs=["depth"])
        request.update(options)
        return self.controller.submit(token, **request)

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            self.assertLess(time.monotonic(), deadline, self.controller.snapshot("a"))
            time.sleep(0.005)

    def test_invalid_requests_rejected_before_runner(self):
        for options in ({"image": None}, {"variant_id": "unknown"}, {"device": "cuda:7"},
                        {"parameters": {"unknown": 1}}, {"parameters": []}, {"dtype": "float16"},
                        {"timeout": 0}, {"timeout": True}, {"outputs": ["points"]}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.submit(**options)
        self.assertFalse(self.runner.entered.is_set())
        self.assertFalse(self.controller._admission.locked())
        # The common Runner must still reject unknown values independently of UI.
        from mde.runner import ExperimentRunner
        store = RunStore(PROJECT, Path(self.temp.name) / "runner-runs")
        runner = ExperimentRunner(self.runner.registry, object(), store, PROJECT)
        for options in ({"variant_id": "unknown"}, {"device": "unknown"}, {"parameters": {"unknown": 1}}):
            with self.assertRaises(ValueError):
                runner.submit("fake", IMAGE, **options)
        self.assertFalse(store.root.exists())

    def test_png_corrupt_oversize_and_pixel_limits(self):
        path = Path(self.temp.name) / "bad.png"
        for data in (b"", b"not a png", IMAGE.read_bytes()[:33]):
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                validate_upload(path)
        with path.open("wb") as stream:
            stream.truncate(MAX_UPLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            validate_upload(path)
        data = bytearray(IMAGE.read_bytes()); data[16:24] = struct.pack(">II", 4096, 4096)
        path.write_bytes(data)
        with self.assertRaises(ValueError):
            validate_upload(path)
        self.assertEqual(validate_upload(IMAGE), IMAGE)

    def test_jpeg_conversion_and_png_identity(self):
        from PIL import Image, ImageOps
        root = Path(self.temp.name)
        png_dir = root / "png"; png_dir.mkdir()
        self.assertIsNone(stage_upload(IMAGE, png_dir))
        self.assertEqual((png_dir / "image.png").read_bytes(), IMAGE.read_bytes())
        for orientation in (1, 6):
            jpeg = root / f"{orientation}.jpeg"
            exif = Image.Exif(); exif[274] = orientation
            Image.new("RGB", (24, 12), (40, 80, 120)).save(jpeg, exif=exif)
            out = root / str(orientation); out.mkdir()
            provenance = stage_upload(jpeg, out)
            self.assertEqual(provenance["sha256"], sha256_file(jpeg))
            self.assertEqual(provenance["exif_orientation"], orientation)
            with Image.open(jpeg) as source, Image.open(out / "image.png") as converted:
                expected = ImageOps.exif_transpose(source).convert("RGB")
                self.assertEqual(converted.mode, "RGB")
                self.assertEqual(converted.size, expected.size)
                self.assertEqual(converted.tobytes(), expected.tobytes())
        bad = root / "bad.jpg"; bad.write_bytes(jpeg.read_bytes()[:-20])
        with self.assertRaises(ValueError):
            validate_upload(bad)
        huge = root / "huge.jpg"
        Image.new("RGB", (4097, 2)).save(huge)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            validate_upload(huge)

    def test_immediate_busy_no_queued_inference_and_session_cancel(self):
        self.submit()
        self.assertTrue(self.runner.entered.wait(1))
        start = time.monotonic()
        with self.assertRaises(BackendBusy):
            self.submit("b")
        self.assertLess(time.monotonic() - start, 0.1)
        self.assertIn("No active", self.controller.cancel("b", 0))
        self.assertEqual(self.controller.snapshot("b")["status"], "IDLE")
        # Request cancellation before Runner even returns a handle.
        self.assertIn("cancel_requested", self.controller.cancel("a", 1))
        self.runner.release.set()
        self.wait(lambda: not self.controller._admission.locked())
        self.assertEqual(self.controller.snapshot("a")["status"], "CANCELLED")
        self.assertEqual(len(self.runner.handles), 1)
        time.sleep(0.03)
        self.assertEqual(len(self.runner.handles), 1)  # rejected request never starts later
        self.submit("b")
        self.wait(lambda: len(self.runner.handles) == 2)
        self.runner.states[self.runner.handles[-1].run_id] = JobStatus.COMPLETED
        self.wait(lambda: not self.controller._admission.locked())
        self.assertEqual(self.controller.snapshot("b")["status"], "COMPLETED")
        self.assertNotEqual(self.controller.snapshot("a")["run_id"], self.controller.snapshot("b")["run_id"])

    def test_poll_and_cancel_never_wait_for_slow_backend(self):
        self.controller.poll_interval = 0.1
        self.runner.status_gate = threading.Event()
        self.runner.release.set()
        self.submit()
        self.wait(lambda: bool(self.runner.handles))
        start = time.monotonic()
        self.assertEqual(self.controller.snapshot("a")["progress"], "unavailable (indeterminate while running)")
        self.controller.cancel("a", 1)
        self.assertLess(time.monotonic() - start, 0.1)
        self.runner.status_gate.set()
        self.wait(lambda: self.controller.snapshot("a")["status"] == "RUNNING")
        self.assertTrue(self.controller.snapshot("a")["cancel_requested"])
        self.wait(lambda: not self.controller._admission.locked())

    def test_status_results_missing_metrics_and_failure(self):
        self.runner.release.set()
        for state in (JobStatus.QUEUED, JobStatus.UNKNOWN, JobStatus.RUNNING):
            if not self.runner.handles:
                self.submit()
                self.wait(lambda: bool(self.runner.handles))
            self.runner.states[self.runner.handles[0].run_id] = state
            self.wait(lambda: self.controller.snapshot("a")["status"] == state.value)
        self.runner.states[self.runner.handles[0].run_id] = JobStatus.FAILED
        self.wait(lambda: not self.controller._admission.locked())
        result = self.controller.snapshot("a")["result"]
        self.assertEqual(result["error"]["code"], "TIMEOUT")
        self.assertEqual(result["metrics"], {})

    def test_terminal_integrity_failure_has_no_results(self):
        self.runner.release.set(); self.runner.collect_error = True
        self.submit(); self.wait(lambda: bool(self.runner.handles))
        self.runner.states[self.runner.handles[0].run_id] = JobStatus.COMPLETED
        self.wait(lambda: not self.controller._admission.locked())
        self.assertEqual(self.controller.snapshot("a")["status"], "INTEGRITY_ERROR")
        self.assertIsNone(self.controller.snapshot("a")["result"])

    def test_completion_cancel_race_and_stale_cancel(self):
        self.runner.release.set(); self.runner.cancel_completes = True
        self.submit(); self.wait(lambda: bool(self.runner.handles))
        self.controller.cancel("a", 1)
        self.wait(lambda: not self.controller._admission.locked())
        self.assertEqual(self.controller.snapshot("a")["status"], "COMPLETED")
        self.submit(); self.wait(lambda: len(self.runner.handles) == 2)
        self.assertIn("Stale", self.controller.cancel("a", 1))
        self.assertEqual(len(self.runner.cancels), 1)
        self.assertEqual(self.controller.snapshot("a")["generation"], 2)

    def test_old_load_completion_and_forgotten_session_do_not_publish(self):
        entered, release, old_done = threading.Event(), threading.Event(), threading.Event()
        handles = []
        for _ in range(2):
            run_id = str(uuid.uuid4())
            handle = JobHandle(run_id, "attempt-0001", "local", str(uuid.uuid4()), utc_now(), "key", run_id, "local")
            handles.append(handle)
            self.runner.states[run_id] = JobStatus.COMPLETED
            write_json(self.runner.store.root / run_id / "attempts/attempt-0001/handle.json", handle.to_dict())
        original = self.runner.collect
        def delayed(handle):
            if handle == handles[0]:
                entered.set()
                release.wait(5)
                old_done.set()
            return original(handle)
        self.runner.collect = delayed
        self.addCleanup(release.set)
        self.controller.open_run("a", handles[0].run_id)
        self.assertTrue(entered.wait(1))
        self.controller.open_run("a", handles[1].run_id)
        self.wait(lambda: self.controller.snapshot("a")["run_id"] == handles[1].run_id)
        release.set()
        self.assertTrue(old_done.wait(1))
        time.sleep(0.02)
        self.assertEqual(self.controller.snapshot("a")["run_id"], handles[1].run_id)
        # A load already in flight must not recreate a disconnected session.
        entered.clear(); release.clear(); old_done.clear()
        self.controller.open_run("a", handles[0].run_id)
        self.assertTrue(entered.wait(1))
        self.controller.forget("a")
        release.set()
        self.assertTrue(old_done.wait(1))
        time.sleep(0.02)
        self.assertEqual(self.controller.snapshot("a")["status"], "IDLE")

    def test_disconnect_is_not_cancel(self):
        self.submit(); self.runner.release.set()
        self.wait(lambda: bool(self.runner.handles))
        self.controller.forget("a")
        self.assertEqual(self.runner.cancels, [])
        self.runner.states[self.runner.handles[0].run_id] = JobStatus.COMPLETED
        self.wait(lambda: not self.controller._admission.locked())
        self.assertEqual(self.controller.snapshot("a")["status"], "IDLE")


@unittest.skipUnless(HAS_PIL, "UI contract tests require the independent application environment")
class UILocalContractTests(unittest.TestCase):
    def setUp(self):
        from tests.test_local_contract import LocalContractTests
        # Reuse setup/cleanup, without inheriting and rerunning all Phase 01 tests.
        self.stop_workers = lambda: LocalContractTests.stop_workers(self)
        LocalContractTests.setUp(self)
        self.controller = InferenceController(self.runner, "fake", poll_interval=0.02)

    def wait(self, token, predicate):
        deadline = time.monotonic() + 30
        while not predicate(self.controller.snapshot(token)):
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)

    def submit(self, token, action="success", timeout=30):
        return self.controller.submit(token, IMAGE, "fake-depth", "cpu", "float32", {"action": action}, timeout, ["depth"])

    def test_jpeg_saved_provenance_and_integrity(self):
        from PIL import Image
        from mde.storage import read_json
        from mde.contracts import ArtifactIntegrityError
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        jpeg = Path(temp.name) / "source.jpg"
        exif = Image.Exif(); exif[274] = 6
        Image.new("RGB", (32, 16), (32, 80, 140)).save(jpeg, exif=exif)
        self.controller.submit("jpeg", jpeg, "fake-depth", "cpu", "float32", {}, 30, ["depth"])
        self.wait("jpeg", lambda v: v["result"] is not None)
        view = self.controller.snapshot("jpeg")
        self.assertEqual(view["status"], "COMPLETED")
        run = self.store.root / view["run_id"]
        source = read_json(run / "job.json")["inputs"][0]
        self.assertEqual(source["source"]["sha256"], sha256_file(jpeg))
        self.assertEqual((run / source["source"]["path"]).read_bytes(), jpeg.read_bytes())
        self.assertEqual(source["original_size"], {"width": 16, "height": 32})
        (run / source["source"]["path"]).write_bytes(b"tampered")
        with self.assertRaises(ArtifactIntegrityError):
            self.runner.collect(self.controller._sessions["jpeg"].handle)

    def test_real_backend_session_busy_cancel_failure_timeout_and_next_job(self):
        self.submit("a", "block")
        self.wait("a", lambda v: v["status"] == "RUNNING")
        with self.assertRaises(BackendBusy):
            self.submit("b")
        self.controller.cancel("b", 0)
        self.assertEqual(self.controller.snapshot("a")["status"], "RUNNING")
        self.controller.cancel("a", 1)
        self.wait("a", lambda v: v["result"] is not None)
        self.assertEqual(self.controller.snapshot("a")["status"], "CANCELLED")
        for action, timeout, expected in (("raise", 30, "FAILED"), ("block", 1, "FAILED"), ("success", 30, "COMPLETED")):
            # Admission release follows terminal publication immediately.
            while self.controller._admission.locked():
                time.sleep(0.005)
            self.submit("b", action, timeout)
            self.wait("b", lambda v: v["result"] is not None)
            self.assertEqual(self.controller.snapshot("b")["status"], expected)
            if timeout == 1:
                self.assertEqual(self.controller.snapshot("b")["result"]["error"]["code"], "TIMEOUT")
        self.assertEqual(self.controller.snapshot("a")["status"], "CANCELLED")

    def test_concurrent_saved_load_readonly_and_active_recovery_rejected(self):
        self.submit("a")
        self.wait("a", lambda v: v["result"] is not None)
        run_id = self.controller.snapshot("a")["run_id"]
        run = self.store.root / run_id
        before = {p.relative_to(run): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
        for token in ("b", "c"):
            self.controller.open_run(token, run_id)
        for token in ("b", "c"):
            self.wait(token, lambda v: v["result"] is not None)
            self.assertEqual(self.controller.snapshot(token)["run_id"], run_id)
        after = {p.relative_to(run): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        with self.assertRaises(ValueError):
            self.controller.open_run("b", "../escape")
        # A different backend can only reopen terminal persisted results.
        from mde.backends import LocalBackend
        from mde.runner import ExperimentRunner
        reader = InferenceController(ExperimentRunner(self.runner.registry, LocalBackend(self.store.root),
                                                     self.store, PROJECT), "fake")
        reader.open_run("reader", run_id)
        deadline = time.monotonic() + 5
        while reader.snapshot("reader")["result"] is None:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        self.assertEqual(reader.snapshot("reader")["run_id"], run_id)
        while self.controller._admission.locked():
            time.sleep(0.005)
        self.submit("active", "block")
        self.wait("active", lambda v: bool(v["run_id"]))
        active_id = self.controller.snapshot("active")["run_id"]
        reader.open_run("rejected", active_id)
        deadline = time.monotonic() + 5
        while reader.snapshot("rejected")["status"] == "LOADING":
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.01)
        self.assertEqual(reader.snapshot("rejected")["status"], "ERROR")
        self.assertIn("Active job recovery", reader.snapshot("rejected")["error"])
        self.controller.cancel("active", 1)
        self.wait("active", lambda v: v["result"] is not None)
