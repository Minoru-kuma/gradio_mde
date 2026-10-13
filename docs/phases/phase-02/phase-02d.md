# Phase 02D — Run Management

Status: **NOT_STARTED / 実装未承認**。Phase 02の内部milestone。以下は設計のみ。
親: [Phase 02](../phase-02.md)、管理: [PLANS](../../../PLANS.md)。
今回の承認は文書整備・検証・commit / main pushのみ。実装開始・依存導入は行わない。

## Goal / Background

Resultsから保存Runを安全に管理する。確定推論の証拠とユーザー管理情報を分離し、
callbackにfilesystem操作を埋め込まず共通Run Management Serviceへ委譲する。
現在はterminal collectがあるが、一覧 / archive / delete等の管理serviceは未実装。

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

- [ ] 共通serviceでlist / load / detail / update user metadata / export /
  regenerate derived / archive / restore / delete run / delete derivedを公開。
  callbackはRun ID・対象generation・確認内容を渡すだけとする。
- [ ] Run ID / attempt / view、model / variant、入力・実行条件、status / error、
  取得済みmetrics、raw / derived区別とprovenanceを詳細表示する。
- [ ] 表示名・メモ・archive情報は独立したversioned user metadataに保存。
  job / result / raw artifactを変更しない。旧Runでsidecarなしはdefaultとして扱う。
- [ ] 条件変更の再推論はRunnerへ新Runとして送る。同一Runのrawを更新しない。
  derived再生成は新generationとalgorithm / params / inputs / digest / historyを追加し、
  同条件reuseと明示再生成を区別する。既存generationを上書きしない。
- [ ] exportは検証済みrefだけを選び、条件・unit / frame / scale・manifestも含める。
  Run外path / symlinkを拒否し、一時exportの保存方針も明示する。
- [ ] archiveはmetadata更新だけで実ファイル非削除、restoreで通常一覧に戻す。
  archived Runも直接読込 / exportできる。archiveをdeleteと混同しない。
- [ ] Run削除は対象Run IDと削除範囲を示す明示確認が必要。derived削除にも対象generationを示す。
  実行中・terminal未確定Runは削除禁止。JobStatusだけで安全と推測せず再検証する。
- [ ] 同一application内で生成 / export / 読込 / 削除を共通のRun単位lock等で調停。
  confirm後に状態と選択対象を再検証し、別session / stale selectionの対象を削除しない。
  application再起動後にactiveが不明なRunも削除拒否し、active recoveryは実装しない。
- [ ] filesystem pathはRun Root配下でRun ID・relative refsから検証。
  traversal / absolute / Run間参照 / symlink / TOCTOUを検証し、エラーをUIに返す。
- [ ] derived削除後も生成条件・履歴tombstoneを残す。明示Run削除はrawを含むRunを消す操作として
  確認画面に説明する。これは確定rawの編集・上書きとは区別する。

## Tests / Exit criteria

- [ ] 旧Runと新Runの履歴 / 直接読込 / 詳細、sidecar欠如、破損・不明Runを検証。
- [ ] 名前・メモ・archive / restoreでraw / job / JobResult hash不変、archiveでfile数不変。
- [ ] exportに選択Run以外のfileを含めず、geometry metadata / digestを保持する。
- [ ] 再生成が新generation / historyを作り、条件追跡と再起動後読込が可能。
  同条件通常要求はreuseし、明示再生成を区別する。
- [ ] 未確認削除、実行中 / terminal未確定削除、stale対象・別Run・symlink / traversalを拒否。
  生成 / export中削除race、partial failureと状態再読込も検証する。
- [ ] browserで確認cancelは無変更、確認済みRun削除とderivedのみ削除の範囲を確認。
  derived削除履歴が残り、別Run / rawの誤削除なし。自動削除経路がないことを確認。
- [ ] callbackに直接管理filesystem処理なし、serviceのfake Storeによる契約テストと
  temporary Run Rootによる実filesystem検証を実施し、管理手順を記録。

全項目成功で02D exit。Phase 02全体のexitを再評価する。今回は未実行。

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
