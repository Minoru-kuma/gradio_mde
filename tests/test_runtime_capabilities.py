"""Runtime declarations gate prediction; synthetic integration preserves old adapters."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from mde.backends import LocalBackend
from mde.registry import ModelRegistry
from mde.runtime_capabilities import check_runtime_capabilities
from mde.storage import read_json, sha256_file
from tests import test_local_contract as local_contract

PROJECT = local_contract.PROJECT


class RuntimeCapabilityTests(unittest.TestCase):
    def test_supported_conditional_and_nonrequested_unsupported(self):
        source = {'depth': {'status': 'supported'},
                  'points': {'status': 'conditional', 'condition': 'not executed', 'extension': [1, None]},
                  'normals': {'status': 'unsupported'}}
        before = deepcopy(source)
        check, warnings = check_runtime_capabilities(source, ('depth','points'))
        self.assertEqual(check['declaration'], 'declared')
        self.assertEqual(check['requested_outputs'], ['depth','points'])
        self.assertEqual(check['capabilities'], source)
        self.assertEqual(len(warnings), 1)
        check['capabilities']['points']['extension'].append(2)
        self.assertEqual(source, before)
        _, warnings = check_runtime_capabilities(source, ('depth',))
        self.assertEqual(warnings, [])

    def test_empty_map_is_legacy_but_partial_missing_requested_is_rejected(self):
        check, warnings = check_runtime_capabilities({}, ('depth','points'))
        self.assertEqual(check['declaration'], 'legacy_undeclared')
        self.assertEqual(check['capabilities'], {})
        self.assertEqual(len(warnings), 1)
        for value, message in (({'depth': {'status': 'supported'}}, 'Missing requested'),
                ({'depth': {'status': 'supported'}, 'points': {'status': 'unsupported'}}, 'Unsupported requested')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                check_runtime_capabilities(value, ('depth','points'))

    def test_malformed_declarations_cannot_reach_prediction_or_wire(self):
        for value in (None, [], True, {'depth': True}, {'depth': {'status': True}},
                      {'depth': {'status': 'unknown'}}, {1: {'status': 'supported'}},
                      {'': {'status': 'supported'}}, {'depth': {'status': 'supported', 'condition': []}},
                      {'depth': {'status': 'supported', 'extension': float('nan')}},
                      {'depth': {'status': 'supported', 'extension': object()}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_runtime_capabilities(value, ('depth',))

    def test_helper_has_no_model_or_numeric_imports(self):
        script = '''
import sys
from mde.runtime_capabilities import check_runtime_capabilities
check_runtime_capabilities({'depth':{'status':'supported'}},('depth',))
assert not set(sys.modules).intersection({'torch','numpy','PIL','models.moge.adapter','models.unik3d.adapter'})
'''
        call = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(call.returncode, 0, call.stderr)


class RuntimeCapabilityWorkerTests(unittest.TestCase):
    stop_workers = local_contract.LocalContractTests.stop_workers

    def setUp(self):
        local_contract.LocalContractTests.setUp(self)
        registry = tempfile.TemporaryDirectory(prefix='runtime-capabilities-', dir=PROJECT / '.local')
        self.addCleanup(registry.cleanup)
        self.plugin = Path(registry.name) / 'runtime-fixture'
        self.plugin.mkdir()
        self.manifest = read_json(PROJECT / 'tests/fixtures/models/geometry/manifest.json')
        self.manifest.update(model_id='runtime-fixture',
            adapter_entrypoint='tests.fixtures.runtime_capabilities:RuntimeCapabilityAdapter')
        self.runner.registry = ModelRegistry(self.plugin.parent)

    def run_fixture(self, mode, action='success', outputs=('depth','points')):
        self.manifest['variants'][0]['runtime_fixture'] = mode
        (self.plugin / 'manifest.json').write_text(json.dumps(self.manifest))
        handle = self.runner.submit('runtime-fixture', PROJECT / 'tests/assets/sample.png', device='cpu',
                                    requested_outputs=outputs, parameters={'action': action})
        self.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
        return handle, self.runner.collect(handle), self.store.root / handle.run_id

    def test_rejected_runtime_never_predicts_and_backend_can_be_reused(self):
        for mode, message in (('unsupported','Unsupported requested runtime'), ('missing','Missing requested runtime'),
                              ('invalid','Invalid runtime capability'), ('nonjson','finite JSON metadata')):
            with self.subTest(mode=mode):
                _, result, run = self.run_fixture(mode)
                self.assertEqual(result.status, 'FAILED')
                self.assertEqual(result.error['stage'], 'preflight')
                self.assertIn(message, result.error['message'])
                self.assertEqual(result.outputs, [])
                self.assertNotIn('runtime_capability_check', result.execution)
                stdout = (run / 'logs/attempt-0001/stdout.log').read_text()
                self.assertNotIn('geometry predict', stdout)
                self.assertIn('fake unloaded', stdout)
        _, result, _ = self.run_fixture('conditional')
        self.assertEqual(result.status, 'COMPLETED', result.error)

    def test_conditional_presence_legacy_roundtrip_and_unrequested_unsupported(self):
        for mode, outputs in (('conditional',('depth','points')), ('legacy',('depth','points')),
                              ('unsupported',('depth',))):
            with self.subTest(mode=mode):
                handle, result, run = self.run_fixture(mode, outputs=outputs)
                self.assertEqual(result.status, 'COMPLETED', result.error)
                check = result.execution['runtime_capability_check']
                self.assertEqual(check['declaration'], 'legacy_undeclared' if mode=='legacy' else 'declared')
                self.assertEqual(check['requested_outputs'], list(outputs))
                if mode in ('conditional','legacy'):
                    self.assertTrue(any('after predict' in warning for warning in result.warnings))
                before = {str(p): (sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
                manager = Mock()
                fresh = LocalBackend(self.store.root,manager)
                for _ in range(2): self.assertEqual(fresh.collect(handle).to_dict(), result.to_dict())
                manager.start.assert_not_called()
                self.assertEqual(before,{str(p): (sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()})
        _, result, run = self.run_fixture('conditional', action='missing_points')
        self.assertEqual(result.status,'FAILED')
        self.assertEqual(result.error['stage'],'serialize')
        self.assertIn('Missing requested points',result.error['message'])
        stdout = (run / 'logs/attempt-0001/stdout.log').read_text()
        self.assertIn('geometry predict',stdout)
        self.assertIn('fake unloaded',stdout)
