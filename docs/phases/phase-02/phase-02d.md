# Phase 02D — Run Management

Status: **COMPLETE / 全Exit達成**。Phase 02の内部milestone。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
作業ブランチへのcommit / 通常pushのみ承認。今回mainへの反映は禁止。Phase 03以降は未承認。

## Goal / Background

Resultsから保存Runを安全に管理する。確定推論の証拠とユーザー管理情報を分離し、
callbackにfilesystem操作を埋め込まず共通Run Management Serviceへ委譲する。
共通service・UIと全Exitの検証を完了。

## Scope / Non-goals

保存Run履歴、Run ID直接読込、詳細、表示名 / メモ更新、artifact export、derived再生成、
archive / restore、Runおよびderivedの明示削除。ローカル単独利用を基本とする。
高度な検索、共有ユーザー管理、アクセス制御、認証、多ユーザー公開、お気に入り、
自動削除 / retention、高度なjob復旧は対象外。

## Dependencies

02C exitと02D実装承認。02A validation、02B session境界、02C derived storageを利用。
[Run Management](../../run-management-spec.md) が共通service / storage計画を定義する。
UI / model / backendの責務を混ぜない。

## Implementation tasks

- [x] 共通serviceでlist / load / detail / update user metadata / export /
  regenerate derived / archive / restore / delete run / delete derivedを公開。
  callbackはRun ID・対象generation・確認内容を渡すだけとする。
- [x] Run ID / attempt / view、model / variant、入力・実行条件、status / error、
  取得済みmetrics、raw / derived区別とprovenanceを詳細表示する。
- [x] 表示名・メモ・archive情報は独立したversioned user metadataに保存。
  job / result / raw artifactを変更しない。旧Runでsidecarなしはdefaultとして扱う。
- [x] 条件変更の再推論はRunnerへ新Runとして送る。同一Runのrawを更新しない。
  derived再生成は新generationとalgorithm / params / inputs / digest / historyを追加し、
  同条件reuseと明示再生成を区別する。既存generationを上書きしない。
- [x] exportは検証済みrefだけを選び、条件・unit / frame / scale・manifestも含める。
  Run外path / symlinkを拒否し、一時exportの保存方針も明示する。
- [x] archiveはmetadata更新だけで実ファイル非削除、restoreで通常一覧に戻す。
  archived Runも直接読込 / exportできる。archiveをdeleteと混同しない。
- [x] Run削除は対象Run IDと削除範囲を示す明示確認が必要。derived削除にも対象generationを示す。
  実行中・terminal未確定Runは削除禁止。JobStatusだけで安全と推測せず再検証する。
- [x] 同一application内で生成 / export / 読込 / 削除を共通のRun単位lock等で調停。
  confirm後に状態と選択対象を再検証し、別session / stale selectionの対象を削除しない。
  application再起動後にactiveが不明なRunも削除拒否し、active recoveryは実装しない。
- [x] filesystem pathはRun Root配下でRun ID・relative refsから検証。
  traversal / absolute / Run間参照 / symlink / TOCTOUを検証し、エラーをUIに返す。
- [x] derived削除後も生成条件・履歴tombstoneを残す。明示Run削除はrawを含むRunを消す操作として
  確認画面に説明する。これは確定rawの編集・上書きとは区別する。

## Tests / Exit criteria

- [x] 旧Runと新Runの履歴 / 直接読込 / 詳細、sidecar欠如、破損・不明Runを検証。
- [x] 名前・メモ・archive / restoreでraw / job / JobResult hash不変、archiveでfile数不変。
- [x] exportに選択Run以外のfileを含めず、geometry metadata / digestを保持する。
- [x] 再生成が新generation / historyを作り、条件追跡と再起動後読込が可能。
  同条件通常要求はreuseし、明示再生成を区別する。
- [x] 未確認削除、実行中 / terminal未確定削除、stale対象・別Run・symlink / traversalを拒否。
  生成 / export中削除race、partial failureと状態再読込も検証する。
- [x] browserで確認cancelは無変更、確認済みRun削除とderivedのみ削除の範囲を確認。
  derived削除履歴が残り、別Run / rawの誤削除なし。自動削除経路がないことを確認。
- [x] callbackに直接管理filesystem処理なし、serviceのfake Storeによる契約テストと
  temporary Run Rootによる実filesystem検証を実施し、管理手順を記録。

全項目成功で02D exitを達成し、Phase 02全体もCOMPLETEと再評価した。

## Known risks

確認と削除のrace、symlink / path混線、exportの容量、partial delete、
derived参照中の削除、archiveをbackupと誤認、未知active状態。
単一application processでの調停範囲と拒否条件を文書化する。multi-process調停は別scope。

## Decisions / Deferred decisions

Service分離、sidecar更新、raw不変、履歴付きderived再生成、archive非削除、
明示確認付き削除、active削除禁止、自動retentionなしを採用。
sidecar schema / export形式 / delete失敗時の診断保存・再試行手順 / lock具体方式は実装前に確定。
削除失敗を成功とせず、確認された同一対象への明示再試行に限定する。
お気に入り、検索、共有・認証は後続Phase（時期未定）。


## Final acceptance evidence

| 検証 | 結果 |
| --- | --- |
| 固定production source全suite | **87件 / 322.291秒、82成功・opt-in browser 5 skip** |
| 別実行browser全5件 | **5成功 / 247.236秒**。管理 / 02B fake / 02B CPU / 02C fake / 02C CPU |
| 追加2session / retry UI browser | **1成功 / 38.598秒**。古い確認拒否・別session未確認拒否・cancel・再確認後retry |
| 追加regeneration / export競合 | **1成功 / 5.392秒**。exportは生成完了を待ち、完成世代を同梱 |
| 管理 / Results補強 | 最終削除contracts 18成功、前段contracts 28成功。上記全suiteで再検証 |
| 旧Run互換 | 01A / 02A / 02B / 新CPUの4Runでdetail各2回・export、全hash / mtime不変 |
| 静的 / 環境 | 33 Python AST、206 local Markdown参照 / 11 anchors / fences、JSON / TOML、pip check、diff whitespace成功 |

### Selection and partial failure

実Geometry RunでMeshを3世代作り、最新削除後に2世代が残る状態で再起動Serviceから
新しい旧世代をreuse。非最新削除で選択を維持し、raw / JobResult hash / mtime・predict 1回を確認。
`current` 優先、欠如 / 削除対象除外時は `created_at` 降順・同時刻はgeneration ID降順。
全世代削除後は新規生成。条件・schemaは [管理仕様](../../run-management-spec.md) に確定。

最新generationのmanifestを途中まで削除して失敗させ、残る世代のreuse、履歴からの再確認・削除完了を検証。
directory削除後のpointer整理失敗も、再起動後の明示retryでtombstoneを完了。
公開失敗の履歴・未commit / failed世代の候補除外をfixtureで検証。

### Safety and service boundary

削除・失敗注入は全てTemporaryDirectoryのRun Root。既存実験Runを削除していない。
未確認・別Run・未入力・stale inventory / revision・active / terminal未確定・再起動unknownを拒否。
名前・メモ・archive / restoreで原本不変。sidecar作成後のarchive file数不変も確認。
exportは選択Runの参照fileに限定し、全digestとJobResult / geometry metadataを照合。

export / generation中の削除待機、generation後の古い確認拒否、exportの再生成完了待機を検証。
TOCTOU fixture: 読込直前のsymlink置換、同bytesのdirectory置換、quarantine rename直前のRun置換、
derived親directoryのdescriptor open後の置換。別対象を削除せず、隔離のidentity不一致はretryも拒否する。
全Runのrmtree失敗は成功扱いせず隔離、再確認 / typed IDで同一対象だけretryする。
UIに直接管理filesystem操作はなく、Service fake Storeと実LocalBackend / filesystemを検証。

### Real CPU / compatibility / limits

最終native CPU Run **`67d893e9-f399-4c9f-a7c5-405b52976a6f`**、COMPLETED、JPEG入力、
125,125 Mesh faces、predict 1回、raw不変・workerなし再起動読込、外部HTTP / page errors 0。
`source_digest=c6f2c2c9f327d2b0be5081de24d2f5448c04521622b12659cae4c98702fc81e9` が
最終production sourceと一致。depth-only CPU Run `a3d6f8f7-9c06-4f31-b0af-134f3dd41139` も成功。
CUDA不可失敗・CPU cancel / timeout、4表示モード・camera・RGB / normals / texture・offlineも既存testで再確認。

互換4Run: 01A `9c5b6556-30d3-43ae-827f-7bd8b0a47580`、02A `a2c9ca5a-4eb7-4697-b880-8041e7749bae`、
02B `799d2355-c57b-4552-92c4-644a7f25e775`、先行CPU `0e751a9d-0619-48b5-ad66-a2be5ece8ee9`。
旧Runは読込・exportだけに使用し、原本の全hash / mtime不変を確認。

Linux / Chrome 154.0.8037.92 / WebGL SwiftShader、Python application / worker socket guardと
browser routeのegress遮断条件で成功。OS全体firewall、GPU推論、他OS/browser、学会実演は未検証。
単一application processでの調停。外部process同時書換え・multi-process leaseは範囲外。
ZIP 256 MiB / inventory 1file 256 MiB、viewer上限は02Cと同じ。高解像度・MoGe品質は変更していない。
既存upstreamのunclosed event loop ResourceWarningは残るが、ブラウザー機能・console/page errorは成功。
先行suiteでは既存4秒timeout fixtureがreadiness前に終了する失敗が1件（329.843秒）。
条件変更なしの最終固定source suiteで成功し、未実行を成功扱いしていない。

ローカル証拠（Git管理外）: `.local/validation/02d-final-{suite,browser}.log`、
`02d-session-final-browser.log` / `02d-race-final.log` / `02d-final-delete-contracts.log` /
`02d-compatibility.json`。環境・weights・Run・生成物はcommitしない。

**02D COMPLETE、Phase 02 COMPLETE。main反映なし、Phase 03以降未承認。**
