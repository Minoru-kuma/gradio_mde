# MoGe-2 plugin — Phase 01

1画像の raw depth 保存に絞った adapter。Gradio / Tracking / scheduler / Store を import しない。
共通 worker が画像を読み、ModelAdapter が load / predict / unload と MDEOutput を担当する。
raw depth / metadata / report の保存は worker 側で行う。

## 選定と固定版

- Variant: **MoGe-2 ViT-S Normal**（35M parameters）。最小公開 checkpoint で最初の経路を通す。
- Source: [`07444410f1e33f402353b99d6ccd26bd31e469e8`](https://github.com/microsoft/MoGe/tree/07444410f1e33f402353b99d6ccd26bd31e469e8)
  （2025-11-02、package 2.0.0）。最新 MoGe-3 とその追加依存を自動採用しない。
- Checkpoint: [`Ruicheng/moge-2-vits-normal`](https://huggingface.co/Ruicheng/moge-2-vits-normal/tree/26b477f41595707c5db6770294c0d1721e8ed4ed)、
  revision `26b477f41595707c5db6770294c0d1721e8ed4ed`、`model.pt`。
- SHA-256: `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc`、140,550,416 bytes。
- Source の要件: Python >=3.9、torch >=2.0。01A は Python 3.11.14、
  torch 2.6.0+cu124 / torchvision 0.21.0+cu124 を選定。GPU 互換性は未確認。
  この revision の inference は wheel の userspace CUDA を使い、nvcc / NVIDIA driver を Conda 管理しない。
- Source license: MIT、DINOv2 部分 Apache-2.0。checkpoint の Hub license は MIT。

## 環境の準備

Conda は Python / pip bootstrap、pip は NumPy / Pillow / SciPy / OpenCV-headless / Hub 等を担当する。
新規環境は1つだけ。base / system Python / pip --user を変更しない。

```bash
conda env create -f models/moge/environment.yml
```

environment.yml は [公式対応表](https://docs.pytorch.org/get-started/previous-versions/#v2-6-0) の
cu124 torch / torchvision 組を pip で固定する。CUDA runtime の存在と GPU 実行の可否は別。
GPU / driver との互換性は実機 smoke で確認する。driver は Conda に入れない。
**CPU を実行先として明示選択した場合のみ**、`--device cpu` で実行する。
CUDA wheel でも CPU 実行は可能だが、CPU 専用 build に変更したい場合は以下の置換が必要となる。
この CPU build は現在の environment.yml と異なり、まだ検証していない。

```bash
conda run --no-capture-output -n mde-moge python -m pip install --force-reinstall \
  torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
```

推論に不要な upstream の Gradio / training 依存を導入しないため、推論 API に必要な依存を
environment.yml で準備し、upstream は `--no-deps` で固定する。
全 upstream UI / CLI の dependency completeness を保証する環境ではない。

```bash
conda run -n mde-moge python -m pip install --no-deps \
  'git+https://github.com/microsoft/MoGe.git@07444410f1e33f402353b99d6ccd26bd31e469e8' \
  'git+https://github.com/EasternJournalist/utils3d.git@3fab839f0be9931dac7c8488eb0e1600c236e183'
```

## Checkpoint を事前取得

モデル環境で明示的に準備する。inference Job の中で network download をせず、load 時に
checkpoint hash と installed source revision を照合する。weights / cache は Git 管理外。

```bash
conda run --no-capture-output -n mde-moge python -m models.moge.prepare_checkpoint \
  --output .local/weights/moge-2-vits-normal.pt --cache-dir .local/huggingface
```

その後、control Python から公開 CLI を利用する。

```bash
PYTHONPATH=src python -m mde.cli run --model moge --input tests/assets/sample.png \
  --device cuda:0 --checkpoint .local/weights/moge-2-vits-normal.pt
```

CUDA が使えなければ明示的に FAILED となり、CPU に切り替えない。
CPU を明示選択する場合は `--device cpu` を指定する。
Conda binary は PATH / MDE_CONDA_EXE / --conda-exe、環境は --conda-env / --conda-prefix で指定可能。
application に Miniconda の絶対 path を埋め込まない。

## Depth の意味と保存範囲

[`infer()` の固定 source](https://github.com/microsoft/MoGe/blob/07444410f1e33f402353b99d6ccd26bd31e469e8/moge/model/v2.py) は
camera-space points の z 成分に metric_scale を適用する。
共通出力は **z_depth / metric / m / float32 [H,W]**、OpenCV の x right / y down / z forward。
入力を RGB [0,1] の CHW tensor に変換し、num_tokens=1200、float32、native input grid を使用する。
出力 grid は入力画像に対応する。normal / points / normalized intrinsics は native に存在するが、
01A では depth のみ保存する。mask は validity 判定に使い、invalid Inf は worker が NaN に保存する。
metric scale は推定値であり、この smoke に GT / 精度評価はない。

## 01A 検証状態（2026-10-11時点）

2026-10-11、ユーザーの CPU 選択に基づいて上記 CLI を `--device cpu` で実行し、E2E が成功。
Run ID: `9c5b6556-30d3-43ae-827f-7bd8b0a47580`。float32 `[256,256]` の metric z-depth（m）、
65,536 pixel 有効、invalid 0。raw depth / metadata / WorkerResult / JobResult / stdout / stderr を読み戻した。
実測は Python 3.11.14、torch 2.6.0+cu124、torchvision 0.21.0+cu124、torch CUDA runtime 12.4。
device=cpu、cuda_available=false、GPU / driver=null。GPU 実行・driver 互換性は未検証。
依存導入後の8件の contract tests も成功（17.025秒）。証拠は [PLANS](../../PLANS.md) と
[Phase 01](../../docs/phases/phase-01.md)。01A COMPLETE、01B NOT_STARTED。

upstream の CPU float32 autocast 警告は stderr に保持した。autocast 無効化の通知であり、
device / dtype は明示指定した CPU / float32。警告抑制や upstream 改変はしていない。
`--no-deps` の推論限定環境のため、pip は upstream の click / gradio / matplotlib / pipeline /
trimesh / opencv-python requirements 不足を通知する。cv2 は headless package で提供し、
native v2 API とこの推論経路は検証済み。upstream 全 CLI / UI や pip check の成功は保証しない。

今回、既存環境へ固定 torch / torchvision を導入したコマンド:

```bash
conda run --no-capture-output -n mde-moge python -m pip install --timeout 120 \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu124 \
  --find-links .local/packages torch==2.6.0+cu124 torchvision==0.21.0+cu124
```

`.local/packages` の取得済み NVIDIA wheel 5個は PyPI の SHA-256 と照合済み。
必要な残り package を download して導入し、native API import と実測 runtime を確認した。
CPU を選択する際は CLI の `--device cpu` を指定する。CUDA 要求時の自動 fallback は行わない。

## Phase 01B regression / environment recreation

2026-10-12、旧環境・weightsのないcheckoutから固定版環境を再作成して検証した。
base / systemに導入せず、生成物をGit管理外に置く例:

```bash
CONDA_PKGS_DIRS=$PWD/.local/conda-pkgs conda env create \
  --prefix .local/envs/mde-moge -f models/moge/environment.yml
PIP_CACHE_DIR=$PWD/.local/pip-cache conda run --no-capture-output \
  --prefix .local/envs/mde-moge python -m pip install --no-deps \
  'git+https://github.com/microsoft/MoGe.git@07444410f1e33f402353b99d6ccd26bd31e469e8' \
  'git+https://github.com/EasternJournalist/utils3d.git@3fab839f0be9931dac7c8488eb0e1600c236e183'
conda run --no-capture-output --prefix .local/envs/mde-moge \
  python -m models.moge.prepare_checkpoint \
  --output .local/weights/moge-2-vits-normal.pt --cache-dir .local/huggingface
PYTHONPATH=src MDE_TEST_CONDA_PREFIX=$PWD/.local/envs/mde-moge \
  python -m unittest discover -s tests -v
PYTHONPATH=src python -m mde.cli run --model moge --input tests/assets/sample.png \
  --device cpu --conda-prefix .local/envs/mde-moge \
  --checkpoint .local/weights/moge-2-vits-normal.pt --timeout-seconds 180
```

29 tests成功（53.102秒）。CPU smoke Run ID:
`f4a2052f-71da-4664-9c9f-281cca95fb41`、COMPLETED / exit 0。
float32 [256,256]のmetric z-depth、65,536 valid / 0 invalid、必須12 filesを読み戻した。
新backend / CLIのterminal再collectは再推論せずhash / mtimeも不変。

load / predict / depth serialization / unload / metadata / worker timingと、42 Python distributions /
24 Conda packagesを含むfingerprintを保存。runtime / package digest / 計測scopeは
[Phase 01](../../docs/phases/phase-01.md) と [Environment](../../docs/environment-strategy.md) に記録。
CUDA unavailable環境でcuda:0要求はloadでFAILED、CPU fallbackなしを確認した。
GPU成功 / allocator実機計測 / 精度評価 / upstream全extras充足は未検証。
01A / 01B / Phase 01 COMPLETE、Phase 02は未着手・未承認。
