# Development plans

## Current authorization and status

- Current work: **Phase 03 — 03.1 / 03.2受入完了、03.3以降未着手（2026-11-11）**。COMPLETEではない。
- Authorization: 2026-11-11のユーザー指示により03.1〜03.6を順番に実装・独立環境構築・検証。
  各段階の受入成功後にcommit / 同名remoteへ通常pushし、結果と残課題を報告する。
  `codex/phase-03-implementation`をPhase 03完了まで継続使用する。
- Phase 00 / 01 / 01A / 01B / 02A / 02B / 02C / 02D / Phase 02 COMPLETE。
- PR作成・main統合・Phase 04–08、Tracking / Benchmark / Slurm / queue / active recoveryは未承認。
- Start evidence: fetch成功。最新origin/mainは `e22322d5acc8ce7603b38d36311fc39ea56f6135`
  （Phase 03計画PR #2統合）。開始時の計画ブランチはcleanでmainとtree差分なし。
  最新origin/mainから指定の実装ブランチを作成。競合・範囲外差分なし。
- 正本: [AGENTS.md](AGENTS.md)、本計画、[Phase 03](docs/phases/phase-03.md)、関連仕様。
  以下の2026-11-09の計画限定承認と02D以前の承認状態は当時の履歴として保持する。
- main直接編集・commit、force push禁止。remoteの追加更新・競合・範囲外変更は停止・報告。

## Phase 03 implementation record — 2026-11-11

- Purpose / scope: 既存MoGe / CLI / Gradio / 旧Run / raw不変を維持し、下記03.1〜03.6を順次実装。
  新モデルの採用はimmutable upstream / checkpoint・digest・license・CPU根拠を確定してから行う。
  根拠不足・互換性問題・外部障害は停止して報告し、未達gateを飛ばさない。
- 03.1変更順: baseline suite / browser → metadata-only discoveryと診断 → manifest scalar schema検証 →
  実効variant / environment選択の共通化 → Runner / CLI / 現行controllerへ適用 → fakeと既存回帰。
- 03.1設計: variantのcapabilities / parameter_schema / devices / dtypes / input_constraints /
  environment_refsは項目単位で全体置換、未指定のみmodel値へfallback。元manifest / variantは保持。
  複数environmentは明示ID必須、1候補は従来fallback。conditional説明文は実行せず、
  statusで事前検査、出力の欠如は既存workerで拒否。runtime能力照合は後段03.4で追加する。
- 検証: directory追加の第2fakeを同一Runner / Backendで順次実行、import境界・不正manifest・
  duplicate IDs・variant差異・未準備環境を検証。既存suite / opt-in browser、明示MoGe CPU CLI、
  旧Run読込のhash / mtime不変を記録。GPU / 新モデルはこの段階の検証に含めない。
- Risks / rollback: discoveryによる不正pluginの巻込み、variantの暗黙merge、曖昧な環境選択を拒否。
  新schema major / geometry profileは03.1では追加しない。旧Runへのmigration / 上書きなし。
  環境・weights・runsはGit管理外。段階単位の修正commitで戻し、force pushしない。
- Completed / remaining: 実装ブランチ作成、正本確認、承認状態更新。03.1受入完了、03.2〜03.6未着手。

### 03.1 acceptance evidence — PASS

- 実装: metadata-only discovery / diagnostics / duplicate ID拒否、manifest scalar schema検証、
  実効variant全体置換とenvironment選択、Runner / CLI / 現行controllerの共通解決。
  adapter / worker protocol / serialization profilesは変更せず、新実モデルはまだ追加しない。
- fake: `tests/fixtures/models/alternate/`のdirectory追加だけで発見・実行。
  fake → alternate(depth + mask) → alternate別variant → fakeを同一Runner / Backendで成功。
  parameter / capability / environmentの切替、選択adapterだけのimport、新instance collect不変を確認。
  未登録profile / 未作成Conda prefixの失敗を不正manifestと区別し、自動installしないことを確認。
- 実MoGe + fakeの同一instance検証: `6e2d58ec-6101-45a7-aa2f-1c220b3302b8` →
  `3b594338-702a-4781-81a8-ab436fe651b6`、両方COMPLETED / 新instance collect hash・mtime不変。
  一時registryに既存MoGe directoryと追加fake directoryを置いた検証。
  このfixtureは既存単一checkpoint設定を共有し、model / variant別weights mapは03.3で追加予定。
- 最終production sourceでMoGe CLI CPU: `a9ed78c0-314e-49cf-aec2-05fd4a1e12e1`、
  source_digest `2e9c296bd71caba77196eebbcee4a71e1a1ee6f5d80124781e6f8ece5397a933`一致。
  Python 3.11.14 / torch 2.6.0+cu124 / CUDA runtime 12.4 / cuda_available=false / cpu。
  depth float32 [256,256] / z_depth / metric / m、65,536 pixel有効。
  同一入力の01A Run `9c5b6556-30d3-43ae-827f-7bd8b0a47580`とmax absolute error=0。
  実行と数値回帰の証拠でありmetric accuracy評価ではない。
- 旧Run 4件（01A depth-only、02C geometry、JPEG、02D）を各2回CLI collectし全fileのhash / mtime不変。
  01B履歴Run `f4a2052f-71da-4664-9c9f-281cca95fb41`はローカルdirectoryがなく未検証。
  01B形式の互換性は既存contract fixtureでも検証する。
- browser: 既存5件成功（231.693秒）。Python非loopback / DNSとbrowser外部HTTP遮断下で
  MoGe CPU推論 / native Points・4表示・mesh / 再起動保存読込 / busy・cancel・timeout・管理操作成功。
  CPU UI Run `4026bcb2-e92b-4068-ae10-1e4edf15e110`、native Points Run
  `70f69f38-2473-4ede-b3fc-154204e8f8a4`（125,125 faces、predict 1回、raw不変）。
  Chrome 154.0.8037.92 / Linux / SwiftShader、外部requests・page errorsなし。
  browser検証中にregistryの不正JSON検査を強化したため、最終source一致の実推論証拠は上記CLIを使う。
- baseline: control Pythonの初回suiteはNumPy不在で6 errors / 29 skip。
  origin/mainの隔離sourceを独立UI環境で実行し88件中82成功 / 5 skip / 1 failure（266.924秒）。
  4秒timeoutがfixture子processのreadiness前に終了した。単独再実行1成功（4.268秒）。
  baseline browser 3件成功（187.534秒）。変更後の初回suiteも同じtimeout fixtureだけ失敗
  （97件中91成功 / 5 skip、364.042秒）。
  テストのbudgetを10秒へ変更し、submitから15秒以内にstatus pollingなしでTIMEOUT・子process停止を
  確認する方式を維持。productionのtimeout動作・既定値は変更していない。最終固定sourceのsuiteは
  **100件中95成功 / opt-in browser 5 skip（206.751秒）**。browser 5件は上記別実行で全成功。
- 静的検証: Markdown 28件 / local links・anchors 224件 / Python AST 35件、errors 0。
  `git diff --check`成功。GPU・新モデル・新しい独立環境・他OS/browserは未検証。
- 03.1受入条件達成。commit / 通常push後に03.2の代表variant・依存・checkpoint / license根拠確認へ進む。
  終了前fetchでorigin/mainは開始時の`e22322d5acc8ce7603b38d36311fc39ea56f6135`のまま。
  ローカル証拠は`.local/validation/phase-03*`、生成Runと同様Git管理外。

### 03.2 implementation plan and adoption investigation

- 03.1 commit / push: `9e87189bb15ca09d6a627fae617b7e9499ddf4e7`、同名remoteと一致、clean tree。
- 候補: DA3-SMALL、公式source `3d835ec1a5802d64a8b8b15f817a1ab54809bfe4`をGit管理外へ取得。
  checkpoint `depth-anything/DA3-SMALL` revision `e08cab65ca0ec38e7826075418411ab90cab4da3`。
  model.safetensors 137,248,940 bytes、Hub LFS SHA-256
  `364492e38a3a06d221ac75da7f6621ada3f2361cd24fde11ba79091e9f40efcf`。
  config.json SHA-256 `a486e29e82b7ab4a7d4cefc1ea4526cfe2ae438a572c8ca98917cfbcde7447d2`。
  source / model cardはApache-2.0表記。現時点では採用候補、CPU実動作は未確認。
- 根拠: 固定sourceのapi.pyは入力processor → native network → output processorを使用。
  上位forwardはautocastを強制し、API importはexport / pose alignment依存も読み込む。
  float32 / depth-only専用経路として公式のconfig constructor・InputProcessor・native networkを
  直接使用する案を確認する。upstreamをpatchせず、モデル固有処理はmodels/da3内だけに置く。
  固定GLB exporterのinverse-K ray × depthはz-depthの根拠。SMALLのscaleはrelativeとして扱い、mを付けない。
- 手順: import graph / checkpoint構造確認 → 依存・native呼出し採用決定をdocsへ記録 →
  独立Conda prefix `.local/envs/mde-da3`へ固定依存を構築 → plugin / manifest / checkpoint準備script →
  GPU不要契約・CPU正式CLI E2E・新instance再collect・hash / mtime不変 → 既存回帰 → commit / 通常push。
- 検証: 1 PNG / 明示CPU / float32 / depth-only。native depthのshape / scale / frameと保存値を照合。
  source revision / checkpoint hash・logs / unload / runtime / source_digestを記録。
  optional出力は03.4まで宣言を限定。multi-view実行・新UIは03.3以降。旧Run / MoGeを保持する。
- Risks / rollback: CPU未対応、依存のimport時必須化、checkpoint key対応、preprocess grid、resource不足。
  根拠不足や外部障害では停止・報告する。base / system / MoGe / UI環境を変更しない。
  新pluginとGit管理外の専用prefix / weightsだけを追加し、既存rawを変更しない。
- 未実施: 新環境構築、weights本体取得、production plugin、新実モデル推論。03.3〜03.6未着手。

### 03.2 selected native integration (before implementation)

| Decision | Reason / evidence | Trade-off | Future extension |
| --- | --- | --- | --- |
| DA3-SMALLの上記固定source / weightsを代表variantとして採用 | 公式source / Hub Apache-2.0、weights 137 MB、native SDPA実装、model cardにCPU選択例。CPU実動作はこれから確認 | metric scaleなし、GPU保証なし | 他variantは別検証 |
| 公式InputProcessor + config constructor + DepthAnything3Netのfloat32経路 | 固定api.pyの呼出し順・model/da3.py・dinov2/layers/attention.pyで確認。上位APIはexport群もimportしautocastを強制する | 上位API全機能は利用せずnative構成・state keysを厳密照合 | confidence / pose等は03.4 |
| checkpoint directoryにmodel.safetensorsとconfig.jsonを事前配置 | 両方の固定digestをworker load前に検証、Hub configと採用source configも照合する | local checkpoint引数はこのpluginではdirectory | model別path mapは03.3 |
| 独立CPU環境 Python 3.11.14 / torch 2.6.0+cpu / torchvision 0.21.0+cpu | upstream Python範囲内・torch>=2、SDPAはPyTorch実装。MoGeの環境は変更しない | GPU実行はこの環境では非対応、他OS未検証 | GPU環境は別検証 |
| process_res既定252・upper_bound_resize、depth-only / relative / arbitrary | native patch size14に整合するCPU smoke設定。公式GLB exporterは整数pixelのinvK ray×depthを使用 | 元RGBのidentity対応を主張せずK / pointsを補わない | grid / optional拡張を03.4で検証 |

環境は上記案の依存解決・import・実CPU検証が必要。成功するまで03.2 PASSにしない。

### 03.2 shared tensor checkpoint finding

最初のCPU Run `aae4f709-fdaa-47de-892e-978c68e5ed51`はloadでFAILED。
`load_file` → prefix除去 → PyTorch strict state_dictではaux head LayerNormの6別名をmissingと判定した。
推論 / depth保存には進んでいない。固定sourceのdualdpt.py L132–148は同一LayerNorm objectを
4箇所へ登録し、実際の`is`比較でも同じparameter objectであることを確認。
checkpointのSafetensors metadataも6 alias → 保存されたindex 0の対応を持つ。
[公式Safetensors仕様](https://huggingface.co/docs/safetensors/torch_shared_tensors)と
導入済み0.5.3のload_model sourceで共有storage検証・真正な欠落拒否を確認した。

Decision: prefixを除去せずnative modelを`model` childに持つ薄いnn.Moduleで包み、
公式`load_model(strict=True, device=cpu)`で読込。Reason: native共有parameterとcheckpointの構造を保持。
Trade-off: plain state_dict読込は使用しない。Future extension: 他variantも同じ厳密読込と個別検証を行う。
ランダム補完・alias tensor複製・missingの無条件無視・upstream source変更は行わない。
この確認は互換性調査であり、CPU E2E成功はまだ未確認。

### 03.2 acceptance evidence — PASS

- 代表variant: DA3-SMALL、上記source / weights pin、Apache-2.0、native float32 / 明示CPU。
  追加はmodels/da3だけでproduction registryに発見。core / UI / backendの変更なし。
- 独立Conda prefixをenvironment.ymlから新規構築し、固定sourceを--no-deps install。
  native configとHub config一致、34,299,463 unique parameters。不要なAPI / exporter / MoGe / UI importなし。
  Python 3.11.14 / torch 2.6.0+cpu / torchvision 0.21.0+cpu / CUDA runtimeなし。
  requirements.lockに今回の推移依存とsourceを記録。lockによる再作成は未検証。
- 正式CLI → Runner → LocalBackend → 専用workerのCPU Run
  `541dcd67-8153-48b1-a1d4-9063b79e1435` COMPLETED。
  float32 [252,252]、z_depth / relative / arbitrary、63,504 pixel有限・正。
  source_digest `6f24fb9f3f5f613a5ba94ebb660e38c57ad5561ed57c9a1bbe765645bb8b0073`一致。
  native autocast無効、depth-only既存profile、stderr空・exit 0・predict 1回・unload完了。
- Python非loopback socket / DNS遮断下の正式推論成功。OS全体・native独自通信遮断を保証するものではない。
  新Backendと新CLIで各2回collect、全file hash / mtime不変。Condaなしの保存結果読込も確認。
- 共通ResultsServiceのDepth / RawDepth表示、Point Cloud / Meshの理由付きunavailableを確認。
  K / Pointsを補完せず、表示後もraw / 確定result含む全fileのhash / mtime不変。
  旧4Runの各2回CLI collectとhash / mtime不変も再確認（01B履歴Runのdirectory不在は継続）。
- plugin契約5件成功（1.289秒）、共有aliasを正しく読込し真正な欠落は拒否する数値fixtureを含む。
  最終既存全回帰は**105件中100成功 / opt-in browser 5 skip（154.074秒）**。
  core / UI / backendは03.1以降不変のため、browserは03.1の別実行5成功を証拠とし03.2では未再実行。
  新モデルのbrowser操作・切替は03.3の受入対象。静的リンク / AST / JSON / diff検証も実施。
- 未検証: process_res=504、GPU / 他OS、lock再作成、native optional、multi-view、UniK3D。
  03.2受入条件達成、commit / 通常push後に03.3へ進む。Phase 03全体はExit未達。
  初回のshared alias読込失敗と解決根拠は前節に保持する。

## Phase 03 investigation and staged design — 2026-11-09

### Purpose, scope and evidence

目的は既存MoGe / CLI / 保存Runを保ったまま、model directory追加で複数モデルを
共通Runner / Backendから実行できる契約を設計すること。**本節は設計案であり実装済み仕様ではない。**
今回変更するのは本計画とphase文書の状態・計画参照、およびAGENTSの承認範囲・commit / push方針。
実装は改めて指示を受けて開始する。

調査基準は上記main commit。参照した契約は
[Architecture](docs/architecture.md)、[Model adapter](docs/model-adapter-spec.md)、
[Environment](docs/environment-strategy.md)、[Execution](docs/execution-backend-spec.md)、
[Run Directory](docs/run-directory-spec.md)、[Gradio](docs/gradio-inference.md)、
[Results Viewer](docs/results-viewer.md)、[Run Management](docs/run-management-spec.md)。
先行する将来設計と末尾の01B / 02A / 02B実装契約を区別してコードと照合した。

| 対象 / 確認箇所 | 実装済み・単一モデル前提 / 不足 | Phase 03の変更案 |
| --- | --- | --- |
| `src/mde/registry.py`: `ModelRegistry.get_model` | 指定directoryのmanifestだけを読む。adapter非importは成立。ID形式・一致・entrypoint・majorの検査はあるが一覧探索、全manifestの重複検出、詳細schema検査はない | metadata-only discoveryと一覧API。model / variant ID重複、default参照、schema subset、environment参照を検査。環境未準備とmanifest不正を区別 |
| `contracts.py`: `ModelInfo.variant`、`runner.py`: `submit` | モデルIDは既に汎用。capabilityはvariant優先だがparameters / devices / dtypes / input constraintsはvariant解決が不十分。environmentは常に先頭 | 共通の実効variant metadata解決をRegistry / Runner / UIで共有。単一環境の従来fallbackを維持し、複数候補は明示選択・曖昧なら拒否 |
| `ui.py`: `build_app/main`、`ui_controller.py`: `InferenceController` | 起動時1モデル固定、Model欄は非編集Textbox。controlsは初期schema、outputsはvariants[0]で固定。controllerのmodel_id / infoは共有 | model選択とvariant変更でschema / choicesを再構成。選択model / parametersをsession別に保持しsubmit時にsnapshot化。共有controllerのmodel_idを書き換えない |
| `environments.py`: `WorkerManager`、UI / CLI composition roots | Resolver自体は複数profile対応。起動時は1環境のみ登録。checkpoint overrideはmanager全体の `MDE_CHECKPOINT_PATH` 1個 | target設定のlogical environment mapとmodel / variant別local weights map。実行jobごとに解決し他モデルへoverrideが漏れない。adapterにhost設定を持たせない |
| `worker.py`: `execute`、`LoadedModelInfo` | 選択entrypointだけをimportしload / predict / unload。返されたruntime capabilitiesは共通preflightで照合・保存していない。欠落optionalはserialize段階で拒否 | manifest宣言とruntime能力を照合しpredict前に要求可否判定、実出力presenceも検証。実効能力と理由を結果へ保存 |
| `contracts.py`: `PredictionRequest/Batch`、`JobSpec.from_dict` | BatchはlistだがRequestはimage / view_id単体。Jobはinputs=1 / view-0001 / attempt-0001、cpu・cuda:0 / float32を強制 | 最初は1viewとdevice / dtype制限を維持。後段で入力view listとscene metadataの互換方式を設計し、multi-view契約をfixtureで通す |
| `contracts.py`: `OUTPUT_NAMES`、`worker.py`、`geometry.py` | depth / points / normals / intrinsics / maskのみ保存・検証。rays / confidence / camera_poseはMDEOutputの型だけ。extrasはJSONとして渡すがtyped refsの専用検証はない。scene_metadataは保存しない | 新出力ごとに要求名・保存・値 / 意味検証・profileを一組で追加。typed extrasとscene情報のserializationも契約化 |
| `storage.py`: `validate_outputs/validate_job_files`、`geometry.py` | 固定1view path / outputs[0] / metadata views=1を検証。z / ray_distance、metric / relative / unknownは既に受理。Pointsとdepthの数値整合もある | depthの意味を新設し直さず再利用。新profileと後段multi-viewでID集合・per-view検証へ広げ、旧reader経路を保持 |
| `results.py`、`run_management.py` | Resultsは最初のviewを使用。native pointsを優先し、明示pinhole Kの場合のみderived逆投影。RGB / textureはidentity gridだけ。管理は共通collector / artifact inventoryを利用 | 初回はDepth / RawDepth中心、optionalなしを正常表示。新refsのexport / 再読込を監査。新モデルのresize対応不明ならRGBを無効のままにし、仮Kを補わない |
| `models/moge/adapter.py/manifest.json` | 固定MoGe v2 / metric scale head / float32専用。固有APIはplugin内に隔離済み。depth-onlyとPoints要求でforce_projectionが異なる | この制約はcoreの欠陥ではない。既存variant / pin / 引数 / checkpoint digest / native Pointsを維持。新世代は別variantとして後から検証 |

再利用する検証資産は `tests/test_local_contract.py`、`test_local_robustness.py`、
`test_geometry_artifacts.py`、`test_ui_controller.py`、`test_ui_structure.py`、
`test_results.py`、`test_run_management.py` とbrowser suites、`tests/fixtures/` のfake / geometry plugin。
過去の個別実行コードは今回未取得・未調査。必要時の参考とし、取得をE2Eのgateにしない。

外部の参考確認（2026-11-09、mutable main。採用pin・実機検証ではない）:
[UniK3D公式README](https://github.com/lpiccinelli-eth/UniK3D)はinferとcamera入力を示す。
[DA3公式API](https://github.com/ByteDance-Seed/Depth-Anything-3/blob/main/docs/API.md)は
view配列・optional confidence・w2c extrinsicsを示すが、返値説明の(N,3,4)と例の(N,4,4)に
相違がある。文書だけでshapeを断定せず採用revisionのsourceと実配列で確認する。
新モデルのdepthの意味・scale、CPU対応、依存・license・weightsは今回確定していない。

### Contract proposals and compatibility gates

1. **Manifest / discovery**: `models/*/manifest.json` の決定的な列挙とmetadata検証を追加する。
   未installでも発見可能。壊れたmanifestは診断として一覧で識別し、そのmodelのsubmitを拒否。
   重複IDは曖昧なregistryを作らず拒否する。runtime import / install / weights downloadは行わない。
   許可schemaは既存scalar型 / enum / bounds / defaultsを先に使い、実モデルで必要な条件だけ拡張。
   variantの上書き規則は明示し、parameter schemaは丸ごと置換を推奨（暗黙deep mergeしない）。
2. **Request / environment / weights**: model / variantの実効metadataを一度解決しJobSpecへsnapshot。
   logical EnvironmentRefはJobに、prefixとlocal checkpoint pathはtarget設定へ分離する。
   checkpointのrevision / digestはmodel_refに残しadapterで検証する。既存CLIの
   `--model moge --variant ... --checkpoint ... --conda-env/--conda-prefix` は単一job overrideとして維持。
   global環境変数の書換えでmodelを切り替えない。全sessionで1つのBackend・busy即拒否を維持。
3. **Capabilities**: supported / conditional / unsupportedとtested状態を別軸で管理。
   conditionalの条件文を評価コードとして実行しない。表現可能な条件は共通validatorで判定し、
   未解決条件はworker preflightへ渡す。runtime能力 / 欠如理由を記録し、要求した出力不足は失敗。
4. **Geometry / extras**: 既存depth必須、float32 / camera frame / 単位 / invalid規則を維持。
   raysはcamera model / grid / unit direction / validity、confidenceはnative meaning / range / direction、
   poseはc2w・world frame / reference view / translation scaleを必須の意味metadata案とする。
   raysの後方向・非正zを通常z-depthへ無条件変換しない。pose欠如をidentityで埋めない。
   extrasの未知JSONを保持し、typed refsはpath / dtype / shape / unit / digestを検証して保存・exportする。
   confidence / ray独自のvalidityとdepth maskの関係、poseの剛体性・invertibilityの許容差はfixtureで確定する。
5. **Version / profiles**: `01A-depth-only`（profileなしを含む）と `02A-geometry-v1` のreader / writerは維持。
   新出力は別serialization profile案で扱い、古いprofileの許可fieldを黙って変えない。
   optionalな加算で済むmanifest / metadataは同majorのminor案、必須項目・意味・Request signatureの
   破壊変更はmajor案とadapter移行手順を仕様化する。番号はまだ未決定。
   現行check_schemaは任意の1.xを受理するため、minor番号だけで旧worker互換とは主張しない。
   worker protocol / profileの対応確認とunknown profile拒否を試験する。新reader→旧Runの互換は必須、
   旧reader→新profileの読込は保証せず明示拒否とする。旧Runを書き換えるmigrationは行わない。
6. **Multi-view**: 初回single-view成功から独立した後段。入力IDの順序と集合の対応、重複 / 欠落 /
   未知view拒否、per-view artifact path、scene metadata / extrasのround-tripを必須とする。
   `PredictionRequest` にview listを加算し旧single fieldsを維持する案と、版付きbatch requestを
   追加する案を比較する。既存MoGeへ複数viewを渡さない。Job readerだけの制限解除で済ませず、
   worker / Store / metadata / export全経路をfakeで確認する。1attempt制約は解除しない。

これらは実装時にModel adapter / Environment / Execution / Run Directory / Gradio仕様へ
同時反映する。viewer / exportの意味やAPI変更を伴う段階ではResults Viewer / Run Management仕様も更新する。

### Recommended implementation order (2026-11-11に実装承認済み)

以下の03.1〜03.6はPhase 03内の作業区切り案で、承認済みの新phase名ではない。
各段階を小さなレビュー単位とし、先行段階の成功後に進む。初回E2Eへ全契約拡張を詰め込まない。

| 順序 | 変更対象と成果 | 受入証拠 / 次へのgate |
| --- | --- | --- |
| 03.1 既存経路の固定とdiscovery | Registry一覧・manifest検証・実効variant metadataを整理。既存MoGe + directory追加だけの第2fake pluginを同じRunner / Backendで順次実行 | import境界、重複 / 不正schema / 未準備環境、異なるparametersとcapabilities、既存MoGe CLI / 旧Run回帰。新出力・UI刷新を待たずfake E2Eを成立 |
| 03.2 第2実モデルのdepth-only E2E | 下記条件で代表variantを1つ選定・pin。plugin / environment / preparation docsを追加。既存CLI→Runner→Backend→独立worker→depth保存→新instance collect | 1 PNG / 明示CPU / 1variant。Run ID、実測runtime、depth_kind / scale / unit / shape、logs・cleanup・digest、再collectのhash / mtime不変。CPU不可なら原因・実行機材を確認し、CUDA要求をCPUへfallbackしない |
| 03.3 UIのmodel切替 | environment / weights mapを組み込み、session別model / variant / schema controls・requested outputsを更新。単一Runner / Backend共有 | 2browserで別model選択、同時submitは1受理1busy、未準備表示、切替後の古いcallback / parameters / checkpoint混入なし。既存2タブ・cancel / timeout / 保存Runを回帰 |
| 03.4 第3実モデルと必要optional | 残るmodelのdepth-only E2Eを先に成立。実モデルが必要とする順にrays / non-pinhole、confidence / pose / extrasを1契約ずつ追加 | 各新出力はfake数値fixture→worker保存→stdlib reader検証→実モデルで実出力照合。unsupported / 不要求の欠如は正常、要求欠落は失敗。仮K / native points捏造なし |
| 03.5 Multi-view契約 | 版 / adapter互換案を確定しinput list・ID mapping・scene serialization / Store / exportを更新 | fake 2viewで入力順序・出力ID対応 / 欠落 / 重複 / 不正refs、unknown extras round-trip。single-view MoGe互換。実モデルmulti-view UI / 評価は追加scopeであり必須にしない |
| 03.6 統合受入 | 3つの独立環境、代表variant各1つのsingle-view Local E2E、capability matrix・再作成条件を揃える | 下記回帰とphase正本の全Exitを照合。成功していないvariant / GPUをtestedとしない。Phase 03完了をPhase 04開始許可にしない |

第2モデルは**暫定的にDA3のsingle-view小型variantを先に評価し、UniK3Dを後にする案**。
既存1view depth契約で通せるかを先に確認し、non-pinhole / raysの拡張を初回成功から分けるため。
具体的variant / pin / CPU可否を確認した採用決定ではない。CPUでの依存・資源・license条件が
UniK3Dの方が適する証拠が得られれば順序を交換する。MoGe追加variantは3family統合後を推奨する。

### Verification, risks and rollback

- 実装前baseline: 既存unittest suiteと必要browser opt-inを実行し環境 / skip理由を記録。
  各段階では変更境界のcontract tests、受入時には既存全回帰を行う。
- GPU不要: fake pluginのdirectory追加だけでdiscovery / submit / collect、新旧manifest互換、
  unsupported / conditional / runtime欠落、scalar型 / 非有限値 / unknown parameter、
  adapter非import、選択workerのみimport、環境 / checkpointの交差混入なしを検証する。
- 幾何fixture: z vs range、metric vs relative、non-pinhole / 負z ray、normalized Kの画素中心、
  w2c→c2w、mask / invalid、confidenceの意味、poseとscene scale、typed extras / view ID、
  unknown major / profile、corrupt dtype / shape / path / symlink / digestを検証する。
- 互換性: 旧schema 1.0 / depth-only / geometry / JPEG Run、CLI既定・flags、native Points、
  4表示・derived再利用・履歴 / export / archive / 削除確認、busy / cancel / timeoutを回帰。
  saved Runsのraw / WorkerResult / JobResult hash・mtime不変とpredict回数を確認する。
- 実機: 固定MoGe明示CPUを回帰し、新モデルも各single-viewの正式worker経路を実測する。
  過去証拠は当時の成功であり今回の実行成功ではない。GPU・依存再作成・offlineは実施した条件だけ報告。
  事前準備後のoffline推論 / browser / 保存Runを確認し、自動download / installしない。
- リスク: upstream出力解釈、巨大weights / CPU memory、native extension、依存衝突、
  schema変更による旧Run拒否、UI切替race、global checkpoint漏れ、non-identity RGB誤対応。
  追加geometryに旧profileを流用せず、旧readerと固定MoGe経路を先に回帰する。
- Rollback: 今回は計画文書のみの差分。将来は段階ごとに追加plugin / UI切替 / 新profileを
  独立して戻せる変更単位とし、既存Runや確定resultの移設・上書き・自動削除を伴わせない。
  環境 / weights / runs / credentialsはGitへ追加せず、base / system Pythonを変更しない。

### Decisions and items to settle

| Decision / 提案 | Reason | Trade-off | Future extension / 判断時点と必要証拠 |
| --- | --- | --- | --- |
| directory manifest discoveryを先行 | 既存plugin境界を活用 | 外部package配布をまだ扱わない | package entrypoint / hot reloadは将来。今回はsource checkout |
| depth-onlyの第2実モデルを最初の実E2Eにする | 小さな成功を優先しMoGeを保つ | optional全対応は後続 | 実装前にvariant / immutable source・weights revision / SHA-256 / license / CPU依存と資源を確認して採用決定 |
| variant metadata共通解決、schemaは全体置換を推奨 | UI / Runnerの判定差を防ぐ | manifestに重複記述があり得る | 03.1前にfallback / override規則とconditionalの検証可能subsetを仕様確定 |
| target設定に環境・weights map | adapter / Jobへhost prefixを漏らさない | 設定形式が追加になる | 03.2〜03.3前にJSON等の形式・lookup key・既存CLI overrideの優先順位とdigest記録を確定 |
| UI model選択はsession別snapshot | 実行中のmodel / checkpoint混線防止 | controlsの再構成が必要 | 03.3前にmodel切替と実行中編集の扱い、staleイベント破棄規則を確定。read-only起動互換も確認 |
| 新optionalは別profile、番号未決定 | 旧profile検証を保つ | readerにprofile分岐が増える | 03.4前にfieldごとのvalidity / provenance・unknown refs保持 / 検証・対応worker versionを確定 |
| multi-viewはsingle-view成功後、Request互換方式未決定 | 旧MoGe adapterに破壊変更を押し付けない | fake contract段階が必要 | 03.5前にadditive fields vs versioned request、scene schema・pose基準view / scaleを決定 |
| 実装成功とcapability宣言を分離 | upstreamの対応と実測を混同しない | matrix管理が必要 | model / variant / output / device / environment別tested・conditional・untestedとRun証拠を記録 |

### Completed / remaining in this planning task

- 完了: main / clean tree確認、作業ブランチ作成、仕様とsource調査、単一モデル前提・契約差分、
  段階計画・受入条件・互換性・リスク・要決定事項の整理。
- 未実施: production実装、test追加、suite / browser / 実モデル推論、環境構築・weights取得。
  既存環境・weightsの現在の可用性は未確認。Phase 03の実装Exitは未達。
- 今回の検証: `git diff --check`成功。変更Markdown 2件のlocal links / anchors 34件と
  fencesを検証し成功。変更は本計画とPhase 03文書のみ。終了前の再fetchでもorigin/mainは
  開始時の `8a6d5082ecf64eb9b9bcb8c668c41c0c3f145333` のまま。
  上記は計画整理時点の検証記録。同日の追加指示によりAGENTSへ作業ブランチのcommit / 通常push方針を
  記録し、3文書の最終差分・リンク・fencesを確認後にcommit / 通常pushする。main反映は行わない。
  最終検証: 3文書のlocal links / anchors 44件・fencesと `git diff --check` 成功。
  実装着手には次のユーザー指示が必要。

## Phase 02D review continuation

- 承認: `codex/phase-02d-run-management` で実装・最終検証を継続。作業ブランチへの通常pushのみ。mainへの反映は禁止。
- 優先: Meshを3世代以上作成し最新を削除した後、残る完成世代のcreated_at / generation_id降順で検証・選択し、再起動後もreuseする。削除要求中・失敗partial・tombstoneは候補外。
- 検証: 選択pointer欠如 / 破損、最新 / 非最新削除、全世代削除、途中失敗と再試行、generation / export / delete競合、TOCTOU、2browser session、retry UI、既存browser全回帰。全破壊fixtureはtemporary Root。
- 手順: selector修正と安全性監査 → service / filesystem tests → browser retry / session tests → source固定で全suiteと既存browser → docs / Exit判定 → 作業ブランチcommit / push。mainには反映しない。

## Phase 02D implementation plan — 2026-11-05

- Scope: 共通serviceによる履歴 / 詳細 / metadata / archive / export / derived再生成・履歴 / 確認付き削除とResults UI統合。既存raw / JobResult / CLI互換を維持。
- Order: latest main・契約確認 → 安全な保存 / lock / active判定を設計 → serviceとviewer統合 → UI確認 / session境界 → 隔離Rootでfake・filesystem・競合・browser検証 → Phase 02全Exit監査 → remote再確認・全Exit時のみcommit / 通常push。
- Verification: 旧Run・sidecar欠如 / 破損、metadataによるraw不変、export選択範囲、再生成とtombstone、stale / active / symlink / traversal / partial failure / concurrent access、確認cancelと削除範囲、既存suiteとoffline再表示。
- Risks: 共有lockの欠落、別processや外部変更によるTOCTOU、部分削除、unknown active状態、export容量。単一process境界を明確化し不明時は拒否。破壊試験は隔離Rootのみ。全Exit未達ならCOMPLETE / main反映しない。承認済みの作業ブランチへの途中commit / pushは可能。
- 完了: Service / UI、3世代以上の選択・再利用、公開失敗 / 部分削除・retry、共有lock / TOCTOU / session分離、旧Run互換を検証。02D全Exit達成。
- 最終証拠: 固定production source全87件中82成功・opt-in 5 skip（322.291秒）、別browser5件成功（247.236秒）、追加2session browser成功（38.598秒）、追加generation / export競合1成功（5.392秒）。旧4Runのdetail各2回 / exportで全hash・mtime不変。
- 最終CPU Run `67d893e9-f399-4c9f-a7c5-405b52976a6f` / source digest一致、native Points / JPEG / 3D / 再起動・offline成功。GPU / 他OS/browser / 学会実演は未検証。全破壊fixtureは隔離Root。
- Phase 02全体もCOMPLETE。mainへは反映せず作業ブランチのみcommit / push。Phase 03以降は未承認。詳細は [02D evidence](docs/phases/phase-02/phase-02d.md#final-acceptance-evidence)。

## JPEG input improvement — 2026-10-28

- Scope: Gradio JPEG validation, EXIF transpose / RGB PNG conversion, original bytes and optional JobSpec provenance; preserve CLI and 02C COMPLETE.
- Order: validate owned upload → convert and record source / transformation → Runner saves both before submit → contract / regression and feasible CPU browser smoke → docs / remote check / commit / normal push.
- Validation: PNG byte identity, JPEG and EXIF orientation, corrupt / size / pixel limits, provenance and integrity, existing suite and browser smoke.
- Risks: decoder limits and malformed images, original / converted consistency, optional schema compatibility; preserve the PNG as the authoritative model input and retain source JPEG for reproduction.
- Evidence: 全67 tests中63成功・opt-in browser 4 skip（153.515秒）。最終controller 13成功。
  JPEG実MoGe CPU browser / offline 1成功（35.044秒）、Run `8f133a54-fc83-4467-9992-42d33e9c5885`、
  native Points / 4表示 / 125,125 mesh faces / restart読込、元JPEG digest一致、predict 1回、
  raw不変・外部HTTP / page errors 0。Linux / Chrome SwiftShader、GPU・他browserは未検証。
  初回browserはsandbox port制限、次回はtestのPNG固定filename assertionで失敗し修正後成功。
  suite実行中にowned copyのbounded readを追加し、変更対象controllerとCPU browserを再実行した。

## Phase 02C implementation plan — 2026-10-27（完了時点の履歴）

- Goal / scope: ResultsのDepth / RawDepth / Point Cloud / Mesh、保存Run再表示、
  RGB / Depth / Normal色、texture / Geometry / Wireframe、meshの初回遅延生成・永続reuse。
  空Run IDの入力案内と非同期load完了表示も改善。02D管理操作は実装しない。
- Order: latest main / source確認 → 承認・plan更新 → 既存suite baseline →
  固定版renderer比較と小fixture技術検証 → 共通numeric reader / derived service / renderer →
  fake・contract・browser・実CPU native Points・offline検証 → docs / Exit監査 → remote再確認 → commit / push。
- Contracts: UI環境のNumPy / Pillowのみで表示配列を作る。モデル分岐・torch importなし。
  保存frame / unit / scaleを維持、Kは明示pinhole / integer grid / depth_kind適合時のみ使用。
  RGBは記録したgrid対応がある場合のみ。raw / WorkerResult / JobResult / CLIを変更しない。
- Derived: canonical algorithm版・展開parameters・run / attempt / view・全使用入力digestと意味metadataをkey化。
  Run内別manifest、同条件lock、generation一時directoryからatomic rename。破損cacheを拒否。
  同条件reuse・条件差別key・interrupted publication・同時要求・再起動読込をfixture検証。
- Validation: baseline / 全既存回帰、数値fixture（invalid / all-invalid / constant / holes / discontinuity /
  degeneracy / camera / RGB）、browserの4モード・色・mesh・回転 / zoom / pan / camera保持、
  native Points等を明示要求するCPU MoGe UI Run、egress遮断下の推論・保存Run / frontend / 3D操作。
  predict回数とraw / 確定結果hash不変を確認し、GPU・OS・browser・容量限界を明記する。
- Risks / rollback: browser WebGL・memory、texture対応・K convention、cache破損 / race。
  追加viewer / derivedだけrevert可能、rawは保持。単一application process、multi-process調停は範囲外。
- Decisions: renderer名 / 版・mesh閾値・容量上限は技術検証で確定して仕様へ記録。
- Completed / remaining: 02C全Exit達成。下記completion evidenceを参照。02Dは未承認。

### Phase 02C completion evidence

- 全Exit達成で02C COMPLETE、Phase 02 IN_PROGRESS、02D以降未承認。
- 全65 tests: 61成功・opt-in browser4 skip（290.527秒）。別実行の02C fake browser1成功（87.308秒）、
  native Points CPU browser1成功（51.529秒）、02B fake browser回帰1成功（29.257秒）。
  02B旧depth-only CPU UI testは今回は未再実行、旧Run CLI再読込と新native CPUで確認した。
- Three.js r180 / 0.180.0（MIT）同梱、RGB / Depth / native Normal色、RGB texture / Geometry /
  Wireframe、camera保持/reset、Depth統計・raw download・optional理由付き無効化を検証。
- 初回meshのみ遅延生成、manifest schema 1.0 / digest条件reuse / atomic directory publish。
  6同時要求・条件差・中断partial・破損digest / manifest・symlink拒否・再起動reuseを確認。
- 最終CPU Run `cf867c2d-6591-4962-9e77-504cef5013c3`、65,536 native Points / m、124,848 faces。
  raw / WorkerResult / JobResult hash・mtime不変、predict1回、final Python source digest一致。
- Python / worker非loopback socketとbrowser外部HTTP遮断下で推論・frontend / 3D / 再起動読込が成功。
  external / console / page error 0。512×512で262,143点 / 522,240 facesを操作、超過は案内付き拒否。
- 旧01A / 02A / 02B / 最終CPUの4RunをCLIで各2回collect、全file hash / mtime不変。
- 詳細・Run IDs / 制限 / warning / 未検証項目は [02C evidence](docs/phases/phase-02/phase-02c.md)。
  API / schema / renderer比較は [Results Viewer](docs/results-viewer.md)。GPU / 他OS/browser /
  上限超geometry / multi-process / 精度 / 学会実演は未検証、02D管理操作は未実装。
- 最終静的検証: 28 Markdown / 199 local links・anchors・fences、29 Python AST、JSON / TOML /
  JS syntax、pip check、git diff --check成功。再fetch後もorigin/mainは開始HEAD `9954b77` と一致。
  commit / mainへ通常pushする。SHAはGit履歴・完了報告に記録し、force pushは禁止。

## Phase 02B implementation plan — 2026-10-23（完了済み履歴）

- Goal / scope: 独立application環境のGradioから既存Runner / Backendを短いcallbackで操作。
  Inference / Resultsの2タブ、manifestに基づく設定、PNG検証、明示device / timeout、
  共有LocalBackend busy拒否、session別input / handle / result / callback世代、status / cancel。
  Resultsは検証済み共通詳細・Run ID受渡しとterminal Run ID読込。4モードviewer・管理操作は追加しない。
- Order: source / 承認更新 → Gradio公式仕様・pin / 独立環境 → 既存40tests baseline →
  UI非依存controllerとsession / 非同期操作 → Gradio構成 → fake / contract / browser →
  固定MoGe明示CPU UI smoke・旧CLI / Run互換 → docs / Exit判定 → remote再確認 → commit / 通常push。
- Contracts: UIはRegistry metadata / Runnerのみ。composition rootが単一Backendを構成。
  submit / poll / cancelを推論待機させず、Gradio eventはqueue=Falseで同時browserから即busyを検証。
  cancel / collectはbackendの停止・検証を背景処理へ渡し、UIは状態をpollする。
  世代を検証して古いcallback結果・cancel対象の混線を防止。進捗%・未測定値を捏造しない。
- Tests: 入力空 / 破損 / 過大、未知variant / parameter / device、各status / timeout / missing metrics、
  2browser sessionsの入力・handle・Results分離、busy即拒否・自動待機なし、cancel / 完了race、
  terminal後の次job、古い通知、adapter / torch / subprocess境界、既存全tests・CLI互換。
- Environment: applicationはrepo内Git管理外venv、Gradioと推移依存lock・再作成手順を保存。
  既存独立mde-moge / pin weightsを再利用。frontend同梱assets、analytics / share / 外部fontを無効化し、
  準備済み依存・weightsでのoffline browser / 推論を検証。worker依存は変更しない。
- Risks / rollback: Gradio dispatch / callback順序、thread間backend lock、upload寿命 / 制限、
  multi-process調停は保証しない。単一process / loopback運用。変更は追加中心、schema / CLI維持。
  戻す場合は02B追加UI・application依存のみrevertしraw / 確定結果を保持。
- Decision / Reason / Trade-off / Future extension: 1共有Backend + session別状態 / busy guardを維持 /
  同時推論は拒否 / queue・認証・active recoveryは後続承認。数値progressはunavailableで契約拡張しない。
- Start record: sourceとlatest main確認・承認更新済み。開始時点では実装・検証は未実行。

### Phase 02B completion evidence（2026-10-23時点の履歴）

- 全Exit達成で02B COMPLETE、Phase 02 IN_PROGRESS、02C–02D NOT_STARTED / 未承認。
  2タブ / 1共有Backend / session分離 / 即時busy拒否 / 非同期status・cancel / terminal Resultsを実装。
- 変更前40 tests成功（140.204秒）。最終全体55件は53成功・opt-in browser2件skip（149.853秒）。
  最後に強化したRunner事前検証・load順序逆転の2件も成功（0.051秒）。
  実browserは別実行でfake 1件成功（23.097秒）、実CPU UI 1件成功（25.977秒）。
- fake / contract / browserで各status、PNG異常・未知設定、2session入力・handle・結果分離、
  同時submit=1受理1busy、拒否jobの後日自動実行なし、session別cancel、完了race・古い世代、
  disconnect非cancel、old load非上書き、terminal次job、integrity / path / active recovery拒否を確認。
- Gradio 6.30.0 / Python 3.13.13を独立venvに固定。ui.lockから別venvへoffline再導入・pip check成功。
  frontend外部要求0、queue join0、page errors0。worker依存は不変、applicationにtorch / MoGeなし。
- 最終実CPU UI Run `799d2355-c57b-4552-92c4-644a7f25e775` COMPLETED。
  float32 [256,256] / metric m / z_depth / 01A-depth-only、既存CLI CPU depth digest一致。
  最終production source digest一致。CUDA不可失敗・実CPU cancel / timeoutのUI表示も確認。
- Python application / Conda / worker非loopback socketとbrowser外部HTTPを遮断して成功。
  新application / WorkerManagerなしで保存Runを再表示し全file hash / mtime不変。
  旧01A・02A・新CPU / failure / cancel / timeoutの6Runを新CLIで各2回collectし全file不変。
- 詳細・Run IDs / measured metrics / warning / offline条件は [02B evidence](docs/phases/phase-02/phase-02b.md)。
  起動・callback契約は [Gradio Inference](docs/gradio-inference.md)。GPU / 3D / 学会実演は未検証。
- 最終検証: 27 Markdown / 184 local links・anchors・fences、26 Python AST、JSON / TOML、
  control dependencies空、git diff --check成功。remote再取得後もorigin/main = 開始HEAD、左右差分0。
- Git publication: Exit達成済み差分をcommit / mainへ通常pushする。SHAと到達先は完了報告・Git履歴を参照。
  remote更新・競合・範囲外変更なら停止。force pushしない。02C開始は未承認。

## Phase 02A implementation plan（完了済み履歴）

- Goal / Scope: depth必須 + optional points / normals / intrinsics / maskを正式Run artifactsへ保存・検証。
  実MoGe CPU native Pointsの保存・再読込・frame / metric尺度・depth整合を必須Exitに追加。
- Order: source確認・承認更新 → 既存独立環境 / pin / weights検証・29tests baseline →
  native API / K / normal convention調査 → requested outputsとprofile契約確定 → adapter・worker・
  RunStore実装 → fake / adversarial / 01A・01B regression → 実CPU smokeと旧Run再読込 →
  docs / Exit / hygiene → remote更新確認 → commit / main push。02Bへ進まない。
- Contract: schema major 1 / 既存depth-only defaultを維持。explicit optional requestを事前capability検証し、
  runtime欠落は失敗。新geometry profileはoptional refs・共通effective validity / native provenanceを持つ。
  controlはstdlibでNPY検証、numeric依存はworker。raw / 確定JobResultを上書きしない。
- Tests: 各optional有無・組合せ、NPY dtype / shape / mask / semantic不正、missing / corrupt /
  traversal / symlink / digest、旧profile / CLI・cancel / timeout / busy回帰、再collect不変。
  native points / K / normal mappingは数値fixturesとpin source、実CPUは正式worker経由で検証。
- Environment: 既存named mde-mogeとcheckpointが見える。pin / runtimeを照合して利用し、
  base / systemを変更しない。環境・weights・runs・logsはGit管理外。GPUは未検証。
- Risks: native normalized K pixel center、normal方向、points/depth尺度、optional capability過剰申告、
  payload検証のmemory負荷、旧結果互換。source / fixture / 実測で確認し不明値を捏造しない。
- Exit: 02A checklistとnative実Points条件の全達成のみCOMPLETE・commit / push。
  未達なら原因・残条件を記録。remote更新・競合・範囲外変更は停止、force pushなし。

### Phase 02A completion evidence

- Baseline: 29 tests成功（107.062秒）。最終40 tests成功（238.662秒）、既存29 + 新geometry11。
  初回全体はtimeout=4秒の既存testがreadiness前に終了し1 failure（248.709秒）。
  条件を変更せず単独再実行（4.247秒）と最終全体で成功。数値roundtrip最終補足1 testも成功。
- 実CPU geometry Run: 0c33df74-f72d-4348-a9a1-c2968d5f9e7b、COMPLETED。
  native points（force_projection=False）float32 [256,256,3] / metric m、65,536 valid / 0 invalid、
  points.z-depth最大誤差0 m。Normals / Intrinsics / effective mask / model maskも実出力で保存・検証。
- 既定depth-only CPU Run: 5d0351b3-1a6b-460f-80eb-c19f528e5656、COMPLETED、depth digest一致。
  geometry / 旧01A Runを新CLIで各2回collect、全file hash / mtime不変・predict追加なし。
- 既存独立mde-moge / fixed weights再利用。依存導入・環境定義変更なし、GPU / accuracyは未検証。
- Python AST / JSON、25 Markdown / 165相対リンク・anchor / fence、control import境界、
  `git diff --check`を検証。変更は02A code / tests / related docsのみ。generated artifactsはGit管理外。
- 02A COMPLETE、Phase 02 IN_PROGRESS、02B–02D NOT_STARTED / 未承認。次milestoneを自動開始しない。
  [02A evidence](docs/phases/phase-02/phase-02a.md#acceptance-evidence--実cpu--compatibility)に詳細を記録。
  remote更新確認後に本作業単位をcommit / mainへ通常pushする。


最終production sourceでの追加CPU smoke Run: `a2c9ca5a-4eb7-4697-b880-8041e7749bae`、COMPLETED / exit 0。
Runのsource_digestが最終src / models/mogeの対象source filesと一致することを確認した。
Points [256,256,3] / m、65,536 valid、points.z-depth誤差0 m、Normals / Intrinsics / masksも再検証。
新CLIによる2回collectで全file hash / mtime不変、predictは1回。
初回geometryと既定depth-onlyのdepth SHA-256も一致。GPU / GT精度は未検証。

## Phase 02 documentation plan — 2026-10-13 (完了済み履歴)

- Goal: 02A を安全に開始できる共通契約と範囲を GitHub 上に確定する。実装承認は別途必要。
- Scope: README / AGENTS / PLANS、Phase 02 親文書と4内部 milestone、関連技術仕様の必要部分。
  Phase 01 の実装済み仕様・完了証拠を保持し、新規 storage / service 契約は設計のみと明記する。
- Order: latest main / clean確認 → 実装・仕様照合 → 親仕様 / 02A–02D / 技術仕様 →
  状態・相対リンク・範囲・差分検証 → remote更新確認 → docs commit → `main`へ通常push。
  remote の更新・競合・範囲外変更があれば上書きせず停止する。
- Implementation order (未承認): **01 → 02A → 02B → 02C → 02D**。
  02C は02Aの geometry保存と02BのResults枠、02Dは02Cの派生保存契約に依存。
  02Cでderived storageの最小生成・再利用・読込、02Dで管理操作を追加する。
- Verification: milestone依存・検証可能なexit、旧depth-only/schema 1.0互換、状態表示、
  実装/設計/未検証の区別、Markdown相対リンク・fence、docsのみの変更、`git diff --check`。
  今回は実装テスト・モデル推論・GPU / 学会デモを実行しない。
- Risks: native / standard frame混同、K変換とRGB対応、optional欠如、巨大geometry容量、
  Gradio event queue / session混線、derived cacheの衝突、削除race / path逸脱、offline frontend依存。
  契約とfake/adversarial/browser/実機検証を各milestoneに割り当てる。
- Exit (今回の文書作業): 上記検証成功、承認範囲のdocsをcommit / mainへpush、clean確認。
  Phase 02と02A–02Dの実装状態はNOT_STARTEDを維持し、実装を自動開始しない。

### Documentation validation evidence — 2026-10-13

- README / AGENTS / PLANS / Phase 01冒頭 / Phase 02親・4milestoneの状態整合を確認。
  Phase 01 COMPLETEを維持し、Phase 02 / 02A–02Dの実装はNOT_STARTED / 未承認。
- 24 Markdown文書の157相対リンク（heading anchorsを含む）とfenced blocksを検証し成功。
- 02A→02B→02C→02Dの依存、fixture / browser / 実機ごとの検証可能なexit、
  schema 1.0 / depth-only互換とraw / JobResult不変の計画を照合。
- `git diff --check`成功。変更対象は15 Markdown文書のみ、production code / 依存定義の変更なし。
- 新規契約は設計のみと明記。実装tests / 推論 / UI / GPU / 学会デモ検証は今回実施していない。
  commit / pushの結果はGit履歴で確認し、remote更新があれば停止する。

## Phase 02 internal milestones

| Milestone | Dependencies | 検証する主要 exit |
| --- | --- | --- |
| [02A — Geometry Artifacts](docs/phases/phase-02/phase-02a.md) | 01 COMPLETE | depth必須・optional保存/検証、旧Run読込、raw不変、実CPU native Points（COMPLETE） |
| [02B — Gradio Inference](docs/phases/phase-02/phase-02b.md) | 02A | Local推論/状態/cancel/timeout、session分離・busy、CLI互換 |
| [02C — 3D Results Viewer](docs/phases/phase-02/phase-02c.md) | 02A・02B | 4表示モード、offline操作、派生meshの遅延永続保存・再利用・再起動読込 |
| [02D — Run Management](docs/phases/phase-02/phase-02d.md) | 02C | 共通service経由の一覧/編集/export/再生成/archive/restore/確認付き削除 |

02A–02DはPhase 02の内部milestoneであり独立Phaseではない。全exit達成でPhase 02 COMPLETE。
文書作成と実装の開始・完了は別。02A / 02B / 02C / 02Dは全Exit達成でCOMPLETE。

## Phase management

状態は `NOT_STARTED → PLANNED → IN_PROGRESS → REVIEW_READY → COMPLETE` を基本とし、
外部条件の不足は `BLOCKED` として理由を残す。`PLANNED` は計画文書の準備状態であり、
production code の実装承認・開始を意味しない。実験 JobStatus とは別の管理状態である。
文書準備だけでは実装を開始しない。02Dは全Exit達成済み。Phase 03は2026-11-11に実装承認。Phase 04以降は未承認。

各 phase 開始前に、最新のユーザー指示がその phase の実作業を承認していることを確認する。
必要な通常作業のたびに承認を取り直す必要はないが、未指示の phase に進んではならない。
README / phase 文書のロードマップは将来計画であり実装の指示ではない。

各 phase 文書の Goal、Background、Scope、Non-goals、Dependencies、Implementation tasks、
Tests、Exit criteria、Known risks、Decisions deferred to later phases を維持する。

| Phase | 前提 | 主要 exit | 現状 |
| --- | --- | --- | --- |
| [00](docs/phases/phase-00.md) | clean-start の正式確認 | 調査記録・共通契約・段階計画の整合 | COMPLETE |
| [01](docs/phases/phase-01.md) | 00 完了、最初の model / variant 選定 | 01A の最小 E2E → 01B の基本的堅牢化 | COMPLETE、01A / 01B exit 達成 |
| [02](docs/phases/phase-02.md) | 01 | 02A geometry → 02B Inference → 02C 3D Results → 02D Run管理 | COMPLETE（02A〜02D全Exit達成） |
| [03](docs/phases/phase-03.md) | 01・02 | 3 モデルが同じ契約を満たす | 実装中（03.1、Exit未達） |
| [04](docs/phases/phase-04.md) | 03 | Runner から MLflow、失敗時にも結果保存 | 未着手 |
| [05](docs/phases/phase-05.md) | 03・04 | 同じ single inference に基づく比較評価 | 未着手 |
| [06](docs/phases/phase-06.md) | 01–05 | Mock backend で非同期・状態・再収集を検証 | 未着手 |
| [07](docs/phases/phase-07.md) | 06、研究室設定の確認 | Slurm prototype と承認された現地設定 | 未着手 |
| [08](docs/phases/phase-08.md) | 07、研究室 Slurm / NFS / GPU | 実機 lifecycle・障害・成果物・追跡の検証 | 未着手 |

Phase 01 から backend interface と process isolation を使用する。
Phase 03 は plugin の初導入ではなく、最初の adapter 契約を複数モデルに拡張・検証する段階。
Phase 06 は abstraction の初導入ではなく、backend の可搬性を検証する段階。

## Phase 01 internal milestones

| Milestone | 優先する成果 | Exit に含めないもの | 状態 |
| --- | --- | --- | --- |
| 01A — Minimum Local E2E | 1 model × 1 image × 1 独立 Conda 環境、subprocess、ModelAdapter、LocalBackend、MDEOutput、Run Directory、raw depth / metadata / result / logs | GPU lease、queue、cancel / timeout API の完成、性能計測、retry、active job recovery、複雑な concurrency | COMPLETE（明示 CPU、2026-10-11） |
| 01B — Local robustness | 基本 cancel / timeout、子 process 終了、単一 worker の busy guard、artifact validation、基本計測と再現手順 | 高度な retry / reconciliation、application restart recovery、分散 lease / multi-GPU queue | COMPLETE、2026-10-12 |

まず 01A の実モデル推論成功を証拠付きで確定し、その前に 01B の要件を追加しない。
01A / 01B は既存 Phase 01 の内部 milestone であり、Phase 02–08 の番号と architecture は維持する。
Phase 01 全体の COMPLETE は 01A / 01B 双方の exit を満たした時点とし、01A 単独の完了を区別する。
01A 完了は 01B または Phase 02 の実装を自動承認しない。

以下の 01B implementation plan は完了済み作業の履歴であり、現在の承認範囲は冒頭を参照する。
2026-10-07 の文書のみの計画更新は完了済みで、今回の実装承認とは区別する。
リスク: 将来の完全な契約を 01A の必須実装と混同すると scope が再拡大する。
各仕様に milestone の適用範囲を記載し、共通 interface / Run layout を維持して段階的に検証する。

## Phase 01B implementation plan — 2026-10-12

- Goal / scope: 01A の経路・schema major 1・既存 layout を維持して Local robustness を追加する。
- Evidence: 開始 HEAD `24efc22`、branch main、clean。現在の checkout に旧環境・weights・runs はない。
  既存8 tests の初回は環境不足で5 failures（2.516秒）。コード回帰とは区別する。
- Order: source of truth 確認 → 固定環境を Git 管理外 `.local/envs/` に再作成 →
  変更前01A regression → process group cancel / timeout・instance busy guard → validation / terminal
  再 collect → worker timing / fingerprint → adversarial / lifecycle tests → 同じ MoGe CPU smoke → docs / exit → commit / push。
- Process: POSIX の独立 session / process group、SIGTERM、bounded grace 後 SIGKILL。
  wrapper exit だけで終了扱いにせず group の生存を確認。timeout は poll に依存せず backend timer で発火。
  cancel は停止確認後 CANCELLED、timeout は FAILED / TIMEOUT。終了前に完了した job は完了を優先。
- Validation: job / handle identity、必須 report 型・error・outputs・metadata、Run 内 path、
  checksums / NPY / 入力・環境定義 digest。確定後破損は ArtifactIntegrityError、結果を書き換えない。
  新 backend の保存済み terminal collect は読むだけ。active handle の監視・停止復旧は実装しない。
- Measurements: perf_counter による load / adapter predict / depth serialization / unload、
  CUDA 利用時のみ synchronize / allocator peak（bytes）。package name/version list と digest、
  Python / platform / 定義 hash / torch / CUDA / device を記録。未測定値を0にしない、秘密の環境変数を保存しない。
- Tests: 01A contract regression、実 Conda のcancel / timeout（SIGTERM無視の子を含む）と busy 再使用、
  malformed / missing / corrupt report・path / checksum、terminal 再 collect / active拒否、
  timing / fingerprint / CPU no allocator、CLI failure / interrupt / unsupported。実機は明示 CPU。
- Risks: orphan / zombie、終了競合、timer と collect の race、依存 download / native API 不整合。
  group を逸脱する daemon、OS quota、複数 backend 間の調停は保証しない。Linux POSIX で検証する。
- Rollback / hygiene: 追加情報は optional、既存 JSON の読み戻し互換テストを追加。
  base / system を変更せず environment / downloads / runs / secrets を commit しない。
  failures を成功にせず、force push しない。Phase 02 以降の実装は開始しない。

### Phase 01B completion evidence — 2026-10-12

- 変更前01A 8 tests成功（9.501秒）、最終29 tests成功（53.102秒）。既存8 + 追加21。
- 実Condaのcancel / timeout / orphan / graceful停止でwrapper waitとworker / child PID消失を確認。
  pollingなしtimeout、busy解除 / 再使用、cancel競合、停止確認失敗の非terminal維持も検証。
- 保存済みterminalの再collect（新backend / CLI、FAILED / CANCELLEDを含む）、
  hash / mtime不変とpredict log 1回、01A形式互換、active recovery拒否を確認。
- 環境再作成: 固定environment.yml、MoGe / utils3d revision、checkpoint SHA-256を利用。
  Python 3.11.14 / torch 2.6.0+cu124 / torchvision 0.21.0+cu124 / runtime 12.4、明示CPU。
- MoGe regression Run ID: f4a2052f-71da-4664-9c9f-281cca95fb41。COMPLETED / exit 0。
  float32 [256,256]、metric z_depth (m)、65,536 valid / 0 invalid、必須12 files / JSON / logs検証。
- 42 Python distributions / 24 Conda packagesとdefinition digest / list digest / fingerprintを保存。
  load / predict / serialization / unload / metadata / worker timingを単位・scope付きで保存。
  CPU allocator値は省略。実GPUは未検証。CUDA要求の負例はFAILEDでfallbackなし。
- 完了証拠の詳細と測定値は [Phase 01](docs/phases/phase-01.md) に集約。
  .local/validation/ / runs/はGit管理外。base / system変更なし。
- 01A COMPLETE、01B COMPLETE、Phase 01 COMPLETE。Phase 02以降は未着手・未承認。
  automatic retry / active recovery / queue / GPU lease / UI / tracking / Slurm / 他モデルは追加しない。
- Exit達成により現在のmainへcommit / pushする。force pushなし、生成物・環境本体・secretを含めない。

## Phase 01A implementation plan — 2026-10-09

- Evidence: 最新 `origin/main` は `3b7e1d208d31e506b9574ed2d7cc346b5dbc5623`。
  workspace の Git metadata は利用不可のため、前回同様に一時 checkout で履歴・差分・push を扱う。
- Goal: 1 MoGe variant × 1 非機密 sample × 1 独立 Conda 環境で実推論を成功させ、depth / JSON / logs を回収。
- Order: 指定文書確認 → README の worker 保存矢印を修正 → 機材 / Conda / NVIDIA 調査 →
  公式 upstream API / dependencies / checkpoint / depth semantics 確認・pin 選定 → 最小実装 →
  subprocess fake tests → 実モデル E2E → artifacts 読戻し → docs / diff / exit 再確認 → commit / push。
- Components: stdlib 中心の control contracts / manifest Registry / thin Runner / RunStore / LocalBackend、
  configurable Conda launcher、共通 worker、`models/moge/` の adapter / manifest / environment 定義。
  配列・画像の依存は worker に隔離し、adapter から Store を呼ばない。
- Tests: fake subprocess と depth 読戻し、stdout / stderr、制御側 import 境界、非ゼロ終了・欠落成果物、
  MDE_RUN_ROOT。実機は明示した device で実行し、Python / torch / runtime / GPU / model identity / Run ID を記録。
- Selection: 下記に MoGe variant / commit / checkpoint と依存候補を記録済み。
  GPU 不可時に CPU fallback しない。CPU 実行はユーザーの明示選択を待つ。
  sample の出典・license は tests/assets/README.md に記録する。
- Risks: GPU 不可視、driver / wheel 不整合、download / 容量不足、upstream 出力の尺度、環境構築権限。
  不成功を COMPLETE と記録せず、必要な E2E を残課題として明示する。
- Rollback / hygiene: base / system Python は変更しない。新規モデル環境・cache / runs は Git 管理外。
  source は初期 commit との差分で追跡し、破壊的変更・force push をしない。

### Pre-inference preparation — 2026-10-11

- Goal / scope: 実モデル投入前の code / fake contract 検証と文書・差分整理を完了する。
  実推論・大容量 download はユーザーが自宅 Wi-Fi 接続後に再開するまで保留。
- Order: 中断後の files / environment を確認 → 最新 main を読み取り確認 → fake suite を再実行 →
  AST / JSON / TOML / Markdown / Git hygiene を検証 → 実測状態と再開手順を記録。
- Observed: `mde-moge` と MoGe / utils3d / NumPy / Pillow / SciPy は存在する。
  torch / torchvision はまだ未導入。検証済み CUDA wheel 5 個と checkpoint は `.local/` に残っている。
  前回の一時 checkout / logs は失われたため、再検証 logs と比較 checkout は Git 管理外の `.local/` に置く。
- Limit: code / fake 検証完了は 01A COMPLETE ではない。実モデル成功と環境 runtime 検証が残る。
  CPU の明示選択または GPU 実行先の確認も再開時に必要。CPU fallback しない。
- Git: exit 未達のため completion commit / push は行わず、変更を review 可能な状態で保持する。
- Verified: fake suite 8件成功（18.968秒）。ログは `.local/validation/contract-tests-2026-10-11.log`。
  checkpoint 140,550,416 bytes の SHA-256 を再照合し一致。
  最新 main は引き続き `3b7e1d208d31e506b9574ed2d7cc346b5dbc5623`。
  比較用 checkout は `.local/review-checkout/`。実モデル job は投入していない。

### Real inference resume — 2026-10-11

- Decision: 自宅 Wi-Fi 接続後の再開指示と CPU 選択の指示を受け、01A の当初の範囲に戻す。
- Order: 固定 torch / torchvision の残り依存を既存 `mde-moge` へ導入 → native API / runtime を確認 →
  CLI に `--device cpu` を明示して実推論 → depth / metadata / WorkerResult / JobResult / logs を検証 →
  static validation / docs / diff / hygiene → exit 達成時のみ main の作業単位を commit / push。
- Reason: このノート PC に NVIDIA GPU が見えず、ユーザーが CPU 推論の選択を指示した。
  CPU と GPU 実行の証拠は区別し、自動 fallback は実装しない。
- Trade-off: CUDA 対応 wheel を固定した環境でも CPU 実行を検証できるが、driver / GPU 互換性・性能は未確認のまま。
- Future extension: GPU 機材がある際に同じ経路へ `--device cuda:0` を明示し、GPU runtime / driver を実測する。
- Risks / rollback: download timeout、native import の不足依存、CPU 実行時間 / memory。
  base / system Python は変更せず、取得物 / weights / runs は Git 管理外。失敗を COMPLETE としない。

### 01A selection / preflight

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| MoGe-2 ViT-S Normal、source `07444410f1e33f402353b99d6ccd26bd31e469e8` | 最小公開モデル（35M）、v2 infer API と metric scale。2025-11-02 の MoGe-2 revision を確認 | 大きい variant の精度・最新 MoGe-3 は検証しない | Phase 03 で variant を追加 |
| checkpoint `Ruicheng/moge-2-vits-normal`、revision `26b477f41595707c5db6770294c0d1721e8ed4ed` | 公開 model.pt の immutable identity を追跡 | 事前取得と hash 確認が必要 | weights cache を設定で差し替え |
| checkpoint SHA-256 `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc` | Hub の LFS metadata に基づく内容確認 | 140,550,416 bytes の download が必要 | cache 再利用、offline load |
| Python 3.11、torch 2.6.0 / torchvision 0.21.0 の公式 cu124 build を準備 | source は Python >=3.9 / torch >=2.0。固定版の公式 wheel 組で依存・import と GPU 要求時の失敗を検証する | このマシンに NVIDIA driver が見えず GPU 実行の互換性は未検証 | 明示した CPU 実行、または GPU 環境で runtime / driver を実測 |
| upstream は推論依存のみを明示導入し `--no-deps` で install | v2 package の全依存には Gradio / training 向け処理もある | upstream 全 CLI / UI の dependency completeness は保証しない | 使用する API と import を smoke で検証 |

Preflight: Linux x86_64、Miniconda を確認。base Python は 3.13、NumPy / Pillow は未導入。
NVIDIA device files / driver files / nvidia-smi は見つからず、PCI では Intel Graphics のみを確認。
当初は CPU 実行の選択を問い合わせ、2026-10-11 の指示を受けて明示 CPU smoke を行った。
native depth は `points[..., 2]` に metric_scale を適用した z-depth、invalid pixel は Inf。
共通出力は float32 / z_depth / metric / m、invalid を NaN として保存し finite-positive pixel で判定する。
参考: [固定 source](https://github.com/microsoft/MoGe/tree/07444410f1e33f402353b99d6ccd26bd31e469e8)、
[checkpoint](https://huggingface.co/Ruicheng/moge-2-vits-normal/tree/26b477f41595707c5db6770294c0d1721e8ed4ed)、
[PyTorch wheel 組](https://docs.pytorch.org/get-started/previous-versions/#v2-6-0)。

### 01A implementation evidence — 2026-10-09

- 最小 control / worker / MoGe adapter / manifest を追加。adapter から Store への依存はない。
- `mde-moge` の作成に成功。Python 3.11.14、NumPy 1.26.4、Pillow 11.1.0、SciPy 1.14.1、
  OpenCV-headless 4.10.0.84、Hub 0.28.1。base / system Python は変更していない。
  固定 source の MoGe 2.0.0 と utils3d を `--no-deps` で導入。
  torch 2.6.0 / torchvision 0.21.0 cu124 の導入は未完。GPU 互換性の成功は未確認。
  初回 pip download は通信 read timeout で失敗し、再試行後に取得済み wheel を保持して download を停止。
  2026-10-11 の指示により大容量 download / 実モデル smoke の再開は保留。
- 固定 checkpoint を事前取得し、140,550,416 bytes と上記 SHA-256 を照合済み。
  weights / Hub cache は `.local/` に置き Git 管理外。
- NASA astronaut の public-domain 画像を RGB 256×256 の smoke 入力にした。
  画像は動作確認用であり GT / 研究データ / benchmark として扱わない。
- GPU 不要の Conda subprocess contract tests は8件成功（22.269秒）。終了コード0でも
  depth file / result が欠ければ FAILED を確認。fake 出力は
  float32 256×256、任意尺度の一定値であり、MoGe の実推論結果とは別。
- **実モデル smoke は未実行**。NVIDIA が見えず、CPU 選択または GPU 実行先の回答待ち。
  real Run ID / depth / torch runtime はまだない。01A exit は未達で COMPLETE にしない。
- cancel / timeout / queue / lease / retry / recovery、UI / tracking / benchmark / Slurm は追加していない。
- 静的検証: 21 Markdown、101 local links / anchors、9 phase 文書の必須10節、
  15 Python files の AST、manifest JSON と pyproject TOML を確認（errors 0）。

### 01A completion evidence — 2026-10-11

- 実推論成功: `9c5b6556-30d3-43ae-827f-7bd8b0a47580`。CLI → thin Runner → LocalBackend →
  `mde-moge` subprocess worker → MoGeAdapter → MDEOutput → Run Directory → collect。
- `mde-moge`: Python 3.11.14、torch 2.6.0+cu124、torchvision 0.21.0+cu124、
  torch.version.cuda=12.4、cuda_available=false、GPU / driver=null、device=cpu。
  CPU は Intel Core Ultra 5 125U。CUDA 対応 wheel の存在を GPU 成功と混同しない。
- 固定 upstream / checkpoint revision と SHA-256 は上記選定どおり。
  raw depth は `runs/<run_id>/output/attempt-0001/views/view-0001/depth.npy`、
  float32 `[256,256]` / z_depth / metric / m。65,536 pixel が有限・正、invalid 0。
  最小 0.8110444 m、最大 4.2878127 m。GT はなく metric accuracy を評価した値ではない。
- WorkerResult.outcome と JobResult.status は COMPLETED、exit_code=0。
  必須12 file、全 JSON の Run ID、JobSpec snapshots、input / artifact checksum、NPY header、
  metadata/runtime 一致、stdout / stderr、unload を読み戻して検証した。
- 実モデル import / runtime preflight 成功。依存導入後の fake suite は8件成功（17.025秒）。
  ローカル証拠は `.local/validation/`、実験生成物は `runs/` に保持し、Git には含めない。
- upstream の CPU float32 autocast 警告は stderr に保存した。autocast が無効化されるという警告であり、
  CPU / float32 は明示指定どおり。upstream を改変・警告抑制していない。
- upstream package の全 extras は導入しない設計のため、pip は click / gradio / matplotlib / pipeline /
  trimesh / opencv-python の requirements 不足を通知した。cv2 は opencv-python-headless で提供。
  native v2 API と実推論は成功したが、upstream 全 CLI / UI や pip check の成功は保証しない。
- Git metadata が workspace で使えないため結果の git_commit は unknown、source_digest を記録した。
  自動 Git provenance の取得と詳細 environment fingerprint は未実装として残す。
- 9要素の 01A exit を充足。01A COMPLETE、01B NOT_STARTED / NOT_AUTHORIZED、Phase 01 IN_PROGRESS。
  GPU / driver 検証、cancel / timeout、optional geometry / visualization、01B 以降は未実施。
- 最終静的検証: 21 Markdown、103 local links / anchors、9 phase 文書の必須10節、
  15 Python AST、2 manifest JSON、pyproject TOML、control dependencies 空を確認（errors 0）。
- Git hygiene: 32変更 file、最大115,680 bytes。weights / cache / Conda / runs / credentials / host 固有 path
  を含めず、生成物の ignore、日本語 README、project 表示名、repository origin の維持、差分一致を確認。
  比較・publish 用 checkout は `.local/review-checkout/` の main。completion commit / push は最終差分確認後。

今回の変更対象（32 files。生成物は含めない）:

- Root: `AGENTS.md`、`PLANS.md`、`README.md`、`.gitignore`、`pyproject.toml`。
- Specs: `docs/architecture.md`、`docs/model-adapter-spec.md`、`docs/environment-strategy.md`、
  `docs/execution-backend-spec.md`、`docs/run-directory-spec.md`、`docs/phases/phase-01.md`。
- Control / worker: `src/mde/__init__.py`、`contracts.py`、`registry.py`、`storage.py`、
  `environments.py`、`backends.py`、`runner.py`、`worker.py`、`cli.py`（いずれも `src/mde/`）。
- Model: `models/moge/adapter.py`、`manifest.json`、`environment.yml`、`prepare_checkpoint.py`、
  `README.md`（いずれも `models/moge/`）。
- Tests: `tests/__init__.py`、`tests/test_local_contract.py`、`tests/fixtures/__init__.py`、
  `tests/fixtures/fake.py`、`tests/fixtures/models/fake/manifest.json`、
  `tests/assets/sample.png`、`tests/assets/README.md`。

## How Codex updates a plan

1. 調査の根拠（対象 path / commit、既存 CLI、依存定義、未確認箇所）を記録する。
2. 作業前に対象 phase、承認範囲、具体的な変更、再利用対象、tests、rollback を更新する。
3. 大規模変更や interface 変更が必要と分かった時点で、実装前に plan と対応 docs を更新する。
4. 決定は `Decision / Reason / Trade-off / Future extension` の四項目で記録する。
   未決定の値を決定済みにせず、担当 phase と必要な証拠を付ける。
5. 作業中は成果・残課題・scope 変更を簡潔に残す。実行していない tests は未実行とする。
6. Exit criteria を一つずつ証拠で確認し、完了時は README の状態と次 phase の前提も更新する。
7. 次 phase の提案はできるが、ユーザーの指示なしに着手しない。

計画の記録テンプレート（文書仕様、実行スクリプトではない）:

```text
Phase / Status / User-authorized scope:
Evidence and existing assets to reuse:
Changes and order:
Tests and acceptance evidence:
Risks / rollback:
Decisions and deferred items:
Completed / remaining:
```

## Phase 00 work record — 2026-10-07

- [x] cwd と対象 root、隠しディレクトリを含む可視全体を確認。
- [x] 上位・対象 path の AGENTS.md を探索。既存の指示ファイルは確認できず。
- [x] `rg --files --hidden`、directory walk、`git status` / `git log` による根拠を記録。
- [x] upstream のモデル・Conda・CUDA・Slurm・MLflow の一次資料を読み、参考情報と区別。
- [x] 指定の root 文書 3、仕様文書 7、phase 文書 9 を作成。
- [x] ローカル相対リンク、phase 必須節、コード未追加、文書間の契約を確認。
  初回作成時に 19 Markdown files / 9 phase documents、89 local links / anchors の静的検証を実施。
  model / GPU / Slurm / MLflow の実行テストは今回未実行。
- [x] ユーザーが repository を正式な clean-start として確認。
- [x] repository 内に再利用必須の既存 production implementation がないことを記録。
  過去のモデルコードの確認は Phase 01 / 03 の必要時へ移し、Phase 00 の gate から外す。
- [x] 決定を architecture / README / phase 文書へ反映し、Phase 00 の exit を再評価して COMPLETE。
  実装 phase は開始しない。

## Completion reassessment and Phase 01 planning record — 2026-10-07

- [x] clean-start を正式記録し、Phase 00 の exit 全条件を再評価して COMPLETE。
- [x] 01A の 9 要素と最小 real inference、01B の基本 robustness の tasks / tests / exit を分割。
- [x] GPU lease、高度な retry / reconciliation / restart recovery / concurrency を初回成功条件から除外。
- [x] 関連仕様の実装段階と Phase 03 の過去コード参考方針を同期。
- [x] 19 Markdown files、9 phase documents の必須 10 節、90 local links / anchors、fenced blocks を静的検証。
  文書のみの 11 ファイル変更を確認。production code・環境・実データの追加なし。
  実モデル推論・GPU・Slurm・MLflow の tests は今回未実行。

変更ファイル: `AGENTS.md`、`README.md`、`PLANS.md`、`docs/architecture.md`、
`docs/environment-strategy.md`、`docs/execution-backend-spec.md`、`docs/mlflow-design.md`、
`docs/run-directory-spec.md`、`docs/phases/phase-00.md`、`docs/phases/phase-01.md`、
`docs/phases/phase-03.md`。Phase 01 の状態は計画整理済み・実装未着手のまま。

## Key decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| clean-start を正式な出発点とし source audit gate を完了 | ユーザーが repository 内に再利用必須の実装がないと確認 | legacy 動作・出力の互換移行を初期条件にしない | 過去コードは 01 / 03 の必要時に参考として確認 |
| Phase 01 から adapter / backend / worker 契約を使う | 後から Local と UI を切り離す refactor を避ける | 最初の 1 モデルにも薄い共通層が必要 | Phase 03 / 06 で実証を広げる |
| 共通 Run ID と append-only attempt | 再試行と複数 tracking ID を混同しない | 1 run 内に attempt 記録が増える | Slurm requeue / tracking 再送 / benchmark 子 run |
| Phase 01 を 01A / 01B に分ける | 最初の実モデル推論成功を堅牢化で遅らせない | 01A の運用能力は明示的に限定 | 01B で基本 robustness、06 で高度な回復・状態検証 |
| 正式名称は MGE Experiment Platform、repository 名は gradio_mde を維持 | MDE を中心的用途に含む MGE / MDE 統合基盤と、当初の Gradio 構想の歴史を表す | 表示名と repository 名が異なるため README で説明する | UI / model / backend / tracking を独立して拡張 |

## README naming and publication plan — 2026-10-07

- Scope: 前節までの文書修正と README の名称・日本語説明を、同じ commit で `main` へ push。
- Order: Phase 00 / 01 計画の修正完了 → 静的検証 → README 更新 → diff / status / file set 確認 → commit / push。
- README: MDE を主要構成要素・中心的ユースケースとして明記。Gradio は UI の一つとし、
  Local / Conda / 将来 Slurm / MLflow / Benchmark と model plugin の拡張方針を維持する。
- Preservation: `gradio_mde`、directory / package 名、architecture、roadmap、文書 index、未実装表記を維持。
- Validation: Markdown links / anchors、phase 必須節、fenced blocks、Git diff / status、文書のみの変更、
  secrets / credentials・weights・runs・環境生成物が commit 対象にないことを確認する。
- Git: workspace の Git metadata が利用できないため、既存の一時 checkout で remote / branch を確認し、
  文書のみを同期する。remote の他の変更は上書きせず、通常の push を使う。
- Risk / rollback: 文書内容と GitHub 内容の不一致を同期・diff で防ぐ。commit 前は文書を復元可能。
  push 後の訂正は別途 revert / 修正 commit とし、force push しない。
- Phase boundary: Phase 01 は計画のみ。次 phase の実装はユーザーの明示指示があるまで開始しない。

## GitHub snapshot — 2026-10-07

- Target: `Minoru-kuma/gradio_mde`、remote `git@github.com:Minoru-kuma/gradio_mde.git`。
- Scope: 現段階の 19 Markdown 文書を初期コミットとして `main` に登録する。
- Evidence: GitHub metadata と remote refs を確認し、登録前の repository は空。
- Method: workspace の `.git` は読み取り専用のため、一時 checkout で文書だけを commit / push。
  local source 文書と checkout の内容が一致することを確認する。
- Validation: phase 必須節・相対リンク、commit の file set、push 後の remote commit を確認する。
- Result: 初期コミット `1e4167b` を main へ push し、19 文書の remote content を照合済み。
- Phase boundary: この snapshot 保存時点では source audit の回答待ちだった。
  その後のユーザーの clean-start 決定により gate は解消。Phase 01 の実装は未開始。
