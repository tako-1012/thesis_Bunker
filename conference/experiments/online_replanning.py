#!/usr/bin/env python3
"""Exploratory: online replanning with a limited sensing radius (NOT in the paper).

Usage (from conference/):  python3 experiments/online_replanning.py [--summary-only]
"""
import csv
import os
import sys
import time
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from tapp import terrain                         # noqa: E402
from tapp.config import DEFAULT_W                # noqa: E402
from tapp.metrics import evaluate                # noqa: E402
from tapp.online import run_online               # noqa: E402
from tapp.scenario import build, run_planner     # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "online")
SIZES = (50, 100)
SEEDS = range(10)
VARIANTS = [  # (name, planner, unknown_cost, sense_radius_m)
    ("online TA*-S optimistic", "TA*-S", 0.0, 15.0),
    ("online TA*-S prior=0.3", "TA*-S", 0.3, 15.0),
    ("online TA*-S adaptive", "TA*-S", "adaptive", 15.0),
    ("online A*-HC", "A*-HC", 0.0, 15.0),
    ("online TA*-S adaptive R=7.5", "TA*-S", "adaptive", 7.5),
    ("online TA*-S adaptive R=30", "TA*-S", "adaptive", 30.0),
    ("online TA*-S optimistic R=30", "TA*-S", 0.0, 30.0),
]
KEY = ["kind", "side_m", "seed"]


def run(args):
    kind, side, seed = args
    sc = build(kind, side, seed)
    tm = sc["tmap"]
    s, g = sc["start"], sc["goal"]
    base = {"kind": kind, "side_m": side, "seed": seed}
    rows = []
    for name in ("A*", "TA*-S"):
        r = run_planner(name, sc, w=DEFAULT_W)
        rows.append(dict(base, variant=f"oracle {name}", success=r["success"], plan_time=r["time"],
                         max_plan_time=r["time"], n_plans=1, **evaluate(r["path"], tm)))
    for name, planner, uc, R in VARIANTS:
        r = run_online(tm, s, g, planner=planner, w=DEFAULT_W, unknown_cost=uc, sense_radius_m=R)
        row = dict(base, variant=name, success=r["success"], reason=r["reason"], plan_time=r["plan_time"],
                   max_plan_time=r["max_plan_time"], n_plans=r["n_plans"])
        if r["success"]:
            row.update(evaluate(r["traj"], tm))
        rows.append(row)
    return rows


def summary():
    d = pd.read_csv(os.path.join(OUT, "online.csv"))
    ref = d[d.variant == "oracle TA*-S"].set_index(KEY)
    refA = d[d.variant == "oracle A*"].set_index(KEY)
    d = d.join(ref[["length_xy", "energy_kj", "mean_cost"]].rename(columns=lambda c: c + "_O"), on=KEY)
    d = d.join(refA[["energy_kj"]].rename(columns=lambda c: c + "_A"), on=KEY)
    d["dL_vs_oracle"] = 100 * (d.length_xy / d.length_xy_O - 1)
    d["dE_vs_oracle"] = 100 * (d.energy_kj / d.energy_kj_O - 1)
    d["dE_vs_A"] = 100 * (d.energy_kj / d.energy_kj_A - 1)
    order = ["oracle A*", "oracle TA*-S"] + [v[0] for v in VARIANTS]
    agg = d.groupby("variant").agg(
        succ=("success", "mean"), steep_exposed=("steep_len", lambda x: (x > 0).mean()),
        dL_oracle=("dL_vs_oracle", "median"), dE_oracle=("dE_vs_oracle", "median"),
        dE_A=("dE_vs_A", "median"), cost=("mean_cost", "median"), slope95=("p95_slope", "median"),
        plans=("n_plans", "median"), plan_time=("plan_time", "median"),
        max_plan=("max_plan_time", "max")).reindex(order)
    pd.set_option("display.width", 200)
    print(agg.round(3).to_string())
    print("\nper size (median dE vs oracle TA*-S [%]):")
    print(d.pivot_table(index="variant", columns="side_m", values="dE_vs_oracle", aggfunc="median").reindex(order).round(1).to_string())
    print("\nper terrain (median dL vs oracle [%]):")
    print(d.pivot_table(index="variant", columns="kind", values="dL_vs_oracle", aggfunc="median").reindex(order).round(1).to_string())
    print("\nfailures:", d[~d.success.astype(bool)].groupby(["variant", "reason"]).size().to_dict())


def main():
    if "--summary-only" not in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        t0 = time.time()
        tasks = [(k, s, sd) for k in terrain.TERRAIN_TYPES for s in SIZES for sd in SEEDS]
        tasks.sort(key=lambda t: -t[1])
        rows = []
        with Pool(os.cpu_count()) as pool:
            for i, rs in enumerate(pool.imap_unordered(run, tasks), 1):
                rows.extend(rs)
                if i % 10 == 0:
                    print(f"{i}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
        keys = sorted({k for r in rows for k in r})
        with open(os.path.join(OUT, "online.csv"), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=keys)
            wr.writeheader()
            wr.writerows(rows)
        print(f"done in {time.time() - t0:.0f}s")
    summary()


if __name__ == "__main__":
    main()
