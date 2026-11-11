"""03.3 browser acceptance for model/variant selection and independent CPU workers."""
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest

from tests.test_ui_browser import BrowserHarness,PROJECT


@unittest.skipUnless(os.environ.get('MDE_BROWSER_TESTS')=='1','Opt-in multi-model browser')
class MultiModelBrowserTests(unittest.TestCase,BrowserHarness):
    def test_two_models_simultaneous_admission_unprepared_variant_and_selection_reset(self):
        from playwright.sync_api import expect
        from mde.environments import EnvironmentProfile
        from mde.targets import TargetConfiguration
        from mde.storage import read_json,sha256_file
        prefix=os.environ.get('MDE_TEST_CONDA_PREFIX')
        targets=TargetConfiguration({'mde-moge':EnvironmentProfile('mde-moge',
            name=None if prefix else os.environ.get('MDE_TEST_CONDA_ENV','mde-moge'),prefix=prefix)})
        with tempfile.TemporaryDirectory() as temporary:
            self.start(PROJECT/'tests/fixtures/models','fake',Path(temporary)/'runs',7866,targets=targets)
            try:
                a,b=self.page(),self.page()
                self.select(b,'#model-choice','Independent alternate fixture')
                expect(b.locator('#parameter-distance input')).to_have_value('3.5')
                expect(a.locator('#parameter-action')).to_be_visible()
                self.assertEqual(b.locator('#parameter-action').count(),0)
                self.select(b,'#variant-choice','offset')
                expect(b.locator('#model-preparation')).to_contain_text('Unprepared')
                expect(b.locator('#submit-run')).to_be_disabled()
                expect(b.locator('#parameter-offset input')).to_have_value('4')
                self.select(b,'#variant-choice','distance')
                expect(b.locator('#parameter-distance input')).to_have_value('3.5')
                expect(b.locator('#submit-run')).to_be_enabled()
                expect(b.locator('#device-choice input')).to_have_value('')
                b.locator('#parameter-distance input').fill('6.25')
                self.select(a,'#parameter-action','block')
                for page in (a,b):
                    self.upload(page,PROJECT/'tests/assets/sample.png')
                    self.select(page,'#device-choice','cpu')
                target=int(time.time()*1000)+500
                for page in (a,b):
                    page.evaluate("t=>setTimeout(()=>document.querySelector('#submit-run').click(),t-Date.now())",target)
                a.wait_for_timeout(1200)
                messages=[p.locator('#action-notice textarea').input_value() for p in (a,b)]
                self.assertEqual(sum('accepted' in x for x in messages),1,messages)
                self.assertEqual(sum('BackendBusy' in x for x in messages),1,messages)
                self.assertEqual(len(self.runner.backend._jobs),1)
                winner=next(i for i,x in enumerate(messages) if 'accepted' in x)
                pages=(a,b);expected_models=('fake','alternate')
                if winner==0:
                    expect(a.locator('#job-status textarea')).to_have_value('RUNNING',timeout=20000)
                    self.select(a,'#model-choice','Independent alternate fixture')
                    expect(a.locator('#parameter-distance input')).to_have_value('3.5')
                    a.locator('#cancel-run').click()
                    expect(a.locator('#job-status textarea')).to_have_value(re.compile('CANCELLED.*',re.S),timeout=15000)
                else:
                    expect(b.locator('#job-status textarea')).to_have_value('COMPLETED',timeout=30000)
                loser=1-winner
                if loser==0:self.select(a,'#parameter-action','success')
                pages[loser].locator('#submit-run').click()
                expect(pages[loser].locator('#job-status textarea')).to_have_value('COMPLETED',timeout=30000)
                self.assertEqual(len(self.runner.backend._jobs),2)
                jobs=[read_json(job.run/'job.json') for job in self.runner.backend._jobs.values()]
                self.assertEqual({job['model_ref']['model_id'] for job in jobs},{'fake','alternate'})
                alternate=next(job for job in jobs if job['model_ref']['model_id']=='alternate')
                self.assertEqual(alternate['inference']['parameters'],{'distance':6.25})
                fake=next(job for job in jobs if job['model_ref']['model_id']=='fake')
                self.assertEqual(set(fake['inference']['parameters']),{'action'})
                completed=next(job for job in self.runner.backend._jobs.values() if job.spec.model_ref['model_id']=='alternate')
                run=completed.run
                def snapshot():return {p.relative_to(run).as_posix():(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
                before=snapshot();c=self.page();c.get_by_role('tab',name='Results',exact=True).first.click()
                c.locator('#saved-run-id textarea').fill(run.name);c.locator('#open-saved-run').click()
                expect(c.locator('#selected-run-id textarea')).to_have_value(run.name,timeout=15000)
                self.assertEqual(snapshot(),before)
                self.assertFalse(any('/queue/join' in url for url in self.requests))
                self.assertEqual(self.external,[]);self.assertEqual(self.errors,[])
                print(json.dumps({'two_model_browser':'PASS','messages':messages,'winner_model':expected_models[winner],
                    'saved_reload_hash_mtime_unchanged':True,'jobs':len(jobs),'page_errors':self.errors}),flush=True)
            finally:self.stop()


@unittest.skipUnless(os.environ.get('MDE_UI_CPU_SMOKE')=='1','Opt-in two real model CPU UI')
class MultiModelCPUUIBrowserTests(unittest.TestCase,BrowserHarness):
    def test_moge_and_da3_share_backend_use_separate_environments_and_checkpoint_map(self):
        from playwright.sync_api import expect
        from mde.environments import EnvironmentProfile
        from mde.targets import TargetConfiguration
        from mde.storage import read_json,sha256_file
        prefix=os.environ.get('MDE_TEST_CONDA_PREFIX')
        targets=TargetConfiguration({
            'mde-moge':EnvironmentProfile('mde-moge',name=None if prefix else 'mde-moge',prefix=prefix),
            'mde-da3':EnvironmentProfile('mde-da3',prefix=str(PROJECT/'.local/envs/mde-da3'))},
            {'moge/moge-2-vits-normal':PROJECT/'.local/weights/moge-2-vits-normal.pt',
             'da3/da3-small':PROJECT/'.local/weights/da3-small'})
        root=PROJECT/'runs'
        self.start(PROJECT/'models','moge',root,7867,targets=targets)
        evidence=[]
        try:
            a,b=self.page(),self.page()
            self.select(b,'#model-choice','Depth Anything 3 Small (CPU)')
            expect(b.locator('#parameter-process_res')).to_be_visible()
            self.assertEqual(b.locator('#parameter-num_tokens').count(),0)
            expect(a.locator('#parameter-num_tokens')).to_be_visible()
            for page,model,unit,shape in ((a,'moge','m',[256,256]),(b,'da3','arbitrary',[252,252])):
                self.upload(page,PROJECT/'tests/assets/sample.png');self.select(page,'#device-choice','cpu')
                page.locator('#submit-run').click()
                expect(page.locator('#job-status textarea')).to_have_value('COMPLETED',timeout=120000)
                run_id=page.locator('#selected-run-id textarea').input_value();run=root/run_id
                result=read_json(run/'attempts/attempt-0001/job-result.json');job=read_json(run/'job.json')
                self.assertEqual(job['model_ref']['model_id'],model)
                self.assertEqual(result['outputs'][0]['metadata']['depth_unit'],unit)
                self.assertEqual(result['outputs'][0]['metadata']['shape'],shape)
                self.assertEqual(result['execution']['device'],'cpu')
                self.assertEqual((run/'logs/attempt-0001/stdout.log').read_text().count('predict: '),1)
                before={p.relative_to(run).as_posix():(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
                c=self.page();c.get_by_role('tab',name='Results',exact=True).first.click()
                c.locator('#saved-run-id textarea').fill(run_id);c.locator('#open-saved-run').click()
                expect(c.locator('#selected-run-id textarea')).to_have_value(run_id,timeout=15000)
                after={p.relative_to(run).as_posix():(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
                self.assertEqual(before,after)
                evidence.append({'model':model,'run_id':run_id,'torch':result['execution']['torch_version'],
                    'prefix':result['execution']['python_prefix'],'shape':shape,'unit':unit,'raw_hash_mtime_unchanged':True})
            self.assertNotEqual(evidence[0]['prefix'],evidence[1]['prefix'])
            self.assertEqual(len(self.runner.backend._jobs),2)
            self.assertEqual(self.external,[]);self.assertEqual(self.errors,[])
            print(json.dumps({'two_real_cpu_models':evidence,'external_requests':self.external,'page_errors':self.errors}),flush=True)
        finally:self.stop()
