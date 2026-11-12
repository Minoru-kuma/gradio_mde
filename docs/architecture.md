# Architecture

Status: Phase 00 COMPLETE。Phase 01A の最小経路を実装し、fake tests を確認済み。
MoGe の明示 CPU E2E と成果物検証、Local robustness / CPU regression により
01A / 01B / Phase 01 COMPLETE。GPU は未検証。02AはCOMPLETE。02BのGradio操作は全Exit達成でCOMPLETE、02Cは2026-10-27に全Exit達成でCOMPLETE、02Dも全Exit達成でCOMPLETE。Phase 03は2026-11-11に実装承認、段階実装中。Phase 04以降は未承認。
以下の全体図には将来設計も含む。

## License decision policy

全Phase・全モデルの判断は[AGENTSの共通方針](../AGENTS.md#license-review-and-decisions)を正本とする。
非商用の研究・検証を主用途とし、ソース / checkpointの条件・不明点・予定行為を分けて記録する。
条件内の利用は通常進め、不確実性だけで独立作業を一律停止しない。直接影響する行為は用途・リスクを整理し、
必要に応じユーザー判断を求める。禁止との衝突や重大な権利リスクは該当作業のみ停止する。
作者への照会は共通必須条件にせず、商用 / 重み再配布 / 公開package同梱はlocal研究利用と別に判断する。
これは開発運用の方針であり、Model / Environment / Backendの責務やschemaに新しい許可判定を追加しない。
Phase承認、技術的受入、重大な安全性・互換性問題の停止条件は維持する。

## Publication and model provisioning

公開・配布対象はプラットフォーム本体と自作Adapter。外部モデルsource / checkpointは原則同梱・再配布せず、
利用者が公式配布元から必要なモデルを別途準備し、各配布元の条件に従う構成とする。
自作のmanifest / environment定義 / 準備scriptで取得先と固定版・digest・条件の出典を案内する。
local研究用の準備と配布物への同梱は分け、license不確実性は上記の共通方針で影響範囲を限定して判断する。
詳細は[公開・配布仕様](distribution-policy.md)。既存の責務分離・実装実績・Phaseの承認やExit条件は維持する。

## Repository investigation

調査日: 2026-10-07。対象: `gradio_mde` の repository root。

| 調査項目 | 方法 | 確認結果 | 設計への影響 |
| --- | --- | --- | --- |
| 現在位置 / root | `pwd`、path resolve、`ls -la` | 指定 root に一致 | 別 root を対象にした調査ではない |
| 可視 directory 全体 | hidden を含む `rg --files` と recursive walk | 空の `.git` / `.agents` / `.codex` / `.aws` のみ | 既存 production file は見えない |
| 作業指示 | root と上位の AGENTS.md 探索 | 可視範囲に既存 AGENTS.md なし | 今回入口を新規作成 |
| 履歴 / 差分 | `git status --short --branch`、`git log -5 --oneline` | `not a git repository` | commit・dirty state は unknown、変更 diff を取得不可 |
| モデル / UI / Slurm | 全可視 file の確認 | 実装や起動スクリプトを確認できず | 動作済みと記載しない |
| 依存 / 環境 / tests | 同上 | pyproject / requirements / environment.yml 等なし | exact version、既存環境名、test command は未確認 |

文書作成前の可視構造:

```text
gradio_mde/
├── .git/      # 空、Git metadata を確認できない
├── .agents/   # 空
├── .codex/    # 空
└── .aws/      # 空
```

過去に 3 モデルを個別に動作させた情報、Gradio / Slurm 同時実装で複雑化した情報は
ユーザー提供の背景であり、ソースを実見した結果とは分ける。上の表は文書作成前の調査記録。
その後、ユーザー指定の GitHub repository へ Phase 00 文書を集約した。
保護された空 directory の理由、研究室への接続経路は推測しない。

### Existing-code reuse gate

2026-10-07 のユーザー決定により、source audit gate は充足した。

1. この repository 内には再利用必須の既存 production implementation は存在しない。
2. 新しい実験基盤の clean-start repository として正式に開始する。
3. 過去の MoGe / UniK3D / DA3 個別コードは repository 外の参考資料であり、
   必要に応じて Phase 01 / Phase 03 で確認する。取得・移植は Phase 00 の完了条件ではない。

参考コードを確認する際は model / checkpoint / upstream revision、Python / torch / CUDA 条件、
前後処理、depth の意味・単位、export の再利用候補を記録する。利用する処理は adapter の境界に
閉じ込め、当該環境で再検証する。参考コードをこの repository の実装済み機能や保証済み baseline
として扱わず、旧 CLI / output の移行を初回 E2E の前提にしない。

## Responsibilities and dependency rules

| Component | 責務 / 公開契約 | 依存してよい対象 | 持たない責務 |
| --- | --- | --- | --- |
| Gradio | 入力、選択、進捗、可視化、download | Registry metadata、Runner、backend catalog | model import、Conda 起動、sbatch、MLflow 記録 |
| ExperimentRunner | 検証、Run ID、入力保存、Job 作成、submit / collect、結果・評価・tracking 調整 | 共通契約、Registry、Backend、Storage、TrackingSink | torch inference、scheduler command、環境 activation |
| Model Registry | manifest 発見、ModelInfo / variant / capability / parameter schema | metadata reader、schema | adapter import、重み loading、Conda activation |
| ModelAdapter | load / predict / unload、モデル前後処理、共通出力への変換 | worker contracts、当該 upstream 依存 | Gradio、Slurm、MLflow、実行場所選択 |
| Environment Resolver | logical environment と target profile を起動情報へ解決 | EnvironmentSpec、設定、launcher | モデル inference、scheduler 状態管理 |
| Worker Manager | process 起動・監視、worker protocol とログ。終了制御は 01B、GPU lease は必要性を後で判断 | Resolver、process interface、Run Store | モデルごとの実行分岐、MLflow、UI |
| ExecutionBackend | submit / status / cancel / collect | Job 契約、Storage、実行 adapter | モデル API / preprocessing |
| LocalBackend | process handle、worker manager の呼び出し。01A は単一 subprocess、queue は後の拡張 | local Worker Manager | Runner 内への subprocess 直書き |
| SlurmBackend（将来） | scheduler / site profile、job ID、状態正規化、共有成果物回収 | Slurm command adapter、shared Store | モデル名で分岐した runner |
| Artifact Storage | Run Root、file publication、checksum、result validation / access | filesystem interface、共通契約 | モデル評価、MLflow 内部 ID の生成 |
| TrackingSink / MLflow | Runner から受け取った実験情報の記録と再送 | JobResult / provenance、MLflow client（UI 側のみ） | worker の必須依存、artifact の唯一の保存先 |

worker 用の薄い共通契約は UI / tracking / upstream package を import しない。
Runtime の array handling はモデル環境内で完結し、境界を越えるのは JSON と file reference。

```mermaid
flowchart TD
    User[Gradio / CLI / Benchmark] --> Runner[ExperimentRunner]
    User --> Registry[Model Registry: manifest only]
    Runner --> Registry
    Runner --> Backend[ExecutionBackend interface]
    Backend --> Local[LocalBackend]
    Backend --> Mock[MockSlurmBackend: Phase 06]
    Backend --> Slurm[SlurmBackend: Phase 07 onward]
    Local --> WMLocal[Worker Manager: local target]
    Slurm --> Scheduler[Slurm scheduler + shared Run Directory]
    Scheduler --> WMRemote[Worker Manager / bootstrap: compute target]
    WMLocal --> Resolver[Environment Resolver + launcher]
    WMRemote --> Resolver
    Resolver --> Worker[Generic worker in selected Conda environment]
    Worker --> Adapter[ModelAdapter]
    Adapter --> Upstream[Selected model package + checkpoint]
    Runner --> Store[Artifact Storage]
    Worker --> Store
    Slurm --> Store
    Runner --> Sink[TrackingSink]
    Sink --> Noop[No-op until Phase 04]
    Sink --> MLflow[MLflow client in application environment]
```

矢印は操作・データの関係を表す。MLflow SDK を model worker に import する関係ではない。
Local と Slurm で同じ JobSpec / Result を使うが、環境 prefix と Run Root は実行先で解決する。
図は段階的に構築する全体像。01A は単一 manifest、薄い Runner / Store / environment launcher と
LocalBackend / worker の経路だけを実装対象とし、UI、TrackingSink、queue、plugin discovery の
汎用 framework を最初の成功条件にしない。

## Public application interfaces

UI / CLI / Benchmark は共通 application service を使う。以下は将来の概念 signature。

```text
Registry.list_models() -> list[ModelInfo]
Registry.get_model(model_id, variant_id) -> resolved ModelInfo
BackendCatalog.list_profiles() -> list[BackendProfileInfo]
ExperimentRunner.submit(request: RunRequest) -> RunHandle
ExperimentRunner.status(handle: RunHandle) -> RunStatus
ExperimentRunner.cancel(handle: RunHandle, reason) -> CancelReceipt
ExperimentRunner.collect(handle: RunHandle) -> RunResult
ExperimentRunner.artifacts(handle: RunHandle) -> list[ArtifactRef]
```

RunRequest はモデル / variant、logical environment の選択、backend profile、入力参照、
parameters / requested outputs / resources を持つ。Runner が検証して Run ID / JobSpec を作る。
RunHandle は run / attempt ID と永続 handle の参照であり、特定 backend の PID を UI に要求しない。
RunStatus / RunResult は JobStatus / JobResult と tracking_state / optional evaluation を包む。
UI は raw file publication や worker report を直接見て完了判定しない。
公開 artifacts は確定した selected attempt の検証済み reference とする。
BackendCatalog は利用可能な profile と準備状態の metadata を返し、UI が Backend を直接起動しない。

01A の実装済み subset は `ModelRegistry.get_model(model_id)` と
`ExperimentRunner.submit(model_id, image, variant_id=None, device, dtype, parameters)`。
submit は `JobHandle`、status は `JobStatusSnapshot`、collect は `JobResult` を返す。
CLI が LocalBackend を構成し、Runner は ExecutionBackend の公開契約のみを使う。
01B では submit に optional `walltime_seconds` を追加。cancel は CancelReceipt を返す。
LocalBackend は instance の RLock / busy guard と job ごとの execution timer を持ち、
WorkerProcess の独立 process group を停止確認して結果を確定する。複数 instance 間の調停はしない。
新しい backend は保存済み terminal 結果だけを読み戻せる。active job recovery は拒否する。
区間計測・環境観測は共通 worker / runtime module、検証は Storage に置く。
RunRequest / RunHandle wrapper、catalog / discovery / tracking はまだ実装しない。

## Planned package topology

以下は将来の配置案。01A では各責務を同名の小さな `.py` module に実装する。
01A で全 directory / service を完成させる必要はなく、責務の境界を保った最小構成から始める。

```text
src/mde/
  contracts/         # model / job / result / environment schema、版管理
  registry/          # manifest discovery、metadata validation
  runner/            # orchestration、共通 evaluation 呼び出し
  environments/      # resolver と conda / future micromamba launcher
  workers/           # generic worker、process lifecycle、serialization
  backends/          # Local と将来 plugin の共通 interface
  storage/           # RunStore、atomic publication、artifact readers
  tracking/          # NoOpTracking / MLflowTracking
  evaluation/        # 共通 metric protocol（Phase 05）
  ui/                # Gradio（Phase 02）
models/<model_name>/
  adapter.py
  manifest.json
  environment.yml
  README.md
  tests/             # model contract と shape / convention の検証
```

モデル追加は原則 `models/<model_name>/` の追加だけで行う。manifest に adapter entrypoint、
upstream / variant、capability、logical environment、params schema を宣言する。
利用者は environment provisioning を別途行う必要があり、directory を追加しただけで
GPU / dependency が準備済みになるわけではない。新しい出力種別が必要な場合だけ共通契約を
版付きで拡張する。01A は source checkout + `PYTHONPATH=src` を基準とし、worker へ src / project root
の import path を渡す。control の pyproject dependencies は空。adapter は `models/` 内の namespace
module であり、source checkout を伴わない wheel 単体配布は現時点では保証しない。

## End-to-end lifecycle

1. Runner が metadata に基づき要求を検証し、immutable JobSpec と入力を Store に準備する。
2. backend が JobSpec を受理して JobHandle を返す。Runner は handle を永続化する。
3. backend 側で logical environment を実行 target の profile に解決する。
4. Worker Manager が共通 worker を起動する。worker だけが adapter entrypoint を import する。
5. worker は version / input / environment を確認し、load → predict → serialize → unload を行う。
6. result manifest を最後に atomic publish する。backend は process / scheduler と manifest の
   両方を確認し、契約上の成功を判定する。
7. Runner は collect 結果を検証し、表示・共通評価・tracking に渡す。
   UI が閉じても保存結果を再収集できる。

Phase 01 の worker は原則 1 job / 1 process。01A は利用者が単一 job を起動する最小経路とし、
GPU lease / queue / concurrency 制御を要求しない。cancel / timeout と同一 Backend instance の
二重起動拒否は 01B、高度な retry / reconciliation / application restart recovery は Phase 06 以降。
GPU lease の必要性も実際の競合要件を確認して後で判断する。warm worker pool、job arrays、
並列評価は後の拡張。上の lifecycle にある tracking / 再収集も各 milestone の範囲で追加する。

## UI and benchmark contracts

UI は capability の `supported / conditional / unsupported` と実際の artifact の有無を見て
depth / points / normals / intrinsics / rays / pose / confidence を表示する。
parameter controls は manifest の schema から生成し、モデル名による callback 分岐を増やさない。
計測値は worker の実測値と Runner の経過時間を区別し、未測定値は unavailable と表示する。

BenchmarkCoordinator（Phase 05）は image × model × config を複数の通常 JobSpec に展開し、
同じ Runner / backend / adapter を通す。共通 Evaluator が raw depth を評価し、
比較条件・失敗数・skip 理由を保存する。可視化 PNG を深度評価の入力にしない。

## Architecture decisions

| ID | Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- | --- |
| A01 | Model / Environment / Backend を別識別子にする | モデル × 実行先の直交性を保つ | 設定の参照解決が必要 | 同一 model を Local / Slurm で実行 |
| A02 | Registry は metadata だけを読む | UI 環境へ torch 等を持ち込まない | runtime capability を worker で再確認する | directory discovery / package entrypoint |
| A03 | Phase 01 から subprocess worker | Python / torch / CUDA runtime を隔離 | 起動と serialization の費用 | pool / persistent worker を protocol の上に追加 |
| A04 | JSON + file artifacts の Run protocol | Local / NFS と別環境で同じ契約 | 小さな対話 RPC より遅い | optional streaming progress、Store backend |
| A05 | local Run Store を一次記録にする | Tracking 障害で成果を失わない | MLflow に複製・再送が必要 | remote artifact service / policy-based retention |
| A06 | metric / relative と camera convention を明示 | 不公平な評価と幾何変換の誤りを避ける | adapter の変換責務が増える | rays / multi-view / 新 camera model |
| A07 | 初期モデルは固定版 MoGe-2 ViT-S Normal | 最小公開 checkpoint と metric scale の API を使う | 最新 MoGe-3 / 大きな variant は未検証 | Phase 03 で variant 追加、実測は PLANS に記録 |
| A08 | Slurm は contract と確認表まで | 現地仕様・アクセスが不明 | 現地まで実機保証できない | 07 / 08 の site plugin と integration test |
| A09 | 今後導入する interface / 保存形式の互換性を維持 | clean-start 後に蓄積する実験結果を読めるようにする | schema reader / 移行手順の維持 | deprecation を明示し major schema で変更 |
| A10 | clean-start、外部の過去コードは必要時の参考資料 | repository 内に再利用必須実装がないとユーザーが確認 | 既存実装への適合や旧 baseline は保証しない | 01 / 03 で参考処理を adapter 内へ接続 |
| A11 | Phase 01 を最小 E2E の 01A と基本堅牢化の 01B に分ける | まず 1 model / 1 image の実推論を成立させる | 01A 単独では cancel / timeout / 復旧を保証しない | 共通契約を維持して 01B / 06 / Slurm へ拡張 |

## Open decisions

初期 model / checkpoint / upstream revision は [PLANS](../PLANS.md) に固定した。
GPU 実行の互換性・性能、UI package pin、GT dataset / evaluation protocol、MLflow version / URI、
研究室設定は未確定。各仕様・phase に判断時点を割り当て、値を仮定してコード化しない。
外部の過去コードの所在・利用可否は、参考資料が必要になった 01 / 03 で確認する。

## Phase 02 application / geometry / management boundaries

Phase 02は02A〜02Dの全Exit達成でCOMPLETE。
以下の02A記述は実装前の計画であり、確定契約は末尾を参照。親仕様は [Phase 02](phases/phase-02.md)。
02Aはadapterの意味変換、workerのgeometry serialization、RunStoreのvalidationを拡張する。
02BはInference / Resultsの2タブで既存Runnerを操作、全sessionに1つのLocalBackendを共有する。
sessionごとのinput / handle / selectionは独立。instance busy guardを維持して同時jobは拒否しqueueしない。
Gradio callbackにadapter / torch / Conda / subprocess制御を置かない。

02Cは共通artifact reader / geometry generation / rendererを利用して4表示モードを提供する。
02Dは [Run Management Service](run-management-spec.md) 経由で履歴・metadata・export・archive・deleteを扱う。
derived storageの最小生成 / reuseは02C、管理操作は02D。管理serviceは推論経路を呼ばない。
raw / 確定JobResultは不変、user sidecarとderived manifestを別保存する計画。
UIを閉じることは暗黙cancel / deleteではなく、terminal保存Runを再起動後に読む。
active job recovery・multi-process調停・公開多ユーザーはPhase 02に導入しない。

## Phase 02A implemented geometry boundary

02Aのoptional output要求をRunner / JobSpecに追加し、workerがserialization、RunStoreが
geometry検証を担当する。`mde.geometry`はstdlibのみ、NPYのheader・bounded payload読込で
Points / Depth・normal length・K・maskを検証する。numeric依存はworker、MoGe変換はmodels/mogeに閉じる。
ModelAdapterにStorage / LocalBackend依存を追加せず、coreのモデル名分岐も追加しない。
既定CLI / depth-only保存形式を維持。02BのUI操作境界は下記を参照。02C viewerは下記実装、02D管理は共通Serviceとして実装・検証済み。


## Phase 02B implemented application boundary

独立application環境（Python 3.13.13 / Gradio 6.30.0）に `mde.ui` とUI非依存の
`mde.ui_controller` を追加。composition rootが既存Runner / Backendを一度構成する。
callbackはmodel / torch / Conda / subprocessを制御しない。background observerのみRunnerを操作し、
Gradioはsession snapshotをpollする。全eventはqueue=False、同時推論はnonblocking admissionで拒否。
server-side State tokenとgenerationでhandle / cancel / result selectionを分離し、表示writerは単一Timer。
02B時点のResultsは共通JobResult詳細と既存terminal collectのRun ID読込。
02Cでは`mde.results`と同梱Three.js r180による4モード表示と最小derived保存を追加する。
詳細は [Results Viewer](results-viewer.md)。02D管理操作は [Run Management Service](run-management-spec.md) で提供し、Run単位lockをRunner.collect / Viewer / DerivedStoreと共有する。
PNG制限、pin / offline条件、callback / lifecycleの詳細は [Gradio Inference](gradio-inference.md)。
保存schemaは変更せず、Runner.collectのsummary publicationを同instance内で直列化して
同内容の再collectをread-onlyにした。raw / 確定JobResultを変更しない。

## Phase 03.1 implemented plugin discovery

Registryにmetadata-only directory探索・一覧・不正manifest診断・重複ID拒否を追加。
ModelInfoの実効variant解決をRunner / CLI / controllerが共有する。
Environment / Backend / workerの責務は維持し、core / UI / backendにモデル名分岐を追加しない。
source checkoutのdirectory追加だけでfake pluginを発見・実行できる。
model別target設定と動的UIは03.3、geometry拡張とmulti-viewは03.4 / 03.5で追加予定。
詳細は [Model adapter](model-adapter-spec.md#phase-031-discovery-and-effective-variant-metadata)。


## Phase 03.3 implemented application boundary

Gradio now selects model / variant metadata per session and rebuilds schema controls without model imports.
Server configuration tickets and accepted-job snapshots keep model / parameters / checkpoint selections separate.
A single Runner / Backend / admission slot serves every browser; selection events do not queue inference.
`mde.targets` reads local target configuration; WorkerManager resolves per-variant checkpoint locations from JobSpec.
ModelAdapter still owns native conversion and digest verification, while Environment / Backend own execution.
CLI legacy flags and existing Run readers remain compatible. See [target configuration](target-configuration.md)
and [Gradio contract](gradio-inference.md#phase-033-model--variant-switching).
03.1 / 03.2 / 03.3 acceptance passed. The instruction to stop at 03.3 is historical;
work resumed for 03.4, initially stopped at the UniK3D license-evidence adoption gate, then resumed
independent adapter / synthetic geometry work under the revised stop conditions.
See [investigation and resume conditions](unik3d-investigation.md).
Historically 03.4 had only an injected synthetic runtime and no production manifest / real bridge.
A later scoped user decision allowed fixed Small acquisition and noncommercial local CPU research, while source / checkpoint terms remain unresolved.
The documentation-only update itself did not release the hold. The subsequent action-specific decision is recorded
in the investigation; redistribution / public bundling / commercial use remain outside that decision.
Depth / native points reuse existing profiles; core / UI / backend and schema are unchanged.
03.4 native Small CPU E2E and native Points validation now pass. 03.5–03.6 remain unimplemented; Phase 03 is not COMPLETE.

## Phase 03.4 runtime capability preflight

The resumed implementation adds model-independent capability checks after load and before predict.
A nonempty runtime map must explicitly permit every requested output; malformed, missing or unsupported
declarations fail before prediction. Empty maps retain legacy behavior with a warning. Conditional
declarations still require actual output validation. The optional execution.runtime_capability_check
records a validated JSON snapshot. Existing profiles, schema major and old Run readers remain compatible.
The UniK3D checkpoint decision is scoped separately from this independent work; subsequent native CPU E2E passed.

## Phase 03.4 native Small integration

The self-authored UniK3D plugin wraps a separately installed, pinned official source and prepared local
checkpoint. CPU-only torch / float32, source revision and two file digests are checked before native inference.
Native distance and Points use existing profiles with unknown units / scale; no pinhole K or Points are synthesized.
Unsupported native rays / confidence / pose are not exported. Their absence does not require a new profile
for this accepted depth / Points integration. Existing UI / Registry / Runner / Backend remain model-independent.
See the [plugin](../models/unik3d/README.md) and [03.4 acceptance](phases/phase-03.md#034-acceptance-evidence--pass).
