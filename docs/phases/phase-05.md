# Phase 05 — Benchmark Mode

Status: 未着手・未承認。
管理: [PLANS.md](../../PLANS.md)。

## Goal

複数画像 × 複数モデル × 共通評価指標を、既存 single inference と同じ Runner / adapter / backend を
使って実行し、公平な条件・失敗・coverage を含む比較結果を保存する。

## Background

モデルごとに benchmark 専用 inference を書くと通常実行との乖離が生じる。
metric scale、relative scale、z depth、ray distance、resize / mask の違いを評価 protocol で明示する。

## Scope

BenchmarkSpec、dataset / GT reader、共通 Evaluator、Job 展開、子 run index、集計、MLflow 親 run、
UI の benchmark mode。最初の dataset / GT はこの phase で選定する。
GT がない場合は qualitative / timing 比較を行い、accuracy の成功を主張しない。

## Non-goals

新しいモデル実装系統、training、Slurm / distributed batch、自動 hyperparameter search、
大規模 dataset 管理基盤、全 camera / normal / pose / multi-view metric の網羅。

## Dependencies

Phase 03 の multi-model single inference、Phase 04 の Tracking、
[MDEOutput conventions](../model-adapter-spec.md)、[Job / Result](../execution-backend-spec.md)。
dataset の利用条件、GT units / invalid mask / image 対応、代表モデルの scale を確認する。

## Implementation tasks

- [ ] image / camera / GT / split / checksum を安定 ID で結ぶ dataset manifest を設計。
- [ ] BenchmarkSpec に models / variants、config matrix、seed、repetitions、resources、protocol を保存。
- [ ] 画像 × モデルの各 task を通常 JobSpec にし、既存 Runner.submit 経路へ渡す。
- [ ] child Run ID / attempt を保存し、完了済み子 task の再利用と failure policy を実装。
- [ ] GT grid / crop / resize interpolation / units / depth kind / scale alignment を protocol として固定。
- [ ] metric / aligned evaluation を別名・別条件で保存し、unsupported case を skip reason とする。
- [ ] per-image score、valid pixels、coverage、failure / skip count と集計を保存。
- [ ] Run Store の summary artifact と MLflow parent / child tags、UI の結果表を用意。
- [ ] metrics の定義、timing 条件、比較限界を docs に記載。

### Common evaluation protocol

有効 GT pixel 集合 V に対し、同じ単位・grid の positive prediction p と GT g を評価する。

| Metric | 定義 |
| --- | --- |
| AbsRel | `mean_V(abs(p - g) / g)` |
| RMSE | `sqrt(mean_V((p - g)^2))`、単位は評価した depth と同じ |
| delta_k | `mean_V(max(p/g, g/p) < 1.25^k)`、k = 1, 2, 3 |

V は GT-valid と dataset の固定 crop / camera policy から作り、model mask の任意除外で
モデルごとに分母を変えない。初期 strict protocol は V 内の予測が欠落・非有限・非正ならその sample の
accuracy 評価を不成立とし、prediction coverage と failure 理由を必ず報告する。
optional coverage-aware / conditional metrics は別 protocol として定義し、strict score と同列にしない。

metric evaluation は `alignment = none`。relative output は unaligned metric score と混ぜず、
例えば median scale alignment を選定した別 protocol で評価する。GT を使う alignment は研究上の
診断条件であり、metric inference 能力として宣伝しない。unknown scale は拒否 / skip。
non-pinhole / ray distance の GT 対応は rays 等で変換が検証できる場合だけ対象にする。

集計は per-image macro mean を基本とし、pixel-weighted mean を加える場合は別名を使う。
model 間で評価画像集合が異なる場合は shared successful subset と全体 failure / coverage を併記する。
accuracy、coverage、success rate を併せて比較し、失敗した画像を黙って落とさない。
timing は hardware、requested / actual resolution、dtype、cold / warm、load 除外の有無を揃えて記録する。

## Tests

- synthetic depth で perfect / known error の AbsRel / RMSE / delta_k を検証。
- zero / negative / NaN GT、invalid prediction、empty V、unit mismatch、unknown scale。
- relative scale alignment を有効にした場合だけ期待通りの評価になり、metric score と区別される。
- resize / crop / intrinsics 対応、model mask を悪用した score 改善が起きないこと。
- task 数が image × model × config に対応し、同じ single inference result を利用する。
- 一部 task failure / cancel / restart でも child ID・coverage・counts・summary が整合。
- GT 付き小規模 3 モデル実機比較、同 seed / conditions の再現性と数値許容範囲を記録。

## Exit criteria

少なくとも 2 画像 × 3 モデルの matrix を既存推論経路で実行し、per-task の結果・共通指標または
明示 skip 理由・failure count・summary・Tracking の parent / child 対応が得られる。
GT 付き smoke が実行できた場合に accuracy 経路の exit とし、GT 不在の場合は未達を明記する。
protocol / dataset revision / timing / scale / mask 条件が保存され、single inference に regression がない。

## Known risks

dataset / GT units 不明、relative と metric の混同、preprocessing grid のズレ、model mask による
選択バイアス、解像度差による速度比較の不公平、GPU OOM、失敗 task の分母からの消失。

## Decisions deferred to later phases

06: backend を変えた契約検証。07–08: cluster 上の matrix 実行。
full multi-view scene / normal / pose evaluation、追加 dataset、parallel throughput、統計解析は将来拡張。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| matrix は single inference の子 Job に展開 | 通常実行と benchmark のモデル経路を統一 | Job / artifact 数が増える | batching 最適化を protocol に追加 |
| strict / aligned evaluation を分ける | 尺度・valid coverage の異なる score を混ぜない | failure / skip 表示が増える | 別 dataset / camera protocol |
