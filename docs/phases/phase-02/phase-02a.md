# Phase 02A — Geometry Artifacts

Status: **COMPLETE**（実装・fake / contract・実CPU geometryのExit達成）。Phase 02の内部milestone。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
今回の承認は02A実装・検証・関連docs更新・Exit達成後のcommit / main push。02B以降は未承認。

## Goal / Background

モデル由来の幾何情報を正式なRun成果物として保存・検証する。
開始時のMDEOutputにはpoints / normals / intrinsics / maskがあるが、MoGe adapterはdepthとmaskのみ返し、
共通workerはdepthだけ保存していた。JobSpecもrequested_outputs=[depth]のみだった。
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

- [x] required depth / optional要求の意味を確定。未対応の明示要求はsubmit前に拒否し、
  明示要求のruntime欠落はエラー。未要求・未対応optionalはabsenceとして許容する。
- [x] adapterがnative出力を標準MDEOutputへ変換する。coreにモデル名分岐を追加しない。
  native表現と標準表現をmetadata / namespaced extrasで区別し、native配列を保存する場合もtyped refs。
- [x] 共通workerでCPU配列→non-object NPYとArtifactRef、atomic publication、size / SHA-256を保存。
  required depthは従来のlittle-endian float32 [H,W] / C-order、invalid NaNを維持。
- [x] points / normalsはfloat32 [H,W,3]、intrinsicsはfloat32 [3,3] output-grid pixel K。
  maskはbool [H,W]。native maskと共通effective validityを区別し、生成方法を記録する。
  有効depthはfinite-positiveかつmodel mask、geometryのfinite判定は各artifactにも適用する。
  mask欠如時は従来depthからvalidityを復元する。全depth無効は従来通り失敗。
- [x] depth_kind / camera_frame / scale_type / unit / native convention / conversion /
  normal orientation / pixel center / resize-crop-padding / RGB対応を保存・検証する。
  relative / unknownをmetricとしない。K欠如の非pinholeに偽Kを与えない。
- [x] 標準frameは既存OpenCV規約を維持し、native→standardのbasis / scale変換をadapterで明示。
  points / depthの尺度を一致させ、viewer都合で座標・scaleを変更しない。
  normalsは有効領域のunit vectorを許容誤差付きで検証、Kはfinite・camera / grid conventionを検証。
- [x] RunStoreのheader / payload / shape / dtype / checksum / path / ID検証をoptionalにも拡張。
  worker / metadata / JobResultの参照整合性を確認。pickle / object NPYを禁止。
- [x] schemaはoptional追加を優先。新serialization profileを旧01A-depth-onlyと区別し、
  旧profileの読込を保持する。意味・単位・必須項目変更ならmajor更新と移行/互換テストを先に設計。
- [x] rawは一度publish後不変、再推論は新Run。既存Runにoptionalを後付けしない。

## Tests / Exit criteria

- [x] fake depth-only、各optional単独・組合せ・全欠如をsave / collect / reloadし、値とmetadataが一致。
- [x] shape不一致、object dtype、非finite有効点、normal / K不正、mask不一致、欠落・破損・
  path traversal / Run外symlink、digest不一致を拒否。必須要求欠落を成功にしない。
- [x] 01A / 01B schema 1.0・計測なし・mask別保存なしのfixtureを旧条件で読み戻す。
  CLI / cancel / timeout / busyの契約回帰を実行する。
- [x] pin済みMoGeの明示CPU smokeで実際に返されたgeometryだけを保存・検証。
  native K / points / normalの変換を数値fixtureで確認。未提供optionalはabsenceと理由を残す。
- [x] 再collectでraw / reportsのhashが不変、predictが増えない。仕様・実測証拠を更新。

全項目成功で02A exit。GPU成功や全optional提供を条件にしない。
数値保存の検証と深度精度の評価を区別する。実行結果は下記Acceptance evidenceに記録する。

## Additional mandatory CPU Points acceptance

- [x] pin済みMoGe-2 ViT-S Normalの実CPU推論でnative Pointsを正式Run artifactとして保存・再読込・検証。
- [x] native frame / metric scaleとDepthとの整合を実測し、仮Kや便宜的逆投影をnative Pointsと扱わない。
- [x] Normals / Intrinsicsは実出力・capabilityに従う。実Points未達ならCOMPLETEにしない。

## Known risks

native normalized Kとpixel center、z-depth / ray-distance、relative scale、normal orientation、
invalid maskとgeometry gridの不一致、大容量NPY、旧validatorと新profileの整合。
float許容誤差・容量制約をfixtureと実測に基づき確定する。

## Decisions / Deferred decisions

ModelAdapterは意味変換、workerはserialization、RunStoreは検証を担当。
全optional強制なし、raw不変、共通dtypeとnative conventionの記録を採用。
profile=02A-geometry-v1、outputs / artifacts両方のoptional refs、effective maskとmodel_maskの分離を採用。
normal unit-length許容誤差1e-3、points/depth rtol=1e-4 / atol=1e-5、K canonical許容誤差1e-6。
具体wire契約は [Run Directory](../../run-directory-spec.md#implemented-phase-02a-wire-format-and-validation)。
ray / pose / confidenceと複数モデル検証はPhase 03以降。mesh / viewerは02C。

## Acceptance evidence — 実CPU / compatibility

- Geometry Run: `0c33df74-f72d-4348-a9a1-c2968d5f9e7b`、COMPLETED / CLI exit 0。
  pin済みMoGe-2 ViT-S Normal、source 07444410f1e33f402353b99d6ccd26bd31e469e8、
  checkpoint SHA-256 79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc。
  既存named独立mde-moge、Python 3.11.14 / torch 2.6.0+cu124 / CUDA runtime 12.4、明示CPU。
- requested outputs: depth / points / normals / intrinsics / mask。
  正式NPY refs・SHA-256 / size・metadata・WorkerResult / JobResult / logsを保存して読み戻した。
- Points: native infer(force_projection=False, fov_x=None)、float32 [256,256,3]、OpenCV frame、
  metric scale-headのm。adapter逆投影 / 仮Kなし。有効値をidentity copy、無効値のみNaNへ標準化。
  65,536 valid / 0 invalid、points.z-depth最大誤差 **0 m**。
  depth範囲0.8110443949699402〜4.28781270980835 m。GT accuracy評価ではない。
- Normals: 実native normal headを保存、unit-length最大誤差1.1920928955078125e-7。
  符号反転・depthから生成なし。native learned orientationをmetadataに保持、向きのGT評価は未実施。
- Intrinsics: 実native normalized Kを整数pixel中心へ変換、native数値と式を保存。
  fx=fy=346.61676025390625 pixel、cx=cy=127.5、pinhole canonical bottom row。
  effective maskとmodel maskは別NPY。shape / dtype / unit / frame / digest・数値を独立に検証。
- Depth-only新Run: `5d0351b3-1a6b-460f-80eb-c19f528e5656`、COMPLETED / exit 0、
  CLI既定を変更せず01A-depth-only、geometry Runのdepth SHA-256と一致。
- 新CLI process / Conda利用不可設定でgeometry Runと旧01A Run
  `9c5b6556-30d3-43ae-827f-7bd8b0a47580`を各2回collect。全filesのhash / mtime不変。
  geometry stdoutのpredictは1回。旧schema 1.0 / depth-only / mask未保存の互換を確認。
- 実測seconds: load=7.30340818500008、predict=5.698126064999997、
  numeric serialization=0.2369949550002275、worker=13.559579759999906。
  単位・scopeをresultに保存。CPU allocatorは未計測で省略、GPU / driver / 精度評価は未検証。
- logs / 数値検証script・結果はGit管理外 `.local/validation/02a-*`、Runs / weightsもGit管理外。
  実装・環境の取得物をcommitしない。02B以降は未着手・未承認。

## Test execution record

- 変更前baseline: 既存29 tests成功（107.062秒）。
- 新geometry tests: optional組合せ、missing / invalid output、NPY / semantic tampering、
  path / digest / symlink、readonly collect、worker overwrite拒否、native K / points / normal mapping。
- 初回全40 tests: 39成功、既存timeout test 1件はworker readiness前に終了（248.709秒）。
  execution timeout=4秒に起動完了が間に合わなかった。テスト条件・production timeoutを緩和していない。
- 該当testの単独再実行は成功（4.247秒）。起動所要時間に依存するtestの注意点として記録する。
- 最終numeric roundtripの追加確認は成功（1 test、5.161秒）。
  制御側import境界、Python AST / JSON、25 Markdown / 165相対リンク・anchors・fences、
  `git diff --check`も成功。依存定義・環境・generated artifactsの変更は含めない。
- 最終全体再実行: **40 tests成功（238.662秒）**、既存29 + geometry 11。
  他のsmokeを重ねず順次実行し、timeout / cancel / busy・01A / 01B回帰も成功。
  実CPU native Pointsの必須条件を含む全Exit達成で02A COMPLETE。02B開始は未承認。

最終production sourceでの追加CPU smoke Run: `a2c9ca5a-4eb7-4697-b880-8041e7749bae`、COMPLETED / exit 0。
Runのsource_digestが最終src / models/mogeの対象source filesと一致することを確認した。
Points [256,256,3] / m、65,536 valid、points.z-depth誤差0 m、Normals / Intrinsics / masksも再検証。
新CLIによる2回collectで全file hash / mtime不変、predictは1回。
初回geometryと既定depth-onlyのdepth SHA-256も一致。GPU / GT精度は未検証。
