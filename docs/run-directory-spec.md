# Run Directory specification

Status: Phase 01A の1 Run / 1 attempt / 1 view の最小 layout を実装し、fake 出力の保存・読戻しを確認。
MoGe CPU の実推論成果物も保存・読み戻し確認済み。証拠は [Phase 01](phases/phase-01.md)。
02A optional geometryは末尾の実装契約を参照。tracking / evaluation / retryは将来設計。
関連: [Job contracts](execution-backend-spec.md)、[MDEOutput](model-adapter-spec.md)、
[MLflow](mlflow-design.md)、[Slurm](slurm-integration.md)。

03.4の追加診断: `execution.runtime_capability_check`はload後の能力照合が成功した場合のoptional JSON。
`declaration: declared / legacy_undeclared`、`requested_outputs`、`capabilities` snapshotを持つ。
旧Runのfield欠如は正常。照合失敗時は未検証snapshotを保存せず、既存のpreflight errorで報告する。
意味は[ModelAdapter契約](model-adapter-spec.md#phase-034-runtime-capability-preflight)を参照。
schema 1.0・既存numeric profileとraw不変の契約は変更しない。

## Identity

- `run_id`: application が採番する logical inference / benchmark experiment の安定 ID。
  初期案は UUID 形式。ユーザー入力を directory name としてそのまま使わない。
- `attempt_id`: 同一 inference request の実行 attempt。例 `attempt-0001`。
- `backend_job_id`: Local execution identity または Slurm job ID。
- `mlflow_run_id`: MLflow が採番する別 ID。application の Run ID に置き換えない。

全 JSON report に run / attempt ID を入れ、MLflow に `mde.run_id` / `mde.attempt_id` tags を付ける。
Slurm job ID と MLflow run ID の対応は handle / tracking records に保存する。
Benchmark 親 Run ID と通常 inference 子 Run ID を `parent_run_id` で結ぶ。

## Run Root configuration

RunStore は root を依存注入する。優先順位は **明示設定 > `MDE_RUN_ROOT` > 既定 `./runs`**。
既定と相対指定は実行時の偶然の cwd ではなく、設定した project / config base に対して解決する。
初回に absolute root を解決して以降は同じ設定を使う。UI callback や adapter に path を埋め込まない。

Local と研究室では別 profile の root を設定できる。研究室 path は未確認。
JobSpec の artifact / input path は Run 相対 path とし、submit 側と node 側で mount prefix が違っても
同じ `run_id` と relative path に到達できるよう Store location を target ごとに解決する。
共有 root が存在することと、両方の host が読めることは Phase 07–08 で検証する。

## Standard layout

```text
<run_root>/<run_id>/
  job.json                         # 初回 JobSpec。immutable
  run.json                         # Runner 管理の logical run / selected attempt / parent
  input/
    views/<view_id>/image.png       # 推論入力PNG。checksum / サイズは job に保存
    views/<view_id>/original.jpg    # UI JPEG時のみ、元bytes
    camera/                        # optional 入力 camera metadata
  attempts/
    attempt-0001/
      job.json                     # この attempt の immutable JobSpec snapshot
      handle.json                  # backend job ID / submission identity
      status.json                  # backend が atomic に更新する状態 snapshot
      job-result.json              # backend が確定した terminal JobResult
      tracking.json                # Runner の MLflow 対応 / 未送信記録
    attempt-0002/                  # retry が指示された場合のみ
  output/
    attempt-0001/
      result.json                  # worker report、最後に publish
      metadata.json                # runtime / environment / conversion provenance
      views/<view_id>/
        depth.npy                  # 必須 raw numeric depth
        depth_vis.png              # optional 派生表示
        points.npy                 # optional dense point map
        point_cloud.ply            # optional exporter artifact
        intrinsics.npy             # optional K
        normals.npy                # optional raw normals
        normals_vis.png            # optional 表示
        mask.npy                   # optional bool mask
        confidence.npy             # optional confidence
        rays.npy                   # optional directions
        camera_pose.npy            # optional c2w pose
        extras/                    # namespaced native artifacts
  logs/
    attempt-0001/
      stdout.log
      stderr.log
      worker-events.jsonl          # optional structured diagnostic events
  evaluation/                      # Phase 05: protocol / per-view / aggregate results
  benchmark/                       # benchmark 親 run の plan / child index / summary
```

基本は要求された `job.json / input / output / logs` に、attempt metadata を足したもの。
初回の root `job.json` と `attempts/attempt-0001/job.json` は同じ内容 / digest とする。
root job を retry で書き換えず、新 attempt の JobSpec はその attempt に保存する。
`run.json.selected_attempt_id` で表示対象を選び、root output への壊れやすい symlink は必須にしない。
実装時は成功に必要な最小 file から作り、optional file の空生成はしない。

01A は 1 Run / `attempt-0001` / 1 view のみを使う。入力、JobSpec / handle / status / JobResult、
raw `depth.npy`、`metadata.json`、worker `result.json`、stdout / stderr を保存して最初の成功を
確認する。追加 attempt、tracking record、evaluation、benchmark、optional geometry artifacts を
先に実装しない。01B は基本的な失敗・cancel / timeout と保存結果の検証を拡張し、retry controller
や active job の再起動復旧は Phase 06 以降に扱う。layout / ID はこれらの拡張でも維持する。

## Job and result wire formats

`job.json` は [JobSpec](execution-backend-spec.md#jobspec)、worker `result.json` は
schema version、run / attempt identity、worker outcome、view ID ごとの SerializedMDEOutput、
metrics、execution metadata、errors / warnings を持つ。
wire と worker 内の MDEOutput を混同しない。depth field の wire value は配列そのものではなく参照。

ArtifactRef の概念例（設計例、実ファイルではない）:

```json
{
  "path": "output/attempt-0001/views/view-0001/depth.npy",
  "media_type": "application/x-npy",
  "dtype": "float32",
  "shape": [480, 640],
  "unit": "m",
  "sha256": "PLACEHOLDER_DIGEST",
  "size_bytes": 1228928
}
```

この解像度・unit・size は例であり、実モデルの既定値ではない。
必須 reference は path / media type / checksum / size、numeric artifact は dtype / shape / unit も持つ。
SerializedMDEOutput は view ID、depth reference、optional field references、extras、metadata を持つ。
output dimensions、depth kind / scale、camera frame は result の共通 metadata で検証する。

JSON は UTF-8 とし、NaN / Infinity を JSON scalar にしない。array 内の invalid 値は mask と規則で扱う。
NPY は numeric / bool のみ、pickle / object dtype を禁止。PNG は表示用で raw depth の代用品にしない。
PLY の単位・座標系も manifest に残す。confidence は native 値の保存と表示変換を分ける。

## Writers and atomic publication

| Writer | 書く file | 読む file |
| --- | --- | --- |
| Runner / RunStore | input、JobSpec snapshots、run.json、evaluation、tracking.json | JobResult、artifacts |
| Backend / Worker Manager | handle.json、status.json、job-result.json、捕捉した stdout / stderr、scheduler logs | JobSpec、worker report |
| model worker | attempt 別 output、worker-events、worker report | 自分の JobSpec、input |

同じ file を複数 owner が競合更新しない。Run / attempt の作成は exclusive creation で重複を拒否する。
worker は stdout / stderr の stream を出し、Local の捕捉・保存は Worker Manager が担当する。
Slurm では scheduler の redirection を同じ log contract に対応させる。
input と JobSpec の準備後に submit する。worker report の存在だけで scheduler status を上書きしない。

publication 手順:

1. attempt 内の staging file に artifact を書き、flush / close 後に同じ filesystem 上で rename。
2. dimensions、units、checksums、required depth を検証して metadata を保存する。
3. `result.json` を temporary file から atomic rename し、これを worker report の確定マーカーにする。
4. Backend は execution 成功と report / 必須 artifacts を再確認して JobResult を確定する。
5. Runner は JobResult を使って logical run を更新する。Tracking 更新は導入後の Phase 04。

異なる filesystem 間の rename は atomic と仮定しない。atomic rename も NFS client 間の即時可視性や
停電時 durability を保証しない。01A は Local の atomic publication と基本検証を実装し、
NFS 向け bounded publication grace / reader retry は Phase 06–08 で検証する。
研究室 NFS の実挙動は Phase 08 で確認する。half-written report を成功として読まない。

WorkerResult がない crash / OOM / cancel は Backend が診断 JobResult を生成する。
worker は FAILED report を可能な範囲で保存するが、強制 kill 後の report を要求しない。
stdout / stderr の partial log も保持する。terminal JobResult は確定後に書き換えない。

## Path, retention and recovery rules

- relative path は Run 内に解決する。`..` / absolute path / symlink による Run 外参照を拒否する。
- input hash、checkpoint hash、environment digest、git source identity を保存する。
  Git metadata がない場合は commit unknown とし、実装時は source snapshot digest を代替候補とする。
- 再 collect と Tracking 再送は既存 artifact を読むだけ。再推論を行わない。
- 同じ request の retry は attempt を追加する。条件変更は新 Run ID と related run tag。
- UI download は selected finalized attempt の reference に限定する。
- cleanup は別の明示的 retention policy。実行中 Run と唯一の成果物を自動削除しない。
  容量対策として points / confidence 等の保存は requested outputs と policy で制御する。
- 保存済み terminal result の再読込・再 collect は 01B の検証対象。active job の application
  restart recovery / stale RUNNING の reconciliation は Phase 06 以降とし、01A の exit 条件に
  含めない。directory だけを根拠に再 submit しない。

01A の NPY は little-endian float32 `[H,W]` / C order、invalid は NaN。
control は NumPy を import せず NPY header / payload size / checksum を検証する。
01B では同一 / 新 backend instance と新 CLI process の terminal 再 collect を検証済み。
job-result.json が存在しない active handle は復旧しない。
Git metadata が見えない実行では `git_commit=unknown` と `.py / .json / .yml` の source digest を残す。
metadata は actual Python / Conda prefix / device と、adapter が観測した torch / runtime / GPU を持つ。
machine-specific path はローカル生成結果に限り、repository に commit しない。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| root を設定、payload は relative refs | Local と NFS の mount path を分離 | target Store resolution が必要 | object storage / staging backend |
| attempt 別 output / logs | retry で成果と失敗証拠を失わない | directory の階層が一段増える | execution instance / scheduler requeue |
| WorkerResult と確定 JobResult を分ける | worker 未起動や scheduler failure も表現する | report が二段になる | reconciliation / audit tooling |
| file manifest を最後に publish | 読み手が partial artifacts を成功扱いしない | file validation と publication grace が必要 | NFS / remote Store の専用 writer |

## Phase 01B validation and compatibility

layout と schema_version `1.0` は維持。新規情報は既存 execution / metrics 内の optional field とする。
01A 形式の fingerprint / 計測のない保存結果の読み戻しを tests で確認する。
JSON object 以外、duplicate key、NaN / Infinity / overflow scalar、未知 major を拒否する。
必須 depth と metadata は output/attempt-0001 以下の参照・size / SHA-256 を照合し、
NPY header / payload / dtype / shape、depth unit / scale / camera、metadata の ID / views / runtime
および worker / terminal report の一致を検証する。absolute / parent traversal / Run外 symlink を拒否。
input hash と immutable JobSpec snapshots も照合する。

確定前の不正 result は FAILED、確定後の変更は ArtifactIntegrityError。cancel / timeout の
途中 artifacts を成功出力にしない。診断結果と partial stdout / stderr を保持する。
terminal 再 collect は読み取り専用で、artifact の checksum / mtime と predict log の回数を tests /
MoGe regression で確認した。active job を directory から再 submit する機能はない。

## Phase 02 additive artifacts and management

Phase 02は02A〜02Dの全Exit達成でCOMPLETE。
以下の02A記述は実装前の計画であり、確定契約は末尾を参照。上記layoutのoptional geometryは現行exportではない。
[02A](phases/phase-02/phase-02a.md) でdepth必須、points / normals / intrinsics / maskのoptional
保存・参照検証を追加する計画。既存depth.npy / metadata / reportの場所と意味を維持する。
旧schema 1.0 / 01A-depth-onlyを読込し、optional absenceは許容。
追加profileと参照schemaは実装前に確定し、必須意味の変更ならversion更新 / migrationを用意する。

[02C](phases/phase-02/phase-02c.md) のderived meshは既存output / job-resultとは別領域・manifestに
遅延生成・永続保存する。確定JobResultにrefを追加しない。model由来rawとderivedを明示し、
algorithm / params / 使用入力digestを記録して同条件reuse。raw / WorkerResult / JobResultは不変。
管理metadata / derived generation / 履歴の確定pathとAPIは [Run Management](run-management-spec.md)。
Run / attempt / viewを検証し、別Run path / symlinkを許容しない。

[02D](phases/phase-02/phase-02d.md) は表示名・メモ・archiveをsidecarで更新し、archiveでfileを削除しない。
Run / derivedの削除は対象付き明示確認、active / terminal未確定は拒否、自動削除なし。
上記将来retention policyはPhase 02には導入しない。条件変更の再推論は新Run、
derived明示再生成は新generationと履歴。active restart recoveryは依然Phase 06以降。

## Implemented Phase 02A wire format and validation

先行節の02A設計を以下の追加契約として実装。02C derivedは [Results Viewer](results-viewer.md)の追加契約を実装、02D user metadataと履歴・削除確認は [Run Management](run-management-spec.md)の追加契約。
既存schema_version `1.0` / layout / depth意味は維持し、optional output refsを追加する。
新profile `execution.serialization_profile=02A-geometry-v1` を旧 `01A-depth-only` と区別する。
旧profile（profile field欠如も含む）は従来depth-onlyとして読込可能。旧Runへgeometryを後付けしない。
旧readerにgeometry検証能力があるとはしない。geometry Runの正式検証には02A readerを使う。

| output ref / file (output/attempt-0001/views/view-0001以下) | 型 / 単位 | 保存条件 |
| --- | --- | --- |
| depth / depth.npy | little-endian float32 [H,W]、m / arbitrary / unknown | 必須、従来不変 |
| points / points.npy | little-endian float32 [H,W,3]、depthと同単位・尺度 | 明示要求、実model出力 |
| normals / normals.npy | little-endian float32 [H,W,3]、unitless | 明示要求、実model出力 |
| intrinsics / intrinsics.npy | little-endian float32 [3,3]、pixel | 明示要求、実model出力を標準化 |
| mask / mask.npy | bool [H,W]、unitless | geometry profileで常にeffective validityを保存 |
| model_mask / model_mask.npy | bool [H,W]、unitless | geometry profileでnative maskがある場合 |

refsはpath / media_type=application/x-npy / shape / dtype / unit / size_bytes / SHA-256。
`outputs[0]`と`artifacts`双方に同一refを持ち、metadata.jsonのviewsとreport metadataも一致させる。
maskのexplicit要求はnative maskの提供を要求するが、serialized mask refはeffective validity。
model_maskが元のモデル判定、maskがfinite-positive depth AND model_mask。
geometryのmetadataには各refのorigin / native convention / conversion等を保存する。
共通effective maskだけorigin=validation、その他はorigin=model。rawモデルgeometryと将来derivedを混同しない。

requested_outputsをJobSpecと照合し、geometry profileの欠落・別profile・未対応名を拒否。
C-order / header・payload・dtype・shape・unit・frame・scale・digest・contained pathをstdlibで検証する。
float payloadは4096 records単位で読み、controlにNumPy / PyTorchを導入しない。
有効Pointsはfiniteで、z-depthならpoints.z、ray_distanceならpoints normがdepthと
rtol=1e-4 / atol=1e-5（同単位）以内で一致することを確認。
有効Normalsはfinite・unit length（abs tolerance=1e-3）。Kはfinite、正focal、
canonical pinhole bottom row [0,0,1] / K[1,0]=0（abs tolerance=1e-6）とgrid / pixel center metadataを確認。
無効depth / vectorはNaN、mask payloadは0 / 1、valid / invalid統計も照合。
model_mask / effective maskを混同しない。geometry不正は確定前FAILED、確定後ArtifactIntegrityError。

numeric filesは一時NPYへ書きrenameし、geometry値検証後にmetadata / worker reportを
従来のatomic publicationで確定する。
既存raw fileがあれば保存を拒否し、published WorkerResult / JobResultがあるRunのworker再実行も拒否する。
失敗途中のraw / logsは診断として保持し成功出力へ公開しない。再collectは読み取り専用。


## Phase 02B application reads and compatibility

UIのPNG / JPEGは10 MiB / 4,194,304 pixels / edge 4096を上限とし、Pillowで完全decodeする。
PNGは元bytesを保持。JPEGはEXIF orientation補正・RGB変換後のPNGを推論入力にし、
元JPEGを別保存する。JobSpec inputsのoptional `source` に元形式 / SHA-256 / byte数 / 元サイズ /
orientation / Pillow版と変換操作 / 相対pathを保存し、collectで元JPEGのdigestも検証する。
既存のinput path / hash / original_sizeは変換後PNGに対応し、旧RunとCLI契約を維持する。
terminal表示は既存collectのID / path / digest / geometry validation成功後のみpublishする。
UI serviceはRun IDから保存handleをcontained pathで読んで既存collectへ渡し、active recoveryを拒否。
Runner.collectのrun.json publicationはinstance lockを取り、同内容ならwriteを省略する。
複数sessionの同時collectでtemporary fileを競合させず、再表示によるraw / result更新も行わない。
02Cでdownload / viewer / derivedを追加、管理serviceは02D。
詳細は [Gradio Inference](gradio-inference.md#input-and-result-compatibility)。

## Phase 03.1 compatibility

JobSpecのmodel_ref.variantに実効metadata snapshotを加算し、元manifestも保持する。
旧schema 1.0 Runに実効snapshotを要求するreader変更やmigrationは行わない。
01A-depth-only / 02A-geometry-v1のwire format、raw / 確定result不変を維持する。
複数pluginの新instance collectも再推論せず、hash / mtime不変で検証する。


## Phase 03.3 target configuration boundary

Target names / prefixes and local checkpoint paths are configured outside the immutable JobSpec.
Jobs retain logical environment / model / variant and content identities; runtime fingerprint continues to
record the actual selected Python environment. No layout, profile, required output or raw/result semantics change.
Model switching creates a fresh Run, while opening / collecting saved Runs performs no inference or migration.
The two real CPU UI Runs and old saved Runs are checked for hash / mtime immutability after repeated reads.

## Phase 03.5 multi-view records

Single-view JobSpec writers retain schema1.0 and `view-0001` layout. Multi-view Jobs explicitly use
schema1.1 / inference.request_kind=multi_view_v1 and require the new common worker and declared protocol1.1.
The worker currently supports required protocol1.0 / 1.1, records actual version1.1 in execution metadata,
and rejects a required future version1.2. Generic record-schema major compatibility remains unchanged;
known request kinds and required worker features determine execution support, not merely a 1.x label.
Each input / output view uses its assigned `view-NNNN` directory. One attempt remains the only supported
attempt. All input IDs / hashes are included in the ordered request digest.

The existing 01A-depth-only / 02A-geometry-v1 numerical profiles apply independently to every view.
`metadata.json.views` and `outputs` contain all view metadata in input order. Header, shape, validity,
units, provenance, path and checksum checks cover all views, not just the first.

A new optional `scene` ArtifactRef appears in WorkerReport / JobResult and the metadata document:

```json
{
  "schema_version": "1.1",
  "run_id": "<Run ID>",
  "attempt_id": "attempt-0001",
  "view_ids": ["view-0001", "view-0002"],
  "metadata": {"reference_view_id": "view-0001", "scale_type": "relative", "depth_unit": "arbitrary"}
}
```

This is the content of `output/attempt-0001/scene.json`, registered as application/json with size / SHA-256.
The scene ref is mandatory for completed multi-view results. Its exact identity, order and optional
reference / scale / unit fields are validated, and the ref must agree across worker, metadata and terminal
records. A nonempty single-view model scene also emits the new 1.1 result / metadata / scene format;
existing plugins returning empty scene metadata continue writing the legacy format.

Missing scene fields in old Runs are normal and are not rewritten. `JobResult.scene=None` is omitted from
wire output. New readers support legacy records and the opt-in multi-view extension; old single-view
workers / readers are not claimed to understand multiple views. No raw migration is performed.
Unknown scene / extras metadata remains opaque JSON rather than an implicit file reference. Formally
registered scene and per-view artifacts, plus every original input, are included by Run export.
