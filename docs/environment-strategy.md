# Environment strategy

Status: Phase 01A で独立環境 `mde-moge`、定義、Resolver / Conda launcher を追加。
Conda subprocess の fake tests と MoGe CPU 実推論は確認済み。01Bで環境再作成・
process group 停止・計測・fingerprint・CPU regression を検証。GPU 互換性は未検証。
作成手順と固定版は [MoGe README](../models/moge/README.md)、実測状態は [PLANS](../PLANS.md)。

## Why Miniconda / Conda

ユーザーが通常 Miniconda を使うため、最初の環境構築と再現手順はその運用に合わせる。
設計上の概念は **Conda environment** であり、Miniconda の home path、installer 名、
shell activation を application の前提にしない。

| Logical role | 環境名の例 | 依存の範囲 |
| --- | --- | --- |
| application | `mde-ui` | Runner、Gradio（02）、MLflow client（04）、軽量 artifact reader |
| MoGe worker | `mde-moge` | 共通 worker / contracts、採用 MoGe revision、モデル依存 |
| UniK3D worker | `mde-unik3d` | 共通 worker / contracts、採用 UniK3D revision、モデル依存 |
| DA3 worker | `mde-da3` | 共通 worker / contracts、採用 DA3 revision、モデル依存 |

名前は例であり固定値ではない。各 environment は独立の Python、torch、CUDA userspace runtime、
native extension を持てる。application はモデル package / torch の必須依存にしない。
共通 worker distribution は UI / MLflow extras を要求せず、schema の同じ互換 major を使う。
01A では選定した 1 モデルの独立環境を用意する。control 側には既存の適切な Python を使え、
`mde-ui` 環境や Gradio / MLflow の導入を最初の E2E 成功条件にしない。

## Environment contracts

| Type / Field | 内容 |
| --- | --- |
| `EnvironmentSpec.environment_id` | logical ID。model ID / backend ID とは別 |
| `definition_ref`, `definition_digest` | model directory の environment.yml 等とその hash |
| `worker_protocol_version` | application と worker の契約互換性 |
| `model_revision_constraints` | adapter / upstream revision と環境の対応条件 |
| `runtime_requirements` | OS / arch、Python、必要 torch / CUDA build、必要 extension |
| `EnvironmentRef` | JobSpec の environment ID / definition digest。host prefix を入れない |
| `TargetEnvironmentProfile` | 実行先ごとの logical ID → name / prefix、launcher path、cache path の設定 |
| `ResolvedEnvironment` | target、launcher、env name / prefix、worker argv、実測 fingerprint |

概念 signature:

```text
EnvironmentResolver.resolve(environment_ref, target_profile) -> ResolvedEnvironment
EnvironmentLauncher.build_launch(resolved_environment, worker_request) -> WorkerLaunchSpec
```

Model は推奨 environment を宣言できるが、特定の backend やホストを含めない。
Runner は logical reference を JobSpec に保存し、backend の Worker Manager が target で解決する。
Local の prefix を Slurm node の prefix として再利用しない。未登録・未作成・revision 不一致なら
明示的な environment error とする。別環境や CPU へ黙って fallback しない。

01A の薄い実装は `EnvironmentProfile(environment_id, name | prefix)` と
`EnvironmentResolver.resolve(reference) -> EnvironmentProfile`、`CondaLauncher.argv(...)`。
name / prefix はどちらか一方。`base` と control と同じ Python prefix の worker を拒否する。
CLI の `--conda-env / --conda-prefix / --conda-exe`、または PATH / `MDE_CONDA_EXE` で解決し、
Miniconda の絶対 path は application code / 共有定義に保存しない。

## environment.yml and reproducibility

Phase 01 以降に各 `models/<model_name>/environment.yml` を整備する。含める項目は
Python、channels / priority 方針、Conda dependencies、pip dependencies、モデル revision。
torch build / CUDA runtime と extension の組合せは採用 upstream の要件と実機の互換性を確認して
pin する。過去の動作コード・環境情報は必要に応じて参考にし、取得を必須 gate にしない。

environment.yml は再作成の宣言であり、解決結果が永遠に同じである保証ではない。
検証した OS / arch ごとの resolved package list / lock、pip freeze、定義 hash、upstream commit、
checkpoint revision / SHA-256 を追加記録する。GPU model / driver も結果に残す。
01A は environment.yml、定義 hash、採用 revision、実行時の Python / torch / device 等の基本情報を
保存する。詳細な package fingerprint、計測、環境再作成の検証は 01B で整える。
個人の絶対 `prefix`、base 環境丸ごとの export、credentials を共有定義に入れない。
複数 platform 向けの from-history export だけで pip / 全推移依存の再現性を保証したとはしない。
[Conda の環境管理仕様](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)

provisioning は明示的な準備作業とし、Registry の一覧表示や推論 submit が自動 install しない。
checkpoint は設定した cache または local path から読む。研究室 node の外部通信は不明なので、
事前取得と offline loading ができる adapter を優先する。推論 Job の中で最新版を download しない。

## Conda and pip responsibilities

Conda は Python と環境基盤、採用した native library を管理する。Conda にない upstream package や
適切な torch wheel は、その環境の `python -m pip` により revision / version を固定して導入する。
同一 torch を Conda と pip で二重管理しない。どちらを使うかはモデル環境ごとに記録する。

基本順序は Conda dependencies → pip dependencies → 検証 → 解決結果保存。
pip 導入後の Conda 変更は環境を再作成して検証する方針とし、base や `pip --user` は使わない。
[Conda 公式の pip 混在方針](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html#using-pip-in-an-environment)

## CUDA runtime versus NVIDIA driver

| Layer | 管理責務 | 隔離範囲 |
| --- | --- | --- |
| NVIDIA kernel / user driver | workstation / cluster の管理者・OS | Conda では隔離できない共有 host layer |
| CUDA userspace runtime と関連 library | model environment と torch build の選定 | 多くは各環境の package / wheel で分離可能 |
| CUDA toolkit / nvcc | extension を build する場合の準備 | inference-only に必ず必要とは限らない |
| GPU device / memory | Backend の resource allocation、worker lifetime | Conda は GPU memory quota を保証しない |

環境を分けても host driver は共通であり、その driver が選択 runtime を支えられる必要がある。
`nvidia-smi` の CUDA 表示を、その環境に入った runtime / toolkit の版と同一視しない。
実際の torch / runtime / driver / extension 条件を preflight で記録し、互換性を実機で検証する。
driver の更新を application や推論 worker の仕事にしない。
[NVIDIA の互換性の説明](https://docs.nvidia.com/deploy/cuda-compatibility/latest/why-cuda-compatibility.html)

01A では公式 PyTorch 2.6.0+cu124 / torchvision 0.21.0+cu124 を導入し、明示 CPU で実推論した。
実測 torch.version.cuda=12.4、cuda.is_available()=false、GPU / driver=null。
torch.version.cuda と cuda.is_available() を別々に記録し、CUDA library が存在しても
GPU 実行の成功とは扱わない。採用ホストの minimum driver / 実機互換性は未検証。

## Subprocess workers

初期は 1 job ごとに selected environment の共通 worker を subprocess として起動する。
Conda launcher の候補は argv で表す `conda run --no-capture-output -n <name> python ...` または
prefix 指定。shell の `source activate` 文字列を Runner に埋め込まない。
`--no-capture-output` により process の stdout / stderr を共通 log collector に渡せる。
[Conda run 公式仕様](https://docs.conda.io/projects/conda/en/stable/commands/run.html)

WorkerLaunchSpec は executable / argv、cwd、許可した environment variables、log paths を持つ。
01A は選定環境で worker を起動して process exit / report を確認する薄い launcher とする。
01B では timeout と process group の終了制御を実装。cancel 時は wrapper だけでなく子 worker まで
終了を確認する。JSON Job / result、stdout / stderr の責務は共通 protocol に置く。
structured progress や多環境 provider の汎用化を 01A の前提にしない。

model worker は Gradio や MLflow を import せず、JSON / numeric artifacts を返す。
load time、CUDA-synchronized prediction time、serialization time、peak allocator memory の共通計測は
01B に整える。詳細 environment fingerprint に device 名、driver、torch / runtime、package list
digest を含める。未測定値を 01A の成功条件にしたり 0 で補完したりしない。
`CUDA_VISIBLE_DEVICES` は backend の割当てを尊重し、worker 内では見えている logical device を使う。

再現に必要な環境変数を明示し、credential 等を job / logs / fingerprint にコピーしない。
常駐 worker や shared memory IPC は後の最適化として扱う。

## Future micromamba support

launcher を provider として差し替え、logical EnvironmentRef / JobSpec / ModelAdapter は維持する。
micromamba の binary path、root prefix、env resolution を target profile に持たせる。
CLI flags が同一であるとは仮定せず、その provider の launch / cancel / log contract を別に検証する。
environment.yml の互換性と lock の利用可否も採用時に確認する。
container 等を追加する場合も Environment と ExecutionBackend を混ぜない。

## Decisions and deferred work

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| Miniconda を運用基準、Conda を設計概念とする | 現在の習慣に合わせつつ vendor path を避ける | Resolver / launcher が必要 | micromamba provider |
| model ごとの environment と subprocess | torch / runtime / extension の競合を減らす | disk と process startup の費用 | pool、環境定義共有の optional reuse |
| 定義と実測 fingerprint を両方保存 | 宣言だけでは実行環境を確定できない | provenance が増える | platform lock / offline mirror |
| target 側で environment 解決 | Local と Slurm の prefix 差を吸収する | site profile を用意する必要 | 複数 cluster / launcher |

Phase 01A: 初期モデルの pin、minimal worker packaging、launcher と 1 画像の実機推論。
Phase 01B: cancel / timeout、基本計測、詳細 fingerprint、環境再作成手順の検証。
Phase 03: 3 環境の独立性、capability / runtime matrix。Phase 07–08: module、node driver、offline cache、
共有 prefix と node-local prefix の選択。複数モデル / micromamba / cluster profile は未設定。

## Phase 01B measurement and fingerprint

共通 worker が execution.environment_fingerprint に Python version / implementation / executable /
prefix、OS / release / machine / processor、環境定義 digest、Python distribution の name/version list、
Conda package の name/version/build/subdir list とそれぞれの SHA-256 digest を保存する。
list をソートし canonical JSON（sort_keys、separator comma/colon）で hash を計算する。
fingerprint 全体（fingerprint_digest 自身を除く）も同じ方法で hash。credential / 任意環境変数 /
package source URL を採取しない。prefix は生成されたローカル結果にのみ残す。
execution の device / torch_version / torch_cuda_runtime / cuda_available / GPU名 / driver は
実際に import 済み framework から観測する。device=cpu で GPU名 / driver が null は未検証を意味する。

metrics は各 key に value / unit / scope を持つ。未計測は key を省略し0で埋めない。

| Key | 単位 / scope |
| --- | --- |
| load_seconds | s、adapter.load のcheckpoint IO / device transferを含む |
| predict_seconds | s、adapter.predict の前処理・推論・後処理・CPU出力を含む。CUDA時は前後 synchronize |
| serialization_seconds | s、depth validation / conversion / NPY atomic write / checksum。metadata / result JSONを除く |
| unload_seconds | s、adapter.unload のCPU wall clock。CUDA不調でもcleanupを試みる |
| metadata_serialization_seconds | s、metadata JSON write / checksum |
| worker_seconds | s、execute のimports / fingerprint / cleanup / metadata。result publication / Conda startupを除く |
| cuda_peak_allocated_bytes / cuda_peak_reserved_bytes | bytes、predict開始前resetからdepth保存までのtorch allocator peak。loaded modelを含みcontext / 他processを除く |

allocator はCUDAが実際に利用可能な要求deviceの場合のみ記録する。CPU smoke はallocator未計測、
CUDA API境界はmockで検証し、実GPUの計測は未検証。
計測は perf_counter、timeout はmonotonicを利用する。
実装根拠: [Python subprocess](https://docs.python.org/3/library/subprocess.html)、
[PyTorch CUDA memory API source](https://github.com/pytorch/pytorch/blob/v2.6.0/torch/cuda/memory.py)。

2026-10-12 は既存環境がなかったため environment.yml から .local/envs/mde-moge を再作成し、
固定 upstream --no-deps installとcheckpoint hash照合後にfake / MoGe CPU smokeが成功した。
環境の手順は [MoGe README](../models/moge/README.md)。推移依存の完全lock、
upstream全CLI / UIのrequirements充足、pip check成功は保証しない。

## Phase 02 application / offline conditions

02Bは独立application venv（Python 3.13.13 / Gradio 6.30.0）を利用する。
[ui.lock](../requirements/ui.lock)に推移依存まで固定し、model environmentへGradioを要求しない。
applicationにtorch / model packageは不要。wheelsはGit管理外wheelhouseに準備し、
別venvへの `--no-index` 再作成とpip checkを検証する。
frontendはGradio wheelのassetsをlocalhost配信し、analytics / share / 外部font / SSRを無効化する。
既存独立model環境 / source / fixed checkpointを事前準備し、CPUを明示選択する。
Python socketsとbrowser外向きHTTPを遮断したUI smokeの条件・限界と再作成手順は
[Gradio Inference](gradio-inference.md)、実測は [02B](phases/phase-02/phase-02b.md) を参照。
02Cのnumeric viewer / 3D rendererは2026-10-27に全Exit達成でCOMPLETE。既存UI lock内のNumPy / Pillowと同梱Three.js r180を使用。
[Results Viewer](results-viewer.md)を参照。GPU / 学会実演は未検証。

## Phase 02A validation environment

既存独立named mde-mogeを再利用し、Python 3.11.14 / torch 2.6.0+cu124 / pinned MoGe・utils3d /
checkpoint SHA-256を照合してCPUで検証した。依存追加・環境変更は行っていない。
geometry用のNumPyはworker環境の既存依存、controlのgeometry readerはstdlibのみ。
02A serialization_secondsは要求されたnumeric artifactsの変換・NPY保存・geometry値検証・checksumを
含むscopeを各metricに明記する。01A形式の保存metricのscopeを変更せず読み戻す。
CPUなのでCUDA allocator値は省略、GPU / driver互換は未検証。
