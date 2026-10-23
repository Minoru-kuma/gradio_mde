# Phase 02B — Gradio Inference

Status: **COMPLETE / 全Exit達成（2026-10-23）**。Phase 02の内部milestone。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
02B実装・検証・関連docs更新と、全Exit達成後のcommit / main通常pushを承認。02C以降は未承認。

## Goal / Background

既存ExperimentRunnerをGradioから操作する。推論経路とモデル環境をUIから独立させる。
開始時のRunnerはsubmit / status / collect / cancelを持ち、Gradioは未実装だった。
02BでGradio操作を追加し、数値progress APIは拡張せずunavailableとする。
LocalBackendのbusy guardはinstance内のみであり、sessionごとにbackendを作る設計は避ける。

## Scope / Non-goals

Inference / Resultsの2タブ。Inferenceにmodel / variant、画像upload・検証、明示device、
Local-only backend、parameter / timeout設定、submit、Run ID、非同期status / progress、
cancel / timeout / failure / busyを表示する。完了時にResultsへvalidated resultとRun IDを渡す。
Resultsの枠・共通詳細を扱い、4モードの完全viewerは02C、管理操作は02D。
job queue、他backend、公開多ユーザー、active recovery、torch / native推論のUI実装は対象外。

## Dependencies

02A exitと02Bの個別実装承認。
[Architecture](../../architecture.md)、[Execution](../../execution-backend-spec.md)、
[Environment](../../environment-strategy.md) の公開boundary。Phase 01のCLIを維持する。

## Implementation tasks

- [x] 独立application environmentを計画し、実装時のGradio版・必要依存とfrontend assetsを
  調査してpin、lock / 再作成手順を記録。workerにGradioを要求しない。
- [x] Registry metadataから準備済み1モデル / variant・parameter schemaを表示。
  宣言capabilityと実際の出力を区別する。未知parametersはRunner側でも拒否。
- [x] uploadを共通入力検証経由でRunnerに渡す。現行PNG制約を基準とし、
  追加formatを採る場合は共通変換・サイズ制限・元入力provenanceを別途明文化する。
  空・壊れた画像・過大入力はsubmit前に拒否する。
- [x] 明示cpu / cuda:0、対応dtype、Local backend、実行timeoutを公開requestへ変換。
  CUDA unavailableはfailureで、自動CPU fallbackはしない。
- [x] 全browser sessionが単一のRunner / LocalBackend instanceを共有。
  session stateはinput / parameters / JobHandle / Run ID / Results選択 / callback世代を分離。
  stale poll / 古い完了通知が新しいsession選択を上書きしない。
- [x] callbackは短いsubmit / poll / cancel / collectを呼び、推論完了待ちでblockしない。
  busyのsubmitは明示拒否して再操作を促す。Gradio event dispatchがpending inferenceを
  queueとして受理しない設定を版固定後に検証する。queue表示を新設しない。
- [x] statusに従いRUNNING / COMPLETED / FAILED / CANCELLED、TIMEOUT errorと
  cancel_requestedを区別。数値progress未提供ならindeterminate / unavailableとし架空%を表示しない。
- [x] handle操作はそのsessionに紐付け、別sessionのcancelやuploadを混線させない。
  terminal collectの検証成功後すぐResultsへ引き渡す。02Bは共通詳細・refsの表示までとし、
  直接artifact downloadは02Cに留保する（公開時には共通path検証を必須とする）。
- [x] window切断は暗黙cancel / deleteにしない。保存terminal Runは後でRun IDから開く。
  application再起動によるactive job復旧は提供しない。

## Tests / Exit criteria

- [x] fake Runner / backendで各status、indeterminate progress、error / timeout / missing metricを表示。
- [x] 空・壊れた・過大画像、未知variant / parameter / deviceをsubmit前に拒否。
- [x] 2browser sessionsの入力・handle・結果分離、同時submitのbusy拒否、
  sessionごとのcancel、terminal後の次job成功、古い通知・cancel完了raceを確認。
- [x] UI / Registryにadapter / torch importなし、callbackにConda / subprocess制御なしを静的検証。
- [x] pin環境で明示CPU MoGe 1画像のUI smoke、CLIとの共通成果物契約一致、
  完了→Results引渡し・failure / cancel / timeout表示を確認し起動手順を記録。

全項目成功で02B exit。3D表示・Run削除はここで要求しない。実測・実行記録は以下を参照。

## Known risks

Gradio版によるevent queue / session lifetime / cancel挙動、pollのUI block、
共有backendの複数process起動、古いcallback更新、upload一時ファイルの寿命。
ローカル単一application processを運用条件として明記し、multi-process調停を保証しない。

## Decisions / Deferred decisions

2タブ、Local-only、1共有backend、job queueなし、session state分離を採用。
Gradio 6.30.0 / UI poll 0.5秒 / Backend観測0.2秒 / PNG 10 MiB・4,194,304 pixels・edge4096、
全event queue=False / concurrency_limit=None / trigger_mode=onceを固定・browser検証。
独立application Python 3.13.13、推移依存lockとoffline手順は [起動仕様](../../gradio-inference.md)。
structured progressが必要なら共通契約をoptional拡張し、ログから精度不明な%を捏造しない。
高度なqueue / active recoveryはPhase 06以降、Slurmは07–08、認証は後続の別承認。


## Acceptance evidence — 2026-10-23

- Start: git fetch origin成功、main clean、HEAD / origin/main `a2ccc73`、左右差分0。
  02Bのみ実装・検証・docsと全Exit後のcommit / main通常pushを承認。02C以降は未着手。
- Application: Python 3.13.13 / Gradio 6.30.0の独立venv。推移依存は
  [ui.lock](../../../requirements/ui.lock)、browser専用依存は [browser.lock](../../../requirements/browser.lock)。
  applicationにtorch / MoGeなし、worker環境へのGradio導入・依存変更なし。
  全固定wheelsの事前取得と、別venvへ `--no-index` install / pip check成功。
- fake / contract: status / indeterminate / missing metrics、画像検証、未知設定、
  session input / handle / result分離、busy / terminal後の次job、cancel-before-handle、
  slow status中の即応、cancel完了race、古いcancel世代、load完了順序逆転、disconnect、
  integrity failure、同時collect / read-only / active recovery拒否を検証。
  common Runner単独でも未知variant / device / parameterをRun作成前に拒否する。
- browser: Chrome 154.0.8037.92 / Playwright 1.58.0、独立した2browser contexts。
  入力A sampleと入力B 32×16の異なるPNGが混線せず、保存input hashも照合。
  busyは約0.164秒で拒否（callback応答＋browser観測の実測、性能保証ではない）。
  worker解放後も拒否jobが自動起動しない。別sessionのcancelでjobが止まらない。
  同時刻にscheduleした2つの実clickは1受理・1busy。failure / timeout / cancel / Results引渡し成功。
  inference queue join要求0、外部HTTP要求0、page errors 0。
- 最終source CPU UI Run: `799d2355-c57b-4552-92c4-644a7f25e775`、COMPLETED。
  fixed MoGe-2 ViT-S Normal / upstream 07444410f1e33f402353b99d6ccd26bd31e469e8、
  checkpoint SHA-256 79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc。
  model Python 3.11.14 / torch 2.6.0+cu124 / runtime CUDA 12.4、明示CPU、cuda_available=false。
  raw depth float32 [256,256] / z_depth / metric m、01A-depth-only。
  Depth SHA-256 ada9a6dcc0a776c6277195c4dd362b9600ea61e8d665b0d3c2bbfb492a9e6ab4。
  既存CLI CPU depthと一致。GT accuracy評価・GPU推論成功ではない。
  実測load=2.970123256秒、predict=3.091525671秒、worker=6.343568093秒。
  scope / unitは保存metricsに保持。CPU allocator / GPU memoryは未計測で補完しない。
- 実model UIのCUDA unavailable failure: `84753716-6fec-4e1c-8957-d909bdfdff2f`。
  FAILED / CUDA requested but unavailable; no CPU fallbackを表示。
  明示CPU cancel: `691c1c9f-c4cb-4919-900a-395d04a434bc`、CANCELLED。
  timeout=1秒: `d73ab53c-9038-4a70-8988-cd05925512b7`、FAILED / TIMEOUT。
- application / Conda / workerのPython socket非loopback connect / DNSをaudit hookで拒否し、
  browserの外部HTTPをabortする条件下で上記UI smoke成功。
  frontendの外部要求0。local checkpointを使用し、network namespace全体の遮断とは区別する。
  新application / WorkerManagerなしで成功RunをRun IDから開き、全fileのSHA-256 / mtime不変。
- Static: UI / Registryにadapter / torch importなし。callbackにConda / subprocess制御なし。
  全5events queue=False、表示writerは1Timer、progress %を追加していない。
  numeric / model固有処理・新schema・3D / mesh / 管理serviceを追加していない。

## Test execution and limitations

- 変更前40 tests成功（140.204秒）。
- 追加UI contracts 11件成功（6.703秒）、structureを含む13件成功（11.332秒）。
- 全体初回55件: 53成功・実browser 2件は明示skip（159.715秒）。
  最終全体55件: 53成功・実browser 2件は明示skip（149.853秒）。
  最後に強化したcommon Runner事前検証・load順序逆転2件も成功（0.051秒）。
  browser / CPUは下記別コマンドの実行結果で補完し、未実行を成功に含めない。
- 最終fake browser 1件成功（23.097秒）、最終実CPU UI 1件成功（25.977秒）。
- 開発中にempty-input検証の前提device未選択とGradioのfilename表示空白でbrowser assertionsが失敗。
  テスト前提を訂正。再起動時pollがState初期化前に走る競合を修正し、最終CPUログのTracebackは0。
  stale load testのRun Root未作成を正しく期待するようfixture assertionも訂正した。
- Gradio構成時にupstream由来のunclosed event loop ResourceWarningが出る。
  tests / browser操作は成功し、警告を抑制していない。GPU / 他OS / 他browser / 公開運用は未検証。
- ローカル証拠はGit管理外 `.local/validation/02b-*`、weights / venv / wheelhouse / runsもGit管理外。
  02C / 02D・他モデル・Tracking・Benchmark・Slurm・高度なqueue / recoveryは未実装・未承認。


## Final exit assessment

全Implementation tasks / Tests・Exit criteriaを達成し **02B COMPLETE**。
27 Markdown / 184相対links・anchors・fences、26 Python AST、manifest JSON / pyproject TOML、
control dependencies空、`git diff --check`を確認。旧01A / 02A・最終CPU・失敗 / cancel / timeoutの
6Runを新CLIで各2回collectし全file hash / mtime不変。CPU Runの最終source digest一致も確認した。
保存Run再表示に再推論・model環境を要求しない。02B内の未達Exitはない。
Phase 02はIN_PROGRESS、02C〜02DはNOT_STARTED / 未承認。3D / download / 管理操作へ進まない。
remote更新なしを再確認し、承認済み02B差分のみcommit / mainへ通常pushする。
