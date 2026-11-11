"""Gradio composition root. Run with ``python -m mde.ui --help``.

Callbacks only call the application controller. Worker provisioning belongs to
the existing environment/Backend layer, configured once at startup below.
"""
import argparse
import json
import os
from pathlib import Path
import uuid

# Set before importing Gradio; the worker environment remains independent.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from .ui_controller import InferenceController, MAX_UPLOAD_BYTES


def build_app(controller):
    import gradio as gr
    from .results import ResultsService
    from .run_management import RunManagementService

    assets = Path(__file__).with_name("viewer_assets")
    gr.set_static_paths(paths=[assets / "vendor"])
    results_service = ResultsService(controller.runner.store, controller.runner.collect)
    management = RunManagementService(controller.runner.store, controller.runner.collect)

    def render_view(request):
        try:
            return results_service.view(request["run_id"], request["mode"])
        except Exception as error:
            return {"error": str(error)}

    info = controller.info.data
    catalog = controller.runner.registry.discover()
    models = {item.model_id: item for item in catalog.models}
    event = dict(queue=False, concurrency_limit=None, trigger_mode="once",
                 api_visibility="private", show_progress="hidden")

    def guard(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            return f"{type(error).__name__}: {error}"

    def text_guard(fn, *args):
        value = guard(fn, *args)
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    with gr.Blocks(title="MGE Experiment Platform", analytics_enabled=False) as app:
        token = gr.State(value=None, delete_callback=controller.forget)
        # A JSON component emits frontend change events for nonqueued responses;
        # the authoritative ticket / selection remains in the server session.
        configuration = gr.JSON(value=None, visible=False)
        last_view = gr.State(value=None)
        operation_generation = gr.State(value=0)
        gr.Markdown("# MGE Experiment Platform\nLocal inference · one shared worker · no job queue")
        with gr.Tabs(selected="inference") as tabs:
            with gr.Tab("Inference", id="inference"):
                with gr.Row():
                    model = gr.Dropdown([(item.data["display_name"], item.model_id) for item in catalog.models],
                        value=controller.model_id, label="Model", interactive=False, elem_id="model-choice")
                    variant = gr.Dropdown([v["variant_id"] for v in info["variants"]],
                                          value=info["default_variant"], label="Variant", interactive=False, elem_id="variant-choice")
                    gr.Textbox(value="local", label="Backend", interactive=False)
                upload = gr.File(label="Input PNG / JPEG (10 MiB; 4,194,304 pixels; edge ≤ 4096)",
                                 file_types=[".png", ".jpg", ".jpeg"], type="filepath", elem_id="input-png")
                if catalog.diagnostics:
                    gr.JSON(catalog.diagnostics, label="Unavailable plugin manifests")
                parameter_area = gr.Column()
                cancel = gr.Button("Cancel this session's job", elem_id="cancel-run", interactive=False)
                notice = gr.Textbox(label="Action", interactive=False, elem_id="action-notice")
                run_id = gr.Textbox(label="Run ID", interactive=False, elem_id="active-run-id")
                status = gr.Textbox(value="IDLE", label="Status", interactive=False, elem_id="job-status")
                gr.Markdown("Progress: unavailable (indeterminate while running). CUDA failures do not fall back to CPU.")
            with gr.Tab("Results", id="results"):
                gr.Markdown("Validated result details. Missing measurements are unavailable.\n"
                            "Views use saved artifacts; Mesh is derived and saved on first request.")
                saved_id = gr.Textbox(label="Saved terminal Run ID", elem_id="saved-run-id")
                open_saved = gr.Button("Open saved Run", elem_id="open-saved-run")
                open_notice = gr.Textbox(label="Load action", interactive=False, elem_id="load-notice")
                result_id = gr.Textbox(label="Selected Run ID", interactive=False, elem_id="selected-run-id")
                viewer = gr.HTML(value="", html_template=(assets / "viewer.html").read_text(),
                    js_on_load=(assets / "viewer.js").read_text().replace("__ASSET_URL__",
                        "/gradio_api/file=" + (assets / "vendor").as_posix()),
                    server_functions=[render_view], elem_id="results-viewer",
                    css_template=".viewer-controls {display:flex;gap:16px;flex-wrap:wrap} select, button {padding:6px;border:1px solid #888;border-radius:4px} pre {font-size:13px} [data-message] {white-space:pre-line}")
                result = gr.JSON(label="Validated JobResult", elem_id="validated-result")
                with gr.Accordion("Run management", open=False):
                    management_selection = gr.State(value=None)
                    deletion = gr.State(value=None)
                    include_archived = gr.Checkbox(label="Include archived Runs")
                    refresh = gr.Button("Refresh history")
                    history = gr.JSON(label="Run history")
                    inspect_run = gr.Button("Inspect saved Run ID")
                    details = gr.JSON(label="Run details and provenance")
                    display_name = gr.Textbox(label="Display name")
                    notes = gr.Textbox(label="Notes")
                    archived = gr.Checkbox(label="Archived (files are retained)")
                    save_metadata = gr.Button("Save metadata / archive status")
                    regenerate = gr.Button("Regenerate Mesh (new generation)")
                    export_run = gr.Button("Export validated input / raw / derived")
                    download_export = gr.HTML()
                    generation = gr.Textbox(label="Derived path to delete (blank = entire Run)")
                    prepare = gr.Button("Review deletion")
                    review = gr.JSON(label="Deletion confirmation")
                    typed_id = gr.Textbox(label="Type the exact Run ID to confirm deletion")
                    with gr.Row():
                        confirm = gr.Button("Confirm deletion")
                        dismiss = gr.Button("Cancel deletion")
                    with gr.Accordion("Retry an interrupted Run deletion", open=False):
                        retry_state = gr.State(value=None)
                        quarantine_entry = gr.Textbox(label="Quarantine entry from failure diagnostic")
                        review_retry = gr.Button("Review deletion retry")
                        retry_details = gr.JSON(label="Retry confirmation")
                        retry_typed = gr.Textbox(label="Type exact Run ID for retry")
                        confirm_retry = gr.Button("Confirm deletion retry")
                        cancel_retry = gr.Button("Cancel deletion retry")
                    management_notice = gr.Textbox(label="Management action", interactive=False)

        timer = gr.Timer(0.5)

        def poll(session, previous):
            if session is None:
                return [gr.skip()] * 8
            view = controller.snapshot(session)
            if view == previous:
                return [gr.skip()] * 8
            value = view["result"]
            display = view["status"]
            if view.get("cancel_requested"):
                display += " · cancel_requested"
            for key in ("reason", "error", "action_error", "observation_error"):
                if view.get(key):
                    display += f"\n{key}: {view[key]}"
            if value and value.get("error"):
                display += "\n" + json.dumps(value["error"], ensure_ascii=False)
            new_result = value is not None and (previous is None or previous.get("result") is None
                                               or previous["generation"] != view["generation"])
            return (view["run_id"], display, view["run_id"] if value else "", value,
                    gr.Tabs(selected="results") if new_result else gr.skip(), view,
                    view["run_id"] if new_result else ("" if previous and previous.get("result") and not value else gr.skip()),
                    view.get("load_notice", ""))

        def open_run(session, selected):
            try:
                controller.open_run(session, selected)
            except Exception as error:
                controller.load_error(session, error)

        def inspect_management(selected):
            try:
                detail = management.detail(selected.strip())
                meta = detail["user_metadata"]
                return detail, detail, meta["display_name"], meta["notes"], meta["archived"], None, None, "Loaded management selection"
            except Exception as error:
                return None, None, "", "", False, None, None, str(error)

        def managed_action(selection, selected, operation, *args):
            if not selection or selection["run_id"] != selected.strip():
                raise ValueError("Inspect the selected Run again before this operation")
            run_id = selection["run_id"]
            if operation == "save":
                return management.update_metadata(run_id, selection["user_metadata"]["revision"],
                    display_name=args[0], notes=args[1], archived=args[2])
            if operation == "regenerate":
                return management.regenerate_derived(run_id)
            if operation == "prepare":
                return management.prepare_delete(run_id, generation=args[0].strip() or None)
            if operation == "delete":
                if not args[0] or args[0]["generation"] != (args[2].strip() or None):
                    raise ValueError("Deletion scope changed; review again")
                return management.delete(args[0], run_id, typed_run_id=args[1])
            if operation == "export":
                import base64
                data = base64.b64encode(management.export(run_id)).decode()
                return f'<a download="{run_id}.zip" href="data:application/zip;base64,{data}">Download export ZIP</a>'

        saved_id.input(lambda: (None, None, None), outputs=[management_selection, deletion, review], **event)
        refresh.click(lambda show: guard(management.list_runs, show), include_archived, history, **event)
        inspect_run.click(inspect_management, saved_id,
            [management_selection, details, display_name, notes, archived, deletion, review, management_notice], **event)
        save_metadata.click(lambda selection, selected, name, note, archive: text_guard(managed_action,
            selection, selected, "save", name, note, archive),
            [management_selection, saved_id, display_name, notes, archived], management_notice, **event)
        regenerate.click(lambda selection, selected: text_guard(managed_action, selection, selected, "regenerate"),
            [management_selection, saved_id], management_notice, **event)
        export_run.click(lambda selection, selected: guard(managed_action, selection, selected, "export"),
            [management_selection, saved_id], download_export, **event)

        def prepare_retry(entry):
            try:
                value = management.prepare_retry(entry.strip())
                return value, value, "Deletion retry review ready"
            except Exception as error:
                return None, {"error": str(error)}, str(error)

        def retry_action(confirmation, typed, entry):
            if not confirmation or confirmation["quarantine_name"] != entry.strip():
                raise ValueError("Retry target changed; review again")
            return management.retry_delete(confirmation, typed_run_id=typed)

        quarantine_entry.input(lambda: (None, None), outputs=[retry_state, retry_details], **event)
        review_retry.click(prepare_retry, quarantine_entry, [retry_state, retry_details, management_notice], **event)
        confirm_retry.click(lambda confirmation, typed, entry: text_guard(retry_action, confirmation, typed, entry),
            [retry_state, retry_typed, quarantine_entry], management_notice, **event)
        cancel_retry.click(lambda: (None, None, "Deletion retry cancelled"),
            outputs=[retry_state, retry_details, management_notice], **event)

        def prepare_management(selection, selected, target):
            try:
                confirmation = managed_action(selection, selected, "prepare", target)
                return confirmation, confirmation, "Deletion review ready"
            except Exception as error:
                return None, {"error": str(error)}, str(error)
        prepare.click(prepare_management, [management_selection, saved_id, generation], [deletion, review, management_notice], **event)
        dismiss.click(lambda: (None, None, "Deletion cancelled"), outputs=[deletion, review, management_notice], **event)
        confirm.click(lambda selection, selected, confirmation, typed, target: text_guard(managed_action,
            selection, selected, "delete", confirmation, typed, target),
            [management_selection, saved_id, deletion, typed_id, generation], management_notice, **event)

        def select_configuration(session, selected_model, selected_variant, previous):
            selected_info = models[selected_model]
            valid = {v["variant_id"] for v in selected_info.data["variants"]}
            if (not previous or previous['model_id'] != selected_model or selected_variant not in valid):
                selected_variant = selected_info.data["default_variant"]
            selected = controller.configure(session, selected_model, selected_variant)
            return gr.Dropdown(choices=sorted(valid), value=selected_variant), selected

        # A single nonqueued event serializes selection responses per browser and
        # keeps its final input. It never submits or waits for an inference slot.
        gr.on([model.input, variant.input], select_configuration, [token, model, variant, configuration],
            [variant, configuration], **{**event, "trigger_mode": "always_last"})

        with parameter_area:
            @gr.render(inputs=[token, configuration], triggers=[configuration.change],
                       queue=False, trigger_mode="always_last", show_progress="hidden")
            def render_parameters(session, selected):
                if session is None or selected is None:
                    return
                metadata = selected["variant"]
                readiness = selected["preparation"]
                gr.Markdown(readiness["message"], elem_id="model-preparation")
                with gr.Row():
                    device = gr.Dropdown(metadata["supported_devices"], value=None, label="Device (choose explicitly)",
                                         elem_id="device-choice", interactive=True)
                    dtype = gr.Dropdown(metadata["supported_dtypes"], value=metadata["supported_dtypes"][0], label="Dtype", interactive=True)
                    timeout = gr.Number(value=300, precision=0, minimum=1,
                        label="Timeout (seconds, includes worker startup)", elem_id="timeout-seconds", interactive=True)
                controls, names = [], []
                gr.Markdown("### Model parameters")
                for name, rule in metadata["parameter_schema"].get("properties", {}).items():
                    options = dict(label=name, value=rule.get("default"), elem_id=f"parameter-{name}", interactive=True)
                    if "enum" in rule:
                        control = gr.Dropdown(rule["enum"], **options)
                    elif rule["type"] in ("integer", "number"):
                        control = gr.Number(precision=0 if rule["type"] == "integer" else None,
                            minimum=rule.get("minimum"), maximum=rule.get("maximum"), **options)
                    elif rule["type"] == "boolean":
                        control = gr.Checkbox(**options)
                    else:
                        control = gr.Textbox(**options)
                    names.append(name); controls.append(control)
                from .contracts import OUTPUT_NAMES
                outputs = gr.CheckboxGroup([name for name in OUTPUT_NAMES if
                    metadata["capabilities"].get(name, {}).get("status") in ("supported", "conditional")],
                    value=["depth"], label="Requested artifacts (depth required)", elem_id="requested-artifacts", interactive=True)
                with gr.Accordion("Declared capabilities and parameter schema", open=False):
                    gr.JSON({"capabilities": metadata["capabilities"], "parameter_schema": metadata["parameter_schema"]})
                submit = gr.Button("Run inference", variant="primary", elem_id="submit-run", interactive=readiness["available"])

                def submit_job(session, image, selected_device, selected_dtype, seconds, requested, *values):
                    try:
                        message = controller.submit(session, image, selected["variant_id"], selected_device,
                            selected_dtype, dict(zip(names, values)), seconds, requested,
                            model_id=selected["model_id"], configuration_ticket=selected["ticket"])
                    except Exception as error:
                        message = f"{type(error).__name__}: {error}"
                    return message, controller.snapshot(session)["generation"]

                submit.click(submit_job, [token, upload, device, dtype, timeout, outputs, *controls],
                             [notice, operation_generation], **event)

        cancel.click(controller.cancel, [token, operation_generation], notice, **event)
        open_saved.click(open_run, [token, saved_id], **event)
        # This is the sole writer for status, Results, and tab selection. Timer
        # trigger_mode=once prevents overlapping/stale poll responses in a browser.
        timer.tick(poll, [token, last_view], [run_id, status, result_id, result, tabs, last_view, viewer, open_notice], **event)
        def initialize():
            session = uuid.uuid4().hex
            selected = controller.configure(session, controller.model_id)
            return (session, selected, gr.Dropdown(interactive=True), gr.Dropdown(interactive=True),
                    gr.Button(interactive=True))
        app.load(initialize, outputs=[token, configuration, model, variant, cancel], **event)
    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="MGE local Gradio application (single process)")
    parser.add_argument("--model", required=True, help="Initial model ID from Registry metadata")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-root", type=Path)
    env = parser.add_mutually_exclusive_group()
    env.add_argument("--conda-env")
    env.add_argument("--conda-prefix")
    parser.add_argument("--conda-exe")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--target-config", type=Path, help="Local environment and per-variant checkpoint map")
    parser.add_argument("--read-only", action="store_true", help="Read terminal Runs without a model environment")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args(argv)
    from .backends import LocalBackend
    from .environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
    from .registry import ModelRegistry
    from .runner import ExperimentRunner
    from .storage import RunStore
    from .targets import TargetConfiguration

    root = args.project_root.resolve()
    store = RunStore(root, args.run_root)
    registry = ModelRegistry(root / "models")
    info = registry.get_model(args.model)
    targets = TargetConfiguration.read(args.target_config) if args.target_config else TargetConfiguration()
    manager = None
    if not args.read_only:
        environment_id = info.environment()["environment_id"]
        if args.conda_env or args.conda_prefix or not args.target_config:
            targets.profiles[environment_id] = EnvironmentProfile(environment_id,
                name=None if args.conda_prefix else args.conda_env or environment_id, prefix=args.conda_prefix)
        initial_key = f'{args.model}/{info.variant()["variant_id"]}'
        initial_checkpoint = args.checkpoint or (os.environ.get('MDE_CHECKPOINT_PATH') if not args.target_config else None)
        if initial_checkpoint:
            targets.checkpoints[initial_key] = Path(initial_checkpoint).resolve()
        elif not args.target_config:
            # Preserve the initial model's pre-existing offline cache behavior.
            targets.cached_checkpoints.add(initial_key)
        manager = WorkerManager(root, EnvironmentResolver(targets.profiles), CondaLauncher(args.conda_exe),
                                checkpoints=targets.checkpoints)
    if args.read_only:
        targets = TargetConfiguration()
    backend = LocalBackend(store.root, manager)
    controller = InferenceController(ExperimentRunner(registry, backend, store, root), args.model, targets=targets)
    app = build_app(controller)
    app.launch(server_name="127.0.0.1", server_port=args.port, share=False, inbrowser=False,
               max_file_size=MAX_UPLOAD_BYTES, enable_monitoring=False, ssr_mode=False,
               theme=__import__("gradio").themes.Default(font=["system-ui"], font_mono=["monospace"]),
               footer_links=[], run_history=False)


if __name__ == "__main__":
    main()
