"""Checkpoint-free auxiliary task provider used in subprocess contracts."""
import time


def calibrate(request):
    behavior=request.get('behavior','success')
    if behavior=='error':raise ValueError('fixture calibration failed')
    if behavior=='hang':time.sleep(30)
    return {'K':[[300,0,127.5],[0,300,127.5],[0,0,1]],'grid':[256,256],
        'camera_model':'pinhole','pixel_center':'integer','camera_frame':'opencv_x_right_y_down_z_forward'}
