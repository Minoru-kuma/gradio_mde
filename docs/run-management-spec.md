# Run Management / Derived Storage specification

Status: **02D COMPLETE / 全Exit達成**。Phase 02全体もCOMPLETE。
作業ブランチのみを更新し、今回mainへは反映しない。
関連: [02D](phases/phase-02/phase-02d.md)、[Results Viewer](results-viewer.md)、
[Run Directory](run-directory-spec.md)、[Gradio](gradio-inference.md)。

## Responsibility and API

`RunManagementService(store, collect)` は既存terminal collectorを注入して使う。
モデル環境・adapter・torchを起動せず、推論を送信しない。UIの管理callbackはServiceを呼ぶ。
条件を変えた推論は既存InferenceからRunnerへ新Runとして送る。

| API | 動作 |
| --- | --- |
| `list_runs(include_archived=False)` | UUID Runの履歴。active / corruptはunavailable、archiveは既定で除外 |
| `detail(run_id)` | terminal collect、job / result / metadata / derived / history / derived_errors |
| `update_metadata(run_id, revision, display_name=..., notes=..., archived=...)` | revision照合、表示名・メモ・archive / restore |
| `export(run_id)` | 検証済み入力 / raw / 完成derivedとmanifestを含むZIP bytes |
| `regenerate_derived(run_id)` | 現在のMesh条件で新generationを明示生成 |
| `prepare_delete(run_id, generation=None)` | 対象・scope・inventory・directory identityを確認用に返す |
| `delete(confirmation, selected_run_id, typed_run_id=...)` | terminalと確認を再検証して限定削除 |
| `prepare_retry(quarantine_name)` | 中断した全Run削除の隔離先と記録を再確認 |
| `retry_delete(confirmation, typed_run_id=...)` | 再確認した同一隔離対象のみ削除 |

既存JobSpec / WorkerResult / JobResultとrawは編集・上書きしない。旧depth-only Runと
JPEG入力のRunも同じcollectorを使う。破損derivedはdetailsの理由付き診断にし、rawの詳細と
確認付きderived削除を利用可能にする。破損・未完成成果物を成功exportに含めない。

## Additive storage

```text
<run_root>/<run_id>/
  user-metadata.json
  derived/
    <key>/
      current.json
      <generation_id>/
        manifest.json
        geometry.npz
      .partial-<generation_id>/
    history.json
<run_root>/.management-quarantine/
  <run_id>-<nonce>/
  <run_id>-<nonce>.json
```

既存Run内のjob / attempts / output / logs / run.jsonは移設しない。
管理metadata schema 1.0: revision / display_name / notes / archived / updated_at。
absenceはrevision 0・未設定・非archive。表示名256文字、メモ16,384文字まで。
最初の更新でsidecarを1つ追加し、以後archive / restoreでfile数を変えない。
元の入力・job・result・rawのfile数 / hash / mtimeを維持する。archiveはbackupではない。
archived RunもRun IDから直接読込 / exportできる。

## Derived identity, publication and selection

条件keyはcanonical JSON（sort keys、compact separators、nonfinite scalar禁止）のSHA-256。
algorithm / version、展開parameters、run / attempt / view、使用input refsのdigest、
frame / unit / scale / grid等の意味metadata、必要なlibrary版を含む。詳細はResults Viewer仕様を参照。
同条件の通常要求はreuse、明示再生成はUUIDの新generationを追加して旧generationを保持する。

私有stagingにNPZとschema 1.0のmanifestを書き、atomic rename、history commit、current pointerの
順に公開する。新manifestのoptional `publication_protocol=history-commit-v1` は対応する成功historyを
必要とする。生成 / 保存 / 公開の失敗はfailed eventに対象と条件を記録し、利用候補から除外する。
stagingや不完全directoryは自動削除しない。旧02C / 初期02Dのprotocol fieldなしも読める。

選択ルール:

1. `current.json` が示す完成世代を優先する。pointer破損・参照先不明は理由付きerror。
2. currentが存在しない場合、または削除要求・削除済み・公開失敗の対象なら、残る完成世代を選ぶ。
3. fallbackはmanifestのtimezone付き `created_at` の新しい順。同時刻はgeneration IDの辞書順で大きい方。
4. 使用する世代のidentity / path / output digest / arraysを検証する。壊れたcacheを黙って成功扱いしない。
5. 候補がなければ新規生成する。選択は再起動後も同じ。rawや旧generationを上書きしない。

3世代以上から最新を削除して複数の旧世代が残ってもfallbackする。非最新削除はcurrentを維持する。
`delete_requested` は再試行まで含めたdurable exclusion。途中まで削除された世代をreuseしない。
履歴schema 1.0のeventsはgenerate / regenerate / failed / delete_requested / deleted。
immutable manifestと生成条件を履歴に保持し、derived削除後もtombstoneを残す。

## Confirmation, deletion and interrupted operations

UIはInspectしたRunと入力Run IDを照合し、入力変更時にsession内の選択・確認を破棄する。
metadata更新後は再Inspect。Run削除の範囲（raw・Run内historyを含む全体）と、derived相対pathによる
限定削除を明示し、正確なRun IDの入力を要求する。scope変更時は再確認する。
確認cancelは状態破棄のみ。別browser sessionに確認状態を共有しない。

Serviceは実行時にterminal collect、全fileのdigest inventory、対象directoryのdevice / inodeを
再検証する。active / UNKNOWN / terminal未確定・restart後active不明は削除不可。
FAILED / CANCELLEDもBackendが停止・terminalを確定した保存結果を必要とする。
管理inventoryは1fileあたり256 MiBまでで、超過は拒否する。

全Run削除はRoot / quarantineのdescriptorを開き、対象をランダムな隔離名へrename後にidentityを照合し、
symlink耐性のあるrmtreeを実行する。失敗は成功表示せず隔離先を診断に返す。
隔離前にterminal確認・対象identity・確認inventoryを別schema 1.0記録へ保存する。
この確認記録は成功後も残る（raw bytesやRun内の派生履歴のコピーは含まない）。自動retentionはない。

再試行はReview deletion retryへ診断の隔離名を入力し、確認後に元Run IDを入力して実行する。
元Run IDの再利用、隔離対象の置換・symlink・変更済みinventoryは拒否する。
再試行の確認cancelと入力変更も確認状態を破棄する。

derived削除はdelete_requestedを先に保存し、親descriptorに固定して削除、currentを整理してから
完了tombstoneを書く。manifestの部分削除後は履歴の元manifestから再確認できる。
directoryだけ消えてpointer整理が失敗した場合も、記録とinventoryを再確認して整理を完了できる。

## Locking, paths and operational limits

`run_access.run_lock` のRun単位RLockをRunner.collect、Results load / view、DerivedStoreと
管理Serviceで共有する。読込・生成・export・metadata・削除を同じRunについて直列化する。
確認待ちではlockを保持せず、実行時に再照合する。生成後の古い削除確認は拒否する。

UUID / relative refのcontainment、symlink全component、nonregular fileを検証する。
管理ファイル読込はdirectory descriptor / O_NOFOLLOW、sidecarはdescriptorに固定した一時fileから
atomic replaceする。削除は親descriptorとdevice / inodeを照合する。
外部processによるRun Rootの同時書換え、multi-process / host間lease、active recoveryは保証しない。
検証したTOCTOU fixtureとOSの範囲は02D evidenceに明記する。運用は単一application process / Linux POSIX。

## Export

最大256 MiBのZIPをメモリ内で作成する。Gradioからdata URLでdownloadし、永続一時exportは作らない。
入力PNGとoptional元JPEG、raw artifacts、job / terminal snapshots、完成derivedのmanifest / NPZ、
管理metadata・派生history・各fileのSHA-256 / byte数を同梱する。
unit / frame / scale / 条件は元JobResult・derived manifest内の値を保持する。
logs・credentials・環境ファイル・Run外path・未参照file・partial / failed derivedは含めない。
大容量ZIPはapplication / browser memoryを消費する。解像度上限・MoGe推定品質は今回変更しない。

## Phase 03.5 multi-view export

Run detail retains the complete Job inputs, terminal outputs and optional scene ArtifactRef. Export
includes every registered per-view artifact, the scene record and all inputs, subject to the existing
integrity / containment / size checks. Unknown JSON extras are retained in their records; arbitrary
path-like metadata is not opened. No raw record is rewritten by repeated collect / export.

## Phase 03.7 calibration generations

K-only derived calibration generations use the existing history / publication / selection and export inventory.
Raw inference JobResult remains unchanged. Regenerate Mesh uses the default saved-native / configured-estimator
camera path; browser-supplied known K is session-specific and does not overwrite that default.
Explicit known-K regeneration is available through ResultsService.view with known_camera and regenerate=True.
K cache and reconstruction provenance: [03.7 specification](depth-reconstruction-spec.md).
