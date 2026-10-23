import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from mde.backends import LocalBackend
from mde.registry import ModelRegistry
from mde.runner import ExperimentRunner
from mde.storage import RunStore
from mde.ui_controller import InferenceController

PROJECT = Path(__file__).resolve().parents[1]


class UIBoundaryTests(unittest.TestCase):
    def test_model_imports_and_execution_stay_out_of_callbacks(self):
        paths = [PROJECT / "src/mde" / name for name in ("ui.py", "ui_controller.py", "registry.py")]
        for path in paths:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    self.assertFalse(any(m.startswith(("torch", "models.", "subprocess")) for m in modules), path)
        self.assertNotIn("torch", sys.modules)
        self.assertFalse(any(m.startswith("models.moge") for m in sys.modules))

    @unittest.skipUnless(importlib.util.find_spec("gradio"), "Independent UI environment required")
    def test_every_event_bypasses_queue_and_single_poll_writes_results(self):
        from mde.ui import build_app
        with tempfile.TemporaryDirectory() as temporary:
            store = RunStore(PROJECT, Path(temporary))
            controller = InferenceController(ExperimentRunner(ModelRegistry(PROJECT / "models"),
                LocalBackend(store.root), store, PROJECT), "moge")
            app = build_app(controller)
            events = app.config["dependencies"]
            self.assertEqual(len(events), 5)
            self.assertTrue(all(e["queue"] is False for e in events))
            self.assertTrue(all(e["trigger_mode"] == "once" for e in events))
            # No inference listener owns status or Results outputs. One timer is
            # the sole writer, so poll HTTP responses cannot overtake one another.
            polls = [e for e in events if any(target[1] == "tick" for target in e["targets"])]
            self.assertEqual(len(polls), 1)
            poll_outputs = set(polls[0]["outputs"])
            for event in events:
                if event is not polls[0]:
                    self.assertFalse(set(event["outputs"]) & poll_outputs)
            self.assertFalse(app.analytics_enabled)
