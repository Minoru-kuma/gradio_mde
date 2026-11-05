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

    def test_three_mesh_generations_latest_delete_partial_retry_and_reload(self):
        import numpy as np
        import shutil
        from unittest.mock import patch
        from mde.results import DerivedStore
        from mde.storage import read_json
        store = DerivedStore()
        identity = {'algorithm': 'mesh-fixture', 'version': '1'}
        calls = []
        def generate():
            calls.append(1)
            return {'points': np.ones((2, 2, 3), dtype='<f4'), 'faces': np.array([[0, 1, 2]], dtype='<u4')}
        generations = [store.get(self.run, identity, generate, force=True)[1] for _ in range(3)]
        latest = str(Path(generations[-1]['output']['path']).parent)
        raw = (self.run/'job.json').read_bytes()
        confirmation = self.service.prepare_delete(self.run_id, generation=latest)
        original_remove = shutil.rmtree
        def partial(name, *, dir_fd):
            import os
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=dir_fd)
            try:
                os.unlink('manifest.json', dir_fd=fd)
            finally:
                os.close(fd)
            raise OSError('fixture partial removal')
        with patch('shutil.rmtree', side_effect=partial) as removal:
            removal.avoids_symlink_attacks = True
            with self.assertRaises(OSError):
                self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        # A partially deleted latest generation never becomes a reuse candidate.
        self.assertEqual(DerivedStore().get(self.run, identity, generate)[1], generations[1])
        retry = self.service.prepare_delete(self.run_id, generation=latest)
        self.service.delete(retry, self.run_id, typed_run_id=self.run_id)
        self.assertEqual(DerivedStore().get(self.run, identity, generate)[1], generations[1])
        self.assertEqual(len(calls), 3)
        # Remove the selected generation while multiple generations existed.
        target = str(Path(generations[1]['output']['path']).parent)
        self.service.delete(self.service.prepare_delete(self.run_id, generation=target), self.run_id, typed_run_id=self.run_id)
        self.assertEqual(DerivedStore().get(self.run, identity, generate)[1], generations[0])
        target = str(Path(generations[0]['output']['path']).parent)
        self.service.delete(self.service.prepare_delete(self.run_id, generation=target), self.run_id, typed_run_id=self.run_id)
        self.assertFalse(DerivedStore().get(self.run, identity, generate)[2])
        self.assertEqual((self.run/'job.json').read_bytes(), raw)
        self.assertEqual(sum(e['operation']=='deleted' for e in read_json(self.run/'derived/history.json')['events']), 3)

    def test_generation_in_progress_makes_old_delete_confirmation_stale(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        import numpy as np
        from mde.results import DerivedStore
        confirmation = self.service.prepare_delete(self.run_id)
        entered, release = threading.Event(), threading.Event()
        def generate():
            entered.set()
            if not release.wait(5): raise RuntimeError('gate timeout')
            return {'points': np.ones((2, 2, 3), dtype='<f4')}
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(DerivedStore().get, self.run, {'algorithm':'fixture'}, generate)
            self.assertTrue(entered.wait(2))
            deletion = pool.submit(self.service.delete, confirmation, self.run_id, typed_run_id=self.run_id)
            self.assertFalse(deletion.done())
            release.set(); future.result()
            with self.assertRaisesRegex(ValueError, 'Stale'):
                deletion.result()
        self.assertTrue(self.run.exists())

    def test_directory_swap_after_review_cannot_authorize_quarantine_retry(self):
        import os
        from unittest.mock import patch
        confirmation = self.service.prepare_delete(self.run_id)
        original = os.rename
        def swap(source, destination, **kwargs):
            if source == self.run_id:
                original(self.run, self.root/'preserved')
                self.run.mkdir(); (self.run/'foreign.txt').write_text('preserve')
            return original(source, destination, **kwargs)
        with patch('os.rename', side_effect=swap):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        entry = next(p for p in (self.root/'.management-quarantine').iterdir() if p.is_dir())
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.service.prepare_retry(entry.name)
        self.assertEqual((entry/'foreign.txt').read_text(), 'preserve')
        self.assertTrue((self.root/'preserved/job.json').exists())

    def test_generation_parent_swap_uses_pinned_directory(self):
        from unittest.mock import patch
        folder = 'derived/' + 'a'*64 + '/' + 'b'*32
        write_json(self.run/folder/'manifest.json', {'identity':'fixture'})
        (self.run/folder/'geometry.npz').write_bytes(b'fixture')
        victim = self.root/'victim'; (victim/('b'*32)).mkdir(parents=True)
        (victim/('b'*32)/'keep').write_text('preserve')
        confirmation = self.service.prepare_delete(self.run_id, generation=folder)
        original = self.service._open_directory
        def swap(root, relative):
            fd = original(root, relative)
            key = self.run/Path(folder).parent
            key.rename(self.run/'derived'/'pinned-original')
            key.symlink_to(victim, target_is_directory=True)
            return fd
        with patch.object(self.service, '_open_directory', side_effect=swap):
            with self.assertRaises(ValueError):
                self.service.delete(confirmation, self.run_id, typed_run_id=self.run_id)
        self.assertEqual((victim/('b'*32)/'keep').read_text(), 'preserve')

    def test_archive_file_count_corruption_and_path_scope(self):
        self.service.update_metadata(self.run_id,0,display_name='name',notes='note',archived=False)
        count = len([p for p in self.run.rglob('*') if p.is_file()])
        self.service.update_metadata(self.run_id,1,display_name='name',notes='note',archived=True)
        self.assertEqual(count,len([p for p in self.run.rglob('*') if p.is_file()]))
        self.service.update_metadata(self.run_id,2,display_name='name',notes='note',archived=False)
        for relative in ('derived/../job.json', '/tmp/another/run', 'derived/key/../../other'):
            with self.assertRaises(ValueError):
                self.service.prepare_delete(self.run_id,generation=relative)
        with self.assertRaises(FileNotFoundError):
            self.service.detail(str(uuid.uuid4()))
        (self.run/'user-metadata.json').write_text('{bad')
        with self.assertRaises(ValueError): self.service.detail(self.run_id)
        self.assertEqual(self.service.list_runs()[0]['status'],'unavailable')

    def test_failed_publication_is_recorded_and_never_reused(self):
        import numpy as np
        from unittest.mock import patch
        from mde.results import DerivedStore
        from mde.run_access import write_sidecar
        from mde.storage import read_json
        store = DerivedStore(); identity = {'algorithm':'mesh-fixture','version':'1'}
        generate = lambda: {'points':np.ones((2,2,3),dtype='<f4')}
        original = store.get(self.run,identity,generate)[1]
        def fail_pointer(run, relative, value):
            if relative.endswith('current.json'): raise OSError('fixture pointer failure')
            return write_sidecar(run, relative, value)
        with patch('mde.results.write_sidecar',side_effect=fail_pointer):
            with self.assertRaises(OSError): store.get(self.run,identity,generate,force=True)
        self.assertEqual(DerivedStore().get(self.run,identity,generate)[1],original)
        failed = read_json(self.run/'derived/history.json')['events'][-1]
        self.assertEqual(failed['operation'],'failed')
        self.assertTrue((self.run/failed['target']).exists())
        self.assertEqual(len(self.service.detail(self.run_id)['derived']),1)

    def test_corrupt_derived_remains_visible_and_can_be_explicitly_removed(self):
        import numpy as np
        from mde.results import DerivedStore
        manifest = DerivedStore().get(self.run,{'algorithm':'fixture'},lambda:{'points':np.ones((2,2,3),dtype='<f4')})[1]
        (self.run/manifest['output']['path']).write_bytes(b'corrupt')
        detail = self.service.detail(self.run_id)
        self.assertEqual(len(detail['derived_errors']),1)
        target = str(Path(manifest['output']['path']).parent)
        restarted = RunManagementService(self.service.store,self.service.collect)
        restarted.delete(restarted.prepare_delete(self.run_id,generation=target),self.run_id,typed_run_id=self.run_id)
        self.assertFalse((self.run/target).exists())

    def test_retry_after_directory_removed_but_pointer_cleanup_failed(self):
        import os
        import numpy as np
        from unittest.mock import patch
        from mde.results import DerivedStore
        from mde.storage import read_json
        identity = {'algorithm':'fixture'}
        generate = lambda:{'points':np.ones((2,2,3),dtype='<f4')}
        first = DerivedStore().get(self.run,identity,generate)[1]
        second = DerivedStore().get(self.run,identity,generate,force=True)[1]
        target = str(Path(second['output']['path']).parent)
        confirmation = self.service.prepare_delete(self.run_id,generation=target)
        original = os.unlink
        def fail_pointer(name, **kwargs):
            if name == 'current.json': raise OSError('fixture pointer cleanup failure')
            return original(name, **kwargs)
        with patch('os.unlink',side_effect=fail_pointer):
            with self.assertRaises(OSError):
                self.service.delete(confirmation,self.run_id,typed_run_id=self.run_id)
        self.assertFalse((self.run/target).exists())
        self.assertEqual(DerivedStore().get(self.run,identity,generate)[1],first)
        restarted = RunManagementService(self.service.store,self.service.collect)
        retry = restarted.prepare_delete(self.run_id,generation=target)
        self.assertIsNone(retry['directory_identity'])
        restarted.delete(retry,self.run_id,typed_run_id=self.run_id)
        self.assertEqual(read_json(self.run/'derived/history.json')['events'][-1]['operation'],'deleted')


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
