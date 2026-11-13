"""Run management primitives; terminal validation is delegated to the backend.

Viewer and management operations share a per-Run coordination protocol.
All destructive operations require an explicit, revalidated confirmation.
"""
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .run_access import run_lock, write_sidecar

from .contracts import (ATTEMPT_ID, ArtifactIntegrityError, JobHandle,
                        ResultNotReady, UnknownJob, UnsupportedOperation)
from .storage import contained_path, run_path


class RunManagementService:
    def __init__(self, store, collect, *, camera_estimator=None):
        self.store, self.collect = store, collect
        self.camera_estimator = camera_estimator

    def _lock(self, run_id):
        run = run_path(self.store.root, run_id)
        if (Path(self.store.root) / run_id).is_symlink():
            raise ArtifactIntegrityError('Symlink Run is forbidden')
        return run_lock(run)

    def _metadata(self, run):
        if (run / 'user-metadata.json').is_symlink():
            raise ArtifactIntegrityError('Symlink metadata is forbidden')
        path = contained_path(run, 'user-metadata.json')
        if not path.exists():
            return {'schema_version': '1.0', 'revision': 0, 'display_name': '',
                    'notes': '', 'archived': False, 'updated_at': None}
        data = self._read_json(run, path.relative_to(run).as_posix())
        if (set(data) != {'schema_version', 'revision', 'display_name', 'notes', 'archived', 'updated_at'}
                or data['schema_version'] != '1.0' or type(data['revision']) is not int
                or data['revision'] < 1 or type(data['archived']) is not bool
                or not isinstance(data['display_name'], str) or not isinstance(data['notes'], str)
                or not isinstance(data['updated_at'], str)):
            raise ArtifactIntegrityError('Invalid user metadata')
        return data

    def detail(self, run_id, *, include_derived=True):
        with self._lock(run_id):
            run = run_path(self.store.root, run_id)
            saved = self._read_json(run, f'attempts/{ATTEMPT_ID}/handle.json')
            handle = JobHandle(**{key: saved[key] for key in JobHandle.__dataclass_fields__ if key in saved})
            if handle.run_id != run_id:
                raise ArtifactIntegrityError('Run / handle identity mismatch')
            result = self.collect(handle).to_dict()
            if result.get('status') not in ('COMPLETED', 'FAILED', 'CANCELLED'):
                raise ResultNotReady(run_id)
            history_path = self._safe_file(run, 'derived/history.json')
            history = self._read_json(run, history_path.relative_to(run).as_posix()) if history_path.exists() else {'schema_version': '1.0', 'events': []}
            excluded = {e.get('target') for e in history['events'] if e.get('operation') in ('delete_requested', 'deleted', 'failed')}
            committed = {e.get('manifest', {}).get('generation_id') for e in history['events'] if e.get('operation') in ('generate', 'regenerate')}
            generations, derived_errors = [], []
            derived = run / 'derived'
            if derived.is_symlink():
                raise ArtifactIntegrityError('Symlink derived directory')
            if derived.exists() and include_derived:
                from .storage import validate_artifact
                for path in sorted(derived.glob('*/*/manifest.json')):
                    if path.parent.name.startswith('.partial-') or path.parent.relative_to(run).as_posix() in excluded:
                        continue
                    try:
                        manifest = self._read_json(run, path.relative_to(run).as_posix())
                        if manifest.get('publication_protocol') == 'history-commit-v1' and manifest.get('generation_id') not in committed:
                            continue
                        import hashlib, json
                        identity_key = hashlib.sha256(json.dumps(manifest['identity'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                        if (manifest.get('schema_version') != '1.0' or manifest.get('origin') != 'derived'
                                or manifest.get('key') != path.parent.parent.name or identity_key != manifest.get('key')
                                or manifest.get('generation_id') != path.parent.name):
                            raise ArtifactIntegrityError('Invalid generation identity')
                        if manifest.get('publication_protocol') == 'history-commit-v1' and not any(
                                e.get('operation') in ('generate', 'regenerate') and e.get('manifest') == manifest for e in history['events']):
                            raise ArtifactIntegrityError('Generation commit mismatch')
                        ref = manifest['output']
                        if ref['path'] != (path.parent / 'geometry.npz').relative_to(run).as_posix():
                            raise ArtifactIntegrityError('Invalid generation output reference')
                        self._safe_file(run, ref['path'])
                        validate_artifact(run, ref)
                        generations.append(manifest)
                    except (ValueError, OSError, KeyError, TypeError) as error:
                        derived_errors.append({'path': path.parent.relative_to(run).as_posix(), 'error': str(error)})
            return {'run_id': run_id, 'job': self._read_json(run, 'job.json'),
                    'result': result, 'user_metadata': self._metadata(run),
                    'derived': generations, 'derived_errors': derived_errors, 'history': history}

    def list_runs(self, include_archived=False):
        root = Path(self.store.root)
        if not root.exists():
            return []
        entries = []
        for item in sorted(root.iterdir()):
            try:
                canonical_id = str(uuid.UUID(item.name)) == item.name
            except ValueError:
                continue
            if item.is_symlink() or not item.is_dir() or not canonical_id:
                continue
            try:
                detail = self.detail(item.name)
                if include_archived or not detail['user_metadata']['archived']:
                    entries.append({'run_id': item.name, 'status': detail['result']['status'],
                                    'user_metadata': detail['user_metadata']})
            except (ValueError, OSError, KeyError, TypeError, ResultNotReady, UnknownJob, UnsupportedOperation):
                # Keep damaged or active entries visible without treating them as terminal.
                entries.append({'run_id': item.name, 'status': 'unavailable'})
        return entries

    def update_metadata(self, run_id, revision, *, display_name, notes, archived):
        if (type(revision) is not int or not isinstance(display_name, str) or len(display_name) > 256
                or not isinstance(notes, str) or len(notes) > 16384 or type(archived) is not bool):
            raise ValueError('Invalid metadata')
        with self._lock(run_id):
            detail = self.detail(run_id)
            previous = detail['user_metadata']
            if previous['revision'] != revision:
                raise ValueError('Stale metadata revision')
            updated = {'schema_version': '1.0', 'revision': revision + 1, 'display_name': display_name,
                       'notes': notes, 'archived': archived,
                       'updated_at': datetime.now(timezone.utc).isoformat()}
            write_sidecar(run_path(self.store.root, run_id), 'user-metadata.json', updated)
            return updated

    def regenerate_derived(self, run_id):
        from .results import ResultsService
        with self._lock(run_id):
            return ResultsService(self.store, self.collect, camera_estimator=self.camera_estimator).view(run_id, 'Mesh', regenerate=True)['derived']

    def _safe_file(self, run, relative):
        """Reject every symlink component, including links within the same Run."""
        contained_path(run, relative)
        target = run
        for part in Path(relative).parts:
            target /= part
            if target.is_symlink():
                raise ArtifactIntegrityError('Symlinks are forbidden')
        return contained_path(run, relative)

    def _read_json(self, run, relative):
        import json
        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ArtifactIntegrityError('Duplicate JSON key')
                value[key] = item
            return value
        def invalid(value):
            raise ArtifactIntegrityError('Nonfinite JSON scalar')
        value = json.loads(self._read_file(run, relative), object_pairs_hook=pairs, parse_constant=invalid)
        if not isinstance(value, dict):
            raise ArtifactIntegrityError('JSON record must be an object')
        return value

    def _open_directory(self, root, relative):
        import os
        contained_path(root, relative)
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in Path(relative).parts:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory); directory = child
            return directory
        except Exception:
            os.close(directory)
            raise

    def _read_file(self, run, relative):
        """Walk via directory descriptors so a replacement symlink is never followed."""
        import os
        import stat
        self._safe_file(run, relative)
        parts = Path(relative).parts
        directory = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory); directory = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ArtifactIntegrityError('Nonregular file')
                return stream.read(256 * 1024 * 1024 + 1)
        finally:
            os.close(directory)

    def export(self, run_id):
        """Return a self-contained ZIP in memory; no temporary exports to retain."""
        import hashlib
        import io
        import json
        import zipfile
        from .storage import sha256_file
        with self._lock(run_id):
            detail = self.detail(run_id)
            if detail['derived_errors']:
                raise ArtifactIntegrityError('Export unavailable: incomplete or corrupt derived generation')
            run = run_path(self.store.root, run_id)
            refs = list(detail['result'].get('artifacts', []))
            for source in detail['job'].get('inputs', []):
                refs.append(source)
                if 'source' in source:
                    refs.append(source['source'])
            names = {'job.json', f'attempts/{ATTEMPT_ID}/job.json', f'attempts/{ATTEMPT_ID}/job-result.json'}
            expected = {}
            for ref in refs:
                names.add(ref['path']); expected[ref['path']] = ref['sha256']
            for generation in detail['derived']:
                ref = generation['output']
                names.add(str(Path(ref['path']).parent / 'manifest.json'))
                names.add(ref['path']); expected[ref['path']] = ref['sha256']
            stream = io.BytesIO(); manifest = []
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                total = 0
                for relative in sorted(names):
                    path = self._safe_file(run, relative)
                    data = self._read_file(run, relative)
                    total += len(data)
                    if total > 256 * 1024 * 1024:
                        raise ValueError('Export exceeds 256 MiB')
                    digest = hashlib.sha256(data).hexdigest()
                    if relative in expected and digest != expected[relative]:
                        raise ArtifactIntegrityError('Export digest mismatch')
                    archive.writestr(relative, data)
                    manifest.append({'path': relative, 'sha256': digest, 'size_bytes': len(data)})
                archive.writestr('derived-history.json', json.dumps(detail['history']))
                archive.writestr('export-manifest.json', json.dumps({'schema_version': '1.0',
                    'run_id': run_id, 'files': manifest, 'user_metadata': detail['user_metadata']}))
            return stream.getvalue()

    def _inventory(self, run):
        import hashlib
        result = {}
        for path in sorted(run.rglob('*')):
            path = self._safe_file(run, path.relative_to(run).as_posix())
            if path.is_file():
                data = self._read_file(run, path.relative_to(run).as_posix())
                if len(data) > 256 * 1024 * 1024:
                    raise ValueError('Management inventory exceeds 256 MiB per file')
                result[path.relative_to(run).as_posix()] = hashlib.sha256(data).hexdigest()
            elif not path.is_dir():
                raise ArtifactIntegrityError('Nonregular Run entry')
        return result

    def _generation_manifest(self, run, generation):
        path = self._safe_file(run, generation + '/manifest.json')
        if path.exists():
            return self._read_json(run, path.relative_to(run).as_posix())
        history = self._read_json(run, 'derived/history.json')
        for event in reversed(history['events']):
            if event.get('target') == generation and event.get('operation') == 'delete_requested':
                return event['manifest']
        raise ArtifactIntegrityError('Missing generation manifest and deletion record')

    def prepare_delete(self, run_id, *, generation=None):
        """A reviewable snapshot, never permission to delete a different target."""
        with self._lock(run_id):
            self.detail(run_id, include_derived=False)
            run = run_path(self.store.root, run_id)
            if generation is not None:
                parts = Path(generation).parts
                if len(parts) != 3 or parts[0] != 'derived':
                    raise ValueError('Expected derived/key/generation')
                target = self._safe_file(run, generation)
                self._generation_manifest(run, generation)
                if target.exists() and not target.is_dir():
                    raise ValueError('Invalid generation directory')
            target = self._safe_file(run, generation) if generation else run
            target_identity = target.stat() if target.exists() else None
            return {'run_id': run_id, 'generation': generation,
                    'directory_identity': [target_identity.st_dev, target_identity.st_ino] if target_identity else None,
                    'inventory': self._inventory(run),
                    'scope': 'derived generation only' if generation else 'entire Run including raw and history'}

    def delete(self, confirmation, selected_run_id, *, typed_run_id):
        import os
        import shutil
        if (not isinstance(confirmation, dict) or confirmation.get('run_id') != selected_run_id
                or typed_run_id != selected_run_id):
            raise ValueError('Explicit confirmation for selected Run required')
        with self._lock(selected_run_id):
            current = self.prepare_delete(selected_run_id, generation=confirmation.get('generation'))
            if current != confirmation:
                raise ValueError('Stale deletion confirmation; review again')
            if not shutil.rmtree.avoids_symlink_attacks:
                raise RuntimeError('Secure recursive deletion unavailable')
            run = run_path(self.store.root, selected_run_id)
            generation = confirmation.get('generation')
            if generation:
                # Keep original identity and a tombstone even if removal fails.
                manifest = self._generation_manifest(run, generation)
                history_path = self._safe_file(run, 'derived/history.json')
                history = self._read_json(run, history_path.relative_to(run).as_posix()) if history_path.exists() else {'schema_version': '1.0', 'events': []}
                history['events'].append({'operation': 'delete_requested', 'target': generation, 'manifest': manifest})
                write_sidecar(run, 'derived/history.json', history)
                parent_fd = self._open_directory(run, str(Path(generation).parent))
                try:
                    try:
                        target_stat = os.stat(Path(generation).name, dir_fd=parent_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        target_stat = None
                    actual = [target_stat.st_dev, target_stat.st_ino] if target_stat else None
                    if actual != confirmation['directory_identity']:
                        raise ArtifactIntegrityError('Generation directory changed after review')
                    if target_stat is not None:
                        shutil.rmtree(Path(generation).name, dir_fd=parent_fd)
                    pointer = self._safe_file(run, str(Path(generation).parent / 'current.json'))
                    if pointer.exists() and self._read_json(run, pointer.relative_to(run).as_posix()).get('generation_id') == Path(generation).name:
                        os.unlink('current.json', dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
                history['events'].append({'operation': 'deleted', 'target': generation, 'manifest': manifest})
                write_sidecar(run, 'derived/history.json', history)
            else:
                # First hide atomically; failed removal stays quarantined for diagnosis.
                root_fd = os.open(self.store.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                quarantine_fd = None
                name = selected_run_id + '-' + uuid.uuid4().hex
                try:
                    try:
                        os.mkdir('.management-quarantine', dir_fd=root_fd)
                    except FileExistsError:
                        pass
                    quarantine_fd = os.open('.management-quarantine', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
                    write_sidecar(self.store.root, '.management-quarantine/' + name + '.json',
                        {'schema_version': '1.0', 'run_id': selected_run_id, 'quarantine_name': name,
                         'terminal_validated': True, 'confirmation': confirmation})
                    original_inode = confirmation['directory_identity'][1]
                    os.rename(selected_run_id, name, src_dir_fd=root_fd, dst_dir_fd=quarantine_fd)
                    import stat
                    moved = os.stat(name, dir_fd=quarantine_fd, follow_symlinks=False)
                    if not stat.S_ISDIR(moved.st_mode) or moved.st_ino != original_inode:
                        raise ArtifactIntegrityError('Run changed during deletion; quarantined for review')
                    try:
                        shutil.rmtree(name, dir_fd=quarantine_fd)
                    except Exception as error:
                        raise RuntimeError(f'Deletion incomplete; quarantine entry {name}: {error}') from error
                finally:
                    if quarantine_fd is not None:
                        os.close(quarantine_fd)
                    os.close(root_fd)
            return {'deleted': selected_run_id, 'generation': generation}


    def prepare_retry(self, quarantine_name):
        """Review only a previously terminal-validated, quarantined Run deletion."""
        if (not isinstance(quarantine_name, str) or len(quarantine_name) != 69
                or quarantine_name[36] != '-' or str(uuid.UUID(quarantine_name[:36])) != quarantine_name[:36]
                or any(c not in '0123456789abcdef' for c in quarantine_name[37:])):
            raise ValueError('Invalid quarantine entry')
        run_id = quarantine_name[:36]
        with self._lock(run_id):
            root = Path(self.store.root)
            record = self._read_json(root, '.management-quarantine/' + quarantine_name + '.json')
            if (record.get('schema_version') != '1.0' or record.get('run_id') != run_id
                    or record.get('quarantine_name') != quarantine_name or record.get('terminal_validated') is not True):
                raise ArtifactIntegrityError('Invalid deletion record')
            folder = self._safe_file(root, '.management-quarantine/' + quarantine_name)
            if not folder.is_dir() or (root / run_id).exists():
                raise ValueError('Quarantine entry unavailable or Run ID reused')
            identity = folder.stat()
            if [identity.st_dev, identity.st_ino] != record['confirmation'].get('directory_identity'):
                raise ArtifactIntegrityError('Quarantined directory identity changed')
            return {'run_id': run_id, 'quarantine_name': quarantine_name,
                    'directory_identity': [identity.st_dev, identity.st_ino],
                    'inventory': self._inventory(folder), 'record': record}

    def retry_delete(self, confirmation, *, typed_run_id):
        import os
        import shutil
        if not confirmation or typed_run_id != confirmation.get('run_id'):
            raise ValueError('Type exact Run ID to confirm retry')
        with self._lock(typed_run_id):
            current = self.prepare_retry(confirmation['quarantine_name'])
            if current != confirmation:
                raise ValueError('Stale retry confirmation')
            if not shutil.rmtree.avoids_symlink_attacks:
                raise RuntimeError('Secure deletion unavailable')
            directory = os.open(Path(self.store.root) / '.management-quarantine',
                                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                import stat
                entry = os.stat(confirmation['quarantine_name'], dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISDIR(entry.st_mode) or [entry.st_dev, entry.st_ino] != confirmation['directory_identity']:
                    raise ArtifactIntegrityError('Retry target changed after review')
                shutil.rmtree(confirmation['quarantine_name'], dir_fd=directory)
            finally:
                os.close(directory)
            return {'deleted_quarantine': confirmation['quarantine_name']}
