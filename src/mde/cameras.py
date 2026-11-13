"""Application-side pinhole camera validation and explicit image-grid transforms."""
import numpy as np

from .geometry import FRAME


def pixel_k(value):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'fiu' or raw.shape != (3,3):
        raise ValueError('Camera K must be a numeric 3x3 matrix')
    k = np.asarray(raw, dtype=np.float64)
    if (not np.isfinite(k).all() or min(k[0,0],k[1,1]) <= 0
            or not np.allclose(k[2],[0,0,1],rtol=0,atol=1e-6) or abs(k[1,0]) > 1e-6):
        raise ValueError('Invalid finite positive pinhole camera K')
    return k


def grid(value):
    if not isinstance(value, (list,tuple)) or len(value)!=2 or any(type(x) is not int or x<1 for x in value):
        raise ValueError('Camera grid must be positive integer [height,width]')
    return list(value)


def output_transform(metadata, source_grid, output_grid):
    mapping=metadata.get('image_to_output',{})
    if source_grid==output_grid and mapping=={'type':'identity','pixel_center':'integer'}:
        return np.eye(3)
    if mapping.get('type')!='affine' or mapping.get('pixel_center')!='integer':
        raise ValueError('3D unavailable: camera mapping unavailable: no verified input-to-depth pixel transform')
    a=np.asarray(mapping.get('matrix'),dtype=np.float64)
    if (a.shape!=(3,3) or not np.isfinite(a).all() or not np.array_equal(a[2],[0,0,1])
            or a[0,0]<=0 or a[1,1]<=0 or a[0,1]!=0 or a[1,0]!=0):
        raise ValueError('Invalid resize/crop pixel transform')
    return a


def align_camera(camera, metadata, source_grid, output_grid):
    if camera.get('camera_model')!='pinhole' or camera.get('camera_frame')!=FRAME:
        raise ValueError('Only explicit pinhole / OpenCV camera calibration is supported')
    k=pixel_k(camera.get('K'));shape=grid(camera.get('grid'))
    center=camera.get('pixel_center')
    if center not in ('integer','half'):
        raise ValueError('Camera pixel_center must be integer or half')
    center_a=np.eye(3)
    if center=='half':center_a[:2,2]=-.5
    space=camera.get('grid_space')
    if space not in (None,'source','depth'):
        raise ValueError('Camera grid_space must be source or depth')
    if space=='source':
        if shape!=list(source_grid):raise ValueError('Source camera grid dimensions mismatch')
        a=output_transform(metadata,source_grid,output_grid)
    elif space=='depth':
        if shape!=list(output_grid):raise ValueError('Depth camera grid dimensions mismatch')
        a=np.eye(3)
    elif shape==list(source_grid)==list(output_grid):
        mapping=output_transform(metadata,source_grid,output_grid)
        if not np.array_equal(mapping,np.eye(3)):
            raise ValueError('Ambiguous camera grid: explicitly choose source or depth grid_space')
        a=np.eye(3)
    elif shape==list(output_grid):a=np.eye(3)
    elif shape==list(source_grid):a=output_transform(metadata,source_grid,output_grid)
    else:raise ValueError('Camera grid matches neither source image nor depth')
    try:
        with np.errstate(over='raise',invalid='raise'):
            converted=pixel_k(a @ center_a @ k).astype('<f4')
    except FloatingPointError as error:
        raise ValueError('Camera K cannot be represented in float32') from error
    pixel_k(converted)
    return converted,{'source_grid':shape,'output_grid':list(output_grid),'source_pixel_center':center,
        'pixel_center':'integer','source_grid_space':space or ('depth' if shape==list(output_grid) else 'source'),
        'source_K':k.tolist(),'pixel_transform':(a @ center_a).tolist(),
        'K':converted.tolist(),'camera_model':'pinhole','camera_frame':FRAME}
