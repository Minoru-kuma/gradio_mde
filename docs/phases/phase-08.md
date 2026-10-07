# Phase 08 — Real Slurm Integration Test

Status: 未着手・未承認。研究室 Slurm / NFS 実環境で検証する。
管理: [PLANS.md](../../PLANS.md)。

## Goal

実際の cluster / GPU / NFS 上で既存の ModelAdapter と SlurmBackend を組み合わせ、
成功・failure・cancel・artifact・Tracking の共通契約が成立することを確認する。

## Background

Mock と prototype だけでは installed Slurm policy、accounting delay、NFS visibility、
Conda / module / GPU driver の実挙動を保証できない。現地で Run ID ごとの証拠を残す。

## Scope

許可された小規模 real inference、Local と Slurm の共通 request 比較、shared Store、lifecycle、
stdout / stderr、node / GPU metadata、cancel / timeout / failure diagnostics、MLflow への回収記録。
最初の 1 モデルを必須 smoke とし、最終 matrix は3 モデルの採用 variant へ広げる。

## Non-goals

cluster 管理設定の変更、driver 更新、他ユーザーの job 操作、破壊的な node failure 誘発、
大規模 load test、未承認 partition の利用、native requeue の未確認運用、production SLA。

## Dependencies

Phase 07 の site profile / prototype、cluster 利用許可、node target environments / weights、
read/write 可能な shared Run Root、test用小画像と resource budget。
MLflow は submission 側から利用可能、または local pending / 後日同期を検証する条件が必要。

## Implementation tasks

- [ ] 実機 test plan、対象 variant、resource / time 上限、failure injection の安全な範囲を記録。
- [ ] 最小 job を実行し Run / attempt / Slurm ID、node、environment、GPU を照合。
- [ ] same inference request を Local / Slurm の別 Run ID で実行し artifact / provenance を比較。
- [ ] 3 モデルの representative variants と small image matrix を同じ backend で検証。
- [ ] NFS publication / checksum / mount mapping / logs / collect の実挙動を確認。
- [ ] queued / running cancel、walltime timeout、worker exception、missing / corrupt report を限定的に確認。
- [ ] application 再接続・reconciliation・再 collect・manual retry の証拠を保存。
- [ ] worker から MLflow を呼ばず submission 側でログし、outage / pending replay を確認。
- [ ] failure matrix、known limitations、site profile revision、README / phase 状態を更新。

## Tests

- 実際の QUEUED / RUNNING / terminal と normalized JobStatus、job / step accounting の対応。
- 同じ Run relative artifact が submission / compute から読み書きでき、half-written report を読まない。
- 各 model の raw depth / optional outputs / units / frame / checksum と保存 logs。
- Local / Slurm の numerical result を同じ preprocessing / checkpoint / dtype で許容誤差比較。
  GPU 世代差による完全一致は前提にしない。runtime は hardware 差を記録して解釈する。
- user cancel と timeout が区別され、停止後に resource が解放され collect できる。
- bounded accounting / NFS delay、schema / environment / worker failure、manual retry の旧成果保持。
- Slurm job ID / partition / node / GPU と MLflow tags、application Run ID の照合。
- node failure / preemption / native requeue は利用可能な証拠・管理者許可がある場合のみ実施し、
  実施できないものを検証済みにしない。

## Exit criteria

3 モデルの採用 variant が実 Slurm で共通契約を満たす。Run Store の入力・raw output・logs を
再 collect でき、MLflow に記録または障害後に同期できる。
cancel / timeout / representative worker failure、ID mapping、environment / driver、NFS の
publication が現地証拠で確認される。未試験の cluster 条件は運用制限として列挙する。
Local 経路に regression がなく、docs が実設定・対応範囲と一致する。

## Known risks

GPU 待ち時間、node heterogeneity、NFS cache / quota、accounting retention、許可されない failure tests、
数値非決定性、外部通信制約、cluster 設定の将来変更。

## Decisions deferred to later phases

Phase 08 以後の scope は別途ユーザー指示で決める。
複数 cluster、job arrays、multi-node、warm workers、native requeue / transient retry、
大規模 benchmark、production 運用を自動開始しない。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| 実機証拠と未試験条件を併記 | Mock / fixture から実環境成功を推測しない | exit と運用制限を分けて記録する | site regression checklist |
| Local / Slurm は同じ契約・別 Run ID | backend provenance と数値比較を追跡する | 比較する Run が複数になる | cross-backend benchmark |
