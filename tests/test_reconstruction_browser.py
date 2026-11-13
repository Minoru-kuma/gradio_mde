"""Opt-in actual DA3 native-K and depth-only GeoCalib / derived browser acceptance."""
import json
import os
import unittest

from tests.test_results_browser import ViewerBrowserHarness
from tests.test_ui_browser import PROJECT


@unittest.skipUnless(os.environ.get('MDE_UI_CPU_SMOKE')=='1','Opt-in depth-only reconstruction CPU browser')
class ReconstructionBrowserTests(unittest.TestCase,ViewerBrowserHarness):
    def test_da3_native_and_estimated_camera_points_mesh_restart_and_known_override(self):
        from playwright.sync_api import expect
        from mde.environments import EnvironmentProfile
        from mde.targets import TargetConfiguration
        from mde.storage import read_json,sha256_file
        targets=TargetConfiguration({'mde-da3':EnvironmentProfile('mde-da3',prefix=str(PROJECT/'.local/envs/mde-da3'))},
            {'da3/da3-small':PROJECT/'.local/weights/da3-small'})
        root=PROJECT/'.local/validation/phase-03-7-browser-runs'
        self.start(PROJECT/'models','da3',root,7868,targets=targets,camera_config=PROJECT/'configs/camera-estimator.example.json')
        evidence=[]
        try:
            for native in (True,False):
                page=self.page()
                page.get_by_role('tab',name='Inference',exact=True).first.click()
                self.upload(page,PROJECT/'tests/assets/sample.png')
                self.select(page,'#device-choice','cpu')
                page.locator('#requested-artifacts').get_by_label('intrinsics',exact=True).set_checked(native)
                page.locator('#submit-run').click()
                expect(page.locator('#job-status textarea')).to_have_value('COMPLETED',timeout=120000)
                run_id=page.locator('#selected-run-id textarea').input_value();run=root/run_id
                result=read_json(run/'attempts/attempt-0001/job-result.json')
                self.assertNotIn('points',result['outputs'][0])
                self.assertEqual('intrinsics' in result['outputs'][0],native)
                raw={p.relative_to(run).as_posix():(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
                self.mode(page,'Point Cloud')
                provenance=json.loads(page.locator('[data-provenance]').text_content())
                self.assertEqual(provenance['camera']['source'],'model native' if native else 'estimated')
                self.mode(page,'Mesh');faces=int(page.locator('[data-stage]').get_attribute('data-faces'))
                self.assertGreater(faces,0);self.operate(page)
                evidence.append({'native':native,'run_id':run_id,'faces':faces,'camera':provenance['camera']})
                if native:
                    page.locator('details').filter(has=page.locator('[data-known-camera]')).locator('summary').click()
                    page.locator('[data-known-camera]').check()
                    for key,value in {'fx':600,'fy':600,'cx':126,'cy':126,'width':252,'height':252}.items():
                        page.locator('[data-k-'+key+']').fill(str(value))
                    page.locator('[data-apply-camera]').click()
                    expect(page.locator('[data-provenance]')).to_contain_text('"source": "known"',timeout=15000)
                    page.locator('[data-known-camera]').uncheck();page.locator('[data-apply-camera]').click()
                    expect(page.locator('[data-provenance]')).to_contain_text('"source": "model native"',timeout=15000)
                for relative,expected in raw.items():self.assertEqual((sha256_file(run/relative),(run/relative).stat().st_mtime_ns),expected)
            self.reopen(evidence[-1]['run_id'],7868)
            self.assertEqual(self.external,[]);self.assertEqual(self.errors,[])
            self.assertEqual(len(self.runner.backend._jobs),2)
            print(json.dumps({'reconstruction_browser':evidence,'restart_without_models':True,
                'raw_hash_mtime_unchanged':True,'external_requests':self.external,'page_errors':self.errors}),flush=True)
        finally:self.stop()
