"""Per-pixel ray spacing of each saved first camera cloud (organized height x width, x forward/y left/z up).
Fits z/x against row and y/x against column on valid pixels and compares the slope with the spacing implied by the
recorded spec: square pixels from horizontal FOV and width (A2: no intrinsics), i.e. tan(hfov/2)/(width/2) per pixel.
Usage: python3 angle_steps.py RAW_FOLDER MANIFEST"""
import json, math, sys
from pathlib import Path
import numpy as np
raw, man = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
spec = man['sensor_configuration']['depth_camera_spec']
W, H = spec['width'], spec['height']
step = math.tan(math.radians(spec['horizontal_fov_deg'])/2)/(W/2)
out = dict(spec=spec, expected_tan_step_per_pixel=round(step, 6),
           implied_vertical_fov_deg=round(2*math.degrees(math.atan(step*H/2)), 4))
for c in ('camera1', 'camera2'):
    p = np.load(raw/f'first_cloud_{c}.npz')['points'].reshape(H, W, 3)
    rows = [(r, float(np.median(p[r, ok, 2]/p[r, ok, 0]))) for r in range(H) for ok in [np.isfinite(p[r]).all(1) & (p[r, :, 0] > 0)] if ok.sum() > 20]
    a = np.polyfit(*zip(*rows), 1)
    cols = [(k, float(np.median(p[ok, k, 1]/p[ok, k, 0]))) for k in range(W) for ok in [np.isfinite(p[:, k]).all(1) & (p[:, k, 0] > 0)] if ok.sum() > 10]
    b = np.polyfit(*zip(*cols), 1)
    out[c] = dict(row_step=round(-a[0], 6), row_ratio=round(-a[0]/step, 4), col_step=round(-b[0], 6), col_ratio=round(-b[0]/step, 4),
                  z_over_x_at_centre_row=round(float(np.polyval(a, (H-1)/2)), 5), rows_used=len(rows), cols_used=len(cols))
print(json.dumps(out, indent=1))
