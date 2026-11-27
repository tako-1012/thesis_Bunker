"""Audit 067 runs and measure the fifth leg in 0167 using the 064 definitions."""
from collections import Counter
import csv
import json
from pathlib import Path
import shlex

import numpy as np
from scipy.stats import fisher_exact

from experiments.eval_runs import read_trajectory
from results.eval_064.audit064 import (
    PATCHES, applications, approaches, inspect_goal, length, masks, read_json, records, revision_data, terminal,
)
from tapp.config import RESOLUTION
from tapp.endpoint_policy import audit_path

ROOT = Path(__file__).resolve().parent
CONDITIONS = {
    "PD": ("--terrain-source", "prior"),
    "PDS": ("--terrain-source", "prior", "--steep-clearance", "distance"),
    "GD": ("--ground-near-obstacle", "exclude"),
    "GDS": ("--ground-near-obstacle", "exclude", "--steep-clearance", "distance"),
}
COMMON = tuple(("--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 "
                "--sensors lidar_real+depth2 --diagnostics --real-time-factor 1.0 --save-plan-maps "
                "--pose-trace --obstacle-clearance distance").split())
PAIRS = (("PDS", "PD"), ("GDS", "GD"))
PIN = "98ddbde64ff49e21fbacc111c0523ed63ee03e8b"


def write(name, rows):
    if not rows:
        print(f"{name}: no rows", flush=True)
        return
    cols = list(dict.fromkeys(key for row in rows for key in row))
    with (ROOT / name).open("x", newline="") as f:
        writer = csv.DictWriter(f, cols, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows)} rows", flush=True)


def key(row):
    return row["patch"], row["condition"], row["rep"]


def check_inventory(rows):
    expected = [(p, c, str(r)) for p in PATCHES for r in range(1, 7) for c in CONDITIONS]
    actual = {(p.parent.name, *p.name.rsplit("_r", 1)) for p in (ROOT/"runs").glob("*/*") if p.is_dir()}
    assert set(expected) == actual, (set(expected)-actual, actual-set(expected))
    assert Counter(map(key, rows)) == Counter(expected)
    log = [line.split() for line in (ROOT/"run067_log.txt").read_text().splitlines()]
    for marker in ("START", "END"):
        got = [tuple(line[2:5]) for line in log if len(line)>4 and line[1]==marker]
        assert got == expected, marker
    info, images = [], set()
    for p, c, r in expected:
        path = ROOT/"runs"/p/f"{c}_r{r}"
        metadata = (path/"run_conditions.txt").read_text().splitlines()
        args = tuple(shlex.split(metadata[2].removeprefix("args=")))
        tags = dict(item.split("=",1) for line in metadata[:2] for item in line.split())
        exp = dict(commit=PIN, branch="claude/067-eval", tracked_changes="0", patch=p, condition=c,
                   rep=r, rtf="1.0", domain="69", rendering="gpu", stale_sim_s="1.0", seed="0", prior_variant="exact")
        assert all(tags.get(k) == v for k,v in exp.items()) and args == COMMON+CONDITIONS[c], path
        code = int((path/"exit.txt").read_text())
        images.add(tags["image"])
        info.append(dict(patch=p, condition=c, rep=r, exit_code=code,
                         conditions_ok=True, started=tags["started"], commit=tags["commit"], image=tags["image"]))
    assert len(images) == 1
    assert all(row["exit_code"] == 0 for row in info)
    write("run_inventory.csv", info)


def case_manifest(raw, tag):
    m = read_json(raw.parents[1]/"manifest.json")
    (case,) = [r for r in m["cases"] if r["selected"]]
    c = tag["condition"]
    expected = dict(only_patch=tag["patch"], execution="finished", protocol="rtf_check", patch_count=3,
                    real_time_factor=1.0, stale_timeout_s=1.0, map_method="fine", ground_estimate="non_obstacle",
                    online_fixes="v2", sensors="lidar_real+depth2", diagnostics=True, save_plan_maps=True,
                    pose_trace=True, endpoint_policy="none", obstacle_clearance="distance")
    assert case["patch"] == tag["patch"] and all(m[k]==v for k,v in expected.items()), (raw, expected)
    assert m["rendering"]["mode"] == "gpu" and m["rendering"]["backend"] == "EGL"
    assert m.get("terrain_source", "sensor") == ("prior" if c.startswith("P") else "sensor")
    assert m.get("ground_near_obstacle", "keep") == ("exclude" if c.startswith("G") else "keep")
    assert m.get("steep_clearance", "centre") == ("distance" if c.endswith("S") else "centre")
    assert m["distance_clearance"]["R_soft"] == 1.5 and m["distance_clearance"]["R_hard"] == .5, raw
    if c.endswith("S"):
        assert m["steep_distance_clearance"] == dict(R_hard=.5, R_soft=1.5, w=1.), raw
    return case


def fifth_leg(raw, files, paths, trace, mission, truth, halo, events):
    target = (137, 294)
    assert tuple(mission["stops_cells"][4]) == target, raw
    first, next_leg = None, None
    for path in files:
        with np.load(path, allow_pickle=False) as f:
            goal = tuple(f["goal"])
            if first is None and goal == target:
                first = float(f["sim_time"])
            elif first is not None and goal == tuple(mission["stops_cells"][5]):
                next_leg = float(f["sim_time"])
                break
    planned = [path for path in paths if len(path) and np.array_equal(np.rint(path[-1]/RESOLUTION),target)]
    if first is None:
        return dict(leg5_measured=False)
    end = next_leg if next_leg is not None else mission["finished_t"]
    t,xy = trace[:,0],trace[:,1:]
    lo,hi = max(first,t[0]),min(end,t[-1])
    assert hi >= lo, raw
    stamp = np.r_[lo, t[(lo<t)&(t<hi)], hi]
    segment = np.column_stack([np.interp(stamp,t,xy[:,i]) for i in range(2)])
    marks = audit_path(segment, halo, truth)
    return dict(leg5_measured=True, leg5_start_s=first, leg5_end_s=end, leg5_sim_s=end-first,
                leg5_trajectory_coverage_s=hi-lo, leg5_executed_xy_m=length(segment),
                leg5_beginning_path_m=length(planned[0]) if planned else None,
                leg5_planned_versions_total_m=sum(length(path) for path in planned),
                leg5_true_steep_m=marks["truth_lethal_length_m"], leg5_true_halo_m=marks["relaxed_length_m"],
                leg5_tilt_events=sum(e["kind"]=="unsafe_tilt" and first<=e["t"]<=end for e in events))


def tests(rows):
    metrics = dict(tilt=lambda r:int(r["ev_unsafe_tilt"])>0,
                   true_halo=lambda r:float(r["travel_true_halo_m"])>0,
                   completed=lambda r:r["outcome"]=="completed")
    for name, indicator in metrics.items():
        counts = {c:sum(indicator(r) for r in rows if r["condition"]==c) for c in CONDITIONS}
        comparisons = []
        for a,b in PAIRS:
            k,j = counts[a],counts[b]
            p = fisher_exact([[k,30-k],[j,30-j]],alternative="two-sided").pvalue
            comparisons.append(dict(metric=name, condition_a=a, condition_b=b,
                                    count_a=k, total_a=30, count_b=j, total_b=30, p_raw=p))
        prior = 0
        for i,row in enumerate(sorted(comparisons,key=lambda r:r["p_raw"])):
            prior = min(1,max(prior,(2-i)*row["p_raw"]))
            row["p_holm"] = prior
        yield from comparisons


def main():
    rows = records(ROOT/"common_eval_all/runs.csv")
    check_inventory(rows)
    safety, failures, goals, intervals, abnormal = [], [], [], [], []
    for row in rows:
        raw = Path(row["run"]).resolve()
        tag = {k:row[k] for k in ("patch","condition","rep")}
        case = case_manifest(raw,tag)
        mission = read_json(raw/"mission.json")
        trace,_,_ = read_trajectory(raw)
        times,paths = revision_data(records(raw/"path_revisions.csv"))
        truth,halo,prior = masks(raw)
        travel = audit_path(trace[:,1:],halo,truth)
        audits = [audit_path(p,halo,truth) for p in paths]
        folder=raw/"plan_maps"
        files=sorted(folder.glob("plan_*.npz"))
        marker=folder/"incomplete.json"
        cutoff=float(read_json(marker)["from_sim_time"]) if marker.is_file() else float("inf")
        events=json.loads(row["stops_detail"] or "[]")
        metrics=dict(tag,travel_true_steep_m=travel["truth_lethal_length_m"],travel_true_halo_m=travel["relaxed_length_m"],
                     plan_true_steep_m=sum(d["truth_lethal_length_m"] for d in audits),
                     plan_true_halo_m=sum(d["relaxed_length_m"] for d in audits),
                     executed_xy_m=length(trace[:,1:]),plan_version_total_m=sum(length(p) for p in paths),
                     wall_elapsed_s=mission.get("wall_elapsed_s"),gpu_rendered=case.get("rendering",{}).get("gpu_rendered"),
                     plan_maps_n=len(files),plan_maps_bytes=sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
                     plan_maps_incomplete=marker.is_file(),pose_trace_bytes=sum(p.stat().st_size for p in (raw/"pose_trace").glob("*.csv")))
        safety.append(metrics)
        row.update(metrics)
        n=int(row["truth_below_radius_entries"])
        saved=applications(folder) if n or row["outcome"]=="no_path" else []
        if n:
            measured=list(approaches(raw,trace,times,paths,saved,cutoff))
            assert len(measured)==n and abs(sum(v["duration_s"] for v in measured)-float(row["truth_below_radius_s"]))<1e-6, raw
            intervals.extend(dict(tag,interval=i,**v) for i,v in enumerate(measured,1))
        causes=sorted({err for p in (raw/"follower").glob("*/mission.json") if (err:=read_json(p).get("online_error"))})
        if row["outcome"]=="no_path":
            failures.append(dict(tag,follower_error=",".join(causes),**terminal(raw,saved,row,truth,halo,prior)))
        if row["outcome"]!="completed":
            p=mission.get("perception") or {}
            states=p.get("sensors") or {}
            stamps={name:d["last_stamp"] for name,d in states.items() if d.get("last_stamp") is not None}
            oldest=min(stamps,key=stamps.get) if stamps else ""
            age=mission["finished_t"]-stamps[oldest] if oldest else None
            abnormal.append(dict(tag,outcome=row["outcome"],no_path_type=row["no_path_type"],
                                 follower_error=",".join(causes),goals_reached=row["goals_reached"],
                                 finished_sim_s=mission["finished_t"],unsafe_tilt=row["ev_unsafe_tilt"],
                                 oldest_sensor_at_end=oldest,oldest_age_sim_s=age))
        if tag["patch"].endswith("-0167"):
            result=dict(outcome=row["outcome"],reached=row["goals_reached"],maps_incomplete=marker.is_file())
            goals.append(dict(tag,**inspect_goal(raw,files,paths,result,truth,halo),
                              **fifth_leg(raw,files,paths,trace,mission,truth,halo,events)))
    for name,data in (("run_evidence.csv",safety),("approach_intervals.csv",intervals),("no_path_evidence.csv",failures),
                      ("0167_leg5.csv",goals),("abnormal_runs.csv",abnormal),("fisher_holm.csv",list(tests(rows)))):
        write(name,data)


if __name__=="__main__":
    main()
