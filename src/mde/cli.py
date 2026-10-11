"""Composition root for the minimum Local experiment; never imports a model."""
import argparse
import json
from pathlib import Path
import sys
import time

from .backends import LocalBackend
from .environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
from .registry import ModelRegistry
from .runner import ExperimentRunner
from .storage import RunStore


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MGE Experiment Platform — Phase 01A")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run one PNG image through a Conda worker")
    run.add_argument("--model", required=True)
    run.add_argument("--variant")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--backend", choices=["local"], default="local")
    run.add_argument("--device", choices=["cuda:0", "cpu"], default="cuda:0")
    run.add_argument("--dtype", choices=["float32"], default="float32")
    run.add_argument("--params", default="{}", help="Manifest parameters as a JSON object")
    run.add_argument("--run-root", type=Path)
    run.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    env = run.add_mutually_exclusive_group()
    env.add_argument("--conda-env")
    env.add_argument("--conda-prefix")
    run.add_argument("--conda-exe")
    run.add_argument("--checkpoint", type=Path, help="Optional pre-downloaded checkpoint; hash is verified")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        registry = ModelRegistry(root / "models")
        info = registry.get_model(args.model)
        environment_id = info.data["environment_refs"][0]["environment_id"]
        profile = EnvironmentProfile(environment_id, None if args.conda_prefix else args.conda_env or environment_id,
                                     args.conda_prefix)
        resolver = EnvironmentResolver({environment_id: profile})
        store = RunStore(root, args.run_root)
        manager = WorkerManager(root, resolver, CondaLauncher(args.conda_exe), args.checkpoint)
        backend = LocalBackend(store.root, manager)
        runner = ExperimentRunner(registry, backend, store, root)
        parameters = json.loads(args.params)
        if not isinstance(parameters, dict):
            raise ValueError("--params must be a JSON object")
        handle = runner.submit(args.model, args.input, variant_id=args.variant, device=args.device,
                               dtype=args.dtype, parameters=parameters)
        print(json.dumps({"run_id": handle.run_id, "status": "SUBMITTED", "run_root": str(store.root)}), flush=True)
        while not runner.status(handle).status.terminal:
            time.sleep(0.1)
        result = runner.collect(handle)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.status == "COMPLETED" else 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
