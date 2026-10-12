"""Single-job Local execution through a model-independent backend interface."""
from dataclasses import dataclass, replace
import threading
import time
import uuid
from pathlib import Path

from .contracts import (ArtifactIntegrityError, ATTEMPT_ID, BackendBusy, CancelReceipt,
                        ExecutionBackend, JobHandle, JobResult, JobSpec, JobStatus,
                        JobStatusSnapshot, ResultNotReady, UnknownJob, UnsupportedOperation, utc_now)
from .environments import WorkerManager, WorkerProcess
from .storage import (contained_path, read_json, run_path, validate_job_files,
                      validate_outputs, validate_report, write_json)


@dataclass
class _LocalJob:
    spec: JobSpec
    handle: JobHandle
    run: Path
    worker: WorkerProcess | None
    snapshot: JobStatusSnapshot
    result: JobResult | None = None
    started_monotonic: float | None = None
    timer: threading.Timer | None = None
    cleanup: dict | None = None


class LocalBackend(ExecutionBackend):
    backend_id = "local"
    profile_id = "local"
    supports_cancel = True

    def __init__(self, run_root: Path, manager: WorkerManager | None = None, *, stop_grace_seconds=1.0):
        if stop_grace_seconds < 0:
            raise ValueError("Negative stop grace")
        self.run_root = Path(run_root)
        self.manager = manager
        self.stop_grace_seconds = stop_grace_seconds
        self.instance_id = str(uuid.uuid4())
        self._jobs: dict[str, _LocalJob] = {}
        self._keys: dict[str, str] = {}
        self._lock = threading.RLock()

    def submit(self, spec: JobSpec) -> JobHandle:
        with self._lock:
            JobSpec.from_dict(spec.to_dict())
            if spec.backend_id != self.backend_id or spec.backend_profile != self.profile_id:
                raise ValueError("Backend / profile mismatch")
            self._validate_resources(spec)
            if spec.idempotency_key in self._keys:
                old = self._jobs[self._keys[spec.idempotency_key]]
                if old.spec.to_dict() != spec.to_dict():
                    raise ValueError("Submission identity conflict")
                return old.handle
            for old in list(self._jobs.values()):
                if not old.snapshot.status.terminal and not self.status(old.handle).status.terminal:
                    raise BackendBusy("LocalBackend instance is busy; no queue is supported")
            if self.manager is None:
                raise UnsupportedOperation("Read-only backend: configure WorkerManager to submit")
            self.manager.resolver.resolve(spec.environment_ref)
            run = run_path(self.run_root, spec.run_id)
            validate_job_files(run, spec)
            attempt = run / "attempts" / spec.attempt_id
            if (attempt / "handle.json").exists():
                raise UnsupportedOperation("Persisted attempt already submitted; no active recovery or retry")
            handle = JobHandle(spec.run_id, spec.attempt_id, self.backend_id, str(uuid.uuid4()),
                               utc_now(), spec.idempotency_key, spec.run_id, self.profile_id)
            snapshot = JobStatusSnapshot(JobStatus.QUEUED, utc_now(), "not_started", 0)
            job = _LocalJob(spec, handle, run, None, snapshot)
            self._jobs[handle.backend_job_id] = job
            self._keys[spec.idempotency_key] = handle.backend_job_id
            write_json(attempt / "handle.json", {**handle.to_dict(), "manager_instance": self.instance_id})
            self._save_status(job)
            try:
                job.worker = self.manager.start(spec.environment_ref, attempt / "job.json", run)
                job.started_monotonic = time.monotonic()
                job.snapshot = JobStatusSnapshot(JobStatus.RUNNING, utc_now(), "process_started", 1,
                                                 started_at=utc_now())
                write_json(attempt / "handle.json", {**handle.to_dict(), "manager_instance": self.instance_id,
                           "pid": job.worker.process.pid, "process_started_at": job.snapshot.started_at})
                self._save_status(job)
                timeout = spec.resources.get("walltime_seconds")
                if timeout is not None:
                    job.timer = threading.Timer(timeout, self._timeout, args=(handle,))
                    job.timer.daemon = True
                    job.timer.start()
            except Exception as error:
                if job.worker is not None:
                    job.cleanup = job.worker.stop(self.stop_grace_seconds)
                self._finish(job, None, self._error("LAUNCH_FAILED", "backend", str(error)))
            return handle

    @staticmethod
    def _validate_resources(spec):
        resources = spec.resources
        allowed = {"cpu_count", "gpu_count", "gpu_type", "host_memory_mib", "gpu_memory_mib", "walltime_seconds"}
        if resources.keys() - allowed:
            raise UnsupportedOperation("Unknown Local resource request")
        if type(resources.get("cpu_count", 1)) is not int or resources.get("cpu_count", 1) < 1:
            raise ValueError("cpu_count must be a positive integer; recorded only, no thread quota")
        if type(resources.get("gpu_count", 0)) is not int or resources.get("gpu_count", 0) not in (0, 1):
            raise UnsupportedOperation("Local supports 0-1 GPU and one worker")
        if resources.get("gpu_count", 0) != int(spec.inference["device"].startswith("cuda")):
            raise ValueError("Device / gpu_count mismatch")
        for key in ("gpu_type", "host_memory_mib", "gpu_memory_mib"):
            if resources.get(key) is not None:
                raise UnsupportedOperation(f"Local does not enforce {key}")
        timeout = resources.get("walltime_seconds")
        if timeout is not None and (type(timeout) is not int or timeout < 1):
            raise ValueError("walltime_seconds must be a positive integer")

    @staticmethod
    def _error(code, stage, message):
        return {"code": code, "stage": stage, "message": message, "retryability": False}

    def _get(self, handle: JobHandle) -> _LocalJob:
        if not isinstance(handle, JobHandle):
            raise UnknownJob("Expected JobHandle")
        job = self._jobs.get(handle.backend_job_id)
        if job is not None:
            if job.handle != handle:
                raise UnknownJob(handle.backend_job_id)
            return job
        if (handle.backend_id != self.backend_id or handle.backend_profile != self.profile_id
                or handle.attempt_id != ATTEMPT_ID or handle.run_location != handle.run_id):
            raise UnknownJob("Handle backend / location mismatch")
        run = run_path(self.run_root, handle.run_id)
        try:
            saved = read_json(contained_path(run, f"attempts/{handle.attempt_id}/handle.json"))
        except FileNotFoundError as error:
            raise UnknownJob(handle.backend_job_id) from error
        if any(saved.get(key) != value for key, value in handle.to_dict().items()):
            raise UnknownJob("Persisted handle mismatch")
        result_path = contained_path(run, f"attempts/{handle.attempt_id}/job-result.json")
        if not result_path.is_file():
            raise UnsupportedOperation("Active job recovery is unsupported; terminal result is required")
        try:
            data = read_json(result_path)
            validate_report(data, handle.run_id, handle.attempt_id, terminal=True)
            if data.get("backend_id") != self.backend_id or data["execution"].get("backend_job_id") != handle.backend_job_id:
                raise ArtifactIntegrityError("Persisted result backend identity mismatch")
            if data["execution"].get("manager_instance") != saved.get("manager_instance"):
                raise ArtifactIntegrityError("Persisted manager identity mismatch")
            result = JobResult(**{key: data[key] for key in JobResult.__dataclass_fields__ if key in data})
            spec = JobSpec.from_dict(read_json(contained_path(run, f"attempts/{handle.attempt_id}/job.json")))
            if spec.run_id != handle.run_id or spec.idempotency_key != handle.idempotency_key:
                raise ArtifactIntegrityError("Persisted job identity mismatch")
            snapshot = JobStatusSnapshot(JobStatus(result.status), result.finished_at, "persisted_terminal", 0,
                                         result.started_at, result.finished_at,
                                         cancel_requested=result.status == "CANCELLED",
                                         reason=(result.error or {}).get("message"))
            job = _LocalJob(spec, handle, run, None, snapshot, result)
        except Exception as error:
            raise ArtifactIntegrityError(f"Invalid persisted terminal result: {error}") from error
        self._jobs[handle.backend_job_id] = job
        return job

    def _save_status(self, job: _LocalJob) -> None:
        write_json(job.run / "attempts" / job.spec.attempt_id / "status.json",
                   {"schema_version": job.spec.schema_version, "run_id": job.spec.run_id,
                    "attempt_id": job.spec.attempt_id, **job.snapshot.to_dict()})

    def _finish(self, job, report, error, exit_code=None, *, cancelled=False):
        if job.result is not None:
            return
        if job.timer:
            job.timer.cancel()
        status = JobStatus.CANCELLED if cancelled else JobStatus.FAILED if error else JobStatus.COMPLETED
        finished = utc_now()
        job.snapshot = JobStatusSnapshot(status, finished, f"exit={exit_code}", job.snapshot.sequence + 1,
                                         job.snapshot.started_at, finished, job.snapshot.cancel_requested,
                                         reason=error["message"] if error else None)
        execution = {**((report or {}).get("execution", {})), "backend_job_id": job.handle.backend_job_id,
                     "exit_code": exit_code, "manager_instance": self.instance_id}
        if job.cleanup:
            execution["process_cleanup"] = job.cleanup
        job.result = JobResult(job.spec.run_id, job.spec.attempt_id, self.backend_id, status.value,
                               [] if error else report["outputs"], [] if error else report["artifacts"],
                               execution, job.snapshot.started_at, finished, error,
                               (report or {}).get("warnings", []), (report or {}).get("metrics", {}))
        write_json(job.run / "attempts" / job.spec.attempt_id / "job-result.json", job.result.to_dict())
        self._save_status(job)

    def _timeout(self, handle):
        try:
            self.status(handle)
        except Exception as error:
            # Failed stops are not terminal; a later status/cancel can stop again.
            with self._lock:
                job = self._jobs[handle.backend_job_id]
                if job.result is None:
                    job.snapshot = replace(job.snapshot, reason=f"timeout stop failed: {error}")
                    self._save_status(job)

    def status(self, handle: JobHandle) -> JobStatusSnapshot:
        with self._lock:
            job = self._get(handle)
            if job.result:
                return job.snapshot
            code = job.worker.process.poll()
            timeout = job.spec.resources.get("walltime_seconds")
            if code is None:
                if timeout is None or time.monotonic() - job.started_monotonic < timeout:
                    return job.snapshot
                job.cleanup = job.worker.stop(self.stop_grace_seconds)
                self._finish(job, None, self._error("TIMEOUT", "backend", f"Execution exceeded {timeout} seconds"),
                             job.worker.process.returncode)
                return job.snapshot
            job.cleanup = job.worker.stop(self.stop_grace_seconds)
            report = None
            error = None
            try:
                candidate = read_json(contained_path(job.run, f"output/{job.spec.attempt_id}/result.json"))
                validate_report(candidate, job.spec.run_id, job.spec.attempt_id)
                report = candidate
                if code != 0 or report["outcome"] != "COMPLETED":
                    error = report.get("error") or self._error("WORKER_FAILED", "backend", f"Worker exited {code}")
                else:
                    validate_job_files(job.run, job.spec)
                    validate_outputs(job.run, report)
            except Exception as failure:
                error = self._error("INVALID_RESULT" if code == 0 else "WORKER_FAILED", "collect", str(failure))
                report = None
            self._finish(job, report, error, code)
            return job.snapshot

    def cancel(self, handle: JobHandle, reason: str | None = None) -> CancelReceipt:
        with self._lock:
            observed = self.status(handle)
            requested = utc_now()
            if observed.status.terminal:
                return CancelReceipt(False, requested, observed.status.value, already_terminal=True)
            job = self._get(handle)
            job.snapshot = replace(job.snapshot, cancel_requested=True, reason=reason or "User cancelled",
                                   observed_at=requested, sequence=job.snapshot.sequence + 1)
            self._save_status(job)
            job.cleanup = job.worker.stop(self.stop_grace_seconds)
            self._finish(job, None, self._error("CANCELLED", "backend", reason or "User cancelled"),
                         job.worker.process.returncode, cancelled=True)
            return CancelReceipt(True, requested, job.snapshot.status.value)

    def collect(self, handle: JobHandle) -> JobResult:
        with self._lock:
            snapshot = self.status(handle)
            if not snapshot.status.terminal:
                raise ResultNotReady(handle.run_id)
            job = self._get(handle)
            try:
                saved = read_json(contained_path(job.run, f"attempts/{job.spec.attempt_id}/job-result.json"))
                if any(saved.get(key, {} if key == "metrics" else None) != value
                       for key, value in job.result.to_dict().items()):
                    raise ArtifactIntegrityError("Terminal JobResult changed after finalization")
                validate_report(saved, handle.run_id, handle.attempt_id, terminal=True)
                if job.result.status == "COMPLETED":
                    validate_job_files(job.run, job.spec)
                    validate_outputs(job.run, saved)
                    worker = read_json(contained_path(job.run, f"output/{job.spec.attempt_id}/result.json"))
                    validate_report(worker, handle.run_id, handle.attempt_id)
                    validate_outputs(job.run, worker)
                    if worker["outcome"] != "COMPLETED" or any(worker.get(key, {}) != saved[key] for key in ("outputs", "artifacts", "metrics", "warnings")):
                        raise ArtifactIntegrityError("Worker / terminal result mismatch")
            except Exception as error:
                raise ArtifactIntegrityError(f"Terminal result integrity check failed: {error}") from error
            return job.result
