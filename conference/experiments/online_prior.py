#!/usr/bin/env python3
"""Online replanning with coarse elevation priors (exploratory, not in the paper).

Usage (from conference/): python3 experiments/online_prior.py [--summary-only]
"""
import argparse
import csv
import io
import os
import sys
import time
from contextlib import redirect_stdout
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp import terrain                         # noqa: E402
from tapp.config import DEFAULT_W                # noqa: E402
from tapp.metrics import evaluate                # noqa: E402
from tapp.online import run_online               # noqa: E402
from tapp.prior import coarse_prior              # noqa: E402
from tapp.scenario import build, run_planner     # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "online_prior")
SIZES = (50, 100)
SEEDS = range(10)
VARIANTS = [  # (name, coarse cell size [m] or None, lethal policy, noise std [m])
    ("online adaptive", None, "soft", 0.0),
    ("online prior5 soft", 5.0, "soft", 0.0),
    ("online prior5 hard", 5.0, "hard", 0.0),
    ("online prior10 soft", 10.0, "soft", 0.0),
    ("online prior5 soft noisy", 5.0, "soft", 0.5),
]
KEY = ["kind", "side_m", "seed"]
ORDER = ["oracle A*", "oracle TA*-S"] + [v[0] for v in VARIANTS]


def run(args):
    kind, side, seed = args
    sc = build(kind, side, seed)
    tm = sc["tmap"]
    s, g = sc["start"], sc["goal"]
    base = {"kind": kind, "side_m": side, "seed": seed}
    rows = []
    for name in ("A*", "TA*-S"):
        r = run_planner(name, sc, w=DEFAULT_W)
        row = dict(base, variant=f"oracle {name}", success=r["success"],
                   reason="" if r["success"] else "no_path", plan_time=r["time"],
                   max_plan_time=r["time"], n_plans=1)
        if r["success"]:
            row.update(evaluate(r["path"], tm))
        rows.append(row)
    for name, cell_m, mode, noise in VARIANTS:
        pm = None if cell_m is None else coarse_prior(tm, cell_m, z_noise_m=noise, seed=seed)
        r = run_online(tm, s, g, planner="TA*-S", w=DEFAULT_W, unknown_cost="adaptive",
                       sense_radius_m=15.0, prior_map=pm, prior_lethal=mode)
        row = dict(base, variant=name, success=r["success"], reason=r["reason"],
                   plan_time=r["plan_time"], max_plan_time=r["max_plan_time"], n_plans=r["n_plans"])
        if r["success"]:
            row.update(evaluate(r["traj"], tm))
        rows.append(row)
    return rows


def summary():
    d = pd.read_csv(os.path.join(OUT, "online_prior.csv"))
    ref = d[d.variant == "oracle TA*-S"].set_index(KEY)
    refA = d[d.variant == "oracle A*"].set_index(KEY)
    d = d.join(ref[["length_xy", "energy_kj", "mean_cost"]].rename(columns=lambda c: c + "_O"), on=KEY)
    d = d.join(refA[["energy_kj"]].rename(columns=lambda c: c + "_A"), on=KEY)
    d["dL_vs_oracle"] = 100 * (d.length_xy / d.length_xy_O - 1)
    d["dE_vs_oracle"] = 100 * (d.energy_kj / d.energy_kj_O - 1)
    d["dE_vs_A"] = 100 * (d.energy_kj / d.energy_kj_A - 1)
    agg = d.groupby("variant").agg(
        succ=("success", "mean"), steep_exposed=("steep_len", lambda x: (x > 0).mean()),
        dL_oracle=("dL_vs_oracle", "median"), dE_oracle=("dE_vs_oracle", "median"),
        dE_A=("dE_vs_A", "median"), cost=("mean_cost", "median"), slope95=("p95_slope", "median"),
        plans=("n_plans", "median"), plan_time=("plan_time", "median"),
        max_plan=("max_plan_time", "max")).reindex(ORDER)
    output = io.StringIO()
    with redirect_stdout(output), pd.option_context("display.width", 200):
        print(agg.round(3).to_string())
        print("\nper size (median dE vs oracle TA*-S [%]):")
        print(d.pivot_table(index="variant", columns="side_m", values="dE_vs_oracle", aggfunc="median").reindex(ORDER).round(1).to_string())
        print("\nper terrain (median dL vs oracle [%]):")
        print(d.pivot_table(index="variant", columns="kind", values="dL_vs_oracle", aggfunc="median").reindex(ORDER).round(1).to_string())
        failures = d[~d.success.astype(bool)]
        print("\nfailures:", failures.groupby(["variant", "reason"]).size().to_dict())
        if not failures.empty:
            print(failures[KEY + ["variant", "reason"]].to_string(index=False))
    report = output.getvalue()
    print(report, end="")
    with open(os.path.join(OUT, "online_prior_log.txt"), "w") as f:
        f.write(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if not args.summary_only:
        os.makedirs(OUT, exist_ok=True)
        t0 = time.time()
        tasks = [(k, s, sd) for k in terrain.TERRAIN_TYPES for s in SIZES for sd in SEEDS]
        tasks.sort(key=lambda t: -t[1])
        rows = []
        with Pool(args.workers) as pool:
            for i, rs in enumerate(pool.imap_unordered(run, tasks), 1):
                rows.extend(rs)
                if i % 10 == 0:
                    print(f"{i}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
        rows.sort(key=lambda r: (terrain.TERRAIN_TYPES.index(r["kind"]), r["side_m"],
                                 r["seed"], ORDER.index(r["variant"])))
        keys = sorted({k for r in rows for k in r})
        with open(os.path.join(OUT, "online_prior.csv"), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=keys)
            wr.writeheader()
            wr.writerows(rows)
        print(f"done in {time.time() - t0:.0f}s")
    summary()


if __name__ == "__main__":
    main()
