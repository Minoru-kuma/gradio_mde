# UniK3D independent adapter contract — adoption pending

This directory contains independently authored lifecycle and numeric conversion code. It contains no
upstream implementation, checkpoint loader, downloaded weights, environment definition or production
manifest. UniK3D is not available as a runnable model in CLI / Gradio discovery.
The [investigation](../../docs/unik3d-investigation.md) preserves conflicting CC BY-NC / CC BY-NC-SA
source labels and unresolved checkpoint applicability. Real checkpoint acquisition, use and redistribution
remain on hold. Missing information alone does not stop independent synthetic contract work.

`UniK3DAdapter.load()` without an injected fixture factory reports that hold before path access or
model / numeric imports. An injected runtime must be independently authored, accept HWC uint8 RGB,
return native-layout NumPy arrays and expose `close()`. Even with injection a non-null checkpoint
is rejected before the factory runs. This seam is for synthetic contracts; an upstream torch bridge,
native preprocessing / precision policy and verified source / checkpoint loading are not implemented.
Only explicit CPU / float32 is accepted for the synthetic path; no actual UniK3D CPU support is claimed.

| Mapping | Current synthetic contract |
| --- | --- |
| Input | One HWC RGB uint8 image, no adopted inference parameters |
| Native distance | float32 `[1,1,H,W]` → canonical depth `[H,W]`, `ray_distance` |
| Native points | float32 `[1,3,H,W]` → optional `[H,W,3]`, no backprojection / resampling |
| Native depth, if present | float32 `[1,1,H,W]`, checked against points.z, not used as canonical range |
| Consistency | distance equals norm(points), rtol 1e-4 / atol 1e-5 on valid pixels |
| Validity | finite positive distance and finite points; invalid values become NaN without inventing a model mask |
| Scale / units | `unknown` / `unknown`; synthetic fixtures do not verify real metric scale |
| Camera frame / grid | Fixture explicitly assumes OpenCV camera frame and original image grid; real outputs remain unverified |
| Other outputs | K / normals / mask / rays / confidence / pose absent; requests outside depth / points rejected |
| Storage | Existing `01A-depth-only` and `02A-geometry-v1`; no new schema or profile |

The fixed upstream infer source defines distance as norm(points) and depth as points.z; see the
[fixed model source](https://github.com/lpiccinelli-eth/UniK3D/blob/29f7862f3c3ee79c53ef0153dfc901ce511df575/unik3d/models/unik3d.py).
Selecting distance avoids discarding directions with zero or negative z. Synthetic tests explicitly
include these directions, bad layouts / dtypes, native distance / z inconsistency and invalid values.
Output arrays are owned contiguous copies; native arrays are not modified.

Verification command (existing test environments only, no UniK3D install or checkpoint):

```sh
OMP_NUM_THREADS=2 PYTHONPATH=src .local/envs/mde-ui/bin/python -m unittest tests.test_unik3d_plugin -v
```

Numeric tests run in a separate NumPy process to preserve the control import boundary. Worker tests
use an isolated synthetic registry and the existing test Conda environment, verify saved points with
the stdlib reader and check repeated collection leaves hashes / mtimes unchanged. They do not count
as real UniK3D E2E, independent UniK3D environment validation or Phase 03.4 acceptance.
