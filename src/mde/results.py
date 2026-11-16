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
from .run_access import run_lock, locked_view, write_sidecar
from .geometry import FRAME
from .cameras import align_camera, output_transform, pixel_k
from .storage import (artifact_ref, contained_path, read_json, run_path,
                      sha256_file, validate_artifact, write_json, json_metadata)

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
    # Normalize rays in float64: a finite float32 K can still produce rays
    # whose squared length overflows float32 and collapses range points to 0.
    y, x = np.indices(depth.shape, dtype=np.float64)
    rays = np.stack((x, y, np.ones_like(x)), axis=-1) @ np.linalg.inv(pixel_k(k)).T
    if kind == "ray_distance":
        length=np.linalg.norm(rays,axis=-1,keepdims=True)
        if not np.isfinite(length).all() or (length<=0).any():
            raise ValueError('Invalid camera rays for range backprojection')
        rays /= length
    elif kind != "z_depth":
        raise ValueError("Back-projection unavailable: unsupported depth kind")
    return np.asarray(rays * depth[..., None], dtype="<f4")


def validate_reconstructed_points(points, depth, valid, kind):
    if not np.isfinite(points[valid]).all():
        raise ArtifactIntegrityError('Derived points exceed finite float32 range; check camera K and depth')
    if kind == 'z_depth' and not np.allclose(
            points[..., 2][valid], depth[valid], rtol=1e-6, atol=0):
        raise ArtifactIntegrityError('Derived points Z / z-depth mismatch')


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

    def get(self, run, identity, generate, *, force=False, provenance=None):
        key = hashlib.sha256(canonical(identity)).hexdigest()
        location = derived_path(run, f"derived/{key}")
        with self._guard:
            lock = self._locks.setdefault(str(location), threading.Lock())
        with run_lock(run), lock:
            location.mkdir(parents=True, exist_ok=True)
            folder = self._select(run, location) if not force else None
            if folder is not None:
                manifest_path = derived_path(run, (folder / "manifest.json").relative_to(run).as_posix())
                if not manifest_path.is_file():
                    raise ArtifactIntegrityError("Incomplete derived cache; explicit repair required")
                manifest = read_json(manifest_path)
                if (manifest.get("schema_version") != "1.0" or manifest.get("key") != key
                        or manifest.get("identity") != identity or manifest.get("generation_id") != folder.name):
                    raise ArtifactIntegrityError("Derived cache identity mismatch; explicit repair required")
                if manifest.get("publication_protocol") == "history-commit-v1":
                    history_path = derived_path(run, "derived/history.json")
                    events = read_json(history_path)["events"] if history_path.exists() else []
                    if not any(e.get("operation") in ("generate", "regenerate") and e.get("manifest") == manifest for e in events):
                        raise ArtifactIntegrityError("Uncommitted derived generation")
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
            try:
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
                    "generation_id": generation, "publication_protocol": "history-commit-v1", "created_at": datetime.now(timezone.utc).isoformat(),
                    "identity": identity, "output": ref, "arrays": shapes,
                    "warnings": ["No coordinate transform or LOD; raw geometry is unchanged"]}
                if provenance is not None:
                    manifest['provenance'] = json_metadata(provenance(), 'Derived provenance')
                write_json(staging / "manifest.json", manifest)
                os.rename(staging, final)
                history_path = derived_path(run, "derived/history.json")
                history = read_json(history_path) if history_path.exists() else {"schema_version": "1.0", "events": []}
                history["events"].append({"operation": "regenerate" if force else "generate", "manifest": manifest})
                write_sidecar(run, "derived/history.json", history)
                write_sidecar(run, (location / "current.json").relative_to(run).as_posix(), {"generation_id": generation})
                return arrays, manifest, False
            except Exception as error:
                history_path = derived_path(run, "derived/history.json")
                history = read_json(history_path) if history_path.exists() else {"schema_version": "1.0", "events": []}
                history["events"].append({"operation": "failed", "generation_id": generation,
                    "target": (location / generation).relative_to(run).as_posix(),
                    "identity": identity, "error": str(error)})
                write_sidecar(run, "derived/history.json", history)
                raise

    def _select(self, run, location):
        """Prefer the recorded selection; otherwise newest completed generation.

        Deletion requests are durable exclusions, including partially removed
        generations. Corruption is reported rather than silently skipped.
        """
        history_path = derived_path(run, "derived/history.json")
        history = read_json(history_path) if history_path.exists() else {"events": []}
        excluded = {e.get("target") for e in history["events"]
                    if e.get("operation") in ("delete_requested", "deleted", "failed")}
        committed = {e.get("manifest", {}).get("generation_id") for e in history["events"]
                     if e.get("operation") in ("generate", "regenerate")}
        pointer = derived_path(run, (location / "current.json").relative_to(run).as_posix())
        if pointer.exists():
            selected = read_json(pointer).get("generation_id")
            if not isinstance(selected, str) or len(selected) != 32 or any(c not in "0123456789abcdef" for c in selected):
                raise ArtifactIntegrityError("Invalid generation pointer")
            candidate = location / selected
            if candidate.relative_to(run).as_posix() not in excluded:
                if not candidate.is_dir():
                    raise ArtifactIntegrityError("Incomplete derived cache; explicit repair required")
                return derived_path(run, candidate.relative_to(run).as_posix())
        candidates = []
        for folder in location.iterdir():
            if folder.name == "current.json" or folder.name.startswith(".partial-"):
                continue
            relative = folder.relative_to(run).as_posix()
            derived_path(run, relative)
            if relative in excluded:
                continue
            if not folder.is_dir():
                raise ArtifactIntegrityError("Invalid derived cache entry")
            path = derived_path(run, relative + "/manifest.json")
            if not path.is_file():
                raise ArtifactIntegrityError("Incomplete derived cache; explicit repair required")
            manifest = read_json(path)
            if manifest.get("publication_protocol") == "history-commit-v1" and folder.name not in committed:
                continue
            try:
                created = datetime.fromisoformat(manifest["created_at"])
                if created.tzinfo is None:
                    raise ValueError("Missing timezone")
            except (KeyError, TypeError, ValueError) as error:
                raise ArtifactIntegrityError("Invalid generation creation time") from error
            candidates.append((created, folder.name, folder))
        return max(candidates, key=lambda item: (item[0], item[1]))[2] if candidates else None

    @staticmethod
    def _validate(arrays):
        if set(arrays) == {"intrinsics"}:
            if arrays['intrinsics'].dtype != np.dtype('<f4'):
                raise ArtifactIntegrityError('Invalid derived camera dtype')
            try:
                pixel_k(arrays['intrinsics'])
            except ValueError as error:
                raise ArtifactIntegrityError(str(error)) from error
            return
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
    def __init__(self, store, collect, *, camera_estimator=None):
        self.store, self.collect = store, collect
        self.derived = DerivedStore()
        self.camera_estimator = camera_estimator

    def _camera(self, run, result, output, source, known_camera):
        metadata=output['metadata'];shape=metadata['shape']
        source_shape=[source['original_size']['height'],source['original_size']['width']]
        if metadata.get('camera_frame') != FRAME:
            raise ValueError('3D unavailable: depth camera frame is not OpenCV')
        if known_camera is not None:
            k,provenance=align_camera(known_camera,metadata,source_shape,shape)
            return k,{'source':'known',**provenance}
        if 'intrinsics' in output:
            meaning=metadata.get('geometry',{}).get('intrinsics',{})
            camera={'K':np.load(contained_path(run,output['intrinsics']['path']),allow_pickle=False),
                'grid_space':'depth',
                'grid':meaning.get('grid'),'pixel_center':meaning.get('pixel_center'),
                'camera_model':meaning.get('camera_model'),'camera_frame':metadata.get('camera_frame')}
            k,provenance=align_camera(camera,metadata,source_shape,shape)
            return k,{'source':'model native','artifact':output['intrinsics'],'meaning':meaning,**provenance}
        # Calibration is on the input RGB grid. Refuse unknown resize/crop even
        # when dimensions happen to match, before starting any model task.
        output_transform(metadata,source_shape,shape)
        base={'algorithm':'single-image-calibration','version':'1','run_id':result['run_id'],
              'attempt_id':result['attempt_id'],'view_id':output['view_id'],'inputs':[source],
              'job_sha256':sha256_file(run/'job.json'),'grid':source_shape,'frame':FRAME}
        if self.camera_estimator is not None:
            identity={**base,'provider':self.camera_estimator.identity()}
        else:
            history_path=derived_path(run,'derived/history.json')
            history=read_json(history_path) if history_path.exists() else {'events':[]}
            candidates=[e['manifest']['identity'] for e in history['events']
                if e.get('operation') in ('generate','regenerate')
                and {k:v for k,v in e.get('manifest',{}).get('identity',{}).items() if k!='provider'}==base]
            if not candidates:
                raise ValueError('3D unavailable: no saved points or defined pinhole camera / pixel K; configure a camera estimator. No fixed FOV is substituted.')
            identity=candidates[-1]
        observation={}
        def estimate():
            if self.camera_estimator is None:
                raise ValueError('Calibration cache unavailable; configure a camera estimator to create it')
            camera=self.camera_estimator.estimate(contained_path(run,source['path']))
            observation.update(camera.get('execution',{}))
            # Store only K on its original grid; no gravity / pose is exported.
            k,prov=align_camera({**camera,'grid_space':'source'},{'image_to_output':{'type':'identity','pixel_center':'integer'}},source_shape,source_shape)
            return {'intrinsics':k}
        arrays,manifest,reused=self.derived.get(run,identity,estimate,provenance=lambda:observation)
        camera={'K':arrays['intrinsics'],'grid':source_shape,'pixel_center':'integer',
                'grid_space':'source',
                'camera_model':'pinhole','camera_frame':FRAME}
        k,provenance=align_camera(camera,metadata,source_shape,shape)
        return k,{'source':'estimated','calibration_key':manifest['key'],
            'calibration_output':manifest['output'],'provider':identity['provider'],
            'execution':manifest.get('provenance',{}),**provenance}

    @locked_view
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

    @locked_view
    def view(self, run_id, mode, *, regenerate=False, known_camera=None):
        if mode not in ("Depth", "RawDepth", "Point Cloud", "Mesh"):
            raise ValueError("Unknown Results mode")
        run, result, output = self.load(run_id)
        metadata = output["metadata"]
        def array(name):
            return np.load(contained_path(run, output[name]["path"]), allow_pickle=False)
        depth = array("depth")
        valid, colors, rgba, stats = depth_view(depth, array("mask") if "mask" in output else None)
        stats.update({k: metadata.get(k, "unavailable") for k in ("depth_kind", "depth_unit", "scale_type", "camera_frame")})
        if len(result['outputs']) > 1:
            stats.update(view_id=output['view_id'], view_count=len(result['outputs']), preview='first input view')
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
        source = next(source for source in job["inputs"] if source["view_id"] == output["view_id"])
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
            k,camera_provenance=self._camera(run,result,output,source,known_camera)
            identity={**identity,'camera':camera_provenance,'version':'2'}
            point_identity = {**identity, "algorithm": "pinhole-backprojection", "parameters": {}}
            def reconstruct():
                with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
                    reconstructed=backproject(depth,k,metadata['depth_kind'])
                validate_reconstructed_points(reconstructed,depth,valid,metadata['depth_kind'])
                return {'points':np.where(valid[...,None],reconstructed,np.nan).astype('<f4')}
            arrays, generated, reuse = self.derived.get(run, point_identity, reconstruct)
            points = arrays["points"]
            validate_reconstructed_points(points,depth,valid,metadata['depth_kind'])
            payload.update(origin="derived points from saved depth + pixel K", point_cache_reused=reuse,
                           camera=camera_provenance)
        if not np.isfinite(points[valid]).all():
            raise ArtifactIntegrityError('Nonfinite points at valid depth pixels')
        faces = None
        if mode == "Mesh":
            arrays, generated, reuse = self.derived.get(run, identity,
                lambda: {"points": points, "faces": triangulate(points, depth, valid, identity["parameters"])}, force=regenerate)
            points, faces = arrays["points"], arrays["faces"]
            if "points" not in output:
                validate_reconstructed_points(points,depth,valid,metadata['depth_kind'])
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
