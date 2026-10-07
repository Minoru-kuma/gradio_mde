# Phase 01 — Single Model + Local Execution + Miniconda

Status: 未着手・未承認。開始にはユーザーの Phase 01 指示が必要。
管理: [PLANS.md](../../PLANS.md)。

## Goal

まず 1 モデルだけを独立 Conda environment の subprocess worker と LocalBackend 経由で
end-to-end 実行し、共通 raw depth / result / logs を保存できる状態にする。

## Background

UI / cluster より前に推論、環境分離、結果契約を確認する。
候補はユーザーの動作経験がある MoGe。ただし具体的な世代・weights・既存スクリプトは未確認で、
latest を自動採用しない。既存動作版が得られたらその最小経路を再利用する。

## Scope

minimal contracts / RunStore / metadata Registry / ModelAdapter、Environment Resolver + Conda launcher、
Worker Manager、LocalBackend、CLI または Python service entrypoint、最初の environment.yml。
初期は 1 image / 1 model / 1 worker process / 0–1 GPU、Tracking は NoOp。

## Non-goals

Gradio、2 モデル目、MLflow server、Benchmark、Slurm、distributed inference、worker pool。
将来機能を先に実装せず、Local 直結の使い捨て runner も作らない。

## Dependencies

Phase 00 の調査 gate、初期モデル / variant の選定、利用可能な Miniconda / Conda と GPU / driver。
[Adapter](../model-adapter-spec.md)、[Environment](../environment-strategy.md)、
[Backend](../execution-backend-spec.md)、[Run Directory](../run-directory-spec.md) の契約。
ユーザーが CPU を選ぶ場合は対応 variant の確認が必要で、GPU 不可時に黙って CPU fallback しない。

## Implementation tasks

- [ ] plan に再利用対象、初期 model / checkpoint / upstream revision を記録。
- [ ] worker / contracts を UI / MLflow / upstream 依存なしで導入できる最小 packaging を選定。
- [ ] 共通型と metadata-only discovery を実装し、1 adapter を薄く接続。
- [ ] environment.yml と実機で検証した package / runtime fingerprint を用意。
- [ ] target profile、Conda launcher、generic worker と finally cleanup を実装。
- [ ] LocalBackend の submit / status / cancel / collect、GPU lease、timeout を実装。
- [ ] Runner がすべての実行を backend 経由にし、input / result / logs を Store に保存。
- [ ] CLI / service でモデル選択、input、resources、Run Root を指定できるようにする。
- [ ] documented cold-run timing と allocator memory を共通 worker で収集。
- [ ] 既存 CLI がある場合は互換の起動方法・保存形式を保護して migration を記載。

## Tests

- GPU なし: fake adapter を別 subprocess で走らせ、Job → serialized depth → collect を検証。
- metadata listing が model / torch import を必要としないこと、optional artifact の欠如が正常であること。
- malformed job、未知 environment、非ゼロ終了、load / predict error、missing depth / checksum mismatch。
- queued / running cancel、timeout、process group と resource lease の解放、重複 collect / submit。
- Run Root の明示設定 / MDE_RUN_ROOT、relative path、application 再起動後の保存結果読み込み。
- 実機: 選定モデル 1 枚の inference と再作成環境での smoke。depth shape / units / frame を確認し、
  upstream の動作 baseline がある場合は同じ input / parameters と許容誤差で比較。

実機結果と fake tests を分け、GPU 未利用時に実モデル成功を主張しない。

## Exit criteria

最初のモデルを指定 Conda 環境から LocalBackend 経由で実行し、raw depth、report、handle、logs を
新規 Run に保存・再 collect できる。必須契約の失敗が明示され、cancel が子 process を残さない。
application に torch / model import が不要で、environment.yml と実測 provenance が記録される。
関連 docs と起動手順を更新する。ここで Phase 02 を自動開始しない。

## Known risks

既存 baseline 不在、checkpoint download / cache、driver / torch build 不整合、extension build、
subprocess 起動 overhead、GPU OOM、Conda wrapper の子 process 終了、Git commit unknown。

## Decisions deferred to later phases

02: UI / viewer。03: 2・3 モデル目、camera / optional output の実機 matrix。
04: Tracking。05: dataset evaluation。06: mock scheduler / robust reconciliation。
07: target site。warm worker / distributed inference は別の将来計画。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| adapter / backend / worker を 1 モデルから使う | 後の責務分離 refactor を避ける | 最小 E2E に薄い共通層が必要 | multi-model / Slurm |
| cold process を基準にする | 環境隔離と cleanup を最初に検証する | load overhead が毎回発生 | 契約を維持した warm pool |
