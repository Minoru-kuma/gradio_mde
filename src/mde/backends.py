"""Single-job Local execution through a model-independent backend interface."""
from dataclasses import dataclass
import uuid
from pathlib import Path

from .contracts import (ExecutionBackend, JobHandle, JobResult, JobSpec, JobStatus,
                        JobStatusSnapshot, ResultNotReady, UnknownJob, UnsupportedOperation, check_schema, utc_now)
from .environments import WorkerManager, WorkerProcess
from .storage import read_json, run_path, validate_outputs, write_json


@dataclass
class _LocalJob:
    spec: JobSpec
    handle: JobHandle
    run: Path
    worker: WorkerProcess | None
    snapshot: JobStatusSnapshot
    result: JobResult | None = None


class LocalBackend(ExecutionBackend):
    backend_id = "local"
    profile_id = "local"
    supports_cancel = False

    def __init__(self, run_root: Path, manager: WorkerManager):
        self.run_root = Path(run_root)
        self.manager = manager
        self.instance_id = str(uuid.uuid4())
        self._jobs: dict[str, _LocalJob] = {}
        self._keys: dict[str, str] = {}

    def submit(self, spec: JobSpec) -> JobHandle:
        JobSpec.from_dict(spec.to_dict())
        if spec.backend_id != self.backend_id:
            raise ValueError("Backend mismatch")
        if spec.resources.get("walltime_seconds") is not None:
            raise UnsupportedOperation("execution timeout is not supported in 01A")
        if spec.resources.get("gpu_count", 0) not in (0, 1) or spec.resources.get("cpu_count", 1) < 1:
            raise UnsupportedOperation("01A supports one worker and 0-1 GPU")
        if spec.idempotency_key in self._keys:
            old = self._jobs[self._keys[spec.idempotency_key]]
            if old.spec.request_digest != spec.request_digest:
                raise ValueError("Submission identity conflict")
            return old.handle
        run = run_path(self.run_root, spec.run_id)
        attempt = run / "attempts" / spec.attempt_id
        if read_json(attempt / "job.json") != spec.to_dict():
            raise ValueError("Persisted JobSpec mismatch")
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
            job.snapshot = JobStatusSnapshot(JobStatus.RUNNING, utc_now(), "process_started", 1,
                                             started_at=utc_now())
            write_json(attempt / "handle.json", {**handle.to_dict(), "manager_instance": self.instance_id,
                       "pid": job.worker.process.pid, "process_started_at": job.snapshot.started_at})
            self._save_status(job)
        except Exception as error:
            self._finish(job, None, {"code": "LAUNCH_FAILED", "stage": "backend",
                                    "message": str(error), "retryability": False})
        return handle

    def _get(self, handle: JobHandle) -> _LocalJob:
        job = self._jobs.get(handle.backend_job_id)
        if job is None or job.handle != handle:
            raise UnknownJob(handle.backend_job_id)
        return job

    def _save_status(self, job: _LocalJob) -> None:
        write_json(job.run / "attempts" / job.spec.attempt_id / "status.json",
                   {"schema_version": job.spec.schema_version, "run_id": job.spec.run_id,
                    "attempt_id": job.spec.attempt_id, **job.snapshot.to_dict()})

    def _finish(self, job: _LocalJob, report: dict | None, error: dict | None, exit_code=None) -> None:
        status = JobStatus.FAILED if error else JobStatus.COMPLETED
        finished = utc_now()
        job.snapshot = JobStatusSnapshot(status, finished, f"exit={exit_code}", job.snapshot.sequence + 1,
                                         job.snapshot.started_at, finished, reason=error["message"] if error else None)
        execution = {**((report or {}).get("execution", {})), "backend_job_id": job.handle.backend_job_id,
                     "exit_code": exit_code, "manager_instance": self.instance_id}
        job.result = JobResult(job.spec.run_id, job.spec.attempt_id, self.backend_id, status.value,
                               [] if error else report["outputs"], (report or {}).get("artifacts", []),
                               execution, job.snapshot.started_at, finished, error,
                               (report or {}).get("warnings", []))
        write_json(job.run / "attempts" / job.spec.attempt_id / "job-result.json", job.result.to_dict())
        self._save_status(job)

    def status(self, handle: JobHandle) -> JobStatusSnapshot:
        job = self._get(handle)
        if job.result:
            return job.snapshot
        code = job.worker.process.poll()
        if code is None:
            return job.snapshot
        report = None
        error = None
        try:
            report = read_json(job.run / "output" / job.spec.attempt_id / "result.json")
            check_schema(report)
            if report["run_id"] != job.spec.run_id or report["attempt_id"] != job.spec.attempt_id:
                raise ValueError("WorkerResult identity mismatch")
            if code != 0 or report.get("outcome") != "COMPLETED":
                error = report.get("error") or {"code": "WORKER_FAILED", "stage": "backend",
                                               "message": f"Worker exited {code}", "retryability": False}
            else:
                validate_outputs(job.run, report)
        except Exception as failure:
            error = {"code": "INVALID_RESULT" if code == 0 else "WORKER_FAILED", "stage": "collect",
                     "message": str(failure), "retryability": False}
        self._finish(job, report, error, code)
        return job.snapshot

    def collect(self, handle: JobHandle) -> JobResult:
        snapshot = self.status(handle)
        if not snapshot.status.terminal:
            raise ResultNotReady(handle.run_id)
        job = self._get(handle)
        if job.result.status == "COMPLETED":
            validate_outputs(job.run, job.result.to_dict())
        return job.result
