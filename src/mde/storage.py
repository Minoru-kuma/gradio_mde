"""Filesystem records and integrity checks, without numerical dependencies."""
import ast
import hashlib
import json
import os
import shutil
import struct
import uuid
from pathlib import Path

from .contracts import ArtifactIntegrityError, ATTEMPT_ID, SCHEMA_VERSION, VIEW_ID


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def run_path(root: Path, run_id: str) -> Path:
    # Accept only the canonical UUID created by Runner.
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("Invalid Run ID")
    return Path(root) / run_id


def contained_path(run: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactIntegrityError("Run references must be relative and contained")
    resolved = (run / path).resolve()
    if not resolved.is_relative_to(run.resolve()):
        raise ArtifactIntegrityError("Reference escapes Run Directory")
    return resolved


def artifact_ref(run: Path, path: Path, **metadata) -> dict:
    return {"path": path.relative_to(run).as_posix(), "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size, **metadata}


def inspect_png(path: Path) -> tuple[int, int]:
    with Path(path).open("rb") as stream:
        header = stream.read(33)
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("01A requires a PNG image; worker checks image decoding")
    width, height = struct.unpack(">II", header[16:24])
    if min(width, height) < 1:
        raise ValueError("Empty image")
    return width, height


def inspect_depth(path: Path) -> dict:
    """Read the NPY header with stdlib; do not import NumPy in control."""
    with path.open("rb") as stream:
        if stream.read(6) != b"\x93NUMPY":
            raise ArtifactIntegrityError("Invalid NPY magic")
        version = stream.read(2)
        if version not in (b"\x01\x00", b"\x02\x00"):
            raise ArtifactIntegrityError("Unsupported NPY version")
        length_size = 2 if version[0] == 1 else 4
        length = int.from_bytes(stream.read(length_size), "little")
        if length > 4096:
            raise ArtifactIntegrityError("Unexpected NPY header size")
        info = ast.literal_eval(stream.read(length).decode("latin1"))
        shape = info["shape"]
        if info["descr"] != "<f4" or info["fortran_order"] or len(shape) != 2 or min(shape) < 1:
            raise ArtifactIntegrityError("Depth must be C-contiguous float32 [H,W]")
        if path.stat().st_size != stream.tell() + shape[0] * shape[1] * 4:
            raise ArtifactIntegrityError("Depth payload size mismatch")
    return {"shape": list(shape), "dtype": "float32"}


def validate_outputs(run: Path, report: dict) -> None:
    outputs = report.get("outputs", [])
    if len(outputs) != 1 or outputs[0].get("view_id") != VIEW_ID:
        raise ArtifactIntegrityError("Expected exactly one output view")
    output = outputs[0]
    depth = output["depth"]
    for ref in report.get("artifacts", []):
        path = contained_path(run, ref["path"])
        if path.stat().st_size != ref["size_bytes"] or sha256_file(path) != ref["sha256"]:
            raise ArtifactIntegrityError(f"Artifact mismatch: {ref['path']}")
    path = contained_path(run, depth["path"])
    if sha256_file(path) != depth["sha256"] or path.stat().st_size != depth["size_bytes"]:
        raise ArtifactIntegrityError("Depth integrity mismatch")
    info = inspect_depth(path)
    if depth["shape"] != info["shape"] or depth["dtype"] != info["dtype"]:
        raise ArtifactIntegrityError("Depth manifest/header mismatch")
    metadata = output["metadata"]
    if metadata["shape"] != info["shape"] or metadata["dtype"] != info["dtype"]:
        raise ArtifactIntegrityError("Depth metadata/header mismatch")
    if metadata["depth_kind"] not in ("z_depth", "ray_distance"):
        raise ArtifactIntegrityError("Unknown depth kind")
    if metadata["scale_type"] not in ("metric", "relative", "unknown"):
        raise ArtifactIntegrityError("Unknown scale type")
    if depth["unit"] != metadata["depth_unit"]:
        raise ArtifactIntegrityError("Depth unit mismatch")
    if not (run / "output" / ATTEMPT_ID / "metadata.json").is_file():
        raise ArtifactIntegrityError("Missing metadata.json")


class RunStore:
    def __init__(self, project_root: Path, root: str | Path | None = None):
        base = Path(project_root).resolve()
        chosen = Path(root if root is not None else os.environ.get("MDE_RUN_ROOT", "runs"))
        self.root = (chosen if chosen.is_absolute() else base / chosen).resolve()

    def prepare(self, run_id: str, image: Path) -> Path:
        run = run_path(self.root, run_id)
        run.mkdir(parents=True, exist_ok=False)
        for relative in (f"input/views/{VIEW_ID}", f"attempts/{ATTEMPT_ID}",
                         f"output/{ATTEMPT_ID}/views/{VIEW_ID}", f"logs/{ATTEMPT_ID}"):
            (run / relative).mkdir(parents=True)
        shutil.copyfile(image, run / "input" / "views" / VIEW_ID / "image.png")
        write_json(run / "run.json", {"schema_version": SCHEMA_VERSION, "run_id": run_id,
                   "selected_attempt_id": ATTEMPT_ID, "status": "QUEUED"})
        return run
