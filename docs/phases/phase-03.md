# Phase 03 — Model Plugin Architecture / Multi-model Support

Status: **COMPLETE（2026-11-13、03.1〜03.6と全Exit達成）**。03.6のcommit / 通常pushをもって承認範囲を終了し、Phase 04以降には進まない。
`codex/phase-03-implementation`で03.1〜03.6を順番に実施し、受入成功ごとにcommit / 通常push。
2026-11-11の停止条件見直しで03.4の独立実装・合成検証を継続し、実checkpointの個別保留は維持した。
履歴: 2026-11-12の直前作業は[AGENTSの全Phase共通方針](../../AGENTS.md#license-review-and-decisions)と関連文書の更新のみだった。
最新の再開後、用途・リスクを提示し、固定Smallの取得・非商用local CPU研究利用について個別回答を得た。
不確実性と当時の保留履歴を保持してUniK3D実E2Eを検証し、03.4・03.5の受入・commit / 通常push後に03.6へ進んだ。
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

- [x] `models/moge/`、`models/unik3d/`、`models/da3/` の必要 adapter / manifest / environment を整える。
- [x] upstream / checkpoint / license / scale / shape / camera conventions を variant ごとに記録。
- [x] 3 environment の解決と独立 worker 実行を確認し、依存を application に混ぜない。
- [x] normalized K、w2c / c2w、native dtype / channel layout 等の変換を adapter で行う。
- [x] rays、non-pinhole camera、optional normal / confidence / pose、extras の不足を正しく扱う。
- [x] manifest parameter schema から controls を生成し、worker runtime capability と照合。
- [x] representative single-view を 3 モデルで実行し raw artifacts / metrics を揃える。
- [x] 新しい fake plugin directory の追加だけで Registry に発見されることを確認。
- [x] shared interface を変える必要がある場合は docs / schema reader / compatibility を同時更新。

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

以下は各時点の履歴。停止・未着手の記述を削除せず、後続の受入記録と冒頭の最新状態で更新を追跡する。

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
当時core / UI / backend / schemaへの変更なし。rays / confidence / pose保存・新profile・runtime能力照合は当時未実装。

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

03.4の残条件: 共通方針に沿ったソース / checkpointの用途別利用判断と個別保留の再開判断
（公式資料・用途 / リスク整理と必要なユーザー判断。作者への照会・個別許諾は共通必須条件にしない）、採用判断、独立環境構築、実runtime接続、
checkpoint実file digest検証、実モデルdepth-only E2Eと必要optionalの実出力照合。
[作者への確認事項](../unik3d-investigation.md#checkpoint-resume-gate-and-next-steps)は整理済み、送信していない。
**03.4受入未達 / 03.5・03.6未着手 / Phase 03はCOMPLETEではない。**

## License policy documentation update — 2026-11-12

上記の調査事実・当時の停止判断・検証実績は履歴として保持する。今後の運用はAGENTS共通方針を正本とし、
license不確実性を記録して非影響作業を継続し、直接影響する行為を個別判断する。
今回の更新は実装・実推論の再開、既存checkpoint保留の解除、03.4受入や次段階への移行を意味しない。
文書検証とGit結果は[今回の計画・記録](../../PLANS.md#license-policy-harness-update--2026-11-12)を参照。

## Resumed runtime capability work — 2026-11-12

文書限定作業の後、最新指示により03.4実装・検証を再開。load後 / predict前の汎用runtime capability照合を追加。
非空mapの要求欠落・unsupported・不正宣言は推論前に失敗しunloadする。空mapは旧adapter未宣言として
warning付きで従来検証を継続。conditionalは実出力presence検証を代替しない。正常なsnapshotを
optionalなexecution.runtime_capability_checkへ保存する。モデル名分岐・新profile・schema major変更なし。
詳細: [runtime preflight契約](../model-adapter-spec.md#phase-034-runtime-capability-preflight)。

対象テストはruntime / UniK3D合成あわせて11件成功（26.571秒）。全回帰127件 / 120成功 / browser opt-in 7 skip（175.067秒）。
旧Run4件を各2回collectしhash / mtime不変、旧01Bの1件はlocal不在で未検証。
MoGe `1cad5ed8-488d-457e-9847-8d8069f4c686`、DA3 `07b9015e-3f1a-425a-8d98-f03354852ab8`の
実CPU CLI成功、runtime宣言照合済み / 再collect不変。Python socket guardで外部接続試行なし。
過去保存値とは約1.9e-6 / 1.55e-6の差を観測し完全一致とは記載しない。
同じCPU条件の変更前commit隔離実行との比較では両モデルとも配列完全一致・差0。
静的検証はMarkdown32件 / links・anchors267件 / Python AST49件、errors 0。詳細はPLANSの再開記録を参照。
UniK3Dの[行為別評価と選択肢](../unik3d-investigation.md#scoped-decision-on-resume--2026-11-12)を作成し、
固定Small checkpointの非商用local研究利用に限定した取得・使用の判断をユーザーへ依頼した。
その後ユーザーが不確実性を記録したうえで固定Smallの取得・local研究利用を進めると回答。
この限定範囲で独立環境・実runtime接続へ進む。再配布・商用・公開同梱は含めず、許諾の確定とは記載しない。
03.4実E2E未達 / 03.5未着手 / Phase 03はCOMPLETEではない。

## 03.4 acceptance evidence — PASS

個別判断を受けたfixed Smallのlocal研究取得・使用を実施。適用条件の不確実性は未解決のまま記録し、
再配布・公開同梱・商用利用は未承認。source / weightsをGitへ含めていない。

- 独立環境: Python3.11.14 / torch2.6.0+cpu / torchvision0.21.0+cpu / NumPy2.2.2。
  公式source pin・weights / configの実size / SHA一致、strict native state読込・CPU float32を確認。
  native utils importに必要なwandb / matplotlibは専用環境だけに導入し、Trackingは初期化しない。
- depth-only Run `2f40b740-11d1-4bdb-9b7a-e287bbeed832`、native Points Run `87615672-90ef-44cb-9f3c-9b4239372223`、
  最終source / manifest Run `04826895-b67d-42fa-8314-02751be35d1c`。全てCLI→Runner→Backend→独立workerでCOMPLETED。
  最終source_digest `23e50c71c8d69733a85d44cba08b3d2b599af8a8fa6e19acb532b6e4a4c18abe`。
- 保存range / native Pointsは別の公式API直接実行と配列完全一致。float32 [256,256] / [256,256,3]、65,536 valid。
  `ray_distance / unknown / unknown`でnative値を維持し、仮K・逆投影なし。サンプルの負zは0、fakeは負z / z=0を検証。
- 01A depth-only / 02A geometry profileを再利用。必要optionalはnative Pointsで充足し、新profileは不要。
  rays / confidence / pose等はunsupportedを明記し、要求を拒否・不要求は保存しない。
  正本の「unsupported / 不要求の欠如は正常」に沿い、並行read-only reviewでも追加profile必須の根拠やblockerなし。
- 全3Runを新CLIで各2回collectしhash / mtime不変、再推論なし・unload完了。Python socket外部通信遮断下で実E2E成功。
  旧4Runも各2collect不変、旧01Bの1件はlocal不在で未検証。
- 対象25 tests成功（31.094秒）、全suite129件 / 122成功 / browser opt-in7 skip（248.243秒）。
  UniK3D browser / GPU / 他variant・resolution / metric accuracy・unit確定 / camera入力 / full training・evaluation /
  full upstream pip check・lock別prefix再作成は未検証。既存環境は変更していない。

詳細: [native plugin](../../models/unik3d/README.md)、[調査と履歴](../unik3d-investigation.md)。
03.4のcommit / 通常push後に03.5へ進む。**Phase 03全体はCOMPLETEではない。**

Final static validation: Markdown33件 / local links・anchors289件 / Python AST51件、errors 0。diff whitespace検査成功。

## 03.5 implementation record

03.4 commit / 通常push完了後に開始。旧PredictionRequestを保持し、別MultiViewPredictionRequestと
Runner.submit_viewsを追加。multi-viewのみschema1.1 / request_kind / worker protocol1.1と明示能力でopt-inする。
全input / output ID対応・per-view数値検証・scene JSON / optional terminal ref・全view ZIP保存を実装中。
UIは先頭view previewを維持し、実モデルmulti-view / multi-view入力UIはこの段階の必須にしない。
受入結果は検証後に記録する。03.6 / Phase 04以降には進んでいない。

## 03.5 acceptance evidence — PASS

- Legacy PredictionRequest / single wire1.0 / pathを維持し、別MultiViewPredictionRequestとRunner.submit_viewsを追加。
  multi-viewはJob / result1.1、既知request_kind・variant能力・view数・required worker1.1でopt-in。
  実worker上限1.1を超える要求1.2をRunner準備前とworker読込時に拒否し、一般metadataの同major互換は維持。
- 全input / output ID・順序、全viewのchecksum / shape / original-size provenance / 数値geometryを検証。
  sceneをworker / metadata / terminal / CLI collect / ZIPで保持。未知extrasはopaque JSONで保持し、任意pathは開かない。
- Fake E2E `380684a3-942f-4e08-a8f5-6ba17f043a94`、shape[2,3] / [4,5]、native返却逆順を入力ID順へ保存。
  source_digest `38d43538bfa00f9c77b0c53c2f9982898d1dc47378700d81cafe4b77fe380490`。
  1predict / unload、新Backend2collect・新CLI2collect・ZIPでhash / mtime不変、scene.reference_view_idと未知metadata保持。
- Missing / duplicate / unknown IDs、second-view破損、要求欠落、scene reference / scale / nonfinite JSON、
  formal ref path / checksum異常、runtime未対応を拒否。失敗batchは部分成功を公開しない。
  先頭view previewとIDによるRGB対応、raw不変・再推論なしも確認。
- 最終full139件 / 132成功 / browser opt-in7 skip（218.558秒）、multi-view10 tests成功（42.071秒）。
  追加single nonempty-sceneはjob1.0 / result1.1を確認（最終fullに含む）。
- 実MoGe CPU `58345407-fbf7-4397-a720-4bcec045f5fe`はlegacy wire1.0 / scene省略、旧同条件出力と配列完全一致、
  新CLI2collect不変。旧4Run各2collect不変、旧01B1件はlocal不在で未検証。
- 実モデルmulti-view / multi-view入力UI / pose tensor / generic extras-array exporterは今回の必須scope外、実装していない。
  browser opt-inと3実モデル統合受入・capability matrixは03.6で実施する。

03.5 commit / 通常push後に03.6へ進む。Phase 03全体のCOMPLETEはまだ宣言しない。

## 03.6 integration acceptance evidence — 2026-11-13

03.5 commit / 通常push `0fa251b4b4fb9880025e3fb0f84ad88724fbdc01`の後に開始。
実装範囲は3モデルtarget設定例、既存browser試験の3モデル化、再現条件・capability matrixと受入docs。
core / UI / backendのモデル名分岐や外部source / weightsの同梱を追加していない。

| 統合試験 | 実測証拠 |
| --- | --- |
| 共有Runner / Backend、実CPU / 独立worker | MoGe `7ff6a9da-502a-4d65-83b1-251f7f1f10a1`、DA3 `aecee741-9fe9-461e-af6d-ff2150074892`、UniK3D `4b49e2bd-92d9-4e0c-a43c-239963bc94a4`、全てCOMPLETED |
| Runtime / shape / scale | 3別prefix / Python3.11.14、MoGe torch2.6+cu124 CPU / 256×256 z metric m、DA3 torch2.6+cpu / 252×252 z relative arbitrary、UniK3D torch2.6+cpu / 256×256 range unknown unknown |
| Native optional | MoGe JPEG・Points / normals / K / maskのbrowser4表示、Run `4b9bd75d-38fd-407c-b880-dd7ead47aca1`。UniK3D CLI Points `6f851ef4-8fed-426b-85e1-e28557ecd764`、rangeとnorm(Points)整合、旧直接API照合済みPointsと配列完全一致 |
| Source / numeric regression | 上記共有Backendの3depth RunとUniK3D CLI Points Runのsource_digestを現sourceと照合。3モデルのdepthは03.4同CPU条件の保存値と配列完全一致。値を再scale・補完していない |
| Collect / raw不変 | この4Runを新Backend2回・新CLI2回collect、全file hash / mtime不変、predict各1回・unload完了。wire1.0 / scene省略を維持 |
| Browser | 7 tests全成功、180.328秒。3モデル切替・別session、同時1受理1busy、未準備・controls reset、cancel / timeout / CUDA失敗、Results4表示・再起動・export / deleteを回帰 |
| Offline | Chrome154.0.8037.92、browser外部routeとPython socket guardで遮断。外部接続試行・page errorなし。既存のevent-loop ResourceWarningは残る |
| 旧Run | 現存4Runを各2CLI collect、hash / mtime不変。旧01B `f4a2052f-71da-4664-9c9f-281cca95fb41`はlocal不在、実Run再検証は未実施 |

Local evidence: `.local/validation/phase-03-6-browser.log`、`phase-03-6-readback.json`、
`phase-03-6-compatibility.json`、`phase-03-6-unik3d.stdout.json`とoffline guard logs。
生成物はGitへ追加しない。全回帰の初回はcontrol Pythonを誤使用しNumPy不足6 errors / 35 skipsとなった。
失敗ログを`phase-03-6-wrong-environment.log`へ保持し、独立UI Pythonで再実行し成功した。

最終全回帰は独立UI環境で139件 / 132成功 / browser opt-in7 skip（209.238秒）。
browserは上記別実行7件全成功。target設定5 testsも成功（0.009秒）。
並行read-only監査で新たなExit blockerなし。DA3 / UniK3D lock別prefix再作成やGPU、全upstream extras、
実multi-view / 精度評価、demo packageは未検証であり、今回のExitに含まれない。

### Final Exit audit

- [x] 3モデル各1代表variantのLocal single-view E2E: 上記3実CPU Runが共通経路で成功。
- [x] Directory plugin追加で動作: 03.1 fake discovery / import分離・同じRunner実行、03.2 / 03.4実plugin。
  core / UI / backendにモデル名分岐なし（source検索・import境界回帰）。選択modelだけが独立workerでload。
- [x] Capability matrixのtested / conditional / untested、optional / raw保存: [matrix](../model-capability-matrix.md)、
  MoGe / UniK3D実native optional、DA3 depth-only、runtime拒否・要求欠落、03.5 fake2view / scene / extrasで検証。
- [x] 3環境の再現条件・版・幾何convention・互換docs: 定義・lock・source / checkpoint pin・SHA、
  各plugin README / matrixに再作成手順と未検証範囲を記録。旧single / CLI / raw不変・browserを回帰。

**全Exit達成によりPhase 03 COMPLETE。** 03.6を同じ実装ブランチへcommit / 通常pushし終了する。
PR・main統合・Phase 04以降は未実施・未承認。通常版外部source / weights非同梱、デモは仕様決定のみを維持。
UniK3Dのlicense条件不確実性と過去停止履歴を保持し、個別local研究承認を再配布許諾へ拡張しない。

Final static validation: Markdown34件 / local links・anchors323件 / Python AST53件、errors 0。
JSONとdiff whitespaceも検証。最終read-only並行reviewでもblockerなし。
