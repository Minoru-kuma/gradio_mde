"""Explicit Hub provisioning; workers require the two already verified local files."""
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
    checkpoint = json.loads(Path(__file__).with_name('manifest.json').read_text())['variants'][0]['checkpoint']
    if args.output.exists():
        verify_checkpoint(args.output, checkpoint)
        print('Existing DA3 checkpoint verified; unchanged')
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='da3-prepare-', dir=args.output.parent) as temporary:
        for reference in (checkpoint, checkpoint['config']):
            path = hf_hub_download(checkpoint['repo_id'], reference['filename'], revision=checkpoint['revision'],
                                   cache_dir=args.cache_dir)
            shutil.copyfile(path, Path(temporary) / reference['filename'])
        verify_checkpoint(temporary, checkpoint)
        # Publish the complete directory only after both digests are verified.
        Path(temporary).rename(args.output)
    print(json.dumps({'checkpoint': checkpoint, 'directory': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
