# Phase 02B Gradio inference

02Bの実装契約と起動手順。検証結果は [02B](phases/phase-02/phase-02b.md) に記録する。
Inference / Resultsの2タブ、準備済み1モデル、Local-only、単一application processで使う。
Resultsは検証済みJobResult / Run ID / metadata / artifact refs / 実測metrics / errorsの共通詳細。
4モードviewer・raw depth download・派生生成は02Cで追加（[Results Viewer](results-viewer.md)）。
履歴・export・削除等の管理操作は02D、未実装・未承認。

## Environment and dependency pins

- 検証OS: Linux x86_64。application Python **3.13.13**、Gradio **6.30.0**。
- 直接依存: [ui.in](../requirements/ui.in)。全推移依存: [ui.lock](../requirements/ui.lock)。
  Pillow 12.3.0、gradio-client 2.7.2、FastAPI 0.161.1等もlockに固定する。
  Linux / Python 3.13用の検証済みresolutionであり、他OS / Pythonの再現は未検証。
- applicationは独立venv。baseやmodel環境へGradioを導入しない。
  Gradioの推移依存にNumPy / pandasがあるがtorch / MoGeはapplicationに不要。
  model workerは既存独立Conda環境を維持する。
- browser検証の追加依存は [browser.lock](../requirements/browser.lock)。
  Playwright 1.58.0とsystem Google Chrome 154.0.8037.92で検証する。
  通常利用にPlaywrightは不要。別のbrowser executableは `MDE_CHROME_EXE` で指定できる。
- lockはexact-version resolution。wheelhouseの配布・hash照合は環境準備時に行い、
  repositoryへweights / wheels / venv / Runをcommitしない。

Python 3.13.13を事前準備したsource checkoutで、オンライン初回構築:

```bash
python3.13 -m venv .local/envs/mde-ui
.local/envs/mde-ui/bin/python -m pip install -r requirements/ui.lock
.local/envs/mde-ui/bin/python -m pip check
```

model環境・checkpointの準備は [MoGe README](../models/moge/README.md) の固定版手順に従う。
通常起動（browserは `http://127.0.0.1:7860` を開く）:

```bash
PYTHONPATH=src .local/envs/mde-ui/bin/python -m mde.ui --model moge \
  --checkpoint .local/weights/moge-2-vits-normal.pt
```

`--conda-env` / `--conda-prefix` / `--conda-exe`、`--run-root`、`--port`も指定できる。
Run Root優先順位はCLIと同じ明示引数 → `MDE_RUN_ROOT` → project rootの `runs/`。
UIのdeviceは初期未選択。推論前に **cpu** または **cuda:0** を明示選択する。
CUDA unavailableはFAILEDでCPU fallbackしない。dtypeは現行manifestのfloat32。
timeoutは既定300秒、正の整数または空欄（制限なし）、Conda起動時間を含む。
モデルparametersはmanifestの型・enum・範囲・defaultからcontrolを生成する。
未知variant / parameter / device / dtype / outputsはUI serviceとRunnerで拒否する。

InferenceでPNGをuploadし、条件とoutputsを選びRun inferenceを押す。
statusは0.5秒ごとに更新され、terminal collect成功後にResultsを選択する。
FAILED / TIMEOUT / CANCELLEDも確定JobResultのerrorとともに表示する。
progressはunavailable / indeterminate。未計測metrics / GPU memoryはunavailableとし捏造しない。
busyなら自動再実行せず、現在のjob終了後に利用者がRun inferenceを押す。

保存済みterminal RunはResultsのRun ID入力から開く。model環境なしの起動も可能:

```bash
PYTHONPATH=src .local/envs/mde-ui/bin/python -m mde.ui --model moge --read-only
```

read-only起動ではsubmitはエラーになり推論しない。保存terminal結果の参照には
manifest / source checkout / Run Directoryが必要。active recoveryは拒否する。
これは既存collect経路の最小利用であり、02Dの管理service / 履歴一覧ではない。

## Session and dispatch contract

`mde.ui`のcomposition rootがRegistry / Store / WorkerManager / LocalBackend / Runnerを
一度だけ構成する。`mde.ui_controller.InferenceController`が全browserの共有serviceとなる。
callbackはcontrollerのみを呼び、model adapter / torch / Conda / subprocessを制御しない。
worker / RegistryはGradioに依存しない。

- browserごとの `gr.State` にserver生成token、operation generation、最後の表示snapshotを持つ。
  upload / parametersは各browser componentの状態。handleはserver側sessionだけに保持する。
  clientから任意handleを受け取るcancel APIは設けない。
- submitはnonblockingな単一admission slotを取得し、busyなら即時拒否。
  入力検証・owned staging copy後にdaemon threadを開始する。inference待機のqueueはない。
  slotはBackendのterminal確認・collect完了まで保持する。Backend自身のbusy guardも維持する。
- background threadだけがRunner.submit / status / cancel / collectを呼ぶ。
  0.2秒周期で観測する。Gradio pollはin-memory snapshotのみで停止処理・成果物検証を待たない。
  cancel callbackは要求flagを記録し、Backend receipt / terminal確認までcancel_requestedを表示する。
  successが先ならCOMPLETED、timeoutはFAILED / TIMEOUT、cancelはCANCELLEDを維持する。
  stop / status観測失敗はUNKNOWNまたはaction_errorとし、成功・slot解放を捏造しない。
- 全イベントに **queue=False / concurrency_limit=None / trigger_mode=once**。
  submit / cancel / openへの応答はnoticeだけを更新する。
  status / Results / tab選択のwriterは一つのTimerのみ。Timerの重複発火を禁止する。
  operation generationをcancelと完了通知で検証し、古いcancelは次jobを止めない。
  保存Runの古いload完了は新しいselection generationへpublishしない。
- session初期化までsubmit / cancelを無効にし、初期化前pollはskipする。
  disconnectやState削除はcancel / Run削除にしない。jobの観測はterminalまで続く。
  アプリ停止時のactive job復旧は提供しない。複数application processの相互調停も行わない。

## Input and result compatibility

PNG 1枚、最大 **10 MiB / 4,194,304 pixels / 4096 pixels per edge**。
APNG / multi-frameは拒否する。共通 `inspect_png` に加えapplication側Pillowでverify / loadし、
空・破損・過大入力をRunner.submit前に拒否する。Gradio upload routeにも10 MiB上限を設定する。
uploadのowned copyを背景処理へ渡し、寿命をbrowser一時fileに依存させない。
resize / re-encodeしない。Runnerへ元PNG bytesを渡すため、既存input hash provenanceを維持する。

JobSpec / schema 1.0 / depth-only default / optional geometry profileを変更しない。
collectのID / path / symlink / digest / geometry検証は既存Backend / Storeを利用する。
Runnerの `run.json` publicationだけをinstance lockで直列化し、同内容の再collectは再書込しない。
raw / WorkerResult / 確定JobResultは不変。再表示で再推論しない。
02Bはartifactのrefsを表示し、直接file downloadは公開しない。

## Offline preparation and limits

オンラインで同じOS / Pythonに対するwheelhouseを準備し、必要ならSHA-256 manifestを保存する:

```bash
.local/envs/mde-ui/bin/python -m pip download --only-binary=:all: \
  --dest .local/packages/ui-wheelhouse -r requirements/ui.lock
```

オフラインでは事前準備したPythonとwheelsから独立venvへ導入できる:

```bash
python3.13 -m venv .local/envs/mde-ui-offline
.local/envs/mde-ui-offline/bin/python -m pip install --no-index \
  --find-links .local/packages/ui-wheelhouse -r requirements/ui.lock
.local/envs/mde-ui-offline/bin/python -m pip check
```

model source / model環境 / 固定checkpoint / 必要cacheも別途事前準備する。
起動時にGradio analytics無効、share=False、system fonts、SSR無効、loopback bind、
`HF_HUB_OFFLINE=1`（未設定時）を指定。frontend JS / CSSはGradio wheelからlocalhost配信する。
推論中の自動installは行わない。local checkpointなしではoffline推論成功を保証しない。

検証ではbrowserの非localhost HTTPをabortし、Python application / Conda / workerの非loopback
socket connect / DNSをtest-only audit hookで拒否する。OS全体のnetwork namespace遮断や
native library独自の通信を包括的に制御するものではない。検証条件をこの範囲で区別する。
公開多ユーザー運用・認証・GPU成功・3D表示・学会実演は今回の検証対象外。

## Verification commands

```bash
PYTHONPATH=src .local/envs/mde-ui/bin/python -m unittest discover -s tests -v
.local/envs/mde-ui/bin/python -m pip install -r requirements/browser.lock
MDE_BROWSER_TESTS=1 PYTHONPATH=src .local/envs/mde-ui/bin/python \
  -m unittest tests.test_ui_browser.FakeBrowserTests -v
MDE_UI_CPU_SMOKE=1 MDE_TEST_DENY_EGRESS=1 \
  MDE_TEST_OFFLINE_LOG="$PWD/.local/validation/02b-offline-sockets.log" \
  PYTHONPATH=tests/fixtures/offline:src .local/envs/mde-ui/bin/python \
  -m unittest tests.test_ui_browser.CPUUIBrowserTests -v
```

browserテストはlocalhost ports 7861 / 7862を使用する。CPU smokeは `runs/` に成果物を保持する。
通常のdiscoverは2つの実browserテストをskipするため、Exit検証では上記を明示的に実行する。
UI依存がないcontrol環境ではUI専用testsもskipする。未実行を成功と数えない。

公式参照: [Gradio event dispatch](https://github.com/gradio-app/gradio/blob/gradio%406.30.0/gradio/events.py)、
[Timer](https://www.gradio.app/docs/gradio/timer)、[Queue](https://www.gradio.app/guides/queuing)、
[PyPI release](https://pypi.org/project/gradio/6.30.0/)。
版固定のinstalled source signature / browser requestを実際の判断根拠とする。
