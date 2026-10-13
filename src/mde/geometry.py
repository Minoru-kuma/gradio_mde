"""Geometry profile validation using bounded stdlib reads; no model imports."""
import ast
import math
import struct
from contextlib import ExitStack

from .contracts import ATTEMPT_ID, VIEW_ID, ArtifactIntegrityError, GEOMETRY_PROFILE, normalize_outputs
from .storage import contained_path, read_json


FRAME = "opencv_x_right_y_down_z_forward"
NORMAL_TOLERANCE = 1e-3
POINT_RTOL = 1e-4
POINT_ATOL = 1e-5


def inspect_array(path, shape, dtype):
    """Validate canonical NPY header/payload and return the payload offset."""
    descriptor, size = {"float32": ("<f4", 4), "bool": ("|b1", 1)}[dtype]
    with path.open("rb") as stream:
        if stream.read(6) != b"\x93NUMPY":
            raise ArtifactIntegrityError("Invalid geometry NPY magic")
        version = stream.read(2)
        if version not in (b"\x01\x00", b"\x02\x00"):
            raise ArtifactIntegrityError("Unsupported geometry NPY version")
        count = 2 if version[0] == 1 else 4
        raw_length = stream.read(count)
        if len(raw_length) != count:
            raise ArtifactIntegrityError("Truncated NPY length")
        length = int.from_bytes(raw_length, "little")
        if not 1 <= length <= 4096:
            raise ArtifactIntegrityError("Unexpected geometry NPY header size")
        try:
            header = ast.literal_eval(stream.read(length).decode("latin1"))
        except (ValueError, SyntaxError) as error:
            raise ArtifactIntegrityError("Invalid geometry NPY header") from error
        if (not isinstance(header, dict) or set(header) != {"descr", "shape", "fortran_order"}
                or header["descr"] != descriptor or header["fortran_order"] is not False
                or not isinstance(header["shape"], tuple)
                or any(type(axis) is not int or axis < 1 for axis in header["shape"])
                or list(header["shape"]) != shape):
            raise ArtifactIntegrityError("Geometry dtype / shape / layout mismatch")
        offset = stream.tell()
        if path.stat().st_size != offset + math.prod(shape) * size:
            raise ArtifactIntegrityError("Geometry payload size mismatch")
        return offset


def rows(stream, fmt):
    width = struct.calcsize(fmt)
    while data := stream.read(width * 4096):
        yield from struct.iter_unpack(fmt, data)


def validate_geometry(run, report):
    output = report["outputs"][0]
    metadata = output["metadata"]
    profile = report["execution"].get("serialization_profile", "01A-depth-only")
    job_requested = normalize_outputs(read_json(contained_path(run, "job.json"))["inference"]["requested_outputs"])
    optional = {key for key in ("points", "normals", "intrinsics", "mask", "model_mask") if key in output}
    if profile == "01A-depth-only":
        if optional or job_requested != ["depth"]:
            raise ArtifactIntegrityError("Geometry refs require geometry profile")
        return
    if profile != GEOMETRY_PROFILE:
        raise ArtifactIntegrityError("Unknown serialization profile")
    requested = normalize_outputs(metadata.get("requested_outputs"))
    if requested != job_requested:
        raise ArtifactIntegrityError("Requested outputs / JobSpec mismatch")
    geometry = metadata.get("geometry")
    if (not isinstance(geometry, dict) or set(geometry) != optional
            or "mask" not in optional or any(key not in output for key in requested)
            or ("mask" in requested and "model_mask" not in optional)):
        raise ArtifactIntegrityError("Missing requested geometry or geometry metadata")
    h, w = metadata["shape"]
    shapes = {"points": [h, w, 3], "normals": [h, w, 3], "intrinsics": [3, 3],
              "mask": [h, w], "model_mask": [h, w]}
    offsets = {}
    for key in optional:
        ref, meaning = output[key], geometry[key]
        dtype = "bool" if key in ("mask", "model_mask") else "float32"
        unit = metadata["depth_unit"] if key == "points" else "pixel" if key == "intrinsics" else "unitless"
        if (not isinstance(ref, dict) or ref not in report["artifacts"]
                or ref.get("path") != f"output/{ATTEMPT_ID}/views/{VIEW_ID}/{key}.npy"
                or ref.get("media_type") != "application/x-npy"
                or ref.get("shape") != shapes[key] or ref.get("dtype") != dtype or ref.get("unit") != unit):
            raise ArtifactIntegrityError(f"Invalid {key} artifact reference")
        if (not isinstance(meaning, dict) or meaning.get("origin") != ("validation" if key == "mask" else "model")
                or not isinstance(meaning.get("conversion"), str) or not meaning["conversion"]
                or (key != "mask" and (not isinstance(meaning.get("native_convention"), str)
                                       or not meaning["native_convention"]))):
            raise ArtifactIntegrityError(f"Missing {key} provenance")
        if key in ("points", "normals") and meaning.get("camera_frame") != FRAME:
            raise ArtifactIntegrityError("Geometry camera frame mismatch")
        if key == "points" and meaning.get("scale_type") != metadata["scale_type"]:
            raise ArtifactIntegrityError("Points scale mismatch")
        if key == "normals" and not isinstance(meaning.get("orientation"), str):
            raise ArtifactIntegrityError("Missing normal orientation")
        if key == "intrinsics" and (meaning.get("camera_model") != "pinhole"
                                    or meaning.get("pixel_center") != "integer"
                                    or meaning.get("grid") != [h, w]):
            raise ArtifactIntegrityError("Invalid intrinsics convention")
        offsets[key] = inspect_array(contained_path(run, ref["path"]), shapes[key], dtype)
    with ExitStack() as stack:
        streams = {}
        for key in optional | {"depth"}:
            path = contained_path(run, output[key]["path"])
            offset = offsets[key] if key in offsets else inspect_array(path, [h, w], "float32")
            stream = stack.enter_context(path.open("rb"))
            stream.seek(offset)
            streams[key] = stream
        if "intrinsics" in streams:
            k = struct.unpack("<9f", streams["intrinsics"].read(36))
            if (not all(math.isfinite(x) for x in k) or k[0] <= 0 or k[4] <= 0
                    or any(abs(k[i]) > 1e-6 for i in (3, 6, 7)) or abs(k[8] - 1) > 1e-6):
                raise ArtifactIntegrityError("Invalid pinhole intrinsics values")
        vectors = {key: rows(streams[key], "<3f") for key in ("points", "normals") if key in streams}
        model_mask = rows(streams["model_mask"], "B") if "model_mask" in streams else None
        valid_count = 0
        for (depth,), (valid,) in zip(rows(streams["depth"], "<f"), rows(streams["mask"], "B")):
            native_valid = next(model_mask)[0] if model_mask else 1
            if valid not in (0, 1) or native_valid not in (0, 1):
                raise ArtifactIntegrityError("Invalid bool payload")
            if bool(valid) != (math.isfinite(depth) and depth > 0) or (valid and not native_valid):
                raise ArtifactIntegrityError("Depth / effective / model mask mismatch")
            if not valid and not math.isnan(depth):
                raise ArtifactIntegrityError("Invalid depth must be NaN")
            valid_count += valid
            for key, iterator in vectors.items():
                vector = next(iterator)
                if not valid:
                    if not all(math.isnan(x) for x in vector):
                        raise ArtifactIntegrityError("Invalid geometry must be NaN")
                elif not all(math.isfinite(x) for x in vector):
                    raise ArtifactIntegrityError("Nonfinite valid geometry")
                elif key == "normals":
                    if abs(math.sqrt(sum(x*x for x in vector)) - 1) > NORMAL_TOLERANCE:
                        raise ArtifactIntegrityError("Normals must be unit vectors")
                else:
                    expected = vector[2] if metadata["depth_kind"] == "z_depth" else math.sqrt(sum(x*x for x in vector))
                    if not math.isclose(depth, expected, rel_tol=POINT_RTOL, abs_tol=POINT_ATOL):
                        raise ArtifactIntegrityError("Points / depth scale or kind mismatch")
        if (valid_count < 1 or metadata.get("valid_pixels") != valid_count
                or metadata.get("invalid_pixels") != h*w-valid_count):
            raise ArtifactIntegrityError("Geometry validity statistics mismatch")
