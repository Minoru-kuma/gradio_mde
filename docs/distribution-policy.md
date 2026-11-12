# Publication and distribution policy

MGE Experiment Platformは、実験プラットフォーム本体と自作Adapterを公開・配布する構成とする。
外部モデルのソースコード・学習済みcheckpointは原則として同梱・再配布しない。
利用者は、必要なモデルと重みを各公式配布元から別途準備し、それぞれのライセンス・利用条件に従う。
この方針は全Phase・全モデルに適用し、開発上の判断は[AGENTS共通方針](../AGENTS.md#license-review-and-decisions)に従う。

## Distribution boundary

| 対象 | 方針 |
| --- | --- |
| プラットフォーム本体・自作Adapter | 公開・配布の対象。モデル固有処理はAdapterに閉じ込め、外部モデル実体とは分離する |
| 自作manifest・環境定義・準備script・利用手順 | 公式URL、固定revision、digest、出典・条件への参照を含めて提供できる。外部モデル実体を同梱することとは区別する |
| 外部モデルのソースコード・学習済みcheckpoint | 原則同梱・再配布しない。利用者が必要なものを公式配布元から準備する |
| 研究用に取得したsource、weights、cache、モデル環境 | local準備と配布は別行為。Git除外領域や利用者設定先に置き、取得済み内容を配布物へ混ぜない |
| その他の第三者依存・frontend assets | 各条件と必要な帰属表示・通知を個別に扱う。既存Three.js等の扱いを外部モデルの非同梱方針だけで変更しない |

自作Adapterが外部モデルのAPIを呼び出す構成とし、外部モデルの実装全体をプラットフォームへ取り込まない。
参考にした第三者コードを公開物へ取り込む場合は、自作という名称だけで処理せず、出典と適用条件を別に確認する。
原則と異なる同梱・再配布を検討する場合も、各配布元の条件と対象行為を別に判断し、この方針だけで承認済みとはしない。

## User preparation and runtime

利用者は選択したモデルの公式配布元・固定版・条件を確認し、pluginの手順に従って独立環境とcheckpointを準備する。
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

今回の更新は配布境界と準備構成の文書化であり、Phase承認範囲・実装状況・受入条件を変更しない。
プラットフォーム本体・自作Adapterの具体的な配布ライセンス選定、公開packageの作成、
実配布物の同梱内容の検証、公開・配布作業は今回実施していない。
これらを実施するときは、対象artifactの内容と必要な帰属表示・通知を確認する。
既存のRun export形式・raw不変契約は変更しない。
