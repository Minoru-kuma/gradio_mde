"""Single-process Run coordination shared by viewer and management services."""
from functools import wraps
from pathlib import Path
import threading

_guard = threading.Lock()
_locks = {}


def run_lock(run):
    key = str(Path(run).absolute())
    with _guard:
        return _locks.setdefault(key, threading.RLock())


def locked_view(method):
    @wraps(method)
    def wrapped(self, run_id, *args, **kwargs):
        from .storage import run_path
        with run_lock(run_path(self.store.root, run_id)):
            return method(self, run_id, *args, **kwargs)
    return wrapped


def write_sidecar(run, relative, value):
    """Atomic sidecar publication anchored to directories opened without symlinks."""
    import json
    import os
    import uuid
    from .storage import contained_path
    contained_path(run, relative)
    parts = Path(relative).parts
    directory = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.pending-' + uuid.uuid4().hex
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory); directory = child
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        os.close(directory)
