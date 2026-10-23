"""Opt-in real browser acceptance; installs no packages and never uses a GPU.

MDE_BROWSER_TESTS=1 enables fake LocalBackend browser coverage.
MDE_UI_CPU_SMOKE=1 additionally enables pinned MoGe CPU inference from the UI.
Run from the isolated UI environment with requirements/browser.lock installed.
"""
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import unittest
from urllib.parse import urlparse

PROJECT = Path(__file__).resolve().parents[1]


class BrowserHarness:
    def start(self, models_root, model_id, run_root, port, checkpoint=None):
        import gradio as gr
        from playwright.sync_api import sync_playwright
        from mde.backends import LocalBackend
        from mde.environments import CondaLauncher, EnvironmentProfile, EnvironmentResolver, WorkerManager
        from mde.registry import ModelRegistry
        from mde.runner import ExperimentRunner
        from mde.storage import RunStore
        from mde.ui import build_app
        from mde.ui_controller import InferenceController

        self.store = RunStore(PROJECT, run_root)
        registry = ModelRegistry(models_root)
        info = registry.get_model(model_id)
        env_id = info.data["environment_refs"][0]["environment_id"]
        prefix = os.environ.get("MDE_TEST_CONDA_PREFIX")
        resolver = EnvironmentResolver({env_id: EnvironmentProfile(env_id,
            name=None if prefix else os.environ.get("MDE_TEST_CONDA_ENV", env_id), prefix=prefix)})
        backend = LocalBackend(self.store.root, WorkerManager(PROJECT, resolver, CondaLauncher(), checkpoint))
        self.runner = ExperimentRunner(registry, backend, self.store, PROJECT)
        self.controller = InferenceController(self.runner, model_id)
        self.app = build_app(self.controller)
        self.app.launch(server_name="127.0.0.1", server_port=port, share=False, prevent_thread_lock=True,
            max_file_size=10 * 1024 * 1024, ssr_mode=False, enable_monitoring=False, quiet=True,
            theme=gr.themes.Default(font=["system-ui"], font_mono=["monospace"]), footer_links=[], run_history=False)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            executable_path=os.environ.get("MDE_CHROME_EXE") or shutil.which("google-chrome"),
            headless=True, args=["--no-sandbox"], timeout=15000)
        self.url = f"http://127.0.0.1:{port}"
        self.external, self.requests, self.errors = [], [], []
        self.contexts = []

    def page(self):
        context = self.browser.new_context()
        self.contexts.append(context)
        def route(request):
            host = urlparse(request.request.url).hostname
            if host not in ("127.0.0.1", "localhost", None):
                self.external.append(request.request.url)
                request.abort()
            else:
                request.continue_()
        context.route("**/*", route)
        page = context.new_page()
        page.on("request", lambda r: self.requests.append(r.url))
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(self.url)
        page.locator("#submit-run").wait_for()
        from playwright.sync_api import expect
        expect(page.locator("#job-status textarea")).to_have_value("IDLE", timeout=10000)
        return page

    def select(self, page, selector, value):
        page.locator(selector).locator("input").click()
        page.get_by_role("option", name=value, exact=True).click()

    def upload(self, page, path):
        from playwright.sync_api import expect
        page.locator("#input-png input[type=file]").set_input_files(str(path))
        expect(page.locator("#input-png")).to_contain_text(re.compile(re.escape(path.stem) + r"\s*\.png"), timeout=10000)

    def stop(self):
        for job in list(self.runner.backend._jobs.values()):
            if not self.runner.status(job.handle).status.terminal:
                self.runner.cancel(job.handle, "Browser validation cleanup")
        self.browser.close()
        self.playwright.stop()
        self.app.close()


@unittest.skipUnless(os.environ.get("MDE_BROWSER_TESTS") == "1", "Opt-in browser acceptance")
class FakeBrowserTests(unittest.TestCase, BrowserHarness):
    def test_two_sessions_dispatch_busy_cancel_timeout_failure_results(self):
        from playwright.sync_api import expect
        from PIL import Image
        from mde.storage import read_json, sha256_file
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            alternate = root / "alternate.png"
            Image.new("RGB", (32, 16), (20, 100, 200)).save(alternate)
            self.start(PROJECT / "tests/fixtures/models", "fake", root / "runs", 7861)
            try:
                a, b = self.page(), self.page()
                # Empty upload is rejected, without creating a Run.
                self.select(a, "#device-choice", "cpu")
                a.locator("#submit-run").click()
                expect(a.locator("#action-notice textarea")).to_have_value(re.compile(".*Upload one PNG.*"))
                self.upload(a, PROJECT / "tests/assets/sample.png")
                self.upload(b, alternate)
                self.select(b, "#device-choice", "cpu")
                self.select(a, "#parameter-action", "block")
                a.locator("#submit-run").click()
                expect(a.locator("#job-status textarea")).to_have_value("RUNNING", timeout=20000)
                a_id = a.locator("#active-run-id textarea").input_value()
                started = time.monotonic()
                b.locator("#submit-run").click()
                expect(b.locator("#action-notice textarea")).to_have_value(re.compile(".*BackendBusy.*"), timeout=3000)
                busy_seconds = time.monotonic() - started
                expect(b.locator("#job-status textarea")).to_have_value("IDLE")
                b.locator("#cancel-run").click()
                expect(b.locator("#action-notice textarea")).to_have_value(re.compile("No active.*"))
                expect(a.locator("#job-status textarea")).to_have_value("RUNNING")
                a.locator("#cancel-run").click()
                expect(a.locator("#job-status textarea")).to_have_value(re.compile("CANCELLED.*", re.S), timeout=15000)
                expect(a.locator("#selected-run-id textarea")).to_have_value(a_id)
                # A refused submission must never run later after the slot clears.
                b.wait_for_timeout(800)
                self.assertEqual(len(self.runner.backend._jobs), 1)
                expect(b.locator("#input-png")).to_contain_text(re.compile(r"alternate\s*\.png"))
                b.locator("#submit-run").click()
                expect(b.locator("#job-status textarea")).to_have_value("COMPLETED", timeout=30000)
                b_id = b.locator("#selected-run-id textarea").input_value()
                self.assertNotEqual(a_id, b_id)
                self.assertEqual(read_json(self.store.root / b_id / "job.json")["inputs"][0]["sha256"], sha256_file(alternate))
                expect(a.locator("#selected-run-id textarea")).to_have_value(a_id)
                # Results auto-selected only after validated terminal collect.
                self.assertTrue(b.locator("#validated-result").is_visible())
                # Failure and timeout remain distinct in visible status/error.
                for action, timeout, error in (("raise", 30, "intentional predict failure"), ("block", 1, "TIMEOUT")):
                    b.get_by_role("tab", name="Inference", exact=True).first.click()
                    self.select(b, "#parameter-action", action)
                    b.locator("#timeout-seconds input").fill(str(timeout))
                    b.locator("#submit-run").click()
                    expect(b.locator("#job-status textarea")).to_have_value(re.compile(f"FAILED.*{error}", re.S), timeout=30000)
                    self.assertTrue(b.locator("#validated-result").is_visible())
                # Schedule two physical browser clicks at the same wall-clock
                # instant. Exactly one must get the slot, with no deferred job.
                for page in (a, b):
                    page.get_by_role("tab", name="Inference", exact=True).first.click()
                    self.select(page, "#parameter-action", "block")
                    page.locator("#timeout-seconds input").fill("30")
                target = int(time.time() * 1000) + 500
                for page in (a, b):
                    page.evaluate("target => setTimeout(() => document.querySelector('#submit-run').click(), target - Date.now())", target)
                a.wait_for_timeout(1000)
                messages = [p.locator("#action-notice textarea").input_value() for p in (a, b)]
                self.assertEqual(sum("BackendBusy" in message for message in messages), 1, messages)
                self.assertEqual(sum("accepted" in message for message in messages), 1, messages)
                winner = (a, b)[next(i for i, message in enumerate(messages) if "accepted" in message)]
                winner.locator("#cancel-run").click()
                expect(winner.locator("#job-status textarea")).to_have_value(re.compile("CANCELLED.*", re.S), timeout=15000)
                a.wait_for_timeout(700)
                self.assertEqual(len(self.runner.backend._jobs), 5)
                self.assertFalse(any("/queue/join" in url for url in self.requests))
                self.assertEqual(self.external, [])
                self.assertEqual(self.errors, [])
                print(json.dumps({"browser": self.browser.version, "fake_busy_seconds": busy_seconds,
                    "runs": len(self.runner.backend._jobs), "queue_join_requests": 0,
                    "external_requests": self.external, "page_errors": self.errors}), flush=True)
            finally:
                self.stop()


@unittest.skipUnless(os.environ.get("MDE_UI_CPU_SMOKE") == "1", "Opt-in pinned MoGe CPU UI smoke")
class CPUUIBrowserTests(unittest.TestCase, BrowserHarness):
    def test_pinned_cpu_ui_and_saved_results_without_worker(self):
        from playwright.sync_api import expect
        from mde.backends import LocalBackend
        from mde.runner import ExperimentRunner
        from mde.storage import read_json, sha256_file
        from mde.ui_controller import InferenceController
        checkpoint = Path(os.environ.get("MDE_UI_CHECKPOINT", PROJECT / ".local/weights/moge-2-vits-normal.pt"))
        self.start(PROJECT / "models", "moge", PROJECT / "runs", 7862, checkpoint)
        try:
            page = self.page()
            self.upload(page, PROJECT / "tests/assets/sample.png")
            self.select(page, "#device-choice", "cpu")
            page.locator("#submit-run").click()
            expect(page.locator("#job-status textarea")).to_have_value("COMPLETED", timeout=180000)
            run_id = page.locator("#selected-run-id textarea").input_value()
            self.assertTrue(page.locator("#validated-result").is_visible())
            run = self.store.root / run_id
            result = read_json(run / "attempts/attempt-0001/job-result.json")
            self.assertEqual(result["execution"]["device"], "cpu")
            self.assertNotIn("torch", __import__("sys").modules)
            before = {str(p.relative_to(run)): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
            # Confirm the actual model failure / cancel / timeout UI path too.
            page.get_by_role("tab", name="Inference", exact=True).first.click()
            self.select(page, "#device-choice", "cuda:0")
            page.locator("#submit-run").click()
            expect(page.locator("#job-status textarea")).to_have_value(re.compile("FAILED.*CUDA requested but unavailable.*", re.S), timeout=60000)
            cuda_run_id = page.locator("#selected-run-id textarea").input_value()
            page.get_by_role("tab", name="Inference", exact=True).first.click()
            self.select(page, "#device-choice", "cpu")
            page.locator("#submit-run").click()
            expect(page.locator("#job-status textarea")).to_have_value("RUNNING", timeout=15000)
            page.locator("#cancel-run").click()
            expect(page.locator("#job-status textarea")).to_have_value(re.compile("CANCELLED.*", re.S), timeout=15000)
            cancel_run_id = page.locator("#selected-run-id textarea").input_value()
            page.get_by_role("tab", name="Inference", exact=True).first.click()
            page.locator("#timeout-seconds input").fill("1")
            page.locator("#submit-run").click()
            expect(page.locator("#job-status textarea")).to_have_value(re.compile("FAILED.*TIMEOUT.*", re.S), timeout=15000)
            timeout_run_id = page.locator("#selected-run-id textarea").input_value()
            # A fresh application backend with no WorkerManager reopens the same Run.
            self.controller = InferenceController(ExperimentRunner(self.runner.registry,
                LocalBackend(self.store.root), self.store, PROJECT), "moge")
            # Restart the Gradio application and browser session, retaining saved files.
            self.app.close()
            import gradio as gr
            from mde.ui import build_app
            self.app = build_app(self.controller)
            self.app.launch(server_name="127.0.0.1", server_port=7862, share=False, prevent_thread_lock=True,
                quiet=True, ssr_mode=False, enable_monitoring=False,
                theme=gr.themes.Default(font=["system-ui"], font_mono=["monospace"]), footer_links=[], run_history=False)
            saved = self.page()
            saved.get_by_role("tab", name="Results", exact=True).first.click()
            saved.locator("#saved-run-id textarea").fill(run_id)
            saved.locator("#open-saved-run").click()
            expect(saved.locator("#selected-run-id textarea")).to_have_value(run_id, timeout=15000)
            after = {str(p.relative_to(run)): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(self.external, [])
            self.assertEqual(self.errors, [])
            self.assertFalse(any("/queue/join" in url for url in self.requests))
            print(json.dumps({"cpu_ui_run_id": run_id, "browser": self.browser.version,
                "status": result["status"], "runtime": {key: result["execution"].get(key) for key in
                    ("python_version", "torch_version", "torch_cuda_runtime", "cuda_available", "device", "serialization_profile")},
                "cuda_failure_run_id": cuda_run_id, "cancel_run_id": cancel_run_id, "timeout_run_id": timeout_run_id,
                "metrics": result.get("metrics", {}),
                "external_requests": self.external, "saved_reload_all_files_unchanged": True}), flush=True)
        finally:
            self.stop()
