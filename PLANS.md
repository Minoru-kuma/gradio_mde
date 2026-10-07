# Development plans

## Current authorization and status

- Current work: **Phase 00 完了・Phase 01 計画の文書更新、README の正式名称整理、commit / push**。
- Authorization: clean-start 決定、Phase 00 の状態、Phase 01 の計画と関連する仕様の段階分けを更新。
  README を日本語中心に整え、正式名称 MGE Experiment Platform と歴史的 repository 名を説明し、
  同じ作業単位で現在の branch へ commit / push する。production code の実装は含まない。
- Phase 00: **COMPLETE**。ユーザーの正式な clean-start 決定により source audit gate は充足。
- Phase 01: **PLANNED / IMPLEMENTATION_NOT_STARTED / IMPLEMENTATION_NOT_AUTHORIZED**。
  内部 milestone 01A / 01B の実装開始にはユーザーの指示が必要。
- Phase 02–08: **NOT_STARTED / NOT_AUTHORIZED**。
- Source policy: repository 内に再利用必須の既存 production implementation は存在しない。
  過去のモデルコードは Phase 01 / 03 の必要時に参考資料として確認する。
- 今回禁止: production code、Gradio app、モデル推論コード、Conda 環境作成、
  install、Slurm job、MLflow server、大規模 refactor、既存コード削除。

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
| [01](docs/phases/phase-01.md) | 00 完了、最初の model / variant 選定 | 01A の最小 E2E → 01B の基本的堅牢化 | PLANNED、実装未着手 |
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
| 01A — Minimum Local E2E | 1 model × 1 image × 1 独立 Conda 環境、subprocess、ModelAdapter、LocalBackend、MDEOutput、Run Directory、raw depth / metadata / result / logs | GPU lease、queue、cancel / timeout API の完成、性能計測、retry、active job recovery、複雑な concurrency | PLANNED、実装未承認 |
| 01B — Local robustness | 基本 cancel / timeout、子 process 終了、単一 worker の busy guard、artifact validation、基本計測と再現手順 | 高度な retry / reconciliation、application restart recovery、分散 lease / multi-GPU queue | PLANNED、実装未承認 |

まず 01A の実モデル推論成功を証拠付きで確定し、その前に 01B の要件を追加しない。
01A / 01B は既存 Phase 01 の内部 milestone であり、Phase 02–08 の番号と architecture は維持する。
Phase 01 全体の COMPLETE は 01A / 01B 双方の exit を満たした時点とし、01A 単独の完了を区別する。
01A 完了は 01B または Phase 02 の実装を自動承認しない。

当面の更新手順: clean-start / exit を記録 → Phase 01 の tasks / tests を milestone 別に整理 →
architecture / backend / environment / storage の実装段階を揃える → 文書を静的検証して報告。
rollback は更新前の文書内容への復元。コード・環境の変更は行わない。
リスク: 将来の完全な契約を 01A の必須実装と混同すると scope が再拡大する。
各仕様に milestone の適用範囲を記載し、共通 interface / Run layout を維持して段階的に検証する。

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
