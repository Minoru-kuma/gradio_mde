# Phase 01 — Single Model + Local Execution + Miniconda

Status: **計画整理済み / production code 未着手・未承認**。
01A / 01B は内部 milestone。今回行うのは計画更新だけで、実装開始にはユーザーの指示が必要。
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
候補はユーザーの動作経験がある MoGe。ただし具体的な世代・weights・既存スクリプトは未確認で、
latest を自動採用しない。この repository は正式な clean-start で、既存 production implementation の
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
共通 cancel signature は保持するが、01A の backend は `supports_cancel = false` を宣言し、
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
01A の実装指示、初期モデル / variant / checkpoint の選定、利用可能な Miniconda / Conda と GPU / driver。
[Adapter](../model-adapter-spec.md)、[Environment](../environment-strategy.md)、
[Backend](../execution-backend-spec.md)、[Run Directory](../run-directory-spec.md) の契約。
ユーザーが CPU を選ぶ場合は対応 variant の確認が必要で、GPU 不可時に黙って CPU fallback しない。
01B は 01A の実モデル成功と、01B の作業を含むユーザーの実装指示が前提。
過去コードの取得は mandatory dependency ではない。

## Implementation tasks

### 01A tasks — first inference success

- [ ] 初期 model / variant / checkpoint / upstream revision と 1 枚の input を選定して plan に記録。
- [ ] selected model の manifest / environment.yml と最小 adapter を用意。
- [ ] common contracts を用意し、adapter import / torch / model dependency を worker 側に閉じる。
- [ ] configurable Run Root と初回 `attempt-0001` の input / JobSpec / output / logs を準備。
- [ ] logical environment を Local profile に解決し、argv で Conda subprocess worker を起動。
- [ ] worker で load → predict → serialize を行い、正常時・通常例外の finally で unload。
- [ ] raw depth、depth kind / scale / units / shape、model / environment / device metadata、report を保存。
- [ ] stdout / stderr を捕捉し、worker 非ゼロ終了・欠落 report を成功にしない。
- [ ] LocalBackend.submit / status / collect を thin Runner / CLI から使い、1 枚の実推論を成功させる。
- [ ] 証拠の Run ID / artifacts / 起動条件と 01A の能力制限を docs に残す。

### 01B tasks — after 01A acceptance

- [ ] cancel / timeout と process group の停止、子 worker の終了確認を実装。
- [ ] same LocalBackend instance の同時 submit は busy として拒否する簡単な guard を整備。
  GPU 全体の lease・他 process との調停には拡張しない。
- [ ] malformed job / unknown environment / corrupt result / checksum / path validation を補強。
- [ ] load / prediction / serialization timing と optional allocator memory の計測を整備。
- [ ] environment の実測 fingerprint、再作成手順、保存済み terminal result の再 collect を確認。
- [ ] CLI error / cancel の説明、未対応 ResourceSpec / backend operations を明示。
- [ ] unsupported → supported cancel の capability を更新し、01A の E2E regression を確認。

## Tests

以下は今後の実装時の検証計画であり、今回実行する tests ではない。

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

## Exit criteria

### 01A exit

Goal の 9 要素すべてを通る real inference が 1 回以上成功し、Run ID と raw depth / metadata /
WorkerResult / JobResult / stdout / stderr を保存・読み戻しできる。
モデル推論は worker 内の ModelAdapter、起動は LocalBackend の公開 interface を通る。
depth の意味、使用 model / checkpoint / environment / device が記録され、制御側に model / torch の
必須依存がない。環境定義と最小起動手順、未対応機能を記録する。
**GPU lease、cancel 完成、retry、restart recovery、concurrency は 01A exit の条件ではない。**

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
