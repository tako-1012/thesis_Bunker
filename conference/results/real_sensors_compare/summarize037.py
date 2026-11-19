"""Task 037 descriptive tables and contact/failure evidence from retained Gazebo records."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from experiments import eval_035_report as audit
from tapp.config import RESOLUTION, Robot
from tapp.collision import segment_cells
from tapp.traversability import inflate, slope_deg

ROOT = Path(__file__).resolve().parent
SENSORS = {"L": "lidar_real", "LC": "lidar_real+depth2"}
audit.EXPECTED.update({k: {"sensors": v} for k, v in SENSORS.items()})


def nearby(cell, shape):
    return tuple(slice(max(0, i - 2), min(n, i + 3)) for i, n in zip(cell, shape))


def contact_evidence(folder, raw, tag):
    with np.load(raw / "evaluation_reference.npz") as ref:
        debris = ref["truth_rock"] & ~ref["prior_rock"]
        lethal = ref["truth_lethal"]
    poses = np.array([[float(row[k]) for k in ("t", "x", "y")]
                      for row in audit.read_csv_parts(raw / "trajectory.csv")])
    cells = np.rint(poses[:, 1:] / RESOLUTION).astype(int)
    valid = ((cells >= 0) & (cells < lethal.shape)).all(axis=1)
    revisions = [(float(row["t"]), np.array(json.loads(row["path"])))
                 for row in audit.read_csv_parts(raw / "path_revisions.csv")]
    snapshots = {}
    for f in sorted(folder.glob("diag_all/periodic_*.npz")):
        with np.load(f) as z:
            snapshots[float(z["sim_time"])] = f
    for name, mask in (("debris", debris), ("truth_lethal", lethal)):
        inside = np.zeros(len(cells), dtype=bool)
        inside[valid] = mask[tuple(cells[valid].T)]
        changes = np.flatnonzero(np.diff(np.r_[False, inside, False]))
        for first, end in changes.reshape(-1, 2):
            for index in range(first, end):
                if index > first and np.array_equal(cells[index], cells[index - 1]):
                    continue
                t, x, y = poses[index]
                cell = tuple(cells[index])
                row = dict(tag, mask=name, t=t, x=x, y=y, cell=cell,
                           episode_start=poses[first, 0], episode_end=poses[end - 1, 0])
                before = [stamp for stamp in snapshots if stamp <= t]
                if before:
                    stamp = max(before)
                    with np.load(snapshots[stamp]) as z:
                        row.update(map_time=stamp, map_age_s=t-stamp)
                        for field in ("lethal", "seen", "detected"):
                            grid = audit.bits(z, field)
                            row["map_" + field] = bool(grid[cell])
                            row["nearby_" + field] = int(grid[nearby(cell, grid.shape)].sum())
                paths = [(stamp, path) for stamp, path in revisions if stamp <= t and len(path) > 1]
                if paths:
                    stamp, path = max(paths, key=lambda item: item[0])
                    coords = path / RESOLUTION
                    traversed = np.concatenate([segment_cells(a, b, mask.shape)
                                                 for a, b in zip(coords[:-1], coords[1:])])
                    d = np.diff(path, axis=0)
                    offset = np.array([x, y]) - path[:-1]
                    alpha = np.clip((offset*d).sum(axis=1) / np.maximum((d*d).sum(axis=1), 1e-12), 0, 1)
                    row.update(path_time=stamp, path_offset_m=np.linalg.norm(offset-alpha[:, None]*d, axis=1).min(),
                               path_crosses_mask=bool(mask[tuple(traversed.T)].any()),
                               path_crosses_cell=bool((traversed == cell).all(axis=1).any()))
                yield row


def failure_evidence(raw, tag):
    with np.load(raw / "evaluation_reference.npz") as ref:
        truth_slope = slope_deg(ref["truth_elev"])
        truth_lethal = ref["truth_lethal"]
    for file in sorted((raw / "diag").glob("plan_fail_*.npz")):
        with np.load(file) as z:
            start, goal = tuple(z["start"]), tuple(z["goal"])
            lethal = audit.bits(z, "lethal")
            steep = inflate(audit.bits(z, "steep"), Robot().footprint_radius)
            detected = audit.bits(z, "detected")
            row = dict(tag, t=float(z["sim_time"]), start=start, goal=goal)
            for label, cell in (("start", start), ("goal", goal)):
                if all(0 <= i < n for i, n in zip(cell, lethal.shape)):
                    row.update({label + "_map_lethal": bool(lethal[cell]),
                                label + "_inflated_steep": bool(steep[cell]),
                                label + "_detected_5x5": int(detected[nearby(cell, lethal.shape)].sum()),
                                label + "_truth_lethal": bool(truth_lethal[cell]),
                                label + "_truth_slope": truth_slope[cell]})
            yield row


def detections(raw, tag):
    data = json.loads((raw / "pointcloud_map.npz.sensors.json").read_text())
    rows = data["first_detections"]
    camera_cells = set()
    for sensor in data["mounts"]:
        first = [r for r in rows if r["triggering_sensor"] == sensor]
        distance = [r["robot_distance_xy_m"] for r in first]
        # Unique cells whose first recorded insertion had no LiDAR support.
        camera_only = {tuple(r["fine_cell"]) for r in first
                       if sensor.startswith("camera") and not r["supporting_returns"].get("lidar", 0)}
        camera_cells.update(camera_only)
        yield dict(tag, sensor=sensor, detections=len(first),
                   distance_min_m=min(distance, default=None),
                   distance_median_m=np.median(distance) if distance else None,
                   camera_only_cells=len(camera_only))
    if len(data["mounts"]) > 1:
        yield dict(tag, sensor="camera_union", camera_only_cells=len(camera_cells))


def table(name, rows, group=(), excluded=()):
    frame = pd.DataFrame(rows)
    frame.to_csv(ROOT / (name + ".csv"), index=False)
    if frame.empty:
        print(name, "no records")
        return
    if group:
        numeric = [c for c in frame.select_dtypes(include="number") if c not in excluded]
        stats = frame.groupby(list(group))[numeric].agg(["count", "min", "median", "max"])
        stats.columns = ["_".join(c) for c in stats.columns]
        stats.to_csv(ROOT / (name + "_grouped.csv"))
        print(name, stats.to_string())
    else:
        print(name, len(frame), "rows")


def main():
    runs, sensors, first, contacts, failures, errors = [], [], [], [], [], []
    for patch_dir in sorted((ROOT / "runs").iterdir()):
        terrain = audit.build_real(patch_dir.name, 200, 0, debris=True, dataset="shizuoka_beach_las")["terrain"]
        for folder in sorted(patch_dir.iterdir()):
            condition, rep = folder.name.split("_r")
            tag = dict(patch=patch_dir.name, condition=condition, rep=int(rep))
            try:
                raw = folder / "physical_1" / "raw" / patch_dir.name
                row, raw = audit.run_row(folder, patch_dir.name, condition, int(rep), terrain)
                row["outcome"] = audit.outcome(row)
                runs.append(row)
            except (ValueError, KeyError, OSError, StopIteration, IndexError, AttributeError) as exc:
                exit_file = folder / "exit.txt"
                row = dict(tag, outcome="record_incomplete",
                           exit_code=exit_file.read_text().strip() if exit_file.exists() else None)
                manifest = folder / "physical_1" / "manifest.json"
                if manifest.exists():
                    cases = json.loads(manifest.read_text()).get("cases", [])
                    case = next((item for item in cases if item.get("selected")), {})
                    row.update(recorded_status=case.get("termination"),
                               online_error=case.get("error"),
                               planning_status=case.get("planning_status"))
                runs.append(row)
                errors.append(dict(tag, field="run", error=repr(exc)))
            for field, target, fn in (
                ("updates", sensors, lambda: (dict(tag, **r) for r in audit.sensor_update_table(raw))),
                ("detections", first, lambda: detections(raw, tag)),
                ("contacts", contacts, lambda: contact_evidence(folder, raw, tag)),
                ("failures", failures, lambda: failure_evidence(raw, tag)),
            ):
                try:
                    target.extend(fn())
                except (ValueError, KeyError, OSError, IndexError, AttributeError) as exc:
                    errors.append(dict(tag, field=field, error=repr(exc)))
    counts = pd.DataFrame(runs).groupby(["patch", "condition", "outcome"]).size().unstack(fill_value=0)
    counts.to_csv(ROOT / "outcome_counts.csv")
    print(counts.to_string())
    for name, rows, group in (("runs", runs, ("patch", "condition")),
                              ("sensor_updates", sensors, ("patch", "condition", "sensor")),
                              ("first_detections", first, ("patch", "condition", "sensor"))):
        table(name, rows, group, excluded=("rep",))
    old = ROOT.parent / "eval_035/runs/08OB86_-0205/S1_r1"
    try:
        record = old / "physical_1/raw/08OB86_-0205"
        table("s1_035_contact_evidence", list(contact_evidence(
            old, record, dict(patch="08OB86_-0205", condition="035_S1", rep=1))))
    except (ValueError, OSError, IndexError, KeyError) as exc:
        print("035 S1 original evidence unavailable", repr(exc))
    table("contact_evidence", contacts)
    table("failure_evidence", failures)
    table("missing_records", errors)
    print("Run records:", len(runs), "/ 30")


if __name__ == "__main__":
    main()
