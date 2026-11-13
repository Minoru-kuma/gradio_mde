"""Pinned native DA3 network + processors, explicit float32 depth and optional native pixel K."""
import gc
import importlib.metadata
import json

from mde.contracts import LoadedModelInfo, MDEOutput, ModelAdapter, PredictionBatch
from .checkpoint import verify_checkpoint


class DA3Adapter(ModelAdapter):
    def __init__(self):
        self.model = None
        self.context = None

    def load(self, context):
        if self.context is not None:
            raise RuntimeError('Adapter is already loaded')
        if context.device != 'cpu' or context.dtype != 'float32':
            raise ValueError('This DA3 environment supports explicit CPU / float32 only; no fallback')
        directory, hub_config = verify_checkpoint(context.checkpoint, context.variant['checkpoint'])
        installed = json.loads(importlib.metadata.distribution('depth-anything-3').read_text('direct_url.json') or '{}')
        revision = installed.get('vcs_info', {}).get('commit_id')
        if revision != context.model_info.data['upstream_revision']:
            raise RuntimeError('Installed DA3 source revision does not match manifest')
        import torch
        from omegaconf import OmegaConf
        from depth_anything_3.cfg import create_object, load_config
        from depth_anything_3.registry import MODEL_REGISTRY
        from depth_anything_3.utils.io.input_processor import InputProcessor
        from depth_anything_3.utils.io.output_processor import OutputProcessor

        name = context.variant['native_model_name']
        config = load_config(MODEL_REGISTRY[name])
        if hub_config.get('model_name') != name or OmegaConf.to_container(config, resolve=True) != hub_config.get('config'):
            raise ValueError('DA3 Hub and pinned native source configurations differ')
        self.context = context
        torch.manual_seed(context.seed)
        self.model = create_object(config)
        load_native_checkpoint(self.model, directory / context.variant['checkpoint']['filename'])
        self.model = self.model.to(device=context.device, dtype=torch.float32).eval()
        self.input_processor = InputProcessor()
        self.output_processor = OutputProcessor()
        identity = {'model_id': context.model_info.model_id, 'variant_id': context.variant['variant_id'],
                    'model_version': context.variant['model_version'], 'upstream_revision': revision,
                    'checkpoint': context.variant['checkpoint'],
                    'checkpoint_sha256': context.variant['checkpoint']['sha256']}
        return LoadedModelInfo(identity,
            {'device': context.device, 'inference_dtype': context.dtype, 'native_autocast': False,
             'checkpoint_loader': 'safetensors.load_model(strict=True); native shared parameter aliases'},
            context.variant['capabilities'], ['Relative depth only; no metric accuracy claim.'])

    def predict(self, request):
        if self.model is None:
            raise RuntimeError('Adapter is not loaded')
        if set(request.requested_outputs) - {'depth', 'intrinsics'} or 'depth' not in request.requested_outputs:
            raise ValueError('This DA3 integration supports depth and optional native intrinsics')
        import torch
        images, _, _ = self.input_processor([request.image], process_res=request.parameters['process_res'],
            process_res_method='upper_bound_resize', sequential=True)
        with torch.inference_mode(), torch.autocast(device_type='cpu', enabled=False):
            native = self.model(images[None].to(device=self.context.device, dtype=torch.float32),
                                export_feat_layers=[], infer_gs=False, use_ray_pose=False,
                                ref_view_strategy='first')
            prediction = self.output_processor(native)
        output = map_prediction(prediction, request.view_id, request.image.shape[:2],
                                request.parameters['process_res'], sorted(native), include_intrinsics='intrinsics' in request.requested_outputs)
        return PredictionBatch([output])

    def unload(self):
        self.model = None
        self.context = None
        self.input_processor = self.output_processor = None
        gc.collect()


def load_native_checkpoint(model, path):
    """Preserve native shared LayerNorm weights and the checkpoint's wrapper prefix."""
    import torch
    from safetensors.torch import load_model
    wrapper = torch.nn.Module()
    wrapper.add_module('model', model)
    # load_file + load_state_dict cannot resolve omitted aliases. This official
    # loader checks model storage sharing and rejects all genuinely missing keys.
    load_model(wrapper, str(path), strict=True, device='cpu')


def map_prediction(prediction, view_id, input_shape, process_res, native_keys, *, include_intrinsics=False):
    import numpy as np
    depth = np.asarray(prediction.depth)
    if depth.ndim != 3 or depth.shape[0] != 1 or min(depth.shape[1:]) < 1 or depth.dtype != np.dtype('float32'):
        raise ValueError('DA3 depth must be native float32 [1,H,W]')
    # No normalization, calibration, resampling, K synthesis or backprojection.
    depth = np.ascontiguousarray(depth[0])
    metadata = {'depth_kind': 'z_depth', 'scale_type': 'relative', 'depth_unit': 'arbitrary',
                'camera_frame': 'opencv_x_right_y_down_z_forward',
                'native_output_keys': native_keys,
                'native_inference': {'api': 'InputProcessor / DepthAnything3Net / OutputProcessor',
                    'autocast': False, 'infer_gs': False, 'use_ray_pose': False, 'ref_view_strategy': 'first'},
                'image_to_output': {'type': 'affine', 'pixel_center': 'integer',
                    'matrix': [[depth.shape[1]/input_shape[1], 0., .5*depth.shape[1]/input_shape[1]-.5],
                               [0., depth.shape[0]/input_shape[0], .5*depth.shape[0]/input_shape[0]-.5], [0.,0.,1.]],
                    'method': 'OpenCV boundary resize then patch-divisible resize; no crop or padding'},
                'resize_crop_padding': {'method': 'upper_bound_resize', 'process_res': process_res,
                    'patch_size': 14, 'original_hw': list(input_shape), 'output_hw': list(depth.shape),
                    'native_pipeline': 'longest-side boundary resize then nearest patch-divisible resize; no padding'},
                'warnings': []}
    k = None
    if include_intrinsics:
        native_k = np.asarray(prediction.intrinsics)
        if (native_k.dtype != np.dtype('float32') or native_k.shape != (1,3,3)
                or not np.isfinite(native_k).all() or native_k[0,0,0] <= 0 or native_k[0,1,1] <= 0
                or not np.allclose(native_k[0,2], [0,0,1], rtol=0, atol=1e-6)
                or abs(native_k[0,1,0]) > 1e-6):
            raise ValueError('Invalid native DA3 pixel intrinsics')
        k = np.ascontiguousarray(native_k[0])
        metadata['geometry'] = {'intrinsics': {'origin': 'model', 'camera_model': 'pinhole',
            'pixel_center': 'integer', 'grid': list(depth.shape),
            'native_convention': 'CameraDec pose encoding to pixel K at native depth H,W; official GLB uses integer meshgrid',
            'conversion': 'singleton view removal only; retain native K without half-pixel offset',
            'native_intrinsics': k.tolist()}}
    return MDEOutput(view_id, depth, metadata, intrinsics=k)
