"""Cross-check the 064 stage 1 records and measure slopes, routes and box episodes."""
from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np

from experiments.eval_runs import read_csv, read_trajectory
from experiments.plan_map_inspect import active_handoff, box_evidence, causes
from results.eval_057.audit057 import masks
from results.tracking_error.replay import (
    approach_segments, box_distances, classification, event_geometry, revision_data,
)
from tapp.endpoint_policy import audit_path, load_snapshot

ROOT = Path(__file__).resolve().parent
PATCHES = ("08OB86_-0205", "08OB88_-1417", "08OB88_-0167", "08OB88_00332", "08OB89_-0847")
CONDITIONS = ("S", "P", "D", "PD", "G", "GD")
GOAL = (137, 294)


def records(path):
    return read_csv(path)[1]


def read_json(path):
    return json.loads(path.read_text())


def length(xy):
    return float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())


def write(name, rows):
    if not rows:
        print(f"{name}: no rows", flush=True)
        return
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (ROOT / name).open("x", newline="") as stream:
        table = csv.DictWriter(stream, columns, lineterminator="\n")
        table.writeheader()
        table.writerows(rows)
    print(f"{name}: {len(rows)} rows", flush=True)


def manifest_evidence(raw, patch, condition):
    m = read_json(raw.parents[1] / "manifest.json")
    case, = [item for item in m["cases"] if item["selected"]]
    expected = dict(only_patch=patch, execution="finished", patch_count=3, protocol="rtf_check",
                    real_time_factor=1.0, stale_timeout_s=1.0, map_method="fine",
                    ground_estimate="non_obstacle", online_fixes="v2", sensors="lidar_real+depth2",
                    diagnostics=True, save_plan_maps=True, pose_trace=True, endpoint_policy="none")
    assert case["patch"] == patch and all(m[k] == value for k, value in expected.items()), (patch, condition, m)
    assert m["rendering"]["mode"] == "gpu" and m["rendering"]["backend"] == "EGL"
    assert m.get("terrain_source", "sensor") == ("prior" if condition in ("P", "PD") else "sensor")
    assert m.get("ground_near_obstacle", "keep") == ("exclude" if condition in ("G", "GD") else "keep")
    assert m.get("obstacle_clearance", "centre") == ("distance" if condition.endswith("D") else "centre")
    if condition.endswith("D"):
        assert m["distance_clearance"]["R_soft"] == 1.5
    return case


def applications(folder):
    data = []
    for path in folder.glob("applied_*.npz"):
        with np.load(path, allow_pickle=False) as record:
            data.append({name: record[name] for name in record.files})
    return sorted(data, key=lambda r: (float(r["sim_time"]), int(r["plan_id"])))


def approaches(raw, trace, times, paths, saved, cutoff):
    rows = records(raw / "debris_footprints.csv")
    boxes = np.array([[float(r[k]) for k in ("xmin", "ymin", "xmax", "ymax")] for r in rows])
    lo, hi = boxes[:, :2], boxes[:, 2:]
    xy = trace[:, 1:]
    distances = box_distances(xy, (lo, hi))
    for enter, leave, (distance, stamp, j, point) in approach_segments(trace[:, 0], xy, (lo, hi), distances):
        fields = event_geometry(stamp, point, times, paths, lo[j:j+1], hi[j:j+1])
        evidence = dict(enter_s=enter, leave_s=leave, duration_s=leave-enter, nearest_t_s=stamp,
                        x_m=float(point[0]), y_m=float(point[1]), box_index=j, min_box_m=distance,
                        classification=classification(fields.get("projected_point_to_box_m")), **fields)
        handoff, basis = active_handoff(raw, saved, stamp) if stamp < cutoff else (None, None)
        if handoff is None:
            reason = "after recording cutoff" if stamp >= cutoff else "no matching handoff"
            yield dict(evidence, map_issue=reason)
            continue
        plan_id = int(handoff["plan_id"])
        target = raw / "plan_maps" / f"plan_{plan_id:06d}.npz"
        if not target.is_file():
            yield dict(evidence, map_issue="search map missing")
            continue
        plan = load_snapshot(target)
        yield dict(evidence, plan=plan_id, plan_time_s=float(plan["sim_time"]), path_time_basis=basis,
                   **box_evidence(plan, handoff["path_m"], boxes[j]))


def terminal(raw, saved, row, truth, halo, prior):
    data = dict(no_path_type=row["no_path_type"], last_online_error=row["online_error"])
    if not saved or not saved[-1]["failed"]:
        return dict(data, map_issue="no terminal search handoff")
    plan_id = int(saved[-1]["plan_id"])
    search = load_snapshot(raw / "plan_maps" / f"plan_{plan_id:06d}.npz")
    kind = str(search["failure_class"])
    data.update(plan=plan_id, stamp_s=float(search["sim_time"]), failure_class=kind,
                plan_reason=str(search["reason"]), goal=str(tuple(map(int, search["goal"]))),
                start=str(tuple(map(int, search["start"]))))
    if kind not in ("goal_cell", "start_cell", "start_steep"):
        return data
    cell = tuple(search["goal"] if kind == "goal_cell" else search["start"])
    layers = ("detected", "obstacle_halo", "prior_raw", "prior_inflated", "steep", "steep_halo", "retained_lethal")
    return dict(data, cause=causes(search, cell), blocked=bool(search["lethal"][cell]),
                true_steep=bool(truth[cell]), true_halo=bool(halo[cell]), prior_steep_halo=bool(prior[cell]),
                **{key: bool(search[key][cell]) for key in layers if key in search})


def inspect_goal(raw, files, paths, result, truth, halo):
    block = {}
    attempts = 0
    for i, snapshot in enumerate(files, 1):
        with np.load(snapshot, allow_pickle=False) as saved:
            attempts += tuple(saved["goal"]) == GOAL
            if not block:
                index = np.ravel_multi_index(GOAL, tuple(saved["lethal_shape"]))
                blocked = (int(saved["lethal_bits"][index//8]) >> (7-index%8)) & 1
                if blocked:
                    plan = load_snapshot(snapshot)
                    block = dict(first_block_plan=i, first_block_s=float(plan["sim_time"]),
                                 first_block_cause=causes(plan, GOAL))
    with np.load(raw / "pointcloud_map.npz", allow_pickle=False) as final:
        final_blocked = bool(final["lethal"][GOAL])
    ends = sum(np.array_equal(np.rint(path[-1] / .5), GOAL) for path in paths if len(path))
    return dict(result, true_steep=bool(truth[GOAL]), true_halo=bool(halo[GOAL]),
                searches_to_goal=attempts, accepted_path_revisions_to_goal=ends, final_blocked=final_blocked, **block)


def main():
    rows = records(ROOT / "common_eval/runs.csv")
    assert Counter((r["patch"], r["condition"], r["rep"]) for r in rows) == Counter(
        (patch, condition, str(rep)) for patch in PATCHES for condition in CONDITIONS for rep in (1, 2, 3))
    metrics, episodes, failures, goals, tilts = [], [], [], [], []
    for row in rows:
        raw = Path(row["run"]).resolve()
        tag = {k: row[k] for k in ("patch", "condition", "rep")}
        assert row["exit_code"] == "0", row["run"]
        case = manifest_evidence(raw, tag["patch"], tag["condition"])
        trace, _, _ = read_trajectory(raw)
        times, paths = revision_data(records(raw / "path_revisions.csv"))
        truth, halo, prior = masks(raw)
        travel = audit_path(trace[:, 1:], halo, truth)
        plan_audits = [audit_path(path, halo, truth) for path in paths]
        folder = raw / "plan_maps"
        files = sorted(folder.glob("plan_*.npz"))
        marker = folder / "incomplete.json"
        cutoff = float(read_json(marker)["from_sim_time"]) if marker.is_file() else float("inf")
        render = case.get("rendering", {})
        metrics.append(dict(tag,
            executed_xy_m=length(trace[:, 1:]), plan_versions=len(paths),
            plan_version_total_m=sum(length(p) for p in paths),
            plan_true_steep_m=sum(a["truth_lethal_length_m"] for a in plan_audits),
            plan_true_halo_m=sum(a["relaxed_length_m"] for a in plan_audits),
            travel_true_steep_m=travel["truth_lethal_length_m"], travel_true_halo_m=travel["relaxed_length_m"],
            plan_maps_n=len(files), plan_maps_bytes=sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
            plan_maps_incomplete=marker.is_file(),
            pose_trace_bytes=sum(p.stat().st_size for p in (raw/"pose_trace").glob("*.csv")),
            gpu_rendered=render.get("gpu_rendered"), gl_renderer=render.get("gl_renderer"),
            wall_elapsed_s=read_json(raw/"mission.json").get("wall_elapsed_s")))
        n = int(row["truth_below_radius_entries"])
        saved = applications(folder) if n or row["outcome"] == "no_path" else []
        if n:
            evidence = list(approaches(raw, trace, times, paths, saved, cutoff))
            assert len(evidence) == n, (raw, len(evidence), n)
            assert abs(sum(e["duration_s"] for e in evidence)-float(row["truth_below_radius_s"])) < 1e-6, raw
            assert abs(min(e["min_box_m"] for e in evidence)-float(row["min_truth_clearance_m"])) < 1e-8, raw
            episodes.extend(dict(tag, interval=i, **item) for i, item in enumerate(evidence, 1))
        if row["outcome"] == "no_path":
            failures.append(dict(tag, **terminal(raw, saved, row, truth, halo, prior)))
        if tag["patch"] == "08OB88_-0167":
            goals.append(dict(tag, **inspect_goal(raw, files, paths, dict(outcome=row["outcome"],
                                reached=row["goals_reached"], maps_incomplete=marker.is_file()), truth, halo)))
        for e in json.loads(row["stops_detail"] or "[]"):
            if e["kind"] == "unsafe_tilt":
                tilts.append(dict(tag, outcome=row["outcome"], **e))
    for name, data in (("run_evidence.csv", metrics), ("approach_intervals.csv", episodes),
                       ("no_path_evidence.csv", failures), ("0167_goals.csv", goals), ("tilt_evidence.csv", tilts)):
        write(name, data)


if __name__ == "__main__":
    main()
