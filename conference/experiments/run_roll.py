#!/usr/bin/env python3
"""E7: roll-aware extension (TA*-R, TA*-S-R) on the TEST split.

Same scenarios and weights (w, alpha from results/selected_weights.json) as the
main experiment; only the slope term and constraints become heading-dependent.
The roll limit is an assumption, so it is swept.

Usage (from conference/):  python3 experiments/run_roll.py
"""
import csv
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp import terrain                                              # noqa: E402
from tapp.aniso import DirectionalCost, astar_roll, smooth_roll       # noqa: E402
from tapp.config import DEFAULT_W, Robot, check_selected_weights      # noqa: E402
from tapp.metrics import evaluate                                     # noqa: E402
from tapp.scenario import build, run_planner                          # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
SIZES = (50, 100, 200)
SEEDS = range(10)
ROLL_LIMITS = (10.0, 15.0, 20.0)
BASELINES = ("A*", "Theta*", "A*-HC", "TA*-S")


def run(args):
    kind, side, seed = args
    sc = build(kind, side, seed)
    tm = sc["tmap"]
    s, g = sc["start"], sc["goal"]
    base = {"kind": kind, "side_m": side, "seed": seed}
    rows = []
    paths = {}
    for p in BASELINES:
        r = run_planner(p, sc, w=DEFAULT_W)
        paths[p] = r
        for lim in ROLL_LIMITS:
            row = dict(base, planner=p, roll_limit=lim, success=r["success"], time=r["time"])
            if r["success"]:
                row.update(evaluate(r["path"], tm, roll_limit=lim))
            rows.append(row)
    for lim in ROLL_LIMITS:
        dc = DirectionalCost(tm, w=DEFAULT_W, roll_limit=lim)
        r = astar_roll(dc, s, g)
        row = dict(base, planner="TA*-R", roll_limit=lim, success=r["success"], time=r["time"])
        if r["success"]:
            row.update(evaluate(r["path"], tm, roll_limit=lim))
        rows.append(row)
        row = dict(base, planner="TA*-S-R", roll_limit=lim, success=r["success"], time=r["time"])
        if r["success"]:
            path, ts = smooth_roll(r["path"], dc)
            row.update(time=r["time"] + ts, **evaluate(path, tm, roll_limit=lim))
        rows.append(row)
    return rows


def main():
    check_selected_weights(os.path.join(RESULTS, "selected_weights.json"))
    t0 = time.time()
    tasks = [(k, s, sd) for k in terrain.TERRAIN_TYPES for s in SIZES for sd in SEEDS]
    rows = []
    with Pool(os.cpu_count()) as pool:
        for i, rs in enumerate(pool.imap_unordered(run, tasks), 1):
            rows.extend(rs)
            if i % 20 == 0:
                print(f"{i}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
    keys = sorted({k for r in rows for k in r})
    with open(os.path.join(RESULTS, "roll_results.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)
    print(f"done in {time.time() - t0:.0f}s; robot default roll limit {Robot().max_roll_deg}")


if __name__ == "__main__":
    main()
