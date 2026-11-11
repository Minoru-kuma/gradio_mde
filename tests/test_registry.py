"""03.1 discovery / variant boundaries and shared Backend subprocess acceptance."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from mde.backends import LocalBackend
from mde.environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
from mde.registry import ModelRegistry, validate_manifest, validate_parameters
from mde.runner import ExperimentRunner
from mde.storage import RunStore, read_json, sha256_file

PROJECT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT / 'tests/fixtures/models'


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = read_json(FIXTURES / 'alternate/manifest.json')

    def write(self, directory, data):
        path = self.root / directory / 'manifest.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))

    def test_metadata_discovery_in_application_without_numeric_imports(self):
        script = '''
import sys
from pathlib import Path
from mde.registry import ModelRegistry
registry = ModelRegistry(Path(sys.argv[1]))
assert [m.model_id for m in registry.list_models()] == ['alternate', 'fake', 'geometry']
assert registry.get_model('alternate').data['test_extension'] == {'preserve': True}
assert not set(sys.modules).intersection({'torch','numpy','PIL','tests.fixtures.fake','models.moge.adapter','tests.fixtures.models.alternate.adapter'})
'''
        call = subprocess.run([sys.executable, '-c', script, str(FIXTURES)],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(call.returncode, 0, call.stderr)

    def test_invalid_plugin_diagnostics_and_valid_models_are_separate(self):
        self.write('alternate', self.data)
        broken = deepcopy(self.data); broken['model_id'] = 'broken'; broken['schema_version'] = '2.0'
        self.write('broken', broken)
        (self.root / 'invalid').mkdir(); (self.root / 'invalid/manifest.json').write_text('{')
        registry = ModelRegistry(self.root)
        self.assertEqual([m.model_id for m in registry.list_models()], ['alternate'])
        self.assertEqual(set(registry.discover().diagnostics), {'broken', 'invalid'})
        with self.assertRaisesRegex(ValueError, 'Invalid manifest'):
            registry.get_model('broken')
        for key in ('../alternate', 'missing'):
            with self.assertRaises(ValueError): registry.get_model(key)

    def test_duplicate_id_is_fatal_even_when_one_directory_mismatches(self):
        self.write('alternate', self.data); self.write('collision', self.data)
        with self.assertRaisesRegex(ValueError, 'Duplicate plugin ID'):
            ModelRegistry(self.root).get_model('alternate')

    def test_malformed_json_duplicate_keys_and_nonfinite_metadata_are_diagnosed(self):
        self.write('alternate', self.data)
        path = self.root / 'alternate/manifest.json'
        for content in ('[]', '{"model_id":"alternate","model_id":"other"}',
                        '{"extension":NaN}', '{"extension":1e999}'):
            with self.subTest(content=content):
                path.write_text(content)
                self.assertIn('alternate', ModelRegistry(self.root).discover().diagnostics)

    def test_variant_resolution_replaces_whole_fields_and_preserves_source(self):
        original = deepcopy(self.data)
        info = validate_manifest(self.data, 'alternate')
        resolved = info.effective_variant('offset')
        self.assertEqual(set(resolved['parameter_schema']['properties']), {'offset'})
        self.assertNotIn('mask', resolved['capabilities'])
        self.assertEqual(resolved['supported_devices'], ['cpu'])
        self.assertEqual(info.environment('offset')['environment_id'], 'mde-fake-alternate')
        resolved['supported_devices'].append('invalid'); resolved['capabilities']['depth']['status'] = 'unsupported'
        self.assertEqual(info.data, original)
        with self.assertRaisesRegex(ValueError, 'Unknown variant'): info.effective_variant('unknown')

    def test_variant_overrides_devices_dtype_and_input_constraints(self):
        self.data['variants'][1].update(supported_devices=['cuda:0'], supported_dtypes=['float16'],
                                       input_constraints={'min_views': 2, 'max_views': 3})
        info = validate_manifest(self.data, 'alternate')
        selected = info.effective_variant('offset')
        self.assertEqual(selected['supported_devices'], ['cuda:0'])
        self.assertEqual(selected['supported_dtypes'], ['float16'])
        self.assertEqual(selected['input_constraints'], {'min_views': 2, 'max_views': 3})
        self.assertEqual(info.effective_variant('distance')['supported_devices'], ['cpu'])

    def test_ambiguous_environment_requires_explicit_selection(self):
        self.data['environment_refs'].append({'environment_id': 'other', 'definition_ref': 'missing/environment.yml'})
        info = validate_manifest(self.data, 'alternate')
        with self.assertRaisesRegex(ValueError, 'Multiple environments'): info.environment()
        self.assertEqual(info.environment(environment_id='other')['environment_id'], 'other')
        with self.assertRaisesRegex(ValueError, 'Unknown environment'): info.environment(environment_id='absent')

    def test_rejects_invalid_manifest_and_schema_definitions(self):
        patches = [
            {'default_variant': 'absent'}, {'variants': []},
            {'variants': [self.data['variants'][0], self.data['variants'][0]]},
            {'adapter_entrypoint': 'bad..module:Adapter'}, {'capabilities': {'depth': {'status': 'yes'}}},
            {'supported_devices': []}, {'supported_dtypes': ['float32', 'float32']},
            {'environment_refs': [{'environment_id': 'ok', 'definition_ref': '../environment.yml'}]},
            {'environment_refs': [{'environment_id': 'ok', 'definition_ref': 'x', 'worker_protocol_version': '2.0'}]},
            {'input_constraints': {'min_views': 2, 'max_views': 1}},
            {'parameter_schema': {'properties': {'p': {'type': 'array'}}}},
            {'parameter_schema': {'properties': {'p': {'type': []}}}},
            {'parameter_schema': {'properties': {'p': {'type': 'number', 'default': float('nan')}}}},
            {'parameter_schema': {'properties': {'p': {'type': 'integer', 'minimum': 4, 'maximum': 1}}}},
            {'parameter_schema': {'properties': {'p': {'type': 'string', 'enum': [1]}}}},
            {'parameter_schema': {'properties': {}, 'required': ['absent']}},
            {'parameter_schema': {'properties': {}, 'additionalProperties': True}},
            {'parameter_schema': {'allOf': []}},
            {'parameter_schema': {'properties': {'p': {'type': 'number', 'multipleOf': 2}}}},
            {'variants': [{'variant_id': 'distance', 'supported_devices': []}]},
        ]
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_manifest({**self.data, **patch}, 'alternate')

    def test_scalar_parameters_reject_nonfinite_bool_unknown_and_missing(self):
        schema = {'required': ['n'], 'properties': {'n': {'type': 'number', 'minimum': 1, 'maximum': 5},
                                                 's': {'type': 'string', 'enum': ['a'], 'default': 'a'}}}
        self.assertEqual(validate_parameters(schema, {'n': 2.5}), {'n': 2.5, 's': 'a'})
        for supplied in ({}, [], {'n': True}, {'n': float('nan')}, {'n': float('inf')},
                         {'n': 0}, {'n': 6}, {'n': 2, 'other': 1}, {'n': 2, 's': 'b'}):
            with self.subTest(supplied=supplied), self.assertRaises(ValueError):
                validate_parameters(schema, supplied)


class PluginExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = RunStore(PROJECT, self.temporary.name)
        prefix = os.environ.get('MDE_TEST_CONDA_PREFIX')
        profiles = {key: EnvironmentProfile(key, name=None if prefix else os.environ.get('MDE_TEST_CONDA_ENV', 'mde-moge'), prefix=prefix)
                    for key in ('mde-moge', 'mde-fake-alternate')}
        self.manager = WorkerManager(PROJECT, EnvironmentResolver(profiles), CondaLauncher())
        self.backend = LocalBackend(self.store.root, self.manager)
        self.runner = ExperimentRunner(ModelRegistry(FIXTURES), self.backend, self.store, PROJECT)
        self.addCleanup(self.stop)

    def stop(self):
        for job in self.backend._jobs.values():
            if job.worker and job.worker.group_alive(): job.worker.stop(0.1)

    def execute(self, model, **kwargs):
        handle = self.runner.submit(model, PROJECT / 'tests/assets/sample.png', device='cpu', **kwargs)
        deadline = time.monotonic() + 45
        while not self.runner.status(handle).status.terminal:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.05)
        result = self.runner.collect(handle)
        self.assertEqual(result.status, 'COMPLETED', result.error)
        return handle, result, self.store.root / handle.run_id

    def test_directory_only_plugin_shared_backend_sequential_execution_and_readonly_collect(self):
        for model, kwargs, environment_id in (
                ('fake', {}, 'mde-moge'), ('alternate', {'requested_outputs': ('depth', 'mask')}, 'mde-moge'),
                ('alternate', {'variant_id': 'offset'}, 'mde-fake-alternate'), ('fake', {}, 'mde-moge')):
            with self.subTest(model=model, kwargs=kwargs):
                handle, result, run = self.execute(model, **kwargs)
                job = read_json(run / 'job.json')
                self.assertEqual(job['environment_ref']['environment_id'], environment_id)
                self.assertEqual(result.execution['requested_environment'], environment_id)
                if model == 'alternate':
                    self.assertEqual(result.outputs[0]['metadata']['depth_kind'], 'ray_distance')
                    self.assertIn('only selected adapter imported', (run / 'logs/attempt-0001/stdout.log').read_text())
                    parameter = 'offset' if 'variant_id' in kwargs else 'distance'
                    self.assertEqual(set(job['inference']['parameters']), {parameter})
                snapshot = lambda: {p.relative_to(run).as_posix(): (sha256_file(p), p.stat().st_mtime_ns)
                                      for p in run.rglob('*') if p.is_file()}
                before = snapshot()
                self.assertEqual(LocalBackend(self.store.root).collect(handle).to_dict(), result.to_dict())
                self.assertEqual(self.runner.collect(handle).to_dict(), result.to_dict())
                self.assertEqual(snapshot(), before)

    def test_variant_validation_and_missing_target_environment_before_worker_launch(self):
        for options in ({'variant_id': 'offset', 'parameters': {'distance': 2}},
                        {'variant_id': 'offset', 'requested_outputs': ('depth', 'mask')},
                        {'parameters': []}, {'device': 'cuda:0'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.runner.submit('alternate', PROJECT / 'tests/assets/sample.png', **{'device': 'cpu', **options})
        self.assertEqual(len(self.backend._jobs), 0)
        del self.manager.resolver.profiles['mde-fake-alternate']
        self.assertIn('alternate', [m.model_id for m in self.runner.registry.list_models()])
        with self.assertRaisesRegex(ValueError, 'Unknown environment'):
            self.runner.submit('alternate', PROJECT / 'tests/assets/sample.png', variant_id='offset', device='cpu')
        self.assertEqual(len(self.backend._jobs), 0)

    def test_uncreated_environment_fails_execution_without_hiding_plugin(self):
        self.manager.resolver.profiles['mde-fake-alternate'] = EnvironmentProfile(
            'mde-fake-alternate', prefix=str(Path(self.temporary.name) / 'uncreated-model-env'))
        self.assertIn('alternate', [m.model_id for m in self.runner.registry.list_models()])
        handle = self.runner.submit('alternate', PROJECT / 'tests/assets/sample.png',
                                    variant_id='offset', device='cpu')
        job = self.backend._jobs[handle.backend_job_id]
        job.worker.process.wait(timeout=30)
        result = self.runner.collect(handle)
        self.assertEqual(result.status, 'FAILED')
        self.assertEqual(result.outputs, [])
        self.assertNotIn('alternate predict', (job.run / 'logs/attempt-0001/stdout.log').read_text())
        self.assertFalse((Path(self.temporary.name) / 'uncreated-model-env').exists())
