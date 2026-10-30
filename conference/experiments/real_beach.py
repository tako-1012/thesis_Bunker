#!/usr/bin/env python3
"""Read-only real ALB beach comparisons with exact safety audits and checkpointed Pool jobs."""
import argparse
import hashlib
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapp.real_beach import list_patches, load_patch, fill_nodata, build_real, DATA
from tapp.config import DEFAULT_W, RESOLUTION, Robot
from tapp.traversability import TraversabilityMap
from tapp.beach_scenario import build_beach
from tapp.natural_terrain import spectrum_slope
from tapp.exact_planners import run_planner_exact
from tapp.scenario import run_planner
from tapp.collision import path_lethal_cells
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.tour import (
    sample_waypoints,
    cost_matrix,
    euclid_matrix,
    solve_tour,
    tour_legs,
)
from tapp.directional import segment_cost_dir
from tapp.metrics import evaluate
from experiments.beach_terrain import VARIANTS, ORDER, metrics
from experiments.multi_goal_tour import join_legs
from experiments.analyze import paired_test, holm

OUT = Path(__file__).resolve().parent.parent / "results" / "real_beach"
DATASET = "shizuoka_beach"
CACHE = None
KEY = ["kind", "side_m", "seed", "debris"]
METHODS = ["euclid", "terrain sym", "terrain dir"]
PLANNERS = ["A*", "A*-HC", "TA*", "TA*-S", "TA*-S exact"]
KAPPA = 1 / Robot().rolling_coeff
STAT_COLS = [
    "slope50",
    "slope90",
    "slope99",
    "steep_land",
    "foreshore_gradient",
    "land_width_m",
    "rough",
    "spectrum",
    "lethal_land",
]


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def job_key(job):
    return "_".join(str(v) for v in job)


def cached(stage, job):
    return CACHE / (stage + "_" + job_key(job) + ".json")


def statistics(raw, tm):
    valid = np.isfinite(raw)
    land = valid & (raw >= 0)
    front = land & (raw <= 2)
    widths = []
    for x in range(len(raw)):
        ground = np.flatnonzero(land[x])
        if not len(ground):
            continue
        shore = ground[0]
        free = np.flatnonzero(land[x] & ~tm.lethal[x])
        free = free[free >= shore]
        if not len(free):
            widths.append(0.0)
            continue
        end = np.flatnonzero(
            (tm.lethal[x] | ~valid[x]) & (np.arange(len(raw)) > free[0])
        )
        widths.append(((end[0] if len(end) else len(raw)) - shore) * RESOLUTION)
    q = np.percentile(tm.slope[land], [50, 90, 99])
    return dict(
        slope50=q[0],
        slope90=q[1],
        slope99=q[2],
        steep_land=np.mean(tm.slope[land] > 25),
        foreshore_gradient=np.median(tm.gy[front]) if front.any() else np.nan,
        land_width_m=np.median(widths),
        rough=np.median(tm.rough[land]),
        spectrum=spectrum_slope(tm.elev),
        lethal_land=tm.lethal[land].mean(),
        nodata_fraction=(~valid).mean(),
        water_fraction=(valid & (raw < 0)).mean(),
    )


def run_a(job):
    source, name, seed = job
    t = time.perf_counter()
    if source == "real":
        raw = load_patch(name, dataset=DATASET)
        tm = TraversabilityMap(fill_nodata(raw), ~np.isfinite(raw) | (raw < 0))
        split = next(
            r["split"] for r in list_patches(dataset=DATASET) if r["name"] == name
        )
    else:
        sc = build_beach(name, 200, seed)
        tm = sc["tmap"]
        raw = tm.elev
        split = "validation"
    values = statistics(raw, tm)
    return dict(
        source=source,
        kind=name,
        split=split,
        side_m=200,
        seed=seed,
        elapsed_s=time.perf_counter() - t,
        **values,
    )


def scenario(job):
    name, size, debris = job
    return build_real(name, size, 0, debris=debris, dataset=DATASET)


def base_row(job, sc=None):
    name, size, debris = job
    row = dict(kind=name, side_m=size, seed=0, debris=bool(debris))
    if sc is not None:
        row.update(
            used_seed=sc["used_seed"],
            redraws=sc["redraws"],
            crop_origin=json.dumps(sc["crop_origin_cells"]),
        )
    return row


def run_b(job):
    t = time.perf_counter()
    base = base_row(job)
    try:
        sc = scenario(job)
    except RuntimeError as exc:
        return dict(
            rows=[
                dict(base, planner=p, success=False, reason=str(exc)) for p in PLANNERS
            ],
            paths={},
            elapsed_s=time.perf_counter() - t,
        )
    base = base_row(job, sc)
    tm = sc["tmap"]
    rows = []
    paths = {}
    for name in PLANNERS:
        r = (
            run_planner_exact("TA*-S", sc, w=DEFAULT_W)
            if name == "TA*-S exact"
            else run_planner(name, sc, w=DEFAULT_W)
        )
        row = dict(
            base,
            planner=name,
            success=r["success"],
            reason="" if r["success"] else "no_path",
            time=r["time"],
        )
        if r["success"]:
            row.update(metrics(r["path"], tm))
            row["lethal_cells"] = len(path_lethal_cells(r["path"], tm.lethal))
            paths[name] = r["path"]
        rows.append(row)
    return dict(rows=rows, paths=paths, elapsed_s=time.perf_counter() - t)


def run_c(job):
    t = time.perf_counter()
    base = base_row(job)
    b = json.loads(cached("B", job).read_text())
    refs = {r["planner"]: r for r in b["rows"]}
    if not refs["TA*-S exact"]["success"]:
        return dict(
            rows=[
                dict(base, variant=v, success=False, reason="oracle unavailable")
                for v in ORDER
            ],
            traces={},
            elapsed_s=time.perf_counter() - t,
        )
    sc = scenario(job)
    tm = sc["tmap"]
    base = base_row(job, sc)
    rows = []
    traces = {}
    for name, source in [("oracle A*", "A*"), ("oracle TA*-S", "TA*-S exact")]:
        row = dict(refs[source])
        row["variant"] = name
        row["n_plans"] = 1
        row["plan_time"] = row.pop("time", np.nan)
        rows.append(row)
        traces[name] = b["paths"].get(source)
    jo = refs["TA*-S exact"]["J"]
    for name, radius, cell in VARIANTS:
        r = run_online(
            tm,
            sc["start"],
            sc["goal"],
            planner="TA*-S",
            w=DEFAULT_W,
            exact_los=True,
            prior_lethal="soft",
            unknown_cost="adaptive",
            sense_radius_m=radius,
            prior_map=None if cell is None else coarse_prior(tm, cell),
        )
        row = dict(
            base,
            variant=name,
            success=r["success"],
            reason=r["reason"],
            n_plans=r["n_plans"],
            plan_time=r["plan_time"],
            lethal_cells=len(path_lethal_cells(r["traj"], tm.lethal)),
        )
        if r["success"]:
            row.update(metrics(r["traj"], tm))
        traces[name] = r["traj"]
        rows.append(row)
    for row in rows:
        if row["success"]:
            for target, col in [("dJ", "J"), ("dL", "length_xy"), ("dE", "energy_kj")]:
                row[target] = 100 * (row[col] / refs["TA*-S exact"][col] - 1)
            row["dE_A"] = (
                100 * (row["energy_kj"] / refs["A*"]["energy_kj"] - 1)
                if refs["A*"]["success"]
                else np.nan
            )
    return dict(rows=rows, traces=traces, elapsed_s=time.perf_counter() - t)


def run_d(job):
    t = time.perf_counter()
    base = base_row(job)
    try:
        sc = scenario(job)
    except RuntimeError as exc:
        return dict(
            rows=[
                dict(base, n_goals=n, method=m, success=False, reason=str(exc))
                for n in (5, 8, 12)
                for m in METHODS
            ],
            pairs=[],
            elapsed_s=time.perf_counter() - t,
        )
    tm = sc["tmap"]
    base = base_row(job, sc)
    try:
        points = [sc["start"]] + sample_waypoints(
            sc, 12, np.random.SeedSequence([0, 3000, 200, sc["patch_index"]])
        )
    except ValueError as exc:
        return dict(
            rows=[
                dict(base, n_goals=n, method=m, success=False, reason=str(exc))
                for n in (5, 8, 12)
                for m in METHODS
            ],
            pairs=[],
            elapsed_s=time.perf_counter() - t,
        )
    points = [tuple(map(int, p)) for p in points]
    sym = cost_matrix(sc, points, kappa=0)
    directed = cost_matrix(sc, points, kappa=KAPPA)
    ts = time.perf_counter()
    euclid = euclid_matrix(points)
    euclid_time = time.perf_counter() - ts
    pairs = []
    for i in range(13):
        for j in range(i + 1, 13):
            a, b = directed["C"][i, j], directed["C"][j, i]
            u, v = sym["C"][i, j], sym["C"][j, i]
            pairs.append(
                dict(
                    base,
                    i=i,
                    j=j,
                    C_ij=a,
                    C_ji=b,
                    asymmetry=abs(a - b) / (a + b),
                    zero_kappa_asymmetry=abs(u - v) / (u + v),
                )
            )
    rows = []
    examples = {}
    mult = 1 + DEFAULT_W * tm.cost
    for n in (5, 8, 12):
        batch = []
        for name, C, mt in [
            ("euclid", euclid, euclid_time),
            ("terrain sym", sym["C"], sym["time"]),
            ("terrain dir", directed["C"], directed["time"]),
        ]:
            ts = time.perf_counter()
            order, objective = solve_tour(C[: n + 1, : n + 1])
            solve_time = time.perf_counter() - ts
            row = dict(
                base,
                n_goals=n,
                method=name,
                success=bool(order),
                reason="" if order else "unreachable tour",
                order=json.dumps(order),
                points=json.dumps(points[: n + 1]),
                matrix_time_s=mt,
                solve_time_s=solve_time,
            )
            if order:
                path = join_legs(order, directed["paths"])
                row.update(evaluate(path, tm))
                row["cost_dir"] = sum(
                    segment_cost_dir(mult, tm.elev, a, b, KAPPA)
                    for a, b in zip(path, path[1:])
                )
                row["lethal_cells"] = len(path_lethal_cells(path, tm.lethal))
                if n == 12 and sc["patch_index"] == 0:
                    examples[name] = path
            batch.append(row)
        ref = batch[-1]
        for row in batch:
            if row["success"] and ref["success"]:
                row["cost_rel_pct"] = 100 * (row["cost_dir"] / ref["cost_dir"] - 1)
                row["energy_rel_pct"] = 100 * (row["energy_kj"] / ref["energy_kj"] - 1)
        rows.extend(batch)
    return dict(
        rows=rows,
        pairs=pairs,
        examples=examples,
        points=points,
        elapsed_s=time.perf_counter() - t,
        sym_matrix_s=sym["time"],
        dir_matrix_s=directed["time"],
    )


def dispatch(args):
    stage, job, resume = args
    path = cached(stage, job)
    if resume and path.exists():
        return json.loads(path.read_text())
    result = {"A": run_a, "B": run_b, "C": run_c, "D": run_d}[stage](job)
    path.write_text(json.dumps(result, default=plain) + "\n")
    return result


def pool_phase(pool, stage, jobs, resume):
    start = time.perf_counter()
    results = []
    for i, r in enumerate(
        pool.imap(dispatch, [(stage, job, resume) for job in jobs]), 1
    ):
        results.append(r)
        print(
            f"{stage}: completed {i}/{len(jobs)} ({time.perf_counter()-start:.1f}s)",
            file=sys.stderr,
            flush=True,
        )
    return results, time.perf_counter() - start


def table(title, frame):
    print("\n" + title)
    print(frame.to_string(index=False, float_format=lambda x: f"{x:.6g}"))


def offline_summary(df):
    df = df.copy()
    ref = df[df.planner == "A*"].set_index(KEY).energy_kj
    df = df.join(ref.rename("energy_A"), on=KEY)
    df["energy_rel"] = 100 * (df.energy_kj / df.energy_A - 1)
    return (
        df.groupby(["debris", "planner"])
        .agg(
            success=("success", "mean"),
            exposed=("steep_len", lambda x: (x > 0).mean()),
            steep_len=("steep_len", "median"),
            cost=("mean_cost", "median"),
            climb=("climb", "median"),
            energy_vs_A_pct=("energy_rel", "median"),
            max_roll=("max_roll", "median"),
            p95_roll=("p95_roll", "median"),
            roll_frac=("roll_frac", "median"),
            length=("length_xy", "median"),
            time=("time", "median"),
            touching=("lethal_cells", lambda x: (x > 0).sum()),
        )
        .reset_index()
    )


def online_summary(df):
    return (
        df.groupby(["debris", "variant"])
        .agg(
            success=("success", "mean"),
            exposed=("steep_len", lambda x: (x > 0).mean()),
            dJ=("dJ", "median"),
            dL=("dL", "median"),
            dE=("dE", "median"),
            dE_A=("dE_A", "median"),
            slope95=("p95_slope", "median"),
            plans=("n_plans", "median"),
            plan_time=("plan_time", "median"),
            touching=("lethal_cells", lambda x: (x > 0).sum()),
            dJ90=("dJ", lambda x: x.quantile(0.9)),
            dJmax=("dJ", "max"),
            dL90=("dL", lambda x: x.quantile(0.9)),
            dLmax=("dL", "max"),
        )
        .reset_index()
    )


def tour_summary(df):
    rows = []
    for (debris, n, method), d in df.groupby(["debris", "n_goals", "method"]):
        row = dict(debris=debris, n_goals=n, method=method, success=d.success.mean())
        for col in [
            "cost_rel_pct",
            "energy_rel_pct",
            "length_xy",
            "climb",
            "p95_roll",
            "steep_len",
        ]:
            row[col + "_median"] = d[col].median()
            row[col + "_p90"] = d[col].quantile(0.9)
        rows.append(row)
    return pd.DataFrame(rows)


def summary(runtime):
    a = pd.read_csv(OUT / "statistics.csv")
    b = pd.read_csv(OUT / "offline.csv")
    c = pd.read_csv(OUT / "online.csv")
    d = pd.read_csv(OUT / "tours.csv")
    pairs = pd.read_csv(OUT / "pair_costs.csv")
    orientation = []
    for patch in list_patches(dataset=DATASET):
        raw = load_patch(patch["name"], dataset=DATASET)
        counts = np.isfinite(raw).sum(axis=0)
        profile = np.divide(
            np.nansum(raw, axis=0), counts, out=np.full(400, np.nan), where=counts > 0
        )
        sea = float(profile[0])
        front = float(np.nanmax(profile[100:201]))
        if not (sea < 0 and front > 0):
            orientation.append(
                dict(
                    kind=patch["name"],
                    split=patch["split"],
                    sea_side_mean=sea,
                    front_profile_max=front,
                )
            )
    orientation = pd.DataFrame(
        orientation, columns=["kind", "split", "sea_side_mean", "front_profile_max"]
    )
    orientation.to_csv(OUT / "orientation_violations.csv", index=False)
    table(
        "A: supplied patches violating the requested mean-profile orientation (data unchanged)",
        orientation,
    )
    real = a[a.source == "real"]
    synthetic = a[a.source == "synthetic"]
    outside = []
    for kind, g in synthetic.groupby("kind"):
        for col in STAT_COLS:
            low, high = real[col].quantile([0.1, 0.9])
            value = g[col].median()
            if value < low or value > high:
                outside.append(
                    dict(
                        kind=kind,
                        metric="energy_vs_A_pct" if col == "energy_kj" else col,
                        synthetic_median=value,
                        real_p10=low,
                        real_p90=high,
                    )
                )
    pd.DataFrame(
        outside, columns=["kind", "metric", "synthetic_median", "real_p10", "real_p90"]
    ).to_csv(OUT / "artificial_outside.csv", index=False)
    table(
        "A: terrain statistics; medians over patches / artificial validation seeds",
        a.assign(group=np.where(a.source == "real", a.split, a.kind))
        .groupby(["source", "group"])[STAT_COLS]
        .median()
        .reset_index(),
    )
    table(
        "A: real-patch 10th/90th percentiles (all 60; descriptive, never used for tuning)",
        real[STAT_COLS].quantile([0.1, 0.9]).rename_axis("quantile").reset_index(),
    )
    table("A: artificial medians outside real 10..90% range", pd.DataFrame(outside))
    table("B: offline medians; energy only relative to A* [%]", offline_summary(b))
    tests = []
    for debris, group in b.groupby("debris"):
        for col in ["steep_len", "mean_cost", "climb", "energy_kj", "length_xy"]:
            p = group.pivot(index=KEY, columns="planner", values=col)[
                ["TA*-S exact", "A*"]
            ].dropna()
            if col == "energy_kj":
                p["TA*-S exact"] = 100 * (p["TA*-S exact"] / p["A*"] - 1)
                p["A*"] = 0.0
            pv, r, delta = paired_test(p["TA*-S exact"], p["A*"])
            tests.append(
                dict(
                    debris=debris,
                    metric="energy_vs_A_pct" if col == "energy_kj" else col,
                    n=len(p),
                    p=pv,
                    r=r,
                    delta=delta,
                )
            )
    for t, adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = adj
    table("B: paired two-sided Wilcoxon; Holm over ten tests", pd.DataFrame(tests))
    pd.DataFrame(tests).to_csv(OUT / "offline_tests.csv", index=False)
    table("B: failures", b[~b.success][KEY + ["planner", "reason"]])
    table(
        "C: online medians and tails; dJ/dL/dE relative to exact oracle [%]",
        online_summary(c),
    )
    for debris, g in c.groupby("debris"):
        table(
            f"C: per patch median dJ [%], debris={debris}",
            g.pivot_table(
                index="kind", columns="variant", values="dJ", aggfunc="median"
            ).reset_index(),
        )
    high = c[(c.dJ > 25) & ~c.variant.str.startswith("oracle")].sort_values(
        ["dJ"] + KEY + ["variant"], ascending=[False, True, True, True, True, True]
    )
    table(
        "C: all dJ > 25% trajectories (largest ten plotted)",
        high[KEY + ["variant", "dJ", "dL", "n_plans"]],
    )
    high.to_csv(OUT / "detours.csv", index=False)
    table("C: failures", c[~c.success][KEY + ["variant", "reason"]])
    table(
        "D: tour metrics; relative cost and energy vs terrain dir [%]", tour_summary(d)
    )
    changes = []
    tests = []
    costs = []
    for (debris, n), group in d[d.success].groupby(["debris", "n_goals"]):
        cp = group.pivot(index=KEY, columns="method", values="cost_dir").dropna()
        orders = group.pivot(index=KEY, columns="method", values="order").dropna()
        changes.append(
            dict(
                debris=debris,
                n_goals=n,
                euclid_vs_dir_pct=100 * (orders.euclid != orders["terrain dir"]).mean(),
                sym_vs_dir_pct=100
                * (orders["terrain sym"] != orders["terrain dir"]).mean(),
            )
        )
        costs.append(
            dict(
                debris=debris,
                n_goals=n,
                dir_vs_euclid_pct_median=np.median(
                    100 * (cp["terrain dir"] / cp.euclid - 1)
                ),
            )
        )
        for method in METHODS[:2]:
            p, r, delta = paired_test(cp[method], cp["terrain dir"])
            tests.append(
                dict(
                    debris=debris,
                    n_goals=n,
                    comparison=method + " vs terrain dir",
                    n=len(cp),
                    p=p,
                    r=r,
                    median_cost_difference=delta,
                )
            )
    patch_rows = []
    for key, group in d[d.success].groupby(KEY + ["n_goals"]):
        methods = group.set_index("method")
        if not set(METHODS).issubset(methods.index):
            continue
        row = dict(zip(KEY + ["n_goals"], key))
        row["dir_vs_euclid_pct"] = 100 * (
            methods.loc["terrain dir", "cost_dir"] / methods.loc["euclid", "cost_dir"]
            - 1
        )
        row["dir_vs_sym_pct"] = 100 * (
            methods.loc["terrain dir", "cost_dir"]
            / methods.loc["terrain sym", "cost_dir"]
            - 1
        )
        row["euclid_order_changed"] = (
            methods.loc["euclid", "order"] != methods.loc["terrain dir", "order"]
        )
        row["sym_order_changed"] = (
            methods.loc["terrain sym", "order"] != methods.loc["terrain dir", "order"]
        )
        patch_rows.append(row)
    patch_frame = pd.DataFrame(patch_rows)
    patch_frame.to_csv(OUT / "tour_patch_summary.csv", index=False)
    table(
        "D: per-patch directed cost relative to Euclidean ordering [%]",
        patch_frame.pivot(
            index=["kind", "n_goals"], columns="debris", values="dir_vs_euclid_pct"
        )
        .rename(columns={False: "clean_pct", True: "debris_pct"})
        .reset_index(),
    )
    patch_asym = (
        pairs.groupby(["kind", "debris"])
        .agg(
            median=("asymmetry", "median"), p90=("asymmetry", lambda x: x.quantile(0.9))
        )
        .reset_index()
    )
    patch_asym.to_csv(OUT / "patch_asymmetry.csv", index=False)
    table("D: per-patch asymmetry |Cij-Cji|/(Cij+Cji)", patch_asym)
    table("D: terrain dir relative to euclid ordering [%]", pd.DataFrame(costs))
    table("D: changed orders [%]", pd.DataFrame(changes))
    table(
        "D: pair-matrix asymmetry; zero-kappa audit included",
        pairs.groupby("debris")
        .agg(
            pairs=("asymmetry", "size"),
            median=("asymmetry", "median"),
            p90=("asymmetry", lambda x: x.quantile(0.9)),
            zero_kappa_median=("zero_kappa_asymmetry", "median"),
            zero_kappa_p90=("zero_kappa_asymmetry", lambda x: x.quantile(0.9)),
        )
        .reset_index(),
    )
    for t, adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = adj
    table(
        "D: paired two-sided Wilcoxon; Holm over all twelve comparisons",
        pd.DataFrame(tests),
    )
    pd.DataFrame(tests).to_csv(OUT / "tour_tests.csv", index=False)
    table(
        "D: matrix / Held-Karp time [s]; full 13-point matrices reused by all prefixes",
        d.groupby(["debris", "n_goals", "method"])
        .agg(
            matrix_median=("matrix_time_s", "median"),
            matrix_max=("matrix_time_s", "max"),
            solve_median=("solve_time_s", "median"),
            solve_max=("solve_time_s", "max"),
        )
        .reset_index(),
    )
    table("D: failures", d[~d.success][KEY + ["n_goals", "method", "reason"]])
    # Compare only matching sizes and the three artificial beach families from 007/008.
    old_b = pd.read_csv(OUT.parent / "beach_terrain" / "offline.csv")
    old_b = old_b[
        old_b.kind.str.startswith("beach") & old_b.side_m.isin([100, 200])
    ].assign(debris="artificial 007 (includes debris)")
    old_c = pd.read_csv(OUT.parent / "beach_terrain" / "online_relative.csv")
    old_c = old_c[old_c.kind.str.startswith("beach") & (old_c.side_m == 100)].assign(
        debris="artificial 007 (100m, includes debris)"
    )
    old_d = pd.read_csv(OUT.parent / "multi_goal_tour" / "tours.csv")
    old_d = old_d[
        old_d.kind.str.startswith("beach")
        & (old_d.side_m == 200)
        & old_d.method.isin(METHODS)
    ].assign(debris="artificial 008 (200m, includes debris)", success=True)
    table(
        "Comparison B: artificial 007, matching 100/200m beach families",
        offline_summary(old_b),
    )
    table("Comparison C: artificial 007, 100m beach families", online_summary(old_c))
    table(
        "Comparison C: real 100m subset (200m is additional)",
        online_summary(c[c.side_m == 100]),
    )
    table(
        "C: real 200m subset (additional experiment)",
        online_summary(c[c.side_m == 200]),
    )
    table("Comparison D: artificial 008, 200m beach families", tour_summary(old_d))
    table(
        "Measured phase wall times [s]; includes cache reads only if --resume was requested",
        pd.DataFrame(
            [dict(phase=k, wall_time_s=v) for k, v in runtime["phase_wall_s"].items()]
        ),
    )
    print(
        f'Total wall time [s]: {runtime["total_wall_s"]:.6f}; workers={runtime["workers"]}; resume={runtime["resume"]}'
    )
    print(
        "Source: 静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB 地面の点群（Ground）"
        if DATASET == "shizuoka_beach_las"
        else "Source: 静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB グリッドデータ（0.5m）"
    )
    print("https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb")
    print(
        "ライセンス：CC BY 4.0 / ODbL。このフォルダのデータは、上のデータを加工して作成したものです。"
    )
    print(
        "Caveats: nearest-data fill affects spectra; zero-kappa greedy smoothing need not be symmetric; closed-tour endpoint elevation potentials cancel."
    )


def draw_paths(sc, paths, title, path, points=None):
    tm = sc["tmap"]
    fig, ax = plt.subplots(figsize=(7, 6))
    extent = [0, sc["side_m"], 0, sc["side_m"]]
    ax.imshow(tm.slope.T, origin="lower", extent=extent, cmap="YlOrBr", vmin=0, vmax=25)
    ax.imshow(
        np.ma.masked_where(~tm.lethal.T, tm.lethal.T),
        origin="lower",
        extent=extent,
        cmap="Greys",
        vmin=0,
        vmax=1,
        alpha=0.5,
    )
    ax.imshow(
        np.ma.masked_where(~sc["water"].T, sc["water"].T),
        origin="lower",
        extent=extent,
        cmap="Blues",
        vmin=0,
        vmax=1,
    )
    ax.imshow(
        np.ma.masked_where(~sc["nodata"].T, sc["nodata"].T),
        origin="lower",
        extent=extent,
        cmap="Purples",
        vmin=0,
        vmax=1,
    )
    for label, p in paths.items():
        if p is None:
            continue
        p = (np.asarray(p) + 0.5) * RESOLUTION
        ax.plot(p[:, 0], p[:, 1], lw=1.3, label=label)
    if points:
        for i, p in enumerate(points):
            ax.annotate(
                str(i),
                ((p[0] + 0.5) * RESOLUTION, (p[1] + 0.5) * RESOLUTION),
                fontsize=8,
            )
    ax.legend(fontsize=7)
    ax.set(title=title, xlabel="x alongshore [m]", ylabel="y inland [m]")
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def figures(c, d_results):
    high = (
        c[(c.dJ > 25) & ~c.variant.str.startswith("oracle")]
        .sort_values(
            ["dJ"] + KEY + ["variant"], ascending=[False, True, True, True, True, True]
        )
        .head(10)
    )
    for i, row in enumerate(high.itertuples(), 1):
        job = (row.kind, row.side_m, bool(row.debris))
        sc = scenario(job)
        data = json.loads(cached("C", job).read_text())
        draw_paths(
            sc,
            {
                "oracle TA*-S": data["traces"]["oracle TA*-S"],
                f"{row.variant}: dJ={row.dJ:.2f}%": data["traces"][row.variant],
            },
            f"{row.kind}, {row.side_m}m, debris={row.debris}",
            OUT / f"detour_{i:02d}.png",
        )
    for result in d_results:
        if result.get("examples"):
            row = result["rows"][0]
            job = (row["kind"], 200, row["debris"])
            sc = scenario(job)
            draw_paths(
                sc,
                {m: result["examples"][m] for m in ["euclid", "terrain dir"]},
                f'{row["kind"]}, 200m, 12 goals, debris={row["debris"]}',
                OUT / f'tour_example_debris_{int(row["debris"])}.png',
                result["points"],
            )


def configure_worker(dataset, cache):
    global DATASET, CACHE
    DATASET, CACHE = dataset, Path(cache)


def main():
    global CACHE, OUT, DATASET
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=min(5, os.cpu_count() or 1))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--dataset",
        choices=["shizuoka_beach", "shizuoka_beach_las"],
        default="shizuoka_beach",
    )
    args = parser.parse_args()
    DATASET = args.dataset
    if DATASET == "shizuoka_beach_las":
        OUT = OUT.parent / "real_beach_las"
    OUT.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(
        Path(__file__).read_bytes()
        + (Path(__file__).parent.parent / "tapp" / "real_beach.py").read_bytes()
    ).hexdigest()[:16]
    if DATASET != "shizuoka_beach":
        fingerprint = hashlib.sha256((fingerprint + DATASET).encode()).hexdigest()[:16]
    CACHE = Path("/tmp/real-beach-cache") / fingerprint
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.summary_only:
        runtime = json.loads((OUT / "runtime.json").read_text())
    else:
        start = time.perf_counter()
        phases = {}
        rows = list_patches(dataset=DATASET)
        names = [r["name"] for r in rows if r["split"] == "test"]
        jobs = [
            (name, size, debris)
            for name in names
            for size in (100, 200)
            for debris in (False, True)
        ]
        with Pool(
            args.workers, initializer=configure_worker, initargs=(DATASET, str(CACHE))
        ) as pool:
            a, phases["A"] = pool_phase(
                pool,
                "A",
                [("real", r["name"], 0) for r in rows]
                + [
                    ("synthetic", k, sd)
                    for k in ["beach_gentle", "beach_steep", "beach_scarp"]
                    for sd in range(100, 105)
                ],
                args.resume,
            )
            pd.DataFrame(a).to_csv(OUT / "statistics.csv", index=False)
            b, phases["B"] = pool_phase(pool, "B", jobs, args.resume)
            pd.DataFrame([r for item in b for r in item["rows"]]).to_csv(
                OUT / "offline.csv", index=False
            )
            c, phases["C"] = pool_phase(pool, "C", jobs, args.resume)
            cf = pd.DataFrame([r for item in c for r in item["rows"]])
            cf.to_csv(OUT / "online.csv", index=False)
            d, phases["D"] = pool_phase(
                pool, "D", [j for j in jobs if j[1] == 200], args.resume
            )
            pd.DataFrame([r for item in d for r in item["rows"]]).to_csv(
                OUT / "tours.csv", index=False
            )
            pd.DataFrame([r for item in d for r in item["pairs"]]).to_csv(
                OUT / "pair_costs.csv", index=False
            )
        tf = time.perf_counter()
        figures(cf, d)
        phases["figures"] = time.perf_counter() - tf
        runtime = dict(
            phase_wall_s=phases,
            total_wall_s=time.perf_counter() - start,
            workers=args.workers,
            resume=args.resume,
            cache_fingerprint=fingerprint,
            per_job_elapsed_sum_s={
                key: sum(item["elapsed_s"] for item in value)
                for key, value in [("A", a), ("B", b), ("C", c), ("D", d)]
            },
        )
        (OUT / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
    output = io.StringIO()
    with redirect_stdout(output):
        summary(runtime)
    log = output.getvalue()
    (OUT / "real_beach_log.txt").write_text(log)
    print(log, end="")


if __name__ == "__main__":
    main()
