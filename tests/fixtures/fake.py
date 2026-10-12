import sys

from mde.contracts import LoadedModelInfo, MDEOutput, ModelAdapter, PredictionBatch


class FakeAdapter(ModelAdapter):
    def __init__(self):
        self.loaded = False

    def load(self, context):
        if self.loaded:
            raise RuntimeError("already loaded")
        self.loaded = True
        return LoadedModelInfo({"model_id": "fake", "variant_id": "fake-depth", "checkpoint": "none"},
                               {"torch_version": None, "torch_cuda_runtime": None, "gpu": None})

    def predict(self, request):
        import numpy as np
        if not self.loaded:
            raise RuntimeError("not loaded")
        print("fake predict: stdout", flush=True)
        print("fake predict: stderr", file=sys.stderr, flush=True)
        action = request.parameters["action"]
        if action == "raise":
            raise RuntimeError("intentional predict failure")
        if action == "missing_result":
            raise SystemExit(0)
        if action in ("block", "stubborn", "orphan", "gentle"):
            import json
            import os
            import signal
            import subprocess
            import time
            child_code = "import signal,time; "
            if action != "gentle":
                child_code += "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            child_code += "print('ready',flush=True); time.sleep(120)"
            child = subprocess.Popen([sys.executable, "-c", child_code],
                stdout=subprocess.PIPE, text=True)
            child.stdout.readline()
            child.stdout.close()
            print("fake child ready: " + json.dumps({"worker": os.getpid(), "child": child.pid}), flush=True)
            if action == "orphan":
                raise SystemExit(0)
            if action == "stubborn":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
            if action == "gentle":
                def terminate(*_):
                    child.wait(timeout=2)
                    raise SystemExit(143)
                signal.signal(signal.SIGTERM, terminate)
            time.sleep(120)
        depth = None if action == "missing_depth" else np.full(request.image.shape[:2], 2.5, dtype=np.float32)
        return PredictionBatch([MDEOutput(request.view_id, depth,
            {"depth_kind": "z_depth", "scale_type": "relative", "depth_unit": "arbitrary",
             "camera_frame": "opencv_x_right_y_down_z_forward", "warnings": []})])

    def unload(self):
        self.loaded = False
        print("fake unloaded", flush=True)
