#!/usr/bin/env python3
"""Run every experiment of the paper and write raw results to results/.

  E0 val_sweep : terrain-weight sweep on VALIDATION seeds (used only to pick w)
  E1 main      : 5 planners on the TEST set
  E2 sweep     : terrain-weight sweep on the TEST set (reported, not used to tune)
  E3 ablation  : slope/roughness weighting alpha
  E4 noise     : planning on a noisy elevation map, evaluation on ground truth

Usage (from conference/):  python3 experiments/run_all.py [--quick]
"""
import argparse
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp import terrain                                   # noqa: E402
from tapp.config import CostWeights, Robot, DEFAULT_W      # noqa: E402
from tapp.metrics import evaluate                          # noqa: E402
from tapp.scenario import PLANNERS, build, run_planner     # noqa: E402
from tapp.traversability import TraversabilityMap          # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
SIZES = (50, 100, 200)
TEST_SEEDS = range(10)
VAL_SEEDS = range(100, 105)
W_GRID = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
NOISE = (0.02, 0.05, 0.10)
NOISE_PLANNERS = ("A*-HC", "TA*")


def row(exp, sc, planner, r, w=None, alpha=None, noise=None, truth=None):
    out = {"exp": exp, "kind": sc["kind"], "side_m": sc["side_m"], "seed": sc["seed"],
           "redraws": sc["redraws"], "planner": planner, "w": w, "alpha": alpha,
           "noise": noise, "success": bool(r["success"]), "time": r["time"],
           "expansions": r["expansions"]}
    if r["success"]:
        out.update(evaluate(r["path"], truth or sc["tmap"]))
    return out


def run_scenario(args):
    kind, side, seed, split, w_main = args
    rows = []
    sc = build(kind, side, seed)
    if split == "val":
        for w in W_GRID:
            for p in ("TA*", "TA*-S"):
                rows.append(row("val_sweep", sc, p, run_planner(p, sc, w=w), w=w))
        return rows, None

    example = None
    for p in PLANNERS:
        r = run_planner(p, sc, w=w_main)
        rows.append(row("main", sc, p, r, w=w_main if p.startswith("TA") else None))
        if seed == 0 and side == 100:
            example = example or {"elev": sc["tmap"].elev, "cost": sc["tmap"].cost,
                                  "lethal": sc["tmap"].lethal, "start": sc["start"],
                                  "goal": sc["goal"], "paths": {}}
            example["paths"][p] = np.asarray(r["path"]) if r["success"] else None
    for w in W_GRID:
        for p in ("TA*", "TA*-S"):
            rows.append(row("sweep", sc, p, run_planner(p, sc, w=w), w=w))
    for a in ALPHAS:
        sca = build(kind, side, seed, weights=CostWeights(alpha=a, beta=1.0 - a))
        r = run_planner("TA*", sca, w=w_main)
        # evaluate on the default-weight map so that the metrics are identical
        rows.append(row("ablation", sca, "TA*", r, w=w_main, alpha=a, truth=sc["tmap"]))
    rng = np.random.default_rng(int(sc["used_seed"]) % (2 ** 32))
    for sigma in NOISE:
        tm = sc["tmap"]
        noisy = TraversabilityMap(tm.elev + rng.normal(0.0, sigma, tm.elev.shape),
                                  np.zeros_like(tm.rock), Robot(), CostWeights())
        noisy.rock = tm.rock.copy()          # obstacles assumed detected
        noisy.lethal = noisy.rock | noisy.steep
        for c in (sc["start"], sc["goal"]):
            noisy.lethal[c] = False
        for p in NOISE_PLANNERS:
            rows.append(row("noise", sc, p, run_planner(p, sc, w=w_main, plan_map=noisy),
                            w=w_main if p == "TA*" else None, noise=sigma))
    return rows, example


def choose_w(val_rows):
    """Pre-registered rule: the largest w whose median path-length overhead of
    TA*-S w.r.t. w=0 is at most 10 % on the validation set."""
    import collections
    base = {}
    by_w = collections.defaultdict(list)
    for r in val_rows:
        if r["planner"] != "TA*-S" or not r["success"]:
            continue
        key = (r["kind"], r["side_m"], r["seed"])
        if r["w"] == 0.0:
            base[key] = r["length_xy"]
    for r in val_rows:
        if r["planner"] == "TA*-S" and r["success"]:
            key = (r["kind"], r["side_m"], r["seed"])
            by_w[r["w"]].append(r["length_xy"] / base[key] - 1.0)
    ok = [w for w in sorted(by_w) if np.median(by_w[w]) <= 0.10]
    return max(ok), {w: float(np.median(v)) for w, v in sorted(by_w.items())}


def write_csv(path, rows):
    keys = sorted({k for r in rows for k in r})
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="1 seed, small maps")
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    a = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    sizes = (50,) if a.quick else SIZES
    test = range(1) if a.quick else TEST_SEEDS
    val = range(100, 101) if a.quick else VAL_SEEDS
    t0 = time.time()

    with Pool(a.procs) as pool:
        tasks = [(k, s, sd, "val", None) for k in terrain.TERRAIN_TYPES for s in sizes for sd in val]
        val_rows = [r for rows, _ in pool.imap_unordered(run_scenario, tasks) for r in rows]
        w_main, overhead = choose_w(val_rows)
        print(f"validation: median length overhead by w = {overhead}; chosen w = {w_main}")

        tasks = [(k, s, sd, "test", w_main) for k in terrain.TERRAIN_TYPES for s in sizes for sd in test]
        rows, examples = [], {}
        for i, (rs, ex) in enumerate(pool.imap_unordered(run_scenario, tasks), 1):
            rows.extend(rs)
            if ex is not None:
                examples[rs[0]["kind"]] = ex
            print(f"  {i}/{len(tasks)} scenarios done ({time.time() - t0:.0f}s)", flush=True)

    write_csv(os.path.join(RESULTS, "val_sweep.csv"), val_rows)
    write_csv(os.path.join(RESULTS, "test_results.csv"), rows)
    np.save(os.path.join(RESULTS, "examples.npy"), examples, allow_pickle=True)
    meta = {"w_main": w_main, "val_overhead": overhead, "sizes": list(sizes),
            "test_seeds": list(test), "val_seeds": list(val), "w_grid": list(W_GRID),
            "alphas": list(ALPHAS), "noise": list(NOISE), "default_w_in_config": DEFAULT_W,
            "robot": Robot().__dict__, "weights": CostWeights().__dict__,
            "cpu_count": os.cpu_count(), "procs": a.procs, "wall_time_s": time.time() - t0,
            "numpy": np.__version__, "python": sys.version.split()[0]}
    with open(os.path.join(RESULTS, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
