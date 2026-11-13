# Repository rules for Codex

このプロジェクトは MDE / MGE の研究用実験基盤を段階的に整備する。
作業前に [README.md](README.md)、[PLANS.md](PLANS.md)、対象の
[phase 文書](docs/phases/) と変更対象の仕様を読む。

1. 作業は phase 単位で行う。ユーザーが指示していない phase に進まない。
   最新の指示（2026-11-11）によりPhase 03 — Model Plugin Architecture /
   Multi-model Support の実装・独立環境構築・検証・関連docs更新を承認。
   `codex/phase-03-implementation` をPhase 03完了まで継続使用し、PLANS.mdの03.1〜03.6を
   順番に実施する。先行段階の受入条件を満たした後に次へ進み、成功した段階ごとにcommit / 通常push。
   履歴: 「再開して」指示により、同じ実装ブランチで03.4からPhase 03の作業を再開した。
   履歴: 直前の指示では03.3の受入・commit / 通常push完了で停止していた。
   最新の2026-11-12再開指示によりPhase 03の実装・検証・関連docs更新を継続する。
   03.1〜03.5は受入・commit / 通常push済み。2026-11-13に03.6統合受入と全Exitを達成しPhase 03 COMPLETE。
   03.6のcommit / 通常pushで終了し、PR / main統合・Phase 04以降を自動開始しない。
   履歴: 直前の2026-11-12指示はハーネス・関連文書更新のみで、モデル作業は開始していなかった。
   今後のlicense判断は下記13の全Phase共通方針に従う。UniK3Dのlicense表記差異・checkpoint適用条件未確認は維持。
   2026-11-12の個別判断で固定Small checkpointの取得・非商用local CPU研究利用を承認。不確実性を記録して進める。
   UniK3Dの重みの再配布・公開同梱・商用利用は未承認。履歴: 一般的な再開指示だけでは個別保留を解除せず、用途・リスクを提示して判断を求めた。
   2026-11-12の追加指示で下記15のMoGeデモ構成を仕様として正式決定。今回の文書commit / 通常push後に元のPhase 03作業へ戻る。
   今回デモpackage生成・weights実同梱・実配布は行わず、実装状況・Phaseの受入条件を変更しない。
   独立adapter / fake / 幾何検証はlicense不確実性だけで止めないが、実作業は各回の承認範囲内で行う。
   重大な互換性問題等を推測で解消しない。03.4実モデルE2E未達のまま03.5へ進まない。
   履歴: 採用前調査時はlicense根拠不足により実装を含め一旦停止していた。
   PR作成・main反映・Phase 04以降は未承認。Phase 02DはPR経由でmain統合済み。
   開始時にlatest origin/mainを確認する。remote更新・競合・範囲外変更は上書きせず停止・報告。
   履歴: 2026-11-09はPhase 03調査・計画・設計と作業ブランチcommit / 通常pushのみ承認。
   当時未承認だったPhase 03実装・環境構築は2026-11-11の指示で承認された。
   force pushは禁止。Phase 01 / 01A / 01B / 02A / 02B / 02C / 02D / Phase 02はCOMPLETE。
   02Cは全Exit達成でCOMPLETE（fake / contract / browser / 実CPU native Points / offline）。
   Phase 03のMoGe / UniK3D / DA3以外のモデル、MLflow / Benchmark / Slurm / 高度なqueue・active recoveryは未承認。
   phase完了による次phaseの自動開始はしない。Gradioは独立application環境で既存Runner / Backendを利用し、
   全sessionで1つのLocalBackendを共有。Inference / Resultsの2タブを維持。
   CPUを明示選択し、CUDA要求時の自動fallbackを行わない。
   仮K・便宜的逆投影をmodel由来Pointsにしない。既存depth-only Run / CLI互換とraw不変を維持。
2. 大規模変更前に PLANS.md の目的・範囲・手順・検証・リスクを更新する。
   plan の更新や前 phase の完了は、次 phase を開始する許可を意味しない。
3. model-specific logic は `models/<model_name>/` に閉じ込める。
   core、UI、ExperimentRunner、ExecutionBackend にモデル名による分岐を追加しない。
4. model に Local / Slurm 等の execution-specific logic を書かない。
   すべての実行は ExecutionBackend を経由し、Local 実行を hard-code しない。
5. Model、Environment、Backend、Tracking、UI の責務を混ぜない。
   UI / Registry は model adapter や PyTorch を import せず、worker は UI に依存しない。
6. この repository は clean-start とし、再利用必須の既存 production implementation はない。
   過去のモデルコードは Phase 01 / 03 の必要時に参考として確認する。
   今後追加する interface / 保存形式の backward compatibility を考慮し、破壊的変更には移行手順と互換テストを用意する。
7. interface / schema / 状態遷移を変更したら、関連 docs と検証方法を同時更新する。
   optional field の追加を優先し、意味・単位・必須項目の変更は版を上げる。
8. 不明な研究室 Slurm / NFS / CUDA / module 設定を推測して実装しない。
   確認事項は [Slurm integration](docs/slurm-integration.md) に記録する。
9. 実装時は fake adapter / subprocess / backend を差し替えられる構造を優先する。
   GPU・クラスタなしの契約テストと、実機テストを分けて報告する。
10. 実装済み・設計のみ・未確認を区別する。測定していない数値や未実行のテストを
    成功と記載しない。調査できないファイルの存在や内容を推測しない。
11. Phase 01 は 01A の最小 E2E 成功を最優先にする。GPU lease、高度な retry / reconciliation、
    restart recovery、複雑な concurrency を 01A の完了条件に追加しない。
    基本的な cancel / timeout 等は 01B、より高度な堅牢化は Phase 06 以降へ段階分けする。

12. 新規作業は最新の `origin/main` と作業ツリーを確認し、変更前に作業内容に対応した
    作業ブランチ（例: `codex/<task-name>`）を作成する。同じ作業の継続は既存の作業ブランチで行う。
    `main` 上で直接編集・commitしない。既に未commit変更がある場合は保持したまま
    作業ブランチへ移し、破棄・reset・上書きをしない。
    承認範囲の作業と必要な検証を終えたら、作業ブランチへcommitし、同名のremoteブランチへ
    通常pushまで行う（2026-11-09ユーザー指示）。同じ作業の継続では既存ブランチを使う。
    `main` への反映はユーザーが承認した範囲・Exit条件を満たした後に行う。

## License review and decisions

13. 以下を今後の全Phase・全モデル・関連依存に適用する共通ルールとする。
    本プロジェクトは非商用の研究・検証を主用途とする実験基盤であり、ライセンス確認を維持しながら、
    研究開発を安全かつ合理的に継続する。確認作業そのものを目的化しない。

    1. 公式LICENSE、README、model card等を確認し、ソースコードと学習済みcheckpointの利用条件を分ける。
       対象component / variant、出典URL・revision、確認日、確認結果と不明点、予定する行為・用途、
       判断と根拠を関連docsに記録する。ソースの条件を根拠なくcheckpointへ適用しない。
    2. 明確な条件が確認でき、予定する利用がその範囲に収まる場合は、承認済み範囲の作業を通常どおり進める。
       作者への直接照会や追加のユーザー承認を定型的なgateにしない。
    3. 表記差異や情報不足は不確実性として記録し、影響を受けない実装・fakeテスト・幾何検証・調査を継続する。
       公開されていることだけで無制限の利用許諾を推定せず、不明確さを利用禁止の確定事実とも扱わない。
    4. 不明点が実checkpointの取得・利用など特定の行為に直接関係する場合は、想定用途・適用範囲・リスクと
       選択肢を整理し、必要に応じてユーザーへ判断を求める。必要な判断待ちは該当行為だけを保留し、
       無関係な作業は継続する。ユーザーの作業承認を権利者による利用許諾と同一視しない。
    5. 明確な禁止条件との衝突や重大な権利上のリスクがある場合は、該当作業だけを停止し、
       対象行為・条件の出典・衝突やリスクの内容を報告する。無関係な開発まで一律停止しない。
    6. 作者への直接問い合わせ・個別許諾の取得を全モデル共通の必須条件にしない。
       必要性が高い場合に理由・確認事項を提示して提案し、ユーザーの判断を仰ぐ。問い合わせは無断送信しない。
    7. 商用利用、モデル重みの再配布、公開パッケージへの同梱等はローカル研究利用と区別して判断する。
       用途・公開範囲が変わるときは該当する条件を再確認し、必要な帰属表示・通知等を記録・遵守する。

    この方針はPhase承認、責務分離、技術的受入条件、Git運用を変更せず、
    ライセンス以外の重大な安全性・互換性問題の停止条件を緩和しない。
    個別の保留・未達gateは、この共通方針だけで自動解除しない。

## Publication and distribution

14. 通常版として公開・配布するのは実験プラットフォーム本体と自作Adapterとし、外部モデルのソースコード・
    学習済みcheckpointは原則同梱・再配布しない。利用者が必要なモデル・重みを公式配布元から別途準備し、
    モデルごとのライセンス・利用条件に従う構成とする。環境定義・準備script・出典metadataの提供と、外部モデル実体の同梱を区別する。
    local研究用のGit除外領域への準備は配布とは別行為であり、既存の個別承認範囲を維持する。
    不明確さだけで開発全体を停止せず上記13に従って影響範囲を限定し、禁止条件・権利上の問題と未確認事項を記録する。
    詳細は[公開・配布仕様](docs/distribution-policy.md)。この方針更新自体は実公開・再配布や次Phase開始の承認ではない。

15. デモ版は**MoGe-2 ViT-S Normalの固定1種類のみを同梱する構成**とする。通常版とは分離したbuild profile / 外部recipeの
    データでモデル実装・checkpoint・独立依存環境と必要なLICENSE / NOTICE / 帰属表示を指定し、既存Plugin境界を維持する。
    core / UI / backendへデモ用のモデル名分岐を追加しない。対象の固定版・提供方法・未確認事項は
    [デモ版仕様](docs/distribution-policy.md#demo-edition--moge-2-vit-s-normal)に記録する。
    全依存の再配布条件、対象OS / archのpacking・可搬性、Conda prefixの丸コピーを検証済みと扱わない。
    過去にモデル同梱デモを決定・配布していなかった履歴を保持し、今回のMoGeデモ構成決定と区別する。
    UniK3D / DA3 / 他のMoGe variant・checkpointをこの決定だけで追加しない。実package生成・実同梱・配布は今回の文書更新には含めない。

詳細: [Architecture](docs/architecture.md) / [Model contracts](docs/model-adapter-spec.md) /
[Environment](docs/environment-strategy.md) / [Execution](docs/execution-backend-spec.md) /
[Run Directory](docs/run-directory-spec.md) / [MLflow](docs/mlflow-design.md)。
