"""Thin orchestration: no model imports, environment activation, or subprocesses."""
from dataclasses import asdict
import hashlib
import json
import uuid
from pathlib import Path

from .contracts import ATTEMPT_ID, VIEW_ID, ExecutionBackend, JobHandle, JobSpec, ResourceSpec, normalize_outputs
from .registry import ModelRegistry, validate_parameters
from .storage import RunStore, inspect_png, run_path, sha256_file, write_json


class ExperimentRunner:
    def __init__(self, registry: ModelRegistry, backend: ExecutionBackend, store: RunStore, project_root: Path):
        self.registry, self.backend, self.store = registry, backend, store
        self.project_root = Path(project_root)

    def submit(self, model_id: str, image: Path, *, variant_id: str | None = None,
               device: str = "cuda:0", dtype: str = "float32", parameters: dict | None = None,
               walltime_seconds: int | None = None,
               requested_outputs: tuple[str, ...] = ("depth",)) -> JobHandle:
        info = self.registry.get_model(model_id)
        variant = info.variant(variant_id)
        if device not in info.data["supported_devices"] or dtype not in info.data["supported_dtypes"]:
            raise ValueError("Unsupported device or dtype")
        outputs = normalize_outputs(requested_outputs)
        capabilities = variant.get("capabilities", info.data["capabilities"])
        for key in outputs:
            if capabilities.get(key, {}).get("status") not in ("supported", "conditional"):
                raise ValueError(f"Unsupported requested output: {key}")
        parameters = validate_parameters(info.data.get("parameter_schema", {}), parameters or {})
        width, height = inspect_png(image)
        environment = dict(info.data["environment_refs"][0])
        definition = self.project_root / environment["definition_ref"]
        environment["definition_digest"] = sha256_file(definition)
        model_ref = {"model_id": model_id, "variant": variant, "manifest": info.data}
        request = {"model_ref": model_ref, "parameters": parameters,
                   "device": device, "dtype": dtype, "input_sha256": sha256_file(image),
                   "environment": environment, "backend_id": self.backend.backend_id}
        request["walltime_seconds"] = walltime_seconds
        if outputs != ["depth"]:
            request["requested_outputs"] = outputs
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        run_id = str(uuid.uuid4())
        run = self.store.prepare(run_id, image)
        sources = hashlib.sha256()
        for directory in (self.project_root / "src", self.registry.models_root / model_id):
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.suffix in (".py", ".json", ".yml"):
                    sources.update(path.relative_to(self.project_root).as_posix().encode())
                    sources.update(path.read_bytes())
        spec = JobSpec(run_id, model_ref,
                       environment, self.backend.backend_id, self.backend.profile_id,
                       [{"view_id": VIEW_ID, "path": f"input/views/{VIEW_ID}/image.png",
                         "sha256": request["input_sha256"], "original_size": {"width": width, "height": height}}],
                       {"device": device, "dtype": dtype, "seed": 0, "parameters": parameters,
                        "requested_outputs": outputs, "resolution_policy": "native_input_grid"},
                       asdict(ResourceSpec(gpu_count=int(device.startswith("cuda")), walltime_seconds=walltime_seconds)),
                       {"run_location": run_id}, f"{run_id}/{ATTEMPT_ID}", digest,
                       {"git_commit": "unknown", "source_digest": sources.hexdigest()})
        write_json(run / "job.json", spec.to_dict())
        write_json(run / "attempts" / ATTEMPT_ID / "job.json", spec.to_dict())
        return self.backend.submit(spec)

    def status(self, handle: JobHandle):
        return self.backend.status(handle)

    def collect(self, handle: JobHandle):
        result = self.backend.collect(handle)
        write_json(run_path(self.store.root, handle.run_id) / "run.json",
                   {"schema_version": result.schema_version, "run_id": handle.run_id,
                    "selected_attempt_id": handle.attempt_id, "status": result.status})
        return result

    def cancel(self, handle: JobHandle, reason: str | None = None):
        return self.backend.cancel(handle, reason)
