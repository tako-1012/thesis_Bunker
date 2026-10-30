"""Pair unchanged scenario identities, preserve task-009 tests and compare LAS outcomes."""

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.analyze import paired_test, holm
from experiments.real_beach import KEY, STAT_COLS, table

RESULTS = Path(__file__).resolve().parent.parent / "results"
ORIGINAL_METRICS = ["steep_len", "mean_cost", "climb", "energy_vs_A_pct", "length_xy"]
REQUESTED_METRICS = [
    "steep_exposed_pct",
    "mean_cost",
    "climb",
    "energy_vs_A_pct",
    "length_xy",
    "p95_roll",
]


def paired(old, new, keys):
    """Never match rows by position or silently drop missing/duplicate identities."""
    if old[keys].isna().any().any() or new[keys].isna().any().any():
        raise ValueError("scenario keys contain missing values")
    joined = old.merge(
        new,
        on=keys,
        how="outer",
        suffixes=("_old", "_new"),
        validate="one_to_one",
        indicator=True,
    )
    if not joined["_merge"].eq("both").all():
        raise ValueError(
            "unmatched scenario identities: "
            + joined.loc[joined["_merge"] != "both", keys + ["_merge"]].to_string(
                index=False
            )
        )
    return joined.drop(columns="_merge").sort_values(keys).reset_index(drop=True)


def read(folder, name):
    frame = pd.read_csv(folder / name)
    for col in ("debris", "success"):
        if col in frame and frame[col].dtype != bool:
            decoded = (
                frame[col].astype(str).str.lower().map({"true": True, "false": False})
            )
            if decoded.isna().any():
                raise ValueError("invalid boolean column: " + col)
            frame[col] = decoded.astype(bool)
    return frame


def direction(effect):
    return "lower" if effect < 0 else ("higher" if effect > 0 else "equal")


def compare_a(old, new, output):
    a, b = read(old, "statistics.csv"), read(new, "statistics.csv")
    real = paired(
        a[a.source == "real"],
        b[b.source == "real"],
        ["kind", "split", "side_m", "seed"],
    )
    rows = []
    for metric in STAT_COLS + ["nodata_fraction", "water_fraction"]:
        x, y = real[metric + "_old"], real[metric + "_new"]
        rows.append(
            dict(
                metric=metric,
                n=len(real),
                old_median=x.median(),
                new_median=y.median(),
                paired_delta_median=(y - x).median(),
            )
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "compare_A_statistics.csv", index=False)
    table("A: matched real-patch statistics; new minus old (all 60)", frame)
    artificial = paired(
        a[a.source == "synthetic"],
        b[b.source == "synthetic"],
        ["kind", "side_m", "seed"],
    )
    outside = []
    for kind, g in artificial.groupby("kind"):
        for metric in STAT_COLS:
            lo, hi = real[metric + "_old"].quantile([0.1, 0.9])
            ln, hn = real[metric + "_new"].quantile([0.1, 0.9])
            vo, vn = g[metric + "_old"].median(), g[metric + "_new"].median()
            before = bool(vo < lo or vo > hi)
            after = bool(vn < ln or vn > hn)
            if before or after:
                outside.append(
                    dict(
                        kind=kind,
                        metric=metric,
                        old_outside=before,
                        new_outside=after,
                        change=(
                            "both"
                            if before and after
                            else ("new_only" if after else "old_only")
                        ),
                        synthetic_old=vo,
                        synthetic_new=vn,
                        old_p10=lo,
                        old_p90=hi,
                        new_p10=ln,
                        new_p90=hn,
                    )
                )
    frame = pd.DataFrame(
        outside,
        columns=[
            "kind",
            "metric",
            "old_outside",
            "new_outside",
            "change",
            "synthetic_old",
            "synthetic_new",
            "old_p10",
            "old_p90",
            "new_p10",
            "new_p90",
        ],
    )
    frame.to_csv(output / "compare_A_outside.csv", index=False)
    table("A: artificial medians outside the real p10..p90 range, before/after", frame)
    table(
        "A: unchanged artificial generator audit (maximum absolute old/new difference)",
        pd.DataFrame(
            [
                dict(
                    metric=m,
                    max_abs_difference=float(
                        np.max(np.abs(artificial[m + "_new"] - artificial[m + "_old"]))
                    ),
                )
                for m in STAT_COLS
            ]
        ),
    )


def offline_tests(frame, family, metrics):
    rows = []
    for debris, g in frame.groupby("debris"):
        for metric in metrics:
            col = (
                "energy_kj"
                if metric == "energy_vs_A_pct"
                else ("steep_len" if metric == "steep_exposed_pct" else metric)
            )
            pivot = g.pivot(index=KEY, columns="planner", values=col)[
                ["TA*-S exact", "A*"]
            ]
            success = g.pivot(index=KEY, columns="planner", values="success")[
                ["TA*-S exact", "A*"]
            ].all(axis=1)
            values = pivot.loc[success].dropna()
            if not len(values):
                raise ValueError("no successful paired offline outcomes")
            if metric == "energy_vs_A_pct":
                values = values.copy()
                values["TA*-S exact"] = 100 * (values["TA*-S exact"] / values["A*"] - 1)
                values["A*"] = 0.0
            elif metric == "steep_exposed_pct":
                values = 100 * (values > 0).astype(float)
            pv, effect, delta = paired_test(values["TA*-S exact"], values["A*"])
            center = "mean_percent" if metric == "steep_exposed_pct" else "median"
            rows.append(
                dict(
                    family=family,
                    debris=debris,
                    metric=metric,
                    n=len(values),
                    center=center,
                    A=(
                        values["A*"].mean()
                        if center == "mean_percent"
                        else values["A*"].median()
                    ),
                    exact=(
                        values["TA*-S exact"].mean()
                        if center == "mean_percent"
                        else values["TA*-S exact"].median()
                    ),
                    delta_median=delta,
                    p=pv,
                    r=effect,
                )
            )
    for row, adj in zip(rows, holm([r["p"] for r in rows])):
        row["p_holm"] = adj
        row["significant"] = bool(adj < 0.05)
        row["direction"] = direction(row["r"])
    return pd.DataFrame(rows)


def compare_b(old, new, output):
    a, b = read(old, "offline.csv"), read(new, "offline.csv")
    aligned = paired(a, b, KEY + ["planner"])
    audit = aligned[
        KEY
        + [
            "planner",
            "success_old",
            "success_new",
            "used_seed_old",
            "used_seed_new",
            "redraws_old",
            "redraws_new",
            "crop_origin_old",
            "crop_origin_new",
        ]
    ].copy()
    audit["same_seed_stream"] = audit.used_seed_old == audit.used_seed_new
    audit["same_crop"] = audit.crop_origin_old == audit.crop_origin_new
    audit.to_csv(output / "compare_scenario_alignment.csv", index=False)
    table(
        "B: nominal identity pairing audit; endpoints can change with terrain masks",
        audit.groupby("debris")
        .agg(
            rows=("planner", "size"),
            same_seed_stream=("same_seed_stream", "sum"),
            same_crop=("same_crop", "sum"),
            old_success=("success_old", "sum"),
            new_success=("success_new", "sum"),
        )
        .reset_index(),
    )
    changes = []
    for family, metrics in [
        ("original009_10", ORIGINAL_METRICS),
        ("requested_12", REQUESTED_METRICS),
    ]:
        x, y = offline_tests(a, family, metrics), offline_tests(b, family, metrics)
        merged = paired(x, y, ["family", "debris", "metric", "center"])
        merged["significance_changed"] = (
            merged.significant_old != merged.significant_new
        )
        merged["direction_changed"] = merged.direction_old != merged.direction_new
        changes.append(merged[merged.significance_changed | merged.direction_changed])
        merged.to_csv(output / ("compare_B_" + family + ".csv"), index=False)
        table(
            "B: "
            + family
            + "; paired two-sided Wilcoxon, Holm within each dataset/family",
            merged,
        )
    changed = pd.concat(changes, ignore_index=True)
    changed.to_csv(output / "compare_B_conclusion_changes.csv", index=False)
    table(
        "B: changed significance or rank direction (non-significant direction is descriptive only)",
        changed,
    )
    # The original family is exactly task 009's ten tests, without adding outcomes.
    stored = pd.read_csv(old / "offline_tests.csv")
    reference = offline_tests(a, "original009_10", ORIGINAL_METRICS)
    audit = stored.merge(
        reference,
        on=["debris", "metric"],
        suffixes=("_stored", "_recomputed"),
        validate="one_to_one",
    )
    verification = pd.DataFrame(
        [
            dict(
                statistic=k,
                max_abs_difference=float(
                    np.max(np.abs(audit[k + "_stored"] - audit[k + "_recomputed"]))
                ),
            )
            for k in ["p", "r", "p_holm"]
        ]
    )
    verification.to_csv(output / "compare_B_original_test_audit.csv", index=False)
    table("B: reproduce stored task-009 tests from original raw CSV", verification)


def compare_c(old, new, output):
    data = paired(read(old, "online.csv"), read(new, "online.csv"), KEY + ["variant"])
    rows = []
    for (debris, size, variant), g in data.groupby(["debris", "side_m", "variant"]):
        ok = g.success_old & g.success_new
        x, y = g.loc[g.success_old, "dJ_old"], g.loc[g.success_new, "dJ_new"]
        row = dict(
            debris=debris,
            side_m=size,
            variant=variant,
            n=len(g),
            paired_success=int(ok.sum()),
            old_success=int(g.success_old.sum()),
            new_success=int(g.success_new.sum()),
            old_median=x.median(),
            old_p90=x.quantile(0.9),
            old_max=x.max(),
            new_median=y.median(),
            new_p90=y.quantile(0.9),
            new_max=y.max(),
            paired_delta_median=(g.loc[ok, "dJ_new"] - g.loc[ok, "dJ_old"]).median(),
            old_touching=int((g.lethal_cells_old.fillna(0) > 0).sum()),
            new_touching=int((g.lethal_cells_new.fillna(0) > 0).sum()),
            old_contact_audited=int(g.lethal_cells_old.notna().sum()),
            new_contact_audited=int(g.lethal_cells_new.notna().sum()),
        )
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "compare_C_online.csv", index=False)
    table("C: dJ [%] paired on patch/size/seed/debris/variant; bad tail=p90", frame)
    actual = frame[~frame.variant.str.startswith("oracle")]
    table(
        "C: contact runs, replanning methods only (oracles excluded)",
        actual.groupby("debris")[
            [
                "old_touching",
                "new_touching",
                "old_contact_audited",
                "new_contact_audited",
                "old_success",
                "new_success",
            ]
        ]
        .sum()
        .reset_index(),
    )


def tour_effects(frame):
    euclid = frame[frame.method == "euclid"]
    directed = frame[frame.method == "terrain dir"]
    values = paired(euclid, directed, KEY + ["n_goals"])
    success = values.success_old & values.success_new
    rows = []
    for metric in ("cost_dir", "energy_kj"):
        g = values.copy()
        g["metric"] = metric
        g["effect_pct"] = np.where(
            success, 100 * (g[metric + "_new"] / g[metric + "_old"] - 1), np.nan
        )
        rows.append(g[KEY + ["n_goals", "metric", "effect_pct"]])
    return pd.concat(rows, ignore_index=True)


def tour_distribution(data):
    rows = []
    for (debris, n, metric), g in data.groupby(["debris", "n_goals", "metric"]):
        valid = g[["effect_pct_old", "effect_pct_new"]].dropna()
        x, y = g.effect_pct_old.dropna(), g.effect_pct_new.dropna()
        rows.append(
            dict(
                debris=debris,
                n_goals=n,
                metric=metric,
                n=len(g),
                paired_success=len(valid),
                old_success=len(x),
                new_success=len(y),
                old_median=x.median(),
                old_p90=x.quantile(0.9),
                new_median=y.median(),
                new_p90=y.quantile(0.9),
                paired_delta_median=(
                    valid.effect_pct_new - valid.effect_pct_old
                ).median(),
            )
        )
    return pd.DataFrame(rows)


def compare_d(old, new, output):
    a, b = read(old, "tours.csv"), read(new, "tours.csv")
    identity = paired(a, b, KEY + ["n_goals", "method"])
    point_cases = identity.drop_duplicates(
        KEY + ["n_goals", "points_old", "points_new"]
    )
    if point_cases.duplicated(KEY + ["n_goals"]).any():
        raise ValueError("waypoints differ between methods within a scenario")
    point_audit = (
        point_cases.assign(same_points=point_cases.points_old == point_cases.points_new)
        .groupby(["debris", "n_goals"])
        .agg(cases=("method", "size"), same_waypoint_sets=("same_points", "sum"))
        .reset_index()
    )
    point_audit.to_csv(output / "compare_D_waypoint_alignment.csv", index=False)
    table(
        "D: nominal scenario pairing audit; sampled waypoints can differ with masks",
        point_audit,
    )
    data = paired(tour_effects(a), tour_effects(b), KEY + ["n_goals", "metric"])
    frame = tour_distribution(data)
    frame.to_csv(output / "compare_D_tours.csv", index=False)
    table("D: terrain dir / euclid - 1 [%]; lower is better, bad tail=p90", frame)
    # Also retain task 009's original denominator/sign for direct report comparison.
    excess = data.copy()
    for suffix, source in [("old", a), ("new", b)]:
        euclid = source[source.method == "euclid"].set_index(KEY + ["n_goals"])
        for metric, column in [("cost_dir", "cost_rel_pct"), ("energy_kj", "energy_rel_pct")]:
            take = excess.metric == metric
            keys = pd.MultiIndex.from_frame(excess.loc[take, KEY + ["n_goals"]])
            excess.loc[take, "effect_pct_" + suffix] = euclid.loc[keys, column].to_numpy()
    frame = tour_distribution(excess)
    frame.to_csv(output / "compare_D_euclid_excess.csv", index=False)
    table("D: task-009 euclid / terrain dir - 1 [%]; euclid excess, bad tail=p90", frame)
    tests = paired(
        pd.read_csv(old / "tour_tests.csv"),
        pd.read_csv(new / "tour_tests.csv"),
        ["debris", "n_goals", "comparison"],
    )
    tests["significance_changed"] = (tests.p_holm_old < 0.05) != (
        tests.p_holm_new < 0.05
    )
    tests.to_csv(output / "compare_D_original_tests.csv", index=False)
    table("D: original task-009 Holm-corrected tour tests, before/after", tests)


def main():
    parser = argparse.ArgumentParser(
        description="同じシナリオで公開グリッド版とLAS点群版の結果を対比較する"
    )
    parser.add_argument("--old", type=Path, default=RESULTS / "real_beach")
    parser.add_argument("--new", type=Path, default=RESULTS / "real_beach_las")
    args = parser.parse_args()
    if args.old.resolve() == args.new.resolve():
        raise ValueError("old/new folders must differ")
    args.new.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    stream = io.StringIO()
    with redirect_stdout(stream):
        print(
            "Paired scenario identities; fixed parameters, no calibration. Old=0.1m source grid; new=LAS Ground."
        )
        print(
            "B original009_10: five outcomes x debris, unchanged family. B requested_12: six requested outcomes x debris, separate supplementary family."
        )
        compare_a(args.old, args.new, args.new)
        compare_b(args.old, args.new, args.new)
        compare_c(args.old, args.new, args.new)
        compare_d(args.old, args.new, args.new)
        times = []
        for label, folder in [("old", args.old), ("new", args.new)]:
            runtime = json.loads((folder / "runtime.json").read_text())
            times.extend(
                dict(
                    dataset=label,
                    phase=phase,
                    wall_s=value,
                    workers=runtime["workers"],
                    resume=runtime["resume"],
                )
                for phase, value in runtime["phase_wall_s"].items()
            )
            times.append(
                dict(
                    dataset=label,
                    phase="total",
                    wall_s=runtime["total_wall_s"],
                    workers=runtime["workers"],
                    resume=runtime["resume"],
                )
            )
        table(
            "Measured experiment wall times [s]; hardware/load/workers differ, not a speed comparison",
            pd.DataFrame(times),
        )
        print(
            "Directions use the sign of matched-pairs rank-biserial r; a zero paired median alone is not interpreted as equality."
        )
        print(
            "Nominal scenario pairs share name/size/seed/debris; masks, retry/crop choices and sampled endpoints/waypoints can differ. This is the prescribed rerun, not fixed-coordinate causal isolation."
        )
    log = stream.getvalue()
    (args.new / "compare_log.txt").write_text(log)
    print(log, end="")
    (args.new / "compare_runtime.json").write_text(
        json.dumps(dict(wall_time_s=time.perf_counter() - start), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
