#!/usr/bin/env python3
"""E5: maps with NO feasible path (steep wall across the map, no pass).

The main benchmark only keeps solvable maps, so every planner reaches 100 %
success there. This experiment checks the other side: a correct planner must
report failure, and a terrain-unaware planner's "success" is unsafe.

Usage (from conference/):  python3 experiments/run_infeasible.py
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp.metrics import evaluate                                  # noqa: E402
from tapp.scenario import PLANNERS, build_infeasible, run_planner  # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
W = 16.0


def main():
    rows = []
    for side in (50, 100, 200):
        for seed in range(10):
            sc = build_infeasible(side, seed)
            for p in PLANNERS:
                r = run_planner(p, sc, w=W)
                row = {"side_m": side, "seed": seed, "planner": p, "returned_path": r["success"],
                       "time": r["time"], "expansions": r["expansions"],
                       "steep_len": "", "max_slope": ""}
                if r["success"]:
                    m = evaluate(r["path"], sc["tmap"])
                    row.update(steep_len=m["steep_len"], max_slope=m["max_slope"])
                rows.append(row)
        print(f"side {side} done", flush=True)
    with open(os.path.join(RESULTS, "infeasible.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


if __name__ == "__main__":
    main()
