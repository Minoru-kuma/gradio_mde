# Run Directory specification

Status: 設計のみ。今回 `runs/` や実データを作成しない。
関連: [Job contracts](execution-backend-spec.md)、[MDEOutput](model-adapter-spec.md)、
[MLflow](mlflow-design.md)、[Slurm](slurm-integration.md)。

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
    views/<view_id>/image.png       # 入力コピー。checksum / 元画像情報は job に保存
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
5. Runner は JobResult を使って logical run と Tracking を更新する。

異なる filesystem 間の rename は atomic と仮定しない。atomic rename も NFS client 間の即時可視性や
停電時 durability を保証しない。bounded publication grace / checksum / reader retry を設け、
研究室 NFS の実挙動を Phase 08 で検証する。half-written report を成功として読まない。

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
- application 再起動は run / handle / terminal result を読み直す。stale RUNNING は process / scheduler を
  調べて reconcile し、directory だけを根拠に再 submit しない。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| root を設定、payload は relative refs | Local と NFS の mount path を分離 | target Store resolution が必要 | object storage / staging backend |
| attempt 別 output / logs | retry で成果と失敗証拠を失わない | directory の階層が一段増える | execution instance / scheduler requeue |
| WorkerResult と確定 JobResult を分ける | worker 未起動や scheduler failure も表現する | report が二段になる | reconciliation / audit tooling |
| file manifest を最後に publish | 読み手が partial artifacts を成功扱いしない | file validation と publication grace が必要 | NFS / remote Store の専用 writer |
