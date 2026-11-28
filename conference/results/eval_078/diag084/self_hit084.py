"""Inspect near returns and replay 076 with and without the fixed self-hit filter."""

from collections import Counter, defaultdict
import csv
from dataclasses import replace
from itertools import product
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

from experiments import offline_localization as offline
from experiments.recording_bridge import open_archive
from ros2_jazzy.src.thesis_bunker_gz.thesis_bunker_gz.model import make_model
from tapp.sensor_recording import iter_lidar

ROOT = Path(__file__).resolve().parent
TRIALS = {
    "1417_d160_s0": "08OB88_-1417/d160_s0",
    "1417_d0_s0": "08OB88_-1417/d0_s0",
    "0205_d40_s1": "08OB86_-0205/d40_s1",
}
BANDS = {"0.1–1m": (.1, 1.), "1–2m": (1., 2.)}
PADDING_M = .05
BIN_M = .05
CUTOFF_M = 1.
STOP_M_S = .05
MOVE_M_S = .2


def write(path, rows):
    rows = list(rows)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name}: {len(rows)} rows", flush=True)


def raw_for(trial):
    physical = ROOT.parent/"runs"/TRIALS[trial]/"physical_1"
    manifest = json.loads((physical/"manifest.json").read_text())
    case, = [case for case in manifest["cases"] if case["selected"]]
    return physical/case["run_folder"]


def transform(pose):
    x, y, z, roll, pitch, yaw = map(float, pose.split())
    mat = np.eye(4)
    mat[:3, 3] = x, y, z
    mat[:3, :3] = Rotation.from_euler("xyz", (roll, pitch, yaw)).as_matrix()
    return mat


def collision_bounds(base_from_lidar):
    """Bounds of the body and wheel collision solids in the LiDAR frame."""
    with TemporaryDirectory() as temp:
        path = make_model(Path(temp)/"model.sdf", sensor_preset="real_bunker", depth_cameras=True)
        model = ET.parse(path).getroot().find("model")
    lidar_from_base = np.linalg.inv(base_from_lidar)
    intervals = []
    for link in model.findall("link"):
        from_link = lidar_from_base @ transform(link.findtext("pose", "0 0 0 0 0 0"))
        for solid in link.findall("collision"):
            frame = from_link @ transform(solid.findtext("pose", "0 0 0 0 0 0"))
            rotation = frame[:3, :3]
            box = solid.find("geometry/box")
            cylinder = solid.find("geometry/cylinder")
            if box is not None:
                half = np.abs(rotation) @ (np.array(box.findtext("size").split(), dtype=float)/2)
            elif cylinder is not None:
                axis = np.abs(rotation[:, 2])
                radius, length = (float(cylinder.findtext(name)) for name in ("radius", "length"))
                half = radius*np.sqrt(np.maximum(0., 1-axis**2)) + length/2*axis
            else:
                raise ValueError("Model collision solid is neither a box nor a cylinder")
            intervals.append((frame[:3, 3]-half, frame[:3, 3]+half))
    lidar = model.find("link/sensor[@name='lidar']/lidar")
    assert lidar is not None
    limits = dict(lidar_min_range_m=float(lidar.findtext("range/min")),
                  lidar_min_elev_deg=np.degrees(float(lidar.findtext("scan/vertical/min_angle"))))
    lower = np.min([a for a, _ in intervals], axis=0)
    upper = np.max([b for _, b in intervals], axis=0)
    return lower, upper, limits


def in_box(xyz, lower, upper):
    return ((lower <= xyz) & (xyz <= upper)).all(axis=1)


def filtered(scans, lower, upper):
    for scan in scans:
        p = np.asarray(scan)
        finite = p[np.isfinite(p).all(axis=1)]
        radii = np.linalg.norm(finite, axis=1)
        yield finite[(radii >= CUTOFF_M) & ~in_box(finite, lower, upper)]


def motion_labels(archive):
    indices, truth = offline.synchronized_truth(archive.lidar_stamp_ns, archive.truth_stamp_ns,
                                                offline.poses_from_xyz_quat(archive.truth_values))
    dt = np.diff(archive.lidar_stamp_ns[indices])/1e9
    speeds = np.r_[np.nan, np.linalg.norm(np.diff(truth[:, :3, 3], axis=0), axis=1)/dt]
    return dict(zip(indices, speeds, strict=True))


def summarize_band(trial, band, collected, counts, occupancy, motion_counts):
    points = np.concatenate(collected) if collected else np.empty((0, 3))
    m = dict(trial=trial, band=band, frames=len(counts), frames_with_points=np.count_nonzero(counts),
             points=len(points), min_per_scan=min(counts), median_per_scan=np.median(counts), max_per_scan=max(counts),
             mean_per_scan=np.mean(counts))
    for i, (axis, tags) in enumerate(zip("xyz", (("forward", "backward"), ("left", "right"), ("up", "down")))):
        n = points[:, i]
        m[tags[0]], m[tags[1]] = int(np.count_nonzero(n>0)), int(np.count_nonzero(n<0))
        for name, reducer in (("min", np.min), ("median", np.median), ("max", np.max)):
            m[f"{axis}_{name}_m"] = float(reducer(n)) if len(n) else None
    stationary, moving = (occupancy[group] for group in ("stationary", "moving"))
    cross = stationary.keys() & moving.keys()
    recurring = [cell for cell in cross if (stationary[cell]*2 >= motion_counts["stationary"]
                                            and moving[cell]*2 >= motion_counts["moving"])]
    top = sorted(cross, key=lambda cell: (-min(stationary[cell]/motion_counts["stationary"],
                    moving[cell]/motion_counts["moving"]), cell))[:1]
    recurrence = dict(trial=trial, band=band, stationary_frames=motion_counts["stationary"],
                      moving_frames=motion_counts["moving"], cells_in_both=len(cross),
                      cells_in_at_least_half_of_both=len(recurring), strongest_shared_bin_xyz_m=None,
                      strongest_stationary_frames=None, strongest_moving_frames=None)
    if top:
        cell = top[0]
        recurrence.update(strongest_shared_bin_xyz_m=json.dumps(((np.array(cell)+.5)*BIN_M).tolist()),
                          strongest_stationary_frames=stationary[cell], strongest_moving_frames=moving[cell])
    return m, recurrence


def inspect_archive(trial):
    raw = raw_for(trial)
    archive = open_archive(raw)
    low, high, limits = collision_bounds(archive.base_from_lidar)
    lower, upper = low-PADDING_M, high+PADDING_M
    xy_reach = max(np.linalg.norm(p) for p in product(*zip(lower[:2], upper[:2])))
    assert upper[2] < 0, raw
    steepest_top = np.degrees(np.arctan2(upper[2], xy_reach))
    bounds = dict(trial=trial, mount_xyz_m=json.dumps(archive.base_from_lidar[:3, 3].tolist()),
                  pad_m=PADDING_M, range_cutoff_m=CUTOFF_M, unpadded_lower_xyz_m=json.dumps(low.tolist()),
                  unpadded_upper_xyz_m=json.dumps(high.tolist()), lower_xyz_m=json.dumps(lower.tolist()),
                  upper_xyz_m=json.dumps(upper.tolist()), shallowest_box_elev_deg=steepest_top, **limits)
    speeds = motion_labels(archive)
    motion_counts = Counter()
    frames, pooled, counts = [], defaultdict(list), defaultdict(list)
    occupancy = defaultdict(lambda: defaultdict(Counter))
    for i, scan in enumerate(iter_lidar(raw/"sensors")):
        assert scan.stamp_ns == archive.lidar_stamp_ns[i], raw
        speed = speeds.get(i, np.nan)
        motion = ("stationary" if speed <= STOP_M_S else "moving" if speed >= MOVE_M_S
                  else "intermediate" if np.isfinite(speed) else "unclassified")
        motion_counts[motion] += 1
        xyz = scan.xyz.reshape(-1, 3)
        finite = xyz[np.isfinite(xyz).all(axis=1)]
        radii = np.linalg.norm(finite, axis=1)
        inside = in_box(finite, lower, upper)
        clip = (radii < CUTOFF_M) | inside
        original = (radii > offline.MIN_RANGE_M) & (radii < offline.MAX_RANGE_M)
        frame = dict(trial=trial, scan=i, stamp_ns=scan.stamp_ns, motion=motion,
                     truth_speed_m_s=speed if np.isfinite(speed) else None, finite_points=len(finite),
                     body_box_points=np.count_nonzero(inside), strictly_below_1m_points=np.count_nonzero(radii < CUTOFF_M),
                     original_076_points=np.count_nonzero(original), removed_from_076=np.count_nonzero(original & clip))
        for band, (lo, hi) in BANDS.items():
            points = finite[(lo <= radii) & (radii < hi)]
            frame[band] = len(points)
            counts[band].append(len(points))
            if len(points):
                pooled[band].append(points)
                occupancy[band][motion].update(map(tuple, np.unique(np.floor(points/BIN_M).astype(int), axis=0)))
        frames.append(frame)
    assert len(frames) == len(archive.lidar_stamp_ns)
    band_rows, recurrence = zip(*(summarize_band(trial, band, pooled[band], counts[band], occupancy[band],
                                                 motion_counts) for band in BANDS))
    return bounds, frames, band_rows, recurrence


def replay(trial, mode):
    raw = raw_for(trial)
    recording, reference_path, _ = offline.load_run_directory(raw)
    reference = offline.load_reference(reference_path)
    if mode == "filtered":
        lo, hi, _ = collision_bounds(recording.base_from_lidar)
        recording = replace(recording, scans=filtered(recording.scans, lo-PADDING_M, hi+PADDING_M))
    print(f"{trial} {mode}: 076 replay of {len(recording.stamps_ns)} scans", flush=True)
    result = offline.localize(recording, reference)
    _, metrics = offline.trajectory_metrics(recording, result)
    output = ROOT/"replay"/trial/mode
    output.mkdir(parents=True, exist_ok=False)
    tag = dict(trial=trial, mode=mode)
    aligned = [dict(tag, **r) for r in offline.alignment_rows(result.alignments, int(recording.stamps_ns[0]))]
    summary = []
    for row in metrics:
        events = [event for event in aligned if event["method"] == row["method"]]
        gicp = row["method"] != "odometry"
        converged = sum(event["converged"] for event in events)
        denom = len(events) if gicp else None
        summary.append(dict(tag, **row, discarded_scans=recording.discarded_scans, attempts=denom,
                            converged=converged if gicp else None, converged_fraction=converged/denom if denom else None,
                            accepted=sum(event["accepted"] for event in events) if gicp else None))
    write(output/"summary.csv", summary)
    write(output/"alignments.csv", aligned)
    print(json.dumps(summary, default=lambda val: val.item(), allow_nan=False), flush=True)


def main():
    if sys.argv[1:] == ["inspect"]:
        geometry, frames, bands, slices = [], [], [], []
        for name in TRIALS:
            bounds, scans, group, recurrent = inspect_archive(name)
            geometry.append(bounds)
            frames.extend(scans)
            bands.extend(group)
            slices.extend(recurrent)
            print(name, len(scans), "body box", sum(r["body_box_points"] for r in scans),
                  "removed from 076", sum(r["removed_from_076"] for r in scans), flush=True)
        for filename, rows in (("body_geometry.csv", geometry), ("near_points_by_scan.csv", frames),
                               ("near_points_by_band.csv", bands), ("near_point_recurrence.csv", slices)):
            write(ROOT/filename, rows)
        return
    trial, mode = sys.argv[1:]
    if trial not in TRIALS or mode not in ("raw", "filtered"):
        raise ValueError("Use inspect or a known trial with raw/filtered")
    replay(trial, mode)


if __name__ == "__main__":
    main()
