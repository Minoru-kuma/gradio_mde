# Phase 04 — MLflow Tracking

Status: 未着手・未承認。
管理: [PLANS.md](../../PLANS.md)。

## Goal

共通 Runner から MLflow に実験条件・実測値・artifacts を記録し、model worker と Tracking を分離する。

## Background

複数モデルの共通結果が成立した後に Tracking を追加する。推論の成否と記録の成否を混ぜない。
application Run ID と MLflow run ID を対応付け、retry の失敗証拠を残す。

## Scope

TrackingSink、NoOp / MLflow 実装、Params / Metrics / Artifacts / Tags、attempt ごとの run、
local pending record、再送、tracking 状態表示。MLflow server は採用する運用方式と開始指示の範囲に
含まれる場合だけ、この phase で準備する。

## Non-goals

model environment への MLflow 強制依存、worker から server 通信、モデル登録 / serving、
production authentication platform、Benchmark、Slurm job の実装。

## Dependencies

Phase 03 の common JobResult / metrics / provenance、[MLflow design](../mlflow-design.md)、
[Run Directory](../run-directory-spec.md)。採用 MLflow version、tracking / artifact URI と到達性を
この phase の計画時に決める。

## Implementation tasks

- [ ] TrackingSink と NoOp の差し替えを Runner の構成で行う。
- [ ] MLflow client を application environment の optional dependency として pin。
- [ ] Run / attempt / MLflow ID mapping を永続化し、Params と actual metadata を分ける。
- [ ] common metrics と units / measurement scope、入力 / raw / visual artifacts を記録。
- [ ] terminal status の mapping と tracking_state の独立管理を実装。
- [ ] pending upload journal、run identity reconciliation、結果を再推論しない再送を実装。
- [ ] large artifact policy、credential exclusion、unknown / unavailable の扱いを文書化。
- [ ] Tracking 無効・失敗でも既存 CLI / UI / Local execution が成立することを維持。

## Tests

- fake tracker で Runner が 3 モデルに同じ logging contract を使う。
- 独立 worker から MLflow import / server 到達が不要であること。
- 採用 MLflow version の isolated store で Params / Metrics / Artifacts / Tags と ID mapping を確認。
- create-run 応答喪失、metric / artifact upload 途中失敗、replay、already-finished run を扱う。
- 推論成功 + Tracking error、推論 FAILED / CANCELLED のそれぞれを正しく記録。
- optional artifact / CPU memory metric の absence、actual resolution / scale の保存。
- 再送がモデル再実行・既存 MLflow run の不要な作り直しを起こさない。

## Exit criteria

3 モデルの少なくとも各 1 run に必要な条件・計測・artifact・追跡 tags が記録される。
保存 mapping から Run Store と MLflow を往復でき、Tracking outage 後に結果を失わず再送できる。
models / workers の必須依存に MLflow がなく、無効化時も Local E2E が使える。
運用手順、version / URI、未検証な deployment を docs に反映する。

## Known risks

API / backend store の version 差、server 不通、大容量 upload、params の再記録、
ambiguous create acknowledgement、metric history の重複、artifact path のremote 到達性。

## Decisions deferred to later phases

05: benchmark 親 run / child mapping と評価集計。07–08: Slurm metadata の実値記録。
本番 authentication / shared service / retention の自動化、model registry は別計画。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| Tracking を optional application dependency とする | モデル環境と実行経路を切り離す | result の後段 upload が必要 | offline / 別 tracker |
| Tracking error を execution status から分離 | 記録障害で推論を失敗扱いしない | UI に二つの状態が必要 | queued background sync |
