# Phase 02C — 3D Results Viewer

Status: **NOT_STARTED / 実装未承認**。Phase 02の内部milestone。以下は設計のみ。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
現在の実装承認は02Aのみ。このmilestoneは未承認のため開始しない。

## Goal / Background

保存した推論成果物をResultsタブで2D / 3D閲覧し、再推論なしでデモできるようにする。
モデル由来raw geometryとviewerで生成するderived artifactsを区別する。
現行Runはdepth-only。3D表示に必要な情報が不足する旧Runも正常に扱う。

## Scope / Non-goals

Resultsに **Depth | RawDepth | Point Cloud | Mesh**。保存Run ID読込、実行条件・計測表示、
回転・zoom・pan、色 / mesh表示切替、derived meshの遅延生成・永続保存・再利用。
高度な3D編集・解析、再推論、モデル名専用viewer、Run管理UI、他モデルは対象外。

## Dependencies

02A / 02B exitと02C実装承認。
[Run Directory](../../run-directory-spec.md)、[Run Management](../../run-management-spec.md)。
02Cでderived storage / generationの最小共通serviceを用意し、02Dで明示管理操作を追加する。

## Implementation tasks

- [ ] Depth: colormapと表示normalizationをraw値から分離。unit / scale / invalid pixel、
  colormap範囲を表示し、NaN / all-invalid / 定数depthを安全に扱う。rawを書き換えない。
- [ ] RawDepth: shape / dtype / min / max / 有効画素数・割合を表示。
  min / maxはfinite-positiveかつ保存maskの有効値のみ、空ならunavailable。raw .npyをdownload。
- [ ] Point Cloud: 保存pointsを優先。回転・zoom・pan、RGB color / Depth color / Normal colorを
  動的に切替。RGBは記録したinput→output grid対応、normal色はorientationを明示。
  欠如するnormal色は理由付きで無効化する。推定normalをnativeとして表示しない。
- [ ] points欠如時はcamera model / depth_kind / K等で変換が定義できる場合だけ共通back-projection。
  生成pointsはderivedとして記録し、camera情報が不足する旧depth-only Runは3D unavailable。
  仮のK・metric scale・poseを補わない。
- [ ] Mesh: モデル由来dense pointsを優先し共通grid triangulation等で生成。
  invalid vertices、mask境界、深度不連続、退化facesを除外し、thresholdの単位・相対基準を記録。
  RGB textured / Geometry / Wireframeを動的切替。texture対応不能なら理由付きで無効化。
- [ ] 初回mesh表示要求で遅延生成。Runに関連付けて永続保存し、algorithm名/版、parameters、
  入力artifactのdigest、attempt / view、frame / unit / scale、出力digestを別manifestに記録。
  同条件を再利用し、partial / corrupt cacheは成功扱いしない。JobResultは変更しない。
- [ ] model成果物とderivedをUIラベル・manifest・保存領域で区別。
  downsampling / 表示LOD / texture生成もrawを変更せず条件を記録する。
- [ ] viewerは保存されたframe / unit / scaleを維持し、初期表示cameraをboundsから調整。
  renderer軸変換が必要なら表示層だけの可逆変換を明示し、artifactは変更しない。
  Point Cloud / Mesh間のcamera stateを可能な範囲で保持し、不可なら制約とresetを説明する。
- [ ] terminal Runはアプリ再起動後Run IDだけで再表示し、モデル環境・weightsを要求しない。
  runtime / GPU memoryは保存された値・単位・scopeのみ表示、欠如はunavailable。
- [ ] 3D libraryを技術検証してpin。browser WebGL、point容量、mesh / texture / wireframe、
  camera state、Gradio統合、license、ローカルasset配信・CDNなしoffline動作を比較して決定。
  Python側生成・ブラウザ描画を分離し、採用可否を固定版の小fixtureで確認する。

## Tests / Exit criteria

- [ ] depthの数値統計・invalid・normalization、各geometry / color欠如、
  RGB grid対応、標準frame / scaleをsynthetic fixtureと既知cameraで検証。
- [ ] browserで4モード、Point Cloud / Meshの回転・zoom・pan、3種colorと3種mesh表示を確認。
  optional欠如時の無効化とcamera保持可能範囲も記録する。
- [ ] 穴・不連続・退化geometryで誤faceを作らないことを数値fixtureで確認。
- [ ] 初回だけderived生成、同条件reuse、条件差の別key、digest破損拒否、
  同時要求 / interrupted write、再起動後の永続mesh読込を検証。
- [ ] mode / color / view切替と旧Run読込でpredict回数が増えず、raw / JobResult hash不変。
- [ ] ネットワーク遮断下で保存Run閲覧・frontend assets・3D操作を確認。
  明示CPUの準備済みMoGeでInference完了→Resultsの利用可能モードをsmokeし、
  GPU未検証とbrowser / OS / 容量上限を別記する。

全項目成功で02C exit。旧Runの3D unavailableは契約上正常。
未提供optionalを捏造せず、モード機能自体はfake geometryで検証する。今回は未実行。

## Known risks

browser memory / WebGL制約、texture転送量、normalized K誤変換、camera state API制限、
discontinuity閾値による面欠損、cache collision / race、offline時の外部JS要求。
容量上限・LODはrawの保持と表示処理を分けて実測で決める。

## Decisions / Deferred decisions

遅延生成・永続保存・digest条件reuse・raw / JobResult不変・自動削除なしを採用。
明示再生成と履歴/削除操作は02D。library名 / 版、export format、mesh閾値、camera保持範囲、
大規模geometry限界は実装前の技術検証で確定。高度な編集・解析は別Phaseの承認対象。
