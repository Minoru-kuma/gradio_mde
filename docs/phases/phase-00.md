# Phase 00 — Foundation / Architecture

Status: **COMPLETE**。2026-10-07、ユーザーの clean-start 決定と exit 再評価により完了。
Phase 01 の計画更新は承認済み、production code の実装は未承認。
管理: [PLANS.md](../../PLANS.md)。

## Goal

現在の repository を把握し、clean-start の出発点、過去資産の参考方針、共通契約、責務の分離、
段階的な開発計画を文書として整える。コード実装は始めない。

## Background

ユーザーは MoGe / UniK3D / DA3 の個別実行経験があるが、UI と Slurm の同時開発で複雑化した。
初回の可視 workspace には空の保護 directory 以外の既存コードがなく、Git metadata も読めなかった。
ユーザーがこの repository を新規実験基盤の clean-start と正式に確認した。
過去コードは存在するが、この repository の production implementation として取り込まれていない。
そのため mandatory reuse の調査を完了条件にせず、必要な参考確認を Phase 01 / 03 に移す。

## Scope

read-only repository 調査、公式 upstream / tool の一次資料確認、AGENTS / README / PLANS、
7 仕様文書、Phase 00–08 の 9 文書作成。調査の制約と再調査手順も記録する。

## Non-goals

production code、Gradio app、実推論コード、environment.yml の実体作成、Conda 環境作成、
package install、Slurm job 実装・投入、MLflow server、大規模 refactor、既存コード削除。
Phase 01 へ自動移行しない。

## Dependencies

ユーザーの今回の要件、workspace の可視性、[調査記録](../architecture.md#repository-investigation)。
source audit gate は「repository 内に再利用必須の実装なし、clean-start を正式採用」という
ユーザーの確認で充足した。過去のモデルコードの取得・詳細調査は Phase 00 の残条件ではない。
GPU / Conda / Slurm / MLflow の起動は文書作成の依存ではない。

## Implementation tasks

ここでいう implementation は **文書作成**を指す。

- [x] hidden files / instructions / Git / directory 全体を調査し、見えるものと未確認を区別。
- [x] Model / Environment / Backend / Tracking / UI の dependency rules と diagram を記載。
- [x] Adapter / capabilities / depth convention、Job / state / resources の契約を定義。
- [x] Conda / process / file protocol / Run ID / Tracking / Slurm の設計を記載。
- [x] 全 phase の scope / tests / exit / deferred decisions を記載。
- [x] ユーザーの clean-start 決定と repository 内の mandatory reuse 不在を記録。
- [x] 過去コードの確認を Phase 01 / 03 の必要時の参考作業として位置付け。
- [x] source audit gate と exit を再評価し、Phase 00 を COMPLETE とする。

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
- [x] repository 内に再利用必須の production implementation がなく、clean-start で始める決定が記録されている。
- [x] 決定と Phase 00 の完了状態が architecture / README / PLANS / 作業ルールに反映されている。
- [x] Phase 01 の計画が最小 E2E と後段の robustness に分かれ、コード実装は未開始。

再評価: 文書の存在・静的検証、責務 / 契約の整合、no-code scope、ユーザーの出発点確認を根拠に
全条件を充足。過去の実装を実見した、または新基盤でモデルが動作済みとは判断していない。

## Known risks

新基盤の実モデル API・依存 pin・checkpoint・GPU はまだ未検証。
最新 upstream と過去の動作版の差、NFS / Slurm 条件未確認は後続 phase のリスクであり、
Phase 00 の source audit blocker ではない。

## Decisions deferred to later phases

Phase 01A: 初期モデル・checkpoint・revision、最小 worker / adapter / backend、環境 pin。
Phase 01B: 基本 cancel / timeout・計測・validation。Phase 06: 高度な復旧 / concurrency。
Phase 02: Gradio version / visualization library。Phase 03: 複数モデルの native convention 確認。
Phase 04: MLflow deployment。Phase 05: datasets / evaluation protocol。
Phase 07–08: 研究室の全 site 設定と実機検証。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| repository を正式な clean-start とし source audit gate を完了 | ユーザーが mandatory reuse 不在を確認 | legacy 実装・CLI の移行保証を初期条件にしない | 過去コードは Phase 01 / 03 の必要時に参考確認 |
| 19 文書に要求を分割する | 入口を簡潔にし契約の詳細を参照可能にする | 相互リンクの保守が必要 | interface 更新時の docs 同期 |
