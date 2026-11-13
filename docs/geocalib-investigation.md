# GeoCalib investigation — Phase 03.7

確認日: **2026-11-13**。対象は公式 `cvg/GeoCalib` の固定sourceと公式pinhole checkpoint。
これは[03.7計画](../PLANS.md#phase-037-depth-only-3d-reconstruction--implementation-plan)の調査記録であり、
実checkpointの取得・環境構築・実CPU成功を調査だけで達成扱いにしない。
[Phase 03](phases/phase-03.md#037-depth-only-3d-reconstruction--additional-stage)、
[共通license判断](../AGENTS.md#license-review-and-decisions)、[配布方針](distribution-policy.md)を適用する。

## Official sources and fixed identity

著者はAlexander Veicht、Paul-Edouard Sarlin、Philipp Lindenberger、Marc Pollefeys。
公式repositoryは[cvg/GeoCalib](https://github.com/cvg/GeoCalib)、研究発表は
[GeoCalib: Single-image Calibration with Geometric Optimization, ECCV 2024](https://arxiv.org/abs/2409.06704)。
今回の実装根拠は以下のimmutable sourceと公式release metadataであり、論文の性能をこの実験基盤の実測値にはしない。

| 対象 | 確認したidentity |
| --- | --- |
| Source revision | `1dedb29f94fc11b896c5f572005978aeebccd67f` |
| Source commit | `2026-10-14T11:32:08Z`、weightsのCC BY 4.0原文への変更 |
| Package metadata | `geocalib` version `1.0`、Python `>=3.9`。package版だけではsource revisionを特定できない |
| Checkpoint release | `v1.0`、release ID `174012542`、公開 `2024-09-08T13:05:40Z` |
| Release tagのsource | `53aac4956f42a2b0a34939ab6da33373dc593f1b`。今回採用する後続source revisionとは別 |
| 対象asset | `geocalib-pinhole.tar`、asset ID `191236355`、`116074121` bytes |
| Asset日時 | 作成 `2024-09-08T12:52:29Z`、更新 `2024-09-08T12:57:46Z` |
| 配布元digest | 公式release APIの`digest`は`null`。publisher SHA-256は今回確認できていない |
| 対象外asset | `geocalib-distorted.tar`、asset ID `191236728`、`116143955` bytes。今回は選定・取得対象にしない |

出典:
[固定commit API](https://api.github.com/repos/cvg/GeoCalib/commits/1dedb29f94fc11b896c5f572005978aeebccd67f)、
[tag API](https://api.github.com/repos/cvg/GeoCalib/git/ref/tags/v1.0)、
[release API](https://api.github.com/repos/cvg/GeoCalib/releases/tags/v1.0)、
[release画面](https://github.com/cvg/GeoCalib/releases/tag/v1.0)、
[pinhole配布URL](https://github.com/cvg/GeoCalib/releases/download/v1.0/geocalib-pinhole.tar)、
[固定package metadata](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/pyproject.toml)。

Releaseのtag / filename / asset IDは取得対象を追跡する情報であり、bytesの暗号学的同一性を代替しない。
実取得時はsizeと自身で算出したSHA-256を記録・固定し、その後のload / cache provenanceで照合する。
未確認のdigestを推測してmanifestへ書かない。

## Source and weights license evidence

固定READMEはcodeをApache-2.0、`geocalib-pinhole` / `geocalib-distorted`のtrained weightsを
CC BY 4.0と明示する。ソースの条件を根拠なくweightsへ転用した判断ではない。
固定`LICENSE-WEIGHTS`はCopyright 2024 ETH ZurichとCC BY 4.0の本文を持つ。

| 公式固定資料 | Bytes | SHA-256 | 確認結果 |
| --- | ---: | --- | --- |
| [README.md](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/README.md#license) | 23799 | `cf161e039075ea38ec646bcad7590cc3f15cade9a425c0a07c0ff2334ef1d275` | Code / weightsを分け、対象weights名も明記 |
| [LICENSE](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/LICENSE) | 10755 | `b458637616125d96702f04666c7717d3a1ade0824f6ea6ccf512b4828f35c8d5` | Apache-2.0 |
| [LICENSE-WEIGHTS](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/LICENSE-WEIGHTS) | 18684 | `2e0ae239ec372d4ab2ccad3b8280f8fa985badd7fb2765097aec2503c892bb8a` | CC BY 4.0、ETH Zurichのcopyright表示 |
| [requirements.txt](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/requirements.txt) | 50 | `c8d36763021eb59b0c037f9a159273812f64f09ea4d915d982d73e701b04d643` | 推論依存名、version pinなし |
| [pyproject.toml](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/pyproject.toml) | 1145 | `a87e9860da5c358797fa70724a90b8f76ada1bcb165dbae0627f1e881c556a24` | Package metadata / source license参照 |

これらのhashは調査時に公式raw HTTPから読んだ資料のhashで、weights本体のhashではない。
Codeを共有・改変配布する場合はApacheのlicense・通知・変更表示等を保持する。
Weightsを共有する場合はCC BYの帰属、license参照、変更の明示等の条件を別に確認・遵守する。
著者名・論文・出典とlicenseへの参照は本記録に残す。全依存の再配布条件・NOTICEの確認済みという意味ではない。

### Scoped research decision

予定する行為は、03.7で承認された固定pinhole weightsの明示取得と独立環境での非商用local CPU研究・検証。
公式資料でcode / 対象weightsの条件が確認でき、この用途との明確な衝突は今回見つかっていない。
AGENTS規則13.2に従い、通常の技術検証を進める。作者への個別照会や追加のユーザー承認を定型gateにはしない。
技術検証の未完了をlicenseによる停止と混同しない。

公開されていることだけで無制限の許諾とは扱わず、用途変更・新たな禁止との衝突が判明した場合は該当行為を再評価する。
本体・通常版、自作Adapterの公開にGeoCalib source / weights / 環境実体を含めない。
MoGeデモ版へGeoCalibを追加する決定でもない。公式配布元から利用者が別途準備する境界を維持する。
問い合わせの送信、外部への公開・再配布は行っていない。

## Native calibration and pixel conventions

根拠は固定[extractor.py](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/geocalib/extractor.py)、
[camera.py](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/geocalib/camera.py)、
[utils.py](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/geocalib/utils.py)。

- `calibrate`への画像はRGB、float、範囲`[0,1]`、CHWまたはbatch付き。今回はsingle-view / pinholeだけを対象にする。
- Native前処理は短辺320へのresizeと32倍数に合わせるcrop。`scales`と`crop_pad`を保持し、
  返却cameraは`undo_scale_crop`を通じて元入力gridへ戻る。処理中の320 gridのKを元画像へそのまま適用しない。
- `camera.K`の焦点距離とprincipal pointはpixel単位。`pixel_coordinates`は`0..W-1` / `0..H-1`の整数grid。
  `from_dict`の一部docstringにnormalizedとの記述があるが、実装のK組立て・normalize・pixel gridを根拠に判断する。
- Principal pointは既定`(W/2,H/2)`を仮定し最適化しない。この値を`((W-1)/2,(H-1)/2)`へ便宜的に置換しない。
  整数pixel-center方式と、principal pointが必ず画像中央の特定pixelに一致するという主張は別である。
- Pinhole逆投影は`[(u-cx)/fx,(v-cy)/fy,1]`に対応する。gravity出力はcamera pose全体・並進・depthのmetric scaleを与えない。
- Distorted cameraの出力をdistortionなしの3×3 Kだけに縮退させない。今回は歪みモデルの推定・補正を採用しない。

## CPU dependencies and execution cautions

上流推論packageのrequirementsは`torch`、`torchvision`、`opencv-python`、`kornia`、`matplotlib`。
上流requirementsに版固定はなく、そのままで環境再現性を保証する資料ではない。NumPyも実際のsourceでimportされる。
独立環境で解決した版・source revision・Python / torch / torchvisionの組合せを定義とfingerprintへ記録する。
Training用`siclib`、mmcv等を推論に必須と推定して追加しない。

固定推論packageのsource走査ではcalibrationをCUDAへ強制する呼出しは確認されなかった。
`utils.get_device`は自動選択helperなので実行側で使わず、CPUを明示する。
`misc.autocast`はNumPy入力をTensorWrapperのdevice / dtypeへ変換するdecoratorで、CUDA混合精度のautocastではない。
LM optimizerのCholesky解法はCPUへ移して計算する。これは実環境でのCPU成功を確認済みという意味ではない。

注意点と根拠:

- `GeoCalib(weights="pinhole")`はtorch hub経由の自動downloadを行う。明示準備済みlocal checkpoint pathを渡し、
  size / hashをload前に照合する。推論・discoveryで自動取得しない。
- Local checkpointの上流loadは`torch.load(..., map_location="cpu")`。PyTorchの`weights_only`既定値やcheckpoint内容との
  互換性を実物で確認する。失敗を無条件のunsafe読込fallbackで隠さない。
- [NMF2D](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/geocalib/modules.py)はeval時も
  forwardごとに乱数でbasesを生成する。再現比較ではseedを明示し、source / weights / dtype / 環境とともにprovenanceへ記録する。
  seed未固定の別推論同士に配列完全一致を要求・主張しない。
- [flexible_load](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/geocalib/geocalib.py)は
  一部key不一致を非strictに読める。選定checkpointのmissing / unexpected keysとparameter充足を検証し、
  任意の部分読込を固定checkpointの成功と扱わない。
- [LM optimizer](https://github.com/cvg/GeoCalib/blob/1dedb29f94fc11b896c5f572005978aeebccd67f/geocalib/lm_optimizer.py)の
  初期値・最適化失敗と、有限の返却値だけでcalibration精度を保証することは別。失敗・不正Kを理由付きで扱う。

## Integration contract to verify

GeoCalibはdepthを持つModelAdapterとして捏造せず、別環境のK-only auxiliary処理として既存Backend経由で実行する。
UI / Registryへadapter・torchをimportせず、core / UI / backendへモデル名分岐を加えない。
以下は03.7で検証する契約であり、本調査だけで実装済みにはしない。

- 既存native Pointsを維持し、depth-only時のK選択は既知K → 保存native K → 推定K。
- 推定Kに対象画像content digest、view ID、EXIF適用後の入力寸法、pixel-center、source revision、weights SHA、
  seed、CPU / dtype、環境fingerprint、処理手法を記録する。返却size・K shape / finite / 正のfocal等を検証する。
- 元画像gridからdepth gridへのresize / crop / paddingを明示affineとして記録し、対応が確認できる場合だけ`K_depth = A K_image`を使う。
  grid対応がunknownなら推測して適用しない。非正方形・crop・pixel-centerのfixtureで検証する。
- K-only cacheと点群・meshは既存DerivedStoreのidentity / checksum / generation / exportを利用し、raw / JobResultへ後付けしない。
  depthに依存する点群・meshにはdepth digestも含める。条件差を同一cacheと扱わない。
- 相対depthはrelative / arbitraryのまま。K推定によってmetric scaleや完全な3D復元が得られたとは扱わない。
  Calibration失敗時に固定FOV・便宜的Kを作らない。

保存・表示の境界は[Results Viewer](results-viewer.md)、[Run Directory](run-directory-spec.md)、
[Environment](environment-strategy.md)に従う。

## Verification status

| 項目 | この調査完了時の状態 |
| --- | --- |
| 公式固定source / release / tag / asset metadata | VERIFIED。公式HTTPを読取確認 |
| Sourceと対象weightsのlicense区別・資料hash | VERIFIED。上記固定資料を読取確認 |
| Native前処理・K / grid・CPU依存・乱数 / load経路 | VERIFIED by source。実行検証と区別 |
| 実weights取得後のSHA-256 / size照合 | VERIFIED。公式asset116074121 bytes、実測SHAは下記 |
| 独立環境定義・解決版・source provenance / fingerprint | VERIFIED。独立Conda prefix・source VCS pin・worker実測fingerprint / lock保存 |
| 実CPU calibration・source / checkpoint互換・offline | VERIFIED。明示CPU float32、safe / strict load、seed0、Python外部socket遮断下で成功 |
| Derived保存・reuse・grid fixture・browser・raw不変 | 03.7で実施。最終Exit結果はPhase 03の追加stage受入記録を参照 |
| GPU、精度評価、全依存再配布、実bundle / demo配布 | 未実施。今回の調査で成功としない |

この調査担当は公式資料の読取と本書作成だけを実施した。checkpoint本体の取得、環境install、推論、外部送信、Git操作は行っていない。
後続の実測結果は既存の調査記録と区別して追記する。03.1〜03.6の受入やUniK3Dの個別判断を変更しない。

## Actual local preparation and CPU verification

公式release pinhole assetを取得し、116,074,121 bytes、SHA256
`86d6aeacd8bbd974c59ce39f61854e00d36911c732ad89be471476fd708722ac`を実測してtask定義に固定した。
publisher digestの不在を埋めて公開検証値が存在したとは扱わない。取得物はGit除外領域のみ。

独立mde-geocalib prefixはPython3.11.14、torch2.6.0+cpu / torchvision0.21.0+cpu、NumPy1.26.4、
Kornia0.8.0、matplotlib3.10.0、opencv-python4.10.0.84。公式sourceを--no-depsで固定導入し、
VCS direct_url commitを照合。初回headless OpenCV代替でnative CPUは成功したがpip metadataを満たさず、
この新環境だけofficial opencv-pythonへ変更後、pip checkはNo broken requirements found。
[環境定義](../models/geocalib/environment.yml) / [全Python固定版](../models/geocalib/requirements.lock)。
lockの別prefix再作成・他OS / GPU / 実配布は未検証。既存3モデル・UI環境は変更していない。

実weightsはtorch.load(weights_only=True)で安全読込でき、889 state項目がnative modelと完全一致、
strict loadで不足 / 余剰なし。無条件unsafe pickle fallbackを加えていない。
seed0 / 明示CPU / float32でKが得られ、256×256 sampleはfx=fy483.3321838、cx=cy128。
principal pointは上記画像中心仮定のままで、推定済みと表現しない。gravity / poseはexportしない。
共通補助workerがPython / torch / package / Conda fingerprintとtask wall timeを観測しderived manifestへ保存する。

実DA3の252×252 depth gridへは記録したOpenCV affineで写し、known / native / estimatedの由来を分ける。
点群・可視表面2.5D mesh・再読込・Resultsの検証は
[03.7受入記録](phases/phase-03.md#037-depth-only-3d-reconstruction--additional-stage)と
[幾何契約](depth-reconstruction-spec.md)を参照。過去03.1〜03.6とUniK3D調査・停止履歴は変更しない。
