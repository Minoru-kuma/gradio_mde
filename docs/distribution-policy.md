# Publication and distribution policy

MGE Experiment Platformの通常版は、実験プラットフォーム本体と自作Adapterを公開・配布する構成とする。
通常版には外部モデルのソースコード・学習済みcheckpointを原則同梱・再配布せず、
利用者が必要なモデルと重みを各公式配布元から別途準備し、それぞれのライセンス・利用条件に従う。
2026-11-12の追加決定により、デモ版は下記の**MoGe-2 ViT-S Normalの固定1種類のみを同梱する構成**とする。
これは通常版の非同梱原則に対する明示的なデモ構成の例外であり、他モデル・weightsへ自動的に広げない。
この方針は全Phase・全モデルに適用し、開発上の判断は[AGENTS共通方針](../AGENTS.md#license-review-and-decisions)に従う。

## Distribution boundary

| 対象 | 通常版の方針 |
| --- | --- |
| プラットフォーム本体・自作Adapter | 公開・配布の対象。モデル固有処理はAdapterに閉じ込め、外部モデル実体とは分離する |
| 自作manifest・環境定義・準備script・利用手順 | 公式URL、固定revision、digest、出典・条件への参照を含めて提供できる。外部モデル実体を同梱することとは区別する |
| 外部モデルのソースコード・学習済みcheckpoint | 原則同梱・再配布しない。利用者が必要なものを公式配布元から準備する |
| 研究用に取得したsource、weights、cache、モデル環境 | local準備と配布は別行為。Git除外領域や利用者設定先に置き、取得済み内容を配布物へ混ぜない |
| その他の第三者依存・frontend assets | 各条件と必要な帰属表示・通知を個別に扱う。既存Three.js等の扱いを外部モデルの非同梱方針だけで変更しない |

自作Adapterが外部モデルのAPIを呼び出す構成とし、外部モデルの実装をプラットフォームcoreへ取り込まない。
参考にした第三者コードを公開物へ取り込む場合は、自作という名称だけで処理せず、出典と適用条件を別に確認する。
下記のMoGeデモ以外に原則と異なる同梱・再配布を検討する場合は、各配布元の条件と対象行為を別に判断する。

## Demo edition — MoGe-2 ViT-S Normal

### Fixed contents

デモ版には通常版の本体・自作Adapterに加え、固定MoGe実装・checkpointと必要な依存環境を提供する構成とする。
同梱する選択対象model / variant / checkpointは次の1種類に限定する。既存の[MoGe README](../models/moge/README.md)と
[manifest](../models/moge/manifest.json)を固定版の根拠とする。

| 項目 | 固定対象 / 現在の記録 |
| --- | --- |
| Model / variant | `moge` / `moge-2-vits-normal`、MoGe-2 ViT-S Normal、model version 2.0.0 |
| MoGe実装 | [source revision `07444410f1e33f402353b99d6ccd26bd31e469e8`](https://github.com/microsoft/MoGe/tree/07444410f1e33f402353b99d6ccd26bd31e469e8) |
| Checkpoint | [Ruicheng/moge-2-vits-normal](https://huggingface.co/Ruicheng/moge-2-vits-normal/tree/26b477f41595707c5db6770294c0d1721e8ed4ed)、revision `26b477f41595707c5db6770294c0d1721e8ed4ed`、`model.pt` |
| Checkpoint identity | 140,550,416 bytes、SHA-256 `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc` |
| Source条件の確認 | 固定LICENSEはMicrosoftのMIT文面とApache-2.0全文を含む。DINOv2由来headerはMeta / Apache-2.0。対象componentのLICENSE / NOTICE・帰属表示を個別に保持する |
| Weights条件の確認 | 固定model cardとHub metadataに`license: mit`。ソース条件と混同せず、checkpointの配布元・固定版・条件の根拠を残す |
| 依存環境の参照 | [environment.yml](../models/moge/environment.yml)とMoGe READMEの環境・再作成記録。Linuxでの既存CPU実行の証拠であり、任意OS向けデモbundleの検証結果ではない |

MoGe-3、他のMoGe variant / checkpoint、UniK3D、DA3の実装・weightsをデモへ追加しない。
upstream packageが他variantのAPIを含むことと、別model / weightsをデモの選択対象・同梱対象へ追加することを区別する。

### Provisioning and build boundary

通常版と分離したbuild profile / 外部recipeのデータに、同梱model / variantのallowlist、source revision、
checkpoint identity、依存版、対象OS / arch、local配置と帰属表示一覧を記述する設計とする。
モデル名を条件にした特別処理をcore / UI / backendへ追加せず、既存Registry・target設定・ModelAdapter・ExecutionBackendを利用する。

- MoGe実装は固定公式sourceからbuild時に準備し、デモ用の独立モデル環境へ組み込む。core / UIにupstream推論処理を取り込まない。
- checkpointは固定公式配布元から準備し、size / SHA-256を照合した1ファイルをデモresourceとして収める。実行先の配置はtarget設定で解決する。
- 依存環境は本体application環境とMoGe worker環境を分離したまま、対象platform向けのrecipeと必要なruntimeを提供する構成とする。
  具体的なpacking媒体・環境bundle形式・CPU / CUDA buildと対象OS / archは、配布条件と実機検証に基づいて決める。
- Registryの一覧表示・推論submit時に自動installせず、推論Job内で最新版をdownloadしない。デモでも準備済みの固定実装・重みを使う。

既存Conda prefixの丸コピーがportableであるとは扱わない。現在の`mde-moge`はtorch 2.6.0+cu124等でCPU実行を検証した環境であり、
その実績だけでCUDA依存一式の再配布可否、GPU対応、他OSでの起動を確認済みとはしない。
現MoGeAdapterはinstalled `direct_url.json.vcs_info.commit_id`を固定source revisionと照合する。
wheel / archive等を用いる場合も、この検査を維持できるsource provenanceの提供方法と読戻しを検証する必要がある。
単にlocal wheelをinstallすれば同じVCS情報が残るとは扱わず、source確認を削除・緩和する前提で配布方式を決めない。
CPUを明示選択し、CUDA要求時に自動fallbackしない既存動作も維持する。
このbuild profile / recipeは設計方針であり、今回ファイル作成・packaging機構の実装を行っていない。

### Redistribution, attribution and open items

デモの構成決定と、配布物に含める各componentの条件確認・対応・実配布の検証を区別する。
MoGe source / checkpointの既存license情報だけで、依存環境全体の再配布条件が確認済みとは扱わない。

公式資料を2026-11-12にread-only確認した範囲は次のとおり。新たなweights取得・実同梱・package生成の記録ではない。

| 公式の固定資料 | 確認結果 |
| --- | --- |
| [MoGe LICENSE](https://raw.githubusercontent.com/microsoft/MoGe/07444410f1e33f402353b99d6ccd26bd31e469e8/LICENSE) | Microsoft MIT文面とApache-2.0全文を含む |
| [DINOv2由来attention header](https://raw.githubusercontent.com/microsoft/MoGe/07444410f1e33f402353b99d6ccd26bd31e469e8/moge/model/dinov2/layers/attention.py) | MetaのcopyrightとApache-2.0の指定 |
| [固定model card](https://huggingface.co/Ruicheng/moge-2-vits-normal/raw/26b477f41595707c5db6770294c0d1721e8ed4ed/README.md)、[固定Hub metadata](https://huggingface.co/api/models/Ruicheng/moge-2-vits-normal/revision/26b477f41595707c5db6770294c0d1721e8ed4ed) | `license: mit`、revision一致。file一覧に専用LICENSE / NOTICEは見られなかった。本文の専用file不在を禁止条件とは扱わない |
| [utils3d LICENSE](https://raw.githubusercontent.com/EasternJournalist/utils3d/3fab839f0be9931dac7c8488eb0e1600c236e183/LICENSE) | MIT、Copyright (c) 2022 EasternJournalist |

取得資料のsize / SHA-256と確認結果は`.local/validation/demo-policy-license-review.json`へ記録した。

- MoGe実装・weightsの公式出典、固定版・digest、適用LICENSE・MITの著作権表示と許諾表示、必要な帰属表示を配布物に対応付けて保持する。
- DINOv2由来のApache-2.0部分を含め、実際に収めるcomponentのLICENSE全文、存在するNOTICE、必要な変更告知・copyright等の帰属情報を確認して保持する。
  商標利用や配布元による推奨・endorsementまで追加許諾されたとは扱わない。
- `utils3d`、PyTorch / torchvision、CPU / CUDA runtime、その他Python依存、application / frontend assets等について、
  実際のbundle内容を基に全依存の再配布条件・帰属表示・NOTICEを確認する。未確認のcomponentは記録し、問題があれば該当同梱を見直す。
- 対象OS / archでの起動、prefix / resource配置の可搬性、native library、offline動作、size / digestと同梱物の一致は未検証の配布作業項目として残す。

全依存の再配布可否・NOTICEの網羅確認、具体的なpacking方式とtarget OS、実bundleの構築・起動検証は今回未実施。
本体・自作Adapterの具体的な配布ライセンス選定も、このMoGe構成決定だけで完了したとは扱わない。
不明確さだけで開発全体を停止せず、明確な禁止との衝突・権利リスクを影響する同梱や配布行為に限定して判断する。

## User preparation and runtime

通常版の利用者は選択したモデルの公式配布元・固定版・条件を確認し、pluginの手順に従って独立環境とcheckpointを準備する。
自作の明示的な準備scriptが公式配布元から取得する方式も、事前準備として扱える。
Registryの一覧表示や推論submitを契機に自動installせず、推論Jobで最新版をdownloadしない既存契約を維持する。
準備済みsource / checkpointのidentity・digestを記録し、Adapterは設定されたlocal配置を利用する。
環境と配置の詳細は[Environment strategy](environment-strategy.md)、[target configuration](target-configuration.md)、
各モデルのREADMEを参照する。

## License decisions and unverified items

ソースとcheckpointの条件を分けて各公式配布元のLICENSE / README / model card等を確認し、
出典・確認日・確認結果・不明点・予定用途・判断を関連docsへ記録する。
外部モデルを同梱しない構成でも、利用者による取得・使用には各モデルの利用条件が関係する。
公開されていることを無制限の許諾とみなさず、不明確さを利用禁止の確定事実とも扱わない。
情報不足や表記差異だけで開発全体を止めず、影響を受けない実装・テスト・調査を継続する。
不明点が特定の取得・利用・配布に直接影響する場合は、その用途とリスクを整理して必要に応じユーザー判断を求める。
明確な禁止との衝突・重大な権利リスクは該当作業を停止・報告する。作者への照会を全モデル共通の必須条件にはしない。

UniK3Dの調査事実・停止判断の履歴・固定Smallの非商用local CPU研究利用に関する個別判断は
[調査記録](unik3d-investigation.md)を維持する。その個別判断はcheckpointの同梱・再配布や商用利用の承認ではない。

## Implementation and release status

履歴: 最初の通常版公開・配布方針では、外部モデル非同梱を原則とし、モデル同梱デモの構成決定・実配布は行っていなかった。
今回の追加指示でMoGe-2 ViT-S Normal固定1種類を同梱するデモ構成を正式決定した。
この変更はMoGeデモに限る。従来のUniK3D local研究判断や、他モデルの同梱・再配布を認めるものではない。

今回の更新は仕様書のみであり、Phase承認範囲・実装状況・受入条件を変更しない。
プラットフォーム本体・自作Adapterの具体的な配布ライセンス選定、公開packageの作成、
weightsの実同梱、実配布物の同梱内容の検証、公開・配布作業は今回実施していない。
これらを実施するときは、対象artifactの内容と必要な帰属表示・通知を確認する。
既存のRun export形式・raw不変契約は変更しない。文書のcommit / 通常push完了後に元のPhase 03作業へ戻る。

## Phase 03.7 camera calibration boundary

GeoCalib is an optional locally prepared calibration dependency for depth-only reconstruction. Its upstream
source, pinhole weights and independent environment are not bundled in either the normal edition or the
MoGe-2 ViT-S Normal demo edition. The platform may provide its self-authored task adapter, fixed-version
metadata, environment definition and explicit preparation instructions. Source Apache-2.0 and weights CC BY4.0
were checked separately; sources, attribution and actual-use evidence are in the
[GeoCalib investigation](geocalib-investigation.md). This addition does not add a demo model or authorize actual distribution.
