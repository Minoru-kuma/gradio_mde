"""DA3 local checkpoint and conversion contracts; no model packages in control."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mde.registry import ModelRegistry, validate_parameters

PROJECT = Path(__file__).resolve().parents[1]


class DA3PluginTests(unittest.TestCase):
    def test_discovery_without_model_environment_and_variant_parameter_isolation(self):
        info = ModelRegistry(PROJECT / 'models').get_model('da3')
        variant = info.effective_variant()
        self.assertEqual(variant['supported_devices'], ['cpu'])
        self.assertEqual(info.environment()['environment_id'], 'mde-da3')
        self.assertEqual(validate_parameters(variant['parameter_schema'], {}), {'process_res': 252})
        for parameters in ({'num_tokens': 1200}, {'process_res': 253}):
            with self.assertRaises(ValueError): validate_parameters(variant['parameter_schema'], parameters)

    def test_checkpoint_requires_both_pinned_files_and_detects_same_size_tampering(self):
        from models.da3.checkpoint import verify_checkpoint
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            weights, config = b'stub weights', b'{"model_name":"fixture"}'
            (directory / 'model.safetensors').write_bytes(weights)
            (directory / 'config.json').write_bytes(config)
            reference = {'filename': 'model.safetensors', 'sha256': hashlib.sha256(weights).hexdigest(),
                         'size_bytes': len(weights), 'config': {'filename': 'config.json',
                         'sha256': hashlib.sha256(config).hexdigest(), 'size_bytes': len(config)}}
            self.assertEqual(verify_checkpoint(directory, reference)[1], {'model_name': 'fixture'})
            with self.assertRaisesRegex(ValueError, 'requires a prepared'): verify_checkpoint(None, reference)
            (directory / 'model.safetensors').write_bytes(b'X' * len(weights))
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'): verify_checkpoint(directory, reference)
            (directory / 'model.safetensors').write_bytes(weights)
            (directory / 'config.json').unlink()
            with self.assertRaisesRegex(ValueError, 'missing or wrong size'): verify_checkpoint(directory, reference)

    def test_adapter_rejects_unloaded_predict_and_non_cpu_without_framework_import(self):
        script = '''
import sys
from types import SimpleNamespace
from models.da3.adapter import DA3Adapter
adapter=DA3Adapter()
try: adapter.predict(None)
except RuntimeError: pass
else: raise AssertionError('unloaded predict accepted')
for device,dtype in [('cuda:0','float32'),('cpu','float16')]:
 try: adapter.load(SimpleNamespace(device=device,dtype=dtype))
 except ValueError: pass
 else: raise AssertionError('unsupported execution accepted')
adapter.unload();adapter.unload()
assert 'torch' not in sys.modules
assert 'depth_anything_3' not in sys.modules
'''
        call = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(call.returncode, 0, call.stderr)

    def test_native_depth_conversion_preserves_values_and_rejects_bad_layout_dtype(self):
        # Numeric checks run in a fresh process, preserving the suite's control import boundary.
        numeric = PROJECT / '.local/envs/mde-ui/bin/python'
        if not numeric.exists(): self.skipTest('Independent numeric UI environment required')
        script = '''
import numpy as np
from types import SimpleNamespace
from models.da3.adapter import map_prediction
array=np.array([[[1.,2.,float('nan')],[3.,4.,5.]]],dtype='float32')
pred=SimpleNamespace(depth=array)
output=map_prediction(pred,'view-0001',(4,6),252,['depth'])
assert np.array_equal(output.depth,array[0],equal_nan=True)
assert output.metadata['depth_kind']=='z_depth'
assert output.metadata['scale_type']=='relative'
assert output.metadata['depth_unit']=='arbitrary'
assert output.points is None and output.intrinsics is None and output.camera_pose is None
assert output.metadata['image_to_output']['type']=='affine'
np.testing.assert_array_equal(output.metadata['image_to_output']['matrix'],[[.5,0,-.25],[0,.5,-.25],[0,0,1]])
for value in [np.ones((2,3),dtype='float32'),np.ones((2,2,3),dtype='float32'),
              np.ones((1,2,3),dtype='float64'),np.ones((1,0,3),dtype='float32')]:
 try: map_prediction(SimpleNamespace(depth=value),'view-0001',(2,3),252,['depth'])
 except ValueError: pass
 else: raise AssertionError('invalid native depth accepted')
'''
        call = subprocess.run([str(numeric), '-c', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(call.returncode, 0, call.stderr)

    def test_shared_checkpoint_aliases_load_strictly_and_real_missing_weights_fail(self):
        worker = PROJECT / '.local/envs/mde-da3/bin/python'
        if not worker.exists(): self.skipTest('Prepared independent DA3 environment required')
        script = '''
import tempfile
from pathlib import Path
import torch
from safetensors.torch import save_model,save_file
from models.da3.adapter import load_native_checkpoint

def create():
 model=torch.nn.Module()
 norm=torch.nn.LayerNorm(2)
 model.head=torch.nn.ModuleList([norm,norm,norm,norm])
 return model

original=create()
with torch.no_grad(): original.head[0].weight.fill_(2.5)
wrapper=torch.nn.Module();wrapper.model=original
with tempfile.TemporaryDirectory() as directory:
 path=Path(directory)/'weights.safetensors'
 save_model(wrapper,str(path))
 restored=create();load_native_checkpoint(restored,path)
 assert all(layer.weight is restored.head[0].weight for layer in restored.head)
 assert torch.equal(restored.head[3].weight,original.head[3].weight)
 save_file({'model.head.0.weight':torch.ones(2)},str(path))
 try: load_native_checkpoint(create(),path)
 except RuntimeError as error: assert 'Missing key' in str(error)
 else: raise AssertionError('genuinely missing weights accepted')
'''
        call = subprocess.run([str(worker), '-c', script], capture_output=True, text=True, timeout=15)
        self.assertEqual(call.returncode, 0, call.stderr)
