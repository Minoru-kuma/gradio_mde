# Phase 03 — Model Plugin Architecture / Multi-model Support

Status: **実装中 / 03.1〜03.3受入完了、03.4独立adapter・合成検証を継続、実checkpoint保留**。Exit未達、COMPLETEではない。
`codex/phase-03-implementation`で03.1〜03.6を順番に実施し、受入成功ごとにcommit / 通常push。
最新の停止条件見直し指示により03.4の独立実装・合成検証を継続。実checkpointの取得・利用・再配布は
適用条件の根拠確認まで保留し、03.4実モデルE2E未達のまま03.5には進まない。
直前の03.3で停止する指示と当時の受入結果は下記の履歴として保持する。
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

03.1完了時点の履歴: PASS。metadata-only discovery / manifest検証・実効variant解決、directory追加fakeの
同一Runner / Backend実行、MoGe CPU CLI数値回帰（01Aとの差0）、旧4Runの再読込不変を確認。
最終suiteは100件中95成功・opt-in browser 5 skip（206.751秒）、別browser 5件全成功（231.693秒）。
03.2〜03.6は未着手、Phase 03全体のExitは未達。GPU / 新モデル / 新規独立環境は未検証。
詳細・baseline失敗と修正・Run IDは [03.1 evidence](../../PLANS.md#031-acceptance-evidence--pass)。

03.2完了時点の履歴: PASS。DA3-SMALL single-view depth-only CPU E2Eと独立環境・固定weights / source / license・
共有parameterの厳密読込を確認。105件中100成功・browser 5 skip（154.074秒）。
新Backend / CLIで各2回collectして全hash / mtime不変。relative z-depth / arbitraryを保持。
03.3〜03.6は未着手であり、UniK3D / optional拡張 / multi-view契約 / Phase全体Exitは未達。
詳細: [03.2 evidence](../../PLANS.md#032-acceptance-evidence--pass)。

03.3完了時点の履歴: PASS（当時の終了点）。model / variantのsession別切替、target環境 / weights map、
stale callback拒否、未準備表示とlegacy CLI / UI互換を確認。
全suite 116件中109成功・browser 7 skip（264.524秒）、別browser 7件成功（234.417秒）。
同一BackendからMoGe / DA3を独立環境で実CPU実行し、再collectでhash / mtime不変。
詳細: [03.3 evidence](../../PLANS.md#033-acceptance-evidence--pass--requested-stop-point)。
03.4〜03.6は未着手。最新ユーザー指示に従い03.3のcommit / 通常push後に停止し、Phase 03 COMPLETEとはしない。

## Historical resume evidence — initial 03.4 adoption stop

再開時のfetch / clean tree / branch一致を確認。03.4のUniK3D採用前調査でsourceのlicense表記差異と
checkpointへの適用条件の根拠不足を確認したため、元の指示に従い停止した。
環境構築・weights本体取得・adapter / optional実装・03.5 / 03.6には進んでいない。
03.1〜03.3の受入結果を維持し、Phase 03全体をCOMPLETEとはしない。
確認資料と再開条件: [UniK3D investigation](../unik3d-investigation.md)。

## 03.4 revised stop conditions and independent implementation

上記のlicense調査と当時の一律停止は履歴として保持する。最新指示により独立adapter / fake / 幾何検証は継続し、
明確な禁止条件と衝突する作業のみ停止する。sourceのCC BY-NC / CC BY-NC-SA表記差異と
checkpointへの適用条件未確認は未解決。実checkpointの取得・利用・再配布は引き続き保留する。

実装範囲は [UniK3D adapter contract](../../models/unik3d/README.md)。native形式の合成distanceを
ray_distanceに、native PointsをHWCに変換し、負z / z=0を保持。range / z / pointsの整合性と
無効値を検証し、scale / unitはunknown。モデル固有処理はmodels/unik3d内のみ。
実runtime bridge / production manifest / 実環境 / real checkpointは追加していない。
既存profileでdepth-only / pointsを保存するfake検証であり、実モデル成功と数えない。
core / UI / backend / schemaへの変更なし。rays / confidence / pose保存・新profile・runtime能力照合は未実装。

Verification results（今回実施）:

- 最終suite: **121 tests / 114成功 / browser opt-in 7 skip、305.103秒**。
  UniK3D合成5 testsを含む。checkpointを開かないguard / lifecycle / geometry / worker保存・読戻し、
  missing distance / 全無効出力の失敗とcleanup、unsupported要求拒否が成功。
- 旧Run4件を各2回CLI collectし、全file hash / mtime不変。旧01B Run1件はlocal directory不在で未検証。
  fakeの新instance collectも再推論なし / hash・mtime不変。
- 固定source HEAD、config / model cardのSHA-256一致。調査結果を変更・推定補完していない。
- Markdown32件 / links・anchors251件 / Python AST46件、errors 0。diff whitespace検査も成功。
- 未実施: 実UniK3D checkpoint取得 / 使用 / 再配布、実runtime / 独立環境、実モデル推論、今回のbrowser opt-in / GPU。
  実施ログは`.local/validation/phase-03-4-regression.log` / `phase-03-4-compatibility.json` / `phase-03-4-static.json`。
  これは独立部分の検証済進捗であり、03.4受入成功ではない。

03.4の残条件: 作者の根拠による適用条件確認、採用判断、独立環境構築、実runtime接続、
checkpoint実file digest検証、実モデルdepth-only E2Eと必要optionalの実出力照合。
[作者への確認事項](../unik3d-investigation.md#checkpoint-resume-gate-and-next-steps)は整理済み、送信していない。
**03.4受入未達 / 03.5・03.6未着手 / Phase 03はCOMPLETEではない。**
