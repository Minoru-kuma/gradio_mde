"""Pinned MoGe-2 inference API; no backend, UI or Artifact Storage dependency."""
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path

from mde.contracts import (LoadedModelInfo, MDEOutput, ModelAdapter, ModelLoadContext,
                           PredictionBatch, PredictionRequest)


class MoGeAdapter(ModelAdapter):
    def __init__(self):
        self.model = None
        self.context = None

    def load(self, context: ModelLoadContext) -> LoadedModelInfo:
        import torch
        from huggingface_hub import hf_hub_download
        from moge.model.v2 import MoGeModel

        if self.model is not None:
            raise RuntimeError("Adapter is already loaded")
        self.context = context
        if context.dtype != "float32":
            raise ValueError("01A MoGe adapter supports explicit float32 inference")
        if context.device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable; no CPU fallback")
        installed = json.loads(importlib.metadata.distribution("moge").read_text("direct_url.json") or "{}")
        revision = installed.get("vcs_info", {}).get("commit_id")
        if revision != context.model_info.data["upstream_revision"]:
            raise RuntimeError("Installed MoGe source revision does not match manifest")
        checkpoint_info = context.variant["checkpoint"]
        checkpoint = Path(context.checkpoint) if context.checkpoint else Path(hf_hub_download(
            repo_id=checkpoint_info["repo_id"], revision=checkpoint_info["revision"],
            filename=checkpoint_info["filename"], local_files_only=True))
        digest = hashlib.sha256()
        with checkpoint.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != checkpoint_info["sha256"]:
            raise ValueError("Checkpoint SHA-256 mismatch")
        torch.manual_seed(context.seed)
        self.model = MoGeModel.from_pretrained(checkpoint).to(torch.device(context.device)).eval()
        if not hasattr(self.model, "scale_head"):
            raise ValueError("Selected metric checkpoint has no scale head")
        identity = {"model_id": context.model_info.model_id, "variant_id": context.variant["variant_id"],
                    "model_version": context.variant["model_version"], "upstream_revision": revision,
                    "checkpoint": checkpoint_info, "checkpoint_sha256": digest.hexdigest()}
        runtime = {"torch_version": torch.__version__, "torch_cuda_runtime": torch.version.cuda,
                   "cuda_available": torch.cuda.is_available(), "gpu": None, "driver_version": None,
                   "device": context.device, "inference_dtype": context.dtype}
        if context.device.startswith("cuda"):
            runtime["gpu"] = torch.cuda.get_device_name(torch.device(context.device))
        return LoadedModelInfo(identity, runtime, context.variant["capabilities"],
            ["Smoke test verifies execution and depth semantics, not metric accuracy."])

    def predict(self, request: PredictionRequest) -> PredictionBatch:
        import numpy as np
        import torch

        if self.model is None:
            raise RuntimeError("Adapter is not loaded")
        image = torch.from_numpy(request.image.astype(np.float32) / 255).permute(2, 0, 1)
        image = image.to(self.context.device)
        with torch.inference_mode():
            native = self.model.infer(image, num_tokens=request.parameters["num_tokens"],
                                      use_fp16=False, apply_mask=True,
                                      force_projection="points" not in request.requested_outputs)
        depth = native["depth"].detach().cpu().numpy().astype(np.float32)
        mask = native.get("mask")
        metadata = {"depth_kind": "z_depth", "scale_type": "metric", "depth_unit": "m",
                    "camera_frame": "opencv_x_right_y_down_z_forward", "resize_crop_padding": "none",
                    "native_invalid_depth": "Inf", "warnings": [],
                    "native_output_keys": sorted(native), "num_tokens": request.parameters["num_tokens"]}
        optional, meanings = map_native_geometry(native, request.requested_outputs, depth.shape)
        metadata["geometry"] = meanings
        metadata["native_inference"] = {"force_projection": "points" not in request.requested_outputs,
                                        "fov_x": None, "apply_mask": True, "use_fp16": False}
        metadata["image_to_output"] = {"type": "identity", "pixel_center": "integer"}
        return PredictionBatch([MDEOutput(request.view_id, depth, metadata,
                               mask=mask.detach().cpu().numpy() if mask is not None else None, **optional)])

    def unload(self) -> None:
        self.model = None
        gc.collect()
        # The process exits after this job; no pool / resource controller is involved.


def map_native_geometry(native, requested, shape):
    """Map infer() outputs, never reconstruct points in the adapter."""
    import numpy as np
    h, w = shape
    optional, meanings = {}, {}
    if native.get("mask") is not None:
        meanings["model_mask"] = {"origin": "model", "native_convention": "infer mask > 0.5 and positive z",
                                  "conversion": "identity bool copy"}
    for key, native_key in (("points", "points"), ("normals", "normal"), ("intrinsics", "intrinsics")):
        if key not in requested or native.get(native_key) is None:
            continue
        array = native[native_key].detach().cpu().numpy().astype(np.float32)
        meaning = {"origin": "model", "native_key": native_key, "conversion": "identity float32 CPU copy",
                   "native_convention": "OpenCV camera x-right y-down z-forward",
                   "camera_frame": "opencv_x_right_y_down_z_forward"}
        if key == "points":
            meaning.update(scale_type="metric", native_convention="infer camera-space points; recovered z shift; metric scale-head metres; force_projection=False")
        elif key == "normals":
            meaning.update(orientation="native learned camera-space normal; no sign flip or face-camera enforcement")
        else:
            # utils3d normalized UV has centers ((x+0.5)/W, (y+0.5)/H).
            # Integer-center pixels require A @ K, including the -0.5 offset.
            native_k = array.copy()
            array = np.array([[w, 0, -0.5], [0, h, -0.5], [0, 0, 1]], dtype=np.float32) @ array
            meaning.update(native_convention="normalized UV pixel centers (x+0.5)/W, (y+0.5)/H",
                           conversion="A @ native_K; A=[[W,0,-0.5],[0,H,-0.5],[0,0,1]]",
                           native_intrinsics=native_k.tolist(), camera_model="pinhole",
                           pixel_center="integer", grid=[h, w])
        optional[key] = array
        meanings[key] = meaning
    return optional, meanings
