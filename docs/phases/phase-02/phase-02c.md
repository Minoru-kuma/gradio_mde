# Phase 02C — 3D Results Viewer

Status: **COMPLETE / 全Exit達成（2026-10-27）**。Phase 02の内部milestone。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
全Exit達成後のcommit / main通常pushまで承認。02D以降は未承認。

## Goal / Background

保存した推論成果物をResultsタブで2D / 3D閲覧し、再推論なしでデモできるようにする。
モデル由来raw geometryとviewerで生成するderived artifactsを区別する。
旧01A Runはdepth-only。02Aのnative geometry Runと、3D情報が不足する旧Runをともに扱う。

## Scope / Non-goals

Resultsに **Depth | RawDepth | Point Cloud | Mesh**。保存Run ID読込、実行条件・計測表示、
回転・zoom・pan、色 / mesh表示切替、derived meshの遅延生成・永続保存・再利用。
高度な3D編集・解析、再推論、モデル名専用viewer、Run管理UI、他モデルは対象外。

## Dependencies

02A / 02B exitと02C実装承認。
[Run Directory](../../run-directory-spec.md)、[Run Management](../../run-management-spec.md)。
02Cでderived storage / generationの最小共通serviceを用意し、02Dで明示管理操作を追加する。

## Implementation tasks

- [x] Depth: colormapと表示normalizationをraw値から分離。unit / scale / invalid pixel、
  colormap範囲を表示し、NaN / all-invalid / 定数depthを安全に扱う。rawを書き換えない。
- [x] RawDepth: shape / dtype / min / max / 有効画素数・割合を表示。
  min / maxはfinite-positiveかつ保存maskの有効値のみ、空ならunavailable。raw .npyをdownload。
- [x] Point Cloud: 保存pointsを優先。回転・zoom・pan、RGB color / Depth color / Normal colorを
  動的に切替。RGBは記録したinput→output grid対応、normal色はorientationを明示。
  欠如するnormal色は理由付きで無効化する。推定normalをnativeとして表示しない。
- [x] points欠如時はcamera model / depth_kind / K等で変換が定義できる場合だけ共通back-projection。
  生成pointsはderivedとして記録し、camera情報が不足する旧depth-only Runは3D unavailable。
  仮のK・metric scale・poseを補わない。
- [x] Mesh: モデル由来dense pointsを優先し共通grid triangulation等で生成。
  invalid vertices、mask境界、深度不連続、退化facesを除外し、thresholdの単位・相対基準を記録。
  RGB textured / Geometry / Wireframeを動的切替。texture対応不能なら理由付きで無効化。
- [x] 初回mesh表示要求で遅延生成。Runに関連付けて永続保存し、algorithm名/版、parameters、
  入力artifactのdigest、attempt / view、frame / unit / scale、出力digestを別manifestに記録。
  同条件を再利用し、partial / corrupt cacheは成功扱いしない。JobResultは変更しない。
- [x] model成果物とderivedをUIラベル・manifest・保存領域で区別。
  downsampling / 表示LOD / texture生成もrawを変更せず条件を記録する。
- [x] viewerは保存されたframe / unit / scaleを維持し、初期表示cameraをboundsから調整。
  renderer軸変換が必要なら表示層だけの可逆変換を明示し、artifactは変更しない。
  Point Cloud / Mesh間のcamera stateを可能な範囲で保持し、不可なら制約とresetを説明する。
- [x] terminal Runはアプリ再起動後Run IDだけで再表示し、モデル環境・weightsを要求しない。
  runtime / GPU memoryは保存された値・単位・scopeのみ表示、欠如はunavailable。
- [x] 3D libraryを技術検証してpin。browser WebGL、point容量、mesh / texture / wireframe、
  camera state、Gradio統合、license、ローカルasset配信・CDNなしoffline動作を比較して決定。
  Python側生成・ブラウザ描画を分離し、採用可否を固定版の小fixtureで確認する。

## Tests / Exit criteria

- [x] depthの数値統計・invalid・normalization、各geometry / color欠如、
  RGB grid対応、標準frame / scaleをsynthetic fixtureと既知cameraで検証。
- [x] browserで4モード、Point Cloud / Meshの回転・zoom・pan、3種colorと3種mesh表示を確認。
  optional欠如時の無効化とcamera保持可能範囲も記録する。
- [x] 穴・不連続・退化geometryで誤faceを作らないことを数値fixtureで確認。
- [x] 初回だけderived生成、同条件reuse、条件差の別key、digest破損拒否、
  同時要求 / interrupted write、再起動後の永続mesh読込を検証。
- [x] mode / color / view切替と旧Run読込でpredict回数が増えず、raw / JobResult hash不変。
- [x] ネットワーク遮断下で保存Run閲覧・frontend assets・3D操作を確認。
  明示CPUの準備済みMoGeでInference完了→Resultsの利用可能モードをsmokeし、
  GPU未検証とbrowser / OS / 容量上限を別記する。

全項目成功で02C exit。旧Runの3D unavailableは契約上正常。
未提供optionalを捏造せず、モード機能をfake geometryと実CPU native Pointsで検証済み。

## Known risks

browser memory / WebGL制約、texture転送量、normalized K誤変換、camera state API制限、
discontinuity閾値による面欠損、cache collision / race、offline時の外部JS要求。
容量上限・LODはrawの保持と表示処理を分けて実測で決める。

## Decisions / Deferred decisions

遅延生成・永続保存・digest条件reuse・raw / JobResult不変・自動削除なしを採用。
明示再生成と履歴/削除操作は02D。library名 / 版、export format、mesh閾値、camera保持範囲、
大規模geometry限界は実装前の技術検証で確定。高度な編集・解析は別Phaseの承認対象。

## Acceptance evidence — 2026-10-27

実装契約・renderer比較・storage schema・起動/操作/制限は [Results Viewer](../../results-viewer.md)。
開始時main = origin/main `9954b777eef66475015c27da06263679a0b438ed`、作業ツリーcleanを確認した。

| 区分 | 結果 |
| --- | --- |
| Baseline | 55 tests / 264.542秒、53成功・opt-in browser 2 skip |
| 最終fake / contract全体 | **65 tests / 290.527秒、61成功・opt-in browser 4 skip**。既存55 + numeric / service 8 + browser定義2 |
| 02C fake browser / offline | **1成功 / 87.308秒**。4モード・3色・3mesh表示・RGB texture実pixel描画・回転/zoom/pan・camera保持/reset・raw download bytes・load完了・空ID案内・再起動reuse・optional無効化 |
| 02C native MoGe CPU / offline | **1成功 / 51.529秒**。明示outputsでInference→4モード→モデル環境なし再起動読込 |
| 02B fake browser回帰 / offline | **1成功 / 29.257秒**。2session・同時submit 1受理1busy・cancel・timeout・failure・Results分離・queue join 0 |
| CLI互換 | 旧01A / 02A / 02B / 新CPUの4Runを各2回collect、全file hash / mtime不変 |
| 環境 / 静的 | application pip check成功、29 Python AST / 28 Markdown・199 local links / anchors / fences / JSON / TOML / JS syntax / diff whitespaceを確認 |

opt-in 4件のうち上記02C 2件と02B fake 1件を別実行。02Bの旧depth-only実CPU UI testは今回再実行せず、
02B完了証拠を保持する。今回の実CPU検証は**native Points等を明示要求した新Run**で行った。

### Numeric / storage contracts

- finite-positive + 保存maskの統計、NaN / Inf / negative / 定数 / all-invalid、raw不変を数値fixtureで確認。
- 既知pixel K（skewあり）とz_depth / ray_distanceで投影roundtrip、標準frame / relative arbitrary尺度を確認。
  記録したidentity gridからのRGBサンプリングとnative normal orientationも確認した。
- 穴を含むcell全体の除外、depth discontinuity・長辺・退化面の除外を数値assertionで検証。
- 同条件6同時要求で生成1回、条件差で別key、再起動後reuse・mtime不変、出力digest破損・
  不正manifest・complete manifest欠落・derived内symlinkを拒否。atomic rename中断のpartialはreuseせず保持する。
- Native Point Cloudまでderived領域なし、初回Meshだけ生成、その後は同条件generationをreuse。
  raw / WorkerResult / JobResultにrefを後付けせず、全原本のhash / mtimeを保持する。

### Real CPU native geometry

最終Run: **`cf867c2d-6591-4962-9e77-504cef5013c3`**、COMPLETED / exit 0 / device=cpu。
`requested_outputs=[depth, points, normals, intrinsics, mask]`。
MoGe-2 ViT-S Normal、固定upstream / checkpointは02Aと同一。
`force_projection=False`のnative Pointsを正式worker経由で保存した。

- depth float32 `[256,256]`、65,536 valid、metric m / z_depth、0.8110444–4.2878127 m。
  points `[256,256,3]` / m、points.zとdepthの最大差 **0 m**。GT精度評価ではない。
- depth SHA-256 `ada9a6dcc0a776c6277195c4dd362b9600ea61e8d665b0d3c2bbfb492a9e6ab4`。
  native Normals / Intrinsics / effective mask / model maskも保存・既存契約で再検証した。
- grid-triangulation v1から **124,848 faces**。RGB textured / Geometry / Wireframeを確認。
  geometry NPZ SHA-256 `eed485eb91bae8c48c0de034e930143dac578a8866e9ebfa1f99f4eb2bda5fea`。
  NPZ生成物はGit管理外。textureとUVは入力RGB/gridからの表示payloadで、manifestに依存条件を記録する。
- Python 3.11.14 / torch 2.6.0+cu124 / torch CUDA runtime 12.4 / cuda_available=false。
  load 7.119887秒、predict 5.197403秒、worker 12.960536秒。scope / unitsは保存JobResultのまま表示する。
  CPUのためGPU memoryはunavailable。CUDA実行・driver互換は未検証。
- predict logは1回。モード/色/mesh表示切替・再読込・再起動・CLI collectで再推論しない。
  モデル環境・weightsを使わない新Backend / controllerから保存Run IDだけでDepth / Meshを再表示した。
- `source_digest=2b1908f39e709f4f41f2d3d815dce7ea493af1f3fc8c8c069002b86c3792d262` が
  最終production Python / model sourceと一致。frontend filesのhashもローカル証拠に記録した。

先行CPU Run `c1698519-1a0b-40fc-a487-0559ffd51176` も成功（54.843秒）。最終Runとは区別する。
旧Run再collectは01A `9c5b6556-30d3-43ae-827f-7bd8b0a47580`、
02A `a2c9ca5a-4eb7-4697-b880-8041e7749bae`、02B `799d2355-c57b-4552-92c4-644a7f25e775` と最終Run。

### Browser / offline / capacity

- Linux x86_64、application Python 3.13.13 / Gradio 6.30.0 / NumPy 2.5.4 / Pillow 12.3.0。
  Chrome **154.0.8037.92** / Playwright 1.58.0、WebGL 2.0 / ANGLE Vulkan SwiftShaderで確認。
  headless検証では `--enable-unsafe-swiftshader` を使用。hardware GPU描画・他OS/browserは未検証。
- Three.js **r180 / 0.180.0** のlocal module / OrbitControls / MIT LICENSEを同梱。
  browser console/page error **0**、external HTTP要求 **0**、推論queue join **0**。
- Python application / Conda / workerの非loopback socketをaudit guardで遮断し、Chromeの
  非loopback HTTPもrouteで遮断した状態で、準備済みweightsの推論・frontend・3D操作・保存Run読込が成功。
  これはtest用egress遮断でありOS全体のfirewall検証ではない。新規download不要、CDN依存なし。
- 保守的なviewer上限 **262,144 output pixels**。512×512 fixture（1 invalid）で
  **262,143 points / 522,240 faces**を表示・回転/zoom/panした。513×512は理由付きで拒否し、
  rawを保持、derivedを生成しない。最大WebGL容量の測定ではなく、この固定環境での受入上限。
- cameraは同RunのPoint Cloud↔Mesh / 色 / mesh表示 / 2D経由で保持。別Run・browser再読込はbounds reset。
  optional normal / RGB / texture欠如を理由付き無効化、depth-onlyの3D unavailableは正常契約。
- 途中の技術probeでは固定版Gradioのasync IIFE / 1引数server function対応を修正。
  browserテストのcanvas viewport / selector / option無効属性の確認方法も修正し、最終実行はすべて成功。
  一部起動処理のasyncio `ResourceWarning: unclosed event loop` はログに保持（原因未特定）。
  browser errors・機能不成功は残っていない。upstream CPU autocast警告は既存通りstderrに保存する。

ローカル証拠: `.local/validation/02c-{suite,fake-browser,cpu-browser-final,02b-browser-regression}.log`、
`02c-compatibility.json` / `02c-cpu-evidence.json` / `02c-final-assets.json` / `02c-static.json` /
`02c-offline-sockets.log` / `02c-cpu-mesh.png`。Run・weights・環境・ログはcommitしない。

再実行（browserはlocalhost server / Chrome実行権限が必要）:

```bash
PYTHONPATH=src .local/envs/mde-ui/bin/python -m unittest discover -s tests -v
MDE_BROWSER_TESTS=1 MDE_TEST_DENY_EGRESS=1 PYTHONPATH=tests/fixtures/offline:src \
  .local/envs/mde-ui/bin/python -m unittest tests.test_results_browser.FakeViewerBrowserTests -v
MDE_UI_CPU_SMOKE=1 MDE_TEST_DENY_EGRESS=1 PYTHONPATH=tests/fixtures/offline:src \
  .local/envs/mde-ui/bin/python -m unittest tests.test_results_browser.CPUViewerBrowserTests -v
```

**02C COMPLETE、Phase 02 IN_PROGRESS、02D以降NOT_STARTED / 未承認。**
GPU / 精度 / 他OS / 他browser / 262,144超の表示 / multi-process調停 / 学会実演は未検証。
02Dの履歴・export・再生成・archive・削除は実装していない。remote再確認後にcommit / mainへ通常pushする。
