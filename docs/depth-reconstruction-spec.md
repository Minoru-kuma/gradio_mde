# 03.7 Depth-only 3D Reconstruction

03.1〜03.6 COMPLETEの履歴を保持した追加stage。受入状態は[Phase 03](phases/phase-03.md#037-depth-only-3d-reconstruction--additional-stage)。
単眼の保存depthからcamera-spaceのderived点群と可視表面2.5D meshを生成する。
相対depthはrelative / arbitraryのままであり、絶対pose・複数視点融合・閉曲面補完・GT精度保証を含めない。

## Camera choice and provenance

保存native Pointsがあれば従来どおりそのrawを使う。depthから点群を生成する場合のKの優先順位は:

1. 利用者が明示した既知K（`known_camera`）。
2. 正式artifactとして保存したモデルnative intrinsics。
3. 設定済みのcamera estimatorによる自動推定K。保存済みcalibrationがあれば再利用する。

native Kを得られるかどうかと、当該Runでその出力を要求・保存したかを区別する。
DA3-SMALLでnative Kを使うには`depth intrinsics`を要求する。既存CLIの既定はdepth-onlyのまま。
Kが欠落した旧Runでも、定義済みinput→depth写像があり、明示設定したestimatorが準備済みなら推定できる。
unknown mapping・不正K・未準備・推定失敗は理由付きエラー。固定FOV・仮Kで代用せず、Depth / RawDepthは利用できる。

Kはfiniteで正のfx/fyを持つpinhole `[3,3]`、OpenCV x right / y down / z forward。
最下行は厳密に `[0,0,1]`、K[1,0]は厳密に0とする。微小な非ゼロ成分も拒否し、黙って丸めない。
skew K[0,1]と画像外principal pointは許容する。
float32化した後も再検証し、overflow / focal underflowを拒否する。source / depth gridと所属空間を記録する。
`known_camera`は`K`、`grid: [H,W]`、`grid_space: source | depth`、`pixel_center: integer | half`、
`camera_model: pinhole`、`camera_frame: opencv_x_right_y_down_z_forward`を指定する。
古い呼出でgrid_space省略時は寸法から一意に判断できる場合だけ受理する。同寸法の非identity変換は曖昧として拒否。

half-center Kはprincipal pointを-0.5ずらしてinteger-centerへ変換する。
source gridのKは記録済みaffine `A`で `K_depth = A K_source_integer`。resize / crop / paddingを推測しない。
既知Kをdepth gridとして与える場合はinput mapping不要。native Kは保存artifactのoutput grid上で使う。
DA3の二段OpenCV resizeでは `sx=Wout/Win, sy=Hout/Hin`、translationは`0.5*s-0.5`。
非正方形・crop / 同寸法translation・半画素差をfixtureで検証する。

## Native DA3-SMALL K

[固定plugin](../models/da3/README.md)のCameraDecと固定SMALL weightsでKを実CPU確認した。
`pose_encoding_to_extri_intri`はdepth gridのpixel Kを返し、公式GLB exporterは整数meshgridで逆投影する。
従ってnative Kに追加の-0.5を入れない。保存はfloat32 `[3,3]`、singleton view除去のみ。
256×256 sampleはdepth252×252、Kはfx337.0307312 / fy431.7342224 / cx126 / cy126。
160×320 sampleはdepth126×252、cx126 / cy63。これらの寸法はsampleでの実測。
CameraDec内部でextrinsicsも計算されるが、03.7はKだけをexportし、外部pose能力を追加しない。

## Automatic camera estimator

[GeoCalib調査](geocalib-investigation.md)の公式fixed source / pinhole weightsを独立環境で明示準備する。
provider固有APIは[models/geocalib](../models/geocalib/README.md)内に閉じ込め、core / UI / backendでモデル名分岐をしない。
GeoCalibのKは元入力RGB gridへ復元済み。principal pointは画像中心の仮定であり、全K要素を推定するわけではない。
seed=0、明示CPU / float32、safe weights loadと全state strict検証を使用し、gravity / poseはexportしない。
通常版・MoGeデモ版にモデル実装・weights・環境を同梱しない。

`CameraEstimator`はtrusted server-side task定義とtarget設定を読み、logical環境を既存WorkerManagerへ登録する。
共通`ExecutionBackend.execute_task`はoptional method（未対応backendはUnsupportedOperation）。LocalBackendは推論と同じ
admissionを共有し、新規同時実行をBusyで拒否する。冪等な既存submitのhandle返却は維持する。
独立Conda workerのJSON schema1.0でentrypointをimportし、画像SHAを前後照合して結果を返す。
成功・失敗・timeoutでprocess group cleanupを確認する。cleanup未確認ならbusyを保持する。
queue / active recovery / 自動download / installはない。calibrationはbounded synchronous taskで、個別UI cancelは提供しない。

## Derived storage and Results

既存[DerivedStore](results-viewer.md#mesh-and-persistence-contract)を使用する。
algorithm `single-image-calibration` version1はfloat32 intrinsics `[3,3]`のみをNPZへ保存する。
identityはRun / attempt / view、input RGBのdigest、job SHA、元grid、providerの固定source / checkpoint / environment定義digest・seedを含む。
optional `provenance`に実workerのPython / torch / prefix・package fingerprint・task wall timeを保存する。
cacheは記録されたprovider / 設定に対する保存結果として再利用し、実installed環境の再観測は再実行時に行う。
環境定義digestだけで現在の全package状態が再観測済みとは主張しない。

ray生成・range正規化はfloat64で行い、小さい有限focalでもfloat32 norm overflowで原点へ潰さない。
最終保存はfloat32で、valid depth画素の点がfiniteで表現できない場合は生成を拒否する。
`pinhole-backprojection` version2でz-depthは`K^-1[x,y,1] * depth`、rangeはunit rayへdepthを掛ける。
K由来（known / model native / estimated）、source K・grid_space・変換行列・depth grid K、provider / calibration artifact refを
点群・mesh identityへ含める。元のframe / units / scaleを維持し、finite-positive depthと既存maskでinvalidを除く。
深度由来meshは`grid-triangulation` version2で、version1と同じ相対閾値によりinvalid・深度不連続・長い辺・退化faceを除く。閉曲面を作る処理ではない。

保存前とpoint / mesh cache再読込時、有効画素でZとz-depthをrtol=1e-6 / atol=0で検証する。
小さい深度の不一致を絶対許容差で隠さない。rangeはZと同一視しない。
旧version1のdepth由来point / meshは修正済みとして再利用せず、新version2を別keyへ生成する。
旧generation / historyを削除・上書きしない。native Points由来meshはversion1のまま。
K-only calibration cacheはversion1を維持し、読込時にも厳密なpinhole検証を適用して不正Kを拒否する。

保存先・atomic publication・generation history / current pointer・破損拒否・明示再生成・exportは既存機構を使う。
K cacheも同じ`derived/<key>/<generation>/geometry.npz` / manifest。raw / WorkerResult / JobResultにrefを追加しない。
モデル環境なしの再読込は、正式raw collect検証後に保存calibration / 点群 / meshのdigestを検証して再利用する。
推定Kが保存済みならestimator target・weightsなしでも再表示できる。unknown / corrupt cacheを黙って補修しない。

ResultsのPoint Cloud / Meshに既知K入力を追加し、sourceかdepthかを明示選択する。入力はbrowser別でRun変更時に無効化する。
既知Kはrawや全sessionのdefaultへ書き込まない。管理のRegenerate Meshは保存native / 設定済み自動cameraのdefault経路を使う。
任意既知Kでの明示再生成は`ResultsService.view(..., known_camera=..., regenerate=True)`を使う。
既存4表示・camera操作・derived/rawラベルを維持する。RGB / textureは従来の厳密identity grid条件のみで、DA3 resizeでは無効。

## Validation and limits

数値fixture、失敗 / 破損 / priority / export / raw不変、補助workerの排他・timeout・再利用を契約試験で確認する。
実DA3 CPUのnative Kとdepth-only + GeoCalibを、点群・mesh・保存・browser・モデルなし再読込まで検証する。
実測Run ID・最終回帰・未検証条件はPhase 03の03.7受入記録に記載する。GPU・他OS / arch・distorted camera・別variant・
精度 / 複数視点 / lock別prefix再作成は未検証。既存viewerの262,144 output pixels上限を維持する。

## Deferred P3 — Backend configuration coupling

最終レビューでCameraEstimatorがbackend.manager.resolver.profilesを直接参照・変更することを確認した。
公開execute_taskを実装してもmanagerを持たないBackendでは初期化がAttributeErrorになる。
現在のLocal経路を阻害しない設計改善事項として保持する。将来、環境profile登録を起動時の構成処理 / Environment層へ移し、
CameraEstimatorを公開Backend契約だけに依存させる。今回のP2修正にはBackend再設計・Slurm実装を含めない。
