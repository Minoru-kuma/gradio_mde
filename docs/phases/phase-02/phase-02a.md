# Phase 02A — Geometry Artifacts

Status: **NOT_STARTED / 実装未承認**。Phase 02の内部milestone。以下は設計のみ。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
今回の承認は文書整備・検証・commit / main pushのみ。実装開始・依存導入は行わない。

## Goal / Background

モデル由来の幾何情報を正式なRun成果物として保存・検証する。
現在のMDEOutputにpoints / normals / intrinsics / maskはあるが、MoGe adapterはdepthとmaskのみ返し、
共通workerはdepthだけ保存する。JobSpecもrequested_outputs=[depth]のみ受理する。
optional fieldsの存在やnative output keysはexport済みを意味しない。

## Scope / Non-goals

必須depth、optional points / normals / intrinsics、valid mask、意味・座標系・単位・scale・
grid対応・conversion provenance。共通worker serialization / RunStore validationと旧depth-only Run互換。
単一モデル・single-view / single-attemptを維持。全モデルへのoptional outputs強制、
mesh生成、Gradio、rays / pose / confidenceの新規export、他モデル追加は対象外。

## Dependencies

Phase 01 COMPLETEと02Aの個別実装承認。
[ModelAdapter](../../model-adapter-spec.md)、[Run Directory](../../run-directory-spec.md)、
[Execution](../../execution-backend-spec.md) の現行depth-only契約を基準にする。
02B / 02Cに標準保存形式を提供し、viewerの実装には依存しない。

## Implementation tasks

- [ ] required depth / optional要求の意味を確定。未対応の明示要求はsubmit前に拒否し、
  明示要求のruntime欠落はエラー。未要求・未対応optionalはabsenceとして許容する。
- [ ] adapterがnative出力を標準MDEOutputへ変換する。coreにモデル名分岐を追加しない。
  native表現と標準表現をmetadata / namespaced extrasで区別し、native配列を保存する場合もtyped refs。
- [ ] 共通workerでCPU配列→non-object NPYとArtifactRef、atomic publication、size / SHA-256を保存。
  required depthは従来のlittle-endian float32 [H,W] / C-order、invalid NaNを維持。
- [ ] points / normalsはfloat32 [H,W,3]、intrinsicsはfloat32 [3,3] output-grid pixel K。
  maskはbool [H,W]。native maskと共通effective validityを区別し、生成方法を記録する。
  有効depthはfinite-positiveかつmodel mask、geometryのfinite判定は各artifactにも適用する。
  mask欠如時は従来depthからvalidityを復元する。全depth無効は従来通り失敗。
- [ ] depth_kind / camera_frame / scale_type / unit / native convention / conversion /
  normal orientation / pixel center / resize-crop-padding / RGB対応を保存・検証する。
  relative / unknownをmetricとしない。K欠如の非pinholeに偽Kを与えない。
- [ ] 標準frameは既存OpenCV規約を維持し、native→standardのbasis / scale変換をadapterで明示。
  points / depthの尺度を一致させ、viewer都合で座標・scaleを変更しない。
  normalsは有効領域のunit vectorを許容誤差付きで検証、Kはfinite・camera / grid conventionを検証。
- [ ] RunStoreのheader / payload / shape / dtype / checksum / path / ID検証をoptionalにも拡張。
  worker / metadata / JobResultの参照整合性を確認。pickle / object NPYを禁止。
- [ ] schemaはoptional追加を優先。新serialization profileを旧01A-depth-onlyと区別し、
  旧profileの読込を保持する。意味・単位・必須項目変更ならmajor更新と移行/互換テストを先に設計。
- [ ] rawは一度publish後不変、再推論は新Run。既存Runにoptionalを後付けしない。

## Tests / Exit criteria

- [ ] fake depth-only、各optional単独・組合せ・全欠如をsave / collect / reloadし、値とmetadataが一致。
- [ ] shape不一致、object dtype、非finite有効点、normal / K不正、mask不一致、欠落・破損・
  path traversal / Run外symlink、digest不一致を拒否。必須要求欠落を成功にしない。
- [ ] 01A / 01B schema 1.0・計測なし・mask別保存なしのfixtureを旧条件で読み戻す。
  CLI / cancel / timeout / busyの契約回帰を実行する。
- [ ] pin済みMoGeの明示CPU smokeで実際に返されたgeometryだけを保存・検証。
  native K / points / normalの変換を数値fixtureで確認。未提供optionalはabsenceと理由を残す。
- [ ] 再collectでraw / reportsのhashが不変、predictが増えない。仕様・実測証拠を更新。

全項目成功で02A exit。GPU成功や全optional提供を条件にしない。
数値保存の検証と深度精度の評価を区別する。今回は未実行。

## Known risks

native normalized Kとpixel center、z-depth / ray-distance、relative scale、normal orientation、
invalid maskとgeometry gridの不一致、大容量NPY、旧validatorと新profileの整合。
float許容誤差・容量制約をfixtureと実測に基づき確定する。

## Decisions / Deferred decisions

ModelAdapterは意味変換、workerはserialization、RunStoreは検証を担当。
全optional強制なし、raw不変、共通dtypeとnative conventionの記録を採用。
profile名・optional refの具体JSON形・mask表現・normal許容誤差は02A実装前に確定し仕様更新。
ray / pose / confidenceと複数モデル検証はPhase 03以降。mesh / viewerは02C。
