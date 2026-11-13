# GeoCalib pinhole camera task — Phase 03.7

Depth modelではなく、depth-only Runの補助K推定provider。モデル固有処理はこのdirectoryに閉じ込める。
独立Conda workerを共通Backend経由で実行し、UI / depth model環境へtorchやGeoCalibを追加しない。
source / weights / 環境本体は通常版・MoGeデモ版へ同梱しない。[調査・条件](../../docs/geocalib-investigation.md)と
[再構成仕様](../../docs/depth-reconstruction-spec.md)を参照。

## Fixed identities and terms

- Official source `cvg/GeoCalib` revision `1dedb29f94fc11b896c5f572005978aeebccd67f`。
- Pinhole release v1.0 asset191236355、116,074,121 bytes。
  SHA256 `86d6aeacd8bbd974c59ce39f61854e00d36911c732ad89be471476fd708722ac`。
  このSHAは公式asset取得後の実測固定値。publisher公開digestはAPI上nullだった。
- Source Apache-2.0、weights CC BY4.0。公式LICENSEとLICENSE-WEIGHTSを分けて確認。
  ローカル非商用研究用の準備・利用を行い、再配布・公開同梱を行わない。帰属・出典は調査記録に保持する。
- [task.json](task.json)はtrusted補助task定義であり、depth model registryのmanifestではない。

## Explicit preparation

```bash
conda env create --prefix .local/envs/mde-geocalib -f models/geocalib/environment.yml
.local/envs/mde-geocalib/bin/python -m pip install --no-deps \
  'git+https://github.com/cvg/GeoCalib.git@1dedb29f94fc11b896c5f572005978aeebccd67f'
PYTHONPATH=src .local/envs/mde-geocalib/bin/python -m models.geocalib.prepare_checkpoint \
  --output .local/weights/geocalib-pinhole/checkpoint.tar
.local/envs/mde-geocalib/bin/python -m pip check
```

既存ファイルはsize / SHA検証のみで上書きしない。準備以外にdownload / installをしない。
Torch2.6.0+cpu / torchvision0.21.0+cpu / Python3.11.14 / NumPy1.26.4 / Kornia0.8.0を固定する。
全Python解決版は[requirements.lock](requirements.lock)。CPU wheel indexを指定し、独立Python bootstrap後に
`pip install --no-deps --extra-index-url https://download.pytorch.org/whl/cpu -r models/geocalib/requirements.lock`で再作成する条件を示す。
lockから別prefixへの再作成は未検証。sourceのVCS direct_url commitをload時に検証する。

## Use and geometry

```bash
OMP_NUM_THREADS=2 PYTHONPATH=src .local/envs/mde-ui/bin/python -m mde.ui --model da3 \
  --target-config configs/local-targets.example.json \
  --camera-estimator-config configs/camera-estimator.example.json
```

DA3でintrinsicsを要求・保存したRunはnative Kを優先し、depth-only Runは設定済みの自動推定を使う。
既知KをResultsで明示した場合はそれを優先する。既存native Pointsは置換しない。
GeoCalibのpinhole Kは元RGB integer gridへ復元済み。principal pointは画像中心仮定で、focalを最適化する。
推定失敗に固定FOVで代用しない。gravity / pose / absolute scaleをexportしない。

safe `torch.load(weights_only=True)`後、公式local-file extractorと全889 state / bufferのstrict読込を検証する。
seed0、CPU / float32、native短辺320・32倍数cropとundo_scale_cropを使用し、src / weightsを改変しない。
実CPU sampleの元256×256 Kはfx=fy483.3321838、cx=cy128。depth252×252へは記録したOpenCV affineで写す。
実行環境fingerprint・手法 / 版・変換はderived manifestへ保存。精度を保証する値ではない。
最終の実CPU・browser・保存結果の検証状態は[Phase 03](../../docs/phases/phase-03.md#037-depth-only-3d-reconstruction--additional-stage)を参照。
