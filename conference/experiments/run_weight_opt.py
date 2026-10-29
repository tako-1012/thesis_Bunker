#!/usr/bin/env python3
"""E6: joint optimisation of the terrain weight w and the slope share alpha.

Grid search over (w, alpha) for TA*-S on BOTH splits. Selection must use the
validation rows only (see analyze_weights.py); test rows are for reporting.

Usage (from conference/):  python3 experiments/run_weight_opt.py
"""
import csv
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp import terrain                                   # noqa: E402
from tapp.metrics import evaluate                          # noqa: E402
from tapp.planners import astar, smooth_cost_aware         # noqa: E402
from tapp.scenario import build                            # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
SIZES = (50, 100, 200)
SPLITS = {"val": range(100, 105), "test": range(10)}
W_GRID = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)


def run(args):
    split, kind, side, seed = args
    sc = build(kind, side, seed)
    tm = sc["tmap"]
    s, g = sc["start"], sc["goal"]
    s_term = np.clip(tm.slope / tm.robot.max_slope_deg, 0, 1)
    r_term = np.clip(tm.rough / tm.robot.rough_sat, 0, 1)
    base = {"split": split, "kind": kind, "side_m": side, "seed": seed}
    rows = []
    ref = astar(tm.rock, s, g)                       # terrain-unaware reference
    rows.append(dict(base, planner="A*", w="", alpha="", time=ref["time"],
                     **evaluate(ref["path"], tm)))
    for a in ALPHAS:
        cost = a * s_term + (1.0 - a) * r_term
        for w in W_GRID:
            if w == 0.0 and a != ALPHAS[0]:
                continue                             # w=0 ignores alpha
            mult = 1.0 + w * cost
            r = astar(tm.lethal, s, g, mult)
            path, ts = smooth_cost_aware(r["path"], tm.lethal, mult)
            rows.append(dict(base, planner="TA*-S", w=w, alpha=a if w > 0 else "",
                             time=r["time"] + ts, **evaluate(path, tm)))
    return rows


def main():
    t0 = time.time()
    tasks = [(sp, k, s, sd) for sp, seeds in SPLITS.items()
             for k in terrain.TERRAIN_TYPES for s in SIZES for sd in seeds]
    rows = []
    with Pool(os.cpu_count()) as pool:
        for i, rs in enumerate(pool.imap_unordered(run, tasks), 1):
            rows.extend(rs)
            if i % 20 == 0:
                print(f"{i}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
    keys = list(rows[0])
    with open(os.path.join(RESULTS, "weight_opt.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
