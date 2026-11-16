"""Explicit official-weight preparation; never called by UI/inference discovery."""
import argparse
import json
from pathlib import Path
import shutil
import urllib.request
import uuid

from mde.storage import sha256_file


def verify(path, reference):
    if path.stat().st_size != reference['size_bytes'] or sha256_file(path) != reference['sha256']:
        raise ValueError('GeoCalib fixed checkpoint size or checksum mismatch')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    reference=json.loads(Path(__file__).with_name('task.json').read_text())['checkpoint']
    if args.output.exists():
        verify(args.output,reference)
        return
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_name('.partial-'+uuid.uuid4().hex)
    try:
        with urllib.request.urlopen(reference['url'],timeout=120) as source, temporary.open('xb') as target:
            shutil.copyfileobj(source,target)
        verify(temporary,reference)
        # No replacement of a concurrently published file.
        import os
        os.link(temporary,args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print('Verified official GeoCalib pinhole checkpoint:',args.output)


if __name__=='__main__':
    main()
