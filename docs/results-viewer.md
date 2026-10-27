# Phase 02C Results viewer

02Cの共通reader / numeric処理は `mde.results.ResultsService`、派生保存は同moduleの
`DerivedStore`、描画は `viewer_assets/viewer.js`。UI環境のみNumPy 2.5.4 / Pillow 12.3.0を利用する。
Registry / Runner / Backend / worker / adapterの契約とCLIのdepth-only defaultは維持する。
検証証拠は [02C](phases/phase-02/phase-02c.md)。履歴・再生成・削除等の02D管理操作は提供しない。

## Library selection and pins

| 候補 | 調査内容・判断 |
| --- | --- |
| Gradio 6.30.0 Model3D | installed component仕様を確認。fileからsolid / point_cloud / wireframeと初期cameraを設定できるが、今回必要なRGB / Depth / native Normal色の動的buffer切替・モード間camera保持には独自処理が必要 |
| Plotly Mesh3d | [公式trace schema](https://plotly.com/python/reference/mesh3d/)を確認。vertex / face colorはあるがUV texture mapを直接扱う契約がなく、RGB textured表示に追加実装が必要 |
| Three.js **r180 / 0.180.0** | 採用。[MeshBasicMaterial](https://threejs.org/docs/pages/MeshBasicMaterial.html)のUV texture / wireframe、[OrbitControls](https://threejs.org/docs/pages/OrbitControls)の回転・zoom・pan、共有cameraを小fixtureとbrowserで検証。MIT、Python生成とbrowser描画を分離できる |

他候補はAPI調査、Three.jsは固定配布物による実動作検証。latest追従はしない。
公式r180のmodule / core / OrbitControls / LICENSEをrepositoryに同梱する。
取得元・SHA-256・唯一の相対import変更は [vendor record](../src/mde/viewer_assets/vendor/README.md)。
Gradioのstatic path公開はvendor directoryだけ。Run Root全体は公開しない。
`gr.HTML`内の初期化はasync IIFE、`server_functions`の固定版経路へ1つのrequest objectを渡す。
表示要求はqueueを経由せず、server threadで保存terminal collectを検証してからpayloadを返す。
request serialを使い、古いmode / Runの応答は表示しない。camera / GPU resourcesはbrowser session別。

## Modes and numeric meaning

- **Depth**: rawと保存effective maskを読み、finite-positiveのmin / maxを表示範囲とする。
  blue→cyan→yellowの明示式、線形min/max normalization。定数depthは0.5、invalidは透明、
  all-invalidは統計unavailableとして純粋数値関数で安全に扱う。正式Runのall-invalidは既存workerが拒否する。
- **RawDepth**: shape / dtype / min / max / valid count / fraction / total、depth kind / unit / scale / frame。
  元のNPY bytesをdownloadできる。表示のnormalizationでrawを書き換えない。
- **Point Cloud**: 保存model pointsを優先。RGB / Depth / Normal色をbrowser内bufferで切替。
  RGBは `image_to_output={type: identity, pixel_center: integer}` と同一original/output sizeが
  記録され、実input PNGのgridが一致する場合のみ。未知resize / cropを推測しない。
  native normalsがなければNormal色を無効化し理由を表示。orientationは保存metadataを表示する。
- **Mesh**: 初回要求時だけgrid triangulationを実行し永続保存。RGB textured / Geometry /
  Wireframeを同じgeometryで切替。textureは元RGBと画素中心UV、RGB対応不能なら無効化し理由を表示。

Point CloudのRGB / colormap / Normal色は表示sRGB値をrendererのlinear bufferへ変換する。
textureはsRGB。保存座標はOpenCV x right / y down / z forward、unit / scaleは保持する。
camera upを-Y、初期cameraをbounds中心の-Z側に置く。座標の軸変換・poseの補完は行わない。
同じRunのPoint Cloud↔Meshと色/mesh表示切替はcamera位置・targetを保持する。
Depth / RawDepthを経由しても保持するが、別Run・browser再読込ではboundsからreset。
Reset cameraボタンで明示的に戻せる。左drag回転、wheel zoom、右drag pan。

保存pointsがなくても、明示pinhole camera / integer pixel K / output grid / 標準frameと
既知depth kindがあれば共通逆投影を行い、**derived points**として別manifestへ保存する。
z_depthは `K^-1[x,y,1] * depth`、ray_distanceはrayをunit length化してdepthを掛ける。
その情報もなければ3D unavailable。仮K・scale・pose・normalを補わない。
旧depth-only RunはDepth / RawDepthを使える。

## Mesh and persistence contract

algorithm `grid-triangulation` version `1`。LOD / downsamplingなし。
すべての頂点がvalidなgrid cellのみ2三角形にする。各faceのすべての辺について:

- depth差 ≤ **0.05 × face内最小depth**（relative、元depth unit）
- Euclidean edge length ≤ **0.1 × face内最小depth**（relative、保存points unit）
- cross productの長さ（double area）> **1e-12 × 最小depth²**（保存unit²）

NaN / mask境界・深度不連続・長すぎる辺・退化faceを除外する。native pointsをdepthから置換しない。
閾値は安全な表示用heuristicであり、精度や全surfaceの復元を保証する値ではない。
面が残らないRunは0 facesとして表示し、Point Cloudで保存点を確認できる。

```text
derived/<sha256 canonical identity>/<generation UUID hex>/
  manifest.json
  geometry.npz
derived/<key>/.partial-<generation>/   # interrupted diagnostic staging, reuseしない
```

manifest schema `1.0`、origin=derived。identityにはalgorithm / version / 展開parameters、
Run / attempt / view、全raw artifact refs・入力RGB digest・JobSpec digest・意味metadata、
frame / unit / scale、NumPy版、LODなし・texture条件を含む。keyはsort_keys / compact JSONのSHA-256。
geometry.npzはpoints float32 `[H,W,3]`、meshではfaces uint32 `[F,3]`を追加する。
manifestはgeneration ID・UTC時刻・array dtype/shape・出力relative path/size/digestも持つ。
texture PNGとUVは保存RGB/gridから生成する表示payloadであり、永続cache本体はNPZ geometry。
RGB digest・grid・texture条件をidentityに含め、raw RGBを書き換えない。
model由来raw / WorkerResult / JobResultへderived refを後付けしない。

同一条件はprocess内の共通lockで1回生成。stagingへ数値配列を書きfsync、manifestを最後に書き、
directoryを同一filesystem内でatomic renameする。complete generationだけをreuseし、毎回
identity / path / digest / dtype / shape / index boundsを検証する。途中stagingは保持する。
壊れたcomplete cacheは明示エラー、上書き・自動削除をしない。修復・明示再生成UIは02Dの未承認範囲。
バックプロジェクションはalgorithm `pinhole-backprojection` version `1`、同じ保存/検証方式。
単一application processを対象とし、multi-process調停・電源断後のdurabilityは保証しない。

## Offline operation and limits

[Gradio起動手順](gradio-inference.md)の環境・weightsを事前準備する。
追加のJS download / npm installは不要。three moduleは同梱配信、texture / arraysはローカルpayload。
保存Runは `--read-only` 起動でモデル環境・weightsなしにRun IDだけで開ける。
Load actionはLoadingからLoaded / Could not loadへ更新し、空欄はRun ID入力を案内する。

viewer上限は**262,144 output pixels（例512×512）**。超過は理由付きで拒否しrawを保持する。
全有効なら同数のpoints、最大522,242 faces。自動LODは導入していない。
browser memoryに余裕を持たせるための運用上限であり、一般的なWebGL最大容量ではない。
payloadはbase64 buffers、同時に1つの3D objectを保持、切替・component削除時にgeometry /
material / texture / controlsをdisposeする。WebGL非対応時は初期化失敗理由を表示する。

検証OS / browser / 容量実測とGPU未検証の区別は02Cの証拠を参照する。
