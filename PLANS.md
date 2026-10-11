# Development plans

## Current authorization and status

- Current work: **Phase 01A — COMPLETE、成果物・docs・Git の最終確認**（2026-10-11）。
- Authorization: 01A の production code、1モデル環境の作成・依存導入、fake tests、実モデル推論、
  docs 更新。exit 達成時のまとまった commit / push。01B 以降は未承認。
- 再開範囲: 残り依存 download / install、native API import、明示した CPU による実モデル smoke、
  成果物検証、docs / Git hygiene、exit 達成時の commit / push。01B 以降へは進まない。
- Phase 00: **COMPLETE**。ユーザーの正式な clean-start 決定により source audit gate は充足。
- Phase 01: **IN_PROGRESS**。01A: **COMPLETE**。01B: **NOT_STARTED / NOT_AUTHORIZED**。
- Phase 02–08: **NOT_STARTED / NOT_AUTHORIZED**。
- Source policy: repository 内に再利用必須の既存 production implementation は存在しない。
  過去のモデルコードは Phase 01 / 03 の必要時に参考資料として確認する。
- 今回禁止: 01B の cancel / timeout 完成、lease / queue / recovery / retry、Gradio、Slurm、
  MLflow、Benchmark、他モデル、warm worker / distributed inference。

## Phase management

状態は `NOT_STARTED → PLANNED → IN_PROGRESS → REVIEW_READY → COMPLETE` を基本とし、
外部条件の不足は `BLOCKED` として理由を残す。`PLANNED` は計画文書の準備状態であり、
production code の実装承認・開始を意味しない。実験 JobStatus とは別の管理状態である。

各 phase 開始前に、最新のユーザー指示がその phase の実作業を承認していることを確認する。
必要な通常作業のたびに承認を取り直す必要はないが、未指示の phase に進んではならない。
README / phase 文書のロードマップは将来計画であり実装の指示ではない。

各 phase 文書の Goal、Background、Scope、Non-goals、Dependencies、Implementation tasks、
Tests、Exit criteria、Known risks、Decisions deferred to later phases を維持する。

| Phase | 前提 | 主要 exit | 現状 |
| --- | --- | --- | --- |
| [00](docs/phases/phase-00.md) | clean-start の正式確認 | 調査記録・共通契約・段階計画の整合 | COMPLETE |
| [01](docs/phases/phase-01.md) | 00 完了、最初の model / variant 選定 | 01A の最小 E2E → 01B の基本的堅牢化 | IN_PROGRESS、01A のみ承認 |
| [02](docs/phases/phase-02.md) | 01 | 1 モデルの Gradio、状態表示と保存結果 | 未着手 |
| [03](docs/phases/phase-03.md) | 01・02 | 3 モデルが同じ契約を満たす | 未着手 |
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
| 01B — Local robustness | 基本 cancel / timeout、子 process 終了、単一 worker の busy guard、artifact validation、基本計測と再現手順 | 高度な retry / reconciliation、application restart recovery、分散 lease / multi-GPU queue | NOT_STARTED、未承認 |

まず 01A の実モデル推論成功を証拠付きで確定し、その前に 01B の要件を追加しない。
01A / 01B は既存 Phase 01 の内部 milestone であり、Phase 02–08 の番号と architecture は維持する。
Phase 01 全体の COMPLETE は 01A / 01B 双方の exit を満たした時点とし、01A 単独の完了を区別する。
01A 完了は 01B または Phase 02 の実装を自動承認しない。

現在の作業手順と rollback は下記 01A implementation plan を使う。
2026-10-07 の文書のみの計画更新は完了済みで、今回の実装承認とは区別する。
リスク: 将来の完全な契約を 01A の必須実装と混同すると scope が再拡大する。
各仕様に milestone の適用範囲を記載し、共通 interface / Run layout を維持して段階的に検証する。

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
