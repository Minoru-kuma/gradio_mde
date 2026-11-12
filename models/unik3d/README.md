# UniK3D Small native CPU plugin — Phase 03.4

Native depth-only and depth + Points CLI E2E have succeeded; full 03.4 acceptance is recorded in
[Phase 03](../../docs/phases/phase-03.md). Only the pinned Small variant / explicit CPU / float32 /
resolution_level=0 are experimentally verified here. GPU, other variants / resolutions, camera inputs,
metric accuracy, multi-view and full upstream training / evaluation tools are unverified.

## License facts and scoped research decision

Source revision: [`29f7862f3c3ee79c53ef0153dfc901ce511df575`](https://github.com/lpiccinelli-eth/UniK3D/tree/29f7862f3c3ee79c53ef0153dfc901ce511df575).
Candidate checkpoint: [`lpiccinelli/unik3d-vits` at `80a99bfeb8d983ca6af27125fd83c88b891e75ad`](https://huggingface.co/lpiccinelli/unik3d-vits/tree/80a99bfeb8d983ca6af27125fd83c88b891e75ad).
Source LICENSE / headers say CC BY-NC-SA 4.0, while README / package metadata say CC BY-NC 4.0.
The pinned checkpoint's applicable conditions remain unconfirmed; `weights_license` is null, not guessed.

After the [recorded assessment and user decision](../../docs/unik3d-investigation.md#scoped-user-decision--acquisition-and-local-research-use),
fixed Small acquisition and noncommercial local CPU research use proceeded with uncertainty recorded.
This is an operational research decision, not a finding that the rights holder granted a license.
Weight redistribution, public-package bundling, public demos and commercial use are outside that decision.
The [distribution policy](../../docs/distribution-policy.md) distributes the platform / self-authored adapter,
with users preparing external model source and weights separately from official sources. No source or weights
are bundled here. The earlier stop and synthetic-only implementation remain in the investigation history.
Direct author contact is not a universal prerequisite and no inquiry has been sent.

## Separate environment and explicit preparation

Use the independent environment definition [environment.yml](environment.yml). Conda provides Python 3.11.14
and bootstrap; pip provides torch 2.6.0+cpu / torchvision 0.21.0+cpu / NumPy 2.2.2 and the declared native dependencies.
Install the fixed official source separately, without its full dependency set:

```sh
.local/envs/mde-unik3d/bin/python -m pip install --no-deps --no-build-isolation \
  'git+https://github.com/lpiccinelli-eth/UniK3D@29f7862f3c3ee79c53ef0153dfc901ce511df575'
PYTHONPATH=src .local/envs/mde-unik3d/bin/python -m models.unik3d.prepare_checkpoint \
  --output .local/weights/unik3d-small --cache-dir .local/huggingface
```

Preparation downloads the two pinned files from the official Hub, checks size and SHA-256, then publishes
one complete local directory. Existing directories are verified without overwriting them. See
[manifest.json](manifest.json) for file identities. Both actual local file digests matched the recorded declarations.
`load()` checks those local files, installed source revision, strict safetensors state loading and explicit
CPU-only torch / float32. It never downloads; the native encoder's `pretrained=null` disables its separate
DINO checkpoint acquisition. The default worker / resolver / backend owns execution as for other models.

Native imports require wandb and matplotlib through `utils/__init__.py`; no tracking is initialized.
KNN evaluation warns that its extension is absent, and upstream decorators warn about disabled CUDA autocast.
Actual inference uses CPU and float32 with native autocast disabled. Gradio / xformers / triton are not installed;
the official CPU attention path uses PyTorch SDPA. This is a tested native inference subset, not a claim
that full upstream extras, training tools or full-package `pip check` succeed.
[requirements.lock](requirements.lock) captures installed native Python distributions. Recreating this new
lock in another clean prefix has not yet been tested. Existing MoGe / DA3 / UI environments were not changed.

## Geometry and serialization

| Native output | Mapping |
| --- | --- |
| distance `[1,1,H,W]` | canonical depth `[H,W]`, `ray_distance`, not native z-depth |
| points `[1,3,H,W]` | optional `[H,W,3]`, singleton batch removal and CHW to HWC only |
| depth `[1,1,H,W]` | checked against points.z; not substituted for range |
| scale / units | preserved native numeric values, `unknown` / `unknown`; no calibrated metric-unit claim |
| validity | finite positive distance AND finite points; invalid values become NaN without inventing a native model mask |
| camera / grid | OpenCV camera frame; native preprocessing and original-grid postprocessing are recorded |
| other outputs | K / normals / native mask / rays / confidence / pose not exported; unsupported requests rejected |
| profiles | existing `01A-depth-only` / `02A-geometry-v1`; no new numeric schema |

The fixed `infer` defines distance=norm(points) and depth=points.z. Selecting distance retains non-pinhole
directions with zero or negative z. Conversion checks use rtol 1e-4 / atol 1e-5. No K synthesis, backprojection,
scale adjustment or extra resampling occurs. Official camera helpers establish x-right / y-down / z-forward;
a synthetic axis fixture checks that convention, separately from actual model Points. Native preprocessing
normalizes RGB, pads aspect ratio, resizes to the selected pixel budget, then postprocesses to the original grid.
The 256×256 sample at resolution_level=0 uses a 448×448 native input, with no padding.

The fixture runtime seam remains checkpoint-free and independent of upstream code. Numeric / lifecycle /
checkpoint / fake subprocess tests include negative-z directions and invalid outputs. Real tensor transfers
are tested using a fake torch model as well as actual native E2E.

## CPU use and evidence

```sh
OMP_NUM_THREADS=2 PYTHONPATH=src python -m mde.cli run --model unik3d \
  --input tests/assets/sample.png --device cpu --outputs depth points \
  --checkpoint .local/weights/unik3d-small --conda-prefix .local/envs/mde-unik3d
```

Depth-only Run `2f40b740-11d1-4bdb-9b7a-e287bbeed832` and Points Run
`87615672-90ef-44cb-9f3c-9b4239372223` completed with float32 256×256 range, all 65,536 pixels valid.
Saved depth and Points matched a separate direct native invocation exactly. Each Run collected twice in new
CLI processes without inference / hash / mtime changes. Python nonloopback socket guards were active and
recorded no external connection attempts. The sample had no negative-z pixels; synthetic fixtures cover them.
Actual accuracy / metric scale, GPU and browser integration for this new plugin are not established by these runs.
