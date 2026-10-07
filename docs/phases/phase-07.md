# Phase 07 — SlurmBackend Prototype

Status: 未着手・未承認。**研究室環境を確認してから実施する。**
管理: [PLANS.md](../../PLANS.md)。

## Goal

確認済みの site profile に基づき、共通 Job / Result と shared Run Directory を使う
single-node / single-task の SlurmBackend prototype を構築する。

## Background

Slurm の version、partition、GRES、NFS、Conda、module、network、driver が現状不明。
自宅から直接使えると仮定せず、研究室で証拠を集めた後に scheduler-specific adapter を作る。

## Scope

site investigation、command adapter、ResourceSpec mapping、generic bootstrap、submit / status /
cancel / collect、job ID / logs / node metadata。最初は小さい単一 GPU または許可された CPU smoke。
共有 filesystem を確認できた場合の shared-directory transport に限定する。

## Non-goals

unknown partition / GRES / NFS path の推測、model-specific sbatch script、remote access の自動構築、
multi-node / job arrays / production 運用、環境調査前の実モデル大量実行、Phase 08 の実機保証。

## Dependencies

Phase 06、研究室に行けることと利用許可、
[Slurm 確認表](../slurm-integration.md#required-site-investigation) の記録。
installed commands、共有 root の両 host からの read/write、compute target の environment / weights / driver。
shared transport 前提が崩れた場合は計画を更新して別 scope を判断する。

## Implementation tasks

- [ ] version / partition / account / GPU / sbatch / NFS / Conda / module / network / driver を調査記録。
- [ ] submission host 上の実行方式と compute target profile を選定。
- [ ] ResourceSpec から verified Slurm options への mapping を実装。
- [ ] sbatch の ID parsing と submission uncertainty / reconciliation を実装。
- [ ] squeue / sacct の current / terminal 観測と raw state 保存を実装。
- [ ] scancel request と実際の停止確認、result publication grace を実装。
- [ ] JobSpec を読む generic bootstrap、target environment resolution、logs / report を接続。
- [ ] environment / weights を事前準備し、node に外部ネットワークを必須としない。
- [ ] policy に沿った最小 smoke を可能な範囲で実施し、未実施の項目を明記。
- [ ] site profile・起動手順・failure codes・retry policy を docs に残す。

## Tests

- 現地で採取した CLI outputs の fixture による parser / state / ID tests。
- resource mapping の単位・unsupported request・limits、fake command failure。
- synthetic Job を使う generic worker / environment / shared-root / log publication smoke。
- permission error、checkpoint / environment 不在、squeue 消失 / sacct 遅延、cancel races。
- Local / Mock の common contract suite regression。
- 実機 smoke は許可・環境条件が揃った場合に実施し、fake 成功と分けて記録。

## Exit criteria

site の unknown values が必要範囲で確認され、model name 分岐なしの prototype と共通 tests が揃う。
job ID / Run ID / attempt を保存でき、generic worker の command / input / output / logs が定義済み。
実機 smoke を行っていない場合は「prototype contract 検証済み、実機未検証」と明記し、
研究室対応済みと宣言しない。実モデル・NFS 障害等の確認は Phase 08 の gate に残す。

## Known risks

site access 時間の制約、old Slurm formats、accounting disabled / delayed、mount prefix 差、
module bootstrap、CUDA / driver 差、requeue policy、NFS visibility、CLI outcome 不明。

## Decisions deferred to later phases

08: real model × Slurm、NFS の同時性・failure、Tracking 通信、cancel / resource cleanup の実機保証。
job arrays、multi-node、remote submit、native requeue / automatic retry は確認済み scope に応じ将来判断。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| 現地確認を implementation の前提にする | unknown infrastructure をコードで固定しない | 自宅だけで完了できない | verified site plugin |
| generic worker を shared Run から起動 | model と scheduler を直交させる | shared filesystem の到達が必要 | staging transport / 別 cluster |
