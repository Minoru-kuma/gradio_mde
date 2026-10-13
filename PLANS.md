# Development plans

## Current authorization and status

- Current work: **Phase 02A — COMPLETE、docs / Git整理**。
- Authorization: 02A実装・検証・関連docs更新、必須Exit達成後のcommit / mainへの通常push。
- Phase 00 / 01 / 01A / 01B: **COMPLETE**。
- Phase 02: **IN_PROGRESS**。02A: **COMPLETE**（実CPU native Pointsを含むExit達成）。
  02B〜02D / 03–08はNOT_STARTED / 未承認。
- Start evidence: latest origin/main / HEAD `7ed21e36e428d07b11d4048b2e9c771e4f6fc6cc`、main、clean。
- Source policy: latest mainの実装・契約を基準とする。旧depth-only成果物を破壊しない。
- 禁止: 02B以降、Gradio、viewer / mesh、Run管理service、他モデル、Tracking / Benchmark / Slurm。

## Phase 02A implementation plan

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
文書作成と実装の開始・完了は別。02Aは実装Exit達成、02B以降は将来の受入条件。

## Phase management

状態は `NOT_STARTED → PLANNED → IN_PROGRESS → REVIEW_READY → COMPLETE` を基本とし、
外部条件の不足は `BLOCKED` として理由を残す。`PLANNED` は計画文書の準備状態であり、
production code の実装承認・開始を意味しない。実験 JobStatus とは別の管理状態である。
文書準備だけでは実装を開始しない。現在は02AのExit達成でCOMPLETE、02B以降は未承認。

各 phase 開始前に、最新のユーザー指示がその phase の実作業を承認していることを確認する。
必要な通常作業のたびに承認を取り直す必要はないが、未指示の phase に進んではならない。
README / phase 文書のロードマップは将来計画であり実装の指示ではない。

各 phase 文書の Goal、Background、Scope、Non-goals、Dependencies、Implementation tasks、
Tests、Exit criteria、Known risks、Decisions deferred to later phases を維持する。

| Phase | 前提 | 主要 exit | 現状 |
| --- | --- | --- | --- |
| [00](docs/phases/phase-00.md) | clean-start の正式確認 | 調査記録・共通契約・段階計画の整合 | COMPLETE |
| [01](docs/phases/phase-01.md) | 00 完了、最初の model / variant 選定 | 01A の最小 E2E → 01B の基本的堅牢化 | COMPLETE、01A / 01B exit 達成 |
| [02](docs/phases/phase-02.md) | 01 | 02A geometry → 02B Inference → 02C 3D Results → 02D Run管理 | IN_PROGRESS（02A COMPLETE、02B以降未承認） |
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
