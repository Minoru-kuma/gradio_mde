# Phase 02 — Geometry Artifacts / Gradio / 3D Results / Run Management

Status: **IN_PROGRESS**。02Aは実CPU native Pointsを含むExit達成でCOMPLETE。docs整理・commit / main pushまで承認。
02B〜02Dは **NOT_STARTED / 実装未承認**。02Aの実装証拠は内部文書、02B以降は将来の受入条件。
管理: [PLANS](../../PLANS.md)。Phase 01 / 01A / 01BはCOMPLETE。

## Goal

単一モデルの幾何成果物を正式に保存・検証し、GradioのInference / Resultsから
Local推論、2D / 3D閲覧、保存Runの安全な管理を行えるようにする。
ノートPCで学会デモできるローカル・オフライン構成を目指す。

## Background

Phase 01のCLI → ExperimentRunner → LocalBackend → 独立Conda worker → ModelAdapterを維持する。
Phase 01はPNG 1枚 / attempt-0001 / depth-onlyの保存経路、schema 1.0。
02Aで明示要求のoptional geometry保存・RunStore検証を追加し、既定depth-onlyを維持する。
Gradio、3D viewer、派生保存、Run管理serviceは存在しない。
実モデルCPU成功は [Phase 01](phase-01.md) の証拠であり、GPU / UI / 学会デモ成功ではない。

## Scope

- 02A: depth必須、points / normals / intrinsics optional、metadata / maskと標準保存・検証、実CPU native Points。
- 02B: **Inference / Results** の2タブ。model / variant、画像検証、device / backend / parameters、
  submit、Run ID、非同期status / progress、cancel / timeout / failure、session分離、Local busy。
- 02C: Resultsの **Depth | RawDepth | Point Cloud | Mesh**、保存Run読込、共通derived mesh保存。
- 02D: 履歴・直接読込・詳細・表示名/メモ・export・再生成・archive / restore・明示削除。

BackendはLocalのみ。UIはRunner / Registry metadataと共通serviceを利用し、
モデル推論・PyTorch・Conda・subprocessの直接制御をcallbackに書かない。
Gradioは独立application environment、version / dependenciesは実装時にpinする。
全sessionで同じLocalBackendを共有し、一度に1job、busyは拒否、実行jobのqueueを作らない。
session stateの画像・handle・表示Runは個別に保持する。公開多ユーザー運用は想定しない。

## Non-goals

Phase 03: 複数モデル統合。04: MLflow。05: Benchmark / 比較評価。
06以降: 高度なqueue / retry / active recovery。07–08: SlurmBackend。
お気に入り / ふぁぼ（時期未定）、認証・本格的多ユーザー公開、高度な検索、共有ユーザー管理、
アクセス制御、高度な3D編集・解析、自動削除 / retentionは対象外。先回り実装しない。

## Dependencies

| 内部 milestone | 前提 | 成果の利用先 |
| --- | --- | --- |
| [02A — Geometry Artifacts](phase-02/phase-02a.md) | Phase 01 COMPLETE、実装承認 | 02B / 02Cの共通成果物 |
| [02B — Gradio Inference](phase-02/phase-02b.md) | 02A exit、実装承認 | 02C / 02Dの2タブ・session境界 |
| [02C — 3D Results Viewer](phase-02/phase-02c.md) | 02A・02B exit、実装承認 | 02Dの派生保存・管理対象 |
| [02D — Run Management](phase-02/phase-02d.md) | 02C exit、実装承認 | Phase 02全体の管理経路 |

**01 → 02A → 02B → 02C → 02D**。独立したPhaseの新設ではない。
02BではResultsに共通結果とRun IDを渡す枠を作り、完全な3D表示は02Cに置く。
02Cで最小derived生成/読込/再利用を作り、再生成・削除のユーザー管理操作は02Dに置く。
関連: [Architecture](../architecture.md)、[Adapter](../model-adapter-spec.md)、
[Execution](../execution-backend-spec.md)、[Run Directory](../run-directory-spec.md)、
[Environment](../environment-strategy.md)、[Run Management](../run-management-spec.md)。

## Implementation tasks

- [x] 02A: 共通serializationとartifact検証、native / standard provenance、旧Run互換。
- [ ] 02B: Runner操作・非同期poll・session分離・busy表示、application依存pin。
- [ ] 02C: 4表示モード・色/描画切替・視点管理、derived meshの遅延生成・永続保存。
- [ ] 02D: callbackと分離した管理service、安全な明示操作と履歴。
- [ ] ローカル起動・事前準備・offline・明示CPU・保存結果デモの再現手順。

## Tests

各milestoneのfake / contract / browser / 実機テストを分けて記録する。
旧depth-only Run、optional欠如、破損path / digest、session混線、cancel完了race、
大きなgeometry、アプリ再起動後の閲覧、raw不変、管理操作の競合を検証する。
offlineはネットワーク遮断下でfrontend操作と準備済みモデル推論を確認する。
GPU検証は機材がある場合の別証拠とし、未計測runtime / GPU memoryはunavailable。

## Exit criteria

02A〜02Dの全exitを満たし、旧CLI・保存Run互換を確認する。
UIから1モデルをLocalで実行し、完了後すぐResultsで確認・downloadできる。
保存Runを再推論せず再起動後も開き、利用可能geometryの3D回転・zoom・panと管理操作ができる。
optional欠如時は理由を表示し、存在しないgeometry / metricsを捏造しない。
raw / JobResultのdigest不変、derived条件の追跡、archive非削除と実行中削除拒否を確認する。
pin済み環境とoffline起動手順・検証結果を記録し、GPU / 学会実演の未検証項目を明示する。
今回の文書完成ではこれらを達成済みにしない。

## Known risks

K / pixel grid / native frameの変換誤り、rawと表示normalizationの混同、geometry容量とbrowser制約、
Gradio event dispatchの待ち行列、shared backendとsession分離、派生cacheのpartial publication、
削除と生成のrace、CDN / 外部通信依存。対策と受入検証は各milestone・管理仕様に分ける。

## Decisions / Deferred decisions

raw推論成果物と確定JobResultは不変。表示による再推論・scale正規化はしない。
標準化で必要な変換はadapter境界でnative conventionとともに記録し、viewerはその保存frame / unit /
scaleを維持する。表示cameraの初期位置のみ自動調整し、可能な範囲でPoint Cloud / Mesh間の視点を保持。
Derived Meshは初回要求時に生成、Runに関連付け永続保存、algorithm / parameters / input digestで再利用。
自動削除なし、明示再生成は新履歴を追加しJobResultを変更しない。
Gradio / viewerの版、3D形式、容量上限、mesh discontinuity閾値、schema minor / profile名は
各milestoneの実装承認後に調査・pin・fixture検証して確定する。
