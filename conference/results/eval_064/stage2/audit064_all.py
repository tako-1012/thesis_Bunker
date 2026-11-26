"""Reapply the stage 1 audit definitions to all 180 runs and run the prespecified tests."""
from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

from experiments.eval_runs import read_trajectory
from results.eval_064.audit064 import (
    PATCHES, CONDITIONS, applications, approaches, inspect_goal, length, manifest_evidence,
    masks, read_json, records, revision_data, terminal,
)
from tapp.endpoint_policy import audit_path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
PAIRS = (("PD", "S"), ("GD", "S"), ("PD", "P"), ("GD", "G"))
INDICATORS = {
    "completed": lambda row: row["outcome"] == "completed",
    "debris": lambda row: float(row["debris_len_m"]) > 0,
    "box_under_0_5m": lambda row: float(row["min_truth_clearance_m"]) < .5,
}


def write(name, rows):
    if not rows:
        print(f"{name}: no rows", flush=True)
        return
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (OUT / name).open("x", newline="") as f:
        writer = csv.DictWriter(f, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows)} rows", flush=True)


def comparisons(rows):
    for metric, applies in INDICATORS.items():
        counts = {c: sum(applies(row) for row in rows if row["condition"] == c) for c in CONDITIONS}
        results = []
        for a, b in PAIRS:
            k, j = counts[a], counts[b]
            p = fisher_exact([[k, 30-k], [j, 30-j]], alternative="two-sided").pvalue
            results.append(dict(metric=metric, condition_a=a, condition_b=b,
                                a_count=k, a_total=30, b_count=j, b_total=30, p_raw=p))
        previous = 0.0
        for i, row in enumerate(sorted(results, key=lambda r: r["p_raw"])):
            previous = min(1.0, max(previous, row["p_raw"]*(len(results)-i)))
            row["p_holm"] = previous
        yield from results


def planner_errors(raw):
    files = sorted((raw / "follower").glob("*/mission.json"))
    return ",".join(sorted({error for path in files if (error := read_json(path).get("online_error"))}))


def validate_pairs(rows):
    def key(row):
        return row["patch"], row["condition"], row["rep"]

    assert Counter(map(key, rows)) == Counter(
        (patch, condition, str(rep)) for patch in PATCHES for condition in CONDITIONS for rep in range(1, 7))
    old = {key(row): row for row in records(ROOT / "common_eval/runs.csv")}
    for row in rows:
        if int(row["rep"]) <= 3:
            assert row == old[key(row)], (key(row), "stage 1 common evaluation changed")


def main():
    rows = records(ROOT / "common_eval_all/runs.csv")
    validate_pairs(rows)
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
        metrics.append(dict(
            tag, executed_xy_m=length(trace[:, 1:]), plan_versions=len(paths),
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
            failure = terminal(raw, saved, row, truth, halo, prior)
            failure["follower_error"] = planner_errors(raw)
            failures.append(dict(tag, **failure))
        if tag["patch"] == "08OB88_-0167":
            state = dict(outcome=row["outcome"], reached=row["goals_reached"], maps_incomplete=marker.is_file())
            goals.append(dict(tag, **inspect_goal(raw, files, paths, state, truth, halo)))
        for event in json.loads(row["stops_detail"] or "[]"):
            if event["kind"] == "unsafe_tilt":
                tilts.append(dict(tag, outcome=row["outcome"], **event))
    stage1 = {(r["patch"], r["condition"], r["rep"]): r for r in records(ROOT / "run_evidence.csv")}
    for run in metrics:
        key = run["patch"], run["condition"], run["rep"]
        if key in stage1:
            assert dict(zip(run, map(str, run.values()))) == stage1[key], (key, "stage 1 audit changed")
    for name, data in (("run_evidence_all.csv", metrics), ("approach_intervals_all.csv", episodes),
                       ("no_path_evidence_all.csv", failures), ("0167_goals_all.csv", goals),
                       ("tilt_evidence_all.csv", tilts), ("fisher_holm.csv", list(comparisons(rows)))):
        write(name, data)


if __name__ == "__main__":
    main()
