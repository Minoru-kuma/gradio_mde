"""Independent UniK3D output contract. Real runtime/checkpoint adoption is pending."""
from mde.contracts import LoadedModelInfo, ModelAdapter, PredictionBatch, MDEOutput, normalize_outputs

FRAME = 'opencv_x_right_y_down_z_forward'
HOLD = 'UniK3D real checkpoint acquisition/use/redistribution is on hold pending applicable terms'


class UniK3DAdapter(ModelAdapter):
    """A synthetic runtime seam, not an installed upstream runtime bridge.

    The injected factory accepts ModelLoadContext and returns an object with
    infer(uint8 HWC RGB) -> native-layout NumPy arrays and close(). It must use
    independently authored fixtures only. No default factory opens checkpoints,
    imports upstream code, downloads files or selects an execution backend.
    """
    def __init__(self, *, fixture_runtime_factory=None):
        self._factory = fixture_runtime_factory
        self._runtime = None
        self._context = None

    def load(self, context):
        if self._runtime is not None:
            raise RuntimeError('Adapter is already loaded')
        # Check before opening a path or importing any numeric/model dependency.
        if self._factory is None or context.checkpoint is not None:
            raise RuntimeError(HOLD)
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
        if request.parameters:
            raise ValueError('No native inference parameters are adopted yet')
        import numpy as np
        image = np.asarray(request.image)
        if image.dtype != np.dtype('uint8') or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
            raise ValueError('Input must be uint8 HWC RGB')
        native = self._runtime.infer(image)
        return PredictionBatch([map_prediction(native, request.view_id, image.shape[:2], requested)])

    def unload(self):
        runtime = self._runtime
        self._runtime = self._context = None
        if runtime is not None and callable(getattr(runtime, 'close', None)):
            runtime.close()


def map_prediction(native, view_id, input_shape, requested_outputs=('depth',)):
    """Preserve native distance and points; never backproject or invent K.

    Fixed upstream infer defines distance=norm(points) and depth=points.z.
    Using distance retains valid directions whose z is zero or negative.
    Real API tensor transfer and preprocessing are deliberately not implemented.
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
            'native points [1,3,H,W]; fixture assumes OpenCV camera frame; real frame unverified',
            'conversion': 'remove singleton batch; CHW to HWC; invalid distance/points to NaN; no resampling',
            'camera_frame': FRAME, 'scale_type': 'unknown'}
    metadata = {'depth_kind': 'ray_distance', 'scale_type': 'unknown', 'depth_unit': 'unknown',
        'camera_frame': FRAME, 'geometry': geometry,
        'image_to_output': {'type': 'identity', 'pixel_center': 'integer'},
        'native_output_keys': sorted(native), 'synthetic_contract_only': True,
        'depth_conversion': 'native distance [1,1,H,W] to [H,W]; no range-to-z conversion',
        'validity': 'finite positive native distance and finite native points; no native model mask asserted',
        'warnings': ['Scale and native camera frame are unverified on real UniK3D outputs.']}
    return MDEOutput(view_id, depth, metadata, points=values)
