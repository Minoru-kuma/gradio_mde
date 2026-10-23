# Execution backend specification

Status: Phase 01A の LocalBackend / 共通型を実装し、Conda worker の fake tests と MoGe CPU E2E を確認済み。
01B の cancel / timeout / busy guard / validation / terminal 再 collect を実装・検証済み。
Phase 01 COMPLETE。Slurm / Mock backend と以下の高度な契約は将来設計。
関連: [Architecture](architecture.md)、[Environment](environment-strategy.md)、
[Run Directory](run-directory-spec.md)、[Slurm](slurm-integration.md)。

## Orthogonal model / environment / backend

Job は `model_ref`、`environment_ref`、`backend_id` を独立に持つ。
ModelAdapter に scheduler command、Backend にモデル loading API を書かない。

| Model | EnvironmentRef の例 | Backend の選択 |
| --- | --- | --- |
| MoGe | `mde-moge` の定義参照 | Local / 将来 Slurm |
| UniK3D | `mde-unik3d` の定義参照 | Local / 将来 Slurm |
| DA3 | `mde-da3` の定義参照 | Local / 将来 Slurm |

名前は logical ID の例。環境 prefix は実行 target で解決する。同一の model contract を使い、
`MoGeSlurmRunner` のような model × backend 専用クラスを作らない。
backend を変えた比較実行は provenance を分けるため新しい Run ID とする。

## ExecutionBackend interface

submit / status / collect の signature は最小実装と共通。Local の CancelReceipt は01Bで実装済み。
以下は全体の共通契約。01A の最小実装と 01B / 06 の追加範囲を
[Phase 01](phases/phase-01.md) と本書の LocalBackend 節で区別する。

```text
submit(spec: JobSpec) -> JobHandle
status(handle: JobHandle) -> JobStatusSnapshot
cancel(handle: JobHandle, reason: str | None) -> CancelReceipt
collect(handle: JobHandle) -> JobResult
```

| Operation | 契約 |
| --- | --- |
| `submit` | 非同期に受理する。戻り値は推論完了ではない。schema / reference / resource を検証し handle を保存する |
| `status` | 非破壊の観測。backend raw state と正規化状態、観測時刻を返す。通信障害で FAILED を捏造しない |
| `cancel` | 対応 backend は冪等な終了要求を返す。受理と実際の CANCELLED を分け、process / scheduler 確認まで terminal としない。未対応は明示エラー |
| `collect` | terminal Job の共通結果と artifact refs を返す。再呼び出し可能で artifact を移動・削除しない |

非 terminal の collect は `ResultNotReady`、不明 handle は `UnknownJob`、schema 不一致は
`UnsupportedSchema` 等の明示エラーにする。poll timeout は job 実行 timeout と区別する。
FAILED / CANCELLED でも診断情報を collect できる。collect はモデルを再実行しない。
01A 時点は `supports_cancel=false` / walltime 未対応だった。01B では
`supports_cancel=true`、Local cancel は bounded な同期停止と確認を行い CancelReceipt を返す。
receipt は accepted / requested_at / status / already_terminal。terminal に対する再 cancel は
accepted=false / already_terminal=true で元の状態を維持する。停止確認失敗は例外となり、
RUNNING / busy guard を維持する。別 process の active handle 復旧・停止は未対応。

## Common types

### JobSpec

`schema_version = "1.0"` を初期案とする JSON document。作成後は immutable。

| Field | 定義 |
| --- | --- |
| `run_id`, `attempt_id`, `attempt_number` | logical experiment と実行 attempt。初回は `attempt-0001` |
| `idempotency_key`, `request_digest` | submission 同一性と immutable inference request の hash |
| `created_at`, `parent_run_id` | UTC timestamp、任意 benchmark 親 run |
| `model_ref` | model / variant ID、adapter / upstream revision、checkpoint revision / digest |
| `environment_ref` | logical environment ID、定義 digest、protocol version |
| `backend_id`, `backend_profile` | 実行先と site profile の識別子。研究室値は未設定 |
| `inputs` | view ID、Run 相対 path、image hash、任意 camera reference |
| `inference` | device / dtype、seed、resolution policy、model parameters、requested outputs |
| `resources` | ResourceSpec |
| `storage` | Run relative location / Store reference。実機 absolute root は対象側で解決 |
| `evaluation` | optional 共通 EvaluationSpec 参照。推論 worker は GT 評価を担当しない |
| `provenance` | git commit / dirty / source identity、requester、protocol revision |

checkpoint の未知 revision は unknown と明示する。初期実機 acceptance では検証した版を確定する。
JobSpec に shell command、torch tensor、MLflow client、host 固有 prefix を入れない。
backend 専用 partition / account 等は backend profile に置き、model metadata から切り離す。

### ResourceSpec

| Field | 意味 / 単位 |
| --- | --- |
| `cpu_count` | 正整数、初期は単一 worker task の CPU 数 |
| `gpu_count` | 非負整数、Phase 01 は 0 または 1。分散推論は対象外 |
| `gpu_type` | optional GPU の要求クラス。site mapping が必要 |
| `host_memory_mib` | optional host memory 要求、MiB |
| `gpu_memory_mib` | optional GPU memory 要求 / admission hint、MiB。強制 quota ではない |
| `walltime_seconds` | optional execution timeout、秒。queue wait と分ける |

未指定と 0 を区別し、不可な組合せは submit 前に拒否する。要求値と実割当てを別記録する。
Local で scheduler 相当の memory enforcement を保証できない項目は best-effort と明示する。
GPU type を Slurm GRES にどう対応させるかは site profile を確認するまで決めない。

### JobHandle

`schema_version`、`run_id`、`attempt_id`、`backend_id`、opaque `backend_job_id`、
`submission_time`、`idempotency_key`、Run relative location、backend profile ID を持つ。
Local PID だけを永続 identity にしない。process start identity / manager instance を別 metadata に
持たせ、PID 再利用を区別する。Slurm job ID は backend_job_id として保存する。
保存形式は読み戻せる JSON とし、MLflow run ID を job handle に代用しない。
handle の保存は 01A から行うが、application 再起動後の active job の監視・停止・復旧を
01A の保証に含めない。高度な recovery / reconciliation は Phase 06 以降に検証する。

### JobStatus and JobStatusSnapshot

共通 lifecycle states（01A で queue 管理や cancel 対応を全て実装することは意味しない）:

| Status | 意味 |
| --- | --- |
| `QUEUED` | 受理済み、まだ worker を実行していない |
| `RUNNING` | worker / scheduler が実行中。結果 publication 中も含める |
| `COMPLETED` | execution 成功と result / 必須 artifact の契約検証が完了 |
| `FAILED` | 実行失敗、timeout、OOM、成功後の result 欠落 / 破損等が確定 |
| `CANCELLED` | cancellation による停止を backend が確認 |

Snapshot は `status`、`last_known_status`、`backend_state`、`observed_at`、`sequence`、
`started_at`、`finished_at`、`cancel_requested`、`reason`、diagnostics を持つ。
観測不能時は補助状態 `UNKNOWN` と last_known を返す。UNKNOWN は実行状態の逆戻りではない。
query 失敗と worker 失敗、job 不在と未登録 handle を区別する。
01A の Local snapshot は status / backend_state / observed_at / sequence / timestamps /
cancel_requested / reason の subset。01B は CANCELLED 遷移を追加。UNKNOWN 観測は未実装。

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    QUEUED --> FAILED
    QUEUED --> CANCELLED
    RUNNING --> COMPLETED
    RUNNING --> FAILED
    RUNNING --> CANCELLED
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

terminal state は immutable。poll の遅い古い観測で戻さない。retry は terminal → QUEUED の
状態変更ではなく、新しい attempt と handle で表す。
collect 時点の artifact 検証に通るまでは COMPLETED としない。確定後に artifact が外部変更された場合は
run 結果を改変せず `ArtifactIntegrityError` として報告する。

### JobResult

`schema_version`、run / attempt / backend IDs、terminal status、timestamps、
`outputs: list[SerializedMDEOutput]`、artifact refs、metrics、actual execution metadata、
warnings、error を持つ。成功時は少なくとも 1 view の depth が必要。

worker の `output/<attempt_id>/result.json` は WorkerResult report であり、execution 全体の
確定結果と区別する。Backend は worker report と process / scheduler 情報を照合して JobResult を作り、
`attempts/<attempt_id>/job-result.json` に保存する。worker が起動しなかった失敗でも backend が
outputs 空の診断結果を生成できる。FAILED の途中 artifact は partial と示し成功出力と混ぜない。01B は成功参照を空にし、
途中fileとpartial logsをRun内に残す。partial artifact参照の一覧化は未実装。

error は code、stage（preflight / load / predict / serialize / backend / collect）、message、
retryability、exit code / signal、traceback artifact ref。native exception class をプロセス越しに渡さない。
metrics は units と measurement scope を伴い、未計測を 0 として補完しない。

## LocalBackend

### Phase 01A — Minimum Local E2E（当時の範囲）

1. 単一 Job を検証・受理・記録し、worker を起動して JobHandle を返す。
   QUEUED は起動までの状態として使えるが、待ち行列や GPU lease を作らない。
2. 薄い Worker Manager / launcher が target profile から 1 つの selected environment を解決する。
3. 共通 worker を argv により起動し、stdout / stderr を attempt 別に保存する。
4. status で process を観測し、exit code と WorkerResult / 必須 depth・metadata の基本検証で
   terminal を確定する。collect は保存済み JobResult / artifacts を返す。

利用者が 1 job を起動する運用を前提とし、他 process との GPU 調停や並列 submit の保証はしない。
cancel / execution timeout は未対応として明示する。自動 retry は 0、active job の restart recovery
は対象外。Runner / Gradio が直接 subprocess を呼ぶ経路は作らず、backend 境界は最初から保つ。
実装は same backend instance の handle / process をメモリに保持する。status / collect は終了後に
JSON / hash / NPY header を stdlib で検証する。terminal collect の繰返しは再推論しない。
cpu_count は要求記録のみで thread quota を強制せず、host / GPU memory quota と GPU type mapping は
未対応。walltime は明示 UnsupportedOperation。GPU count は 0–1 のみ。

### Phase 01B — Local robustness

01B は実装・検証済み。POSIX の `start_new_session=True` で Conda wrapper と子 worker を
独立 group に起動する。SIGTERM → grace（既定1秒）→ 必要なら SIGKILL、wrapper の wait と
group の停止確認後に terminal とする。Linux は /proc で group の実行中 process を確認し、
zombie は実行終了済みとして親 / init の回収に委ねる。tests は worker / 子 PID の消失も確認する。
自ら group を離脱する daemon は対象外。Windows は起動拒否、Linux 以外の POSIX は未実機検証。

`ResourceSpec.walltime_seconds` は正整数。Conda startup を含む launch 後の経過時間を
monotonic clock と job ごとの timer で制限し、polling がなくても停止する。queue はない。
timeout は FAILED / TIMEOUT、ユーザー cancel は CANCELLED。process が既に終了した場合は
先に report を検証し、その結果を優先する。timer / status / cancel / collect は instance lock で直列化。

実行中の異なる submit は BackendBusy。既に受理した同一 spec は同じ handle、異なる spec で
同じ key は identity conflict。終了後は次 job を受理する。instance / host 間の GPU 調停はしない。
unknown resources、GPU type、host / GPU memory quota は UnsupportedOperation、GPU count は0–1。
cpu_count は正整数の要求記録のみで quota enforcement はない。

Job snapshots / input hash、環境定義 hash、WorkerResult の型・ID・timestamp・error・metric、
必須 depth / metadata の参照・checksum・size・NPY・単位・camera・JSON整合を検証する。
不正な終了前 result は FAILED / INVALID_RESULT（非ゼロ exit は WORKER_FAILED）。
確定後の欠落 / 破損は ArtifactIntegrityError、terminal state は書き換えない。

`LocalBackend(run_root, manager=None).collect(saved_handle)` は保存済み terminal 結果を検証して読む。
WorkerManager / Conda は不要で、worker を起動せず file を移動・更新しない。
保存済み handle と job/result identity を照合する。terminal report がなければ active recovery として
UnsupportedOperation、不明 handle は UnknownJob。同一 instance / 新 instance とも再 collect を検証済み。
基本 timing / allocator / fingerprint は [Environment](environment-strategy.md) に定義する。

高度な retry / submission reconciliation / application restart recovery / concurrency 制御は
Phase 06 以降。GPU lease はその必要性と scope を改めて判断する。
OS 強制 quota・複数 host 調停・worker pool は Phase 01 の保証範囲外。

## Future SlurmBackend

same JobSpec → site resource mapping → generic worker job → same JobResult とする。
環境は計算 target で解決し、共有 Store を介して inputs / report / logs を交換する。
sbatch / squeue / sacct / scancel の違いはこの backend と command adapter に閉じ込める。
研究室固有実装は [Phase 07](phases/phase-07.md) で設定確認後に行う。

## MockSlurmBackend / fake backend

01A の tests は fake adapter と実 LocalBackend / Conda subprocess を利用する。
fake backend はまだ実装しない。Phase 06 の MockSlurmBackend は、
clock / executor / command adapter を注入して以下をローカルで再現する。

- QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED。
- queue cancel、running cancel、completion と cancel の競合。
- 一時 UNKNOWN、遅延 status、結果 publication 遅延、破損 / 欠落。
- submit の応答喪失、同じ key の再 submit、重複 collect、process / client 再起動。
- NFS を模した遅延・partial read・stale observation。

実時間の長い sleep や本物の sbatch を必要としない。Mock 成功は実際の Slurm / NFS の保証ではない。

## Failure, cancellation and retry contracts

以下は段階的に検証する契約。01A は基本失敗判定と保存・同一実行中の submission 同一性を扱い、
cancel / timeout は 01B、応答喪失・再起動をまたぐ照合や高度な retry は 06 以降とする。
新 attempt を作れる schema を先に定義しても、retry controller を 01A に実装する必要はない。

- idempotency は run / attempt / request digest で判断する。同じ key の受理済み submit は同じ
  handle を返す。異なる spec に同じ key を使う場合は conflict。
- submit が受理されたか不明なときは `SubmissionUncertain` と記録する。既存 job を照合する前に
  retry して二重実行しない。backend が無条件 exactly-once を保証するとはしない。
- cancel 受理後も worker が終了するまで RUNNING / QUEUED と cancel_requested を保持する。
  成功が先に確定した Job は COMPLETED のまま。cancel 失敗を CANCELLED に見せない。
- execution timeout は FAILED とし、code を TIMEOUT とする。ユーザー cancel は CANCELLED。
- 初期の自動 retry 回数は **0**。schema / dependency / checkpoint / OOM の失敗を盲目的に retry しない。
- 指示された retry は同じ inference request の新 attempt を作り、旧 artifact / handle を保持する。
  model / parameters / environment / backend / resources を変える場合は別 Run ID と `retry_of_run_id`。
- preemption / node failure に限定した bounded retry は Phase 07–08 で policy を確認して追加する。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| すべての Local 実行も backend interface 経由 | 実行場所の後付け refactor を避ける | 最初から handle / poll が必要 | Slurm / 別 scheduler plugin |
| backend 状態と worker report の両方を確認 | exit 0 / scheduler COMPLETED だけでは成果物を保証できない | publication grace と validation が必要 | integrity / remote Store |
| UNKNOWN は観測の補助状態 | 通信障害で実行結果を誤判定しない | UI に未確定表示が必要 | reconciliation / controller recovery |
| retry を別 attempt とする | 失敗の証拠と測定 provenance を保持 | Run Directory が増える | bounded transient retry / scheduler requeue |

## Phase 02 Local UI integration — 02B implementation

[02B](phases/phase-02/phase-02b.md) でGradio操作を実装。運用backendはLocalのみ。
UIは既存Runner submit / status / collect / cancelを使い、timeoutはresources経由。
全sessionで単一Runner / LocalBackend instanceを共有し、busy submitを明示拒否する。
LocalBackendのinstance guardはglobal GPU lease / multi-process調停ではない。
Gradio全eventにqueue=False / concurrency_limit=None / trigger_mode=onceを設定。
UI serviceのnonblocking admissionで1件だけ受理、busyは即拒否。background observerがRunnerの
submit / status / cancel / collectを呼び、Gradio pollはメモリ上snapshotだけを読む。
stop / terminal artifact validation中もcallbackは待機しない。詳細は [UI契約](gradio-inference.md)。

現行JobStatusSnapshotは数値progressを持たない。statusとindeterminate進捗を表示し、
未提供%を捏造しない。数値progress拡張を採るなら共通optional契約として別途仕様更新する。
CUDA要求のCPU fallbackなし、cancel完了race / timeoutの現行terminal semanticsを維持。
UI計画作成時のJobSpecは[depth]のみだった。02Aの実装では末尾のrequest extensionを追加する。
確定JobResultはimmutable、derived geometry・管理sidecarの追加で書き換えない。
保存terminal Run読込は再推論 / active recoveryではない。active削除を拒否する管理責務は
[Run Management Service](run-management-spec.md) に分離する。

## Phase 02A implemented request extension

02AではRunner.submitにoptional `requested_outputs=("depth",)`、CLIに`--outputs depth points ...`を追加。
depth必須、points / normals / intrinsics / maskから一意の集合を選び、共通順序でJobSpecへ保存する。
explicit optional要求はvariant capability supported / conditionalのみ受理し、runtime不足はworker failure。
requested outputsは条件digestにも含む（既定depth-onlyのdigest入力は従来の形を維持）。
JobSpecの旧[depth]制限を拡張し、single-view / single-attempt / cpu・cuda:0 / float32の制限は維持。
新profile・geometry保存後のcollectは同じBackend境界で行い、cancel / timeout / busyを変更しない。
terminal JobResultはimmutable。02BのUI / sessionは上記の実装境界。数値progress契約は追加せずunavailableとする。
