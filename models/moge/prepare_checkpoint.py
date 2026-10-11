"""Explicit provisioning; inference jobs only load a pinned local/cached file."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    from huggingface_hub import hf_hub_download
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())
    checkpoint = manifest["variants"][0]["checkpoint"]
    path = Path(hf_hub_download(checkpoint["repo_id"], checkpoint["filename"],
                    revision=checkpoint["revision"], cache_dir=args.cache_dir))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != checkpoint["sha256"]:
        raise ValueError("Downloaded checkpoint hash mismatch")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, args.output)
    print(json.dumps({"checkpoint": checkpoint, "path": str(args.output), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
