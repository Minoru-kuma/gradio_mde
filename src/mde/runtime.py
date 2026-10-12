"""Worker-only observation. No framework import or model-specific policy."""
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path


def digest_record(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def environment_fingerprint(reference):
    packages = sorted([{"name": dist.metadata["Name"], "version": dist.version}
                       for dist in importlib.metadata.distributions()], key=lambda item: (item["name"].lower(), item["version"]))
    conda_packages = []
    for path in sorted((Path(sys.prefix) / "conda-meta").glob("*.json")):
        data = json.loads(path.read_text())
        conda_packages.append({key: data.get(key) for key in ("name", "version", "build", "subdir")})
    record = {"environment_id": reference["environment_id"],
              "definition_digest": reference["definition_digest"],
              "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
              "python_executable": sys.executable, "python_prefix": sys.prefix,
              "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
              "processor": platform.processor() or platform.machine(),
              "packages": packages, "package_list_digest": digest_record(packages),
              "conda_packages": conda_packages, "conda_package_list_digest": digest_record(conda_packages)}
    return {**record, "fingerprint_digest": digest_record(record)}


def cuda_framework(device):
    torch = sys.modules.get("torch")
    if torch is not None and device.startswith("cuda") and torch.cuda.is_available():
        return torch
    return None


def synchronize(device):
    torch = cuda_framework(device)
    if torch is not None:
        torch.cuda.synchronize(device)


@contextmanager
def timed(metrics, name, scope, device="cpu"):
    synchronize(device)
    started = time.perf_counter()
    try:
        yield
        synchronize(device)
    finally:
        metrics[name] = {"value": time.perf_counter() - started, "unit": "s", "scope": scope}


def reset_allocator(device):
    torch = cuda_framework(device)
    if torch is not None:
        synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
        return True
    return False


def observe_allocator(device, metrics):
    torch = cuda_framework(device)
    if torch is not None:
        synchronize(device)
        for key, method in (("cuda_peak_allocated_bytes", torch.cuda.max_memory_allocated),
                            ("cuda_peak_reserved_bytes", torch.cuda.max_memory_reserved)):
            metrics[key] = {"value": method(device), "unit": "bytes",
                            "scope": "torch allocator from predict start through depth serialization; includes loaded model; excludes CUDA context / other processes"}
