"""Explicit fixed checkpoint acquisition, separate from inference and distribution."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from .checkpoint import verify_checkpoint


def main():
    from huggingface_hub import hf_hub_download
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path)
    args = parser.parse_args()
    reference = json.loads(Path(__file__).with_name('manifest.json').read_text())['variants'][0]['checkpoint']
    if args.output.exists():
        verify_checkpoint(args.output, reference)
        print('Existing UniK3D checkpoint verified; unchanged')
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unik3d-prepare-', dir=args.output.parent) as temporary:
        for file in (reference, reference['config']):
            source = hf_hub_download(reference['repo_id'], file['filename'], revision=reference['revision'],
                                      cache_dir=args.cache_dir)
            shutil.copyfile(source, Path(temporary) / file['filename'])
        verify_checkpoint(temporary, reference)
        Path(temporary).rename(args.output)
    print(json.dumps({'checkpoint': reference, 'directory': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
