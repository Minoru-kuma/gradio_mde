import copy
import itertools
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import Mock

from mde.backends import LocalBackend
from mde.contracts import ArtifactIntegrityError, GEOMETRY_PROFILE, JobSpec
from mde.geometry import inspect_array
from mde.storage import artifact_ref, read_json, sha256_file, validate_outputs
from tests import test_local_contract as local_contract

PROJECT = local_contract.PROJECT


class GeometryArtifactTests(unittest.TestCase):
    setUp = local_contract.LocalContractTests.setUp
    stop_workers = local_contract.LocalContractTests.stop_workers

    def run_geometry(self, outputs=("depth", "points", "normals", "intrinsics", "mask"), action="success"):
        handle = self.runner.submit("geometry", PROJECT / "tests/assets/sample.png", device="cpu",
                                    requested_outputs=outputs, parameters={"action": action})
        self.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
        return handle, self.runner.collect(handle), self.store.root / handle.run_id

    def test_optional_combinations_and_no_model_mask(self):
        for size in range(4):
            for subset in itertools.combinations(("points", "normals", "intrinsics"), size):
                with self.subTest(subset=subset):
                    handle, result, run = self.run_geometry(("depth", *subset))
                    self.assertEqual(result.status, "COMPLETED", result.error)
                    self.assertEqual({key for key in ("points", "normals", "intrinsics") if key in result.outputs[0]}, set(subset))
                    if subset:
                        self.assertEqual(result.execution["serialization_profile"], GEOMETRY_PROFILE)
                        mask = run / result.outputs[0]["mask"]["path"]
                        offset = inspect_array(mask, [256, 256], "bool")
                        with mask.open("rb") as stream:
                            stream.seek(offset)
                            self.assertEqual(stream.read(2), b"\x00\x01")
                    JobSpec.from_dict(read_json(run / "job.json"))
                    self.assertEqual(LocalBackend(self.store.root).collect(handle).to_dict(), result.to_dict())
        _, result, _ = self.run_geometry(("depth", "points"), "missing_mask")
        self.assertEqual(result.status, "COMPLETED", result.error)
        self.assertNotIn("model_mask", result.outputs[0])

    def test_mask_only_and_ray_distance(self):
        _, result, _ = self.run_geometry(("depth", "mask"))
        self.assertEqual(result.status, "COMPLETED", result.error)
        _, result, _ = self.run_geometry(action="ray")
        self.assertEqual(result.status, "COMPLETED", result.error)

    def test_requested_missing_and_invalid_geometry_fail(self):
        for action in ("missing_points", "missing_normals", "missing_intrinsics", "missing_mask",
                       "shape", "object", "nonfinite", "scale", "normal", "intrinsics", "mask_shape",
                       "mask_dtype", "provenance", "frame"):
            with self.subTest(action=action):
                _, result, run = self.run_geometry(action=action)
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(result.outputs, [])
                self.assertIn("fake unloaded", (run / "logs/attempt-0001/stdout.log").read_text())

    def test_optional_requests_rejected_before_run_creation(self):
        for outputs in (("depth", "points"), ("points",), ("depth", "rays"), ("depth", "depth")):
            with self.subTest(outputs=outputs), self.assertRaises(ValueError):
                self.runner.submit("fake", PROJECT / "tests/assets/sample.png", device="cpu", requested_outputs=outputs)
        self.assertFalse(self.store.root.exists() and list(self.store.root.iterdir()))

    def test_geometry_roundtrip_is_read_only_and_no_worker_restarted(self):
        handle, result, run = self.run_geometry()
        self.assertEqual(result.status, "COMPLETED", result.error)
        for key, expected in (("points", (0.25, -0.5, 2.5)), ("normals", (0.0, 0.0, -1.0))):
            ref = result.outputs[0][key]
            path = run / ref["path"]
            offset = inspect_array(path, ref["shape"], ref["dtype"])
            with path.open("rb") as stream:
                stream.seek(offset + 12)
                self.assertEqual(struct.unpack("<3f", stream.read(12)), expected)
        before = {str(p): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
        manager = Mock()
        fresh = LocalBackend(self.store.root, manager)
        fresh.collect(handle); fresh.collect(handle)
        manager.start.assert_not_called()
        self.assertEqual(before, {str(p): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()})
        self.assertEqual((run / "logs/attempt-0001/stdout.log").read_text().count("geometry predict"), 1)
        env = {**os.environ, "PYTHONPATH": str(PROJECT / "src"), "MDE_CONDA_EXE": "/missing/conda"}
        collect = subprocess.run([sys.executable, "-m", "mde.cli", "collect", "--run-id", handle.run_id,
                                  "--run-root", str(self.store.root)], env=env, capture_output=True, text=True)
        self.assertEqual(collect.returncode, 0, collect.stderr)
        self.assertEqual(before, {str(p): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()})

    def test_optional_reference_path_checksum_and_payload_corruption(self):
        _, result, run = self.run_geometry()
        self.assertEqual(result.status, "COMPLETED", result.error)
        for key in ("points", "normals", "intrinsics", "mask", "model_mask"):
            for mutation in ("missing", "digest", "shape", "dtype", "unit", "outside", "other_run", "duplicate"):
                with self.subTest(key=key, mutation=mutation):
                    report = copy.deepcopy(result.to_dict())
                    ref = report["outputs"][0][key]
                    if mutation == "missing": report["artifacts"].remove(ref)
                    elif mutation == "digest": ref["sha256"] = "0" * 64
                    elif mutation == "shape": ref["shape"] = [1]
                    elif mutation == "dtype": ref["dtype"] = "object"
                    elif mutation == "unit": ref["unit"] = "incorrect"
                    elif mutation == "outside": ref["path"] = "../outside.npy"
                    elif mutation == "other_run": ref["path"] = "input/other-run.npy"
                    else: report["artifacts"].append(copy.deepcopy(ref))
                    with self.assertRaises((ArtifactIntegrityError, ValueError)):
                        validate_outputs(run, report)
        path = run / result.outputs[0]["points"]["path"]
        original = path.read_bytes()
        path.write_bytes(original[:-4])
        with self.assertRaises(ArtifactIntegrityError): LocalBackend(self.store.root).collect(self.backend._jobs[next(iter(self.backend._jobs))].handle)
        path.write_bytes(original)
        external = Path(self.temporary.name) / "outside.npy"
        external.write_bytes(original)
        path.unlink(); path.symlink_to(external)
        with self.assertRaises(ArtifactIntegrityError): validate_outputs(run, result.to_dict())

    def test_semantic_payload_tampering_with_valid_digest_is_rejected(self):
        _, result, run = self.run_geometry()
        cases = (("points", 1, "<3f", (0.25, -0.5, 9)),
                 ("normals", 1, "<3f", (0, 0, 0.5)),
                 ("intrinsics", 0, "<f", (-1,)),
                 ("mask", 1, "B", (2,)), ("model_mask", 1, "B", (0,)))
        for key, index, fmt, values in cases:
            path = run / result.outputs[0][key]["path"]
            original = path.read_bytes()
            ref = result.outputs[0][key]
            offset = inspect_array(path, ref["shape"], ref["dtype"])
            with path.open("r+b") as stream:
                stream.seek(offset + index * struct.calcsize(fmt))
                stream.write(struct.pack(fmt, *values))
            report = copy.deepcopy(result.to_dict())
            changed = artifact_ref(run, path, **{k:v for k,v in ref.items() if k not in ("path","sha256","size_bytes")})
            report["outputs"][0][key] = changed
            report["artifacts"] = [changed if item["path"] == ref["path"] else item for item in report["artifacts"]]
            with self.subTest(key=key), self.assertRaises(ArtifactIntegrityError): validate_outputs(run, report)
            path.write_bytes(original)

    def test_npy_header_rejects_object_fortran_shape_and_payload(self):
        path = Path(self.temporary.name) / "bad.npy"
        for dtype, shape, fortran, payload in (("|O", (2,2,3), False, b""),
                ("<f4", (2,2,3), True, b""), ("<f4", (2,2,2), False, b""),
                ("<f4", (True,2,3), False, b""), ("<f4", (2,2,3), False, b"short")):
            header = repr({"descr":dtype,"shape":shape,"fortran_order":fortran}).encode()+b"\n"
            path.write_bytes(b"\x93NUMPY\x01\x00"+struct.pack("<H",len(header))+header+payload)
            with self.subTest(dtype=dtype,shape=shape,fortran=fortran), self.assertRaises(ArtifactIntegrityError):
                inspect_array(path, [2,2,3], "float32")

    def test_geometry_metadata_and_profile_mismatch_is_rejected(self):
        _, result, run = self.run_geometry()
        for mutation in ("profile", "native", "frame", "scale", "grid", "normal_orientation", "requested"):
            report = copy.deepcopy(result.to_dict())
            metadata = report["outputs"][0]["metadata"]
            if mutation == "profile": report["execution"]["serialization_profile"] = "01A-depth-only"
            elif mutation == "native": metadata["geometry"]["points"]["origin"] = "derived"
            elif mutation == "frame": metadata["geometry"]["points"]["camera_frame"] = "unknown"
            elif mutation == "scale": metadata["geometry"]["points"]["scale_type"] = "metric"
            elif mutation == "grid": metadata["geometry"]["intrinsics"]["grid"] = [1,1]
            elif mutation == "normal_orientation": metadata["geometry"]["normals"].pop("orientation")
            else: metadata["requested_outputs"] = ["depth", "rays"]
            with self.subTest(mutation=mutation), self.assertRaises((ArtifactIntegrityError, ValueError)):
                validate_outputs(run, report)

    def test_published_worker_result_cannot_be_overwritten(self):
        _, result, run = self.run_geometry()
        before = {str(p): sha256_file(p) for p in run.rglob("*") if p.is_file()}
        # Direct invocation exercises the overwrite guard before any inference starts.
        prefix = os.environ.get("MDE_TEST_CONDA_PREFIX")
        command = ["conda", "run", "--no-capture-output", *( ["-p",prefix] if prefix else ["-n",os.environ.get("MDE_TEST_CONDA_ENV","mde-moge")]),
                   "python", "-m", "mde.worker", "--job", str(run / "job.json"), "--run-dir", str(run)]
        process = subprocess.run(command, env={**os.environ, "PYTHONPATH":str(PROJECT / "src")}, capture_output=True, text=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("immutable", process.stderr)
        self.assertEqual(before, {str(p): sha256_file(p) for p in run.rglob("*") if p.is_file()})

    def test_native_mapping_preserves_points_and_converts_k_pixel_centers(self):
        script = '''import numpy as np
from models.moge.adapter import map_native_geometry
class Tensor:
 def __init__(self,x): self.x=x
 def detach(self): return self
 def cpu(self): return self
 def numpy(self): return self.x
p=np.array([[[1.,2.,3.]]],dtype=np.float32)
k=np.array([[2,0,.5],[0,3,.5],[0,0,1]],dtype=np.float32)
n=np.array([[[0.,0.,-1.]]],dtype=np.float32)
values,meta=map_native_geometry({'points':Tensor(p),'intrinsics':Tensor(k),'normal':Tensor(n)},('depth','points','normals','intrinsics'),(20,40))
np.testing.assert_array_equal(values['points'],p)
np.testing.assert_array_equal(values['normals'],n)
np.testing.assert_array_equal(values['intrinsics'],[[80,0,19.5],[0,60,9.5],[0,0,1]])
assert meta['intrinsics']['native_intrinsics']==k.tolist()
assert map_native_geometry({},('depth','points'),(20,40))[0]=={}
'''
        prefix = os.environ.get("MDE_TEST_CONDA_PREFIX")
        cmd = ["conda","run", *( ["-p",prefix] if prefix else ["-n",os.environ.get("MDE_TEST_CONDA_ENV","mde-moge")]), "python","-c",script]
        process = subprocess.run(cmd, cwd=PROJECT, env={**os.environ,"PYTHONPATH":str(PROJECT / "src")},capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
