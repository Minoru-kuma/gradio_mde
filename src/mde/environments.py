"""Target environment resolution and subprocess launch, independent of models."""
import os
import shutil
import subprocess
import sys
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from .storage import contained_path, sha256_file


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

    def group_alive(self) -> bool:
        # Linux zombies have terminated; their parent/init owns reaping. They cannot
        # hold a GPU or execute code. Never mistake a wrapper exit for worker exit.
        if sys.platform.startswith("linux"):
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    if int(fields[2]) == self.process.pid and fields[0] not in ("Z", "X"):
                        return True
                except (FileNotFoundError, ProcessLookupError):
                    continue
            return False
        try:
            os.killpg(self.process.pid, 0)
            return True
        except ProcessLookupError:
            return False

    def stop(self, grace_seconds: float = 1.0) -> dict:
        def send(sig):
            try:
                os.killpg(self.process.pid, sig)
            except ProcessLookupError:
                pass

        escalated = False
        if self.group_alive():
            send(signal.SIGTERM)
            deadline = time.monotonic() + grace_seconds
            while self.group_alive() and time.monotonic() < deadline:
                self.process.poll()
                time.sleep(0.02)
            if self.group_alive():
                escalated = True
                send(signal.SIGKILL)
        self.process.wait(timeout=5)
        deadline = time.monotonic() + 5
        while self.group_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if self.group_alive():
            raise RuntimeError("Process group still running after SIGKILL; result not finalized")
        return {"process_group_id": self.process.pid, "group_terminated": True,
                "sigkill_used": escalated, "grace_seconds": grace_seconds}


class WorkerManager:
    def __init__(self, project_root: Path, resolver: EnvironmentResolver, launcher=None,
                 checkpoint: Path | None = None):
        self.project_root = Path(project_root).resolve()
        self.resolver = resolver
        self.launcher = launcher or CondaLauncher()
        self.checkpoint = checkpoint

    def start(self, reference: dict, job_path: Path, run: Path) -> WorkerProcess:
        if os.name != "posix":
            raise RuntimeError("Local worker termination requires POSIX process groups")
        profile = self.resolver.resolve(reference)
        definition = contained_path(self.project_root, reference["definition_ref"])
        if sha256_file(definition) != reference["definition_digest"]:
            raise ValueError("Environment definition digest mismatch")
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
                                       stdout=stdout, stderr=stderr, start_new_session=True,
                                       stdin=subprocess.DEVNULL)
        return WorkerProcess(process)
