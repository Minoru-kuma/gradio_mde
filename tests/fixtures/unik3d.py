"""Independently authored arrays, with no UniK3D source, packages or weights."""
from models.unik3d.adapter import UniK3DAdapter


class NativeFixture:
    def infer(self, image):
        import numpy as np
        print('unik3d synthetic predict', flush=True)
        h, w = image.shape[:2]
        # Non-pinhole directions: behind-camera, on the xy plane, and forward.
        points = np.zeros((1, 3, h, w), dtype='float32')
        points[:, 0] = 3
        points[:, 2, :, ::2] = -4
        points[:, 2, :, 1::2] = 4
        points[:, 0, 0, 1] = 5
        points[:, 2, 0, 1] = 0
        points[:, :, 0, 0] = np.nan
        return {'points': points, 'distance': np.linalg.norm(points, axis=1, keepdims=True),
                'depth': points[:, 2:3].copy()}

    def close(self):
        print('unik3d synthetic closed', flush=True)


class SyntheticAdapter(UniK3DAdapter):
    def __init__(self):
        super().__init__(fixture_runtime_factory=lambda context: NativeFixture())


class MissingDistanceFixture(NativeFixture):
    def infer(self, image):
        return {'points': super().infer(image)['points']}


class BrokenSyntheticAdapter(UniK3DAdapter):
    def __init__(self):
        super().__init__(fixture_runtime_factory=lambda context: MissingDistanceFixture())


class AllInvalidFixture(NativeFixture):
    def infer(self, image):
        native = super().infer(image)
        native['distance'][:] = float('nan')
        return native


class AllInvalidSyntheticAdapter(UniK3DAdapter):
    def __init__(self):
        super().__init__(fixture_runtime_factory=lambda context: AllInvalidFixture())
