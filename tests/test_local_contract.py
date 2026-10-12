import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from mde.backends import LocalBackend
from mde.contracts import JobStatus, UnknownJob
from mde.environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
from mde.registry import ModelRegistry
from mde.runner import ExperimentRunner
from mde.storage import RunStore, inspect_depth, read_json

PROJECT = Path(__file__).resolve().parents[1]


class LocalContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mge-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(PROJECT, self.temporary.name)
        env_name = os.environ.get("MDE_TEST_CONDA_ENV", "mde-moge")
        env_prefix = os.environ.get("MDE_TEST_CONDA_PREFIX")
        resolver = EnvironmentResolver({"mde-moge": EnvironmentProfile(
            "mde-moge", name=None if env_prefix else env_name, prefix=env_prefix)})
        manager = WorkerManager(PROJECT, resolver, CondaLauncher())
        self.backend = LocalBackend(self.store.root, manager)
        self.runner = ExperimentRunner(ModelRegistry(PROJECT / "tests/fixtures/models"),
                                        self.backend, self.store, PROJECT)
        self.addCleanup(self.stop_workers)

    def stop_workers(self):
        for job in list(self.backend._jobs.values()):
            if job.worker and (job.worker.process.poll() is None or job.worker.group_alive()):
                job.worker.stop(0.1)

    def run_fake(self, action="success"):
        handle = self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu",
                                    parameters={"action": action})
        deadline = time.monotonic() + 45
        while not self.runner.status(handle).status.terminal:
            if time.monotonic() > deadline:
                self.fail("fake subprocess did not complete within test deadline")
            time.sleep(0.05)
        return handle, self.runner.collect(handle), self.store.root / handle.run_id

    def test_conda_subprocess_roundtrip_and_logs(self):
        handle, result, run = self.run_fake()
        self.assertEqual(result.status, "COMPLETED")
        self.assertNotEqual(result.execution["worker_pid"], os.getpid())
        self.assertNotEqual(result.execution["python_prefix"], sys.prefix)
        if os.environ.get("MDE_TEST_CONDA_PREFIX"):
            self.assertEqual(Path(result.execution["python_prefix"]).resolve(),
                             Path(os.environ["MDE_TEST_CONDA_PREFIX"]).resolve())
        else:
            self.assertEqual(result.execution["conda_environment"],
                             os.environ.get("MDE_TEST_CONDA_ENV", "mde-moge"))
        depth = run / result.outputs[0]["depth"]["path"]
        self.assertEqual(inspect_depth(depth), {"shape": [256, 256], "dtype": "float32"})
        with depth.open("rb") as stream:
            stream.seek(-4, 2)
            self.assertEqual(struct.unpack("<f", stream.read(4))[0], 2.5)
        self.assertEqual(read_json(run / "job.json"), read_json(run / "attempts/attempt-0001/job.json"))
        self.assertEqual(read_json(run / "attempts/attempt-0001/job-result.json")["status"], "COMPLETED")
        self.assertEqual(read_json(run / "run.json")["status"], "COMPLETED")
        self.assertEqual(read_json(run / "attempts/attempt-0001/status.json")["run_id"], handle.run_id)
        metadata = read_json(run / "output/attempt-0001/metadata.json")
        self.assertEqual(metadata["execution"]["worker_pid"], result.execution["worker_pid"])
        stdout = (run / "logs/attempt-0001/stdout.log").read_text()
        self.assertIn("fake predict: stdout", stdout)
        self.assertIn("fake unloaded", stdout)
        self.assertIn("fake predict: stderr", (run / "logs/attempt-0001/stderr.log").read_text())
        self.assertEqual(self.runner.collect(handle).to_dict(), result.to_dict())
        self.assertEqual(stdout.count("fake predict: stdout"), 1)

    def test_control_has_no_model_or_numeric_imports(self):
        info = ModelRegistry(PROJECT / "models").get_model("moge")
        self.assertEqual(info.model_id, "moge")
        for module in ("torch", "moge", "numpy", "PIL", "models.moge.adapter"):
            self.assertNotIn(module, sys.modules)

    def test_worker_exception_is_failed_and_cleanup_runs(self):
        handle, result, run = self.run_fake("raise")
        self.assertEqual(result.status, "FAILED")
        self.assertNotEqual(result.execution["exit_code"], 0)
        self.assertEqual(result.error["stage"], "predict")
        self.assertIn("intentional predict failure", (run / "logs/attempt-0001/stderr.log").read_text())
        self.assertIn("fake unloaded", (run / "logs/attempt-0001/stdout.log").read_text())

    def test_missing_depth_is_not_success(self):
        _, result, _ = self.run_fake("missing_depth")
        self.assertEqual(result.status, "FAILED")
        self.assertIn("Missing required depth", result.error["message"])
        self.assertEqual(result.outputs, [])

    def test_exit_zero_without_report_is_not_success(self):
        _, result, _ = self.run_fake("missing_result")
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.execution["exit_code"], 0)
        self.assertEqual(result.error["code"], "INVALID_RESULT")

    def test_exit_zero_with_missing_depth_file_is_not_success(self):
        handle = self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu")
        job = self.backend._jobs[handle.backend_job_id]
        self.assertEqual(job.worker.process.wait(timeout=45), 0)
        run = self.store.root / handle.run_id
        (run / "output/attempt-0001/views/view-0001/depth.npy").unlink()
        result = self.runner.collect(handle)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.execution["exit_code"], 0)
        self.assertEqual(result.error["code"], "INVALID_RESULT")

    def test_run_root_precedence_and_base(self):
        with patch.dict(os.environ, {"MDE_RUN_ROOT": "custom-runs"}):
            self.assertEqual(RunStore(PROJECT).root, PROJECT / "custom-runs")
            self.assertEqual(RunStore(PROJECT, "explicit-runs").root, PROJECT / "explicit-runs")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(RunStore(PROJECT).root, PROJECT / "runs")

    def test_cancel_capability_and_unknown_handle(self):
        self.assertTrue(self.backend.supports_cancel)
        with self.assertRaises(UnknownJob):
            self.backend.cancel(None)


if __name__ == "__main__":
    unittest.main()
