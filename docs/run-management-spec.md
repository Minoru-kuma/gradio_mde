# Run Management / Derived Storage specification

Status: **設計のみ / NOT_STARTED**。02Cの最小derived生成・保存・読込と02Dの管理service計画。
現在のsrc/mdeには以下のservice / sidecar / derived manifestは存在しない。
具体schema / API / path名は実装承認後に確定。関連:
[Phase 02](phases/phase-02.md)、[Run Directory](run-directory-spec.md)、[Architecture](architecture.md)。

## Responsibility and service boundary

UIはRun IDと操作意図を共通Run Management Serviceへ渡す。serviceはRunStore / artifact validatorと
連携し、model adapter / torch / Conda / Backend起動に依存しない。
推論条件変更はExperimentRunnerの新規submit、管理操作は保存Runへの処理として分ける。
以下は概念APIであり既存実装のsignatureではない。

| 操作 | 計画上の契約 | 導入 |
| --- | --- | --- |
| load / detail | finalized selected attemptを検証、Run IDからmodel環境なしで読む | 02C |
| get_or_generate_derived | 入力検証→条件key検索→reuseまたは遅延生成→atomic publish | 02C |
| list / user metadata update | 保存履歴、表示名 / メモ、archive状態をsidecarに保存 | 02D |
| export | 検証済みrefsとprovenanceを安全なpackageとして取得 | 02D |
| regenerate_derived | 明示要求で新generation、旧generationと条件履歴を保持 | 02D |
| archive / restore | 実ファイルを保持してユーザー管理状態のみ変更 | 02D |
| delete_run / delete_derived | 対象付き確認・状態再検証・lock後に限定削除 | 02D |

02Cのloadはterminal保存結果の読込でありactive recoveryではない。
既存LocalBackend.collectと同じID / path / digest検証を再利用する方針とし、model環境を起動しない。

## Proposed additive storage (未確定のpath案)

```text
<run_root>/<run_id>/
  user-metadata.json                    # 02D: mutable、独立schema
  derived/
    <derivation_key>/
      <generation_id>/
        manifest.json                   # immutable generation provenance、最後にpublish
        mesh.<format>                   # viewer / exporterに応じ実装時決定
        texture.<format>                # optional
    history.json                        # generation / deletion履歴、atomic更新
```

既存job.json / attempts / output / logs / run.jsonを移設しない。
user metadataとderived indexは独立versionで管理し、legacy Runに存在しなくても正常に読める。
archive / user metadataを既存JobStatusやterminal JobResultへ書き込まない。
raw / WorkerResult / 確定JobResultはimmutable。derived refを確定JobResult.artifactsに後付けしない。
派生manifestを別に読むことで保存後に追加されたviewer成果物を関連付ける。

## Derivation identity and publication

条件keyはcanonicalなalgorithm identity / version、parameters（defaultを展開）、
run / attempt / view、使用するinput artifactsのSHA-256から決める。
RGB / mask / K / normals等も使用する場合はすべてdigest対象に含める。
座標系・単位・scale・depth_kind / grid対応など結果に影響するmetadataとそのdigest、
必要な実装 / library版も記録する。source path名だけで再利用を判断しない。

manifestはkey、generation ID、作成日時、algorithm / parameters / inputs、
input attempt / view、frame / unit / scale、出力relative refs / dtype / shape / size / SHA-256、
変換内容・warningsを持つ。generation IDは同条件の明示再生成でも別IDとする。
通常要求は検証済み同条件generationをreuse、明示再生成は新規generationを追加する。
履歴には生成成功 / 失敗 / 明示削除と条件・対象を残し、失敗を利用可能成果物にしない。

同一Runの同条件同時要求は共通serviceで調停し、complete manifestだけを読ませる。
一時領域に生成・検証し同一filesystem内でatomic publish。途中失敗の出力はcompleteにしない。
壊れた既存cacheはエラーを明示し、raw / old generationを上書きせず明示再生成へ誘導する。
自動削除はしない。partial / 旧generationの削除は確認付き明示操作に限る。

## User metadata / archive / deletion

表示名・メモ・archive flag / 更新日時・metadata revisionをsidecarに保存する計画。
absenceは未設定 / 非archive。archiveは一覧の既定filterで区別し、restoreで戻す。
archive中も実ファイル保持、直接Run ID読込とexport可能。archiveはbackupではない。

削除確認にはRun ID、対象generation、rawを含む全Run削除かderivedのみか、
現在のrevisionを含める。serviceが確認時と実行時の対象・状態を再検証する。
QUEUED / RUNNING / UNKNOWNまたはterminal未確定・active状態不明のRunは削除不可。
FAILED / CANCELLEDも保存terminal結果とworker終了確認が得られたものだけを管理対象とする。
生成 / export / 読込中の削除は共通Run単位lock等で調停し、確認待ちの間はlockを保持しない。
他processのactive recoveryやglobal leaseは追加しない。Phase 02は単一application process運用。

Run Root / UUID / attempt / view / refのcontained pathを検証し、absolute / parent traversal /
Run外symlink / 別Run参照を拒否。check-to-use race対策と削除対象固定を実filesystem testsで検証する。
確認済み範囲外のパスは操作しない。部分削除失敗は診断を返し成功表示しない。
具体的な削除手順・再試行・診断保存先は02D実装前に定義する。
derived削除後も条件・生成履歴と削除tombstoneを保持する。
明示Run削除ではそのRunのrawと履歴も消えることを確認画面に説明する。自動retentionは導入しない。

## Export and compatibility

exportは選択Run / attempt / generationの検証済みrelative refsに限定し、
実行条件・metadata / provenance・digest manifestを同梱する。
入力RGBとraw geometry、derivedのどれを含むか明示し、archive状態で阻害しない。
credentialsやRun外環境ファイルを含めない。形式・一時export lifecycleは02Dで確定する。
保存形式のoptional拡張を優先し、旧schema 1.0 / depth-only読み戻しを必須とする。
互換性を破る変更はversion更新・移行手順・旧fixture testsを先に用意する。

## Validation / risks / deferred decisions

02C: digest-based reuse / explicit generation identity、破損・同時要求・interrupted publication、
再起動読込、raw / JobResult hash不変、model環境不要を検証。
02D: metadata変更 / archive非削除、export隔離、active削除拒否、confirmationとstale revision、
path / symlink / race、derived履歴とpartial failureを検証する。詳細は各milestoneのexitを参照。
API / sidecar schema / format / key canonicalization / lockingは実装前にfixture付きで確定する。
容量・filesystem race・browser format / offline制約は未検証。
検索・favorites・共有 / 認証・自動retention・multi-process調停は後続の別承認対象。
