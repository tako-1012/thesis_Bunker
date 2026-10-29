#!/usr/bin/env python3
"""Calibrate uncertain coarse terrain priors and select risk weight on validation.

Usage (from conference/): python3 experiments/risk_prior.py [--summary-only]
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
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experiments.analyze import holm, paired_test            # noqa: E402
from tapp.config import DEFAULT_W                           # noqa: E402
from tapp.metrics import evaluate                           # noqa: E402
from tapp.online import run_online                          # noqa: E402
from tapp.prior import coarse_prior                         # noqa: E402
from tapp.risk_prior import (calibrate, load_calibration,     # noqa: E402
                             risk_prior, save_calibration)
from tapp.scenario import build, run_planner                 # noqa: E402
from tapp.terrain import TERRAIN_TYPES                       # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "results" / "risk_prior"
CONDITIONS = ((15.0, 5.0), (10.0, 10.0), (10.0, 20.0), (5.0, 10.0), (5.0, 20.0))
LAMBDAS = (0.0, 0.25, 0.5, 1.0, 2.0)
VAL_SEEDS, TEST_SEEDS = range(100, 105), range(10)
SIZES = (50, 100)
COND = ["R_m", "cell_m"]
SCENARIO = ["kind", "side_m", "seed"]
KEY = COND + SCENARIO
ORDER = ["oracle A*", "oracle TA*-S", "coarse", "calibrated mean", "risk λ*"]
_CALIBRATIONS = None
_SELECTED = None


def _initialise(calibrations, selected):
    global _CALIBRATIONS, _SELECTED
    _CALIBRATIONS, _SELECTED = calibrations, selected


def _metrics(path, tm):
    m = evaluate(path, tm)
    return dict(m, J=m["length_xy"] * (1.0 + DEFAULT_W * m["mean_cost"]))


def _oracle(name, sc, base):
    r = run_planner(name, sc, w=DEFAULT_W)
    row = dict(base, variant=f"oracle {name}", success=r["success"],
               reason="" if r["success"] else "no_path", n_plans=1,
               plan_time=r["time"], max_plan_time=r["time"])
    if r["success"]:
        row.update(_metrics(r["path"], sc["tmap"]))
    return row


def _online(sc, base, name, pm, radius):
    r = run_online(sc["tmap"], sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                   sense_radius_m=radius, prior_map=pm, prior_lethal="soft", search="astar")
    row = dict(base, variant=name, success=r["success"], reason=r["reason"],
               n_plans=r["n_plans"], plan_time=r["plan_time"], max_plan_time=r["max_plan_time"])
    if r["success"]:
        row.update(_metrics(r["traj"], sc["tmap"]))
    return row


def run_validation(args):
    kind, side, seed, radius, cell = args
    sc = build(kind, side, seed)
    base = dict(kind=kind, side_m=side, seed=seed, R_m=radius, cell_m=cell)
    rows = [_oracle("TA*-S", sc, base)]
    for lam in LAMBDAS:
        pm = risk_prior(sc["tmap"], cell, _CALIBRATIONS[cell], lam)
        rows.append(dict(_online(sc, base, "risk", pm, radius), lam=lam))
    return rows


def run_test(args):
    kind, side, seed, radius, cell = args
    sc = build(kind, side, seed)
    base = dict(kind=kind, side_m=side, seed=seed, R_m=radius, cell_m=cell)
    rows = [_oracle(name, sc, base) for name in ("A*", "TA*-S")]
    tm = sc["tmap"]
    variants = [("coarse", coarse_prior(tm, cell)),
                ("calibrated mean", risk_prior(tm, cell, _CALIBRATIONS[cell], 0.0)),
                ("risk λ*", risk_prior(tm, cell, _CALIBRATIONS[cell], _SELECTED))]
    for name, pm in variants:
        rows.append(_online(sc, base, name, pm, radius))
    return rows


def _tasks(seeds):
    tasks = [(kind, side, seed, radius, cell) for kind in TERRAIN_TYPES for side in SIZES
             for seed in seeds for radius, cell in CONDITIONS]
    return sorted(tasks, key=lambda t: -t[1])


def _run_pool(worker, seeds, calibrations, selected, workers, filename, phase):
    tasks, rows = _tasks(seeds), []
    t0 = time.perf_counter()
    with Pool(workers, initializer=_initialise, initargs=(calibrations, selected)) as pool:
        for i, rs in enumerate(pool.imap_unordered(worker, tasks), 1):
            rows.extend(rs)
            if i % 10 == 0:
                print(f"{phase}: {i}/{len(tasks)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    rows.sort(key=lambda r: (CONDITIONS.index((r["R_m"], r["cell_m"])),
                             TERRAIN_TYPES.index(r["kind"]), r["side_m"], r["seed"],
                             r["variant"], r.get("lam", -1.0)))
    with open(OUT / filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({k for row in rows for k in row}), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _save_report(filename, render):
    output = io.StringIO()
    with redirect_stdout(output), pd.option_context("display.width", 200):
        render()
    report = output.getvalue()
    print(report, end="", flush=True)
    (OUT / filename).write_text(report)


def calibration_report(calibrations):
    def render():
        for cell, calib in sorted(calibrations.items()):
            print(f"calibration: cell_m={cell:g}")
            table = pd.DataFrame(dict(lower_deg=calib.edges_deg[:-1], upper_deg=calib.edges_deg[1:],
                                      mean_cost=calib.mean_cost, p_lethal=calib.p_lethal, counts=calib.counts))
            print(table.round(6).to_string(index=False))
            print()
    _save_report("risk_prior_calibration_log.txt", render)


def _relative(d):
    ref = d[d.variant == "oracle TA*-S"].set_index(KEY)
    d = d.join(ref[["J", "length_xy", "energy_kj"]].rename(columns=lambda c: c + "_O"), on=KEY)
    for metric, column in (("dJ", "J"), ("dL", "length_xy"), ("dE", "energy_kj")):
        d[metric] = 100 * (d[column] / d[column + "_O"] - 1)
    return d


def select_lambda():
    d = _relative(pd.read_csv(OUT / "risk_prior_validation.csv"))
    candidates = d[d.variant == "risk"]
    table = candidates.groupby("lam").agg(
        succ=("success", "mean"), runs=("success", "size"), computed_dJ=("dJ", "count"),
        dJ_median=("dJ", "median"), plans_median=("n_plans", "median")).reset_index()
    ranking = table.dropna(subset=["dJ_median"]).sort_values(["dJ_median", "plans_median", "lam"])
    if ranking.empty:
        raise RuntimeError("no validation dJ could be computed; lambda cannot be selected")
    selected = float(ranking.iloc[0].lam)
    def render():
        print("lambda selection (validation seeds only; unrounded medians determine rank):")
        print(table.round(6).to_string(index=False))
        print(f"\nselected lambda: {selected:g}")
        _failures(d)
    _save_report("risk_prior_lambda_log.txt", render)
    (OUT / "selected_lambda.json").write_text(json.dumps(dict(
        lam=selected, validation_seeds=list(VAL_SEEDS), sizes=list(SIZES), kinds=list(TERRAIN_TYPES),
        conditions=CONDITIONS, candidates=LAMBDAS,
        criterion=["median dJ", "median n_plans", "smaller lambda"],
        selected_dJ_median=float(ranking.iloc[0].dJ_median),
        selected_plans_median=float(ranking.iloc[0].plans_median)), indent=2, allow_nan=False) + "\n")
    return selected


def _failures(d):
    failures = d[~d.success.astype(bool)]
    print("\nfailures:", failures.groupby(COND + ["variant", "reason"]).size().to_dict())
    if not failures.empty:
        columns = KEY + ["variant", "reason"] + (["lam"] if "lam" in failures else [])
        print(failures[columns].to_string(index=False))


def summary():
    d = _relative(pd.read_csv(OUT / "risk_prior.csv"))
    ref_a = d[d.variant == "oracle A*"].set_index(KEY)
    d = d.join(ref_a[["energy_kj"]].rename(columns={"energy_kj": "energy_kj_A"}), on=KEY)
    d["dE_A"] = 100 * (d.energy_kj / d.energy_kj_A - 1)
    order = pd.MultiIndex.from_tuples([(r, c, v) for r, c in CONDITIONS for v in ORDER], names=COND + ["variant"])
    grouped = d.groupby(COND + ["variant"])
    agg = grouped.agg(
        succ=("success", "mean"), steep_exposed=("steep_len", lambda x: (x.dropna() > 0).mean()),
        dJ=("dJ", "median"), dL=("dL", "median"), dE=("dE", "median"),
        dE_A=("dE_A", "median"), cost=("mean_cost", "median"), slope95=("p95_slope", "median"),
        plans=("n_plans", "median"), plan_time=("plan_time", "median")).reindex(order)
    tails = grouped.agg(dJ90=("dJ", lambda x: x.quantile(0.9)), dJ_max=("dJ", "max"),
                        dL90=("dL", lambda x: x.quantile(0.9)), dL_max=("dL", "max")).reindex(order)
    tests = []
    for variant in ("risk λ*", "calibrated mean"):
        family = []
        for radius, cell in CONDITIONS:
            condition = d[(d.R_m == radius) & (d.cell_m == cell)]
            paired = condition.pivot(index=SCENARIO, columns="variant", values="dJ")[[variant, "coarse"]].dropna()
            if paired.empty:
                raise RuntimeError(f"no paired dJ values for {variant}, R={radius}, cell={cell}")
            p, r, delta = paired_test(paired[variant], paired["coarse"])
            family.append(dict(R_m=radius, cell_m=cell, comparison=f"{variant} - coarse", n=len(paired),
                               dJ_diff_median=delta, r=r, p=p))
        for row, adjusted in zip(family, holm([row["p"] for row in family])):
            tests.append(dict(row, p_holm=float(adjusted)))
    def render():
        print("per condition and variant (medians; relative metrics [%]):")
        print(agg.round(3).to_string())
        print("\nupper tails (90th percentile and maximum [%]):")
        print(tails.round(3).to_string())
        print("\nper condition and terrain (median dJ [%]):")
        print(d.pivot_table(index=COND + ["variant"], columns="kind", values="dJ", aggfunc="median")
              .reindex(order).round(3).to_string())
        print("\npaired two-sided Wilcoxon tests (Holm across five conditions per comparison):")
        print("negative r favours the first method (lower dJ)")
        print(pd.DataFrame(tests).to_string(index=False, float_format=lambda x: f"{x:.6g}"))
        _failures(d)
    _save_report("risk_prior_log.txt", render)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.summary_only:
        start = time.perf_counter()
        calibrations = {}
        for cell in sorted({cell for _, cell in CONDITIONS}):
            calibrations[cell] = calibrate(cell)
            save_calibration(calibrations[cell], OUT / f"calibration_{cell:g}.json")
        calibrated = time.perf_counter()
        calibration_report(calibrations)
        _run_pool(run_validation, VAL_SEEDS, calibrations, None, args.workers,
                  "risk_prior_validation.csv", "validation")
        selected = select_lambda()
        validated = time.perf_counter()
        _run_pool(run_test, TEST_SEEDS, calibrations, selected, args.workers, "risk_prior.csv", "test")
        tested = time.perf_counter()
        summary()
        runtime = dict(calibration_s=calibrated - start, validation_s=validated - calibrated,
                       test_s=tested - validated, total_s=time.perf_counter() - start, workers=args.workers,
                       python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__)
        (OUT / "risk_prior_runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
    else:
        calibration_report({cell: load_calibration(OUT / f"calibration_{cell:g}.json")
                            for cell in sorted({cell for _, cell in CONDITIONS})})
        select_lambda()
        summary()
        runtime = json.loads((OUT / "risk_prior_runtime.json").read_text())
    print("\nruntime [s]:", json.dumps(runtime, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
