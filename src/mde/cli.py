"""Composition root for the minimum Local experiment; never imports a model."""
import argparse
import json
from pathlib import Path
import sys
import time
import signal
import threading

from .backends import LocalBackend
from .environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
from .registry import ModelRegistry
from .runner import ExperimentRunner
from .storage import RunStore
from .storage import contained_path, read_json, run_path
from .contracts import ATTEMPT_ID, JobHandle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MGE Experiment Platform — Phase 01 Local execution")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run one PNG image through a Conda worker")
    run.add_argument("--model", required=True)
    run.add_argument("--variant")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--backend", choices=["local"], default="local")
    run.add_argument("--device", choices=["cuda:0", "cpu"], default="cuda:0")
    run.add_argument("--dtype", choices=["float32"], default="float32")
    run.add_argument("--outputs", nargs="+", choices=["depth", "points", "normals", "intrinsics", "mask"],
                     default=["depth"], help="Required output names; depth must be included")
    run.add_argument("--params", default="{}", help="Manifest parameters as a JSON object")
    run.add_argument("--run-root", type=Path)
    run.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    env = run.add_mutually_exclusive_group()
    env.add_argument("--conda-env")
    env.add_argument("--conda-prefix")
    run.add_argument("--conda-exe")
    run.add_argument("--checkpoint", type=Path, help="Optional pre-downloaded checkpoint; hash is verified")
    run.add_argument("--timeout-seconds", type=int, help="Execution timeout including Conda startup; positive seconds")
    collect = commands.add_parser("collect", help="Read a saved terminal result without starting a worker")
    collect.add_argument("--run-id", required=True)
    collect.add_argument("--run-root", type=Path)
    collect.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    runner = handle = None
    previous_signals = {}
    interrupted = threading.Event()
    try:
        root = args.project_root.resolve()
        store = RunStore(root, args.run_root)
        if args.command == "collect":
            location = run_path(store.root, args.run_id)
            data = read_json(contained_path(location, f"attempts/{ATTEMPT_ID}/handle.json"))
            saved_handle = JobHandle(**{key: data[key] for key in JobHandle.__dataclass_fields__ if key in data})
            result = LocalBackend(store.root).collect(saved_handle)
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if result.status == "COMPLETED" else 1
        if args.timeout_seconds is not None and args.timeout_seconds < 1:
            raise ValueError("--timeout-seconds must be a positive integer")
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_signals[sig] = signal.signal(sig, lambda *_: interrupted.set())
        registry = ModelRegistry(root / "models")
        info = registry.get_model(args.model)
        environment_id = info.data["environment_refs"][0]["environment_id"]
        profile = EnvironmentProfile(environment_id, None if args.conda_prefix else args.conda_env or environment_id,
                                     args.conda_prefix)
        resolver = EnvironmentResolver({environment_id: profile})
        manager = WorkerManager(root, resolver, CondaLauncher(args.conda_exe), args.checkpoint)
        backend = LocalBackend(store.root, manager)
        runner = ExperimentRunner(registry, backend, store, root)
        parameters = json.loads(args.params)
        if not isinstance(parameters, dict):
            raise ValueError("--params must be a JSON object")
        handle = runner.submit(args.model, args.input, variant_id=args.variant, device=args.device,
                               dtype=args.dtype, parameters=parameters, walltime_seconds=args.timeout_seconds,
                               requested_outputs=tuple(args.outputs))
        print(json.dumps({"run_id": handle.run_id, "status": "SUBMITTED", "run_root": str(store.root)}), flush=True)
        while not runner.status(handle).status.terminal:
            if interrupted.is_set():
                runner.cancel(handle, "CLI interrupted (SIGINT / SIGTERM)")
                break
            time.sleep(0.1)
        result = runner.collect(handle)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, allow_nan=False))
        return 130 if result.status == "CANCELLED" else 0 if result.status == "COMPLETED" else 1
    except Exception as error:
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    finally:
        if runner is not None and handle is not None:
            try:
                if not runner.status(handle).status.terminal:
                    runner.cancel(handle, "CLI exiting")
            except Exception as error:
                print(f"worker cleanup failed: {error}", file=sys.stderr)
        for sig, handler in previous_signals.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
