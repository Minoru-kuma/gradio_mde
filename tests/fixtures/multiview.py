"""Synthetic batch interface; no real multi-view model or camera estimation."""
from copy import deepcopy

from mde.contracts import (LoadedModelInfo, MDEOutput, ModelAdapter, MultiViewPredictionRequest,
                           PredictionBatch, PredictionView)


class MultiViewAdapter(ModelAdapter):
    def load(self, context):
        self.loaded = True
        capabilities = deepcopy(context.variant['capabilities'])
        mode = context.variant.get('runtime_mode', 'supported')
        if mode == 'unsupported': capabilities['multi_view']['status'] = 'unsupported'
        if mode == 'legacy': capabilities = {}
        return LoadedModelInfo({'model_id': context.model_info.model_id,
            'variant_id': context.variant['variant_id'], 'checkpoint': None}, capabilities=capabilities)

    def predict(self, request):
        import numpy as np
        assert self.loaded
        multi = isinstance(request, MultiViewPredictionRequest)
        views = request.views if multi else (PredictionView(request.view_id, request.image),)
        print('fake multiview predict', flush=True)
        action = request.parameters['action']
        outputs = []
        for view in views:
            h, w = view.image.shape[:2]
            value = float(view.image[0, 0, 0]) + 1
            depth = np.full((h, w), value, dtype='float32')
            points = np.zeros((h, w, 3), dtype='float32'); points[..., 2] = value
            metadata = {'depth_kind': 'z_depth', 'scale_type': 'relative', 'depth_unit': 'arbitrary',
                'camera_frame': 'opencv_x_right_y_down_z_forward',
                'image_to_output': {'type': 'identity', 'pixel_center': 'integer'},
                'geometry': {'points': {'origin': 'model', 'native_convention': 'synthetic camera coordinates',
                    'conversion': 'identity', 'camera_frame': 'opencv_x_right_y_down_z_forward', 'scale_type': 'relative'}}}
            outputs.append(MDEOutput(view.view_id, depth, metadata, points=points,
                extras={'future/model': {'values': [value, None], 'path': 'opaque metadata; not a file reference'},
                        'fake/request_kind': 'multi_view_v1' if multi else 'legacy_single'}))
        scene = ({'reference_view_id': views[0].view_id, 'scale_type': 'relative', 'depth_unit': 'arbitrary',
                  'future/scene': {'opaque': [None, {'keep': True}]}} if multi or action == 'single_scene' else {})
        if action == 'reverse': outputs.reverse()
        if action == 'missing': outputs.pop()
        if action == 'duplicate': outputs[-1].view_id = outputs[0].view_id
        if action == 'unknown': outputs[-1].view_id = 'view-9999'
        if action == 'missing_depth': outputs[-1].depth = None
        if action == 'bad_points': outputs[-1].points[..., 2] *= 2
        if action == 'bad_extras': outputs[-1].extras['invalid'] = np.ones(1)
        if action == 'bad_scene': scene['reference_view_id'] = 'view-9999'
        if action == 'bad_scene_scale': scene.update(scale_type='metric', depth_unit='m')
        if action == 'bad_scene_json': scene['invalid'] = float('nan')
        return PredictionBatch(outputs, scene)

    def unload(self):
        self.loaded = False
        print('fake multiview unloaded', flush=True)
