"""Supplement common evaluation with task 050 slope metrics and saved search evidence."""
import csv
import json
from pathlib import Path

import numpy as np

from experiments.eval_runs import nearest_path, read_csv, read_trajectory
from experiments.plan_map_inspect import causes
from tapp.config import RESOLUTION, Robot
from tapp.endpoint_policy import audit_path, load_snapshot
from tapp.pure_pursuit import prepare_path
from tapp.traversability import inflate, slope_deg

ROOT = Path(__file__).resolve().parent
ROBOT = Robot()
TARGET_0167 = (137, 294)


def records(path):
    return read_csv(path)[1]


def write(name, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (ROOT / name).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows)} rows", flush=True)


def masks(raw):
    with np.load(raw / "evaluation_reference.npz") as ref:
        truth = slope_deg(ref["truth_elev"]) > ROBOT.max_slope_deg
        prior = slope_deg(ref["prior_elev"]) > ROBOT.max_slope_deg
        return truth, inflate(truth, ROBOT.footprint_radius), inflate(prior, ROBOT.footprint_radius)


def terrain(raw, revisions, truth, halo):
    trace, _, _ = read_trajectory(raw)
    travel = audit_path(trace[:, 1:], halo, truth)
    path_audits = [audit_path(json.loads(row["path"]), halo, truth) for row in revisions]
    return dict(
        plan_revisions=len(path_audits),
        plan_true_steep_m=sum(v["truth_lethal_length_m"] for v in path_audits),
        plan_true_halo_m=sum(v["relaxed_length_m"] for v in path_audits),
        travel_true_steep_m=travel["truth_lethal_length_m"],
        travel_true_halo_m=travel["relaxed_length_m"],
    )


def verify_manifest(raw, tag):
    manifest = json.loads((raw.parents[1] / "manifest.json").read_text())
    condition = tag["condition"]
    expected = dict(only_patch=tag["patch"], execution="finished", protocol="rtf_check",
                    patch_count=3, real_time_factor=.3, diagnostics=True, software_rendering="1",
                    stale_timeout_s=1.0, online_fixes="v2", map_method="fine",
                    ground_estimate="non_obstacle", sensors="lidar_real+depth2", save_plan_maps=True,
                    obstacle_clearance="centre" if condition == "S" else "overlap_goal",
                    terrain_source="prior" if condition == "PG" else "sensor")
    defaults = {"save_plan_maps": False, "terrain_source": "sensor", "obstacle_clearance": "centre"}
    for key, value in expected.items():
        assert manifest.get(key, defaults.get(key)) == value, (tag, key, manifest.get(key), value)
    assert manifest.get("steep_near_obstacle", "keep") == ("no_inflate" if condition == "SGN" else "keep"), tag
    assert manifest.get("endpoint_policy") == "none"
    return manifest


def terminal_map(folder, failure_type, prior, truth, halo):
    applications = []
    for path in folder.glob("applied_*.npz"):
        with np.load(path) as record:
            applications.append((float(record["sim_time"]), int(record["plan_id"]), bool(record["failed"])))
    handoff, plan_id, failed = max(applications)
    assert failed, folder
    search = load_snapshot(folder / f"plan_{plan_id:06d}.npz")
    assert str(search["failure_class"]) == failure_type, (folder, search["failure_class"])
    cell = tuple(search["goal"] if failure_type == "goal_cell" else search["start"])
    layers = ("detected", "obstacle_halo", "prior_raw", "prior_inflated", "steep", "steep_halo", "retained_lethal")
    return dict(
        failure_type=failure_type, plan=plan_id, plan_time_s=float(search["sim_time"]), handoff_s=handoff,
        x=int(cell[0]), y=int(cell[1]), cause=causes(search, cell), blocked=bool(search["lethal"][cell]),
        truth_steep=bool(truth[cell]), truth_steep_halo=bool(halo[cell]), prior_steep_halo=bool(prior[cell]),
        **{name: bool(search[name][cell]) for name in layers if name in search},
    )


def goal_0167(raw, files, revisions):
    target = TARGET_0167
    first_block = None
    searched = 0
    for idx, path in enumerate(files, start=1):
        search = load_snapshot(path)
        if tuple(search["goal"]) == target:
            searched += 1
        if first_block is None and search["lethal"][target]:
            first_block = dict(first_block_plan=idx, first_block_s=float(search["sim_time"]),
                               first_block_cause=causes(search, target))
    with np.load(raw / "pointcloud_map.npz") as final:
        final_blocked = bool(final["lethal"][target])
    revisions_to_goal = sum(
        np.array_equal(np.rint(np.asarray(json.loads(row["path"]))[-1] / RESOLUTION), target) for row in revisions)
    return dict(searches_to_goal=searched, revisions_to_goal=revisions_to_goal, final_blocked=final_blocked,
                **(first_block or {}))


def tilt_evidence(raw, tag, truth, halo):
    stops = next((raw / "follower").glob("*/safety_stops.csv"))
    events = records(raw / "safety_events.csv")
    replans = [r for r in events if r["event"] == "safety_replanned"
               and json.loads(r["detail"])["reason"] == "unsafe_tilt"]
    repeats = [r for r in events if r["event"] == "unsafe_tilt_repeat"]
    previous = None
    for event in records(stops):
        if event["event"] != "unsafe_tilt":
            continue
        t = float(event["sim_time"])
        detail = json.loads(event["detail"])
        x, y, _, roll, pitch, _ = detail["pose"]
        cell = tuple(np.rint(np.array([x, y]) / RESOLUTION).astype(int))
        assert len(replans) == len(repeats) == 1, raw
        yield dict(tag, t_s=t, x_m=x, y_m=y, roll_deg=np.degrees(roll), pitch_deg=np.degrees(pitch),
                   truth_steep=bool(truth[cell]), truth_steep_halo=bool(halo[cell]),
                   revision=detail["revision"], replan_s=replans[0]["sim_time"],
                   repeat_end_s=repeats[0]["sim_time"], seconds_from_previous=t-previous if previous else None)
        previous = t


def main():
    rows = records(ROOT / "common_eval/runs.csv")
    approach = {Path(row["run"]).resolve(): row for row in records(ROOT / "plan_map_inspect/approach.csv")}
    assert len(rows) == len(approach) == 45
    stats, close, failures, goals, tilts = [], [], [], [], []
    for row in rows:
        raw = Path(row["run"]).resolve()
        tag = {key: row[key] for key in ("patch", "condition", "rep")}
        assert row["exit_code"] == "0" and not row["record_error"], row
        verify_manifest(raw, tag)
        folder = raw / "plan_maps"
        files = sorted(folder.glob("plan_*.npz"))
        assert files, raw
        revisions = records(raw / "path_revisions.csv")
        truth, halo, prior = masks(raw)
        stats.append(dict(tag, **terrain(raw, revisions, truth, halo),
                          plan_maps_n=len(files), plan_maps_bytes=sum(p.stat().st_size for p in folder.iterdir()),
                          plan_maps_incomplete=(folder / "incomplete.json").is_file()))
        item = approach[raw]
        d = float(item["distance_m"])
        assert abs(d-float(row["min_truth_clearance_m"])) < 1e-8, raw
        if d < .5:
            with np.load(folder / f'applied_{int(item["plan"]):06d}.npz') as handoff:
                xy = np.array([[float(item["x"]), float(item["y"])]])
                offset, _, _ = nearest_path(xy, prepare_path(handoff["path_m"]))
            close.append(dict(tag, **{key: value for key, value in item.items() if key != "run"},
                              deviation_m=offset[0], outcome=row["outcome"]))
        if row["outcome"] == "no_path":
            failures.append(dict(tag, **terminal_map(folder, row["no_path_type"], prior, truth, halo)))
        if tag["patch"] == "08OB88_-0167":
            goals.append(dict(tag, outcome=row["outcome"], reached=row["goals_reached"],
                              **goal_0167(raw, files, revisions)))
        if int(row["ev_unsafe_tilt"]):
            tilts.extend(tilt_evidence(raw, tag, truth, halo))
    for name, data in (("terrain_and_storage.csv", stats), ("box_approach_evidence.csv", close),
                       ("no_path_evidence.csv", failures), ("0167_goals.csv", goals), ("tilt_evidence.csv", tilts)):
        write(name, data)


if __name__ == "__main__":
    main()
