# Phase 00 — Foundation / Architecture

Status: **文書整備済み / 既存実装調査保留**。今回唯一の承認 phase。
管理: [PLANS.md](../../PLANS.md)。

## Goal

現在の repository を把握し、既存資産を再利用する方針、共通契約、責務の分離、
段階的な開発計画を文書として整える。コード実装は始めない。

## Background

ユーザーは MoGe / UniK3D / DA3 の個別実行経験があるが、UI と Slurm の同時開発で複雑化した。
今回の可視 workspace には空の保護 directory 以外の既存コードがなく、Git metadata も読めない。
調査結果と要求に基づく暫定設計を分け、再利用確認を完了したと誤記しない。

## Scope

read-only repository 調査、公式 upstream / tool の一次資料確認、AGENTS / README / PLANS、
7 仕様文書、Phase 00–08 の 9 文書作成。調査の制約と再調査手順も記録する。

## Non-goals

production code、Gradio app、実推論コード、environment.yml の実体作成、Conda 環境作成、
package install、Slurm job 実装・投入、MLflow server、大規模 refactor、既存コード削除。
Phase 01 へ自動移行しない。

## Dependencies

ユーザーの今回の要件、workspace の可視性、[調査記録](../architecture.md#repository-investigation)。
Phase 00 全体の完了には既存コードの所在確認、または空 workspace を出発点にする確認が必要。
GPU / Conda / Slurm / MLflow の起動は文書作成の依存ではない。

## Implementation tasks

ここでいう implementation は **文書作成**を指す。

- [x] hidden files / instructions / Git / directory 全体を調査し、見えるものと未確認を区別。
- [x] Model / Environment / Backend / Tracking / UI の dependency rules と diagram を記載。
- [x] Adapter / capabilities / depth convention、Job / state / resources の契約を定義。
- [x] Conda / process / file protocol / Run ID / Tracking / Slurm の設計を記載。
- [x] 全 phase の scope / tests / exit / deferred decisions を記載。
- [ ] 既存コードが得られた場合の実行方法・依存・再利用箇所を調査して反映。
- [ ] Source audit 完了、または空 workspace で開始する確認を記録して全体 exit を判定。

## Tests

今回の検証は文書の静的確認に限る。

- 指定 19 ファイルの存在、local Markdown links / anchors、全 phase の必須 10 節。
- JobStatus / Run ID / attempt / output shape / responsibility が文書間で矛盾しないこと。
- 作成物が Markdown のみで、コード・環境・実データを追加していないこと。
- 未実装機能、unknown Slurm 値、未実行 tests を成功 / 対応済みと書いていないこと。

model / GPU / scheduler / MLflow integration tests は今回未実行であり、後続 phase の予定。

## Exit criteria

- [x] 文書が揃い、公開契約と phase の依存関係を追える。
- [x] no-code scope が保持され、未実装 / 未確認を区別している。
- [ ] 既存資産の具体的再利用判断、または空 workspace から始める確認が記録されている。
- [ ] 追加調査の結果が architecture / README / PLANS に反映されている。

文書の納品と Phase 00 全体の完了は別。上の保留項目を黙って完了にしない。

## Known risks

既存コードが不可視で、API の適合や compatibility を現時点で検証できない。
最新 upstream が過去の動作版と違う可能性、依存 pin の未確定、NFS / Slurm 条件未確認がある。

## Decisions deferred to later phases

Phase 01: 初期モデル・checkpoint・revision、package topology の具体化、環境 pin。
Phase 02: Gradio version / visualization library。Phase 03: 複数モデルの native convention 確認。
Phase 04: MLflow deployment。Phase 05: datasets / evaluation protocol。
Phase 07–08: 研究室の全 site 設定と実機検証。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| 文書を完成させ、source audit を保留として残す | 不可視のコードに適合済みと主張しない | Phase 00 全体は部分完了 | source 取得後の追加調査 |
| 19 文書に要求を分割する | 入口を簡潔にし契約の詳細を参照可能にする | 相互リンクの保守が必要 | interface 更新時の docs 同期 |
