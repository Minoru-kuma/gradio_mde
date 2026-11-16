"""Synthetic contracts and local preparation checks; no acquisition or model inference."""
import json
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from mde.backends import LocalBackend
from mde.geometry import inspect_array
from mde.registry import ModelRegistry
from mde.storage import read_json, sha256_file
from tests import test_local_contract as local_contract

PROJECT = local_contract.PROJECT


class UniK3DNumericTests(unittest.TestCase):
    def test_checkpoint_verifies_both_files_and_rejects_same_size_tampering(self):
        from models.unik3d.checkpoint import verify_checkpoint
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            weights, config = b'synthetic weights', b'{"fixture":true}'
            (directory / 'model.safetensors').write_bytes(weights)
            (directory / 'config.json').write_bytes(config)
            reference = {'filename': 'model.safetensors', 'sha256': hashlib.sha256(weights).hexdigest(),
                'size_bytes': len(weights), 'config': {'filename': 'config.json',
                'sha256': hashlib.sha256(config).hexdigest(), 'size_bytes': len(config)}}
            self.assertEqual(verify_checkpoint(directory, reference)[1], {'fixture': True})
            with self.assertRaisesRegex(ValueError, 'prepared local'): verify_checkpoint(None, reference)
            (directory / 'model.safetensors').write_bytes(b'X' * len(weights))
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'): verify_checkpoint(directory, reference)
            (directory / 'model.safetensors').write_bytes(weights)
            (directory / 'config.json').unlink()
            with self.assertRaisesRegex(ValueError, 'missing or wrong size'): verify_checkpoint(directory, reference)

    def test_missing_preparation_and_fixture_checkpoint_fail_before_framework_or_path_access(self):
        script = '''
import sys
from types import SimpleNamespace
from models.unik3d.adapter import UniK3DAdapter
class PathMustNotBeUsed:
 def __str__(self): raise AssertionError('checkpoint inspected')
 def __fspath__(self): raise AssertionError('checkpoint opened')
def forbidden(context): raise AssertionError('runtime factory called')
for adapter, context in [(UniK3DAdapter(),SimpleNamespace(checkpoint=None)),
 (UniK3DAdapter(),SimpleNamespace(checkpoint=PathMustNotBeUsed(),device='cuda:0',dtype='float32')),
 (UniK3DAdapter(fixture_runtime_factory=forbidden),SimpleNamespace(checkpoint=PathMustNotBeUsed()))]:
 try: adapter.load(context)
 except ValueError: pass
 else: raise AssertionError('invalid native preparation or fixture checkpoint accepted')
 adapter.unload(); adapter.unload()
assert not set(sys.modules).intersection({'numpy','torch','unik3d','PIL'})
'''
        self.run_script(sys.executable, script)

    def test_native_tensor_bridge_with_fake_model_has_no_download_or_upstream_import(self):
        worker = PROJECT / '.local/envs/mde-unik3d/bin/python'
        if not worker.exists(): self.skipTest('Independent torch CPU environment required')
        script = '''
import sys
import numpy as np
import torch
from models.unik3d.adapter import NativeRuntime,map_prediction
class Model:
 def infer(self,rgb):
  assert rgb.shape==(3,2,4) and rgb.dtype==torch.uint8 and rgb.device.type=='cpu'
  assert torch.is_inference_mode_enabled() and not torch.is_grad_enabled()
  points=torch.zeros((1,3,2,4));points[:,0]=3;points[:,2]=-4
  return {'points':points,'depth':points[:,2:3],'distance':points.norm(dim=1,keepdim=True),
          'rays':points/5,'confidence':torch.ones((1,1,2,4))}
runtime=NativeRuntime(Model())
native=runtime.infer(np.zeros((2,4,3),dtype='uint8'))
assert set(native)=={'distance','points','depth'}
assert runtime.native_keys==['confidence','depth','distance','points','rays']
assert all(value.dtype==np.dtype('float32') for value in native.values())
output=map_prediction(native,'v',(2,4),('depth','points'),synthetic=False)
assert output.metadata['synthetic_contract_only'] is False
assert (output.depth==5).all() and (output.points[...,2]==-4).all()
assert output.intrinsics is None and output.mask is None and output.rays is None
runtime.close();assert runtime.model is None
assert 'unik3d' not in sys.modules
'''
        self.run_script(worker, script)

    def run_script(self, executable, script):
        call = subprocess.run([str(executable), '-c', script], cwd=PROJECT,
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(call.returncode, 0, call.stderr)

    def test_numeric_geometry_and_lifecycle(self):
        numeric = PROJECT / '.local/envs/mde-ui/bin/python'
        if not numeric.exists(): self.skipTest('Independent NumPy environment required')
        script = '''
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
from mde.contracts import PredictionRequest
from models.unik3d.adapter import UniK3DAdapter, map_prediction
from tests.fixtures.unik3d import NativeFixture
image=np.zeros((2,4,3),dtype='uint8')
native=NativeFixture().infer(image)
before={key:value.copy() for key,value in native.items()}
out=map_prediction(native,'view-0001',(2,4),('depth','points'))
assert out.view_id=='view-0001'
assert out.depth.shape==(2,4) and out.points.shape==(2,4,3)
assert out.depth.dtype==out.points.dtype==np.dtype('float32')
assert out.depth.flags.c_contiguous and out.points.flags.c_contiguous
assert np.isnan(out.depth[0,0]) and np.isnan(out.points[0,0]).all()
assert out.depth[0,1]==5 and out.points[0,1,2]==0
assert out.depth[1,0]==5 and out.points[1,0,2]==-4
assert out.depth[1,1]==5 and out.points[1,1,2]==4
np.testing.assert_array_equal(out.points[1],np.moveaxis(native['points'][0],0,-1)[1])
assert out.metadata['depth_kind']=='ray_distance'
assert out.metadata['scale_type']==out.metadata['depth_unit']=='unknown'
assert out.mask is None and out.intrinsics is None and out.rays is None
assert out.camera_pose is None and out.normals is None and out.confidence is None
assert map_prediction(native,'v',(2,4)).points is None
for key in before: np.testing.assert_array_equal(native[key],before[key])
def rejected(value,shape=(2,4),outputs=('depth','points')):
 try: map_prediction(value,'v',shape,outputs)
 except ValueError: return
 raise AssertionError('invalid geometry accepted')
rejected({});rejected({'distance':native['distance']});rejected(native,(4,2))
rejected(native,(0,4));rejected(native,(True,4));rejected(native,outputs=('depth','mask'))
for key in ('distance','points','depth'):
 for value in (native[key].astype('float64'),native[key][0],native[key].astype(object)):
  bad=deepcopy(native);bad[key]=value;rejected(bad)
bad=deepcopy(native);bad['distance'][0,0,1,0]=4;rejected(bad)
bad=deepcopy(native);bad['depth'][0,0,1,0]=4;rejected(bad)
for value in (0.,-1.,np.inf,np.nan):
 bad=deepcopy(native);bad['distance'][0,0,1,0]=value
 assert np.isnan(map_prediction(bad,'v',(2,4)).depth[1,0])
bad=deepcopy(native);bad['points'][0,0,1,0]=np.inf
assert np.isnan(map_prediction(bad,'v',(2,4)).depth[1,0])
class Runtime(NativeFixture):
 def __init__(self): self.calls=0;self.closed=0
 def infer(self,image): self.calls+=1;return super().infer(image)
 def close(self): self.closed+=1
runtime=Runtime()
context=SimpleNamespace(checkpoint=None,device='cpu',dtype='float32',
 model_info=SimpleNamespace(model_id='synthetic'),variant={'variant_id':'fixture'})
adapter=UniK3DAdapter(fixture_runtime_factory=lambda context: runtime)
def fails(operation,exception):
 try: operation()
 except exception: return
 raise AssertionError('invalid lifecycle/input accepted')
fails(lambda:adapter.predict(None),RuntimeError)
for device,dtype in [('cuda:0','float32'),('cpu','float16')]:
 context.device=device;context.dtype=dtype;fails(lambda:adapter.load(context),ValueError)
context.device='cpu';context.dtype='float32'
assert adapter.load(context).runtime['synthetic'] is True
fails(lambda:adapter.load(context),RuntimeError)
for array in (image.astype('float32'),image[:,:,:2],image[:0]):
 fails(lambda:adapter.predict(PredictionRequest('v',array)),ValueError)
fails(lambda:adapter.predict(PredictionRequest('v',image,{'resolution_level':0})),ValueError)
fails(lambda:adapter.predict(PredictionRequest('v',image,requested_outputs=('depth','intrinsics'))),ValueError)
assert runtime.calls==0
assert adapter.predict(PredictionRequest('v',image)).views[0].view_id=='v'
assert runtime.calls==1
adapter.unload();adapter.unload();assert runtime.closed==1
fails(lambda:adapter.predict(None),RuntimeError)
adapter.load(context);adapter.unload();assert runtime.closed==2
class BadRuntime:
 def __init__(self): self.closed=False
 def close(self): self.closed=True
bad=BadRuntime();adapter=UniK3DAdapter(fixture_runtime_factory=lambda context:bad)
fails(lambda:adapter.load(context),TypeError);assert bad.closed
adapter.unload()
'''
        self.run_script(numeric, script)


class UniK3DSyntheticWorkerTests(unittest.TestCase):
    stop_workers = local_contract.LocalContractTests.stop_workers

    def setUp(self):
        local_contract.LocalContractTests.setUp(self)
        # Isolated registry: never advertise this as an available production model.
        temporary_registry = tempfile.TemporaryDirectory(prefix='unik3d-fixture-', dir=PROJECT / '.local')
        self.addCleanup(temporary_registry.cleanup)
        self.registry_root = Path(temporary_registry.name)
        plugin = self.registry_root / 'unik3d-synthetic'
        plugin.mkdir(parents=True)
        self.manifest = read_json(PROJECT / 'tests/fixtures/models/geometry/manifest.json')
        self.manifest.update(model_id='unik3d-synthetic', display_name='UniK3D synthetic contract only',
            adapter_entrypoint='tests.fixtures.unik3d:SyntheticAdapter',
            capabilities={'depth': {'status': 'supported'}, 'points': {'status': 'supported'}},
            parameter_schema={'type': 'object', 'properties': {}, 'additionalProperties': False})
        self.manifest_path = plugin / 'manifest.json'
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.runner.registry = ModelRegistry(self.registry_root)

    def run_synthetic(self, outputs):
        handle = self.runner.submit('unik3d-synthetic', PROJECT / 'tests/assets/sample.png',
                                    device='cpu', requested_outputs=outputs)
        self.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
        return handle, self.runner.collect(handle), self.store.root / handle.run_id

    def test_depth_only_and_points_roundtrip_preserve_negative_z_and_raw(self):
        for outputs, profile in ((('depth',), '01A-depth-only'), (('depth','points'), '02A-geometry-v1')):
            with self.subTest(outputs=outputs):
                handle, result, run = self.run_synthetic(outputs)
                self.assertEqual(result.status, 'COMPLETED', result.error)
                self.assertEqual(result.execution['serialization_profile'], profile)
                view = result.outputs[0]
                self.assertTrue(view['metadata']['synthetic_contract_only'])
                self.assertEqual(view['metadata']['depth_kind'], 'ray_distance')
                self.assertEqual(view['metadata']['invalid_pixels'], 1)
                self.assertNotIn('model_mask', view)
                self.assertEqual('points' in view, 'points' in outputs)
                if 'points' in view:
                    ref = view['points']; path = run / ref['path']
                    offset = inspect_array(path, ref['shape'], ref['dtype'])
                    with path.open('rb') as stream:
                        stream.seek(offset + 256 * 12)
                        self.assertEqual(struct.unpack('<3f', stream.read(12)), (3.,0.,-4.))
                def snapshot():
                    return {str(p.relative_to(run)): (sha256_file(p), p.stat().st_mtime_ns)
                            for p in run.rglob('*') if p.is_file()}
                before = snapshot()
                manager = Mock(); fresh = LocalBackend(self.store.root, manager)
                for _ in range(2): self.assertEqual(fresh.collect(handle).to_dict(), result.to_dict())
                manager.start.assert_not_called()
                self.assertEqual(before, snapshot())
                stdout = (run / 'logs/attempt-0001/stdout.log').read_text()
                self.assertEqual(stdout.count('unik3d synthetic predict'), 1)
                self.assertEqual(stdout.count('unik3d synthetic closed'), 1)

    def test_missing_distance_or_all_invalid_fails_and_cleanup_runs(self):
        for adapter, message in (('BrokenSyntheticAdapter', 'Missing native distance'),
                                 ('AllInvalidSyntheticAdapter', 'All depth pixels are invalid')):
            with self.subTest(adapter=adapter):
                self.manifest['adapter_entrypoint'] = 'tests.fixtures.unik3d:' + adapter
                self.manifest_path.write_text(json.dumps(self.manifest))
                _, result, run = self.run_synthetic(('depth','points'))
                self.assertEqual(result.status, 'FAILED')
                self.assertEqual(result.outputs, [])
                self.assertIn(message, result.error['message'])
                self.assertIn('unik3d synthetic closed', (run / 'logs/attempt-0001/stdout.log').read_text())

    def test_production_registry_exposes_metadata_and_fixture_rejects_unsupported(self):
        info = ModelRegistry(PROJECT / 'models').get_model('unik3d')
        self.assertEqual(info.environment()['environment_id'], 'mde-unik3d')
        self.assertEqual(info.effective_variant()['supported_devices'], ['cpu'])
        self.assertIsNone(info.data['weights_license'])
        with self.assertRaises(ValueError):
            self.runner.submit('unik3d-synthetic', PROJECT / 'tests/assets/sample.png', device='cpu',
                               requested_outputs=('depth','intrinsics'))
