# Repository rules for Codex

このプロジェクトは MDE / MGE の研究用実験基盤を段階的に整備する。
作業前に [README.md](README.md)、[PLANS.md](PLANS.md)、対象の
[phase 文書](docs/phases/) と変更対象の仕様を読む。

1. 作業は phase 単位で行う。ユーザーが指示していない phase に進まない。
   現在の承認範囲は Phase 00 の調査・文書のみ。production code、環境作成、
   package install、モデル推論、Slurm job、MLflow server は今回の範囲外。
2. 大規模変更前に PLANS.md の目的・範囲・手順・検証・リスクを更新する。
   plan の更新や前 phase の完了は、次 phase を開始する許可を意味しない。
3. model-specific logic は `models/<model_name>/` に閉じ込める。
   core、UI、ExperimentRunner、ExecutionBackend にモデル名による分岐を追加しない。
4. model に Local / Slurm 等の execution-specific logic を書かない。
   すべての実行は ExecutionBackend を経由し、Local 実行を hard-code しない。
5. Model、Environment、Backend、Tracking、UI の責務を混ぜない。
   UI / Registry は model adapter や PyTorch を import せず、worker は UI に依存しない。
6. 既存コードが取得できたら、削除・全面置換の前に実行方法と再利用箇所を確認する。
   backward compatibility を考慮し、破壊的変更には移行手順と互換テストを用意する。
7. interface / schema / 状態遷移を変更したら、関連 docs と検証方法を同時更新する。
   optional field の追加を優先し、意味・単位・必須項目の変更は版を上げる。
8. 不明な研究室 Slurm / NFS / CUDA / module 設定を推測して実装しない。
   確認事項は [Slurm integration](docs/slurm-integration.md) に記録する。
9. 実装時は fake adapter / subprocess / backend を差し替えられる構造を優先する。
   GPU・クラスタなしの契約テストと、実機テストを分けて報告する。
10. 実装済み・設計のみ・未確認を区別する。測定していない数値や未実行のテストを
    成功と記載しない。調査できないファイルの存在や内容を推測しない。

詳細: [Architecture](docs/architecture.md) / [Model contracts](docs/model-adapter-spec.md) /
[Environment](docs/environment-strategy.md) / [Execution](docs/execution-backend-spec.md) /
[Run Directory](docs/run-directory-spec.md) / [MLflow](docs/mlflow-design.md)。
