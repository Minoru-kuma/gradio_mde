# Smoke test image

`sample.png` は NASA の Eileen Collins portrait（scikit-image の `astronaut`）を
256 × 256 RGB に縮小した画像。実推論経路と保存形式の smoke test 専用であり、研究データや
深度精度を評価する benchmark / GT として扱わない。

- 著作者 / 出典: NASA Great Images database。
- 権利: public domain / no known copyright restrictions。
  [scikit-image の出典・権利説明](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut)。
- 取得元: [固定 v0.19.3 の元画像](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/astronaut.png)。
- 変換: Pillow 11.1.0、RGB、LANCZOS、256 × 256、PNG。研究用途の精度保証はない。
- 元画像 SHA-256: `88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5`。
- sample SHA-256: `5e3293b048258e78256f5a4d452b1e61cfdf2b2f416ac322d7bb7e556e2d527e`（115,680 bytes）。
