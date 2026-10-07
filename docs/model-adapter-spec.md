# Model adapter specification

Status: 設計のみ。共通 schema の初期案は `1.0`。実装・manifest・モデル環境はまだない。
関連: [Architecture](architecture.md)、[Execution](execution-backend-spec.md)、
[Environment](environment-strategy.md)、[Run Directory](run-directory-spec.md)。

## Plugin boundary

モデル固有の loading、入力正規化、resize / padding、推論引数、出力変換は
`models/<model_name>/` に置く。Registry は manifest を読むだけで adapter を import しない。
worker は選択された entrypoint だけを import する。モデル追加のために core / UI / backend に
`if model == ...` を追加しない。

想定構成は `adapter.py`、`manifest.json`、`environment.yml`、README、contract tests。
upstream package のコード全体をコピーするより、検証した revision の既存 API を薄く包む。
既存の独立スクリプトが得られた場合は、その load / infer / export 部分を優先して再利用する。

## ModelInfo and manifest

ModelInfo は JSON で表現可能な metadata。schema の検証と adapter import は分離する。

| Field | 内容 |
| --- | --- |
| `schema_version` | manifest / model 契約の版 |
| `model_id`, `display_name` | 安定した plugin ID と表示名。ID と環境名は別 |
| `adapter_entrypoint`, `adapter_version` | worker が解決する import path と adapter revision |
| `upstream_url`, `upstream_revision` | 出典と検証対象 revision。branch 名だけでは再現版としない |
| `variants` | variant ID、model generation / version、checkpoint reference / revision / digest |
| `capabilities` | variant 別の出力・入力能力、条件 |
| `environment_refs` | 推奨 logical environment と許容 environment 定義の参照 |
| `parameter_schema` | 型、範囲、enum、default、説明、required、依存条件 |
| `supported_devices`, `supported_dtypes` | 宣言値。実行可否は worker preflight で再検証 |
| `input_constraints` | input view 数、image mode、サイズ、camera model の制約 |
| `license`, `weights_license`, `citations` | upstream code / weights の出典。利用条件は採用時に確認 |

manifest は runtime にモデルを load するための Python を含めない。parameter schema は
JSON Schema の検証可能な subset を選定し、未知の引数は拒否する。値を shell に展開しない。
Registry は plugin ID の重複、entrypoint の欠落、未知の必須 schema major をエラーにする。
環境未作成はモデル発見失敗と区別し、UI には「未準備」として表示する。

## Capabilities

単なる boolean ではなく、各 capability を `supported / conditional / unsupported` と
条件説明で定義する。variant を選定した後の capability を UI と Runner に渡す。

| Capability | 意味 / 条件 |
| --- | --- |
| `depth` | 必須。少なくとも各出力 view に深度配列を返せる |
| `metric_depth` | 深度がメートル単位の metric scale。世代 / checkpoint / 入力条件を明示 |
| `points` | dense point map、camera frame の 3D 座標 |
| `point_cloud` | point map から共通 exporter で生成可能、または native sparse cloud。区別を明記 |
| `normals` | 法線出力。native と depth からの派生計算を混同しない |
| `intrinsics` | pinhole intrinsics を意味付きで返せる。非 pinhole に偽の K を与えない |
| `rays` | pixel に対応した方向ベクトル。camera model と convention が必要 |
| `camera_pose` | 共通座標系における各 camera pose。single-view で推定されるとは限らない |
| `mask` | model が与える有効 / 無効 pixel の mask |
| `confidence` | confidence の意味・範囲・大小の向き。確率やモデル間で共通尺度とは限らない |
| `multi_view` | 関係のある複数 view を同時処理する能力。独立画像の batch とは別 |

`supported` は宣言した条件で結果を保証する。`conditional` は checkpoint / option / 入力依存。
必須要求が未対応なら submit 前に拒否し、runtime に不足したら明示エラーを返す。
表示可否は capability と実際の artifact presence の両方で判定する。

## ModelAdapter lifecycle

以下は signature の文書案であり、production interface の実装ではない。

```text
load(context: ModelLoadContext) -> LoadedModelInfo
predict(request: PredictionRequest) -> PredictionBatch
unload() -> None
```

- `ModelLoadContext`: ModelInfo / variant、checkpoint location、device、dtype、seed、
  load parameters。Backend、UI object、MLflow client は渡さない。
- `LoadedModelInfo`: 実際の upstream / checkpoint revision、resolved device / dtype、
  runtime capability、warnings。要求と実測の差は記録する。
- `PredictionRequest`: stable `view_id` 付き RGB 入力、任意 camera 情報、predict parameters、
  requested outputs。配列は worker 内部の受け渡しであり JobSpec に巨大配列を載せない。
- `PredictionBatch`: `views: list[MDEOutput]` と任意の共通 scene metadata。
  最初は 1 view。独立した複数画像の Benchmark は別 job とし、multi-view と混ぜない。

状態は `UNLOADED → LOADED → PREDICTING → LOADED → UNLOADED`。
未 load の predict、同じ adapter への同時 predict を拒否する。初期 worker は 1 job / 1 process。
`load()` の二重呼び出しはエラー、`unload()` は冪等とし、部分 load 失敗にも使える。
worker は finally で unload を試み、失敗しても元の推論エラーを失わない。
強制 kill では finally の実行を保証できないため、process 終了による GPU 解放も前提とする。

adapter は upstream の eval / inference mode、model preprocessing / postprocessing を担当する。
計測・serialization・JobStatus 管理は共通 worker に置く。adapter は必要なら計測境界用 hook を
提供するが、モデルごとに runtime の定義を変えない。warm worker は将来の追加である。
初期の predict timing は adapter の predict 全体（固有の前後処理と CPU 出力への変換を含む）とし、
pure network forward time と区別する。比較時は処理 scope を同じ key の metadata に記録する。

## MDEOutput

**各 view の depth は必須、それ以外のモデル出力は optional。**
metadata は深度の解釈に必要な共通項目であり、モデルの追加出力とは区別する。

| Field | Worker 内の表現 | 意味 |
| --- | --- | --- |
| `view_id` | string | input view と一対一に対応する安定 ID |
| `depth` | float32 `[H, W]` | depth。valid pixel は有限・正。PNG 正規化画像を代用しない |
| `points` | optional float32 `[H, W, 3]` | pixel 対応の point map。疎点群は extras / artifact |
| `intrinsics` | optional float32 `[3, 3]` | output pixel grid に対応する pinhole K、pixel 単位 |
| `normals` | optional float32 `[H, W, 3]` | 有効 pixel の unit normal、camera frame |
| `mask` | optional bool `[H, W]` | true が model-valid。GT 評価 mask とは別 |
| `confidence` | optional float32 `[H, W]` | native confidence。無断で 0–1 正規化しない |
| `camera_pose` | optional float32 `[4, 4]` | homogeneous camera-to-world transform |
| `rays` | optional float32 `[H, W, 3]` | camera frame の unit direction、pixel 対応 |
| `extras` | JSON-compatible metadata / typed artifact refs | namespaced モデル固有出力 |
| `metadata` | 共通 JSON metadata | 下記 convention / provenance |

出力の dense maps は同じ `[H, W]` を使用する。配列を CPU に移し共通 dtype に変換した後で
serialization する。推論 dtype と保存 dtype は別々に記録する。

### Geometric conventions

- `depth_kind`: `z_depth` または `ray_distance`。unknown のまま成功出力にしない。
  z は optical axis、ray distance は camera center からの距離。相互に同一扱いしない。
- `scale_type`: `metric / relative / unknown`、`depth_unit`: `m / arbitrary / unknown`。
  scale が不明な場合は metric evaluation を不可とする。
- camera frame: OpenCV 系の x right、y down、z forward、right-handed。
  native frame の違いは adapter が変換し、native convention を metadata に残す。
- pose は camera-to-world。native world-to-camera は adapter が逆変換する。
  scene の world frame / scale / reference view を明記する。single-view で pose がない場合は
  null とし、推定結果として identity pose を捏造しない。
- K は出力 grid の pixel coordinates。pixel center convention は中心が整数 index の方式とし、
  normalized intrinsics からの変換では upstream の定義を確認する。単純な W / H 掛けを
  convention 未確認で行わない。
- `original_size`、`output_size`、resize / crop / padding、image-to-output の変換を残す。
  native output grid を基本とし、入力画像と対応づけて表示・評価する。
- 非 pinhole camera では rays と `camera_model` / params を使い、K は null にできる。
  rays から range → z の変換は幾何条件を満たす場合だけ行い、z が非正となる方向も区別する。
- relative point / pose translation と depth の尺度は一致させる。metric の確証がない値に m を付けない。
- 無効値は mask がある場合と finite / positive 判定で扱う。全部無効の出力は失敗扱い。
  任意 mask の欠如は「全部正しい」ことを意味しない。

metadata は confidence meaning / range / direction、normal orientation、actual capabilities、
conversion provenance、warnings、upstream / checkpoint identity を持つ。
camera model や depth kind が共通 Evaluator の対象外なら skip 理由を保存する。

### Extras and process boundary

extras の key は `moge/...`、`unik3d/...`、`da3/...` 等で衝突を避ける。
未知 extras があっても core は保持できるが、意味を知らないまま評価しない。
NumPy array、torch tensor、Python class instance は JSON に直接入れない。
大きい値は `ArtifactRef`（path、dtype、shape、units、checksum）へ変換する。
pickle と object dtype の NPY は wire format にしない。
MDEOutput と serialized result の対応は [Run Directory](run-directory-spec.md) が定義する。

## Upstream reference and candidate mappings

以下は公式 upstream の参考情報。ローカルで動作を確認した一覧ではなく、checkpoint と
採用 revision の確定後に adapter contract tests で検証する。

| Model | 参考となる既存 API / 出力 | adapter で確認する点 |
| --- | --- | --- |
| MoGe | version 別 MoGeModel、infer、depth / points / mask / intrinsics | 世代別 scale、optional normal、normalized K の変換 |
| UniK3D | UniK3D、infer、depth / points / rays | native depth の定義、camera model、出力 shape / frame |
| DA3 | DepthAnything3、inference、view ごとの depth / confidence / extrinsics / intrinsics | variant 別 metric / multi-view、grid 対応、w2c → c2w |

MoGe は世代・weights によって metric scale と normal 出力が異なるため、一律の capability を
与えない。[公式 MoGe README](https://github.com/microsoft/MoGe)

UniK3D は rays と複数の camera model を扱うため、すべてを pinhole K に還元する設計は避ける。
[公式 UniK3D README](https://github.com/lpiccinelli-eth/UniK3D)

DA3 は view ごとの出力と world-to-camera extrinsics を公開する。multi-view の配列は
view ID を保って分割し、optional 出力は variant と実結果に従う。
[公式 DA3 README](https://github.com/ByteDance-Seed/Depth-Anything-3)、
[公式 DA3 API](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/main/docs/API.md)

公式の UI / CLI 自体をこの基盤の Runner に組み込むのではなく、その推論 API と既存の
独立した変換処理を再利用する。現在の upstream latest を過去の動作版と同一視しない。

## Validation and compatibility

Phase 01 の fake adapter で load / predict / unload、必須 depth、shape、schema、
optional absence、失敗時 cleanup を検証する。Phase 03 で各実モデルの convention を検証する。
metadata major が異なる場合は拒否し、同じ major の未知 optional field は保持または無視できる。
depth 単位・pose の向き・必須項目の変更は破壊的変更とし、docs と reader migration を更新する。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| MDEOutput は 1 view、PredictionBatch は view list | single と multi-view で depth 型を変えない | scene-level result が別 metadata になる | temporal / multi-view pose と共有 scene artifact |
| scale / depth kind / frame を明示 | metric と relative、z と range の比較誤りを避ける | adapter の検証量が増える | camera / evaluation protocol の追加 |
| capability は variant と条件付き | モデル family の機能を過剰申告しない | UI に条件表示が必要 | optional output / derived visualization |
| extras は namespaced typed refs | native output を失わず共通 API を保つ | 汎用 UI は未知 extras を自動可視化しない | plugin-specific artifact renderer を独立追加 |
