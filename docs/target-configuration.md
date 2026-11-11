# Local target configuration — Phase 03.3

`--target-config` is optional for CLI and Gradio. It maps logical environment IDs to local Conda
names / prefixes and model / variant IDs to local checkpoint locations. Model adapters do not
select a backend or environment, and Registry reads metadata without provisioning anything.

The [example](../configs/local-targets.example.json) contains MoGe and DA3. Edit a local copy for
your machine; paths resolve relative to the configuration file's directory. Never commit personal
prefixes, weights or credentials. Configuration loading performs no install or download.

```bash
# From the repository root; adjust paths in your own copy as needed.
PYTHONPATH=src .local/envs/mde-ui/bin/python -m mde.ui --model moge \
  --target-config configs/local-targets.example.json
PYTHONPATH=src python -m mde.cli run --model da3 --device cpu \
  --input tests/assets/sample.png --target-config configs/local-targets.example.json
```

The JSON record uses `schema_version: "1.0"`, optional `environments` and `checkpoints` objects.
Each environment value contains exactly one nonempty `name` or `prefix`; base is rejected.
Checkpoint keys are `model_id/variant_id`, values are local paths. A path may name a file or directory;
the selected adapter validates its own pinned files and digests. Unknown fields / malformed IDs /
ambiguous profiles / duplicate JSON keys / non-finite values are rejected.

CLI's explicit `--conda-env` / `--conda-prefix` and `--checkpoint` override only the selected job.
Without a target file the previous single-job CLI behavior, including the model's offline cache path,
is preserved. `--environment-id` selects among multiple declared logical references; ambiguity is refused.

Gradio uses `--model` only as the initial selection. Legacy environment / checkpoint flags configure
that initial model / default variant, while other entries come from the target file. Without a target
file, the initial model retains its existing offline cache behavior if no checkpoint was specified.
An inherited `MDE_CHECKPOINT_PATH` is scoped to that initial selection. It is never reused for another
model or variant. A target map suppresses inherited checkpoint values and resolves each worker's
checkpoint from the immutable JobSpec model / variant snapshot.

UI preparation metadata checks registered environments, an existing Python under explicit prefixes,
and configured checkpoint path presence. Missing entries / paths appear as **未準備 / Unprepared** and
disable inference. A configured Conda name, package installation, native dependencies and file digests
are checked by the launcher / worker; the UI says “Target configured”, not that runtime validation
has already succeeded. Changing a target file or installing an environment requires restarting the app.
`--read-only` enables saved terminal Run access without starting a model environment.

Host prefixes and local checkpoint paths stay in target configuration and worker launch context;
JobSpec retains logical environment / model / variant / checkpoint identity and content digests.
The same shared Backend serves all browser sessions, with immediate busy rejection and no job queue.
