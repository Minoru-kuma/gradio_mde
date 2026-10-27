"""Application-only numeric views and immutable derived geometry.

No model/environment imports. The injected collector is the existing terminal
integrity gate; it never submits inference. NumPy/Pillow belong to the UI env.
"""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import threading
import uuid

import numpy as np
from PIL import Image

from .contracts import ATTEMPT_ID, ArtifactIntegrityError, JobHandle
from .geometry import FRAME
from .storage import (artifact_ref, contained_path, read_json, run_path,
                      sha256_file, validate_artifact, write_json)

MAX_PIXELS = 262144
MESH_PARAMETERS = {"relative_depth_jump": 0.05, "relative_edge_length": 0.1,
                   "relative_double_area": 1e-12}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def derived_path(run, relative):
    """Derived writes must stay in derived/, including within-Run symlinks."""
    path = Path(run)
    if Path(relative).parts[0] != "derived":
        raise ArtifactIntegrityError("Expected derived namespace")
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ArtifactIntegrityError("Symlinks are not allowed in derived storage")
    return contained_path(run, relative)


def encoded(array, dtype):
    return base64.b64encode(np.ascontiguousarray(array, dtype=dtype).tobytes()).decode()


def png_url(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()


def depth_view(depth, mask=None):
    valid = np.isfinite(depth) & (depth > 0)
    if mask is not None:
        valid &= mask
    values = depth[valid]
    lo, hi = (float(values.min()), float(values.max())) if values.size else (None, None)
    t = np.zeros(depth.shape, dtype=np.float32)
    if values.size:
        t[valid] = (depth[valid] - lo) / (hi - lo) if hi > lo else 0.5
    # A specified, deterministic blue->cyan->yellow ramp; no numeric mutation.
    rgb = np.stack((t, 1 - np.abs(2*t-1), 1-t), axis=-1)
    rgba = np.concatenate(((rgb * 255).astype(np.uint8), (valid[..., None]*255).astype(np.uint8)), axis=-1)
    return valid, rgb, rgba, {"shape": list(depth.shape), "dtype": str(depth.dtype),
        "min": lo, "max": hi, "valid_pixels": int(values.size),
        "valid_fraction": float(values.size / depth.size), "total_pixels": int(depth.size),
        "normalization": "finite-positive + saved effective mask; linear min/max; constant=0.5; invalid=transparent",
        "colormap": "blue-cyan-yellow: (t, 1-|2t-1|, 1-t)"}


def backproject(depth, k, kind):
    y, x = np.indices(depth.shape, dtype=np.float32)
    rays = np.stack((x, y, np.ones_like(x)), axis=-1) @ np.linalg.inv(k).T
    if kind == "ray_distance":
        rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    elif kind != "z_depth":
        raise ValueError("Back-projection unavailable: unsupported depth kind")
    return np.asarray(rays * depth[..., None], dtype="<f4")


def triangulate(points, depth, valid, parameters):
    """Only complete valid grid cells; reject every discontinuous/long edge."""
    if set(parameters) != set(MESH_PARAMETERS) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or v <= 0
            for v in parameters.values()):
        raise ValueError("Mesh thresholds must be finite positive relative values")
    h, w = depth.shape
    grid = np.arange(h*w, dtype=np.uint32).reshape(h, w)
    a, b, c, d = grid[:-1, :-1], grid[:-1, 1:], grid[1:, :-1], grid[1:, 1:]
    cells = valid[:-1, :-1] & valid[:-1, 1:] & valid[1:, :-1] & valid[1:, 1:]
    faces = np.concatenate((np.stack((a[cells], c[cells], b[cells]), axis=-1),
                            np.stack((b[cells], c[cells], d[cells]), axis=-1)))
    p = points.reshape(-1, 3)[faces].astype(np.float64)
    z = depth.reshape(-1)[faces].astype(np.float64)
    scale = z.min(axis=1)
    keep = np.isfinite(p).all(axis=(1, 2))
    for i, j in ((0, 1), (1, 2), (2, 0)):
        keep &= np.abs(z[:, i]-z[:, j]) <= parameters["relative_depth_jump"]*scale
        keep &= np.linalg.norm(p[:, i]-p[:, j], axis=1) <= parameters["relative_edge_length"]*scale
    area = np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1)
    keep &= area > parameters["relative_double_area"] * scale**2
    return np.ascontiguousarray(faces[keep], dtype="<u4")


class DerivedStore:
    """Single-process coordination, shared across service instances/requests.

    Complete generations are immutable. Interrupted staging directories remain
    diagnostic files and are never candidates for reuse. No automatic deletion.
    """
    _guard = threading.Lock()
    _locks = {}

    def get(self, run, identity, generate):
        key = hashlib.sha256(canonical(identity)).hexdigest()
        location = derived_path(run, f"derived/{key}")
        with self._guard:
            lock = self._locks.setdefault(str(location), threading.Lock())
        with lock:
            location.mkdir(parents=True, exist_ok=True)
            complete = sorted(p for p in location.iterdir() if not p.name.startswith(".partial-"))
            if complete:
                if len(complete) != 1 or not complete[0].is_dir():
                    raise ArtifactIntegrityError("Invalid derived cache generations; explicit repair required")
                folder = derived_path(run, complete[0].relative_to(run).as_posix())
                manifest_path = derived_path(run, (folder / "manifest.json").relative_to(run).as_posix())
                if not manifest_path.is_file():
                    raise ArtifactIntegrityError("Incomplete derived cache; explicit repair required")
                manifest = read_json(manifest_path)
                if (manifest.get("schema_version") != "1.0" or manifest.get("key") != key
                        or manifest.get("identity") != identity or manifest.get("generation_id") != folder.name):
                    raise ArtifactIntegrityError("Derived cache identity mismatch; explicit repair required")
                ref = manifest.get("output", {})
                if ref.get("path") != (folder / "geometry.npz").relative_to(run).as_posix():
                    raise ArtifactIntegrityError("Invalid derived output path")
                path = derived_path(run, ref["path"])
                validate_artifact(run, ref)
                arrays = self._read(path, manifest.get("arrays"))
                return arrays, manifest, True
            generation = uuid.uuid4().hex
            staging = derived_path(run, f"derived/{key}/.partial-{generation}")
            staging.mkdir()
            arrays = generate()
            self._validate(arrays)
            path = staging / "geometry.npz"
            with path.open("xb") as stream:
                np.savez(stream, **arrays)
                stream.flush()
                os.fsync(stream.fileno())
            final = location / generation
            ref = artifact_ref(run, path, media_type="application/x-npz")
            ref["path"] = (final / "geometry.npz").relative_to(run).as_posix()
            shapes = {name: {"shape": list(a.shape), "dtype": str(a.dtype)} for name, a in arrays.items()}
            manifest = {"schema_version": "1.0", "origin": "derived", "key": key,
                "generation_id": generation, "created_at": datetime.now(timezone.utc).isoformat(),
                "identity": identity, "output": ref, "arrays": shapes,
                "warnings": ["No coordinate transform or LOD; raw geometry is unchanged"]}
            write_json(staging / "manifest.json", manifest)
            os.rename(staging, final)
            return arrays, manifest, False

    @staticmethod
    def _validate(arrays):
        if set(arrays) not in ({"points"}, {"points", "faces"}):
            raise ArtifactIntegrityError("Invalid derived array names")
        p = arrays["points"]
        if (p.dtype != np.dtype("<f4") or p.ndim != 3 or p.shape[-1] != 3
                or min(p.shape) < 1 or p.size > MAX_PIXELS*3):
            raise ArtifactIntegrityError("Invalid derived points")
        if "faces" in arrays:
            f = arrays["faces"]
            if (f.dtype != np.dtype("<u4") or f.ndim != 2 or f.shape[1] != 3
                    or len(f) > MAX_PIXELS*2 or (f.size and (f.max() >= p.shape[0]*p.shape[1]
                    or not np.isfinite(p.reshape(-1, 3)[f]).all()))):
                raise ArtifactIntegrityError("Invalid derived faces")

    def _read(self, path, expected):
        # Digest was checked first. Disable pickle, bound uncompressed members.
        import zipfile
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > 2 or any(i.file_size > MAX_PIXELS*24+4096 for i in archive.infolist()):
                raise ArtifactIntegrityError("Derived payload exceeds limits")
        with np.load(path, allow_pickle=False) as payload:
            arrays = {name: payload[name] for name in payload.files}
        self._validate(arrays)
        if expected != {name: {"shape": list(a.shape), "dtype": str(a.dtype)} for name, a in arrays.items()}:
            raise ArtifactIntegrityError("Derived array description mismatch")
        return arrays


class ResultsService:
    def __init__(self, store, collect):
        self.store, self.collect = store, collect
        self.derived = DerivedStore()

    def load(self, run_id):
        run = run_path(self.store.root, run_id)
        data = read_json(contained_path(run, f"attempts/{ATTEMPT_ID}/handle.json"))
        handle = JobHandle(**{k: data[k] for k in JobHandle.__dataclass_fields__ if k in data})
        if handle.run_id != run_id:
            raise ArtifactIntegrityError("Saved Run / handle identity mismatch")
        result = self.collect(handle).to_dict()
        if result["status"] != "COMPLETED" or not result["outputs"]:
            raise ValueError("Viewer unavailable: this Run has no completed output; see JobResult")
        output = result["outputs"][0]
        if math.prod(output["metadata"]["shape"]) > MAX_PIXELS:
            raise ValueError(f"Viewer unavailable: exceeds {MAX_PIXELS:,} output pixels; raw artifacts are preserved")
        return run, result, output

    def view(self, run_id, mode):
        if mode not in ("Depth", "RawDepth", "Point Cloud", "Mesh"):
            raise ValueError("Unknown Results mode")
        run, result, output = self.load(run_id)
        metadata = output["metadata"]
        def array(name):
            return np.load(contained_path(run, output[name]["path"]), allow_pickle=False)
        depth = array("depth")
        valid, colors, rgba, stats = depth_view(depth, array("mask") if "mask" in output else None)
        stats.update({k: metadata.get(k, "unavailable") for k in ("depth_kind", "depth_unit", "scale_type", "camera_frame")})
        payload = {"run_id": run_id, "mode": mode, "stats": stats, "origin": "model raw depth",
                   "frame": FRAME, "unit": metadata["depth_unit"], "scale": metadata["scale_type"]}
        if mode == "Depth":
            payload["image"] = png_url(rgba)
            return payload
        if mode == "RawDepth":
            payload["download"] = base64.b64encode(contained_path(run, output["depth"]["path"]).read_bytes()).decode()
            return payload
        # Include all validated raw artifacts plus RGB/job snapshots. This is a
        # conservative dependency set; changing any source invalidates reuse.
        job = read_json(contained_path(run, "job.json"))
        source = job["inputs"][0]
        identity = {"algorithm": "grid-triangulation" if mode == "Mesh" else "pinhole-backprojection",
            "version": "1", "parameters": dict(MESH_PARAMETERS) if mode == "Mesh" else {},
            "run_id": run_id, "attempt_id": result["attempt_id"], "view_id": output["view_id"],
            "inputs": result["artifacts"] + [source], "metadata": metadata,
            "job_sha256": sha256_file(run / "job.json"),
            "frame": FRAME, "unit": metadata["depth_unit"], "scale": metadata["scale_type"],
            "numpy_version": np.__version__, "lod": "none", "texture": "original RGB; identity grid only"}
        generated = None
        if "points" in output:
            points = array("points")
            payload["origin"] = "model points (saved raw)"
        else:
            meaning = metadata.get("geometry", {}).get("intrinsics", {})
            if ("intrinsics" not in output or meaning.get("camera_model") != "pinhole"
                    or meaning.get("pixel_center") != "integer" or meaning.get("grid") != list(depth.shape)
                    or metadata.get("camera_frame") != FRAME):
                raise ValueError("3D unavailable: no saved points or defined pinhole camera / pixel K. No geometry is invented.")
            point_identity = {**identity, "algorithm": "pinhole-backprojection", "parameters": {}}
            arrays, generated, reuse = self.derived.get(run, point_identity,
                lambda: {"points": np.where(valid[..., None], backproject(depth, array("intrinsics"), metadata["depth_kind"]), np.nan).astype("<f4")})
            points = arrays["points"]
            payload.update(origin="derived points from saved depth + pixel K", point_cache_reused=reuse)
        faces = None
        if mode == "Mesh":
            arrays, generated, reuse = self.derived.get(run, identity,
                lambda: {"points": points, "faces": triangulate(points, depth, valid, identity["parameters"])})
            points, faces = arrays["points"], arrays["faces"]
            payload.update(origin="derived mesh from " + payload["origin"], cache_reused=reuse)
        # RGB mapping is deliberately conservative. Do not guess resize/crop.
        rgb = None
        rgb_reason = "RGB unavailable: recorded input→output identity grid correspondence is missing"
        mapping = metadata.get("image_to_output", {})
        if mapping == {"type": "identity", "pixel_center": "integer"} and metadata["original_size"] == metadata["output_size"]:
            with Image.open(contained_path(run, source["path"])) as image:
                if image.size == (depth.shape[1], depth.shape[0]):
                    rgb = np.asarray(image.convert("RGB"))
                    rgb_reason = ""
        flat = valid.reshape(-1)
        normals = array("normals")[valid] if "normals" in output else None
        # Compact valid vertices and remap faces. Coordinates retain saved units.
        remap = np.full(flat.size, -1, dtype=np.int64)
        remap[flat] = np.arange(flat.sum())
        payload.update(positions=encoded(points[valid], "<f4"), count=int(flat.sum()),
            depth_colors=encoded(colors[valid], "<f4"), rgb_reason=rgb_reason,
            rgb_colors=encoded(rgb[valid]/255, "<f4") if rgb is not None else None,
            normal_colors=encoded((normals+1)/2, "<f4") if normals is not None else None,
            normal_orientation=metadata.get("geometry", {}).get("normals", {}).get("orientation", "unavailable"),
            normal_reason="" if normals is not None else "Normal color unavailable: no saved native normals",
            derived=generated)
        if faces is not None:
            y, x = np.indices(depth.shape)
            uv = np.stack(((x+0.5)/depth.shape[1], 1-(y+0.5)/depth.shape[0]), axis=-1)
            payload.update(faces=encoded(remap[faces], "<u4"), face_count=len(faces),
                uv=encoded(uv[valid], "<f4"), texture=png_url(rgb) if rgb is not None else None)
        return payload
