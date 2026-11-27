"""Audit 073 runs, recover true arrival positions, and apply the prespecified tests."""

from collections import Counter
from dataclasses import asdict
import csv
import json
from math import comb
from pathlib import Path
import shlex

import numpy as np
from scipy.stats import fisher_exact

from experiments.eval_runs import read_trajectory
from results.eval_064.audit064 import length, masks, read_json, records
from tapp.config import RESOLUTION
from tapp.endpoint_policy import audit_path
from tapp.pose_error import PoseErrorSettings

ROOT = Path(__file__).resolve().parent
PATCHES = ("08OB86_-0205", "08OB88_-1417", "08OB88_00332", "08OB89_-0847")
MODES = {
    "bias025": ("bias", (.25, 0., 0.), None, "--pose-error-bias=.25,0,0"),
    "none": ("none", None, None, None),
    "bias050": ("bias", (.5, 0., 0.), None, "--pose-error-bias=.5,0,0"),
    "bias100": ("bias", (1., 0., 0.), None, "--pose-error-bias=1,0,0"),
    "yaw2": ("bias", (0., 0., 2.), None, "--pose-error-bias=0,0,2"),
    "drift05": ("drift", None, .5, ".5"),
    "drift1": ("drift", None, 1., "1"),
    "drift2": ("drift", None, 2., "2"),
}
CONDITIONS = ("none", *[name for name in MODES if name != "none"])
PIN = "e0066a5ec29bbd10ed98fe7441d146289b64a1d7"
COMMON = tuple(("--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 "
                "--sensors lidar_real+depth2 --diagnostics --terrain-source prior "
                "--obstacle-clearance distance --save-plan-maps --pose-trace --real-time-factor 1.0").split())
MANIFEST = dict(execution="finished", protocol="rtf_check", patch_count=3, real_time_factor=1.,
                stale_timeout_s=1., map_method="fine", ground_estimate="non_obstacle",
                online_fixes="v2", sensors="lidar_real+depth2", diagnostics=True, save_plan_maps=True,
                pose_trace=True, endpoint_policy="none", obstacle_clearance="distance", terrain_source="prior")


def write(name, rows):
    rows = list(rows)
    print(f"{name}: {len(rows)} rows", flush=True)
    if rows:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        with (ROOT / name).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def key(row):
    return row["patch"], row["condition"], row["rep"]


def run_manifest(raw, condition, rep):
    manifest = read_json(raw.parents[1] / "manifest.json")
    case, = [case for case in manifest["cases"] if case["selected"]]
    patch = raw.name
    assert manifest["only_patch"] == case["patch"] == patch
    assert all(manifest[name] == value for name, value in MANIFEST.items()), raw
    assert manifest["rendering"]["mode"] == "gpu" and manifest["rendering"]["backend"] == "EGL", raw
    assert case["rendering"]["gpu_rendered"] is True, raw
    mode, bias, drift, _ = MODES[condition]
    expected = PoseErrorSettings(mode, seed=0, rep=int(rep), bias=bias, drift_pct=drift)
    if mode == "none":
        assert "pose_error" not in manifest and "pose_error" not in case, raw
    else:
        assert manifest["pose_error"] == mode and manifest["pose_error_settings"] == json.loads(
            json.dumps(asdict(expected))), raw
        assert case["pose_error"]["run_seed"] == expected.run_seed(patch), raw
    return manifest, case


def inventory(rows):
    expected = [(p, c, str(r)) for p in PATCHES for r in range(1, 6) for c in MODES]
    trials = [(p.parent.name, *p.name.rsplit("_r", 1)) for p in (ROOT / "runs").glob("*/*") if p.is_dir()]
    assert Counter(expected) == Counter(trials) == Counter(map(key, rows))
    logs = [line.split() for line in (ROOT / "run073_log.txt").read_text().splitlines()]
    commands = {}
    for marker in ("START", "END"):
        events = [line for line in logs if len(line) >= 5 and line[1] == marker]
        assert [tuple(line[2:5]) for line in events] == expected, marker
        commands[marker] = {tuple(line[2:5]): line for line in events}
    records_out, images = [], set()
    for patch, condition, rep in expected:
        path = ROOT / "runs" / patch / f"{condition}_r{rep}"
        tags1, tags2, arg_line = (path / "run_conditions.txt").read_text().splitlines()
        tags = dict(word.split("=", 1) for word in f"{tags1} {tags2}".split())
        values = dict(commit=PIN, branch="claude/073-eval", tracked_changes="0", patch=patch,
                      condition=condition, rep=rep, rtf="1.0", domain="73", rendering="gpu",
                      stale_sim_s="1.0", seed="0", protocol="rtf_check")
        assert all(tags[name] == value for name, value in values.items()), path
        mode, _, _, arg = MODES[condition]
        args = COMMON + ("--pose-error-seed", "0", "--pose-error-rep", rep, "--pose-error", mode)
        if mode == "bias":
            args += (arg,)
        elif mode == "drift":
            args += ("--pose-error-drift-pct", arg)
        assert tuple(shlex.split(arg_line.removeprefix("args="))) == args, path
        code = int((path / "exit.txt").read_text())
        start = commands["START"][(patch, condition, rep)]
        end = commands["END"][(patch, condition, rep)]
        assert code == 0 and end[5] == "exit=0", path
        assert abs((np.datetime64(start[0][:19]) - np.datetime64(tags["started"][:19]))
                   / np.timedelta64(1, "s")) <= 1
        images.add(tags["image"])
        records_out.append(dict(patch=patch, condition=condition, rep=rep, exit_code=code,
                                started=start[0], ended=end[0], bytes=int(end[6].split("=")[1]),
                                commit=PIN, image=tags["image"], conditions_ok=True))
    assert len(images) == 1
    write("run_inventory.csv", records_out)


def pose_pairs(raw, condition, mission, seed):
    folder = raw / "pose_trace"
    parts = [p for name in ("pose_error_previous.csv", "pose_error.csv")
             if (p := folder / name).is_file()]
    if condition == "none":
        assert not parts, raw
        return None, dict(pair_rows=0, pair_files=0, paired_start_delay_s=None, paired_end_gap_s=None,
                          last_xy_error_m=0., max_xy_error_m=0., last_abs_yaw_error_deg=0.,
                          max_abs_yaw_error_deg=0., relay_travel_m=None, drift_steps=None)
    fields = ("stamp_ns", "travel_m", "drift_steps", "truth_x", "truth_y", "truth_yaw",
              "estimated_x", "estimated_y", "estimated_yaw")
    pair = np.asarray([[float(row[field]) for field in fields]
                       for part in parts for row in records(part)])
    assert pair.ndim == 2 and np.isfinite(pair).all() and (np.diff(pair[:, 0]) >= 0).all(), raw
    pair[:, 0] /= 1e9
    begin, end = mission["started_t"], mission["finished_t"]
    sub = pair[(begin <= pair[:, 0]) & (pair[:, 0] <= end)]
    assert len(sub), raw
    delta = sub[:, 6:8] - sub[:, 3:5]
    yaw = sub[:, 8] - sub[:, 5]
    yaw = np.degrees(np.arctan2(np.sin(yaw), np.cos(yaw)))
    mode, bias, drift, _ = MODES[condition]
    if mode == "bias":
        np.testing.assert_allclose(delta, np.broadcast_to((bias[0], 0.), delta.shape), rtol=0, atol=1e-8)
        np.testing.assert_allclose(yaw, bias[2], rtol=0, atol=1e-8)
    elif mode == "drift":
        steps = np.floor(sub[:, 1]).astype(int)
        np.testing.assert_array_equal(steps, sub[:, 2])
        samples = np.random.Generator(np.random.PCG64(seed)).normal(0., drift/100., (int(steps[-1]), 2))
        walk = np.vstack((np.zeros(2), samples.cumsum(axis=0)))
        expected = walk[steps] * np.array((1., -1.))
        np.testing.assert_allclose(delta, expected, rtol=0, atol=1e-8)
        np.testing.assert_allclose(yaw, 0., rtol=0, atol=1e-8)
    distance = np.linalg.norm(delta, axis=1)
    return pair, dict(pair_rows=len(sub), pair_files=len(parts),
                      paired_start_delay_s=sub[0, 0]-begin, paired_end_gap_s=end-sub[-1, 0],
                      last_xy_error_m=distance[-1], max_xy_error_m=distance.max(),
                      last_abs_yaw_error_deg=abs(yaw[-1]), max_abs_yaw_error_deg=max(abs(yaw)),
                      relay_travel_m=sub[-1, 1], drift_steps=int(sub[-1, 2]))


def arrival(tag, target, index, stamp, pos, source, pair):
    target_m = np.asarray(target)*RESOLUTION
    pos = np.asarray(pos)[:2]
    estimated_distance = float(np.linalg.norm(pos-target_m))
    data = dict(tag, target_num=index+1, kind="return" if index == 5 else "stop",
                target_x_m=target_m[0], target_y_m=target_m[1], decision_sim_s=stamp,
                estimated_x_m=pos[0], estimated_y_m=pos[1], estimated_distance_m=estimated_distance,
                source=source)
    if estimated_distance > .3 + 1e-8:
        return dict(data, issue="saved estimated pose is outside the arrival radius")
    if pair is None:
        truth = pos
        data["truth_basis"] = "no injected error, saved decision pose"
    else:
        matching = np.flatnonzero((np.abs(pair[:, 6:8] - pos) < 1e-8).all(axis=1))
        if not len(matching):
            return dict(data, issue="no matching estimated pose in the relay record")
        i = matching[np.argmin(np.abs(pair[matching, 0] - stamp))]
        gap = stamp - pair[i, 0]
        if not -.06 <= gap <= 1.:
            return dict(data, issue="matched pose timestamp is outside the receipt window", pose_to_decision_s=gap)
        truth = pair[i, 3:5]
        data.update(truth_basis="same stamped relay pose", pose_stamp_s=pair[i, 0], pose_to_decision_s=gap)
    return dict(data, truth_x_m=truth[0], truth_y_m=truth[1],
                true_distance_m=float(np.linalg.norm(truth-target_m)))


def leg_evidence(tag, mission, path, files, pair):
    targets = list(map(tuple, mission["stops_cells"]))
    assert len(targets) == len(set(targets)) == 6
    starts, arrivals, latest_failure = {}, [], {}
    for plan in files:
        with np.load(plan, allow_pickle=False) as item:
            stamp, kind = float(item["sim_time"]), str(item["reason"])
            if kind == "start_leg":
                index = targets.index(tuple(item["goal"]))
                starts.setdefault(index, (stamp, item["pose"], plan.name))
            if not bool(item["success"]):
                latest_failure = dict(last_failed_plan=plan.name, last_failed_sim_s=stamp,
                                      last_failed_type=str(item["failure_class"]),
                                      last_failed_goal=str(tuple(map(int, item["goal"]))),
                                      last_failed_start=str(tuple(map(int, item["start"]))))
    latest = max([0, *starts, *(int(row["leg_index"]) for row in records(path / "replans.csv"))])
    state = mission.get("final_state") or {}
    completed = mission["status"] == "completed"
    n_stops = 5 if completed else latest
    for index in range(n_stops):
        if (next_leg := starts.get(index+1)) is None:
            arrivals.append(dict(tag, target_num=index+1, kind="stop",
                                 issue="next-leg search snapshot unavailable"))
        else:
            stamp, pose, filename = next_leg
            arrivals.append(arrival(tag, targets[index], index, stamp, pose, filename, pair))
    if completed:
        arrivals.append(arrival(tag, targets[-1], 5, state["sim_time"], state["pose"],
                                "final follower state", pair))
    return arrivals, latest_failure


def statistics(rows):
    metrics = ("box_close", "true_steep_halo", "completed")
    for metric in metrics:
        def positive(r):
            if metric == "box_close":
                return r["min_truth_clearance_m"] < .5
            if metric == "true_steep_halo":
                return r["travel_true_halo_m"] > 0
            return r["outcome"] == "completed"

        n = {condition: sum(positive(r) for r in rows if r["condition"] == condition)
             for condition in CONDITIONS}
        baseline = n["none"]
        results = []
        for condition in CONDITIONS[1:]:
            count = n[condition]
            p = fisher_exact([[count, 20-count], [baseline, 20-baseline]], alternative="two-sided").pvalue
            total = count + baseline
            ways = [comb(20, k)*comb(20, total-k) for k in range(max(0, total-20), min(20, total)+1)]
            observed = comb(20, count)*comb(20, baseline)
            independent = sum(w for w in ways if w <= observed)/comb(40, total)
            np.testing.assert_allclose(p, independent, atol=2e-14, rtol=0)
            results.append(dict(metric=metric, condition=condition, reference="none", count=count,
                                total=20, reference_count=baseline, reference_total=20, p_raw=p))
        adjusted = 0.
        for i, row in enumerate(sorted(results, key=lambda r: r["p_raw"])):
            adjusted = min(1., max(adjusted, (len(results)-i)*row["p_raw"]))
            row["p_holm"] = adjusted
        yield from results


def main():
    rows = records(ROOT / "common_eval/runs.csv")
    inventory(rows)
    closest = {str(Path(r["run"]).resolve()): r for r in records(ROOT / "plan_map_inspect/approach.csv")}
    goals = {str(Path(r["run"]).resolve()): r for r in records(ROOT / "plan_map_inspect/goal_cell.csv")}
    pose_diags = {str(Path(r["run"]).resolve()): r for r in records(ROOT / "pose_trace_inspect.csv")}
    output, arrivals, abnormal, close = [], [], [], []
    for row in rows:
        raw = Path(row["run"]).resolve()
        tag = {f: row[f] for f in ("patch", "condition", "rep")}
        condition, rep = tag["condition"], tag["rep"]
        _, case = run_manifest(raw, condition, rep)
        mission = read_json(raw / "mission.json")
        pair, pose = pose_pairs(raw, condition, mission, case.get("pose_error", {}).get("run_seed"))
        trace, _, _ = read_trajectory(raw)
        truth, halo, _ = masks(raw)
        geometry = audit_path(trace[:, 1:], halo, truth)
        folder = raw / "plan_maps"
        files = sorted(folder.glob("plan_*.npz"))
        reached, last_search = leg_evidence(tag, mission, raw, files, pair)
        arrivals.extend(reached)
        min_clearance = float(row["min_truth_clearance_m"])
        assert bool(int(row["truth_below_radius_entries"])) == (min_clearance < .5)
        follower = [read_json(p) for p in (raw / "follower").glob("*/mission.json")]
        causes = sorted({r["online_error"] for r in follower if r.get("online_error")})
        outcome = row["outcome"]
        stop_type = ("stale_cloud" if "lidar_unavailable_or_stale" in causes else outcome)
        metric = dict(tag, outcome=outcome, termination_type=stop_type, controller_status=mission["status"],
                      true_goals_reached=int(row["goals_reached"]),
                      controller_stops=sum(a["kind"] == "stop" for a in reached),
                      true_returned=row["returned_to_start"],
                      min_truth_clearance_m=min_clearance,
                      close_intervals=int(row["truth_below_radius_entries"]),
                      close_s=float(row["truth_below_radius_s"]),
                      travel_true_steep_m=geometry["truth_lethal_length_m"],
                      travel_true_halo_m=geometry["relaxed_length_m"],
                      debris_len_m=float(row["debris_len_m"]), unsafe_tilt=int(row["ev_unsafe_tilt"]),
                      rollover=row["rolled_over"] == "True", travel_m=length(trace[:, 1:]),
                      elapsed_s=float(row["elapsed_s"]), wall_s=mission["wall_elapsed_s"],
                      rtf=float(row["sim_to_wall_ratio"]),
                      plan_maps_bytes=sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
                      plan_maps_incomplete=(folder / "incomplete.json").is_file(),
                      pose_trace_bytes=sum(p.stat().st_size for p in (raw / "pose_trace").glob("*.csv")),
                      arrival_unmatched=sum("issue" in a for a in reached),
                      **pose)
        output.append(metric)
        if min_clearance < .5:
            details = closest.get(str(raw), {})
            if details:
                np.testing.assert_allclose(min_clearance, float(details["distance_m"]), atol=1e-8, rtol=0.)
            close.append(dict(tag, min_truth_clearance_m=min_clearance, intervals=metric["close_intervals"],
                              duration_s=metric["close_s"], **{k: v for k, v in details.items() if k != "run"}))
        if outcome != "completed":
            perc = mission.get("perception") or {}
            stamps = {name: data["last_stamp"] for name, data in (perc.get("sensors") or {}).items()
                      if data.get("last_stamp") is not None}
            oldest = min(stamps, key=stamps.get) if stamps and stop_type == "stale_cloud" else None
            abnormal.append(dict(tag, outcome=outcome, termination_type=stop_type,
                                 controller_status=mission["status"], follower_error=",".join(causes),
                                 no_path_type=row["no_path_type"], true_goals=metric["true_goals_reached"],
                                 controller_stops=metric["controller_stops"],
                                 finished_sim_s=mission["finished_t"], tilt_events=metric["unsafe_tilt"],
                                 oldest_sensor=oldest, oldest_age_s=mission["finished_t"]-stamps[oldest] if oldest else None,
                                 blocked_goal_cause=goals.get(str(raw), {}).get("failure_cause"),
                                 pose_diagnosis=pose_diags.get(str(raw), {}).get("diagnosis"),
                                 **last_search))
    write("run_metrics.csv", output)
    write("arrivals.csv", arrivals)
    write("abnormal_runs.csv", abnormal)
    write("box_approaches.csv", close)
    write("fisher_holm.csv", statistics(output))


if __name__ == "__main__":
    main()
