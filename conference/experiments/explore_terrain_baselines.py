#!/usr/bin/env python3
"""Exploratory comparison with terrain-aware planners (NOT part of the paper).

Same 120 test scenarios, weights and hard constraints as the main experiment.
Writes results/explore/terrain_baselines.csv and prints a summary with paired
Wilcoxon tests (Holm-corrected) of TA*-S against every other planner.

Usage (from conference/):  python3 experiments/explore_terrain_baselines.py [--summary-only]
"""
import csv
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from tapp import terrain                                                        # noqa: E402
from tapp.config import DEFAULT_W                                               # noqa: E402
from tapp.metrics import evaluate                                               # noqa: E402
from tapp.scenario import build, run_planner                                    # noqa: E402
from tapp.terrain_baselines import energy_astar, surface_astar, terrain_theta  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "explore")
SIZES = (50, 100, 200)
SEEDS = range(10)
PLANNERS = ("A*", "A*-HC", "TA*", "TA*-S", "Energy-A*", "Surface-A*", "Terrain-Theta*")
KEY = ["kind", "side_m", "seed"]


def run(args):
    kind, side, seed = args
    sc = build(kind, side, seed)
    tm = sc["tmap"]
    s, g = sc["start"], sc["goal"]
    rows = []
    for p in PLANNERS:
        if p == "Energy-A*":
            r = energy_astar(tm, s, g)
        elif p == "Surface-A*":
            r = surface_astar(tm, s, g)
        elif p == "Terrain-Theta*":
            r = terrain_theta(tm.lethal, 1.0 + DEFAULT_W * tm.cost, s, g)
        else:
            r = run_planner(p, sc, w=DEFAULT_W)
        row = {"kind": kind, "side_m": side, "seed": seed, "planner": p,
               "success": r["success"], "time": r["time"], "expansions": r["expansions"]}
        if r["success"]:
            row.update(evaluate(r["path"], tm))
        rows.append(row)
    return rows


def summary():
    from analyze import holm, paired_test
    d = pd.read_csv(os.path.join(OUT, "terrain_baselines.csv"))
    ref = d[d.planner == "A*"].set_index(KEY)
    d = d.join(ref[["length_xy", "energy_kj"]].rename(columns=lambda c: c + "_A"), on=KEY)
    d["dL"] = 100 * (d.length_xy / d.length_xy_A - 1)
    d["dE"] = 100 * (d.energy_kj / d.energy_kj_A - 1)
    d["rough_mm"] = 1000 * d.p95_rough
    print("== medians (test split, 120 scenarios) ==")
    agg = d.groupby("planner").agg(succ=("success", "mean"), dL=("dL", "median"), dE=("dE", "median"),
                                   climb=("climb", "median"), slope95=("p95_slope", "median"),
                                   maxslope=("max_slope", "median"), rough95=("rough_mm", "median"),
                                   cost=("mean_cost", "median"), maxroll=("max_roll", "median"),
                                   time=("time", "median"), time_max=("time", "max"))
    print(agg.reindex(PLANNERS).round(3).to_string())
    piv = d.pivot_table(index=KEY, columns="planner",
                        values=["energy_kj", "p95_slope", "rough_mm", "mean_cost", "length_xy", "climb", "time"])
    tests = []
    for other in ("Energy-A*", "Surface-A*", "Terrain-Theta*", "TA*"):
        for m in ("energy_kj", "climb", "p95_slope", "rough_mm", "mean_cost", "length_xy", "time"):
            sub = piv[m][["TA*-S", other]].dropna()
            p, r, dm = paired_test(sub["TA*-S"], sub[other])
            tests.append((other, m, p, r, dm))
    adj = holm([t[2] for t in tests])
    print("\n== paired tests: TA*-S minus other (median diff), rank-biserial r, Holm p ==")
    for (o, m, p, r, dm), pa in zip(tests, adj):
        print(f"vs {o:15s} {m:10s} d={dm:+9.3f}  r={r:+.2f}  p={pa:.2g}")
    print("\n== per terrain family: median energy change / slope95 ==")
    print(d.pivot_table(index="kind", columns="planner", values="dE", aggfunc="median")[list(PLANNERS)].round(1).to_string())
    print(d.pivot_table(index="kind", columns="planner", values="p95_slope", aggfunc="median")[list(PLANNERS)].round(1).to_string())
    print("\n== time by map size (median s) ==")
    print(d.pivot_table(index="side_m", columns="planner", values="time", aggfunc="median")[list(PLANNERS)].round(3).to_string())


def main():
    if "--summary-only" not in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        t0 = time.time()
        tasks = [(k, s, sd) for k in terrain.TERRAIN_TYPES for s in SIZES for sd in SEEDS]
        tasks.sort(key=lambda t: -t[1])          # big maps first for load balance
        rows = []
        with Pool(os.cpu_count()) as pool:
            for i, rs in enumerate(pool.imap_unordered(run, tasks), 1):
                rows.extend(rs)
                if i % 20 == 0:
                    print(f"{i}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
        keys = sorted({k for r in rows for k in r})
        with open(os.path.join(OUT, "terrain_baselines.csv"), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=keys)
            wr.writeheader()
            wr.writerows(rows)
        print(f"done in {time.time() - t0:.0f}s")
    summary()


if __name__ == "__main__":
    main()
