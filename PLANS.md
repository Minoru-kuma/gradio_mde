# Development plans

## Current authorization and status

- Active phase: **Phase 00 — Foundation / Architecture**
- Authorization: 既存リポジトリの読み取り調査、指定ドキュメント作成、
  ユーザー指定 GitHub リポジトリへの文書の commit / push。
- Status: **DOCS_READY / SOURCE_AUDIT_PENDING**。Phase 00 全体の exit は未達。
- Phase 01–08: **NOT_STARTED / NOT_AUTHORIZED**。
- Limitation: 可視 workspace にコード・依存定義・有効な Git metadata がなく、
  既存実装の再利用判断はできない。ユーザーへ所在を問い合わせ済み、回答は未確認。
- 今回禁止: production code、Gradio app、モデル推論コード、Conda 環境作成、
  install、Slurm job、MLflow server、大規模 refactor、既存コード削除。

## Phase management

状態は `NOT_STARTED → PLANNED → IN_PROGRESS → REVIEW_READY → COMPLETE` を基本とし、
外部条件の不足は `BLOCKED` として理由を残す。上記の `DOCS_READY / SOURCE_AUDIT_PENDING`
は現在の Phase 00 の部分完了を表す。実験 JobStatus とは別の管理状態である。

各 phase 開始前に、最新のユーザー指示がその phase の実作業を承認していることを確認する。
必要な通常作業のたびに承認を取り直す必要はないが、未指示の phase に進んではならない。
README / phase 文書のロードマップは将来計画であり実装の指示ではない。

各 phase 文書の Goal、Background、Scope、Non-goals、Dependencies、Implementation tasks、
Tests、Exit criteria、Known risks、Decisions deferred to later phases を維持する。

| Phase | 前提 | 主要 exit | 現状 |
| --- | --- | --- | --- |
| [00](docs/phases/phase-00.md) | コードの可視性または空 workspace の確認 | 調査記録・共通契約・段階計画の整合 | 文書整備済み、追加調査保留 |
| [01](docs/phases/phase-01.md) | 00 完了、最初の model / variant 選定 | 1 モデルを独立 Conda + LocalBackend 経由で実行 | 未着手 |
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
  19 Markdown files / 9 phase documents、89 local links / anchors の静的検証を実施。
  model / GPU / Slurm / MLflow の実行テストは今回未実行。
- [ ] 既存コードを読める場所の回答、または空 workspace を出発点にする確認。
- [ ] ソースが得られた場合は実行方法・依存関係・再利用箇所・互換性を追加調査。
- [ ] 上記を反映して Phase 00 の exit を判定する。Phase 01 へは進まない。

## Key decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| 現状を「可視コードなし・追加調査待ち」と記録 | 既存コードを無視した完成宣言を避ける | 再利用判断・初期版 pin は保留 | ソース取得後に調査節と plan を更新 |
| Phase 01 から adapter / backend / worker 契約を使う | 後から Local と UI を切り離す refactor を避ける | 最初の 1 モデルにも薄い共通層が必要 | Phase 03 / 06 で実証を広げる |
| 共通 Run ID と append-only attempt | 再試行と複数 tracking ID を混同しない | 1 run 内に attempt 記録が増える | Slurm requeue / tracking 再送 / benchmark 子 run |

## GitHub snapshot — 2026-10-07

- Target: `Minoru-kuma/gradio_mde`、remote `git@github.com:Minoru-kuma/gradio_mde.git`。
- Scope: 現段階の 19 Markdown 文書を初期コミットとして `main` に登録する。
- Evidence: GitHub metadata と remote refs を確認し、登録前の repository は空。
- Method: workspace の `.git` は読み取り専用のため、一時 checkout で文書だけを commit / push。
  local source 文書と checkout の内容が一致することを確認する。
- Validation: phase 必須節・相対リンク、commit の file set、push 後の remote commit を確認する。
- Phase boundary: Phase 00 の文書 snapshot 保存であり、Phase 01 の開始ではない。
  過去のモデル実装の所在・再利用調査は引き続き保留。
