"""Small, dependency-free model and execution contracts (protocol 1.0)."""
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
import uuid
from typing import Any

SCHEMA_VERSION = "1.0"
ATTEMPT_ID = "attempt-0001"
VIEW_ID = "view-0001"


OUTPUT_NAMES = ("depth", "points", "normals", "intrinsics", "mask")
GEOMETRY_PROFILE = "02A-geometry-v1"


def normalize_outputs(value) -> list[str]:
    if (not isinstance(value, (list, tuple)) or not value
            or any(not isinstance(key, str) or key not in OUTPUT_NAMES for key in value)
            or len(set(value)) != len(value) or "depth" not in value):
        raise ValueError("Outputs must contain depth and unique supported geometry names")
    return [key for key in OUTPUT_NAMES if key in value]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_schema(value: dict) -> None:
    if (not isinstance(value, dict) or not isinstance(value.get("schema_version"), str)
            or not re.fullmatch(r"1\.[0-9]+", value["schema_version"])):
        raise ValueError("UnsupportedSchema: expected protocol major 1")


class UnsupportedOperation(RuntimeError):
    pass


class ResultNotReady(RuntimeError):
    pass


class UnknownJob(KeyError):
    pass


class BackendBusy(RuntimeError):
    pass


class ArtifactIntegrityError(ValueError):
    pass


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"

    @property
    def terminal(self) -> bool:
        return self in (self.COMPLETED, self.FAILED, self.CANCELLED)


@dataclass(frozen=True)
class ResourceSpec:
    cpu_count: int = 1
    gpu_count: int = 0
    gpu_type: str | None = None
    host_memory_mib: int | None = None
    gpu_memory_mib: int | None = None
    walltime_seconds: int | None = None


@dataclass(frozen=True)
class ModelInfo:
    """Preserve manifest metadata, including unknown optional fields."""
    data: dict

    @property
    def model_id(self) -> str:
        return self.data["model_id"]

    def variant(self, variant_id: str | None = None) -> dict:
        key = variant_id or self.data["default_variant"]
        for variant in self.data["variants"]:
            if variant["variant_id"] == key:
                return variant
        raise ValueError(f"Unknown variant: {key}")


@dataclass(frozen=True)
class ModelLoadContext:
    model_info: ModelInfo
    variant: dict
    checkpoint: str | None
    device: str
    dtype: str
    seed: int = 0


@dataclass
class LoadedModelInfo:
    identity: dict
    runtime: dict = field(default_factory=dict)
    capabilities: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PredictionRequest:
    view_id: str
    image: Any
    parameters: dict = field(default_factory=dict)
    requested_outputs: tuple[str, ...] = ("depth",)


@dataclass
class MDEOutput:
    view_id: str
    depth: Any
    metadata: dict
    points: Any = None
    intrinsics: Any = None
    normals: Any = None
    mask: Any = None
    confidence: Any = None
    camera_pose: Any = None
    rays: Any = None
    extras: dict = field(default_factory=dict)


@dataclass
class PredictionBatch:
    views: list[MDEOutput]
    scene_metadata: dict = field(default_factory=dict)


class ModelAdapter(ABC):
    @abstractmethod
    def load(self, context: ModelLoadContext) -> LoadedModelInfo: ...

    @abstractmethod
    def predict(self, request: PredictionRequest) -> PredictionBatch: ...

    @abstractmethod
    def unload(self) -> None: ...


@dataclass(frozen=True)
class JobSpec:
    run_id: str
    model_ref: dict
    environment_ref: dict
    backend_id: str
    backend_profile: str
    inputs: list[dict]
    inference: dict
    resources: dict
    storage: dict
    idempotency_key: str
    request_digest: str
    provenance: dict
    created_at: str = field(default_factory=utc_now)
    schema_version: str = SCHEMA_VERSION
    attempt_id: str = ATTEMPT_ID
    attempt_number: int = 1
    parent_run_id: str | None = None
    evaluation: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "JobSpec":
        check_schema(value)
        job = cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})
        if (job.attempt_id != ATTEMPT_ID or type(job.attempt_number) is not int or job.attempt_number != 1
                or not isinstance(job.inputs, list) or len(job.inputs) != 1):
            raise UnsupportedOperation("Phase 01 supports one view and one initial attempt")
        if str(uuid.UUID(job.run_id)) != job.run_id:
            raise ValueError("Invalid Run ID")
        for key in ("model_ref", "environment_ref", "inference", "resources", "storage", "provenance"):
            if not isinstance(getattr(job, key), dict):
                raise ValueError(f"JobSpec {key} must be an object")
        if job.storage.get("run_location") != job.run_id:
            raise ValueError("Run location mismatch")
        for key in ("backend_id", "backend_profile", "idempotency_key"):
            if not isinstance(getattr(job, key), str) or not getattr(job, key):
                raise ValueError(f"Invalid {key}")
        if not isinstance(job.request_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", job.request_digest):
            raise ValueError("Invalid request digest")
        if not isinstance(job.environment_ref.get("environment_id"), str):
            raise ValueError("Missing environment ID")
        if not isinstance(job.model_ref.get("manifest"), dict) or not isinstance(job.model_ref.get("variant"), dict):
            raise ValueError("Malformed model reference")
        check_schema(job.model_ref["manifest"])
        source = job.inputs[0]
        if not isinstance(source, dict) or source.get("view_id") != VIEW_ID:
            raise ValueError("Invalid input view")
        if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise ValueError("Invalid input checksum")
        if not isinstance(source.get("path"), str) or not isinstance(source.get("original_size"), dict):
            raise ValueError("Malformed input reference")
        for axis in ("width", "height"):
            if type(source["original_size"].get(axis)) is not int or source["original_size"][axis] < 1:
                raise ValueError("Invalid input dimensions")
        if job.inference.get("device") not in ("cpu", "cuda:0") or job.inference.get("dtype") != "float32":
            raise UnsupportedOperation("Phase 01 supports cpu / cuda:0 and float32")
        if not isinstance(job.inference.get("parameters"), dict) or type(job.inference.get("seed")) is not int:
            raise ValueError("Malformed inference parameters / seed")
        normalize_outputs(job.inference.get("requested_outputs"))
        return job


@dataclass(frozen=True)
class JobHandle:
    run_id: str
    attempt_id: str
    backend_id: str
    backend_job_id: str
    submission_time: str
    idempotency_key: str
    run_location: str
    backend_profile: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class JobStatusSnapshot:
    status: JobStatus
    observed_at: str
    backend_state: str
    sequence: int
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested: bool = False
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CancelReceipt:
    accepted: bool
    requested_at: str
    status: str
    already_terminal: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JobResult:
    run_id: str
    attempt_id: str
    backend_id: str
    status: str
    outputs: list[dict]
    artifacts: list[dict]
    execution: dict
    started_at: str | None
    finished_at: str
    error: dict | None = None
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


class ExecutionBackend(ABC):
    backend_id: str
    profile_id: str
    supports_cancel = False

    @abstractmethod
    def submit(self, spec: JobSpec) -> JobHandle: ...

    @abstractmethod
    def status(self, handle: JobHandle) -> JobStatusSnapshot: ...

    @abstractmethod
    def collect(self, handle: JobHandle) -> JobResult: ...

    def cancel(self, handle: JobHandle, reason: str | None = None):
        raise UnsupportedOperation("cancel is not supported in Phase 01A")
