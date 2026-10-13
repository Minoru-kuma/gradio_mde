"""One job in the selected model environment; owns artifact serialization."""
import argparse
import importlib
import os
import platform
import sys
import traceback
import time
from pathlib import Path

from .contracts import (JobSpec, ModelInfo, ModelLoadContext, PredictionRequest,
                        SCHEMA_VERSION, GEOMETRY_PROFILE, normalize_outputs, check_schema, utc_now)
from .storage import artifact_ref, contained_path, read_json, sha256_file, write_json
from .runtime import environment_fingerprint, timed, reset_allocator, observe_allocator


def framework_runtime(device: str) -> dict:
    """Observe an already imported framework; do not make torch a worker requirement."""
    torch = sys.modules.get("torch")
    if torch is None:
        return {}
    data = {"torch_version": torch.__version__, "torch_cuda_runtime": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(), "gpu": None, "driver_version": None}
    if device.startswith("cuda") and data["cuda_available"]:
        data["gpu"] = torch.cuda.get_device_name(torch.device(device))
        import shutil
        import subprocess
        command = shutil.which("nvidia-smi")
        if command:
            observation = subprocess.run([command, "--query-gpu=driver_version", "--format=csv,noheader"],
                                         capture_output=True, text=True, check=False, timeout=5)
            if observation.returncode == 0:
                data["driver_version"] = observation.stdout.strip().splitlines()[0]
    return data


def execute(job_path: Path, run: Path) -> int:
    worker_started = time.perf_counter()
    import numpy as np
    from PIL import Image

    spec = JobSpec.from_dict(read_json(job_path))
    run = Path(run).resolve()
    if run.name != spec.run_id:
        raise ValueError("Run ID/path mismatch")
    output_dir = run / "output" / spec.attempt_id
    if (output_dir / "result.json").exists() or (run / "attempts" / spec.attempt_id / "job-result.json").exists():
        raise ValueError("Published inference results are immutable; create a new Run")
    report = {"schema_version": SCHEMA_VERSION, "run_id": spec.run_id, "attempt_id": spec.attempt_id,
              "outcome": "FAILED", "outputs": [], "artifacts": [], "metrics": {}, "warnings": [],
              "started_at": utc_now(), "execution": {"python_version": platform.python_version(),
              "python_implementation": platform.python_implementation(), "python_prefix": sys.prefix,
              "conda_environment": os.environ.get("CONDA_DEFAULT_ENV", "unknown"),
              "requested_environment": spec.environment_ref["environment_id"],
              "worker_pid": os.getpid(), "device": spec.inference["device"], "provenance": spec.provenance}}
    adapter = None
    stage = "preflight"
    try:
        if sys.prefix == os.environ.get("MDE_CONTROL_PREFIX") or os.environ.get("CONDA_DEFAULT_ENV") == "base":
            raise ValueError("Worker must run in an independent model environment")
        info = ModelInfo(spec.model_ref["manifest"])
        check_schema(info.data)
        checkpoint = os.environ.get("MDE_CHECKPOINT_PATH")
        context = ModelLoadContext(info, spec.model_ref["variant"], checkpoint,
                                   spec.inference["device"], spec.inference["dtype"], spec.inference["seed"])
        module, name = info.data["adapter_entrypoint"].split(":")
        adapter = getattr(importlib.import_module(module), name)()
        report["execution"]["environment_fingerprint"] = environment_fingerprint(spec.environment_ref)
        stage = "load"
        print(f"load: {info.model_id}", flush=True)
        with timed(report["metrics"], "load_seconds", "adapter.load including checkpoint IO and device transfer", context.device):
            loaded = adapter.load(context)
        report["execution"].update(loaded.runtime)
        report["execution"]["model"] = loaded.identity
        report["warnings"].extend(loaded.warnings)
        stage = "preflight"
        input_spec = spec.inputs[0]
        path = contained_path(run, input_spec["path"])
        if sha256_file(path) != input_spec["sha256"]:
            raise ValueError("Input hash mismatch")
        with Image.open(path) as image:
            image = image.convert("RGB")
            original_size = {"width": image.width, "height": image.height}
            if original_size != input_spec["original_size"]:
                raise ValueError("Input size mismatch")
            rgb = np.asarray(image).copy()
        stage = "predict"
        print(f"predict: {original_size}", flush=True)
        allocator_measured = reset_allocator(context.device)
        with timed(report["metrics"], "predict_seconds", "adapter.predict including preprocessing, inference, postprocessing and CPU output; CUDA synchronized", context.device):
            batch = adapter.predict(PredictionRequest(input_spec["view_id"], rgb,
                                      spec.inference["parameters"], tuple(spec.inference["requested_outputs"])))
        if len(batch.views) != 1 or batch.views[0].view_id != input_spec["view_id"]:
            raise ValueError("Prediction view identity mismatch")
        stage = "serialize"
        serialization_started = time.perf_counter()
        output = batch.views[0]
        if output.depth is None:
            raise ValueError("Missing required depth")
        if np.asarray(output.depth).dtype.hasobject:
            raise ValueError("Object depth arrays are forbidden")
        depth = np.asarray(output.depth, dtype=np.dtype("<f4"), order="C")
        if depth.ndim != 2 or min(depth.shape) < 1:
            raise ValueError("Depth must have shape [H,W]")
        valid = np.isfinite(depth) & (depth > 0)
        if output.mask is not None:
            mask = np.asarray(output.mask)
            if mask.dtype != np.dtype(bool):
                raise ValueError("Model mask must be bool")
            if mask.shape != depth.shape:
                raise ValueError("Mask/depth shape mismatch")
            valid &= mask
        if not valid.any():
            raise ValueError("All depth pixels are invalid")
        depth = np.where(valid, depth, np.nan).astype("<f4")
        metadata = {**output.metadata, "shape": list(depth.shape), "dtype": "float32",
                    "original_size": original_size,
                    "output_size": {"width": depth.shape[1], "height": depth.shape[0]},
                    "model": loaded.identity, "device": context.device, "inference_dtype": context.dtype,
                    "warnings": loaded.warnings + output.metadata.get("warnings", []),
                    "invalid_depth": "NaN; valid pixels are finite and positive",
                    "valid_pixels": int(valid.sum()), "invalid_pixels": int((~valid).sum()),
                    "resize_policy": "adapter metadata; original RGB input is preserved"}
        for key in ("depth_kind", "scale_type", "depth_unit", "camera_frame"):
            if key not in metadata:
                raise ValueError(f"Missing output metadata: {key}")
        if metadata["depth_kind"] not in ("z_depth", "ray_distance"):
            raise ValueError("Unknown depth kind")
        if metadata["scale_type"] == "metric" and metadata["depth_unit"] != "m":
            raise ValueError("Metric depth must be in metres")
        def save_array(name, array, unit):
            array = np.ascontiguousarray(array)
            path = contained_path(run, f"output/{spec.attempt_id}/views/{output.view_id}/{name}.npy")
            if path.exists():
                raise ValueError("Raw artifacts are immutable")
            temporary = path.with_suffix(".npy.tmp")
            with temporary.open("xb") as stream:
                np.save(stream, array, allow_pickle=False)
            os.replace(temporary, path)
            return artifact_ref(run, path, media_type="application/x-npy", shape=list(array.shape),
                                dtype="bool" if array.dtype == np.dtype(bool) else "float32", unit=unit)

        ref = save_array("depth", depth, metadata["depth_unit"])
        serialized = {"view_id": output.view_id, "depth": ref, "metadata": metadata, "extras": output.extras}
        report["outputs"] = [serialized]
        report["artifacts"] = [ref]
        requested = normalize_outputs(spec.inference["requested_outputs"])
        profile = "01A-depth-only"
        if requested != ["depth"]:
            profile = GEOMETRY_PROFILE
            meanings = output.metadata.get("geometry", {})
            metadata["requested_outputs"] = requested
            metadata["geometry"] = {"mask": {"origin": "validation",
                "conversion": "finite-positive depth AND model mask; invalid depth and vectors stored as NaN"}}
            serialized["mask"] = save_array("mask", valid, "unitless")
            report["artifacts"].append(serialized["mask"])
            if output.mask is not None:
                serialized["model_mask"] = save_array("model_mask", np.asarray(output.mask), "unitless")
                metadata["geometry"]["model_mask"] = meanings.get("model_mask", {})
                report["artifacts"].append(serialized["model_mask"])
            if "mask" in requested and output.mask is None:
                raise ValueError("Missing requested model mask")
            for key in ("points", "normals", "intrinsics"):
                if key not in requested:
                    continue
                value = getattr(output, key)
                if value is None:
                    raise ValueError(f"Missing requested {key}")
                raw = np.asarray(value)
                if raw.dtype.hasobject:
                    raise ValueError(f"Object {key} arrays are forbidden")
                array = np.asarray(value, dtype=np.dtype("<f4"), order="C")
                expected = (3, 3) if key == "intrinsics" else (*depth.shape, 3)
                if array.shape != expected:
                    raise ValueError(f"{key} shape mismatch")
                if key != "intrinsics":
                    array = np.where(valid[..., None], array, np.nan).astype("<f4")
                unit = metadata["depth_unit"] if key == "points" else "pixel" if key == "intrinsics" else "unitless"
                serialized[key] = save_array(key, array, unit)
                metadata["geometry"][key] = meanings.get(key, {})
                report["artifacts"].append(serialized[key])
        else:
            metadata.pop("geometry", None)
        report["execution"]["serialization_profile"] = profile
        from .geometry import validate_geometry
        validate_geometry(run, report)
        report["metrics"]["serialization_seconds"] = {"value": time.perf_counter() - serialization_started,
            "unit": "s", "scope": "numeric artifact validation, conversion, atomic NPY write and checksum; excludes metadata / result JSON"}
        if allocator_measured:
            observe_allocator(context.device, report["metrics"])
        report["outcome"] = "COMPLETED"
        print(f"saved: {ref['path']} shape={depth.shape}", flush=True)
    except Exception as error:
        traceback.print_exc()
        report["error"] = {"code": "WORKER_ERROR", "stage": stage, "message": str(error),
                           "retryability": False, "traceback_path": f"logs/{spec.attempt_id}/stderr.log"}
    finally:
        if adapter is not None:
            try:
                with timed(report["metrics"], "unload_seconds", "adapter.unload; CPU wall clock"):
                    adapter.unload()
                print("unload: complete", flush=True)
            except Exception as error:
                report["warnings"].append(f"unload failed: {error}")
                traceback.print_exc()
        try:
            report["execution"].update(framework_runtime(spec.inference["device"]))
        except Exception as error:
            report["warnings"].append(f"runtime observation unavailable: {error}")
    report["finished_at"] = utc_now()
    if report["outcome"] == "COMPLETED":
        try:
            with timed(report["metrics"], "metadata_serialization_seconds", "metadata JSON write and checksum"):
                write_json(output_dir / "metadata.json", {"schema_version": SCHEMA_VERSION, "run_id": spec.run_id,
                           "attempt_id": spec.attempt_id, "execution": report["execution"], "views": [metadata],
                           "warnings": report["warnings"]})
                report["artifacts"].append(artifact_ref(run, output_dir / "metadata.json", media_type="application/json"))
        except Exception as error:
            traceback.print_exc()
            report["outcome"] = "FAILED"
            report["error"] = {"code": "WORKER_ERROR", "stage": "serialize", "message": str(error),
                               "retryability": False, "traceback_path": f"logs/{spec.attempt_id}/stderr.log"}
    report["metrics"]["worker_seconds"] = {"value": time.perf_counter() - worker_started,
        "unit": "s", "scope": "worker execute including imports, fingerprint, cleanup, metadata write; excludes result publication / Conda startup"}
    write_json(output_dir / "result.json", report)
    return 0 if report["outcome"] == "COMPLETED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    return execute(args.job, args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
