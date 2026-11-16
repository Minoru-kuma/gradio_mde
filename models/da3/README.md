# DA3-SMALL plugin — Phase 03.2

Status: **03.2 acceptance PASS** is retained. Phase 03.7 adds optional native pixel K; acceptance is tracked in Phase 03.
This variant integrates single-view **relative z-depth**, float32, explicit CPU only.
GPU / other native optional outputs / multi-view execution remain unsupported. Derived Points are separate from native outputs.
Actual pinned network size: 34,299,463 unique parameters (measured by summing native parameters).

The source pin is [`3d835ec1a5802d64a8b8b15f817a1ab54809bfe4`](https://github.com/ByteDance-Seed/Depth-Anything-3/tree/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4).
Code and inherited DINOv2 components use Apache-2.0; the
[fixed model card](https://huggingface.co/depth-anything/DA3-SMALL/tree/e08cab65ca0ec38e7826075418411ab90cab4da3)
also declares Apache-2.0. Weights are not redistributed in this repository.
Checkpoint revision, byte counts and SHA-256 for both files are in [manifest.json](manifest.json).

Use an independent Conda prefix. Conda owns Python / bootstrap; pip owns inference dependencies.
The CPU wheels provide no CUDA execution, and no fallback is performed. Existing MoGe and UI environments are not modified.

```bash
CONDA_PKGS_DIRS="$PWD/.local/conda-pkgs" PIP_CACHE_DIR="$PWD/.local/pip-cache" \
  conda env create --prefix "$PWD/.local/envs/mde-da3" -f models/da3/environment.yml
PIP_CACHE_DIR="$PWD/.local/pip-cache" conda run --no-capture-output --prefix .local/envs/mde-da3 \
  python -m pip install --no-deps \
  'git+https://github.com/ByteDance-Seed/Depth-Anything-3.git@3d835ec1a5802d64a8b8b15f817a1ab54809bfe4'
conda run --no-capture-output --prefix .local/envs/mde-da3 \
  python -m models.da3.prepare_checkpoint --output .local/weights/da3-small --cache-dir .local/huggingface
PYTHONPATH=src python -m mde.cli run --model da3 --device cpu \
  --input tests/assets/sample.png --conda-prefix .local/envs/mde-da3 \
  --checkpoint .local/weights/da3-small --timeout-seconds 300
```

Inference requires a local directory containing `config.json` and `model.safetensors`.
It verifies both files before loading; it never downloads or installs dependencies.
Unknown variants and unsupported requests are rejected through shared metadata validation.
Default `process_res=252` is divisible by native patch size 14; `504` is also declared but not yet tested.
The CLI's CUDA default is rejected for this CPU-only variant; choose `--device cpu` explicitly.

The native integration reuses the pinned config constructor, `InputProcessor`, `DepthAnything3Net` and
`OutputProcessor`. It compares the Hub config against the pinned source config and loads weights strictly,
preserving the high-level wrapper's `model.` prefix. The official Safetensors `load_model(strict=True)`
resolves the native shared LayerNorm parameter aliases; genuinely missing / unexpected weights fail.
See [Safetensors shared tensors](https://huggingface.co/docs/safetensors/torch_shared_tensors).
The source is not patched.
The [high-level API](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/api.py)
imports exporters / pose alignment and forces autocast; the native path keeps the explicit float32 contract
and avoids unrelated dependencies. This environment supports this native inference path; upstream CLI,
exporters, 3DGS and `pip check` for the full upstream package are not claimed to work.

The [pinned GLB exporter](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/utils/export/glb.py)
uses integer pixel coordinates, inverse K and depth multiplication in an OpenCV camera frame.
This establishes z-depth semantics. SMALL does not establish metric scale, so depth uses arbitrary units.
The adapter saves native depth values without normalization or resampling, and supplies no K or Points.
Native resizing is recorded; RGB identity mapping is not asserted. Existing depth-only serialization is reused.

## Validation evidence — 2026-11-11

Run `541dcd67-8153-48b1-a1d4-9063b79e1435` completed through CLI / Runner / LocalBackend /
Conda worker with nonloopback Python connections blocked. Python 3.11.14, torch 2.6.0+cpu,
torchvision 0.21.0+cpu, no CUDA runtime, CPU, native autocast disabled.
Depth is float32 `[252,252]`, all 63,504 pixels finite and positive, z-depth / relative / arbitrary.
The native output grid is retained. Accuracy and cross-model scale comparisons are not evaluated.

The final source digest matches `6f24fb9f3f5f613a5ba94ebb660e38c57ad5561ed57c9a1bbe765645bb8b0073`.
Both new Backend and new CLI processes collected twice without inference or file hash / mtime changes.
Predict ran once, unload completed, worker exit was zero, stderr was empty.
An initial strict state_dict attempt failed on shared LayerNorm aliases (Run
`aae4f709-fdaa-47de-892e-978c68e5ed51`); the native sharing and checkpoint alias metadata were checked
before using the official alias-aware loader. Five plugin contract tests pass, including shared weights
and rejection of genuinely missing tensors. The full regression suite passed: 105 tests, 100 passed and 5 opt-in browser skips (154.074 s).
Existing browser regression remains the 03.1 five-test success; DA3 browser switching is a 03.3 gate.

[requirements.lock](requirements.lock) records all installed native inference Python distributions for
Linux x86_64 / Python 3.11.14. After Conda Python / bootstrap setup, use the isolated environment's
`python -m pip install --no-deps -r models/da3/requirements.lock` to reproduce those exact versions.
The source revision is included. Full upstream extras remain outside this native inference environment.
The environment was created once from environment.yml; recreation from this lock is not yet tested.
MoGe retains its own torch 2.6.0+cu124 environment; Gradio remains in its application environment.
`process_res=504`, GPU, other platforms and native optional outputs remain untested.

## Phase 03.6 integration

The pinned variant completed explicit CPU inference through the shared Runner / Backend and its independent
worker in the three-model browser acceptance. Saved output reload and fresh Backend / CLI collect preserved
file hashes and mtimes. This does not establish GPU, other variants or full upstream tools. See
[final evidence](../../docs/phases/phase-03.md#036-integration-acceptance-evidence--2026-11-13) and the
[capability / reproduction matrix](../../docs/model-capability-matrix.md) for scope and remaining unknowns.

## Phase 03.7 native intrinsics

The fixed SMALL CameraDec returns intrinsics on the native depth grid, verified with square and nonsquare inputs.
Request --outputs depth intrinsics (or check intrinsics in the UI). Default depth-only runs remain valid and do not
save K. Native pixel values are preserved without half-pixel translation; the pinned official GLB exporter uses
integer meshgrid. Points / pose / confidence remain unsupported as native exported outputs.
OpenCV input-to-depth resize is now recorded as an integer-pixel affine including 0.5*s-0.5 offsets.
[Reconstruction](../../docs/depth-reconstruction-spec.md) uses known K, then saved native K, then a configured
GeoCalib task; all resulting Points / 2.5D mesh are derived, with relative scale and arbitrary units unchanged.

Native K evidence at source revision 3d835ec1a5802d64a8b8b15f817a1ab54809bfe4:
[SMALL config](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/configs/da3-small.yaml),
[CameraDec invocation](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/model/da3.py),
[pixel K construction](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/model/utils/transform.py),
[integer-grid backprojection](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/3d835ec1a5802d64a8b8b15f817a1ab54809bfe4/src/depth_anything_3/utils/export/glb.py).
The prior 03.2 depth-only acceptance remains the historical baseline.
