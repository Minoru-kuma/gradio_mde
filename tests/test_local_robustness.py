import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch, Mock

from mde.backends import LocalBackend
from mde.contracts import (ArtifactIntegrityError, BackendBusy, JobHandle, JobSpec,
                           ResultNotReady, UnknownJob, UnsupportedOperation)
from mde.storage import read_json, write_json, sha256_file, contained_path, artifact_ref
from tests import test_local_contract as contract

PROJECT = contract.PROJECT


class LocalRobustnessTests(unittest.TestCase):
    setUp = contract.LocalContractTests.setUp
    stop_workers = contract.LocalContractTests.stop_workers
    run_fake = contract.LocalContractTests.run_fake

    def start_block(self, action="stubborn", timeout=None):
        self.backend.stop_grace_seconds = 0.2
        handle = self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu",
                                    parameters={"action": action}, walltime_seconds=timeout)
        job = self.backend._jobs[handle.backend_job_id]
        log = job.run / "logs/attempt-0001/stdout.log"
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            for line in log.read_text().splitlines():
                if line.startswith("fake child ready: "):
                    return handle, job, json.loads(line.removeprefix("fake child ready: "))
            if job.worker.process.poll() is not None:
                self.fail("blocking fixture exited before readiness")
            time.sleep(0.02)
        self.fail("worker readiness deadline")

    def assert_stopped(self, job, pids):
        self.assertIsNotNone(job.worker.process.poll())
        self.assertFalse(job.worker.group_alive())
        for pid in pids.values():
            path = Path(f"/proc/{pid}/stat")
            deadline = time.monotonic() + 3
            while path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(path.exists(), f"Child PID {pid} remains after stop")

    def test_cancel_reaps_wrapper_and_stops_stubborn_worker_and_child(self):
        handle, job, pids = self.start_block()
        with self.assertRaises(ResultNotReady):
            self.runner.collect(handle)
        receipt = self.runner.cancel(handle, "test cancel")
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.status, "CANCELLED")
        self.assert_stopped(job, pids)
        result = self.runner.collect(handle)
        self.assertEqual(result.error["code"], "CANCELLED")
        self.assertTrue(result.execution["process_cleanup"]["sigkill_used"])
        self.assertTrue(self.runner.status(handle).cancel_requested)
        self.assertTrue(self.runner.cancel(handle).already_terminal)
        self.assertEqual(LocalBackend(self.store.root).collect(handle).to_dict(), result.to_dict())

    def test_graceful_cancel_stops_worker_and_child_without_sigkill(self):
        handle, job, pids = self.start_block("gentle")
        self.runner.cancel(handle)
        self.assert_stopped(job, pids)
        self.assertFalse(self.runner.collect(handle).execution["process_cleanup"]["sigkill_used"])

    def test_timeout_runs_without_status_polling_and_stops_children(self):
        handle, job, pids = self.start_block(timeout=4)
        # No status calls: the independent execution timer must enforce the limit.
        deadline = time.monotonic() + 10
        while not (job.run / "attempts/attempt-0001/job-result.json").exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        result = self.runner.collect(handle)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error["code"], "TIMEOUT")
        self.assertFalse(self.runner.status(handle).cancel_requested)
        self.assert_stopped(job, pids)
        self.assertTrue(result.execution["process_cleanup"]["sigkill_used"])
        self.assertEqual(LocalBackend(self.store.root).collect(handle).to_dict(), result.to_dict())

    def test_wrapper_exit_does_not_leave_orphan_child(self):
        handle, job, pids = self.start_block("orphan")
        job.worker.process.wait(timeout=20)
        result = self.runner.collect(handle)
        self.assertEqual(result.status, "FAILED")
        self.assert_stopped(job, pids)
        self.assertTrue(result.execution["process_cleanup"]["sigkill_used"])

    def test_busy_idempotency_and_reuse_after_cancel(self):
        handle, job, _ = self.start_block("block")
        self.assertEqual(self.backend.submit(job.spec), handle)
        with self.assertRaises(ValueError):
            self.backend.submit(replace(job.spec, inference={**job.spec.inference, "seed": 1}))
        with self.assertRaises(BackendBusy):
            self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu")
        self.runner.cancel(handle)
        _, result, _ = self.run_fake()
        self.assertEqual(result.status, "COMPLETED")

    def test_cancel_after_worker_completion_keeps_completed(self):
        handle = self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu")
        job = self.backend._jobs[handle.backend_job_id]
        job.worker.process.wait(timeout=20)
        receipt = self.runner.cancel(handle)
        self.assertTrue(receipt.already_terminal)
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(self.runner.collect(handle).status, "COMPLETED")

    def test_failed_stop_does_not_finalize_or_release_busy_guard(self):
        handle, job, _ = self.start_block()
        with patch.object(job.worker, "stop", side_effect=RuntimeError("stop not confirmed")):
            with self.assertRaises(RuntimeError):
                self.runner.cancel(handle)
            self.assertEqual(self.runner.status(handle).status.value, "RUNNING")
            with self.assertRaises(BackendBusy):
                self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu")
            self.assertFalse((job.run / "attempts/attempt-0001/job-result.json").exists())
        self.runner.cancel(handle)

    def test_saved_terminal_recollect_is_read_only_and_no_inference(self):
        handle, result, run = self.run_fake()
        files_before = {str(path): (sha256_file(path), path.stat().st_mtime_ns)
                        for path in run.rglob("*") if path.is_file()}
        manager = Mock()
        fresh = LocalBackend(self.store.root, manager)
        self.assertEqual(fresh.collect(handle).to_dict(), result.to_dict())
        self.assertEqual(fresh.collect(handle).to_dict(), result.to_dict())
        manager.start.assert_not_called()
        self.assertEqual(files_before, {str(path): (sha256_file(path), path.stat().st_mtime_ns)
                                       for path in run.rglob("*") if path.is_file()})
        stdout = (run / "logs/attempt-0001/stdout.log").read_text()
        self.assertEqual(stdout.count("fake predict: stdout"), 1)
        with self.assertRaises(UnknownJob):
            fresh.collect(replace(handle, backend_job_id="wrong"))

    def test_active_handle_is_not_recovered_by_new_backend(self):
        handle, _, _ = self.start_block()
        with self.assertRaises(UnsupportedOperation):
            LocalBackend(self.store.root).status(handle)
        self.runner.cancel(handle)

    def test_01a_saved_result_without_new_measurements_is_compatible(self):
        handle, _, run = self.run_fake()
        metadata_path = run / "output/attempt-0001/metadata.json"
        metadata = read_json(metadata_path)
        metadata["execution"].pop("environment_fingerprint")
        write_json(metadata_path, metadata)
        worker_path = run / "output/attempt-0001/result.json"
        worker = read_json(worker_path)
        worker["execution"].pop("environment_fingerprint")
        worker["metrics"] = {}
        worker["artifacts"][1] = artifact_ref(run, metadata_path, media_type="application/json")
        write_json(worker_path, worker)
        terminal_path = run / "attempts/attempt-0001/job-result.json"
        terminal = read_json(terminal_path)
        terminal["execution"].pop("environment_fingerprint")
        terminal["execution"].pop("process_cleanup")
        terminal["metrics"] = {}
        terminal["artifacts"] = worker["artifacts"]
        terminal["future_optional"] = "ignored by major-1 reader"
        write_json(terminal_path, terminal)
        result = LocalBackend(self.store.root).collect(handle)
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.metrics, {})

    def test_corrupt_saved_terminal_and_worker_metadata_are_rejected(self):
        handle, _, run = self.run_fake()
        terminal = run / "attempts/attempt-0001/job-result.json"
        before = terminal.read_bytes()
        for content in ("[]", "{invalid", json.dumps({**json.loads(before), "status": "RUNNING"})):
            terminal.write_text(content)
            with self.assertRaises(ArtifactIntegrityError):
                LocalBackend(self.store.root).collect(handle)
        terminal.write_bytes(before)
        worker = run / "output/attempt-0001/result.json"
        worker.write_text("[]")
        with self.assertRaises(ArtifactIntegrityError):
            self.backend.collect(handle)

    def test_metrics_and_environment_fingerprint_cpu(self):
        _, result, run = self.run_fake()
        for key in ("load_seconds", "predict_seconds", "serialization_seconds", "unload_seconds",
                    "metadata_serialization_seconds", "worker_seconds"):
            self.assertGreater(result.metrics[key]["value"], 0)
            self.assertEqual(result.metrics[key]["unit"], "s")
            self.assertTrue(result.metrics[key]["scope"])
        self.assertNotIn("cuda_peak_allocated_bytes", result.metrics)
        data = result.execution["environment_fingerprint"]
        self.assertEqual(data["definition_digest"], sha256_file(PROJECT / "models/moge/environment.yml"))
        self.assertIn({"name": "numpy", "version": "1.26.4"}, data["packages"])
        self.assertTrue(data["conda_packages"])
        for key in ("package_list_digest", "conda_package_list_digest", "fingerprint_digest"):
            self.assertEqual(len(data[key]), 64)
        self.assertNotIn("environ", data)
        self.assertEqual(read_json(run / "output/attempt-0001/metadata.json")["execution"]["environment_fingerprint"], data)

    def test_invalid_worker_reports_are_failed_without_secondary_crash(self):
        handle = self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu")
        job = self.backend._jobs[handle.backend_job_id]
        job.worker.process.wait(timeout=20)
        path = job.run / "output/attempt-0001/result.json"
        original = read_json(path)
        candidates = [[], {**original, "run_id": "wrong"}, {**original, "outcome": "UNKNOWN"},
                      {**original, "execution": []}, {**original, "warnings": [None]},
                      {**original, "outcome": "FAILED", "error": {"message": "incomplete"}},
                      {**original, "artifacts": None}, {**original, "outputs": []},
                      {**original, "metrics": {"bad": {"value": -1}}}]
        # Each reader is tested before terminal publication; remove only test-owned
        # backend records to test another malformed report against the same output.
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                path.write_text(json.dumps(candidate))
                job.result = None
                result = self.runner.collect(handle)
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.error["code"], "INVALID_RESULT")
        for content in ('{"schema_version":', '{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
            path.write_text(content)
            job.result = None
            self.assertEqual(self.runner.collect(handle).error["code"], "INVALID_RESULT")

    def test_artifact_corruption_paths_and_missing_metadata_fail(self):
        handle = self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu")
        job = self.backend._jobs[handle.backend_job_id]
        job.worker.process.wait(timeout=20)
        path = job.run / "output/attempt-0001/result.json"
        original = read_json(path)
        for mutation in ("checksum", "absolute", "parent", "wrong_attempt", "no_metadata", "bad_unit", "bad_shape"):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(original)
                ref = data["outputs"][0]["depth"]
                if mutation == "checksum": ref["sha256"] = "0" * 64
                if mutation == "absolute": ref["path"] = "/tmp/depth.npy"
                if mutation == "parent": ref["path"] = "../depth.npy"
                if mutation == "wrong_attempt": ref["path"] = "output/attempt-0002/views/view-0001/depth.npy"
                if mutation == "no_metadata": data["artifacts"] = data["artifacts"][:1]
                if mutation == "bad_unit": data["outputs"][0]["metadata"]["depth_unit"] = "m"
                if mutation == "bad_shape": ref["shape"] = [1, 1]
                write_json(path, data)
                job.result = None
                self.assertEqual(self.runner.collect(handle).error["code"], "INVALID_RESULT")
        depth_path = job.run / original["outputs"][0]["depth"]["path"]
        with depth_path.open("r+b") as stream:
            stream.seek(-1, 2)
            stream.write(b"\xff")
        write_json(path, original)
        job.result = None
        self.assertEqual(self.runner.collect(handle).error["code"], "INVALID_RESULT")

    def test_post_terminal_tampering_raises_integrity_error_immutable_status(self):
        handle, _, run = self.run_fake()
        depth = run / "output/attempt-0001/views/view-0001/depth.npy"
        depth.write_bytes(b"corrupt")
        for backend in (self.backend, LocalBackend(self.store.root)):
            with self.assertRaises(ArtifactIntegrityError):
                backend.collect(handle)
            self.assertEqual(backend.status(handle).status.value, "COMPLETED")
        self.assertEqual(read_json(run / "attempts/attempt-0001/job-result.json")["status"], "COMPLETED")

    def test_symlinks_cannot_escape_run(self):
        run = self.store.root / "path-test"
        run.mkdir()
        (run / "outside").symlink_to(PROJECT / "tests/assets/sample.png")
        for reference in ("outside", "../sample.png", "/tmp/sample.png", "", "x\\y"):
            with self.assertRaises(ArtifactIntegrityError):
                contained_path(run, reference)

    def test_malformed_jobs_resources_and_environment_are_rejected(self):
        handle, _, _ = self.run_fake()
        spec = self.backend._jobs[handle.backend_job_id].spec
        for changed in ({"run_id": "../../bad"}, {"inference": {}}, {"environment_ref": {}},
                        {"request_digest": "bad"}, {"inputs": [{"view_id": "wrong"}]}):
            with self.subTest(changed=changed), self.assertRaises((ValueError, KeyError, TypeError, UnsupportedOperation)):
                JobSpec.from_dict({**spec.to_dict(), **changed})
        for resources in ({"walltime_seconds": 0}, {"walltime_seconds": True}, {"gpu_count": 2},
                          {"cpu_count": 0}, {"gpu_type": "A100"}, {"host_memory_mib": 100}, {"unexpected": 1}):
            with self.subTest(resources=resources), self.assertRaises((ValueError, UnsupportedOperation)):
                self.backend.submit(replace(spec, resources=resources))
        manager = self.backend.manager
        with self.assertRaises(ValueError):
            manager.resolver.resolve({"environment_id": "missing"})
        with self.assertRaises(ValueError):
            manager.start({**spec.environment_ref, "definition_digest": "0" * 64}, Path("unused"), self.store.root)

    def test_cli_collect_needs_no_conda_and_rejects_active_or_invalid_timeout(self):
        handle, result, run = self.run_fake()
        environment = {**os.environ, "PYTHONPATH": str(PROJECT / "src"), "MDE_CONDA_EXE": "/missing/conda"}
        response = subprocess.run([sys.executable, "-m", "mde.cli", "collect", "--run-id", handle.run_id,
                                   "--run-root", str(self.store.root)], env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(json.loads(response.stdout), result.to_dict())
        from mde.cli import main
        with patch("sys.stderr") as stderr:
            self.assertEqual(main(["run", "--model", "fake", "--input", "unused", "--timeout-seconds", "0"]), 2)
            self.assertIn("positive integer", stderr.write.call_args_list[0].args[0])

    def cli_fixture(self):
        root = self.store.root / "cli-project"
        (root / "models/fake").mkdir(parents=True)
        (root / "models/moge").mkdir()
        shutil.copyfile(PROJECT / "tests/fixtures/models/fake/manifest.json", root / "models/fake/manifest.json")
        shutil.copyfile(PROJECT / "models/moge/environment.yml", root / "models/moge/environment.yml")
        environment = {**os.environ, "PYTHONPATH": os.pathsep.join((str(PROJECT / "src"), str(PROJECT)))}
        command = [sys.executable, "-m", "mde.cli", "run", "--model", "fake", "--device", "cpu",
                   "--input", str(PROJECT / "tests/assets/sample.png"), "--project-root", str(root)]
        prefix = os.environ.get("MDE_TEST_CONDA_PREFIX")
        command += ["--conda-prefix", prefix] if prefix else ["--conda-env", os.environ.get("MDE_TEST_CONDA_ENV", "mde-moge")]
        return root, environment, command

    def test_cli_interrupt_cancels_process_group_and_reports_reason(self):
        root, environment, command = self.cli_fixture()
        process = subprocess.Popen(command + ["--params", '{"action":"stubborn"}'], env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        submitted = json.loads(process.stdout.readline())
        run = root / "runs" / submitted["run_id"]
        deadline = time.monotonic() + 20
        while "fake child ready:" not in (run / "logs/attempt-0001/stdout.log").read_text():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        process.send_signal(signal.SIGINT)
        output, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 130, stderr)
        result = json.loads(output)
        self.assertEqual(result["status"], "CANCELLED")
        self.assertIn("CLI interrupted", result["error"]["message"])
        self.assertTrue(result["execution"]["process_cleanup"]["group_terminated"])
        pids_line = next(line for line in (run / "logs/attempt-0001/stdout.log").read_text().splitlines()
                         if line.startswith("fake child ready:"))
        for pid in json.loads(pids_line.split(": ", 1)[1]).values():
            path = Path(f"/proc/{pid}/stat")
            deadline = time.monotonic() + 3
            while path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(path.exists(), f"Child PID {pid} remains after CLI cancel")

    def test_cli_worker_failure_is_nonzero_with_structured_reason(self):
        _, environment, command = self.cli_fixture()
        response = subprocess.run(command + ["--params", '{"action":"raise"}'], env=environment,
                                  capture_output=True, text=True, timeout=20)
        self.assertEqual(response.returncode, 1, response.stderr)
        result = json.loads(response.stdout.split("\n", 1)[1])
        self.assertEqual(result["error"]["stage"], "predict")
        self.assertIn("intentional predict failure", result["error"]["message"])


class RuntimeObservationTests(unittest.TestCase):
    def test_optional_cuda_observation_and_synchronized_timing(self):
        from mde.runtime import timed, reset_allocator, observe_allocator
        framework = Mock()
        framework.cuda.is_available.return_value = True
        framework.cuda.max_memory_allocated.return_value = 123
        framework.cuda.max_memory_reserved.return_value = 456
        metrics = {}
        with patch.dict(sys.modules, {"torch": framework}):
            self.assertTrue(reset_allocator("cuda:0"))
            with timed(metrics, "predict_seconds", "test", "cuda:0"):
                pass
            observe_allocator("cuda:0", metrics)
            self.assertEqual(metrics["cuda_peak_allocated_bytes"]["value"], 123)
            self.assertEqual(metrics["cuda_peak_reserved_bytes"]["unit"], "bytes")
            framework.cuda.reset_peak_memory_stats.assert_called_once_with("cuda:0")
            self.assertGreaterEqual(framework.cuda.synchronize.call_count, 4)
            framework.cuda.reset_mock()
            self.assertFalse(reset_allocator("cpu"))
            observe_allocator("cpu", {})
            framework.cuda.synchronize.assert_not_called()
