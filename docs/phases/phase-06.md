# Phase 06 — Execution Backend Expansion

Status: 未着手・未承認。
管理: [PLANS.md](../../PLANS.md)。

## Goal

Phase 01 から使っている ExecutionBackend abstraction が Local 固有実装に依存していないことを
MockSlurmBackend 等で実証し、非同期状態・取消・再収集・障害回復をローカルで検証する。

## Background

自宅から研究室 Slurm を使えないため、実機アクセスなしで public contracts と状態遷移を検証する。
Mock を通過しても研究室の sbatch policy / NFS を検証したことにはならない。

## Scope

injectable clock / executor / command adapter、MockSlurmBackend、Backend contract test suite、
backend catalog / profile selection、submit reconciliation、publication delay simulation。
実モデルとの組合せは必要最小限の Local regression に限る。

## Non-goals

研究室固有 SlurmBackend の完成、実 sbatch / squeue / sacct / scancel の実行、SSH / VPN 接続、
NFS 実在の仮定、production scheduler emulator、model × backend 固有クラス。

## Dependencies

Phase 01–05 の公開 API、[ExecutionBackend spec](../execution-backend-spec.md)、
[Run Directory](../run-directory-spec.md)、[Slurm design](../slurm-integration.md)。
fake と Local で同じ Result contract を使用する。

## Implementation tasks

- [ ] backend factory / catalog を metadata と runtime instance に分ける。
- [ ] mock state machine と fake clock で queue / run / terminal states を制御。
- [ ] command adapter fixtures と Store failure injection を用意。
- [ ] response loss / duplicate submit / stale status / UNKNOWN / missing report を再現。
- [ ] queued / running cancel、completion race、process / controller restart を検証。
- [ ] immutable terminal、attempt retry、collect 冪等性、identity conflict の契約を固める。
- [ ] Runner / UI / Tracking が同じ JobSpec で backend を差し替えられることを確認。
- [ ] Local regression と docs の必要な変更を互換性込みで更新。

## Tests

- QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED と queue cancel。
- status 通信失敗で FAILED へ変わらない、古い観測で状態が戻らない。
- submit acknowledgement 喪失後、reconciliation 前に二重実行しない。
- required artifact の遅延 / checksum failure / worker crash / cancellation。
- 同じ handle の繰り返し collect、run / attempt / backend ID の不一致。
- retry で旧 output が残り、terminal attempt の状態を変更しない。
- fake MoGe / UniK3D / DA3 metadata × Local / Mock の組合せをモデル固有 backend コードなしで処理。
- Tests は injected clock により deterministic にし、長い sleep を必須にしない。

## Exit criteria

共通 Backend contract tests が Local と Mock で通り、UI / Runner / Tracking の model / backend 固有
分岐を追加せず差し替えできる。UNKNOWN / cancel / retry / publication delay / recovery が仕様通り。
Mock が保証しない実機条件を列挙し、Phase 07 の確認項目へ引き継ぐ。

## Known risks

Mock が実 Slurm の parser / accounting / requeue / NFS を単純化しすぎる可能性、
偶然 Local path / PID / environment が Runner に漏れる可能性、再起動時の多重 submit。

## Decisions deferred to later phases

07: installed Slurm version、actual CLI formats、site profiles、resource mapping。
08: accounting delay / NFS visibility / node failure の実挙動。
native requeue / job arrays / multi-node は対応可否を現地で確認して scope を別に決める。

## Decisions

| Decision | Reason | Trade-off | Future extension |
| --- | --- | --- | --- |
| Mock に injectable clock / Store を使う | cluster / GPU なしで障害を再現 | 実 OS / scheduler の証明ではない | 実機 fixture と integration tests |
| Local と Mock に共通 contract suite | abstraction の抜けを早期に見つける | fake-only convenience API を避ける必要 | real Slurm に同じ suite を適用 |
