# UniK3D adoption investigation — Phase 03.4

Status: **candidate only / adoption gate unmet**. Work resumed after 03.3, then stopped before
installation, weight download or implementation because the applicable license evidence is unresolved.
This records conflicting labels and missing information, not a conclusion that use is prohibited.

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

The user's implementation instruction requires stopping when important adoption evidence or licensing
conditions cannot be established. Consequently, no `weights_license` value has been guessed, no variant
has been registered as supported, and the third-model E2E gate has not been marked successful.

## Technical observations — source only, no execution claim

The fixed `UniK3D.infer` performs native preprocessing and returns points, rays, confidence, depth and
distance. Its source defines depth from points' z coordinate and distance from the points' norm;
rays are normalized after native postprocessing. These are distinct quantities, especially for wide-angle
or non-pinhole cameras. A future adapter must select and document the canonical depth meaning without
inventing pinhole K, reconstructing native Points from depth, or discarding directions by assuming positive z.
No geometry-conversion policy has been adopted or validated on real tensors in this investigation.

The package requires Python >=3.11 and declares NumPy >=2, torch >=2.4, torchvision >=0.19, and other
training / visualization / extension dependencies. The README includes an explicit CPU example alongside
CUDA installation requirements. This is source evidence only: no CPU import, memory, runtime, package
subset or independent environment has been validated. Existing MoGe / DA3 / UI environments are unchanged.

## Resume gate and next steps

Resume adoption when authoritative author-provided terms or permission establish the license applicable
to the selected checkpoint and clarify the differing source labels for the intended research integration.
No external message or permission request has been sent to the authors.

Then record the adoption decision and verified terms, establish an independent environment, verify local
weights / config digests, and complete the depth-only CLI → Runner → Backend → worker E2E. Only after that
success, add required optional outputs one contract at a time with numeric fixtures, serialization profiles,
stdlib-reader validation and actual native-output evidence. 03.5 remains gated on 03.4 acceptance.

Local evidence is under `.local/validation/phase-03-4-unik3d-*`; it is excluded from Git. This task changes
only repository documentation. No new implementation tests, real inference or browser tests were run.
