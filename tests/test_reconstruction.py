"""03.7 camera priority, numeric grids, derived persistence and auxiliary admission."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch
import zipfile

from mde.contracts import ArtifactIntegrityError, BackendBusy
from mde.storage import read_json, sha256_file, write_json
from tests import test_local_contract as local_contract
from tests import test_results as results_tests

PROJECT=local_contract.PROJECT
BOUNDARY_K = [[0.001,0,0],[0,100,0],[0.000001,0,1]]

HAS_NUMERIC=all(importlib.util.find_spec(m) for m in ('numpy','PIL'))


@unittest.skipUnless(HAS_NUMERIC,'Independent numeric UI environment required')
class CameraNumericTests(unittest.TestCase):
    def test_half_centers_non_square_resize_and_crop_preserve_ray_mapping(self):
        import numpy as np
        from mde.cameras import align_camera
        from mde.geometry import FRAME
        k=np.array([[400,0,160],[0,300,100],[0,0,1]],dtype='float32')
        a=np.array([[.5,0,-10.25],[0,.75,-5.125],[0,0,1]])
        cam={'K':k.tolist(),'grid':[200,320],'pixel_center':'half','camera_model':'pinhole','camera_frame':FRAME}
        converted,prov=align_camera(cam,{'image_to_output':{'type':'affine','pixel_center':'integer','matrix':a.tolist()}},[200,320],[140,150])
        shift=np.eye(3);shift[:2,2]=-.5
        np.testing.assert_allclose(converted,a@shift@k,rtol=0,atol=0)
        ray=np.array([.1,-.2,1.]);np.testing.assert_allclose(converted@ray,a@shift@k@ray)
        self.assertEqual(prov['source_grid'],[200,320]);self.assertEqual(prov['output_grid'],[140,150])
        for invalid in (np.zeros((3,3)),k*np.nan,[[1,0,0],[0,-1,0],[0,0,1]]):
            with self.assertRaises(ValueError):align_camera({**cam,'K':invalid},{},[200,320],[140,150])
        with self.assertRaisesRegex(ValueError,'transform'):
            align_camera(cam,{'image_to_output':{'type':'unverified'}},[200,320],[140,150])

    def test_pinhole_structure_is_exact_before_and_after_grid_conversion(self):
        import numpy as np
        from mde.cameras import align_camera, pixel_k
        from mde.geometry import FRAME
        from mde.results import backproject
        camera={'K':BOUNDARY_K,'grid':[256,256],'grid_space':'depth',
                'pixel_center':'integer','camera_model':'pinhole','camera_frame':FRAME}
        for bad in (BOUNDARY_K, [[100,0,0],[1e-12,100,0],[0,0,1]],
                    [[100,0,0],[0,100,0],[0,1e-12,1]],
                    [[100,0,0],[0,100,0],[0,0,1+1e-12]]):
            with self.assertRaisesRegex(ValueError,'pinhole'):pixel_k(bad)
            with self.assertRaisesRegex(ValueError,'pinhole'):
                align_camera({**camera,'K':bad},{},[256,256],[256,256])
            with self.assertRaisesRegex(ValueError,'pinhole'):
                backproject(np.ones((2,256),dtype='float32'),bad,'z_depth')
        # Legitimate skew, off-centre principal point and small focal remain valid.
        good=[[.001,.25,-20],[0,100,123],[0,0,1]]
        converted,_=align_camera({**camera,'K':good},{},[256,256],[256,256])
        np.testing.assert_array_equal(backproject(np.ones((2,256),dtype='float32'),converted,'z_depth')[...,2],1)

    def test_float32_overflow_underflow_and_equal_size_grid_ambiguity_are_rejected(self):
        import numpy as np
        from mde.cameras import align_camera
        from mde.geometry import FRAME
        camera={'K':[[300,0,128],[0,300,128],[0,0,1]],'grid':[256,256],
            'pixel_center':'integer','camera_model':'pinhole','camera_frame':FRAME}
        metadata={'image_to_output':{'type':'affine','pixel_center':'integer','matrix':[[1,0,-10],[0,1,-20],[0,0,1]]}}
        with self.assertRaisesRegex(ValueError,'Ambiguous'):align_camera(camera,metadata,[256,256],[256,256])
        source,_=align_camera({**camera,'grid_space':'source'},metadata,[256,256],[256,256])
        depth,_=align_camera({**camera,'grid_space':'depth'},metadata,[256,256],[256,256])
        np.testing.assert_array_equal(source[:2,2],[118,108]);np.testing.assert_array_equal(depth[:2,2],[128,128])
        for focal in (1e40,1e-50):
            bad={**camera,'grid_space':'depth','K':[[focal,0,128],[0,focal,128],[0,0,1]]}
            with self.assertRaises(ValueError):align_camera(bad,metadata,[256,256],[256,256])

    def test_range_z_backprojection_invalid_and_discontinuous_surface(self):
        import numpy as np
        from mde.results import backproject,triangulate,MESH_PARAMETERS
        k=np.array([[100,0,1],[0,100,1],[0,0,1]],dtype='float32');depth=np.ones((4,4),dtype='float32')*2
        z=backproject(depth,k,'z_depth');r=backproject(depth,k,'ray_distance')
        np.testing.assert_array_equal(z[...,2],depth);np.testing.assert_allclose(np.linalg.norm(r,axis=-1),depth,rtol=1e-6)
        tiny=np.array([[1e-20,0,1],[0,1e-20,1],[0,0,1]],dtype='float32')
        extreme=backproject(np.ones((3,3),dtype='float32'),tiny,'ray_distance')
        np.testing.assert_allclose(np.linalg.norm(extreme,axis=-1),1,rtol=1e-6)
        valid=np.ones((4,4),dtype=bool);valid[0,0]=False;z[0,0]=np.nan
        faces=triangulate(z,depth,valid,MESH_PARAMETERS);self.assertFalse((faces==0).any())
        self.assertEqual(len(faces),16)
        depth[:,2:]=10;z=backproject(depth,k,'z_depth');faces=triangulate(z,depth,valid,MESH_PARAMETERS)
        self.assertTrue(all(len(set((face%4>=2).tolist()))==1 for face in faces))

    def test_da3_native_k_identity_values_and_integer_affine(self):
        import numpy as np
        from types import SimpleNamespace
        from models.da3.adapter import map_prediction
        k=np.array([[[300,0,14],[0,400,7],[0,0,1]]],dtype='float32')
        pred=SimpleNamespace(depth=np.ones((1,14,28),dtype='float32'),intrinsics=k)
        out=map_prediction(pred,'view-0001',(40,80),252,['depth','intrinsics'],include_intrinsics=True)
        np.testing.assert_array_equal(out.intrinsics,k[0]);self.assertIsNone(out.points)
        self.assertEqual(out.metadata['geometry']['intrinsics']['grid'],[14,28])
        np.testing.assert_allclose(out.metadata['image_to_output']['matrix'],[[.35,0,-.325],[0,.35,-.325],[0,0,1]])
        self.assertEqual(out.metadata['scale_type'],'relative')
        for bad in (k.astype('float64'),k[0],k*np.nan,-k):
            with self.assertRaises(ValueError):map_prediction(SimpleNamespace(depth=pred.depth,intrinsics=bad),'view-0001',(40,80),252,[],include_intrinsics=True)


@unittest.skipUnless(HAS_NUMERIC,'Independent numeric UI environment required')
class ReconstructionTests(unittest.TestCase):
    setUp=local_contract.LocalContractTests.setUp
    stop_workers=local_contract.LocalContractTests.stop_workers
    make_run=results_tests.ResultsContractTests.make_run

    def estimator(self):
        from mde.geometry import FRAME
        estimator=Mock();estimator.identity.return_value={'fixture':'camera-v1','seed':0}
        estimator.estimate.return_value={'K':[[300,0,127.5],[0,300,127.5],[0,0,1]],'grid':[256,256],
            'pixel_center':'integer','camera_model':'pinhole','camera_frame':FRAME}
        return estimator

    def snapshot(self,run):
        return {p.relative_to(run).as_posix():(sha256_file(p),p.stat().st_mtime_ns) for p in run.rglob('*') if p.is_file() and 'derived' not in p.relative_to(run).parts}

    def test_known_then_native_k_priority_and_native_points_remain_raw(self):
        from mde.results import ResultsService
        h,result,_=self.make_run(('depth','intrinsics'));est=self.estimator();view=ResultsService(self.store,self.runner.collect,camera_estimator=est)
        native=view.view(h.run_id,'Point Cloud');self.assertEqual(native['camera']['source'],'model native')
        known=deepcopy(est.estimate.return_value);known['K'][0][0]=600
        manual=view.view(h.run_id,'Point Cloud',known_camera=known)
        self.assertEqual(manual['camera']['source'],'known');self.assertNotEqual(manual['derived']['key'],native['derived']['key'])
        tiny=deepcopy(known);tiny['K'][0][0]=1e-40
        with self.assertRaisesRegex(ValueError,'finite float32'):
            view.view(h.run_id,'Point Cloud',known_camera=tiny)
        est.estimate.assert_not_called();est.identity.assert_not_called()
        h,_,view=self.make_run(('depth','points'))
        raw=view.view(h.run_id,'Point Cloud',known_camera={'invalid':True});self.assertEqual(raw['origin'],'model points (saved raw)')

    def test_estimated_cache_restart_mesh_export_raw_immutable_and_condition_key(self):
        from mde.results import ResultsService
        from mde.run_management import RunManagementService
        h,result,_=self.make_run(('depth',));run=self.store.root/h.run_id;before=self.snapshot(run)
        est=self.estimator();view=ResultsService(self.store,self.runner.collect,camera_estimator=est)
        point=view.view(h.run_id,'Point Cloud');mesh=view.view(h.run_id,'Mesh')
        self.assertEqual(point['camera']['source'],'estimated');self.assertGreater(mesh['face_count'],0)
        self.assertEqual(est.estimate.call_count,1)
        restarted=ResultsService(self.store,self.runner.collect)
        same=restarted.view(h.run_id,'Mesh');self.assertTrue(same['cache_reused']);self.assertEqual(same['derived'],mesh['derived'])
        package=RunManagementService(self.store,self.runner.collect).export(h.run_id)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            self.assertIn(point['camera']['calibration_output']['path'],archive.namelist())
            self.assertIn(mesh['derived']['output']['path'],archive.namelist())
            self.assertEqual(json.loads(archive.read('attempts/attempt-0001/job-result.json')),result.to_dict())
        est.identity.return_value={'fixture':'camera-v2','seed':1}
        different=view.view(h.run_id,'Mesh');self.assertNotEqual(different['derived']['key'],mesh['derived']['key']);self.assertEqual(est.estimate.call_count,2)
        self.assertEqual(before,self.snapshot(run))

    def test_boundary_k_rejected_without_publishing_or_mutating_raw(self):
        from mde.results import ResultsService
        h,_,_=self.make_run(('depth',));run=self.store.root/h.run_id
        before=self.snapshot(run);camera={**self.estimator().estimate.return_value,'K':BOUNDARY_K}
        with self.assertRaisesRegex(ValueError,'pinhole'):
            ResultsService(self.store,self.runner.collect).view(h.run_id,'Mesh',known_camera=camera)
        self.assertFalse(list((run/'derived').glob('*/*/manifest.json')))
        self.assertEqual(before,self.snapshot(run))

    def test_z_mismatch_rejected_before_publication_and_on_point_and_mesh_cache_read(self):
        import numpy as np
        from mde.results import ResultsService
        h,result,_=self.make_run(('depth','intrinsics'));run=self.store.root/h.run_id
        view=ResultsService(self.store,self.runner.collect);before=self.snapshot(run)
        depth=np.load(run/result.outputs[0]['depth']['path'])
        bad=np.zeros((*depth.shape,3),dtype='<f4');bad[...,2]=depth*.745
        with patch('mde.results.backproject',return_value=bad):
            with self.assertRaisesRegex(ArtifactIntegrityError,'Z / z-depth'):
                view.view(h.run_id,'Point Cloud')
        self.assertFalse(list((run/'derived').glob('*/*/manifest.json')))
        point=view.view(h.run_id,'Point Cloud');mesh=view.view(h.run_id,'Mesh')
        # Digest-valid caches can still contain numerically invalid geometry.
        mesh_identity=mesh['derived']['identity']
        view.derived.get(run,mesh_identity,lambda:{'points':bad,'faces':np.empty((0,3),dtype='<u4')},force=True)
        with self.assertRaisesRegex(ArtifactIntegrityError,'Z / z-depth'):view.view(h.run_id,'Mesh')
        view.derived.get(run,point['derived']['identity'],lambda:{'points':bad},force=True)
        with self.assertRaisesRegex(ArtifactIntegrityError,'Z / z-depth'):view.view(h.run_id,'Point Cloud')
        self.assertEqual(before,self.snapshot(run))

    def test_version_one_bad_geometry_is_preserved_but_never_reused(self):
        import numpy as np
        from mde.results import ResultsService, MESH_PARAMETERS
        h,result,_=self.make_run(('depth','intrinsics'));run=self.store.root/h.run_id
        view=ResultsService(self.store,self.runner.collect)
        # Capture the exact dependencies before publishing any current geometry.
        identities=[]
        def capture(run,identity,generate,**kwargs):
            identities.append(identity);raise RuntimeError('capture identity')
        with patch.object(view.derived,'get',side_effect=capture):
            with self.assertRaisesRegex(RuntimeError,'capture identity'):view.view(h.run_id,'Mesh')
        bad=np.zeros((256,256,3),dtype='<f4');bad[...,2]=1.8625
        old_point={**identities[0],'version':'1'}
        old_mesh={**old_point,'algorithm':'grid-triangulation','parameters':MESH_PARAMETERS}
        for identity in (old_point,old_mesh):
            arrays={'points':bad}
            if identity['algorithm']=='grid-triangulation':arrays['faces']=np.empty((0,3),dtype='<u4')
            view.derived.get(run,identity,lambda:arrays)
        before={str(p):(sha256_file(p),p.stat().st_mtime_ns) for p in (run/'derived').glob('*/*/*') if p.is_file()}
        mesh=view.view(h.run_id,'Mesh');self.assertFalse(mesh['cache_reused'])
        self.assertEqual(mesh['derived']['identity']['version'],'2')
        self.assertTrue(view.view(h.run_id,'Mesh')['cache_reused'])
        for path,expected in before.items():self.assertEqual((sha256_file(Path(path)),Path(path).stat().st_mtime_ns),expected)
        with np.load(run/mesh['derived']['output']['path']) as payload:
            np.testing.assert_array_equal(payload['points'][...,2],np.load(run/result.outputs[0]['depth']['path']))

    def test_estimation_failure_has_no_fixed_fov_or_complete_geometry(self):
        from mde.results import ResultsService
        h,_,_=self.make_run(('depth',));est=self.estimator();est.estimate.side_effect=ValueError('cannot calibrate')
        view=ResultsService(self.store,self.runner.collect,camera_estimator=est)
        with self.assertRaisesRegex(ValueError,'cannot calibrate'):view.view(h.run_id,'Mesh')
        run=self.store.root/h.run_id
        self.assertFalse(list((run/'derived').glob('*/*/manifest.json')))
        est.estimate.side_effect=None;est.estimate.return_value['K'][0][0]=-1
        with self.assertRaises(ValueError):view.view(h.run_id,'Mesh')
        self.assertFalse(list((run/'derived').glob('*/*/manifest.json')))

    def test_unknown_grid_rejected_before_estimator_and_bad_cache_not_repaired(self):
        from mde.results import ResultsService
        h,_,_=self.make_run(('depth',),action='success');est=self.estimator()
        with self.assertRaisesRegex(ValueError,'3D unavailable'):ResultsService(self.store,self.runner.collect,camera_estimator=est).view(h.run_id,'Mesh')
        est.estimate.assert_not_called()
        h,_,_=self.make_run(('depth',));view=ResultsService(self.store,self.runner.collect,camera_estimator=est)
        points=view.view(h.run_id,'Point Cloud');cache=self.store.root/h.run_id/points['camera']['calibration_output']['path']
        cache.write_bytes(b'bad cache')
        with self.assertRaises(ArtifactIntegrityError):ResultsService(self.store,self.runner.collect).view(h.run_id,'Mesh')
        self.assertEqual(est.estimate.call_count,1)


class AuxiliaryBackendTests(unittest.TestCase):
    setUp=local_contract.LocalContractTests.setUp
    stop_workers=local_contract.LocalContractTests.stop_workers
    run_fake=local_contract.LocalContractTests.run_fake

    def request(self,behavior):
        work=Path(self.temporary.name)/('task-'+behavior);work.mkdir()
        request={'schema_version':'1.0','device':'cpu','entrypoint':'tests.fixtures.calibration:calibrate',
            'image_path':str(PROJECT/'tests/assets/sample.png'),'image_sha256':sha256_file(PROJECT/'tests/assets/sample.png'),'behavior':behavior}
        write_json(work/'request.json',request)
        reference={'environment_id':'mde-moge','definition_ref':'models/moge/environment.yml','definition_digest':sha256_file(PROJECT/'models/moge/environment.yml')}
        return reference,work/'request.json',work/'result.json',work

    def test_auxiliary_shared_admission_timeout_error_and_slot_reuse(self):
        saved,_,_=self.run_fake()
        original_spec=self.backend._jobs[saved.backend_job_id].spec
        args=self.request('hang')
        with ThreadPoolExecutor(max_workers=1) as pool:
            task=pool.submit(self.backend.execute_task,*args,timeout_seconds=2)
            deadline=time.monotonic()+5
            while not self.backend._auxiliary_active and time.monotonic()<deadline:time.sleep(.01)
            started=time.monotonic()
            with self.assertRaises(BackendBusy):self.runner.submit('fake',PROJECT/'tests/assets/sample.png',device='cpu')
            self.assertLess(time.monotonic()-started,1)
            with self.assertRaises(BackendBusy):self.backend.execute_task(*args,timeout_seconds=2)
            self.assertEqual(self.backend.submit(original_spec),saved)
            with self.assertRaises(TimeoutError):task.result(timeout=10)
        self.assertFalse(self.backend._auxiliary_active)
        with self.assertRaisesRegex(RuntimeError,'fixture calibration failed'):
            self.backend.execute_task(*self.request('error'),timeout_seconds=15)
        result=self.backend.execute_task(*self.request('success'),timeout_seconds=15)
        self.assertEqual(result['grid'],[256,256]);self.assertFalse(self.backend._auxiliary_active)

    def test_active_inference_refuses_auxiliary_and_task_protocol_checks_input(self):
        h=self.runner.submit('fake',PROJECT/'tests/assets/sample.png',device='cpu',parameters={'action':'block'})
        with self.assertRaises(BackendBusy):self.backend.execute_task(*self.request('unused'),timeout_seconds=2)
        self.runner.cancel(h)
        from mde.task_worker import execute
        with self.assertRaisesRegex(ValueError,'protocol'):execute({'schema_version':'2.0','device':'cpu'})
        request=read_json(self.request('bad-image')[1]);request['image_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'checksum'):execute(request)
