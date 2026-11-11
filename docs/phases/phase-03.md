# Phase 03 — Model Plugin Architecture / Multi-model Support

Status: **実装中 / 03.1受入完了、03.2以降未着手（2026-11-11実装承認）**。Exit未達、COMPLETEではない。
`codex/phase-03-implementation`で03.1〜03.6を順番に実施し、受入成功ごとにcommit / 通常push。
PR作成・main統合・Phase 04以降には進まない。
履歴: 2026-11-09は調査・計画・設計のみ承認、production実装・環境構築は未承認だった。
管理: [PLANS.md](../../PLANS.md)。段階計画と実装記録は
[Phase 03 planning](../../PLANS.md#phase-03-investigation-and-staged-design--2026-11-09)と
[implementation record](../../PLANS.md#phase-03-implementation-record--2026-11-11)を参照。

## Goal

MoGe、UniK3D、DA3 を同じ ModelAdapter / MDEOutput / Job contracts に載せ、
UI / Runner / backend のモデル固有分岐なしで Local 実行できるようにする。

## Background

plugin boundary は Phase 01 で始めている。この phase で実際の複数モデルの環境・出力差に対して
契約を検証する。MoGe の世代別 scale、UniK3D の rays / non-pinhole、DA3 の view / pose を尊重する。

## Scope

3 モデルの代表 variant とそれぞれの environment.yml、metadata discovery、optional outputs、
capability-driven UI、native output conversion、共通 contract tests。
全モデルの single-view E2E を必須とし、multi-view は宣言・view identity・serialization の契約確認まで
必須、実モデルの multi-view UI / benchmark は対応可能な variant に限った追加 scope とする。

## Non-goals

全 upstream variant の網羅、モデル training、checkpoint 自動探索、UI 内への native API 埋め込み、
Slurm、Tracking、完全な multi-view geometry evaluation、model × backend runner の量産。

## Dependencies

Phase 01 / 02、[Model adapter spec](../model-adapter-spec.md)、
[Environment strategy](../environment-strategy.md)、検証する upstream revisions / weights。
clean-start を前提とし、過去の個別実行コードは必要に応じて参考資料として確認する。
repository の既存 production implementation としての取り込みや、取得を必須 gate にしない。

## Implementation tasks

- [ ] `models/moge/`、`models/unik3d/`、`models/da3/` の必要 adapter / manifest / environment を整える。
- [ ] upstream / checkpoint / license / scale / shape / camera conventions を variant ごとに記録。
- [ ] 3 environment の解決と独立 worker 実行を確認し、依存を application に混ぜない。
- [ ] normalized K、w2c / c2w、native dtype / channel layout 等の変換を adapter で行う。
- [ ] rays、non-pinhole camera、optional normal / confidence / pose、extras の不足を正しく扱う。
- [ ] manifest parameter schema から controls を生成し、worker runtime capability と照合。
- [ ] representative single-view を 3 モデルで実行し raw artifacts / metrics を揃える。
- [ ] 新しい fake plugin directory の追加だけで Registry に発見されることを確認。
- [ ] shared interface を変える必要がある場合は docs / schema reader / compatibility を同時更新。

## Tests

- UI 環境で全 manifest が読め、未 install の model も metadata discovery は可能。
- selected worker だけがその upstream を import し、3 環境が互いの torch version を必要としない。
- 必須 depth と optional field の shape / dtype / units / frame を各実モデルで検証。
- pinhole / non-pinhole、range と z、relative と metric の synthetic conversion / rejection tests。
- view ID の入力対応、未知 extras の round-trip、unknown major / duplicate plugin ID の拒否。
- 同じ model の UI / CLI / backend を差し替えた fake execution が同じ公開契約を使う。
- 既存 baseline がある場合は同条件の numeric regression。未対応 variant は tested と書かない。

## Exit criteria

3 モデルの少なくとも各 1 variant が Local single-view E2E を満たす。
各 model directory の追加で動作し、core / UI / backend の model name 分岐が不要。
capability matrix に tested / conditional / untested を記録し、optional 出力と raw artifacts が扱える。
3 環境の再現条件、版、幾何 convention、互換性を docs に反映する。

## Known risks

upstream 更新、checkpoint による scale / normal 差、native depth の意味、normalized intrinsics の定義、
multi-view pose の scale、heavy extension、GPU memory、array shape の違い。

## Decisions deferred to later phases

04: MLflow。05: metric evaluation / scale alignment / datasets。06: backend portability。
multi-view sequence の高度な UI、3D / pose / normal benchmark、全 variant coverage は将来拡張。
07–08: 同じ adapter の Slurm 実機検証。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| representative variant を先に統合 | family ごとの能力差を検証可能な範囲にする | 全 variant 対応を主張しない | manifest に variant を追加 |
| single-view 共通契約を必須にする | MDE 比較の最小単位を先に安定させる | 完全な multi-view 評価は後回し | 同じ PredictionBatch に scene 情報を追加 |

## Stage acceptance status — 2026-11-11

03.1 PASS。metadata-only discovery / manifest検証・実効variant解決、directory追加fakeの
同一Runner / Backend実行、MoGe CPU CLI数値回帰（01Aとの差0）、旧4Runの再読込不変を確認。
最終suiteは100件中95成功・opt-in browser 5 skip（206.751秒）、別browser 5件全成功（231.693秒）。
03.2〜03.6は未着手、Phase 03全体のExitは未達。GPU / 新モデル / 新規独立環境は未検証。
詳細・baseline失敗と修正・Run IDは [03.1 evidence](../../PLANS.md#031-acceptance-evidence--pass)。
