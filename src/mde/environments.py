"""Target environment resolution and subprocess launch, independent of models."""
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentProfile:
    environment_id: str
    name: str | None = None
    prefix: str | None = None


class EnvironmentResolver:
    def __init__(self, profiles: dict[str, EnvironmentProfile]):
        self.profiles = profiles

    def resolve(self, reference: dict) -> EnvironmentProfile:
        key = reference["environment_id"]
        if key not in self.profiles:
            raise ValueError(f"Unknown environment: {key}")
        profile = self.profiles[key]
        if bool(profile.name) == bool(profile.prefix):
            raise ValueError("Configure exactly one Conda name or prefix")
        if profile.name == "base":
            raise ValueError("A model must use an independent Conda environment")
        return profile


class CondaLauncher:
    def __init__(self, executable: str | None = None):
        self.executable = executable or os.environ.get("MDE_CONDA_EXE") or shutil.which("conda")
        if not self.executable:
            raise ValueError("Conda not found; configure MDE_CONDA_EXE")

    def argv(self, profile: EnvironmentProfile, job_path: Path, run: Path) -> list[str]:
        target = ["--prefix", profile.prefix] if profile.prefix else ["--name", profile.name]
        return [self.executable, "run", "--no-capture-output", *target,
                "python", "-m", "mde.worker", "--job", str(job_path), "--run-dir", str(run)]


@dataclass
class WorkerProcess:
    process: subprocess.Popen


class WorkerManager:
    def __init__(self, project_root: Path, resolver: EnvironmentResolver, launcher=None,
                 checkpoint: Path | None = None):
        self.project_root = Path(project_root).resolve()
        self.resolver = resolver
        self.launcher = launcher or CondaLauncher()
        self.checkpoint = checkpoint

    def start(self, reference: dict, job_path: Path, run: Path) -> WorkerProcess:
        profile = self.resolver.resolve(reference)
        environment = os.environ.copy()
        # Source checkout is explicit; no installation into the control interpreter.
        paths = [str(self.project_root / "src"), str(self.project_root)]
        if environment.get("PYTHONPATH"):
            paths.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(paths)
        environment["PYTHONUNBUFFERED"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["MDE_CONTROL_PREFIX"] = sys.prefix
        if self.checkpoint:
            environment["MDE_CHECKPOINT_PATH"] = str(Path(self.checkpoint).resolve())
        logs = run / "logs" / "attempt-0001"
        with (logs / "stdout.log").open("wb") as stdout, (logs / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(self.launcher.argv(profile, job_path, run),
                                       cwd=self.project_root, env=environment,
                                       stdout=stdout, stderr=stderr)
        return WorkerProcess(process)
