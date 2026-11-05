"""02D browser acceptance; every destructive action uses a temporary Run Root."""
import os
import re
from pathlib import Path
import tempfile
import unittest

from tests.test_ui_browser import BrowserHarness, PROJECT


@unittest.skipUnless(os.environ.get('MDE_BROWSER_TESTS') == '1', 'Opt-in management browser')
class ManagementBrowserTests(unittest.TestCase, BrowserHarness):
    def test_metadata_export_regenerate_cancel_and_scoped_delete(self):
        from playwright.sync_api import expect
        from mde.storage import sha256_file
        with tempfile.TemporaryDirectory() as temp:
            self.start(PROJECT/'tests/fixtures/models', 'geometry', Path(temp)/'runs', 7865)
            try:
                handles = []
                for _ in range(2):
                    handle = self.runner.submit('geometry', PROJECT/'tests/assets/sample.png', device='cpu',
                        parameters={'action': 'viewer'}, requested_outputs=('depth', 'points', 'normals', 'intrinsics', 'mask'))
                    self.runner.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
                    self.runner.collect(handle); handles.append(handle)
                run_id = handles[0].run_id; run = self.store.root / run_id
                before = {str(p): sha256_file(p) for p in run.rglob('*') if p.is_file()}
                page = self.page()
                page.get_by_role('tab', name='Results', exact=True).click()
                page.locator('#saved-run-id textarea').fill(run_id)
                page.get_by_text('Run management', exact=True).click()
                def click(name): page.get_by_role('button', name=name, exact=True).click()
                click('Inspect saved Run ID')
                expect(page.get_by_label('Management action', exact=True)).to_have_value('Loaded management selection')
                page.get_by_label('Display name', exact=True).fill('Named fixture')
                click('Save metadata / archive status')
                expect(page.get_by_label('Management action', exact=True)).to_have_value(re.compile('Named fixture'))
                click('Inspect saved Run ID')
                expect(page.get_by_label('Management action', exact=True)).to_have_value('Loaded management selection')
                click('Regenerate Mesh (new generation)')
                expect(page.get_by_label('Management action', exact=True)).to_have_value(re.compile('generation_id'), timeout=15000)
                click('Export validated input / raw / derived')
                expect(page.get_by_role('link', name='Download export ZIP')).to_be_visible(timeout=15000)
                generation = next((run/'derived').glob('*/*/manifest.json')).parent.relative_to(run).as_posix()
                page.get_by_label('Derived path to delete (blank = entire Run)', exact=True).fill(generation)
                click('Review deletion')
                expect(page.get_by_label('Management action', exact=True)).to_have_value('Deletion review ready')
                click('Cancel deletion')
                expect(page.get_by_label('Management action', exact=True)).to_have_value('Deletion cancelled')
                self.assertTrue((run/generation).exists())
                click('Review deletion')
                expect(page.get_by_label('Management action', exact=True)).to_have_value('Deletion review ready')
                page.get_by_label('Type the exact Run ID to confirm deletion', exact=True).fill(run_id)
                click('Confirm deletion')
                expect(page.get_by_label('Management action', exact=True)).to_have_value(re.compile('deleted'))
                self.assertFalse((run/generation).exists())
                self.assertTrue((run/'derived/history.json').exists())
                self.assertEqual(before, {p:sha256_file(Path(p)) for p in before})
                page.get_by_label('Derived path to delete (blank = entire Run)', exact=True).fill('')
                click('Review deletion')
                expect(page.get_by_label('Management action', exact=True)).to_have_value('Deletion review ready')
                click('Confirm deletion')
                expect(page.get_by_label('Management action', exact=True)).to_have_value(re.compile('"generation": null'))
                self.assertFalse(run.exists())
                self.assertTrue((self.store.root/handles[1].run_id).exists())
                self.assertEqual(self.errors, []); self.assertEqual(self.external, [])
            finally:
                # Deleted handles must not be collected again by harness cleanup.
                self.runner.backend._jobs.clear()
                self.stop()
