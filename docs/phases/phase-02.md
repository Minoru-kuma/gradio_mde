# Phase 02 — Gradio Single Model UI

Status: 未着手・未承認。
管理: [PLANS.md](../../PLANS.md)。

## Goal

Phase 01 の single inference を Gradio から操作し、状態・depth・計測・保存結果を確認できるようにする。

## Background

推論経路が成立してから UI を載せる。過去の複雑化を避け、UI callback は Runner の公開 service を
利用する。モデルの native API、Conda、subprocess、Slurm command を UI に持ち込まない。

## Scope

1 モデルの選択、image upload、inference request、async status / cancel、depth visualization、
runtime / GPU memory の表示、raw artifact download。backend selector は catalog から表示するが、
この段階の運用対象は Local のみ。optional points / normals は存在する標準 artifact に限り共通表示。

## Non-goals

複数モデルの統合、MLflow UI、Benchmark mode、Slurm option 入力、model-specific viewer、
モデル推論の reimplementation。未準備 backend を選べるものとして表示しない。

## Dependencies

Phase 01 の Local E2E / collect と [Architecture](../architecture.md) の公開 boundary。
Gradio version と共通 artifact viewer の採用はこの phase で pin し、モデルの環境から分離する。

## Implementation tasks

- [ ] minimal app を application environment に置き、Registry metadata から controls を生成。
- [ ] model / variant、input、requested resources を Runner request に変換。
- [ ] JobHandle / Run ID を session state として扱い、複数 session を混線させない。
- [ ] blocking prediction callback を作らず、poll / progress / cancel を公開 service 経由で扱う。
- [ ] depth の raw 値と表示 normalization を分離し、単位 / scale / invalid mask を表示。
- [ ] capability と actual artifacts に基づき optional panels を表示 / 非表示。
- [ ] missing metrics を unavailable と表示し、selected attempt の download を提供。
- [ ] UI が閉じた後の結果を Run ID から読めるようにし、CLI 経路を維持。

## Tests

- fake Runner の queued / running / failed / cancelled / completed を UI で区別できる。
- 画像なし / 壊れた画像 / unknown parameter の入力が実行前に検証される。
- unknown metric と optional output absence が UI error にならない。
- concurrent sessions で他 session の image / handle / result を使わない。
- cancel 後に完了通知が来る競合、画面再接続、download path の Run 内検証。
- 実モデル 1 枚の UI smoke と同じ request の CLI 結果が同じ共通契約になること。

## Exit criteria

UI から 1 モデルを LocalBackend 経由で実行・cancel・表示・download できる。
UI / Runner に model name 分岐・torch import・Conda / scheduler 起動がない。
CLI と保存結果の互換性、複数 session、failure 表示が確認される。起動手順と docs を更新する。

## Known risks

Gradio event queue の挙動、長い処理での UI blocking、session 混線、大きな point cloud の描画容量、
表示 normalization を raw depth と誤認するリスク。

## Decisions deferred to later phases

03: multi-model capability matrix とパラメータ UI 拡張。04: tracking 状態表示。
05: benchmark 操作。06: mock backend selection。07–08: actual Slurm selection。
viewer の高度な解析機能と認証 / 多ユーザー公開は別 scope。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| UI は公開 Runner service を操作 | UI と inference implementation を分離 | 非同期状態の表示が必要 | backend / model の追加 |
| generic capability-driven panels | モデル追加時の callback 分岐を避ける | 未知 extras の専用表示は後回し | 独立 artifact renderer |
