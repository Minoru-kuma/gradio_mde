"""Session configuration tickets and immutable model snapshots across UI changes."""
import tempfile
import threading
from pathlib import Path
import unittest
from unittest.mock import patch

from mde.contracts import BackendBusy,JobStatus
from mde.ui_controller import InferenceController,stage_upload
from tests import test_ui_controller as controller_tests
from tests.test_ui_controller import FakeRunner,HAS_PIL,IMAGE


class RecordingRunner(FakeRunner):
    def __init__(self,root):
        super().__init__(root);self.requests=[]
    def submit(self,model,image,**options):
        self.requests.append({'model':model,**options})
        return super().submit(model,image,**options)


@unittest.skipUnless(HAS_PIL,'Independent UI environment required')
class ModelSelectionTests(unittest.TestCase):
    cleanup=controller_tests.ControllerTests.cleanup
    wait=controller_tests.ControllerTests.wait
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.runner=RecordingRunner(Path(self.temp.name))
        self.controller=InferenceController(self.runner,'fake',poll_interval=.005)
        self.addCleanup(self.cleanup)

    def submit_selection(self,token,selected,**options):
        values=dict(image=IMAGE,variant_id=selected['variant_id'],device='cpu',dtype='float32',parameters={},
                    timeout=30,outputs=['depth'],model_id=selected['model_id'],configuration_ticket=selected['ticket'])
        values.update(options);return self.controller.submit(token,**values)

    def test_two_sessions_model_snapshot_busy_and_next_model_after_cancel(self):
        a=self.controller.configure('a','fake');b=self.controller.configure('b','alternate','offset')
        self.submit_selection('a',a)
        self.assertTrue(self.runner.entered.wait(1))
        self.controller.configure('a','alternate')
        self.assertEqual(self.runner.requests[0]['model'],'fake')
        self.assertEqual(self.runner.requests[0]['parameters'],{'action':'success'})
        self.assertEqual(self.controller.model_id,'fake')
        with self.assertRaises(BackendBusy):self.submit_selection('b',b)
        self.assertEqual(len(self.runner.requests),1)
        self.controller.cancel('a',1);self.runner.release.set()
        self.wait(lambda:not self.controller._admission.locked())
        self.submit_selection('b',b)
        self.wait(lambda:len(self.runner.handles)==2)
        self.assertEqual(self.runner.requests[1]['model'],'alternate')
        self.assertEqual(self.runner.requests[1]['variant_id'],'offset')
        self.assertEqual(self.runner.requests[1]['parameters'],{'offset':4})

    def test_stale_callback_rejected_including_return_to_same_model(self):
        old=self.controller.configure('a','fake')
        self.controller.configure('a','alternate')
        self.controller.configure('a','fake')
        with self.assertRaisesRegex(ValueError,'Stale model selection'):self.submit_selection('a',old)
        self.assertFalse(self.runner.entered.is_set())
        self.assertFalse(self.controller._admission.locked())

    def test_repeated_identical_selection_keeps_ticket_and_existing_controls_valid(self):
        first=self.controller.configure('a','alternate','offset')
        again=self.controller.configure('a','alternate','offset')
        self.assertEqual(first['ticket'],again['ticket'])

    def test_selection_change_during_upload_snapshot_rejected_before_runner(self):
        old=self.controller.configure('a','fake')
        def stage(image,directory):
            result=stage_upload(image,directory)
            self.controller.configure('a','alternate')
            return result
        with patch('mde.ui_controller.stage_upload',side_effect=stage):
            with self.assertRaisesRegex(ValueError,'Stale model selection'):self.submit_selection('a',old)
        self.assertFalse(self.runner.entered.is_set())
        self.assertFalse(self.controller._admission.locked())
