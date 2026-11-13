# Phase 03 model capability and reproduction matrix

この表は固定代表variantの実装と実測を区別する。`supported` / `conditional` / `unsupported`は
manifest / runtimeの契約であり、`tested` / `untested`は実行証拠の有無である。
`conditional`の条件を満たしても、要求された出力が欠落すればworkerは失敗する。
モデルfamily全体・他checkpoint・未測定の精度へ結果を一般化しない。
受入証拠と状態の正本は[Phase 03](phases/phase-03.md#036-integration-acceptance-evidence--2026-11-13)。

## Representative variants and native conventions

寸法は検証sample（入力256×256）での実測であり、任意入力を常にその寸法へ固定する仕様ではない。

| 固定variant | CPU single-view | Depth kind / scale / unit | optional出力 | Camera / grid |
| --- | --- | --- | --- | --- |
| [MoGe-2 ViT-S Normal](../models/moge/README.md) | tested、float32、num_tokens=1200 | z_depth / metric / m、scale headの推定値 | Points / normals / intrinsics / native maskはconditional、実CPU保存・数値検証済み | OpenCV x right / y down / z forward、入力grid、native Pointsを保存。normalized Kは整数pixel中心へ変換 |
| [DA3-SMALL](../models/da3/README.md) | tested、float32、process_res=252 | z_depth / relative / arbitrary | 03.7でnative pixel K supported。Points / pose / confidence等はunsupported。点群はderivedで生成 | OpenCV、検証sampleのnative resize後252×252を維持。RGB identity対応を主張しない |
| [UniK3D Small](../models/unik3d/README.md) | tested、float32、resolution_level=0 | ray_distance / unknown / unknown、native値を維持 | native Points supported、実CPU保存・直接API照合済み。他optionalはunsupported | OpenCV、検証sampleのnative448×448処理から元256×256 gridへ戻す。norm(Points)=range、Points.zはrangeと同一視しない |

3モデルとも必須depthはsupported。MoGeのみmetric_depth supportedだが、GTによる精度保証ではない。
UniK3Dのmetric_depthはunsupportedで、単位確定・calibrationは未検証。負z / z=0のrange fixtureは
syntheticで検証し、実sampleで負zが観測されたとは主張しない。各adapterでshape / layout / K等を変換し、
core / UI / Runner / Backendへモデル名分岐を追加しない。仮K・便宜的逆投影でnative Pointsを作らない。

全3variantのrays / confidence / camera_pose / multi_viewはunsupported。共通multi-view契約は
fake 2-viewでtested（view ID、異なるshape、scene、未知extras、保存・collect・ZIP）。実モデルmulti-view、
pose tensor / typed rays exporter、multi-view入力UIは未実装で、実モデル能力をfakeから推定しない。
未対応要求は推論前に拒否し、不要求・unsupported出力の不在は正常とする。
DA3 manifestのconfidence / pose / multi-viewの「deferred to 03.4 / 03.5」は当時の検討時点の理由であり、これらは現状unsupportedのまま。native intrinsicsのみ03.7でsupportedへ更新した。
Phase 03.5の共通契約完成がDA3のoptional / multi-view実装済みを意味することはない。

## Independent environments and reproducibility

| Logical environment | 実測の独立Python / torch / NumPy | 共有する再現資料 | 再作成の検証範囲 |
| --- | --- | --- | --- |
| mde-moge | Python3.11.14 / torch2.6.0+cu124 / NumPy1.26.4 | [environment.yml](../models/moge/environment.yml)、READMEのsource・utils3d pin、Run fingerprint | Phase 01Bで別checkoutから再作成・CPU E2E。今回の3環境試験は既存準備済み環境を利用 |
| mde-da3 | Python3.11.14 / torch2.6.0+cpu / NumPy1.26.4 | [environment.yml](../models/da3/environment.yml)、[requirements.lock](../models/da3/requirements.lock)、source pin・Run fingerprint | 定義から独立prefixを新規構築してCPU E2E。lockからさらに別prefixを再作成する試験は未実施 |
| mde-unik3d | Python3.11.14 / torch2.6.0+cpu / NumPy2.2.2 | [environment.yml](../models/unik3d/environment.yml)、[requirements.lock](../models/unik3d/requirements.lock)、source pin・Run fingerprint | 定義から独立prefixを新規構築してCPU E2E。lockからさらに別prefixを再作成する試験は未実施 |

対象はLinux x86_64。application / Gradioは別のmde-ui環境で、controlはstdlibのみ。
UI / Registryはモデルadapter / torchをimportせず、選択workerだけがモデルをloadする。
全3環境の同じtorch版は今回の選定結果であり、同版共有・環境統合の要件ではない。
環境とcheckpointのlogical mapは[targets設定](gradio-inference.md#phase-033-model--variant-switching)で提供し、
ホストの絶対prefixを共有manifestへ埋め込まない。workerがsource revision / checkpoint SHAを照合する。

再作成はモデルREADMEの順に、独立Conda Python / bootstrap → 定義のpip依存 → 公式固定sourceを
`--no-deps`で導入 → checkpoint明示準備 → 明示CPU smokeとする。UniK3Dも最初に
`conda env create --prefix .local/envs/mde-unik3d -f models/unik3d/environment.yml`を実行する。
lockはPython distributionsの固定版記録であり、全OSのConda lock・wheel mirror・実配布用bundleではない。
上流全extrasの`pip check`、training / evaluation / exporterの依存充足、環境の可搬copyは未検証。
再作成時は利用条件とsource pinを再確認し、load時に必要なVCS provenanceも保持する。
推論・discoveryが自動install / downloadすることはない。詳細は[環境仕様](environment-strategy.md)。

## Untested and excluded conditions

- GPU成功、driver互換、CUDA性能・memory。MoGeのCUDA wheelでのCPU成功はGPU成功を意味しない。
  DA3 / UniK3DはCPU-only宣言。CUDA要求をCPUへfallbackしない。
- 他モデルvariant・checkpoint、MoGeの他token設定、DA3 process_res=504、UniK3D他resolution、非sample画像の精度。
- metric accuracy / model間scale比較、実non-pinhole camera入力、実multi-view UI・評価。
- DA3 / UniK3D lockの別prefix再作成、他OS / arch、全upstream extras・native evaluation extension。
- 過去01Bの特定Runはlocal directory不在。互換contract試験と、現存する旧Runの不変性確認を区別する。

## License and distribution boundary

[共通判断規則](../AGENTS.md#license-review-and-decisions)と[配布仕様](distribution-policy.md)を適用する。
通常版はプラットフォーム・自作Adapterのみで、外部source / checkpointは利用者が公式配布元から準備する。
MoGe / DA3の条件・出典は各README / manifest、UniK3Dは[調査履歴](unik3d-investigation.md)を参照。
UniK3DのNC / NC-SA表記差異とweights適用条件は未解決。個別承認は固定Smallの取得・非商用local CPU研究のみで、
権利者の許諾確定、再配布・公開同梱・商用・公開デモへ拡張しない。
MoGe-2 ViT-S Normalのみを含む別デモ版は仕様決定済みだが、package生成・weights同梱・実配布は行っていない。

## Additional 03.7 reconstruction

03.1〜03.6 COMPLETE履歴を保持。DA3 native Kと記録したpixel affineからderived点群・可視表面2.5D meshを生成する。
保存Kがない場合は、既知Kまたは独立GeoCalib taskの推定Kを使える。これはDA3 native Points / poseの能力追加ではない。
[03.7契約](depth-reconstruction-spec.md)、[GeoCalib条件・実測](geocalib-investigation.md)、
[独立環境定義](../models/geocalib/environment.yml)を参照。GeoCalibはsource / weights非同梱で、第四のdepth modelではない。
