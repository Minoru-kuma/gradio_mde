# MLflow Tracking design

Status: Phase 04 で導入予定。現在 MLflow client、server、Tracking 実装はない。
model environment の必須依存にはしない。
関連: [Architecture](architecture.md)、[Run Directory](run-directory-spec.md)、
[Phase 04](phases/phase-04.md)、[Benchmark](phases/phase-05.md)。

## Responsibility and run identity

worker は標準 report / artifacts を Run Store に保存する。ExperimentRunner が JobResult を受け取り、
TrackingSink を通して MLflow client に渡す。モデル package は MLflow を呼ばない。
Phase 01–03 は NoOpTracking、Phase 04 以降も Tracking を optional にできる。

概念 interface は `start_attempt(context)`、`log_result(job_result)`、
`log_evaluation(evaluation_result)`、`finish_attempt(status)`、`flush_pending()`。
Runner はこの契約に依存し、UI callback / Backend に MLflow-specific 呼び出しを置かない。

**MLflow inference run は application の各 attempt に対応**する。
application Run ID、attempt ID と MLflow が採番する run ID は異なる。
`attempts/<attempt_id>/tracking.json` に対応を保存し、MLflow では tags で application ID を検索できる。
retry は新しい MLflow run となり、過去の失敗・metrics を上書きしない。

Phase 05 の benchmark は summary 用 MLflow 親 run を作り、通常 inference の attempt runs を
子として関連付ける。`mlflow.parentRunId` は MLflow 親 ID、`mde.parent_run_id` は application の
benchmark 親 ID とし、両者を混同しない。

MLflow の Params / Metrics / Artifacts 等の記録機能は
[公式 Tracking documentation](https://mlflow.org/docs/latest/ml/tracking/) を参考にする。
以下はこのプロジェクトが追加する記録規約であり、MLflow の自動収集機能としては扱わない。

## Params

Params はその attempt の実験条件として固定する。要求値と actual value は異なる key。
flatten 済みの短い scalar を記録し、大きな構造は JSON artifact に保存する。

| Key の例 | 記録対象 |
| --- | --- |
| `model.name`, `model.variant`, `model.version` | model / checkpoint variant / generation |
| `model.adapter_revision`, `model.upstream_revision` | 実装 identity |
| `model.checkpoint_revision`, `model.checkpoint_sha256` | weights identity、unknown は明示 |
| `model.param.<name>` | model parameters。native names は manifest に定義 |
| `input.width`, `input.height`, `input.views` | 入力 size / view 数 |
| `resolution.policy`, `resolution.requested` | requested resize / resolution 条件 |
| `dtype.requested`, `device.requested` | JobSpec の要求 |
| `dtype.actual`, `device.actual` | worker が確認した条件、取得後に一度記録 |
| `environment.id`, `environment.definition_sha256` | logical environment と宣言の版 |
| `environment.fingerprint_sha256` | 実測 package / runtime fingerprint |
| `execution.backend`, `execution.profile` | Local / Slurm 等と target profile |
| `resources.cpu_count`, `resources.gpu_count`, `resources.walltime_seconds` | 要求 resources |
| `seed` | seed、determinism policy は別 artifact / tag |
| `git.commit` | application commit、取得不可なら unknown |
| `evaluation.protocol_id`, `evaluation.protocol_revision` | Phase 05 の条件 |

model parameters は同じ name でも意味を manifest に残す。
DA3 等の multi-view における view ごとの processed / output size は JSON artifact へ保存し、
単一 size として誤記録しない。request と fingerprint が違う場合は warning と双方を保持する。

## Metrics

| Key | 単位 / 定義 |
| --- | --- |
| `timing.queue_seconds` | backend が観測した queue wait |
| `timing.load_seconds` | model loading、weights 読み込みを含む |
| `timing.predict_seconds` | 共通 prediction boundary。GPU は前後同期して測る |
| `timing.serialize_seconds` | report / artifacts serialization |
| `timing.worker_total_seconds` | worker 起動後の全処理 |
| `timing.end_to_end_seconds` | Runner の submit から collect、queue / process startup を含む |
| `memory.peak_cuda_allocated_bytes` | selected worker device の torch allocator peak |
| `memory.peak_cuda_reserved_bytes` | selected worker device の allocator reserved peak |
| `evaluation.abs_rel`, `evaluation.rmse`, `evaluation.delta_1/2/3` | 共通評価、尺度・単位・protocol を添付 |
| `evaluation.valid_pixels`, `evaluation.prediction_coverage` | 有効 GT と予測の割合 |
| `benchmark.success_count`, `benchmark.failed_count`, `benchmark.skipped_count` | 親 benchmark 集計 |

「inference time」は predict_seconds を指すと明示し、load / queue 込みの時間と混ぜない。
初期は cold worker であり warm throughput を測ったとはしない。後の warmup / repetition policy は
metric scope / protocol を別にする。peak は測定前の reset と CUDA 同期条件を metadata に記録する。
初期の prediction peak は load 後、predict 直前に同期・peak reset し、predict 後に同期して読む。
常駐 weights の allocation を含み、load 中の peak を測った値とは別にする。
allocator memory は NVIDIA driver / 他 process を含む総 GPU 使用量とは異なる。
NVML 等による device total measurement は optional・別 key とする。CPU 実行の CUDA memory は null /
unavailable とし、0 byte として比較しない。

未測定の metric、GT がない画像、尺度不一致の評価は記録しない。reason を JSON / tag に残す。
benchmark の image 平均と pixel-weighted 平均を別名で記録し、失敗画像を黙って除外しない。

## Artifacts

| Artifact group | 内容 / provenance |
| --- | --- |
| `request/` | immutable JobSpec、input image、camera input、input hashes |
| `outputs/` | raw depth、depth visualization、points / PLY、raw / visual normals、mask、confidence、rays、pose |
| `provenance/` | ModelInfo / manifest snapshot、environment definition / package fingerprint、runtime metadata |
| `results/` | WorkerResult、確定 JobResult、backend handle / terminal snapshot |
| `logs/` | stdout / stderr / diagnostics |
| `evaluation/` | protocol、per-image / per-model scores、coverage / skip / aggregation metadata |

Run Store の content を保持して必要な artifact を MLflow に upload する。
PLY 等の大容量出力は policy で optional にできる。upload を省いた場合は local Store reference と
checksum を manifest に残すが、その local path が remote MLflow UI から download 可能とは書かない。
秘匿すべき environment variables / credential は記録しない。

## Tags

| Key | 用途 |
| --- | --- |
| `mde.run_id`, `mde.attempt_id` | 全システム共通の追跡キー |
| `mde.parent_run_id`, `mde.retry_of_run_id` | benchmark / 条件変更 retry の関連 |
| `mde.schema_version`, `mde.job_status` | protocol / 正規化結果 |
| `mde.capabilities`, `mde.depth_scale_type`, `mde.depth_kind` | 出力の意味 |
| `mde.git_dirty`, `mde.source_digest` | commit 以外の再現性情報 |
| `mde.tracking_state`, `mde.evaluation_skip_reason` | 記録・評価状態 |
| `slurm.job_id`, `slurm.partition`, `slurm.compute_node` | 将来 worker / backend が実測した値 |
| `hardware.gpu_name`, `hardware.driver_version`, `runtime.cuda_version` | 実際の execution metadata |

Slurm の requested partition と actual partition を必要なら分ける。
job ID が確定していない、node が割り当てられていない場合は省略 / unknown を使う。
予定値を実測値として記録しない。GPU UUID 等の必要性は運用方針に合わせて判断する。

## Tracking lifecycle and failure isolation

1. Runner が local Run / attempt / JobSpec を先に永続化する。
2. Tracking 有効時は attempt の MLflow run を作り、対応を保存する。
3. JobHandle と params を記録する。worker / scheduler との通信は Backend が行う。
4. collect 後に metric / artifacts / final tags を記録し終了する。
5. successful execution は FINISHED、failure は FAILED、user cancellation は KILLED に対応させる
   方針。API 対応と細かい挙動は採用 MLflow version で検証する。

Tracking server / artifact upload が落ちても inference JobResult を FAILED に書き換えない。
`tracking_state = pending / syncing / complete / error` を inference status と別管理し、
UI は「推論成功、記録未完了」等を表示する。
local tracking record に未送信 items と upload identity を残し、Runner 側から再送できるようにする。

create-run の応答喪失では run / attempt tags と保存 mapping を照合してから再作成する。
metric の再送は同じ key / step / timestamp / value を使い、既送信記録を確認するが、
MLflow 自体に汎用 exactly-once upload があるとは仮定しない。曖昧な重複は diagnostic に残す。
Tracker の冪等性は再推論の防止と MLflow run の重複抑制を対象に契約テストする。

## Deployment choices deferred to Phase 04

MLflow version、tracking URI、experiment naming、backend store、artifact URI、認証、
local-only / server deployment、retention、network reachability は未選定。
設定 / 環境変数で指定し、server 起動は Phase 04 の明示 scope に含まれた場合のみ行う。
研究室の compute node から接続する構成を前提にしない。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| Runner の TrackingSink から記録 | 各 model 環境への SDK / network 依存を避ける | local record と upload の二段管理 | tracker の差替え / offline sync |
| MLflow run は attempt 単位 | retry の状態・metrics を上書きしない | logical run は tag で group 化する | benchmark 親 run |
| Run Store を先に確定する | Tracking outage で成果を失わない | artifact が複製される | upload policy / remote artifact Store |
| metric scope と評価 protocol を記録 | 不公平な latency / accuracy 比較を避ける | provenance が増える | warm worker、別 dataset / metric |
