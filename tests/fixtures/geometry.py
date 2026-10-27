"""Test-only geometry source, independent of real models."""
from mde.contracts import MDEOutput, PredictionBatch
from tests.fixtures.fake import FakeAdapter


class GeometryAdapter(FakeAdapter):
    def predict(self, request):
        import numpy as np
        print("geometry predict", flush=True)
        h, w = request.image.shape[:2]
        action = request.parameters["action"]
        depth = np.full((h, w), 2.5, dtype=np.float32)
        points = np.zeros((h, w, 3), dtype=np.float32)
        points[..., 0], points[..., 1], points[..., 2] = 0.25, -0.5, depth
        if action == "viewer":
            y, x = np.indices((h, w))
            points[..., 0] = (x-(w-1)/2)*depth/300
            points[..., 1] = (y-(h-1)/2)*depth/300
        normals = np.zeros_like(points)
        normals[..., 2] = -1
        k = np.array([[300, 0, (w-1)/2], [0, 300, (h-1)/2], [0, 0, 1]], dtype=np.float32)
        mask = np.ones((h, w), dtype=bool)
        mask[0, 0] = False
        points[0, 0] = np.inf
        if action == "ray":
            depth = np.linalg.norm(points, axis=-1)
        meanings = {key: {"origin": "model", "conversion": "identity",
                         "native_convention": "fixture", "camera_frame": "opencv_x_right_y_down_z_forward"}
                    for key in ("points", "normals", "intrinsics", "model_mask")}
        meanings["points"]["scale_type"] = "relative"
        meanings["normals"]["orientation"] = "camera facing"
        meanings["intrinsics"].update(camera_model="pinhole", pixel_center="integer", grid=[h, w])
        if action == "missing_points": points = None
        if action == "missing_normals": normals = None
        if action == "missing_intrinsics": k = None
        if action == "missing_mask": mask = None; points[0, 0] = [0.25, -0.5, 2.5]
        if action == "shape": points = points[:-1]
        if action == "object": points = points.astype(object)
        if action == "nonfinite": points[1, 1, 0] = np.inf
        if action == "scale": points[1, 1, 2] = 5
        if action == "normal": normals[1, 1, 2] = 0.5
        if action == "intrinsics": k[0, 0] = -1
        if action == "mask_shape": mask = mask[:-1]
        if action == "mask_dtype": mask = mask.astype(np.float32)
        if action == "provenance": meanings["points"] = {}
        if action == "frame": meanings["points"]["camera_frame"] = "unknown"
        metadata = {"depth_kind": "ray_distance" if action == "ray" else "z_depth", "scale_type": "relative",
             "depth_unit": "arbitrary", "camera_frame": "opencv_x_right_y_down_z_forward", "geometry": meanings}
        if action == "viewer":
            metadata["image_to_output"] = {"type": "identity", "pixel_center": "integer"}
        return PredictionBatch([MDEOutput(request.view_id, depth, metadata,
             points=points, normals=normals, intrinsics=k, mask=mask)])
