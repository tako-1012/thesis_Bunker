"""Audit close approaches and terminal states in retained task 044 records."""
import csv
import json
from pathlib import Path

import numpy as np

from experiments.eval_runs import near_intervals, nearest_path, read_csv, read_trajectory
from tapp.config import RESOLUTION, Robot
from tapp.endpoint_policy import load_snapshot
from tapp.obstacle_clearance import path_clearance, point_clearance
from tapp.traversability import inflate, slope_deg

ROOT = Path(__file__).resolve().parent
RADIUS = Robot().footprint_radius


def write(name, records):
    keys = list(dict.fromkeys(k for row in records for k in row))
    with (ROOT / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def logs(path):
    return read_csv(path)[1]


def trajectory(raw):
    trace, _, _ = read_trajectory(raw)
    return trace[:, 0], trace[:, 1:]


def revisions(raw):
    rows = logs(raw / "path_revisions.csv")
    return np.array([float(r["t"]) for r in rows]), [np.array(json.loads(r["path"])) for r in rows]


def active(times, stamp):
    idx = np.searchsorted(times, stamp, side="right") - 1
    if idx < 0:
        raise ValueError("no path revision at event")
    return idx


def distinct(path):
    return path[np.r_[True, (np.diff(path, axis=0) != 0).any(axis=1)]]


def closest_fraction(a, b, lo, hi):
    """Minimize squared rectangle distance, piecewise quadratic along a segment."""
    d = b-a
    gaps = ((side-a)[d != 0] / d[d != 0] for side in (lo, hi))
    bounds = np.unique(np.clip(np.concatenate(([0., 1.], *gaps)), 0, 1))
    candidates = list(bounds)
    for l, r in zip(bounds[:-1], bounds[1:]):
        mid = a + d * ((l+r)/2)
        outside = (mid < lo) | (mid > hi)
        dd = d[outside]
        if dd @ dd:
            offset = (a - np.clip(mid, lo, hi))[outside]
            candidates.append(float(np.clip(-(offset @ dd) / (dd @ dd), l, r)))
    return min(candidates, key=lambda u: point_clearance(a + u*d, lo[None], hi[None]))


def near_episodes(t, xy, lo, hi):
    episodes = []
    for a, b, start, end in zip(xy[:-1], xy[1:], t[:-1], t[1:]):
        nearby = ((lo-RADIUS < np.maximum(a, b)) & (hi+RADIUS > np.minimum(a, b))).all(axis=1)
        for left, right in near_intervals(a, b, lo[nearby], hi[nearby]):
            enter, leave = start + left*(end-start), start + right*(end-start)
            if episodes and abs(enter-episodes[-1][1]) < 1e-9:
                episodes[-1][1] = leave
            else:
                episodes.append([enter, leave])
    return episodes


def detected_box(raw, lo, hi, stamp):
    """Count fine cells with positive footprint overlap recorded by a given time."""
    data = json.loads((raw / "pointcloud_map.npz.sensors.json").read_text())
    points = data["first_detections"]
    cells = np.array([x["fine_cell"] for x in points])
    cell_lo = cells*.1-.25
    overlap = ((cell_lo < hi-1e-8) & (cell_lo+.1 > lo+1e-8)).all(axis=1)
    times = [float(r["stamp_sim_s"]) for hit, r in zip(overlap, points) if hit]
    return dict(box_fine_cells_before=sum(v <= stamp for v in times),
                box_fine_cells_final=len(times), first_box_detection_s=min(times, default=None))


def approaches(raw, row, id_fields):
    t, xy = trajectory(raw)
    box = np.array([[float(r[k]) for k in ("xmin", "ymin", "xmax", "ymax")]
                    for r in logs(raw / "debris_footprints.csv")])
    low, high = box[:, :2], box[:, 2:]
    times, paths = revisions(raw)
    records = []
    for start, end in near_episodes(t, xy, low, high):
        best = (float("inf"), None, None, None)
        for i in np.flatnonzero((t[:-1] < end) & (t[1:] > start)):
            a, b = xy[i:i+2]
            nearby = ((low-RADIUS < np.maximum(a, b)) & (high+RADIUS > np.minimum(a, b))).all(axis=1)
            for j in np.flatnonzero(nearby):
                fraction = closest_fraction(a, b, low[j], high[j])
                stamp = t[i]+fraction*(t[i+1]-t[i])
                if not start <= stamp <= end:
                    continue
                pos = a+fraction*(b-a)
                distance = point_clearance(pos, low[j:j+1], high[j:j+1])
                if distance < best[0]:
                    best = distance, stamp, j, pos
        distance, stamp, box_index, pos = best
        np.testing.assert_allclose(distance, float(row["min_truth_clearance_m"]), atol=1e-8)
        np.testing.assert_allclose(end-start, float(row["truth_below_radius_s"]), atol=1e-8)
        revision = active(times, stamp)
        path = distinct(paths[revision])
        deviation, segment, projected = nearest_path(pos[None], path)
        lo, hi = low[box_index:box_index+1], high[box_index:box_index+1]
        segment_xy = path[segment[0]:segment[0]+2] if len(path)>1 else path
        episode_samples = np.flatnonzero((t >= start) & (t <= end))
        offsets = [nearest_path(xy[i:i+1], distinct(paths[active(times,t[i])]))[0][0]
                   for i in episode_samples]
        records.append(dict(id_fields, entered_s=start, exited_s=end, duration_s=end-start,
            nearest_t_s=stamp, min_box_m=distance, x=pos[0], y=pos[1],
            box_xyxy=json.dumps(box[box_index].tolist()), path_t_s=times[revision],
            path_to_same_box_m=path_clearance(path, lo, hi),
            nearest_path_segment_to_box_m=path_clearance(segment_xy, lo, hi),
            projected_point_to_box_m=point_clearance(projected[0], lo, hi),
            deviation_at_nearest_m=deviation[0], deviation_max_during_m=max(offsets+[deviation[0]]),
            path_revisions_in_window=int(((times>start)&(times<=end)).sum()),
            **detected_box(raw, low[box_index], high[box_index], stamp)))
    assert len(records) == int(row["truth_below_radius_entries"])
    return records


def obstacle_halo(fine, cell, overlap):
    """Whether this coarse cell meets the mapper's integer fine-dilation rule."""
    base = np.array(cell)*5
    query = base+np.array([[i,j] for i in range(5) for j in range(5)] if overlap else [[2,2]])
    lo = np.maximum(query.min(axis=0)-6, 0)
    hi = np.minimum(query.max(axis=0)+7, fine.shape)
    hits = np.argwhere(fine[tuple(slice(a,b) for a,b in zip(lo,hi))])+lo
    delta = np.maximum(2*np.abs(query[:,None]-hits)-(2 if overlap else 1),0)
    return bool((np.sum(delta**2,axis=-1) <= (2*RADIUS/.1)**2).any())


def cell_evidence(z, ref, cell, config):
    overlap = config in ("O", "OT")
    near = tuple(slice(max(0,i-2), i+3) for i in cell)
    known = bool(z["known"][cell])
    return dict(cell=str(list(map(int, cell))), lethal=bool(z["lethal"][cell]), known=known,
        seen=bool(z["seen"][cell]), truth_lethal=bool(ref["truth_lethal"][cell]),
        steep=bool(inflate(z["steep"], RADIUS)[cell]),
        prior_rock=bool(inflate(z["prior_raw"], RADIUS)[cell]),
        actual_obstacle_halo=obstacle_halo(z["fine_obstacle"], cell, overlap),
        centre_halo=obstacle_halo(z["fine_obstacle"], cell, False),
        overlap_halo=obstacle_halo(z["fine_obstacle"], cell, True),
        local_lethal_cells=int(z["lethal"][near].sum()),
        local_detected_cells=int(z["detected"][near].sum()))


def unusual(raw, row, tag):
    t, xy = trajectory(raw)
    times, paths = revisions(raw)
    end = t[-1]
    win = t >= end - 3
    poses = logs(raw / "trajectory.csv")
    events = logs(raw / "safety_events.csv")
    final_mission = json.loads((raw / "mission.json").read_text())
    if row["outcome"] in ("stuck", "pose_timeout"):
        updates = logs(raw / "map_updates.csv")
        last = dict(tag, outcome=row["outcome"], finish_t_s=final_mission["finished_t"],
                    last_pose_s=end, x=xy[-1,0], y=xy[-1,1],
                    pose_max_gap_last_3s=float(np.diff(t[win]).max()),
                    pose_displacement_last_3s_m=float(np.linalg.norm(xy[-1]-xy[win][0])),
                    v_last=float(poses[-1]["v"]), w_last=float(poses[-1]["w"]),
                    last_cloud_stamp_s=max(float(r["stamp"]) for r in updates),
                    last_path_s=float(times[-1]), heading_deg=np.degrees(float(poses[-1]["yaw"])))
        if row["outcome"] == "stuck":
            snapshots = list((raw / "diag").glob("periodic_*.npz"))
            z = max((load_snapshot(f) for f in snapshots), key=lambda s: s["sim_time"])
            with np.load(raw/"evaluation_reference.npz") as ref:
                last.update(cell_evidence(z, ref, tuple(np.rint(xy[-1]/RESOLUTION).astype(int)), row["condition"]))
                last["snapshot_s"] = float(z["sim_time"])
                last["grid_5x5"] = "/".join("".join(str(int(v)) for v in line)
                    for line in z["lethal"][278:283,115:120])
            stop = json.loads(row["stops_detail"])[-1]
            last.update(last_stop_s=stop["t"], moved_after_stop_m=stop["moved_until_end_m"],
                        stationary_tail_s=row["stationary_tail_s"])
            near = [e for e in events if e["event"] == "safety_replanned"
                     and stop["t"] <= float(e["sim_time"]) <= end]
            last["replanned_s"] = float(near[0]["sim_time"]) if near else None
            if len(paths[-1]) > 1:
                last["last_path_first_two_xy"] = json.dumps(paths[-1][:2].tolist())
        return [last]
    if int(row["ev_unsafe_tilt"]):
        out = []
        for detail in json.loads(row["stops_detail"]):
            if detail["kind"] != "unsafe_tilt":
                continue
            stamp = detail["t"]
            future = [e for e in events if float(e["sim_time"]) >= stamp and e["event"] == "safety_replanned"]
            pose = min(poses, key=lambda r: abs(float(r["t"])-stamp))
            stop_pose = [json.loads(e["detail"])["pose"]
                         for f in (raw/"follower").glob("*/safety_stops.csv") for e in logs(f)
                         if e["event"] == "unsafe_tilt" and float(e["sim_time"]) == stamp]
            if stop_pose:
                roll, pitch = stop_pose[0][3:5]
            else:
                roll, pitch = float(pose["roll"]), float(pose["pitch"])
            out.append(dict(tag, outcome="unsafe_tilt", t_s=stamp, x=pose["x"], y=pose["y"],
                roll_deg=np.degrees(roll), pitch_deg=np.degrees(pitch),
                replan_s=future[0]["sim_time"] if future else None, moved_30s_m=detail["moved_30s_m"],
                repeated=row["ev_unsafe_tilt_repeat"], mission_outcome=row["outcome"]))
        return out
    return []


def main():
    records = logs(ROOT / "common_eval/runs.csv")
    assert len(records)==60
    close, failures, others = [], [], []
    for row in records:
        tag = {k:row[k] for k in ("patch","condition","rep")}
        raw = Path(row["run"])
        if int(row["truth_below_radius_entries"]):
            close.extend(approaches(raw,row,tag))
        if row["outcome"]=="no_path":
            snapshots = sorted((raw/"diag").glob("plan_fail_*.npz"))
            assert snapshots and row["no_path_type"] == "goal_cell"
            z = load_snapshot(snapshots[-1])
            goal = tuple(z["goal"])
            with np.load(raw/"evaluation_reference.npz") as ref:
                failures.append(dict(tag, failure=row["no_path_type"], reached=row["goals_reached"],
                    t_s=float(z["sim_time"]), file=snapshots[-1].name,
                    slope_deg=slope_deg(z["elev"])[goal], **cell_evidence(z, ref, goal, row["condition"])))
        if int(row["ev_unsafe_tilt"]) or row["outcome"] in ("stuck","pose_timeout"):
            others.extend(unusual(raw,row,tag))
    for name, values in (("approach_evidence.csv",close),("no_path_evidence.csv",failures),("terminal_evidence.csv",others)):
        write(name, values)
        print(name, len(values))


if __name__ == "__main__":
    main()
