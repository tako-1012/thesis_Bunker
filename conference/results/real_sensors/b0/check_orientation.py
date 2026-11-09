"""Stage B0 check 2: put each sensor's first saved cloud into world coordinates and compare with the true ground.

For each first_cloud*.npz (sensor-frame points, model-origin pose at the cloud stamp): range filter as the mapper does,
transform with the fixed REAL_MOUNTS, sample truth_elev bilinearly (0.5 m cells, cell (i, j) centred at (0.5 i, 0.5 j)),
and report dz = z_world - ground. Points on driftwood cells (truth_rock, dilated by one cell) are reported apart, since
Gazebo's driftwood is a 0.5 m box. Also: bearing of the points relative to the robot heading (left is positive),
and the slope of dz against forward / lateral distance (a tilt shows as a slope). As a control, the same numbers are
computed after reading the points as a ROS optical frame (x right, y down, z forward); the right reading has the
smaller |median dz| and the higher share within 0.10 m. Read-only. Usage (from conference/):
  PYTHONPATH=. python3 results/real_sensors/b0/check_orientation.py RAW_FOLDER"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates, binary_dilation
from tapp.sensor_geometry import REAL_MOUNTS, DepthCameraSpec, transform_sensor_points
RES = .5
raw = Path(sys.argv[1])
ref = np.load(raw/'evaluation_reference.npz')
elev, rock = ref['truth_elev'], binary_dilation(ref['truth_rock'], np.ones((3, 3), bool))
spec = DepthCameraSpec()
def keep(p, sensor):
    if sensor == 'lidar':
        d = np.linalg.norm(p, axis=1); return np.isfinite(p).all(1) & (d >= .9) & (d < 30.)
    x = p[:, 0]
    return (np.isfinite(p).all(1) & (x >= spec.min_range_m) & (np.linalg.norm(p, axis=1) < spec.max_range_m))
def stats(p, pose, sensor):
    if len(p) < 4:
        return dict(points=int(len(p)), note="fewer than 4 points pass the range filter in this reading")
    w = transform_sensor_points(p, pose, REAL_MOUNTS[sensor])
    ij = w[:, :2].T/RES
    g = map_coordinates(elev, ij, order=1, mode='nearest')
    on_rock = rock[np.clip(np.round(ij[0]).astype(int), 0, rock.shape[0]-1), np.clip(np.round(ij[1]).astype(int), 0, rock.shape[1]-1)]
    dz = w[:, 2]-g; ground = dz[~on_rock]
    yaw = pose[5]; rel = w[:, :2]-pose[:2]
    fwd = rel@np.array([np.cos(yaw), np.sin(yaw)]); lat = rel@np.array([-np.sin(yaw), np.cos(yaw)])
    bearing = np.degrees(np.arctan2(lat, fwd))
    A = np.c_[fwd, lat, np.ones_like(fwd)][~on_rock]
    slope = np.linalg.lstsq(A, ground, rcond=None)[0] if len(ground) > 3 else [np.nan]*3
    return dict(points=int(len(p)), ground_points=int(len(ground)), rock_points=int(on_rock.sum()),
                dz_median_m=round(float(np.median(ground)), 4), dz_abs_median_m=round(float(np.median(np.abs(ground))), 4),
                within_0p10_share=round(float((np.abs(ground) <= .10).mean()), 4),
                dz_p05_p95_m=[round(float(v), 3) for v in np.percentile(ground, [5, 95])],
                slope_dz_per_m_forward=round(float(slope[0]), 4), slope_dz_per_m_left=round(float(slope[1]), 4),
                bearing_deg_median=round(float(np.median(bearing)), 1), bearing_deg_p05_p95=[round(float(v), 1) for v in np.percentile(bearing, [5, 95])],
                forward_m_p05_median_p95=[round(float(v), 2) for v in np.percentile(fwd, [5, 50, 95])],
                rock_points_dz_median_m=round(float(np.median(dz[on_rock])), 3) if on_rock.any() else None)
out = {}
for f in sorted(raw.glob('first_cloud*.npz')):
    sensor = 'lidar' if f.stem == 'first_cloud' else f.stem.replace('first_cloud_', '')
    d = np.load(f); p, pose = d['points'].astype(float), d['pose'].astype(float)
    p = p[keep(p, sensor)] if sensor == 'lidar' else p
    row = dict(file=f.name, stamp=float(d['stamp']), pose=[round(float(v), 4) for v in pose], as_saved=None)
    if sensor == 'lidar':
        row['as_saved'] = stats(p, pose, sensor)
    else:
        row['as_saved'] = stats(p[keep(p, sensor)], pose, sensor)
        optical = np.c_[p[:, 2], -p[:, 0], -p[:, 1]]  # control reading: input as x right, y down, z forward
        row['if_optical_frame'] = stats(optical[keep(optical, sensor)], pose, sensor)
    out[sensor] = row
print(json.dumps(out, indent=1))
