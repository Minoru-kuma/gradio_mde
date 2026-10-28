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

    assets = Path(__file__).with_name("viewer_assets")
    gr.set_static_paths(paths=[assets / "vendor"])
    results_service = ResultsService(controller.runner.store, controller.runner.collect)

    def render_view(request):
        try:
            return results_service.view(request["run_id"], request["mode"])
        except Exception as error:
            return {"error": str(error)}

    info = controller.info.data
    event = dict(queue=False, concurrency_limit=None, trigger_mode="once",
                 api_visibility="private", show_progress="hidden")

    def guard(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            return f"{type(error).__name__}: {error}"

    with gr.Blocks(title="MGE Experiment Platform", analytics_enabled=False) as app:
        token = gr.State(value=None, delete_callback=controller.forget)
        last_view = gr.State(value=None)
        operation_generation = gr.State(value=0)
        gr.Markdown("# MGE Experiment Platform\nLocal inference · one shared worker · no job queue")
        with gr.Tabs(selected="inference") as tabs:
            with gr.Tab("Inference", id="inference"):
                with gr.Row():
                    model = gr.Textbox(value=info["display_name"], label="Model", interactive=False)
                    variant = gr.Dropdown([v["variant_id"] for v in info["variants"]],
                                          value=info["default_variant"], label="Variant", elem_id="variant-choice")
                    gr.Textbox(value="local", label="Backend", interactive=False)
                upload = gr.File(label="Input PNG / JPEG (10 MiB; 4,194,304 pixels; edge ≤ 4096)",
                                 file_types=[".png", ".jpg", ".jpeg"], type="filepath", elem_id="input-png")
                with gr.Row():
                    device = gr.Dropdown(info["supported_devices"], value=None, label="Device (choose explicitly)",
                                         elem_id="device-choice")
                    dtype = gr.Dropdown(info["supported_dtypes"], value=info["supported_dtypes"][0], label="Dtype")
                    timeout = gr.Number(value=300, precision=0, minimum=1, label="Timeout (seconds, includes worker startup)",
                                        elem_id="timeout-seconds")
                controls, names = [], []
                gr.Markdown("### Model parameters")
                for name, rule in info.get("parameter_schema", {}).get("properties", {}).items():
                    options = dict(label=name, value=rule.get("default"), elem_id=f"parameter-{name}")
                    if "enum" in rule:
                        control = gr.Dropdown(rule["enum"], **options)
                    elif rule["type"] in ("integer", "number"):
                        control = gr.Number(precision=0 if rule["type"] == "integer" else None,
                                            minimum=rule.get("minimum"), maximum=rule.get("maximum"), **options)
                    elif rule["type"] == "boolean":
                        control = gr.Checkbox(**options)
                    else:
                        control = gr.Textbox(**options)
                    names.append(name)
                    controls.append(control)
                capabilities = info["variants"][0].get("capabilities", info["capabilities"])
                from .contracts import OUTPUT_NAMES
                outputs = gr.CheckboxGroup([key for key in OUTPUT_NAMES if
                    capabilities.get(key, {}).get("status") in ("supported", "conditional")],
                    value=["depth"], label="Requested artifacts (depth required)", elem_id="requested-artifacts")
                with gr.Accordion("Declared capabilities and parameter schema", open=False):
                    gr.JSON({"variants": [{"variant_id": v["variant_id"], "capabilities":
                        v.get("capabilities", info["capabilities"])} for v in info["variants"]],
                        "parameter_schema": info.get("parameter_schema", {})})
                with gr.Row():
                    submit = gr.Button("Run inference", variant="primary", elem_id="submit-run", interactive=False)
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
        timer = gr.Timer(0.5)

        def submit_job(session, image, selected_variant, selected_device, selected_dtype, seconds, requested, *values):
            message = guard(controller.submit, session, image, selected_variant, selected_device, selected_dtype,
                            dict(zip(names, values)), seconds, requested)
            return message, controller.snapshot(session)["generation"]

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

        submit.click(submit_job, [token, upload, variant, device, dtype, timeout, outputs, *controls],
                     [notice, operation_generation],
                     **event)
        cancel.click(controller.cancel, [token, operation_generation], notice, **event)
        open_saved.click(open_run, [token, saved_id], **event)
        # This is the sole writer for status, Results, and tab selection. Timer
        # trigger_mode=once prevents overlapping/stale poll responses in a browser.
        timer.tick(poll, [token, last_view], [run_id, status, result_id, result, tabs, last_view, viewer, open_notice], **event)
        app.load(lambda: (uuid.uuid4().hex, gr.Button(interactive=True), gr.Button(interactive=True)),
                 outputs=[token, submit, cancel], **event)
    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="MGE local Gradio application (single process)")
    parser.add_argument("--model", required=True, help="One prepared model ID from Registry metadata")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-root", type=Path)
    env = parser.add_mutually_exclusive_group()
    env.add_argument("--conda-env")
    env.add_argument("--conda-prefix")
    parser.add_argument("--conda-exe")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--read-only", action="store_true", help="Read terminal Runs without a model environment")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args(argv)
    from .backends import LocalBackend
    from .environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
    from .registry import ModelRegistry
    from .runner import ExperimentRunner
    from .storage import RunStore

    root = args.project_root.resolve()
    store = RunStore(root, args.run_root)
    registry = ModelRegistry(root / "models")
    info = registry.get_model(args.model)
    manager = None
    if not args.read_only:
        environment_id = info.data["environment_refs"][0]["environment_id"]
        resolver = EnvironmentResolver({environment_id: EnvironmentProfile(
            environment_id, name=None if args.conda_prefix else args.conda_env or environment_id,
            prefix=args.conda_prefix)})
        manager = WorkerManager(root, resolver, CondaLauncher(args.conda_exe), args.checkpoint)
    backend = LocalBackend(store.root, manager)
    controller = InferenceController(ExperimentRunner(registry, backend, store, root), args.model)
    app = build_app(controller)
    app.launch(server_name="127.0.0.1", server_port=args.port, share=False, inbrowser=False,
               max_file_size=MAX_UPLOAD_BYTES, enable_monitoring=False, ssr_mode=False,
               theme=__import__("gradio").themes.Default(font=["system-ui"], font_mono=["monospace"]),
               footer_links=[], run_history=False)


if __name__ == "__main__":
    main()
