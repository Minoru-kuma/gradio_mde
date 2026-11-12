# UniK3D adoption investigation — Phase 03.4

Status: **independent contract implemented and synthetically verified / real-model adoption gate unmet**.
History: work resumed after 03.3, then initially stopped before installation, weight download or
implementation because the applicable license evidence was unresolved. The subsequent user instruction
revises that blanket stop: independent adapter / synthetic tests / geometry validation may proceed.
This records conflicting labels and missing information, not a conclusion that use is prohibited.
The 2026-11-12 documentation-only update applies the project-wide
[license decision policy](../AGENTS.md#license-review-and-decisions). It preserves the findings and
historical stop decisions below; it does not acquire weights, implement a runtime or execute a model.

## Scope and source identity

The candidate is UniK3D Small (`unik3d-vits`), following the Phase 03 plan to establish the third
model's depth-only CPU E2E before extending optional artifacts. The official source was inspected in
Git-ignored investigation storage. It was not copied into production code or installed in an environment.

| Item | Verified reference / declaration |
| --- | --- |
| Source | [`29f7862f3c3ee79c53ef0153dfc901ce511df575`](https://github.com/lpiccinelli-eth/UniK3D/tree/29f7862f3c3ee79c53ef0153dfc901ce511df575), latest source commit observed during this investigation |
| Candidate checkpoint | [`lpiccinelli/unik3d-vits` at `80a99bfeb8d983ca6af27125fd83c88b891e75ad`](https://huggingface.co/lpiccinelli/unik3d-vits/tree/80a99bfeb8d983ca6af27125fd83c88b891e75ad) |
| Safetensors | Hub LFS declaration: `model.safetensors`, 141,789,264 bytes, SHA-256 `9f977d058961146582931c136cf2ce44964cff3153dae7823dd1209223489bc6` |
| Config | `config.json`, retrieved from that checkpoint revision, 3,672 bytes, measured SHA-256 `5b5b7d5c6884fdb1c5f2fbf58dfaa6beb81d5ccff3dbcead4632f81eb32ad131` |
| Model card | `README.md`, retrieved from that checkpoint revision, 390 bytes, measured SHA-256 `0d65739e516d91cd2eb8252f8833ab2b9a1e9b6a1e09a9cacd4e79e68f74848d` |

The safetensors body was **not downloaded**, so its digest is a published declaration, not a measured
local verification. The config and model card are read-only research artifacts, not an adopted plugin.

## License evidence and unresolved applicability

| Primary source | Observation |
| --- | --- |
| [Fixed repository LICENSE](https://github.com/lpiccinelli-eth/UniK3D/blob/29f7862f3c3ee79c53ef0153dfc901ce511df575/LICENSE) | CC BY-NC-SA 4.0 text |
| [Fixed model source header](https://github.com/lpiccinelli-eth/UniK3D/blob/29f7862f3c3ee79c53ef0153dfc901ce511df575/unik3d/models/unik3d.py) | CC BY-NC-SA 4.0 label |
| [Fixed README license section](https://github.com/lpiccinelli-eth/UniK3D/blob/29f7862f3c3ee79c53ef0153dfc901ce511df575/README.md#license) | CC BY-NC 4.0 label; describes software and links the different LICENSE text |
| [Fixed package metadata](https://github.com/lpiccinelli-eth/UniK3D/blob/29f7862f3c3ee79c53ef0153dfc901ce511df575/pyproject.toml) | CC BY-NC 4.0 label |
| [Fixed Small model card](https://huggingface.co/lpiccinelli/unik3d-vits/blob/80a99bfeb8d983ca6af27125fd83c88b891e75ad/README.md) | Library / tags and a documentation placeholder; no explicit license field or terms |
| Official Small / Base / Large Hub metadata and file listings | No license in cardData, and no LICENSE / NOTICE file observed |
| [Author's project page](https://lpiccinelli-eth.github.io/pub/unik3d/) | Links code and models; no additional model-license terms found on the inspected page |

The other checkpoint refs observed were Base `c65bb3a8a4fa981a06ee9286ce847aebe7f66fe2` and
Large `008aa54308b8bc142f74c9c7b098833aaede06bd`. These metadata checks do not establish their permissions.
A proposed license edit on a Hub PR ref was not treated as terms applying to the fixed released checkpoint.
Public availability / ungated download does not resolve the missing applicability evidence.

No `weights_license` value has been guessed, no real variant has been registered as supported, and the
third-model E2E gate has not been marked successful. The uncertainty remains unresolved.

## Work-specific stop conditions — revised user instruction

The following is the current UniK3D case status, not a blanket rule for all models. Independent technical
work remains subject to Phase / task authorization; the 2026-11-12 task authorizes documentation only.

| Work | Current treatment |
| --- | --- |
| Independently authored adapter lifecycle, native-layout array conversion, synthetic fixtures, geometry and existing-reader tests | Continue without importing or copying upstream implementation or loading weights |
| Real checkpoint acquisition, use or redistribution (including inference from an existing local copy) | Existing case-specific hold remains. Reconsider the affected action under the common policy using intended use / risk assessment and any needed user decision; this update does not release the hold |
| Production registration, real runtime bridge and independent UniK3D environment | Still unimplemented; this documentation-only update does not begin these steps. Synthetic execution is not adoption evidence |
| Work conflicting with an explicit prohibition or presenting a major rights risk | Stop the affected work and report the specific conflict / risk; do not assume missing information is a prohibition |
| 03.5 / 03.6 | Gate remains closed pending all 03.4 acceptance conditions, including real-model E2E |

Public accessibility and a source-license label do not by themselves resolve checkpoint applicability.
This is a record of missing evidence, not a legal determination or permission to use the checkpoint.

## Technical observations — source only, no execution claim

The fixed `UniK3D.infer` performs native preprocessing and returns points, rays, confidence, depth and
distance. Its source defines depth from points' z coordinate and distance from the points' norm;
rays are normalized after native postprocessing. These are distinct quantities, especially for wide-angle
or non-pinhole cameras. A future adapter must select and document the canonical depth meaning without
inventing pinhole K, reconstructing native Points from depth, or discarding directions by assuming positive z.
The independent synthetic contract now chooses native **distance** as canonical `ray_distance` and
transposes native points `[1,3,H,W]` to `[H,W,3]`, preserving negative or zero z directions.
It validates distance against norm(points), and native z-depth against points.z if present.
It neither invents K nor reconstructs points, changes scale, resamples, or converts range to z.
Nonfinite / nonpositive distances or nonfinite points become invalid depth / vectors; computed validity
is not exposed as a native model mask. Real tensors, camera frame, scale and precision remain unverified.

The package requires Python >=3.11 and declares NumPy >=2, torch >=2.4, torchvision >=0.19, and other
training / visualization / extension dependencies. The README includes an explicit CPU example alongside
CUDA installation requirements. This is source evidence only: no CPU import, memory, runtime, package
subset or independent environment has been validated. Existing MoGe / DA3 / UI environments are unchanged.

## Independent implementation boundary

See [adapter scope](../models/unik3d/README.md). Default `load()` reports the checkpoint hold before
path access or framework import. Only an explicitly injected, independently authored fixture runtime
with no checkpoint can exercise the load / predict / unload contract. No production manifest is
installed, so Gradio and CLI discovery do not advertise a runnable UniK3D variant.
The synthetic runtime runs in an existing test environment; it is not a third independent model environment.
Depth and points reuse `01A-depth-only` / `02A-geometry-v1`. Schema, core, UI and backend are unchanged.
Rays / confidence / pose serialization, new profiles and generic runtime-capability checks remain outstanding.

## Checkpoint resume gate and next steps

Historical gate wording (2026-11-11), preserved as the earlier decision rather than the current common rule:

> Resume adoption when authoritative author-provided terms or permission establish the license applicable
> to the selected checkpoint and clarify the differing source labels for the intended research integration.

Current operation (2026-11-12): follow the [AGENTS common policy](../AGENTS.md#license-review-and-decisions).
Distinguish source and checkpoint conditions and record official sources, the intended action / purpose,
uncertainty, risks and decision basis. Clear terms covering the intended use allow ordinary authorized work;
uncertain terms directly affecting acquisition or use call for a scoped assessment and user judgment when needed.
Unknown terms neither establish unrestricted permission nor prove a prohibition.
The existing UniK3D checkpoint hold remains in place in this documentation-only change. Its reconsideration
does not universally require direct author contact or individual permission: additional official documentation
may supply evidence, and high-value author questions may be proposed to the user if needed.
Commercial use, weight redistribution and public-package bundling require separate assessment from local research.
An operational user decision is not a grant of rights by the rights holder.

No external message or permission request has been sent to the authors.

After an action-specific decision to resume, record the decision, applicable conditions and any remaining
uncertainty, establish an independent environment and runtime
bridge, verify local weights / config digests, and complete the depth-only CLI → Runner → Backend → worker
E2E. Required optional outputs must also be verified against actual native outputs before their acceptance.
Independent fixture preparation may precede these steps; it does not satisfy the real-model E2E.
03.4 remains incomplete and 03.5 remains gated on 03.4 acceptance.

Questions prepared for the authors (not sent; optional clarification proposals, not mandatory gates for all models):

1. For source revision `29f7862...`, should integration follow CC BY-NC or CC BY-NC-SA 4.0?
   Which files / components have different terms, if any, and where is the authoritative clarification?
2. What license applies to `unik3d-vits` checkpoint revision `80a99bf...` and its config, and does it
   differ for Base / Large? Please identify a model card / license document or explicit permission covering them.
3. Under those terms, what attribution / notices and redistribution conditions apply to a research
   integration, local checkpoint cache, shared lab environment and any distributed checkpoint copy?
4. Are inference outputs or a hosted research demo subject to additional conditions, and how should
   noncommercial scope and any share-alike obligations be documented for this intended use?

Local investigation evidence is under `.local/validation/phase-03-4-unik3d-*`; it is excluded from Git.
The earlier investigation commit changed documentation only and ran no new implementation / inference tests.
The current independent implementation has separate verification results in [Phase 03](phases/phase-03.md).
