"""Official fixed GeoCalib calibration task, never a fabricated depth model."""
import gc
import importlib.metadata
import json
from pathlib import Path

from mde.geometry import FRAME
from mde.storage import sha256_file


def calibrate(request):
    reference=json.loads(Path(__file__).with_name('task.json').read_text())
    if (request['task']!=reference or request.get('device')!='cpu' or request.get('dtype')!='float32'
            or request.get('seed')!=0):
        raise ValueError('Unsupported calibration identity or execution; no CPU fallback')
    checkpoint=Path(request['checkpoint_path']);expected=reference['checkpoint']
    if checkpoint.stat().st_size!=expected['size_bytes'] or sha256_file(checkpoint)!=expected['sha256']:
        raise ValueError('Calibration checkpoint checksum mismatch')
    installed=json.loads(importlib.metadata.distribution('geocalib').read_text('direct_url.json') or '{}')
    if installed.get('vcs_info',{}).get('commit_id')!=reference['upstream_revision']:
        raise ValueError('Installed calibration source revision mismatch')
    import torch
    if torch.__version__!='2.6.0+cpu':
        raise ValueError('Calibration requires the verified CPU torch build')
    from geocalib import GeoCalib
    model=None
    try:
        torch.manual_seed(request['seed'])
        # Safe loading only. Never retry with arbitrary pickle execution.
        state=torch.load(str(checkpoint),map_location='cpu',weights_only=True)
        model=GeoCalib(weights=str(checkpoint)).to(device='cpu',dtype=torch.float32).eval()
        # The native flexible loader is followed by full strict tensor/buffer
        # validation; all 889 fixed checkpoint keys match the native state.
        model.model.load_state_dict(state['model'],strict=True)
        image=model.load_image(Path(request['image_path'])).to(device='cpu',dtype=torch.float32)
        with torch.no_grad(),torch.autocast(device_type='cpu',enabled=False):
            result=model.calibrate(image,camera_model='pinhole')
        camera=result['camera'];k=camera.K.detach().cpu()
        if k.shape!=(1,3,3) or not torch.isfinite(k).all() or k[0,0,0]<=0 or k[0,1,1]<=0:
            raise ValueError('Camera estimation failed: invalid pinhole K')
        h,w=image.shape[-2:]
        if not torch.allclose(camera.size.cpu(),torch.tensor([[w,h]],dtype=torch.float32),rtol=0,atol=1e-4):
            raise ValueError('Calibration output grid differs from source RGB')
        if sha256_file(checkpoint)!=expected['sha256']:
            raise ValueError('Calibration checkpoint changed during inference')
        return {'K':k[0].tolist(),'grid':[h,w],'pixel_center':'integer','camera_model':'pinhole','camera_frame':FRAME}
    finally:
        model=None
        gc.collect()
