# Phase 01 — Single Model + Local Execution + Miniconda

Status: **Phase 01 — COMPLETE**（2026-10-12）。
**01A — COMPLETE、01B — COMPLETE**。Phase 02 の実装は NOT_STARTED / 未承認。
2026-10-13 の Phase 02 文書整備のみ承認。管理は [PLANS](../../PLANS.md) を参照。
01A のMoGe CPU E2E経路を維持し、01BのLocal robustnessとCPU regression smokeを検証した。
既存layout / protocol major 1を維持。完了を次phaseの実装承認としない。
管理: [PLANS.md](../../PLANS.md)。

## Goal

最優先は **01A — Minimum Local E2E** の実モデル推論成功。
次の 9 要素を通る最小経路を成立させ、その後に **01B — Local robustness** を行う。

| 必須要素 | 01A の最小到達点 |
| --- | --- |
| 1. 1つのモデル | 1 family / 1 variant / 1 checkpoint を選定 |
| 2. 1つの入力画像 | single-view RGB image 1 枚 |
| 3. 1つの独立 Conda / Miniconda environment | selected model の環境を 1 つ定義・利用 |
| 4. subprocess worker | その環境で 1 job / 1 process を起動 |
| 5. ModelAdapter | load → predict → unload を worker 内で実行 |
| 6. LocalBackend | submit / status / collect の経路で実行 |
| 7. 共通 MDEOutput | depth と解釈に必要な metadata を返す |
| 8. Run Directory | configurable root 以下に input / job / output / logs を保存 |
| 9. raw depth と metadata / result / log | numeric depth と JSON report、stdout / stderr を回収 |

最小経路: CLI / thin Runner → LocalBackend → selected Conda environment の worker →
ModelAdapter → MDEOutput → Run Directory → collect。

## Background

UI / cluster より前に推論、環境分離、結果契約を確認する。
ユーザーの動作経験がある MoGe を最初のモデルとし、公式 upstream を調査して
MoGe-2 ViT-S Normal の source / checkpoint を固定した。latest を自動採用しない。
選定根拠と固定版は [PLANS](../../PLANS.md#01a-selection--preflight) と
[plugin README](../../models/moge/README.md)。この repository は正式な clean-start で、既存 production implementation の
取り込み・互換移行を開始条件にしない。過去の動作コードは必要に応じた参考資料として確認する。

## Scope

### 01A — Minimum Local E2E

上記 9 要素を満たす最小契約・薄い Runner / RunStore / worker 起動 helper、1 adapter と
1 manifest、1 environment.yml、LocalBackend、単純な CLI / service entrypoint。
モデル名による core 分岐を作らず、選択 manifest の metadata / entrypoint を使う。
汎用 plugin discovery や provider framework を先に完成させる必要はない。

制御側から worker を起動し、process poll と result validation で成功 / 失敗を判定する。
`submit()` は handle を返し、呼出し側は単純な poll loop で待てばよい。
一度に 1 job の手動実行を前提とし、queue / GPU lease / concurrency manager を作らない。
01A 当時は共通 cancel signature を保持し、backend は `supports_cancel = false` を宣言し、
呼ばれたら明示的な UnsupportedOperation とする。cancel / timeout の実装完了は 01B の条件。

新規整備するモデル環境は 1 つ。Runner は既存の制御側 Python から起動できればよく、
Gradio / mde-ui 環境・MLflow・Tracking framework の準備を 01A の前提にしない。
artifact は必須 depth / metadata / reports / logs を優先し、optional output・詳細性能計測は exit に含めない。

### 01B — Local robustness

01A の成功を確認後、基本 cancel / execution timeout、子 process 終了、単一 worker の busy guard、
不正・欠落 result の validation、基本 runtime / GPU allocator 計測、環境再現手順を整える。
GPU lease は必要性を確認して別途 scope に入れるもので、01A / 01B の既定の必須成果にしない。
高度な復旧・retry・multi-GPU queue は Phase 06 以降に引き継ぐ。

## Non-goals

Phase 01 全体: Gradio、2 モデル目、MLflow server、Benchmark、Slurm、distributed inference、
worker pool、複雑な plugin / environment provisioning framework。

01A: GPU lease、queue、cancel / timeout API の完成、厳密な性能計測、環境 lock 完全化、
retry / reconciliation、application restart recovery、複雑な concurrency、legacy CLI migration。
01B: 高度な retry / reconciliation、active job の restart recovery、multi-process / multi-host GPU 調停。
将来の interface は維持するが、その全運用能力を最初の推論成功の条件にしない。

## Dependencies

Phase 00 は COMPLETE、source audit gate は解消済み。
01A は承認済み、初期モデル / variant / checkpoint と Miniconda / Conda は確認済み。
GPU / driver は利用できず、ユーザー指示に基づいて CPU を明示選択し実推論を確認した。
[Adapter](../model-adapter-spec.md)、[Environment](../environment-strategy.md)、
[Backend](../execution-backend-spec.md)、[Run Directory](../run-directory-spec.md) の契約。
ユーザーが CPU を選ぶ場合は対応 variant の確認が必要で、GPU 不可時に黙って CPU fallback しない。
01B は 01A の実モデル成功と、01B の作業を含むユーザーの実装指示が前提。
過去コードの取得は mandatory dependency ではない。

## Implementation tasks

### 01A tasks — first inference success

- [x] 初期 model / variant / checkpoint / upstream revision と 1 枚の input を選定して plan に記録。
- [x] selected model の manifest / environment.yml と最小 adapter を用意。
- [x] common contracts を用意し、adapter import / torch / model dependency を worker 側に閉じる。
- [x] configurable Run Root と初回 `attempt-0001` の input / JobSpec / output / logs を準備。
- [x] logical environment を Local profile に解決し、argv で Conda subprocess worker を起動。
- [x] worker で load → predict → serialize を行い、正常時・通常例外の finally で unload（fake 検証）。
- [x] raw depth、depth kind / scale / units / shape、model / environment / device metadata、report の保存を実装（fake 検証）。
- [x] stdout / stderr を捕捉し、worker 非ゼロ終了・欠落 report を成功にしない。
- [x] LocalBackend.submit / status / collect を thin Runner / CLI から使い、1 枚の実推論を成功させる。
- [x] 証拠の Run ID / artifacts / 起動条件と 01A の能力制限を docs に残す。

### 01B tasks — after 01A acceptance

- [x] cancel / timeout と process group の停止、子 worker の終了確認を実装。
- [x] same LocalBackend instance の同時 submit は busy として拒否する簡単な guard を整備。
  GPU 全体の lease・他 process との調停には拡張しない。
- [x] malformed job / unknown environment / corrupt result / checksum / path validation を補強。
- [x] load / prediction / serialization timing と optional allocator memory の計測を整備。
- [x] environment の実測 fingerprint、再作成手順、保存済み terminal result の再 collect を確認。
- [x] CLI error / cancel の説明、未対応 ResourceSpec / backend operations を明示。
- [x] unsupported → supported cancel の capability を更新し、01A の E2E regression を確認。

## Tests

01A は下記の contract / fake tests と実モデル CPU smoke を確認済み。それぞれの証拠を分けて記録する。
01B tests とCPU regressionも2026-10-12に実行済み（下記acceptance evidence）。

### 01A tests

- fake adapter の別 subprocess で Job → depth / report / logs → LocalBackend.collect を確認。
- 制御側に torch / model import がなく、worker が指定の Conda 環境で起動すること。
- raw depth の shape / dtype / depth semantics と JSON reference の一致、optional outputs の欠如。
- 通常 worker failure / 非ゼロ終了 / 必須 depth 欠落を成功扱いせず、stderr を回収できること。
- Run Root 設定 / MDE_RUN_ROOT、1 input / 1 attempt の記録、collect が再推論しないこと。
- 実機: **選定した 1 モデル・1 画像・1 独立環境の real inference 成功**と成果物の読み戻し。
  過去 baseline があれば参考比較できるが、その入手を 01A の exit 条件にしない。

### 01B tests

- running cancel / timeout、Conda wrapper の子 worker 終了、CANCELLED / FAILED の区別。
- same backend instance の busy rejection と終了後の次の単一 job。
- malformed job、unknown environment、corrupt / missing report、checksum / path errors。
- persisted terminal result の再 collect、環境再作成 smoke、計測値の units / scope。
- 01A の single inference regression。高度な並列 / crash recovery tests は Phase 06 へ。

実機結果と fake tests を分け、実モデル推論を実行していない場合に成功を主張しない。
CPU を明示選択して実行した結果は CPU と記録し、GPU 実行済みとは扱わない。

### Current evidence — 2026-10-09

独立 `mde-moge` の Python 3.11.14 で fake worker を起動し、8件の contract tests が成功（22.269秒）。
必須 depth / result 欠落と通常例外を FAILED とし、stdout / stderr と cleanup を確認した。
終了コード0でも depth file / result が欠けるケースを FAILED と確認した。
raw depth の fake 出力は float32 256×256 / relative / arbitrary で、実モデルの出力ではない。
source / checkpoint は固定、checkpoint の SHA-256 は照合済み。
MoGe real inference は未実行。NVIDIA device / driver が見えず、CPU を黙って代用しない。
real Run ID / torch runtime / GPU / raw depth の証拠は成功時に追記する。
Markdown のリンク / 必須節 / fenced blocks と、Python AST / JSON / TOML の静的検証も成功。

### Pre-inference preparation evidence — 2026-10-11

- 中断後の現行コードで fake suite 8件が成功（18.968秒）。ログを Git 管理外の `.local/validation/` に保持。
- checkpoint の SHA-256 を再照合して一致。実モデル job は未投入、real Run ID / raw depth はまだない。
- 独立 `mde-moge` に Python 3.11.14 / MoGe 2.0.0 / utils3d 1.3 / 基本推論依存は存在する。
  torch / torchvision は未導入。既存 CUDA wheel 5個は cache に保持している。
- 残り依存導入、native API import、GPU / CPU の明示的な実行先確認、実モデル E2E と成果物検証を
  再開後に行う。fake 成功と準備完了を実モデル成功と扱わない。
- exit 未達のため completion commit / push はまだ行わない。01B / 02 以降には進まない。

## Exit criteria

### 01A acceptance evidence — 2026-10-11

| 項目 | 確認結果 |
| --- | --- |
| 実モデル / 入力 / backend | MoGe-2 ViT-S Normal × NASA sample RGB 256×256 1枚 × LocalBackend |
| Run ID | `9c5b6556-30d3-43ae-827f-7bd8b0a47580` |
| Upstream revision | `07444410f1e33f402353b99d6ccd26bd31e469e8`、package 2.0.0 |
| Checkpoint | `Ruicheng/moge-2-vits-normal` / `model.pt`、revision `26b477f41595707c5db6770294c0d1721e8ed4ed` |
| Checkpoint SHA-256 | `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc` |
| 独立 environment / Python | `mde-moge` / CPython 3.11.14。control とは別 prefix / process |
| torch / torchvision / runtime | 2.6.0+cu124 / 0.21.0+cu124 / torch.version.cuda=12.4 |
| 実行 device / GPU | 明示 CPU（Intel Core Ultra 5 125U）、cuda_available=false、GPU / driver=null。GPU 実行は未検証 |
| raw depth | `runs/<run_id>/output/attempt-0001/views/view-0001/depth.npy`、float32 `[256,256]` |
| depth semantics | z_depth / metric / m、OpenCV camera frame。65,536 pixel 有効、invalid 0。値域 0.8110444–4.2878127 m |
| WorkerResult / JobResult | outcome / status は COMPLETED、worker exit_code=0。metadata の実行情報とも一致 |
| Run Directory | 必須12 file、全 JSON の Run ID、JobSpec snapshots、checksum、NPY header と NumPy 読戻しを確認 |
| stdout / stderr / cleanup | load / predict / saved / unload の stdout と upstream CPU autocast 警告の stderr を保存 |
| Contract tests | 依存導入後8件成功（17.025秒）。制御側には torch / MoGe / NumPy / Pillow の import なし |
| Provenance | git_commit=unknown、source_digest を保存。workspace の Git metadata が利用不可 |

Goal の9要素をすべて通ったため 01A は COMPLETE とする。GT / benchmark のない smoke であり、
metric accuracy や GPU / driver 互換性を保証しない。CPU float32 に対する upstream autocast 警告は
autocast が無効化されたという通知で、明示した device / dtype は維持されている。
ローカル証拠は `.local/validation/` と `runs/<run_id>/` に保持し、Git に実験生成物を含めない。

### 01A exit

Goal の 9 要素すべてを通る real inference が 1 回以上成功し、Run ID と raw depth / metadata /
WorkerResult / JobResult / stdout / stderr を保存・読み戻しできる。
モデル推論は worker 内の ModelAdapter、起動は LocalBackend の公開 interface を通る。
depth の意味、使用 model / checkpoint / environment / device が記録され、制御側に model / torch の
必須依存がない。環境定義と最小起動手順、未対応機能を記録する。
**GPU lease、cancel 完成、retry、restart recovery、concurrency は 01A exit の条件ではない。**

### 01B acceptance evidence — 2026-10-12

2026-10-12のユーザー実装指示に基づき01Bのみ追加。Phase 02以降には進まない。

| 項目 | 確認結果 |
| --- | --- |
| 01A regression（変更前） | 独立環境再作成後8件成功、9.501秒。環境不足時の初回5 failuresと区別 |
| 最終tests | 29件成功、53.102秒。既存8件と追加21件。cancel未対応の旧期待値は01Bのcapabilityへ更新 |
| cancel | SIGTERM / grace / SIGKILL、CANCELLED、再cancel冪等、完了優先の競合、停止確認失敗時はRUNNING維持 |
| timeout | status pollingなしでtimerが発火、FAILED / TIMEOUT。SIGTERMを無視するworker・子も停止 |
| process終了 | Conda wrapperをwait、worker / child PIDが/procから消失。graceful / 強制停止 / wrapper先行終了を検証 |
| busy | 同じinstanceの別submitを拒否。同一specは同じhandle、変更specはconflict。終了後の次jobが成功 |
| report / artifacts | malformed / missing / corrupt、型・schema・ID・error、depth / metadata / checksum / path / symlink / unit / shape。確定後破損はArtifactIntegrityErrorでterminal不変 |
| terminal再collect | 新backend / 新CLIでも成功。worker未起動、predict log 1回、全filesのhash / mtime不変。FAILED / CANCELLEDも再読込。active recoveryは拒否 |
| 互換性 | 01A形式のfingerprint / metrics未追加結果を読戻し。layout / schema_version 1.0 / depth-only維持 |
| 環境再作成 | environment.ymlから.local/envs/mde-mogeへ作成。固定MoGe / utils3dを--no-deps導入、checkpoint SHA-256照合。base / system変更なし |
| runtime | CPython 3.11.14、torch 2.6.0+cu124、torchvision 0.21.0+cu124、torch CUDA runtime 12.4、device=cpu、cuda_available=false、GPU / driver=null |
| fingerprint | Python distribution 42件、Conda package 24件。Python / OS / arch / prefix、定義・package list・全体SHA-256。任意環境変数やcredentialを保存しない |
| definition digest | b582cfa5e7c85d5d9d48b6dd08f64ce142f546f4831ddcecc8e1d95065224d98 |
| Python package list digest | a4d8eea7de469c9a57fa37f71780e5220a62753a35a10544b23456741884a404 |
| environment fingerprint digest | c38cf05fd74cd90d540e747b3c22befd56fc50d2b10549e4c3fe627408c4edf1 |
| MoGe CPU Run ID | f4a2052f-71da-4664-9c9f-281cca95fb41、COMPLETED / exit 0。固定source / checkpointは01Aと同じ |
| raw depth | float32 [256,256]、z_depth / metric / m、65,536 valid / 0 invalid、0.81104505–4.28780937 m。必須12 files / JSON / logs / NumPy読み戻し成功 |
| basic timing | load 2.339091 s、predict 2.157162 s、depth serialization 0.001107 s、unload 0.077755 s、metadata 0.000749 s、worker execute 4.699339 s。各scopeはEnvironment仕様に記載 |
| CUDA allocator | CPUではkeyなし（未計測）。CUDA synchronize / peak APIはmock検証。実GPUは未検証 |
| CUDA no fallback | dfc5b6d3-80c5-42b8-a28e-ec7d7f413c11、cuda:0要求はFAILED / load / CUDA unavailable、outputs空。CPUに切替なし |
| CLI | SIGINTでgroup停止 / exit 130、worker失敗exit 1と構造化理由、invalid timeout / 未対応は明示エラー。collectはConda不要 |

logs / summaryは.local/validation/、実モデル成果物はruns/に保持しGit管理外。
精度評価やbenchmark、GPU互換性の証拠ではない。推移依存の完全lockやupstream全extras / pip check
の成功は保証しない。実測fingerprintと固定定義を区別する。git_commitは既存のunknownのまま、
source_digestで実行sourceを識別。GPU lease / queue / retry / active recovery等は未実装。
01B exitを充足し、01A / 01B / Phase 01をCOMPLETEとする。

### 01B exit

01A の経路を維持して基本 cancel / timeout、子 process 終了、instance 内の busy guard、
不正 result の検出、基本計測・環境再現手順・terminal result の再 collect が確認される。
高度な reconciliation / restart recovery / GPU lease を追加していなくても 01B を完了できる。

01A / 01B の達成を別々に記録し、両方を満たした時点で Phase 01 全体を COMPLETE とする。
milestone 完了は次 milestone / Phase 02 の実装承認ではない。

## Known risks

checkpoint / upstream API、driver / torch build 不整合、extension build、GPU OOM。
01A は手動の単一 job に限定し、他の GPU process との調停、cancel / timeout、制御側 crash 後の回復を
保証しない。これらの制限を capability / docs に明示し、失敗を隠して再実行しない。
過去コードの未入手は source audit blocker ではない。01B は子 process の終了確認が特に重要。

## Decisions deferred to later phases

01B: 基本 cancel / timeout / instrumentation / validation の詳細。
02: UI / viewer。03: 2・3 モデル目、directory plugin discovery、camera / optional outputs の実機 matrix、
必要時の過去コード参考確認。04: Tracking。05: dataset evaluation。
06: GPU lease の必要性判断、複雑な queue / concurrency、submit retry / reconciliation、
application restart recovery、mock scheduler。07–08: site と cluster failure / retry policy。
warm worker / distributed inference は別の将来計画。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| adapter / backend / worker を 1 モデルから使う | 後の責務分離 refactor を避ける | 最小 E2E に薄い共通層が必要 | multi-model / Slurm |
| cold process を基準にする | 環境隔離と cleanup を最初に検証する | load overhead が毎回発生 | 契約を維持した warm pool |
| 01A の exit は 9 要素の first real inference と保存結果 | 初期成功を robustness で遅らせない | 01A は単一手動実行で運用保証が限定 | 01B の基本 robustness、06 の高度な回復 |
| 未対応 cancel / resources は capability と明示エラーで表す | interface を維持し未実装を成功扱いしない | caller が capability を確認する必要 | 01B で同じ signature に機能を追加 |
