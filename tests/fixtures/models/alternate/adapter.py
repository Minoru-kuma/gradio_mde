"""Independent test plugin, discovered solely from this directory's manifest."""
import sys

from mde.contracts import LoadedModelInfo, MDEOutput, ModelAdapter, PredictionBatch


class AlternateAdapter(ModelAdapter):
    def load(self, context):
        self.context = context
        assert 'tests.fixtures.fake' not in sys.modules
        assert 'tests.fixtures.geometry' not in sys.modules
        assert 'models.moge.adapter' not in sys.modules
        print('alternate load: only selected adapter imported', flush=True)
        return LoadedModelInfo({'model_id': context.model_info.model_id,
                                'variant_id': context.variant['variant_id'], 'checkpoint': 'none'},
                               capabilities=context.variant['capabilities'])

    def predict(self, request):
        import numpy as np
        value = request.parameters.get('distance', request.parameters.get('offset'))
        assert value is not None
        print('alternate predict', flush=True)
        depth = np.full(request.image.shape[:2], value, dtype='<f4')
        mask = np.ones(depth.shape, dtype=bool) if 'mask' in request.requested_outputs else None
        return PredictionBatch([MDEOutput(request.view_id, depth,
            {'depth_kind': 'ray_distance', 'scale_type': 'relative', 'depth_unit': 'arbitrary',
             'camera_frame': 'opencv_x_right_y_down_z_forward',
             'geometry': {'model_mask': {'origin': 'model', 'native_convention': 'all valid fixture',
                                         'conversion': 'identity'}}}, mask=mask)])

    def unload(self):
        print('alternate unloaded', flush=True)
        self.context = None
