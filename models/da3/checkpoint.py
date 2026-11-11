"""Pinned local checkpoint verification; no Hub / framework / storage imports."""
import hashlib
import json
from pathlib import Path


def verify_checkpoint(directory, checkpoint):
    if directory is None:
        raise ValueError('DA3 requires a prepared local checkpoint directory; inference never downloads')
    directory = Path(directory)
    for reference in (checkpoint, checkpoint['config']):
        path = directory / reference['filename']
        if not path.is_file() or path.stat().st_size != reference['size_bytes']:
            raise ValueError(f'DA3 checkpoint file missing or wrong size: {reference["filename"]}')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != reference['sha256']:
            raise ValueError(f'DA3 checkpoint SHA-256 mismatch: {reference["filename"]}')
    return directory, json.loads((directory / checkpoint['config']['filename']).read_text())
