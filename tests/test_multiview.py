"""Two-view fake acceptance, scene integrity/export and unchanged single-view protocol."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
import zipfile
import zlib

from mde.backends import LocalBackend
from mde.contracts import ArtifactIntegrityError, JobSpec, UnsupportedOperation
from mde.registry import ModelRegistry
from mde.run_management import RunManagementService
from mde.storage import artifact_ref, inspect_depth, read_json, sha256_file, validate_outputs, write_json
from tests import test_local_contract as local_contract

PROJECT = local_contract.PROJECT


def write_png(path, width, height, value):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress((b'\0' + bytes([value, value, value]) * width) * height)) + chunk(b'IEND', b''))


class MultiViewTests(unittest.TestCase):
    stop_workers = local_contract.LocalContractTests.stop_workers

    def setUp(self):
        local_contract.LocalContractTests.setUp(self)
        registry = tempfile.TemporaryDirectory(prefix='multiview-', dir=PROJECT / '.local')
        self.addCleanup(registry.cleanup)
        self.plugin = Path(registry.name) / 'multiview-fixture'; self.plugin.mkdir()
        self.manifest = read_json(PROJECT / 'tests/fixtures/models/geometry/manifest.json')
        self.manifest.update(model_id='multiview-fixture', adapter_entrypoint='tests.fixtures.multiview:MultiViewAdapter',
            capabilities={'depth': {'status': 'supported'}, 'points': {'status': 'supported'}, 'multi_view': {'status': 'supported'}},
            input_constraints={'min_views': 1, 'max_views': 2, 'format': 'PNG', 'worker_mode': 'RGB', 'request_kind': 'multi_view_v1'})
        self.manifest['environment_refs'][0]['worker_protocol_version'] = '1.1'
        self.write_manifest()
        self.runner.registry = ModelRegistry(self.plugin.parent)
        self.images = [Path(self.temporary.name) / 'one.png', Path(self.temporary.name) / 'two.png']
        write_png(self.images[0], 3, 2, 10); write_png(self.images[1], 5, 4, 20)

    def write_manifest(self):
        (self.plugin / 'manifest.json').write_text(json.dumps(self.manifest))

    def run_batch(self, action='success', outputs=('depth','points'), images=None):
        handle = self.runner.submit_views('multiview-fixture', self.images if images is None else images,
            device='cpu', parameters={'action': action}, requested_outputs=outputs)
        self.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
        return handle, self.runner.collect(handle), self.store.root / handle.run_id

    def test_two_views_reverse_response_maps_to_input_order_and_native_shapes(self):
        for action in ('success','reverse'):
            with self.subTest(action=action):
                _, result, run = self.run_batch(action)
                self.assertEqual(result.status,'COMPLETED',result.error)
                self.assertEqual(result.schema_version,'1.1')
                self.assertEqual([o['view_id'] for o in result.outputs],['view-0001','view-0002'])
                for output, shape, value in zip(result.outputs, ([2,3],[4,5]), (11.,21.)):
                    self.assertEqual(inspect_depth(run/output['depth']['path'])['shape'],shape)
                    with (run/output['depth']['path']).open('rb') as stream:
                        stream.seek(-4,2);self.assertEqual(struct.unpack('<f',stream.read(4))[0],value)
                    self.assertEqual(output['extras']['future/model']['values'],[value,None])
                    self.assertEqual(output['extras']['fake/request_kind'],'multi_view_v1')
                metadata = read_json(run/'output/attempt-0001/metadata.json')
                self.assertEqual(len(metadata['views']),2)
                scene = read_json(run/result.scene['path'])
                self.assertEqual(scene['view_ids'],['view-0001','view-0002'])
                self.assertEqual(scene['metadata']['reference_view_id'],'view-0001')
                self.assertEqual(scene['metadata']['future/scene'],{'opaque':[None,{'keep':True}]})
                stdout=(run/'logs/attempt-0001/stdout.log').read_text()
                self.assertEqual(stdout.count('fake multiview predict'),1)
                self.assertIn('fake multiview unloaded',stdout)

    def test_depth_only_scene_collect_and_zip_preserve_all_views(self):
        handle,result,run=self.run_batch(outputs=('depth',))
        self.assertEqual(result.status,'COMPLETED',result.error)
        self.assertEqual(result.execution['serialization_profile'],'01A-depth-only')
        self.assertTrue(all('points' not in output for output in result.outputs))
        def snapshot():return {str(p):(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
        before=snapshot();manager=Mock();fresh=LocalBackend(self.store.root,manager)
        for _ in range(2):self.assertEqual(fresh.collect(handle).to_dict(),result.to_dict())
        manager.start.assert_not_called()
        call=subprocess.run([sys.executable,'-m','mde.cli','collect','--run-id',handle.run_id,'--run-root',str(self.store.root)],
            env={**os.environ,'MDE_CONDA_EXE':'/missing/conda'},capture_output=True,text=True,timeout=30)
        self.assertEqual(call.returncode,0,call.stderr)
        self.assertEqual(json.loads(call.stdout)['scene'],result.scene)
        service=RunManagementService(self.store,fresh.collect)
        with zipfile.ZipFile(io.BytesIO(service.export(handle.run_id))) as archive:
            names=set(archive.namelist())
            for ref in [*result.artifacts,*read_json(run/'job.json')['inputs']]:
                self.assertIn(ref['path'],names)
                self.assertEqual(archive.read(ref['path']),(run/ref['path']).read_bytes())
            self.assertEqual(json.loads(archive.read(result.scene['path']))['view_ids'],['view-0001','view-0002'])
        self.assertEqual(before,snapshot())

    def test_invalid_batch_never_publishes_partial_success_and_unloads(self):
        for action in ('missing','duplicate','unknown','missing_depth','bad_points','bad_extras','bad_scene','bad_scene_scale','bad_scene_json'):
            with self.subTest(action=action):
                _,result,run=self.run_batch(action)
                self.assertEqual(result.status,'FAILED')
                self.assertEqual(result.outputs,[]);self.assertIsNone(result.scene)
                worker=read_json(run/'output/attempt-0001/result.json')
                self.assertEqual(worker['outputs'],[])
                self.assertIn('fake multiview unloaded',(run/'logs/attempt-0001/stdout.log').read_text())

    def test_explicit_runtime_multiview_is_required_even_for_legacy_empty_map(self):
        for mode in ('unsupported','legacy'):
            with self.subTest(mode=mode):
                self.manifest['variants'][0]['runtime_mode']=mode;self.write_manifest()
                _,result,run=self.run_batch()
                self.assertEqual(result.status,'FAILED')
                self.assertEqual(result.error['stage'],'preflight')
                stdout=(run/'logs/attempt-0001/stdout.log').read_text()
                self.assertNotIn('fake multiview predict',stdout)
                self.assertIn('fake multiview unloaded',stdout)

    def test_single_view_api_and_wire_remain_legacy(self):
        _,result,run=self.run_batch(images=self.images[:1])
        self.assertEqual(result.status,'COMPLETED',result.error)
        self.assertEqual(result.schema_version,'1.0')
        self.assertNotIn('scene',result.to_dict());self.assertIsNone(result.scene)
        self.assertEqual(result.outputs[0]['extras']['fake/request_kind'],'legacy_single')
        job=read_json(run/'job.json')
        self.assertEqual(job['schema_version'],'1.0');self.assertNotIn('request_kind',job['inference'])
        self.assertEqual(job['inputs'][0]['path'],'input/views/view-0001/image.png')
        _, scene_result, scene_run = self.run_batch('single_scene', images=self.images[:1])
        self.assertEqual(scene_result.status,'COMPLETED',scene_result.error)
        self.assertEqual(read_json(scene_run/'job.json')['schema_version'],'1.0')
        self.assertEqual(scene_result.schema_version,'1.1')
        self.assertIsNotNone(scene_result.scene)
        self.assertEqual(read_json(scene_run/scene_result.scene['path'])['view_ids'],['view-0001'])

    def test_opt_in_limits_protocol_and_input_validation_precede_run_creation(self):
        original=deepcopy(self.manifest)
        for mutation in ('capability','kind','protocol','future_protocol','limit'):
            self.manifest=deepcopy(original)
            if mutation=='capability':self.manifest['capabilities']['multi_view']['status']='unsupported'
            if mutation=='kind':self.manifest['input_constraints'].pop('request_kind')
            if mutation=='protocol':self.manifest['environment_refs'][0]['worker_protocol_version']='1.0'
            if mutation=='future_protocol':self.manifest['environment_refs'][0]['worker_protocol_version']='1.2'
            if mutation=='limit':self.manifest['input_constraints']['max_views']=1
            self.write_manifest()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.runner.submit_views('multiview-fixture',self.images,device='cpu')
        self.manifest=original;self.write_manifest()
        for images in ([],str(self.images[0]),[self.images[0],Path('/missing/second.png')]):
            with self.subTest(images=images),self.assertRaises((ValueError,OSError)):
                self.runner.submit_views('multiview-fixture',images,device='cpu')
        self.assertFalse([path for path in self.store.root.iterdir() if path.is_dir()])

    def test_order_enters_digest_and_identical_images_remain_distinct_views(self):
        _, first, first_run = self.run_batch(outputs=('depth',))
        _, reverse, reverse_run = self.run_batch(outputs=('depth',), images=list(reversed(self.images)))
        self.assertEqual(first.status,'COMPLETED',first.error)
        self.assertEqual(reverse.status,'COMPLETED',reverse.error)
        self.assertNotEqual(read_json(first_run/'job.json')['request_digest'],read_json(reverse_run/'job.json')['request_digest'])
        self.assertEqual(reverse.outputs[0]['depth']['shape'],[4,5])
        self.assertEqual(reverse.outputs[0]['extras']['future/model']['values'],[21.,None])
        _, repeated, run = self.run_batch(outputs=('depth',), images=[self.images[0],self.images[0]])
        self.assertEqual(repeated.status,'COMPLETED',repeated.error)
        self.assertEqual([view['view_id'] for view in repeated.outputs],['view-0001','view-0002'])
        self.assertEqual([item['sha256'] for item in read_json(run/'job.json')['inputs']],[sha256_file(self.images[0])]*2)

    def test_saved_preview_identifies_first_view_without_mutating_raw_or_inference(self):
        handle,result,run = self.run_batch('reverse')
        self.assertEqual(result.status,'COMPLETED',result.error)
        before={ref['path']:(sha256_file(run/ref['path']),(run/ref['path']).stat().st_mtime_ns) for ref in result.artifacts}
        script='''
import sys
from mde.storage import RunStore
from mde.backends import LocalBackend
from mde.results import ResultsService
store=RunStore(sys.argv[1],sys.argv[2])
service=ResultsService(store,LocalBackend(store.root).collect)
payload=service.view(sys.argv[3],'Point Cloud')
assert payload['stats']['view_id']=='view-0001'
assert payload['stats']['view_count']==2
assert payload['stats']['preview']=='first input view'
'''
        call=subprocess.run([str(PROJECT/'.local/envs/mde-ui/bin/python'),'-c',script,str(PROJECT),str(self.store.root),handle.run_id],
                            capture_output=True,text=True,timeout=30)
        self.assertEqual(call.returncode,0,call.stderr)
        self.assertEqual(before,{ref['path']:(sha256_file(run/ref['path']),(run/ref['path']).stat().st_mtime_ns) for ref in result.artifacts})
        self.assertEqual((run/'logs/attempt-0001/stdout.log').read_text().count('fake multiview predict'),1)

    def test_scene_and_second_view_reference_tampering_is_rejected(self):
        _,result,run=self.run_batch()
        self.assertEqual(result.status,'COMPLETED',result.error)
        for mutation in ('missing_scene','scene_path','second_depth_path','second_points_path','duplicate_view','missing_view'):
            report=deepcopy(result.to_dict())
            if mutation=='missing_scene':report.pop('scene')
            if mutation=='scene_path':report['scene']['path']='../outside.json'
            if mutation=='second_depth_path':report['outputs'][1]['depth']['path']=report['outputs'][0]['depth']['path']
            if mutation=='second_points_path':report['outputs'][1]['points']['path']=report['outputs'][0]['points']['path']
            if mutation=='duplicate_view':report['outputs'][1]['view_id']='view-0001'
            if mutation=='missing_view':report['outputs'].pop()
            with self.subTest(mutation=mutation),self.assertRaises((ArtifactIntegrityError,ValueError)):
                validate_outputs(run,report)
        path=run/result.scene['path'];original=path.read_bytes();scene=read_json(path)
        scene['metadata']['reference_view_id']='view-9999';write_json(path,scene)
        report=deepcopy(result.to_dict());changed=artifact_ref(run,path,media_type='application/json')
        report['scene']=changed
        report['artifacts']=[changed if ref['path']==changed['path'] else ref for ref in report['artifacts']]
        with self.assertRaisesRegex(ArtifactIntegrityError,'reference_view_id'):validate_outputs(run,report)
        path.write_bytes(original)
        report=deepcopy(result.to_dict())
        report['outputs'][1]['metadata']['original_size']=report['outputs'][0]['metadata']['original_size']
        with self.assertRaisesRegex(ArtifactIntegrityError,'Original input dimensions'):validate_outputs(run,report)

    def test_job_schema_input_ids_and_second_input_checksum_are_validated(self):
        _,result,run=self.run_batch()
        self.assertEqual(result.status,'COMPLETED',result.error)
        job=read_json(run/'job.json')
        for mutation in ('version','kind','future_protocol','duplicate','order','path'):
            candidate=deepcopy(job)
            if mutation=='version':candidate['schema_version']='1.0'
            if mutation=='kind':candidate['inference'].pop('request_kind')
            if mutation=='future_protocol':candidate['environment_ref']['worker_protocol_version']='1.2'
            if mutation=='duplicate':candidate['inputs'][1]['view_id']='view-0001'
            if mutation=='order':candidate['inputs'].reverse()
            if mutation=='path':candidate['inputs'][1]['path']='../outside.png'
            with self.subTest(mutation=mutation),self.assertRaises((ValueError,UnsupportedOperation)):
                JobSpec.from_dict(candidate)
        path=run/job['inputs'][1]['path'];original=path.read_bytes();path.write_bytes(original[:-1]+b'X')
        from mde.storage import validate_job_files
        with self.assertRaises(ArtifactIntegrityError):validate_job_files(run,JobSpec.from_dict(job))
        path.write_bytes(original)
