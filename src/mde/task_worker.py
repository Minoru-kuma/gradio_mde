"""Small auxiliary JSON task protocol; imports the selected provider only here."""
import argparse
import importlib
import os
import platform
from pathlib import Path
import sys
import time

from .storage import read_json, sha256_file, write_json


def execute(request):
    if request.get('schema_version') != '1.0' or request.get('device') != 'cpu':
        raise ValueError('Auxiliary protocol requires explicit CPU / schema 1.0')
    if os.environ.get('MDE_CONTROL_PREFIX') == sys.prefix:
        raise ValueError('Auxiliary worker must run in an independent environment')
    image = Path(request['image_path'])
    if sha256_file(image) != request['image_sha256']:
        raise ValueError('Auxiliary input checksum mismatch')
    module, separator, name = request['entrypoint'].partition(':')
    if not separator or not all(part.isidentifier() for part in module.split('.')) or not name.isidentifier():
        raise ValueError('Invalid auxiliary provider entrypoint')
    result = getattr(importlib.import_module(module), name)(request)
    if sha256_file(image) != request['image_sha256']:
        raise ValueError('Auxiliary input changed during execution')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    try:
        request = read_json(args.request)
        started = time.monotonic()
        output = execute(request)
        torch = sys.modules.get('torch')
        execution = {'python_version': platform.python_version(), 'python_prefix': sys.prefix,
                     'device': request['device'], 'seed': request.get('seed'),
                     'task_seconds': time.monotonic()-started,
                     'torch_version': str(torch.__version__) if torch is not None else None}
        if 'environment' in request:
            from .runtime import environment_fingerprint
            execution['environment_fingerprint'] = environment_fingerprint(request['environment'])
        output = {**output, 'execution': execution}
        write_json(args.result, {'schema_version': '1.0', 'status': 'COMPLETED', 'output': output})
        return 0
    except Exception as error:
        write_json(args.result, {'schema_version': '1.0', 'status': 'FAILED', 'error': str(error)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
