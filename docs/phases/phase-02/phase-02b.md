# Phase 02B — Gradio Inference

Status: **NOT_STARTED / 実装未承認**。Phase 02の内部milestone。以下は設計のみ。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
今回の承認は文書整備・検証・commit / main pushのみ。実装開始・依存導入は行わない。

## Goal / Background

既存ExperimentRunnerをGradioから操作する。推論経路とモデル環境をUIから独立させる。
現行Runnerはsubmit / status / collect / cancelを持つが、Gradioと数値progress APIは未実装。
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

- [ ] 独立application environmentを計画し、実装時のGradio版・必要依存とfrontend assetsを
  調査してpin、lock / 再作成手順を記録。workerにGradioを要求しない。
- [ ] Registry metadataから準備済み1モデル / variant・parameter schemaを表示。
  宣言capabilityと実際の出力を区別する。未知parametersはRunner側でも拒否。
- [ ] uploadを共通入力検証経由でRunnerに渡す。現行PNG制約を基準とし、
  追加formatを採る場合は共通変換・サイズ制限・元入力provenanceを別途明文化する。
  空・壊れた画像・過大入力はsubmit前に拒否する。
- [ ] 明示cpu / cuda:0、対応dtype、Local backend、実行timeoutを公開requestへ変換。
  CUDA unavailableはfailureで、自動CPU fallbackはしない。
- [ ] 全browser sessionが単一のRunner / LocalBackend instanceを共有。
  session stateはinput / parameters / JobHandle / Run ID / Results選択 / callback世代を分離。
  stale poll / 古い完了通知が新しいsession選択を上書きしない。
- [ ] callbackは短いsubmit / poll / cancel / collectを呼び、推論完了待ちでblockしない。
  busyのsubmitは明示拒否して再操作を促す。Gradio event dispatchがpending inferenceを
  queueとして受理しない設定を版固定後に検証する。queue表示を新設しない。
- [ ] statusに従いRUNNING / COMPLETED / FAILED / CANCELLED、TIMEOUT errorと
  cancel_requestedを区別。数値progress未提供ならindeterminate / unavailableとし架空%を表示しない。
- [ ] handle操作はそのsessionに紐付け、別sessionのcancelやuploadを混線させない。
  terminal collectの検証成功後すぐResultsへ引き渡す。downloadは共通path検証経由。
- [ ] window切断は暗黙cancel / deleteにしない。保存terminal Runは後でRun IDから開く。
  application再起動によるactive job復旧は提供しない。

## Tests / Exit criteria

- [ ] fake Runner / backendで各status、indeterminate progress、error / timeout / missing metricを表示。
- [ ] 空・壊れた・過大画像、未知variant / parameter / deviceをsubmit前に拒否。
- [ ] 2browser sessionsの入力・handle・結果分離、同時submitのbusy拒否、
  sessionごとのcancel、terminal後の次job成功、古い通知・cancel完了raceを確認。
- [ ] UI / Registryにadapter / torch importなし、callbackにConda / subprocess制御なしを静的検証。
- [ ] pin環境で明示CPU MoGe 1画像のUI smoke、CLIとの共通成果物契約一致、
  完了→Results引渡し・failure / cancel / timeout表示を確認し起動手順を記録。

全項目成功で02B exit。3D表示・Run削除はここで要求しない。今回は未実行。

## Known risks

Gradio版によるevent queue / session lifetime / cancel挙動、pollのUI block、
共有backendの複数process起動、古いcallback更新、upload一時ファイルの寿命。
ローカル単一application processを運用条件として明記し、multi-process調停を保証しない。

## Decisions / Deferred decisions

2タブ、Local-only、1共有backend、job queueなし、session state分離を採用。
Gradio版 / polling間隔 / upload上限 / dispatch設定は実装承認後に公式仕様とbrowser検証で確定。
structured progressが必要なら共通契約をoptional拡張し、ログから精度不明な%を捏造しない。
高度なqueue / active recoveryはPhase 06以降、Slurmは07–08、認証は後続の別承認。
