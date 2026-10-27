"""Opt-in offline 02C browser + explicit native geometry CPU acceptance."""
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from tests.test_ui_browser import BrowserHarness, PROJECT


class ViewerBrowserHarness(BrowserHarness):
    def page(self):
        page = super().page()
        page.on('console', lambda message: self.errors.append(message.text) if message.type == 'error' else None)
        return page

    def message(self, page):
        return page.locator('#results-viewer [data-message]')

    def mode(self, page, mode):
        from playwright.sync_api import expect
        selected = page.locator('#selected-run-id textarea').input_value()
        expect(page.locator('#results-viewer section')).to_have_attribute('data-run-id',selected,timeout=30000)
        page.locator('[data-mode]').select_option(mode)
        expect(self.message(page)).to_contain_text('Loaded ' + mode, timeout=30000)
        expect(page.locator('#results-viewer section')).to_have_attribute('data-loaded-mode',mode,timeout=30000)

    def camera(self, page):
        return json.loads(page.locator('[data-stage]').get_attribute('data-camera'))

    def operate(self, page):
        canvas = page.locator('[data-stage] canvas')
        canvas.scroll_into_view_if_needed()
        box = canvas.bounding_box(); x, y = box['x']+box['width']/2, box['y']+box['height']/2
        previous = self.camera(page)
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x+70, y+25, steps=8); page.mouse.up()
        self.assertNotEqual(previous, self.camera(page), 'rotation')
        previous = self.camera(page)
        page.mouse.wheel(0, -150); page.wait_for_timeout(200)
        self.assertNotEqual(previous, self.camera(page), 'zoom')
        previous = self.camera(page)
        page.mouse.move(x, y); page.mouse.down(button='right'); page.mouse.move(x+25, y+15, steps=5); page.mouse.up(button='right')
        self.assertNotEqual(previous, self.camera(page), 'pan')
        # Rendering must contain visible geometry, beyond the background color.
        from PIL import Image
        raw = canvas.evaluate("c => c.toDataURL('image/png').split(',')[1]")
        image = Image.open(io.BytesIO(base64.b64decode(raw))).convert('RGB')
        counts = sorted(image.getcolors(image.width*image.height), reverse=True)
        self.assertGreater(sum(c for c, _ in counts[1:]), 50, 'geometry must draw pixels')

    def four_views(self, page, run, *, geometry=True):
        from playwright.sync_api import expect
        self.mode(page, 'Depth')
        expect(page.locator('[data-depth]')).to_be_visible()
        self.mode(page, 'RawDepth')
        with page.expect_download() as event:
            page.locator('[data-download]').click()
        from mde.storage import read_json
        result = read_json(run/'attempts/attempt-0001/job-result.json')
        original = (run/result['outputs'][0]['depth']['path']).read_bytes()
        self.assertEqual(Path(event.value.path()).read_bytes(), original)
        if not geometry:
            for mode in ('Point Cloud', 'Mesh'):
                page.locator('[data-mode]').select_option(mode)
                expect(self.message(page)).to_contain_text('3D unavailable', timeout=15000)
            return
        self.mode(page, 'Point Cloud')
        self.assertFalse((run/'derived').exists(), 'mesh must remain lazy')
        self.assertEqual(page.locator('[data-stage]').get_attribute('data-library'), '180')
        self.gl_info = page.locator('[data-stage] canvas').evaluate('''canvas => {
          const gl = canvas.getContext('webgl2'); const ext = gl.getExtension('WEBGL_debug_renderer_info');
          return {version:gl.getParameter(gl.VERSION), renderer:ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unavailable'};
        }''')
        self.operate(page)
        camera = self.camera(page)
        for color in ('RGB color', 'Depth color', 'Normal color'):
            page.locator('[data-color]').select_option(color)
            self.assertEqual(page.locator('[data-stage]').get_attribute('data-style'), color)
            self.assertEqual(camera, self.camera(page))
        self.mode(page, 'Mesh')
        self.assertEqual(camera, self.camera(page))
        self.assertEqual(page.locator('[data-stage]').get_attribute('data-cache-reused'), 'false')
        self.assertGreater(int(page.locator('[data-stage]').get_attribute('data-faces')), 0)
        for style in ('RGB textured', 'Geometry', 'Wireframe'):
            page.locator('[data-mesh]').select_option(style)
            self.assertEqual(page.locator('[data-stage]').get_attribute('data-style'), style)
            self.assertEqual(camera, self.camera(page))
            if style == 'RGB textured':
                page.wait_for_timeout(250)
                from PIL import Image
                raw = page.locator('[data-stage] canvas').evaluate("c => c.toDataURL('image/png').split(',')[1]")
                picture = Image.open(io.BytesIO(base64.b64decode(raw))).convert('RGB')
                self.assertGreater(len(picture.getcolors(picture.width*picture.height)), 20,
                    'RGB texture must actually render colors')
        self.operate(page)
        page.locator('[data-reset]').click()
        self.assertNotEqual(camera, self.camera(page))
        self.mode(page, 'Point Cloud'); self.mode(page, 'Mesh')
        self.assertEqual(page.locator('[data-stage]').get_attribute('data-cache-reused'), 'true')

    def reopen(self, run_id, port):
        from mde.backends import LocalBackend
        from mde.runner import ExperimentRunner
        from mde.ui_controller import InferenceController
        from mde.ui import build_app
        import gradio as gr
        from playwright.sync_api import expect
        self.app.close()
        self.controller = InferenceController(ExperimentRunner(self.runner.registry,
            LocalBackend(self.store.root), self.store, PROJECT), self.controller.model_id)
        self.app = build_app(self.controller)
        self.app.launch(server_name='127.0.0.1',server_port=port,share=False,prevent_thread_lock=True,
            quiet=True,ssr_mode=False,enable_monitoring=False,
            theme=gr.themes.Default(font=['system-ui']),footer_links=[],run_history=False)
        page = self.page()
        page.get_by_role('tab',name='Results',exact=True).click()
        page.locator('#open-saved-run').click()
        expect(page.locator('#load-notice textarea')).to_have_value('Enter a saved Run ID before opening a Run.')
        page.locator('#saved-run-id textarea').fill(run_id)
        page.locator('#open-saved-run').click()
        expect(page.locator('#load-notice textarea')).to_have_value('Loaded saved Run '+run_id+' · COMPLETED.',timeout=15000)
        expect(self.message(page)).to_contain_text('Loaded Depth',timeout=15000)
        self.mode(page,'Mesh')
        self.assertEqual(page.locator('[data-stage]').get_attribute('data-cache-reused'),'true')
        self.operate(page)
        return page


@unittest.skipUnless(os.environ.get('MDE_BROWSER_TESTS')=='1','Opt-in 02C browser')
class FakeViewerBrowserTests(unittest.TestCase, ViewerBrowserHarness):
    def test_geometry_views_camera_offline_reuse_restart_and_optional_absence(self):
        from playwright.sync_api import expect
        from mde.storage import sha256_file
        with tempfile.TemporaryDirectory() as tmp:
            self.start(PROJECT/'tests/fixtures/models','geometry',Path(tmp)/'runs',7863)
            try:
                page = self.page(); self.upload(page,PROJECT/'tests/assets/sample.png')
                self.select(page,'#device-choice','cpu')
                page.locator('#parameter-action textarea').fill('viewer')
                for name in ('points','normals','intrinsics','mask'):
                    page.locator('#requested-artifacts').get_by_label(name,exact=True).check()
                page.locator('#submit-run').click()
                expect(page.locator('#job-status textarea')).to_have_value('COMPLETED',timeout=60000)
                run_id = page.locator('#selected-run-id textarea').input_value(); run=self.store.root/run_id
                before={str(p):(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
                self.four_views(page,run)
                saved=self.reopen(run_id,7863)
                self.assertEqual(before,{p:(sha256_file(Path(p)),Path(p).stat().st_mtime_ns) for p in before})
                self.assertEqual((run/'logs/attempt-0001/stdout.log').read_text().count('geometry predict'),1)
                # A depth-only legacy profile provides a clear 3D-unavailable message.
                handle=self.runner.submit('geometry',PROJECT/'tests/assets/sample.png',device='cpu')
                self.runner.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
                self.runner.collect(handle)
                saved.locator('#saved-run-id textarea').fill(handle.run_id);saved.locator('#open-saved-run').click()
                expect(saved.locator('#selected-run-id textarea')).to_have_value(handle.run_id,timeout=15000)
                self.four_views(saved,self.store.root/handle.run_id,geometry=False)
                # Optional colors are disabled with a visible reason.
                handle=self.runner.submit('geometry',PROJECT/'tests/assets/sample.png',device='cpu',
                    requested_outputs=('depth','points'),parameters={'action':'success'})
                self.runner.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
                self.runner.collect(handle)
                saved.locator('#saved-run-id textarea').fill(handle.run_id);saved.locator('#open-saved-run').click()
                expect(saved.locator('#selected-run-id textarea')).to_have_value(handle.run_id,timeout=15000)
                self.mode(saved,'Point Cloud')
                expect(saved.locator('[data-color] option').nth(0)).to_have_attribute('disabled','')
                expect(saved.locator('[data-color] option').nth(2)).to_have_attribute('disabled','')
                expect(self.message(saved)).to_contain_text('RGB unavailable')
                expect(self.message(saved)).to_contain_text('Normal color unavailable')
                self.mode(saved,'Mesh')
                expect(saved.locator('[data-mesh] option').nth(0)).to_have_attribute('disabled','')
                # Exercise the explicit viewer limit in the same offline browser.
                from PIL import Image
                for width, accepted in ((512,True),(513,False)):
                    image=Path(tmp)/f'capacity-{width}.png'
                    Image.new('RGB',(width,512),(100,150,200)).save(image)
                    handle=self.runner.submit('geometry',image,device='cpu',requested_outputs=('depth','points'),
                        parameters={'action':'viewer'})
                    self.runner.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
                    self.runner.collect(handle)
                    saved.locator('#saved-run-id textarea').fill(handle.run_id);saved.locator('#open-saved-run').click()
                    expect(saved.locator('#selected-run-id textarea')).to_have_value(handle.run_id,timeout=20000)
                    if accepted:
                        self.mode(saved,'Point Cloud');self.operate(saved)
                        self.assertEqual(saved.locator('[data-stage]').get_attribute('data-count'),'262143')
                        self.mode(saved,'Mesh');self.operate(saved)
                        capacity_faces=int(saved.locator('[data-stage]').get_attribute('data-faces'))
                    else:
                        expect(self.message(saved)).to_contain_text('exceeds 262,144 output pixels',timeout=20000)
                        self.assertFalse((self.store.root/handle.run_id/'derived').exists())
                self.assertEqual(self.external,[]);self.assertEqual(self.errors,[])
                self.assertFalse(any('/queue/join' in r for r in self.requests))
                print(json.dumps({'fake_viewer_run':run_id,'browser':self.browser.version,
                    'external_requests':self.external,'page_errors':self.errors,'predict_count':1,'raw_hashes_unchanged':True,
                    'capacity_points':262143,'capacity_faces':capacity_faces,'over_limit_rejected':True,'webgl':self.gl_info}),flush=True)
            finally:self.stop()


@unittest.skipUnless(os.environ.get('MDE_UI_CPU_SMOKE')=='1','Opt-in native Points CPU viewer')
class CPUViewerBrowserTests(unittest.TestCase, ViewerBrowserHarness):
    def test_explicit_native_points_cpu_inference_four_views_and_offline_restart(self):
        from playwright.sync_api import expect
        from mde.storage import read_json,sha256_file
        self.start(PROJECT/'models','moge',PROJECT/'runs',7864,PROJECT/'.local/weights/moge-2-vits-normal.pt')
        try:
            page=self.page();self.upload(page,PROJECT/'tests/assets/sample.png')
            self.select(page,'#device-choice','cpu')
            for name in ('points','normals','intrinsics','mask'):
                page.locator('#requested-artifacts').get_by_label(name,exact=True).check()
            page.locator('#submit-run').click()
            expect(page.locator('#job-status textarea')).to_have_value('COMPLETED',timeout=180000)
            run_id=page.locator('#selected-run-id textarea').input_value();run=self.store.root/run_id
            result=read_json(run/'attempts/attempt-0001/job-result.json')
            self.assertEqual(result['execution']['device'],'cpu')
            self.assertIn('force_projection=False',result['outputs'][0]['metadata']['geometry']['points']['native_convention'])
            before={str(p):(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
            self.four_views(page,run)
            page.screenshot(path=str(PROJECT/'.local/validation/02c-cpu-mesh.png'))
            saved=self.reopen(run_id,7864)
            self.assertEqual(before,{p:(sha256_file(Path(p)),Path(p).stat().st_mtime_ns) for p in before})
            self.assertEqual((run/'logs/attempt-0001/stdout.log').read_text().count('predict:'),1)
            self.assertEqual(self.external,[]);self.assertEqual(self.errors,[])
            self.assertFalse(any('/queue/join' in r for r in self.requests))
            print(json.dumps({'native_cpu_viewer_run':run_id,'browser':self.browser.version,
                'faces':saved.locator('[data-stage]').get_attribute('data-faces'),
                'metrics':result['metrics'],'external_requests':self.external,'page_errors':self.errors,
                'predict_count':1,'raw_hashes_unchanged':True,'restart_without_worker':True,'webgl':self.gl_info}),flush=True)
        finally:self.stop()
