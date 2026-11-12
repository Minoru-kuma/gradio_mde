"""Pinned offline UniK3D native runtime plus independently authored output mapping."""
import gc
import importlib.metadata
import json

from mde.contracts import LoadedModelInfo, ModelAdapter, PredictionBatch, MDEOutput, normalize_outputs
from .checkpoint import verify_checkpoint

FRAME = 'opencv_x_right_y_down_z_forward'


class UniK3DAdapter(ModelAdapter):
    """Native runtime and a checkpoint-free seam for independently authored fixtures.

    The injected factory accepts ModelLoadContext and returns an object with
    infer(uint8 HWC RGB) -> native-layout NumPy arrays and close(). It must use
    independently authored fixtures only. Native loading verifies prepared local
    files and source identity; inference never downloads or selects a backend.
    """
    def __init__(self, *, fixture_runtime_factory=None):
        self._factory = fixture_runtime_factory
        self._runtime = None
        self._context = None

    def load(self, context):
        if self._runtime is not None:
            raise RuntimeError('Adapter is already loaded')
        if self._factory is None:
            return self._load_native(context)
        if context.checkpoint is not None:
            raise ValueError('Synthetic runtime cannot open a real checkpoint')
        if context.device != 'cpu' or context.dtype != 'float32':
            raise ValueError('Synthetic contract supports explicit CPU / float32 only; no fallback')
        self._runtime = self._factory(context)
        try:
            if not callable(getattr(self._runtime, 'infer', None)) or not callable(getattr(self._runtime, 'close', None)):
                raise TypeError('Fixture runtime must provide infer and close')
            self._context = context
            return LoadedModelInfo(
                {'model_id': context.model_info.model_id, 'variant_id': context.variant['variant_id'],
                 'implementation': 'synthetic-contract-only', 'checkpoint': None},
                {'device': context.device, 'inference_dtype': context.dtype, 'synthetic': True},
                {'depth': {'status': 'supported'}, 'points': {'status': 'supported'}},
                ['Synthetic fixture only; real UniK3D runtime, camera convention and scale remain unverified.'])
        except Exception:
            self.unload()
            raise

    def predict(self, request):
        if self._runtime is None or self._context is None:
            raise RuntimeError('Adapter is not loaded')
        requested = normalize_outputs(request.requested_outputs)
        if set(requested) - {'depth', 'points'}:
            raise ValueError('Only depth and native points are implemented')
        if self._factory is not None and request.parameters:
            raise ValueError('No native inference parameters are adopted yet')
        if self._factory is None:
            if set(request.parameters) != {'resolution_level'}:
                raise ValueError('UniK3D requires only resolution_level')
            level = request.parameters['resolution_level']
            if type(level) is not int or not 0 <= level < 10:
                raise ValueError('resolution_level must be an integer in [0,10)')
            self._runtime.model.resolution_level = level
        import numpy as np
        image = np.asarray(request.image)
        if image.dtype != np.dtype('uint8') or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
            raise ValueError('Input must be uint8 HWC RGB')
        native = self._runtime.infer(image)
        output = map_prediction(native, request.view_id, image.shape[:2], requested,
                                synthetic=self._factory is not None)
        if self._factory is None:
            output.metadata.update(self._runtime.metadata(image.shape[:2]))
        return PredictionBatch([output])

    def _load_native(self, context):
        # Reject missing preparation / unsupported execution before framework import.
        if context.checkpoint is None:
            raise ValueError('UniK3D requires a prepared local checkpoint directory; inference never downloads')
        if context.device != 'cpu' or context.dtype != 'float32':
            raise ValueError('UniK3D environment supports explicit CPU / float32 only; no fallback')
        directory, config = verify_checkpoint(context.checkpoint, context.variant['checkpoint'])
        installed = json.loads(importlib.metadata.distribution('unik3d').read_text('direct_url.json') or '{}')
        revision = installed.get('vcs_info', {}).get('commit_id')
        if revision != context.model_info.data['upstream_revision']:
            raise RuntimeError('Installed UniK3D source revision does not match manifest')
        # The native encoder's null setting disables its separate DINO weight download.
        if config['model']['pixel_encoder']['pretrained'] is not None:
            raise ValueError('Pinned UniK3D config must disable encoder checkpoint acquisition')
        import torch
        from safetensors.torch import load_model
        from unik3d.models.unik3d import UniK3D
        if torch.version.cuda is not None:
            raise RuntimeError('UniK3D pinned environment requires a CPU-only torch build')
        torch.manual_seed(context.seed)
        model = UniK3D(config)
        self._runtime = NativeRuntime(model)
        load_model(model, str(directory / context.variant['checkpoint']['filename']), strict=True, device='cpu')
        model = model.to(device='cpu', dtype=torch.float32).eval()
        self._runtime.model = model
        self._context = context
        identity = {'model_id': context.model_info.model_id, 'variant_id': context.variant['variant_id'],
            'model_version': context.variant['model_version'], 'upstream_revision': revision,
            'checkpoint': context.variant['checkpoint'], 'checkpoint_sha256': context.variant['checkpoint']['sha256']}
        return LoadedModelInfo(identity, {'device': 'cpu', 'inference_dtype': 'float32', 'synthetic': False,
            'native_autocast': False, 'checkpoint_loader': 'safetensors.load_model(strict=True)'},
            context.variant['capabilities'], ['Checkpoint terms remain unresolved; scoped noncommercial local research decision recorded.',
                'Native scale preserved without a verified metric-unit claim.'])

    def unload(self):
        runtime = self._runtime
        self._runtime = self._context = None
        if runtime is not None and callable(getattr(runtime, 'close', None)):
            runtime.close()
        gc.collect()


class NativeRuntime:
    def __init__(self, model):
        self.model = model
        self.native_keys = []

    def infer(self, image):
        import torch
        rgb = torch.from_numpy(image).permute(2, 0, 1)
        with torch.inference_mode(), torch.autocast(device_type='cpu', enabled=False):
            prediction = self.model.infer(rgb)
        self.native_keys = sorted(prediction)
        return {name: prediction[name].detach().cpu().to(dtype=torch.float32).numpy()
                for name in ('distance', 'points', 'depth')}

    def metadata(self, shape):
        # Record the fixed native helpers' actual preprocessing policy, without reimplementing it.
        from unik3d.models.unik3d import get_paddings, get_resize_factor
        constraints = self.model.shape_constraints
        paddings, padded = get_paddings(shape, constraints['ratio_bounds'])
        width = (constraints['pixels_max'] - constraints['pixels_min']) / 10
        low = constraints['pixels_min'] + self.model.resolution_level * width
        _, resized = get_resize_factor(padded, (low, low + width))
        return {'native_inference': {'api': 'UniK3D.infer', 'resolution_level': self.model.resolution_level,
                    'normalize': True, 'autocast': False, 'camera': None},
                'resize_crop_padding': {'original_hw': list(shape), 'paddings_lrtb': list(paddings),
                    'padded_hw': list(padded), 'native_resized_hw': list(resized),
                    'postprocess': 'native bilinear align_corners=False to padded original grid, then remove padding'},
                'native_output_keys': self.native_keys,
                'native_output_policy': 'distance / points / depth transferred to CPU float32; rays / confidence / features not exported'}

    def close(self):
        self.model = None


def map_prediction(native, view_id, input_shape, requested_outputs=('depth',), *, synthetic=True):
    """Preserve native distance and points; never backproject or invent K.

    Fixed upstream infer defines distance=norm(points) and depth=points.z.
    Using distance retains valid directions whose z is zero or negative.
    Native preprocessing and tensor transfer are separate from this mapping.
    """
    import numpy as np
    requested = normalize_outputs(requested_outputs)
    if set(requested) - {'depth', 'points'}:
        raise ValueError('Only depth and native points are implemented')
    if not isinstance(native, dict) or 'distance' not in native or 'points' not in native:
        raise ValueError('Missing native distance or points')
    if len(input_shape) != 2 or any(not isinstance(size, int) or isinstance(size, bool) or size < 1
                                    for size in input_shape):
        raise ValueError('Input grid must have positive integer height and width')
    h, w = input_shape
    arrays = {}
    for key, shape in (('distance', (1, 1, h, w)), ('points', (1, 3, h, w))):
        value = np.asarray(native[key])
        if value.dtype != np.dtype('float32') or value.shape != shape:
            raise ValueError(f'Native {key} must be float32 {shape}')
        arrays[key] = value
    distance = arrays['distance'][0, 0]
    points = np.moveaxis(arrays['points'][0], 0, -1)
    valid = np.isfinite(distance) & (distance > 0) & np.isfinite(points).all(axis=-1)
    # Accumulate in float64 to avoid overflow when checking malformed float32 outputs.
    norm = np.linalg.norm(points.astype('float64'), axis=-1)
    if not np.allclose(distance[valid], norm[valid], rtol=1e-4, atol=1e-5):
        raise ValueError('Native distance differs from norm(points)')
    if 'depth' in native:
        z = np.asarray(native['depth'])
        if z.dtype != np.dtype('float32') or z.shape != (1, 1, h, w):
            raise ValueError('Native z depth must be float32 [1,1,H,W]')
        if not np.allclose(z[0, 0][valid], points[..., 2][valid], rtol=1e-4, atol=1e-5):
            raise ValueError('Native z depth differs from points.z')
    depth = np.ascontiguousarray(np.where(valid, distance, np.nan), dtype='float32')
    values = None
    geometry = {}
    if 'points' in requested:
        values = np.ascontiguousarray(np.where(valid[..., None], points, np.nan), dtype='float32')
        geometry['points'] = {'origin': 'model', 'native_convention':
            'native points [1,3,H,W]; OpenCV camera frame' if not synthetic else
            'native points [1,3,H,W]; synthetic OpenCV camera frame',
            'conversion': 'remove singleton batch; CHW to HWC; invalid distance/points to NaN; no resampling',
            'camera_frame': FRAME, 'scale_type': 'unknown'}
    metadata = {'depth_kind': 'ray_distance', 'scale_type': 'unknown', 'depth_unit': 'unknown',
        'camera_frame': FRAME, 'geometry': geometry,
        'image_to_output': {'type': 'identity', 'pixel_center': 'integer'},
        'native_output_keys': sorted(native), 'synthetic_contract_only': synthetic,
        'depth_conversion': 'native distance [1,1,H,W] to [H,W]; no range-to-z conversion',
        'validity': 'finite positive native distance and finite native points; no native model mask asserted',
        'warnings': ['Native metric units are not asserted by this integration.']}
    return MDEOutput(view_id, depth, metadata, points=values)
