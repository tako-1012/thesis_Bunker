#!/usr/bin/env python3
"""Compare A* and D* Lite online replanning with a fixed coarse terrain prior.

Usage (from conference/): python3 experiments/online_dstar.py [--summary-only]
Planning times exclude map assembly for both backends, but include all search
state construction/update, repair, path extraction and cost-aware smoothing.
"""
import argparse
import csv
import io
import json
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

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "online_dstar")
SIZES = (50, 100, 200)
VARIANTS = [  # (name, search backend, replan interval [m])
    ("A* prior5", "astar", 10.0),
    ("D*Lite prior5", "dstar_lite", 10.0),
    ("A* prior5 every-step", "astar", 1.0),
    ("D*Lite prior5 every-step", "dstar_lite", 1.0),
]
KEY = ["kind", "side_m", "seed"]
ORDER = ["oracle A*", "oracle TA*-S"] + [v[0] for v in VARIANTS]


def run(args):
    kind, side, seed = args
    sc = build(kind, side, seed)
    tm = sc["tmap"]
    base = {"kind": kind, "side_m": side, "seed": seed}
    rows = []
    for name in ("A*", "TA*-S"):
        r = run_planner(name, sc, w=DEFAULT_W)
        row = dict(base, variant=f"oracle {name}", success=r["success"],
                   reason="" if r["success"] else "no_path", plan_time=r["time"],
                   max_plan_time=r["time"], n_plans=1, plan_times=json.dumps([r["time"]]))
        if r["success"]:
            row.update(evaluate(r["path"], tm))
        rows.append(row)
    pm = coarse_prior(tm, 5.0)
    for name, search, interval in VARIANTS:
        if side == 200 and name == "A* prior5 every-step":
            continue
        r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                       sense_radius_m=15.0, prior_map=pm, prior_lethal="soft",
                       search=search, replan_every_m=interval, record_plan_times=True)
        row = dict(base, variant=name, success=r["success"], reason=r["reason"],
                   plan_time=sum(r["plan_times"]), max_plan_time=max(r["plan_times"]), n_plans=r["n_plans"],
                   plan_times=json.dumps(r["plan_times"], separators=(",", ":")))
        if r["success"]:
            row.update(evaluate(r["traj"], tm))
        rows.append(row)
    return rows


def summary():
    d = pd.read_csv(os.path.join(OUT, "online_dstar.csv"))
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
    calls = d[["variant", "side_m", "plan_times"]].copy()
    calls["call_time"] = calls.pop("plan_times").map(json.loads)
    calls = calls.explode("call_time")
    calls["call_time"] = calls.call_time.astype(float)
    by_size = calls.groupby(["variant", "side_m"]).agg(
        call_median_s=("call_time", "median"), call_max_s=("call_time", "max"))
    by_size = by_size.join(d.groupby(["variant", "side_m"]).plan_time.median().rename("total_median_s"))
    by_size = by_size.reindex(pd.MultiIndex.from_product([ORDER, SIZES], names=["variant", "side_m"]))
    paired = d[d.variant == "D*Lite prior5"].set_index(KEY).join(
        d[d.variant == "A* prior5"].set_index(KEY)[["length_xy", "success"]],
        rsuffix="_astar", validate="one_to_one")
    paired = paired[paired.success & paired.success_astar].copy()
    paired["dL_m"] = paired.length_xy - paired.length_xy_astar
    paired["abs_dL_m"] = paired.dL_m.abs()
    differences = paired.groupby("side_m").agg(
        pairs=("dL_m", "size"), dL_median_m=("dL_m", "median"),
        abs_dL_median_m=("abs_dL_m", "median"), abs_dL_max_m=("abs_dL_m", "max"))
    overall = pd.DataFrame([dict(pairs=len(paired), dL_median_m=paired.dL_m.median(),
                                abs_dL_median_m=paired.abs_dL_m.median(), abs_dL_max_m=paired.abs_dL_m.max())],
                           index=pd.Index(["all"], name="side_m"))
    output = io.StringIO()
    with redirect_stdout(output), pd.option_context("display.width", 200):
        print(agg.round(3).to_string())
        print("\nper size (planning times [s], median over individual calls):")
        print(by_size.round(6).to_string())
        print("\npaired path length difference (D*Lite prior5 - A* prior5 [m]):")
        print(pd.concat([overall, differences]).round(6).to_string())
        print("\nA* prior5 every-step is not run at 200 m (NaN above).")
        failures = d[~d.success.astype(bool)]
        print("\nfailures:", failures.groupby(["variant", "reason"]).size().to_dict())
        if not failures.empty:
            print(failures[KEY + ["variant", "reason"]].to_string(index=False))
    report = output.getvalue()
    print(report, end="")
    with open(os.path.join(OUT, "online_dstar_log.txt"), "w") as f:
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
        tasks = [(kind, side, seed) for kind in terrain.TERRAIN_TYPES for side in SIZES
                 for seed in range(5 if side == 200 else 10)]
        tasks.sort(key=lambda t: -t[1])
        rows = []
        with Pool(args.workers) as pool:
            for i, rs in enumerate(pool.imap_unordered(run, tasks), 1):
                rows.extend(rs)
                if i % 5 == 0:
                    print(f"{i}/{len(tasks)} ({time.time() - t0:.0f}s)", flush=True)
        rows.sort(key=lambda r: (terrain.TERRAIN_TYPES.index(r["kind"]), r["side_m"],
                                 r["seed"], ORDER.index(r["variant"])))
        keys = sorted({k for r in rows for k in r})
        with open(os.path.join(OUT, "online_dstar.csv"), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
            wr.writeheader()
            wr.writerows(rows)
        print(f"done in {time.time() - t0:.0f}s")
    summary()


if __name__ == "__main__":
    main()
