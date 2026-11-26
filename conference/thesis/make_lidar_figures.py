"""Generate thesis LiDAR figures, tables and numeric macros from archived CSVs."""

import argparse
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact


ROOT = Path(__file__).resolve().parents[1]
SENSORS = {"lidar": "LiDAR", "camera1": "Depth camera 1", "camera2": "Depth camera 2"}
OUTCOMES = {
    "completed": ("Completed", "#127960"),
    "partial": ("Partial", "#366eac"),
    "no_path": ("No path", "#d99034"),
    "stuck": ("Stuck", "#68748a"),
    "rollover": ("Rollover", "#ab4663"),
    "other": ("Other ending", "#3d424a"),
    "unknown": ("Unknown ending", "#b7b9bf"),
}
FAILURE_TYPES = ("goal_cell", "start_cell", "start_steep", "corridor", "other", "unknown")
SAFETY = (
    ("rolled_over", "Rollover", "rollovers"),
    ("truth_lethal_len_m", "Lethal [m]", "lethal_m"),
    ("debris_len_m", "Debris [m]", "debris_m"),
    ("min_truth_clearance_m", "Min. box [m]", "min_box_m"),
    ("ev_off_path", "Off-path", "off_path"),
    ("ev_unsafe_tilt", "Unsafe tilt", "unsafe_tilt"),
)
DEBRIS_CLEARANCE = (
    ("debris_entries", "Debris entries", "debris_entries"),
    ("truth_below_radius_entries", "Box intervals", "box_intervals"),
    ("truth_below_radius_s", "Box [sim s]", "box_s"),
)
FOCUS_BEACH = "08OB88_00332"
TERRAIN_STUDIES = ("050", "057")
STUDY_064 = "064"
CONDITIONS_064 = ("S", "P", "D", "PD", "G", "GD")
TERRAIN_PAIRS_064 = (("Sensor terrain", ("S", "D")), ("Prior terrain", ("P", "PD")),
                     ("Ground-only points", ("G", "GD")))
COMPARISONS_064 = (("PD", "S"), ("GD", "S"), ("PD", "P"), ("GD", "G"))
METRICS_064 = {"box_runs": "Box clearance < 0.5 m", "debris_runs": "Debris cell traversal",
               "completed": "Completed"}


@dataclass(frozen=True)
class Study:
    task: str
    csv: str
    conditions: dict | None


STUDIES = (
    Study("030", "eval_ground_endpoint/runs.csv", {"C0": "C0", "C1": "C1", "C2": "C2"}),
    Study("035", "eval_035/runs.csv", {"P1": "C1 + v1"}),
    Study("037", "real_sensors_compare/runs.csv", {"L": "L", "LC": "LC"}),
    Study("039", "rtf_compare/stage_b/common_eval/runs.csv", {"0.3": "0.3x target", "1.0": "1.0x target"}),
    Study("044", "eval_044/common_eval/runs.csv", None),
    Study("050", "eval_050/common_eval/runs.csv", {"S": "050 S", "P": "050 P", "V": "050 V"}),
    Study("057", "eval_057/common_eval/runs.csv", {"S": "057 S", "PG": "057 PG", "SGN": "057 SGN"}),
    Study(STUDY_064, "eval_064/common_eval_all/runs.csv",
          {condition: f"064 {condition} (GPU, 1.0x)" for condition in CONDITIONS_064}),
)


class Sources:
    """Hash the bytes passed to the CSV reader, excluding skipped inputs."""

    def __init__(self, results):
        self.results = Path(results).resolve()
        self.hashes = {}

    def read(self, name):
        path = self.results / name
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            print(f"Skipped missing results file: {path}")
            return None
        key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        self.hashes[key] = hashlib.sha256(raw).hexdigest()
        return pd.read_csv(BytesIO(raw), dtype={"condition": str})


def require(frame, columns, name):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{name}: missing columns {', '.join(sorted(missing))}")


def outcome_for(study, row):
    if "board_outcome" in row:
        value = row["board_outcome"]
    else:
        value = row.get("outcome")
        # Match the common evaluator's wall-timeout classification for 030.
        stationary = row.get("stationary_tail_s")
        if study == "030" and value == "wall_timeout" and pd.notna(stationary) and stationary >= 10:
            value = "stuck"
    if pd.isna(value) or value in ("unknown", "running", "unrun", "pending", "record_incomplete"):
        return "unknown"
    return value if value in OUTCOMES else "other"


def load_runs(sources):
    """Load published per-run records, separating the replicated and pilot cohorts."""
    main, safety = [], []
    for study in STUDIES:
        frame = sources.read(study.csv)
        if frame is None:
            continue
        keys = ["condition", "patch", "rep"]
        require(frame, keys, study.csv)
        if not ({"outcome", "board_outcome"} & set(frame.columns)):
            raise ValueError(f"{study.csv}: missing outcome columns")
        rep = pd.to_numeric(frame["rep"])
        if not np.isfinite(rep).all() or not ((rep > 0) & (rep == np.floor(rep))).all():
            raise ValueError(f"{study.csv}: invalid repetition number")
        frame["rep"] = rep.astype(int)
        if frame[keys].isna().any().any() or frame.duplicated(keys).any():
            raise ValueError(f"{study.csv}: invalid or duplicate run keys")
        available = sorted(frame["condition"].unique())
        conditions = dict(zip(available, available)) if study.conditions is None else study.conditions
        for condition, label in conditions.items():
            group = frame[frame["condition"] == condition]
            if group.empty:
                print(f"Skipped missing condition: {study.task}/{condition}")
                continue
            records = group.sort_values(["patch", "rep"]).to_dict("records")
            rows = [dict(row, study=study.task, condition_label=label,
                         ending=outcome_for(study.task, row)) for row in records]
            main.extend(rows)
            safety.extend(rows)
        if study.task == "035":
            pilots = frame[frame["condition"].isin(("S1", "S2"))]
            safety.extend(dict(row, study=study.task, condition_label=row["condition"]+" (pilot)",
                               ending=outcome_for(study.task, row)) for row in pilots.to_dict("records"))
    return main, safety


def count_outcomes(runs):
    rows = []
    for (study, condition), group in grouped(runs):
        endings = [r["ending"] for r in group]
        rows.append(dict(study=study, condition=condition, condition_label=group[0]["condition_label"],
                         n=len(group), **{key: endings.count(key) for key in OUTCOMES}))
    return rows


def grouped(runs):
    groups = {}
    for row in runs:
        groups.setdefault((row["study"], row["condition"]), []).append(row)
    return groups.items()


def observed(group, column):
    values = [r[column] for r in group if pd.notna(r.get(column))]
    if column == "rolled_over":
        return [int(str(value).lower() == "true") for value in values
                if str(value).lower() in ("true", "false")]
    return list(pd.to_numeric(values))


def safety_rows(runs, *, patch=None):
    if patch is not None:
        runs = [row for row in runs if row["study"] in (*TERRAIN_STUDIES, STUDY_064) and row["patch"] == patch]
    rows = []
    for (study, condition), group in grouped(runs):
        row = dict(study=study, condition=condition, condition_label=group[0]["condition_label"],
                   n=len(group), patch=patch)
        for source, _, key in (*SAFETY, *DEBRIS_CLEARANCE):
            values = observed(group, source)
            row[key] = (min(values) if key == "min_box_m" else sum(values)) if values else None
            row[key+"_n"] = len(values)
        lengths = observed(group, "debris_len_m")
        row["debris_runs"] = sum(length > 0 for length in lengths) if lengths else None
        row["debris_runs_n"] = len(lengths)
        rows.append(row)
    return rows


def outcomes_064(runs):
    """Count the three prespecified binary outcomes over the complete 064 cohort."""
    groups = {condition: group for (study, condition), group in grouped(runs) if study == STUDY_064}
    if not groups:
        return []
    beaches = {row["patch"] for group in groups.values() for row in group}
    expected = {(patch, rep) for patch in beaches for rep in range(1, 7)}
    if len(beaches) != 5 or any({(r["patch"], r["rep"]) for r in groups.get(condition, [])} != expected
                               for condition in CONDITIONS_064):
        raise ValueError("064 requires six repetitions at the same five beaches per condition")
    counts = []
    for condition, group in groups.items():
        debris = observed(group, "debris_len_m")
        box = observed(group, "min_truth_clearance_m")
        if any(len(values) != len(group) or not np.isfinite(values).all() for values in (debris, box)):
            raise ValueError(f"064 {condition}: missing debris lengths or box clearances")
        if any(row["ending"] == "unknown" for row in group):
            raise ValueError(f"064 {condition}: missing run outcomes")
        counts.append(dict(study=STUDY_064, condition=condition, n=len(group),
                           box_runs=sum(distance < .5 for distance in box),
                           debris_runs=sum(length > 0 for length in debris),
                           completed=sum(row["ending"] == "completed" for row in group)))
    return counts


def fisher_holm_064(counts):
    if not counts:
        return []
    groups = {row["condition"]: row for row in counts}
    rows = []
    for metric in METRICS_064:
        family = []
        for a, b in COMPARISONS_064:
            left, right = groups[a], groups[b]
            x, y, n, m = left[metric], right[metric], left["n"], right["n"]
            p = fisher_exact([[x, n-x], [y, m-y]], alternative="two-sided").pvalue
            family.append(dict(study=STUDY_064, metric=metric, condition_a=a, condition_b=b,
                               events_a=x, n_a=n, events_b=y, n_b=m, p_raw=p,
                               comparison=f"{a} vs {b}", a_rate=f"{x}/{n}", b_rate=f"{y}/{m}"))
        ordered = sorted(family, key=lambda row: row["p_raw"])
        adjusted = np.maximum.accumulate([row["p_raw"]*(len(ordered)-rank) for rank, row in enumerate(ordered)])
        for row, p in zip(ordered, np.minimum(adjusted, 1.)):
            row["p_holm"] = p
        rows.extend(family)
    return rows


def failure_type(row):
    # The common evaluator records the terminal type directly. Older runs
    # only retain failure counts, so use them when all failures share a type.
    if "no_path_type" in row:
        value = row["no_path_type"]
        return value if value in FAILURE_TYPES else "unknown"
    counts = {key: row.get("fail_"+key, 0) for key in FAILURE_TYPES[:-1]}
    if not all(pd.notna(value) for value in counts.values()):
        return "unknown"
    present = [key for key, value in counts.items() if value > 0]
    failed = row.get("failed_plans")
    if len(present) == 1 and pd.notna(failed) and counts[present[0]] == failed:
        return present[0]
    return "unknown"


def failure_rows(runs, sources):
    rows = []
    for study in dict.fromkeys(row["study"] for row in runs if row["study"] != STUDY_064):
        labels = [failure_type(row) for row in runs if row["study"] == study and row["ending"] == "no_path"]
        for kind in FAILURE_TYPES:
            if kind in labels:
                rows.append(dict(study=study, record="Terminal no path", metric=kind,
                                 count=labels.count(kind), n=len(labels)))
        if not labels:
            rows.append(dict(study=study, record="Terminal no path", metric="all", count=0, n=0))

    checks = sources.read("waypoint_feasibility/goal_cell.csv")
    if checks is not None:
        require(checks, ["prior_status"], "046 goal_cell.csv")
        status = checks["prior_status"]
        valid = status.isin(("ok", "blocked_cell", "unreachable"))
        detected = status.isin(("blocked_cell", "unreachable"))
        rows.append(dict(study="046", record="Preflight", metric="flagged",
                         count=int(detected.sum()) if valid.any() else None, n=int(valid.sum())))
        if not valid.all():
            rows.append(dict(study="046", record="Preflight", metric="unclassified",
                             count=int((~valid).sum()), n=len(status)))

    replay = sources.read("terrain_from_prior/goals.csv")
    if replay is not None:
        for base, record in (("final", "Final map"), ("failure_snapshot", "Failure snapshot")):
            cols = [base+"_n", *(base+"_"+tag for tag in ("sensor_route", "prior_route", "recovered"))]
            require(replay, cols, "047 goals.csv")
            n = int(replay[cols[0]].sum())
            for field, metric in zip(cols[1:], ("sensor_route", "prior_route", "gained_route")):
                rows.append(dict(study="047", record=record, metric=metric,
                                 count=int(replay[field].sum()) if n else None, n=n))
        require(replay, ["missing_n", "total"], "047 goals.csv")
        rows.append(dict(study="047", record="Replay coverage", metric="missing_map",
                         count=int(replay["missing_n"].sum()), n=int(replay["total"].sum())))
    if any(row["study"] == STUDY_064 for row in runs):
        labels = ["pointcloud_unavailable_or_stale" if row.get("sensor_error") == "lidar_unavailable_or_stale"
                  else failure_type(row)
                  for row in runs if row["study"] == STUDY_064 and row["ending"] == "no_path"]
        for kind in (*FAILURE_TYPES, "pointcloud_unavailable_or_stale") if labels else ("all",):
            if kind in labels or not labels:
                rows.append(dict(study=STUDY_064, record="Terminal no path (GPU, 1.0x)", metric=kind,
                                 count=labels.count(kind), n=len(labels)))
    return rows


def timing_rows(sources):
    rows = []
    bench = sources.read("map_speed/timing.csv")
    if bench is not None:
        require(bench, ["mapper", "ground", "stage", "sensor", "version", "median_ms", "p95_ms"], "038 timing.csv")
        selected = bench[(bench["mapper"] == "PointCloudMapMulti") &
                         (bench["ground"] == "all_returns") & (bench["stage"] == "total")]
        for setup in ("before", "after"):
            for sensor in SENSORS:
                sample = selected[(selected["version"] == setup) & (selected["sensor"] == sensor)]
                if len(sample) > 1:
                    raise ValueError(f"038 duplicate benchmark for {setup}/{sensor}")
                if len(sample):
                    row = sample.iloc[0]
                    rows.append(dict(study="038", setup=setup, sensor=sensor, n=None,
                                     median_ms=row["median_ms"], p95_ms=row["p95_ms"]))
    latency = sources.read("rtf_compare/stage_b/sensor_updates.csv")
    if latency is not None:
        keys = ["patch", "factor", "rep", "sensor"]
        require(latency, [*keys, "median_s", "p95_s"], "039 sensor_updates.csv")
        if latency.duplicated(keys).any():
            raise ValueError("039 duplicate sensor timings")
        for setup in (0.3, 1.0):
            for sensor in SENSORS:
                sample = latency[(latency["factor"] == setup) & (latency["sensor"] == sensor)]
                paired = sample[["median_s", "p95_s"]].dropna()
                if len(paired):
                    rows.append(dict(study="039", setup=f"{setup:.1f}", sensor=sensor, n=len(paired),
                                     median_ms=1000*paired["median_s"].median(),
                                     p95_ms=1000*paired["p95_s"].median()))
    return rows


def save_figure(fig, output, name):
    fig.savefig(output/f"{name}.png", dpi=220, facecolor="white")
    fig.savefig(output/f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def plot_outcomes(runs, totals, output, *, name="F8"):
    """One tile per run, left to right in recorded repetition order."""
    beaches = sorted({r["patch"] for r in runs})
    columns = [(r["study"], r["condition"]) for r in totals]
    fig, ax = plt.subplots(figsize=(max(6, 2+1.03*len(columns)), 2.3+.35*len(beaches)))
    ax.set_axis_off()
    if not runs:
        ax.text(.5, .5, "No outcome records", ha="center", va="center", transform=ax.transAxes)
        save_figure(fig, output, name)
        return
    cells = {}
    for row in runs:
        cells.setdefault((row["patch"], row["study"], row["condition"]), []).append(row)

    ax.set_xlim(-.12, len(columns))
    ax.set_ylim(len(beaches)-.48, -1.22)
    for i, beach in enumerate(beaches):
        ax.text(-.22, i, beach, ha="right", va="center", fontsize=9, family="monospace")
        for j, (study, condition) in enumerate(columns):
            trials = cells.get((beach, study, condition), [])
            width = .86/max(3, max((r["rep"] for r in trials), default=0))
            ax.add_patch(Rectangle((j+.05, i-.32), .86, .64, color="#edf0f3", linewidth=0))
            for row in trials:
                k = row["rep"]-1
                color = OUTCOMES[row["ending"]][1]
                ax.add_patch(Rectangle((j+.05+k*width+.015, i-.27), width-.03, .54,
                                       facecolor=color, linewidth=0))
    for j, row in enumerate(totals):
        ax.text(j+.48, -.61, row["condition_label"], fontsize=9, ha="center", va="center")
    for study in dict.fromkeys(row["study"] for row in totals):
        indices = [i for i, (task, _) in enumerate(columns) if task == study]
        left, right = min(indices), max(indices)
        ax.text((left+right+1)/2, -1.02, study, fontsize=10, fontweight="semibold", ha="center", va="center")
        ax.hlines(-.82, left+.05, right+.91, color="#a7afb7", linewidth=.8)

    shown = {r["ending"] for r in runs}
    handles = [Patch(facecolor=color, label=label) for key, (label, color) in OUTCOMES.items() if key in shown]
    handles.append(Patch(facecolor="#edf0f3", label="No run in archive"))
    fig.legend(handles=handles, ncols=min(4, len(handles)), loc="lower center", fontsize=8, frameon=False,
               bbox_to_anchor=(.55, .09 if len(handles) > 4 else .10))
    fig.text(.094, .93, "LiDAR trial outcomes by beach", fontsize=15, fontweight="semibold")
    fig.text(.094, .03, "Tiles follow the recorded repetition numbers, from left to right.", fontsize=8, color="#475467")
    fig.subplots_adjust(left=.20, right=.985, top=.87, bottom=.22)
    save_figure(fig, output, name)


def plot_timings(rows, runs, output):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.7))
    colors = ("#496581", "#aa582c")
    for ax, study, title, setups, labels in zip(
            axes, ("038", "039"),
            ("038  Synthetic benchmark · all returns", "039  Gazebo runs · non-obstacle returns"),
            (("before", "after"), ("0.3", "1.0")),
            (("Before", "After"), ("0.3x target", "1.0x target"))):
        ax.set_title(title, loc="left", fontweight="semibold", fontsize=10, pad=12)
        sample = {(r["setup"], r["sensor"]): r for r in rows if r["study"] == study}
        if not sample:
            ax.set_axis_off()
            ax.text(.5, .5, "No timing records", ha="center", va="center", transform=ax.transAxes)
            continue
        if study == "038":
            ax.set_xscale("log")
            ax.set_xticks([5, 10, 20, 50, 100, 200], labels=["5", "10", "20", "50", "100", "200"])
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#e5e9ee", linewidth=.7)
        ax.spines[["left", "right", "top"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_ylim(7.45, -.8)
        ax.set_yticks([.5, 3.5, 6.5], SENSORS.values(), fontsize=8)
        for i, sensor in enumerate(SENSORS):
            for j, setup in enumerate(setups):
                row = sample.get((setup, sensor))
                if row and pd.notna(row["median_ms"]) and pd.notna(row["p95_ms"]):
                    y = 3*i+j
                    ax.hlines(y, row["median_ms"], row["p95_ms"], color=colors[j], linewidth=1.8)
                    ax.scatter(row["median_ms"], y, c=colors[j], marker="o", s=25, zorder=3)
                    ax.scatter(row["p95_ms"], y, c=colors[j], marker="D", s=23, zorder=3)
        if study == "038":
            data = [row[key] for row in sample.values() for key in ("median_ms", "p95_ms")
                    if pd.notna(row[key]) and row[key] > 0]
            ax.set_xlim(min([5, *data])/1.12, max([200, *data])*1.15)
        ax.set_xlabel("Update time [ms]" + (" · log scale" if study == "038" else ""), fontsize=9)
        ax.legend(handles=[Patch(facecolor=color, label=label) for color, label in zip(colors, labels)],
                  frameon=False, loc="upper center", bbox_to_anchor=(.5, -.16), fontsize=8, ncols=2)
    ratios = observed([r for r in runs if r["study"] == "039" and r["condition"] == "1.0"], "sim_to_wall_ratio")
    notes = "Circles show medians and diamonds show 95th percentiles. 039 plots medians of per-run values."
    if ratios:
        notes += f"\nFor the 1.0x target, 039 measured {min(ratios):.3f}–{max(ratios):.3f}x."
    fig.text(.06, .94, "Map update time by sensor", fontsize=15, fontweight="semibold")
    fig.text(.06, .026, notes, fontsize=8, color="#475467", linespacing=1.5)
    fig.subplots_adjust(left=.13, right=.985, top=.85, bottom=.275, wspace=.39)
    save_figure(fig, output, "F9")


def plot_064(counts, output):
    fig, axes = plt.subplots(1, 3, sharey=True, figsize=(10.3, 3.65))
    if not counts:
        for ax in axes:
            ax.set_axis_off()
        axes[1].text(.5, .5, "No 064 records", ha="center", va="center", transform=axes[1].transAxes)
        save_figure(fig, output, "F11")
        return
    by_condition = {row["condition"]: row for row in counts}
    colors = ("#4f6283", "#007b69")
    positions = np.arange(len(TERRAIN_PAIRS_064))*1.23
    n = counts[0]["n"]
    for ax, (metric, title) in zip(axes, METRICS_064.items()):
        ax.set_title(title, loc="left", fontweight="semibold", fontsize=11, pad=11)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#dde2e8", linewidth=.7)
        ax.spines[["left", "right", "top"]].set_visible(False)
        ax.spines["bottom"].set_color("#a4adba")
        ax.set_xlim(0, n)
        ax.set_xticks(np.linspace(0, n, 4))
        ax.tick_params(axis="both", labelsize=9, length=0)
        for y, (_, pair) in zip(positions, TERRAIN_PAIRS_064):
            for dy, condition, color in zip((-.22, .22), pair, colors):
                count = by_condition[condition][metric]
                ax.barh(y+dy, count, color=color, height=.30)
                ax.text(count+.65 if count < n-5 else count-.65, y+dy, f"{condition}  {count}",
                        ha="left" if count < n-5 else "right", va="center", fontsize=8.5,
                        color="#1c2939" if count < n-5 else "white")
    axes[0].set_yticks(positions, [name for name, _ in TERRAIN_PAIRS_064])
    axes[0].set_ylim(positions[-1]+.54, -.54)
    fig.text(.05, .92, "064 · GPU rendering at 1.0×", fontsize=16, fontweight="semibold", color="#1c2939")
    fig.supxlabel(f"Runs (out of {n} per condition)", y=.14, fontsize=10)
    fig.legend(handles=[Patch(facecolor=color, label=label)
                        for color, label in zip(colors, ("Centre clearance", "Distance clearance"))],
               loc="lower center", bbox_to_anchor=(.56, .026), ncols=2, fontsize=9, frameon=False)
    fig.subplots_adjust(left=.203, right=.972, top=.759, bottom=.255, wspace=.20)
    save_figure(fig, output, "F11")


TABLE_HEADERS = {
    "study": "Task", "condition_label": "Condition", "n": "Runs",
    **{key: label for key, (label, _) in OUTCOMES.items()},
    **{key: label for _, label, key in (*SAFETY, *DEBRIS_CLEARANCE)},
    "debris_runs": "Runs in debris",
    "other": "Other", "unknown": "Unknown",
    "record": "Record", "metric": "Measure", "count": "Count",
    "comparison": "Comparison", "a_rate": "First", "b_rate": "Second",
    "p_raw": "Raw p", "p_holm": "Holm p",
}
FAILURE_LABELS = {
    "sensor_route": "Route with sensor terrain",
    "prior_route": "Route with prior terrain",
    "gained_route": "Route only with prior terrain",
    "missing_map": "Unavailable map records",
    "flagged": "Goal flagged before travel",
    "unclassified": "Unclassified checks",
    "all": "No no-path endings",
    "pointcloud_unavailable_or_stale": "Point cloud unavailable or stale",
}
NOTES = {
    "T4": "Counts of archived repetitions. 039 conditions are target settings. 035 includes the replicated P1 cohort.",
    "T5": ("Lengths and event counts are sums over available runs. Min. box is the minimum of recorded "
           "centre-to-box clearances. A dash denotes missing measurements. The CSV gives the number of "
           "observations per metric. 035 pilot rows represent single runs. Runs in debris have a positive "
           "debris length. Debris entries count consecutive visits to debris cells. Box intervals and "
           "duration use a centre-to-box distance strictly below 0.5 m."),
    "T6": ("Terminal failure types count runs ending in no path. N is the number of eligible records. "
           "047 uses archived map replay, with final and failure-time maps kept separate."),
    "T7": ("064 trials (GPU, 1.0x). Counts are runs per condition. "
           "Two-sided Fisher exact tests with Holm adjustment across the four comparisons within each measure."),
}
T4_FIELDS = ["study", "condition", "condition_label", "n", *OUTCOMES]
T5_FIELDS = ["study", "condition", "condition_label", "n",
             *(field for _, _, key in (*SAFETY, *DEBRIS_CLEARANCE) for field in (key, key+"_n")),
             "debris_runs", "debris_runs_n", "patch"]
T5_CLEARANCE_FIELDS = ["study", "condition_label", "n", "debris_entries", "debris_runs", "debris_m",
                       "box_intervals", "box_s"]
T6_FIELDS = ["study", "record", "metric", "count", "n"]
T7_FIELDS = ["study", "metric", "condition_a", "condition_b", "events_a", "n_a",
             "events_b", "n_b", "p_raw", "p_holm"]
F9_FIELDS = ["study", "setup", "sensor", "n", "median_ms", "p95_ms"]


def numeric(value):
    return isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(value)


def display(value):
    if pd.isna(value):
        return "—"
    return f"{value:.9g}" if numeric(value) else str(value)


def latex(value):
    escapes = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
               "<": r"\textless{}",
               "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "—": r"\textemdash{}"}
    return "".join(escapes.get(c, c) for c in value)


def write_table(output, name, rows, fields, sections):
    frame = pd.DataFrame(rows, columns=fields)
    frame.to_csv(output/f"{name}.csv", index=False, float_format="%.12g")
    md_line = lambda row: "| " + " | ".join(s.replace("|", r"\|") for s in row) + " |"
    tex_line = lambda row: " & ".join(map(latex, row)) + " " + r"\\"
    md, tex = [], [f"% {NOTES[name]}"]
    for title, subset, visible in sections:
        if title:
            md.extend(("", f"**{title}**", ""))
            tex.extend((r"\par\medskip", r"\textbf{" + latex(title) + r"}\par\smallskip"))
        labels = [TABLE_HEADERS[c] if name != "T6" or c != "n" else "N" for c in visible]
        metric_labels = METRICS_064 if name == "T7" else FAILURE_LABELS
        values = [[f"{r[c]:.6f}" if c in ("p_raw", "p_holm")
                   else display(metric_labels.get(r[c], r[c]) if c == "metric" else r[c])
                   for c in visible] for r in subset]
        if not values:
            values = [["No records", *(["—"]*(len(labels)-1))]]
        md.extend((md_line(labels), md_line(["---"]*len(labels)), *(md_line(r) for r in values)))
        alignment = "".join("l" if c in ("study", "condition_label", "record", "metric", "comparison") else "r"
                            for c in visible)
        tex.extend((r"\begin{tabular}{" + alignment + "}", r"\hline", tex_line(labels),
                    r"\hline", *(tex_line(r) for r in values), r"\hline", r"\end{tabular}"))
    md.extend(("", NOTES[name]))
    (output/f"{name}.md").write_text("\n".join(md)+"\n")
    (output/f"{name}.tex").write_text("\n".join(tex)+"\n")
    print(f"{name}: {len(rows)} rows")


DIGITS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine")
MACRO_FIELDS = {
    "TFour": ("study", "condition"),
    "TFive": ("study", "condition", "patch"),
    "TSix": ("study", "record", "metric"),
    "TSeven": ("study", "metric", "condition_a", "condition_b"),
    "FEleven": ("study", "condition"),
    "FNine": ("study", "setup", "sensor"),
}


def macro_part(value):
    value = "".join(DIGITS[int(c)] if c in "0123456789" else "Dot" if c == "." else c for c in str(value))
    return "".join(w[0].upper()+w[1:] for w in re.findall(r"[A-Za-z]+", value))


def write_numbers(output, tables):
    lines = ["% Generated from the archived LiDAR results. Missing values have no macro."]
    names = set()
    for table, rows in tables.items():
        keys = MACRO_FIELDS[table]
        for row in rows:
            prefix = "Lidar"+table+"Task"+"".join(macro_part(row[key]) for key in keys if row[key] is not None)
            for field, value in row.items():
                if field in keys or not numeric(value):
                    continue
                name = prefix+macro_part(field)
                if name in names:
                    raise ValueError(f"duplicate LaTeX command: {name}")
                names.add(name)
                lines.append(f"\\newcommand{{\\{name}}}{{{value:.9g}}}")
    (output/"numbers_lidar.tex").write_text("\n".join(lines)+"\n")


def make_all(output=ROOT/"thesis/out_lidar", results=ROOT/"results"):
    """Generate the LiDAR artifacts in a separate output directory."""
    output, results = Path(output).resolve(), Path(results).resolve()
    protected = (ROOT/"results", ROOT/"paper", ROOT/"thesis/out", results)
    if any(output.is_relative_to(path) for path in protected):
        raise ValueError(f"output would write into a protected directory: {output}")
    sources = Sources(results)
    runs, safety = load_runs(sources)
    t4, t5 = count_outcomes(runs), safety_rows(safety)
    focused = safety_rows(safety, patch=FOCUS_BEACH)
    t6, f9 = failure_rows(runs, sources), timing_rows(sources)
    f11 = outcomes_064(runs)
    t7 = fisher_holm_064(f11)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        staging = Path(temporary)
        write_table(staging, "T4", t4, T4_FIELDS, [(None, t4, [c for c in T4_FIELDS if c != "condition"])])
        safety_visible = ["study", "condition_label", "n", *(key for _, _, key in SAFETY)]
        safety_sections = [(None, t5, safety_visible),
                           ("Debris and box proximity under 0.5 m", t5, T5_CLEARANCE_FIELDS)]
        if focused:
            safety_sections.append((FOCUS_BEACH + " only", focused, T5_CLEARANCE_FIELDS))
        write_table(staging, "T5", t5+focused, T5_FIELDS, safety_sections)
        write_table(staging, "T6", t6, T6_FIELDS, [(None, t6, T6_FIELDS)])
        write_table(staging, "T7", t7, T7_FIELDS,
                    [(None, t7, ["metric", "comparison", "a_rate", "b_rate", "p_raw", "p_holm"])])
        pd.DataFrame(f9, columns=F9_FIELDS).to_csv(staging/"F9_statistics.csv", index=False, float_format="%.12g")
        other_figures = (*TERRAIN_STUDIES, STUDY_064)
        plot_outcomes([r for r in runs if r["study"] not in other_figures],
                      [r for r in t4 if r["study"] not in other_figures], staging)
        plot_outcomes([r for r in runs if r["study"] in TERRAIN_STUDIES],
                      [r for r in t4 if r["study"] in TERRAIN_STUDIES], staging,
                      name="F10")
        plot_timings(f9, runs, staging)
        plot_064(f11, staging)
        write_numbers(staging, {"TFour": t4, "TFive": t5+focused, "TSix": t6,
                                "FNine": f9, "FEleven": f11, "TSeven": t7})
        (staging/"sources.json").write_text(json.dumps(sources.hashes, sort_keys=True, indent=2)+"\n")
        for file in staging.iterdir():
            file.replace(output/file.name)
    print(f"F8–F11, T4–T7, numbers_lidar.tex and sources.json: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"thesis/out_lidar")
    parser.add_argument("--results", type=Path, default=ROOT/"results")
    args = parser.parse_args()
    make_all(args.output, args.results)
