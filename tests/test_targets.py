"""03.3 target mapping / checkpoint isolation, without model imports."""
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import Mock,patch
import uuid

from mde.environments import CondaLauncher,EnvironmentProfile,EnvironmentResolver,WorkerManager
from mde.registry import ModelRegistry
from mde.storage import RunStore,sha256_file,write_json
from mde.targets import TargetConfiguration

PROJECT=Path(__file__).resolve().parents[1]


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def write(self,data):
        path=self.root/'targets.json';write_json(path,data);return path

    def test_relative_paths_and_unprepared_metadata_without_environment_imports(self):
        targets=TargetConfiguration.read(self.write({'schema_version':'1.0',
            'environments':{'mde-da3':{'prefix':'envs/da3'}},
            'checkpoints':{'da3/da3-small':'weights/da3'}}))
        self.assertEqual(targets.profiles['mde-da3'].prefix,str(self.root/'envs/da3'))
        info=ModelRegistry(PROJECT/'models').get_model('da3')
        self.assertFalse(targets.preparation(info,'da3-small')['available'])
        (self.root/'envs/da3/bin').mkdir(parents=True);(self.root/'envs/da3/bin/python').write_text('fixture')
        self.assertIn('checkpoint',targets.preparation(info,'da3-small')['message'])
        (self.root/'weights/da3').mkdir(parents=True)
        self.assertTrue(targets.preparation(info,'da3-small')['available'])
        self.assertFalse(targets.preparation(ModelRegistry(PROJECT/'models').get_model('moge'),None)['available'])

    def test_rejects_ambiguous_profiles_unknown_fields_and_wrong_checkpoint_keys(self):
        for extra in ({'environments':[]},{'checkpoints':[]},{'extra':True},
            {'environments':{'mde-da3':{'name':'base'}}},
            {'environments':{'mde-da3':{'name':'mde-da3','prefix':'other'}}},
            {'environments':{'mde-da3':{'prefix':''}}},
            {'environments':{'mde-da3':{'name':1}}},
            {'checkpoints':{'da3':'weights'}},{'checkpoints':{'da3/da3-small':None}}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                TargetConfiguration.read(self.write({'schema_version':'1.0',**extra}))

    def test_worker_map_uses_job_variant_and_clears_inherited_checkpoint(self):
        registry=ModelRegistry(PROJECT/'tests/fixtures/models')
        resolver=EnvironmentResolver({key:EnvironmentProfile(key,name='fixture') for key in ('mde-moge','mde-fake-alternate')})
        targets={'fake/fake-depth':self.root/'fake.pt','alternate/offset':self.root/'alternate.pt'}
        manager=WorkerManager(PROJECT,resolver,CondaLauncher(),checkpoints=targets)
        store=RunStore(PROJECT,self.root/'runs')
        with patch.dict(os.environ,{'MDE_CHECKPOINT_PATH':'/wrong/global/checkpoint'}),patch('subprocess.Popen') as spawn:
            for model,variant_id,expected in (('fake','fake-depth',targets['fake/fake-depth']),
                    ('alternate','offset',targets['alternate/offset']),('alternate','distance',None)):
                info=registry.get_model(model);reference=info.environment(variant_id)
                reference['definition_digest']=sha256_file(PROJECT/reference['definition_ref'])
                run=store.prepare(str(uuid.uuid4()),PROJECT/'tests/assets/sample.png')
                job=run/'job.json';write_json(job,{'model_ref':{'model_id':model,'variant':info.effective_variant(variant_id)}})
                manager.start(reference,job,run)
                environment=spawn.call_args.kwargs['env']
                self.assertEqual(environment.get('MDE_CHECKPOINT_PATH'),str(expected) if expected else None)
            self.assertEqual(spawn.call_count,3)

    def test_legacy_single_job_checkpoint_override_is_preserved(self):
        info=ModelRegistry(PROJECT/'tests/fixtures/models').get_model('fake')
        reference=info.environment();reference['definition_digest']=sha256_file(PROJECT/reference['definition_ref'])
        store=RunStore(PROJECT,self.root/'runs');run=store.prepare(str(uuid.uuid4()),PROJECT/'tests/assets/sample.png')
        manager=WorkerManager(PROJECT,EnvironmentResolver({'mde-moge':EnvironmentProfile('mde-moge',name='fixture')}),
                              CondaLauncher(),checkpoint=self.root/'explicit.pt')
        with patch('subprocess.Popen') as spawn:
            manager.start(reference,run/'job.json',run)
        self.assertEqual(spawn.call_args.kwargs['env']['MDE_CHECKPOINT_PATH'],str(self.root/'explicit.pt'))

    def test_map_cannot_be_combined_with_a_manager_wide_override(self):
        with self.assertRaisesRegex(ValueError,'per-variant checkpoint map'):
            WorkerManager(PROJECT,EnvironmentResolver({}),CondaLauncher(),
                          checkpoint=self.root/'global.pt',checkpoints={})
