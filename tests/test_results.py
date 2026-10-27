"""02C numeric and persistence contracts; no numeric imports in control tests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import Mock, patch

from mde.contracts import ArtifactIntegrityError
from mde.storage import read_json, sha256_file


HAS_NUMERIC = all(importlib.util.find_spec(m) for m in ('numpy', 'PIL'))


@unittest.skipUnless(HAS_NUMERIC, 'Independent UI environment required')
class NumericViewTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from mde import results
        self.np, self.views = np, results

    def test_statistics_invalid_mask_constant_all_invalid_and_no_mutation(self):
        np = self.np
        depth = np.array([[1, 2, np.nan], [-1, np.inf, 100]], dtype=np.float32)
        original = depth.copy()
        mask = np.array([[1, 1, 1], [1, 1, 0]], dtype=bool)
        valid, colors, rgba, stats = self.views.depth_view(depth, mask)
        self.assertEqual((stats['min'], stats['max'], stats['valid_pixels']), (1, 2, 2))
        self.assertEqual(stats['valid_fraction'], 2/6)
        self.assertEqual(rgba[..., 3].tolist(), [[255, 255, 0], [0, 0, 0]])
        np.testing.assert_array_equal(original, depth)
        _, colors, _, stats = self.views.depth_view(np.ones((2, 2), dtype=np.float32))
        np.testing.assert_allclose(colors, [[[0.5, 1, 0.5]]*2]*2)
        _, _, rgba, stats = self.views.depth_view(np.full((2, 2), np.nan, dtype=np.float32))
        self.assertIsNone(stats['min']); self.assertIsNone(stats['max'])
        self.assertEqual(stats['valid_pixels'], 0); self.assertFalse(rgba[..., 3].any())

    def test_pixel_camera_z_and_ray_distance_preserve_frame_scale(self):
        np = self.np
        k = np.array([[2, 0.1, 1], [0, 3, 1], [0, 0, 1]], dtype=np.float32)
        depth = np.full((3, 4), 2, dtype=np.float32)
        for kind in ('z_depth', 'ray_distance'):
            p = self.views.backproject(depth, k, kind)
            projected = p @ k.T
            y, x = np.indices(depth.shape)
            np.testing.assert_allclose(projected[..., 0]/projected[..., 2], x, atol=1e-6)
            np.testing.assert_allclose(projected[..., 1]/projected[..., 2], y, atol=1e-6)
            np.testing.assert_allclose(p[..., 2] if kind == 'z_depth' else np.linalg.norm(p, axis=-1), depth)
        self.assertLess(p[0, 0, 0], 0); self.assertLess(p[0, 0, 1], 0)

    def grid(self, h=5, w=5):
        np = self.np
        depth = np.full((h, w), 2, dtype=np.float32)
        p = self.views.backproject(depth, np.array([[100, 0, 2], [0, 100, 2], [0, 0, 1]], dtype=np.float32), 'z_depth')
        return p, depth, np.ones((h, w), dtype=bool)

    def test_mesh_holes_discontinuity_long_edges_and_degenerate_faces(self):
        np = self.np
        p, depth, valid = self.grid()
        tri = lambda: self.views.triangulate(p, depth, valid, self.views.MESH_PARAMETERS)
        self.assertEqual(len(tri()), 32)
        valid[2, 2] = False
        faces = tri(); self.assertEqual(len(faces), 24); self.assertNotIn(12, faces)
        valid[:] = True
        depth[:, 3:] = 4; p[:, 3:, 2] = 4
        faces = tri()
        self.assertTrue(all(not ({int(v%5) for v in f} & {0, 1, 2} and {int(v%5) for v in f} & {3, 4}) for f in faces))
        p[:] = [0, 0, 2]
        self.assertEqual(len(tri()), 0)
        p, depth, valid = self.grid(); p[2, 2, 0] = 100
        self.assertNotIn(12, tri())

    def test_derived_atomic_reuse_concurrent_identity_restart_and_corruption(self):
        np, v = self.np, self.views
        p, depth, valid = self.grid()
        generate = Mock(return_value={'points': p, 'faces': v.triangulate(p, depth, valid, v.MESH_PARAMETERS)})
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            identity = {'algorithm': 'fixture', 'version': '1', 'parameters': dict(v.MESH_PARAMETERS)}
            store = v.DerivedStore()
            with ThreadPoolExecutor(max_workers=6) as pool:
                values = list(pool.map(lambda _: store.get(run, identity, generate), range(6)))
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(sum(not r[2] for r in values), 1)
            manifest = values[0][1]
            self.assertEqual(len(list((run/'derived').glob('*/*/manifest.json'))), 1)
            before = {str(p): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
            arrays, same, reused = v.DerivedStore().get(run, identity, Mock(side_effect=AssertionError('regenerated')))
            self.assertTrue(reused); self.assertEqual(same, manifest)
            self.assertEqual(before, {str(p): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()})
            changed = {**identity, 'parameters': {**identity['parameters'], 'relative_depth_jump': 0.2}}
            self.assertNotEqual(store.get(run, changed, generate)[1]['key'], manifest['key'])
            path = run/manifest['output']['path']; path.write_bytes(b'broken')
            with self.assertRaises(ArtifactIntegrityError): store.get(run, identity, generate)
            self.assertEqual(generate.call_count, 2)

    def test_interrupted_write_is_never_reused_and_bad_manifest_rejected(self):
        v = self.views
        p, _, _ = self.grid()
        with tempfile.TemporaryDirectory() as tmp:
            run, store = Path(tmp), v.DerivedStore()
            with patch.object(v.os, 'rename', side_effect=OSError('interrupted publication')):
                with self.assertRaises(OSError): store.get(run, {'key': 'fixture'}, lambda: {'points': p})
            self.assertEqual(len(list(run.glob('derived/*/.partial-*'))), 1)
            self.assertFalse(store.get(run, {'key': 'fixture'}, lambda: {'points': p})[2])
            manifest = next(run.glob('derived/*/[!.]*/manifest.json'))
            manifest.write_text('{}')
            with self.assertRaises(ArtifactIntegrityError): store.get(run, {'key': 'fixture'}, lambda: {'points': p})

    def test_derived_storage_rejects_symlinks_and_incomplete_complete_generation(self):
        import hashlib
        v = self.views
        points, _, _ = self.grid()
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run/'output').mkdir()
            (run/'derived').symlink_to(run/'output', target_is_directory=True)
            with self.assertRaises(ArtifactIntegrityError):
                v.DerivedStore().get(run, {'fixture':1}, lambda: {'points':points})
            self.assertEqual(list((run/'output').iterdir()), [])
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); identity={'fixture':1}
            key=hashlib.sha256(v.canonical(identity)).hexdigest()
            (run/'derived'/key/'incomplete').mkdir(parents=True)
            with self.assertRaisesRegex(ArtifactIntegrityError,'Incomplete'):
                v.DerivedStore().get(run, identity, lambda: {'points':points})


@unittest.skipUnless(HAS_NUMERIC, 'Independent UI environment required')
class ResultsContractTests(unittest.TestCase):
    from tests.test_local_contract import LocalContractTests
    setUp = LocalContractTests.setUp
    stop_workers = LocalContractTests.stop_workers

    def make_run(self, outputs, action='viewer'):
        from mde.results import ResultsService
        handle = self.runner.submit('geometry', Path(__file__).resolve().parent/'assets/sample.png',
            device='cpu', requested_outputs=outputs, parameters={'action': action})
        self.backend._jobs[handle.backend_job_id].worker.process.wait(timeout=45)
        result = self.runner.collect(handle)
        self.assertEqual(result.status, 'COMPLETED', result.error)
        return handle, result, ResultsService(self.store, self.runner.collect)

    def test_four_views_rgb_mapping_mesh_lazy_reuse_and_raw_result_unchanged(self):
        import base64
        import numpy as np
        h, result, service = self.make_run(('depth', 'points', 'normals', 'intrinsics', 'mask'))
        run = self.store.root/h.run_id
        before = {str(p): (sha256_file(p), p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file()}
        for mode in ('Depth', 'RawDepth', 'Point Cloud'):
            view = service.view(h.run_id, mode)
            self.assertFalse((run/'derived').exists())
        self.assertIsNotNone(view['rgb_colors']); self.assertIsNotNone(view['normal_colors'])
        self.assertEqual(view['frame'], 'opencv_x_right_y_down_z_forward')
        self.assertEqual((view['unit'], view['scale']), ('arbitrary', 'relative'))
        from PIL import Image
        image = np.asarray(Image.open(run/'input/views/view-0001/image.png').convert('RGB'))
        rgb = np.frombuffer(base64.b64decode(view['rgb_colors']), dtype='<f4').reshape(-1, 3)
        np.testing.assert_allclose(rgb[0], image.reshape(-1, 3)[1]/255, atol=1e-7)
        mesh = service.view(h.run_id, 'Mesh')
        self.assertGreater(mesh['face_count'], 0); self.assertFalse(mesh['cache_reused'])
        self.assertTrue(service.view(h.run_id, 'Mesh')['cache_reused'])
        from mde.backends import LocalBackend
        from mde.results import ResultsService
        fresh = ResultsService(self.store, LocalBackend(self.store.root).collect)
        self.assertTrue(fresh.view(h.run_id, 'Mesh')['cache_reused'])
        self.assertEqual(before, {p: (sha256_file(Path(p)), Path(p).stat().st_mtime_ns) for p in before})
        self.assertEqual((run/'logs/attempt-0001/stdout.log').read_text().count('geometry predict'), 1)

    def test_missing_geometry_normal_rgb_and_defined_backprojection(self):
        h, _, service = self.make_run(('depth',))
        with self.assertRaisesRegex(ValueError, '3D unavailable'): service.view(h.run_id, 'Mesh')
        self.assertIn('download', service.view(h.run_id, 'RawDepth'))
        h, _, service = self.make_run(('depth', 'intrinsics'))
        points = service.view(h.run_id, 'Point Cloud')
        self.assertIn('derived points', points['origin']); self.assertIsNotNone(points['derived'])
        self.assertIsNone(points['normal_colors']); self.assertIn('no saved', points['normal_reason'])
        self.assertTrue(service.view(h.run_id, 'Point Cloud')['point_cache_reused'])
        h, _, service = self.make_run(('depth', 'points'), action='success')
        points = service.view(h.run_id, 'Point Cloud')
        self.assertIsNone(points['rgb_colors']); self.assertIn('correspondence', points['rgb_reason'])
        mesh = service.view(h.run_id, 'Mesh')
        self.assertEqual(mesh['face_count'], 0); self.assertIsNone(mesh['texture'])
