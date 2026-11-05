"""Run management metadata contracts against an isolated Run Root."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from mde.contracts import JobHandle, utc_now
from mde.run_management import RunManagementService
from mde.storage import write_json


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_id = str(uuid.uuid4())
        self.run = self.root / self.run_id
        self.handle = JobHandle(self.run_id, 'attempt-0001', 'local', str(uuid.uuid4()),
                                utc_now(), 'key', self.run_id, 'local')
        write_json(self.run / 'attempts/attempt-0001/handle.json', self.handle.to_dict())
        write_json(self.run / 'job.json', {'input': 'preserved'})
        self.result = SimpleNamespace(to_dict=lambda: {'status': 'COMPLETED'})
        self.service = RunManagementService(SimpleNamespace(root=self.root), lambda handle: self.result)

    def test_metadata_archive_revision_and_raw_unchanged(self):
        before = (self.run / 'job.json').read_bytes()
        self.assertEqual(self.service.detail(self.run_id)['user_metadata']['revision'], 0)
        updated = self.service.update_metadata(self.run_id, 0, display_name='test', notes='notes', archived=True)
        self.assertEqual(updated['revision'], 1)
        self.assertEqual(self.service.list_runs(), [])
        self.assertEqual(len(self.service.list_runs(include_archived=True)), 1)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.service.update_metadata(self.run_id, 0, display_name='', notes='', archived=False)
        self.service.update_metadata(self.run_id, 1, display_name='test', notes='notes', archived=False)
        self.assertEqual((self.run / 'job.json').read_bytes(), before)
        self.assertEqual(len(self.service.list_runs()), 1)

    def test_invalid_run_and_symlink_rejected(self):
        with self.assertRaises(ValueError):
            self.service.detail('../escape')
        (self.run / 'user-metadata.json').symlink_to(self.root / 'outside')
        with self.assertRaises(Exception):
            self.service.update_metadata(self.run_id, 0, display_name='', notes='', archived=False)

    def test_explicit_delete_stale_different_run_and_scope(self):
        confirmation = self.service.prepare_delete(self.run_id)
        with self.assertRaises(ValueError):
            self.service.delete(confirmation, str(uuid.uuid4()), typed_run_id=self.run_id)
        with self.assertRaises(ValueError):
            self.service.delete(confirmation, self.run_id, typed_run_id='')
        self.assertTrue(self.run.exists())
        self.service.update_metadata(self.run_id, 0, display_name='changed', notes='', archived=False)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        confirmation = self.service.prepare_delete(self.run_id)
        self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        self.assertFalse(self.run.exists())

    def test_active_refused_and_derived_history(self):
        self.result = SimpleNamespace(to_dict=lambda: {'status': 'RUNNING'})
        with self.assertRaises(Exception):
            self.service.prepare_delete(self.run_id)
        self.result = SimpleNamespace(to_dict=lambda: {'status': 'COMPLETED'})
        folder = 'derived/' + 'a'*64 + '/' + 'b'*32
        write_json(self.run / folder / 'manifest.json', {'identity': 'fixture'})
        (self.run / folder / 'geometry.npz').write_bytes(b'fixture')
        confirmation = self.service.prepare_delete(self.run_id, generation=folder)
        self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        self.assertTrue((self.run / 'job.json').exists())
        self.assertFalse((self.run / folder).exists())
        from mde.storage import read_json
        self.assertEqual(read_json(self.run / 'derived/history.json')['events'][-1]['operation'], 'deleted')

    def test_export_only_selected_refs(self):
        import io
        import zipfile
        write_json(self.run / 'attempts/attempt-0001/job.json', {'job': 'fixture'})
        write_json(self.run / 'attempts/attempt-0001/job-result.json', {'status': 'COMPLETED'})
        (self.run / 'unreferenced.txt').write_text('must not export')
        with zipfile.ZipFile(io.BytesIO(self.service.export(self.run_id))) as archive:
            self.assertNotIn('unreferenced.txt', archive.namelist())
            self.assertIn('export-manifest.json', archive.namelist())

    def test_export_delete_race_and_partial_failure(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from unittest.mock import patch
        write_json(self.run / 'attempts/attempt-0001/job.json', {})
        write_json(self.run / 'attempts/attempt-0001/job-result.json', {})
        confirmation = self.service.prepare_delete(self.run_id)
        entered, release = threading.Event(), threading.Event()
        original = self.service._read_file
        def blocked(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test gate timeout')
            return original(*args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch.object(self.service, '_read_file', side_effect=blocked):
                export = pool.submit(self.service.export, self.run_id)
                self.assertTrue(entered.wait(2))
                deletion = pool.submit(self.service.delete, confirmation, self.run_id, typed_run_id=self.run_id)
                self.assertFalse(deletion.done())
                release.set(); self.assertTrue(export.result())
                deletion.result()
        self.assertFalse(self.run.exists())
        # A filesystem removal failure must be reported and kept for diagnosis.
        write_json(self.run / 'attempts/attempt-0001/handle.json', self.handle.to_dict())
        write_json(self.run / 'job.json', {})
        confirmation = self.service.prepare_delete(self.run_id)
        with patch('shutil.rmtree', side_effect=OSError('fixture failure')) as removal:
            removal.avoids_symlink_attacks = True
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        entries = [p for p in (self.root / '.management-quarantine').iterdir() if p.is_dir()]
        self.assertEqual(len(entries), 1)
        retry = self.service.prepare_retry(entries[0].name)
        with self.assertRaises(ValueError):
            self.service.retry_delete(retry, typed_run_id='')
        self.service.retry_delete(retry, typed_run_id=self.run_id)
        self.assertFalse(entries[0].exists())

    def test_explicit_regeneration_preserves_old_and_restarts(self):
        import numpy as np
        from mde.results import DerivedStore
        from mde.storage import read_json
        store = DerivedStore()
        identity = {'algorithm': 'fixture', 'version': '1'}
        generate = lambda: {'points': np.ones((2, 2, 3), dtype='<f4')}
        first = store.get(self.run, identity, generate)[1]
        second = store.get(self.run, identity, generate, force=True)[1]
        self.assertNotEqual(first['generation_id'], second['generation_id'])
        self.assertTrue((self.run / first['output']['path']).exists())
        self.assertEqual(DerivedStore().get(self.run, identity, generate)[1], second)
        events = read_json(self.run / 'derived/history.json')['events']
        self.assertEqual([e['operation'] for e in events], ['generate', 'regenerate'])

    def test_replaced_symlink_is_not_followed_during_export_read(self):
        from unittest.mock import patch
        path = self.run/'job.json'
        victim = self.root/'victim.json'; victim.write_text('private')
        original = self.service._safe_file
        def replace(run, relative):
            result = original(run, relative)
            path.unlink(); path.symlink_to(victim)
            return result
        with patch.object(self.service, '_safe_file', side_effect=replace):
            with self.assertRaises(OSError):
                self.service._read_file(self.run, 'job.json')
        self.assertEqual(victim.read_text(), 'private')

    def test_same_content_directory_replacement_invalidates_confirmation(self):
        import shutil
        confirmation = self.service.prepare_delete(self.run_id)
        old = self.root/'preserved-original'
        self.run.rename(old)
        shutil.copytree(old, self.run)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        self.assertTrue(old.exists()); self.assertTrue(self.run.exists())


if __name__ == '__main__':
    unittest.main()


class BackendManagementTests(unittest.TestCase):
    from tests.test_local_contract import LocalContractTests
    setUp = LocalContractTests.setUp
    stop_workers = LocalContractTests.stop_workers

    def test_real_terminal_export_and_unknown_active_refused(self):
        from mde.backends import LocalBackend
        from mde.contracts import JobStatus
        from mde.runner import ExperimentRunner
        from mde.storage import sha256_file
        import time
        project = Path(__file__).resolve().parents[1]
        service = RunManagementService(self.store, self.runner.collect)
        handle = self.runner.submit('fake', project/'tests/assets/sample.png', device='cpu', parameters={'action':'block'})
        with self.assertRaises(Exception):
            service.prepare_delete(handle.run_id)
        readonly = ExperimentRunner(self.runner.registry, LocalBackend(self.store.root), self.store, project)
        with self.assertRaises(Exception):
            RunManagementService(self.store, readonly.collect).prepare_delete(handle.run_id)
        self.runner.cancel(handle)
        self.runner.collect(handle)
        run = self.store.root/handle.run_id
        before = {p.relative_to(run):(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
        service.update_metadata(handle.run_id,0,display_name='cancelled',notes='',archived=True)
        self.assertTrue(service.export(handle.run_id))
        self.assertEqual(before,{p:(sha256_file(run/p),(run/p).stat().st_mtime_ns) for p in before})
        service.delete(service.prepare_delete(handle.run_id),handle.run_id,typed_run_id=handle.run_id)
        self.assertFalse(run.exists())
