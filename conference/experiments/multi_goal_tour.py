#!/usr/bin/env python3
"""Exact closed-tour comparisons on shared, physically weighted safe pair paths."""
import argparse
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
from experiments.analyze import paired_test, holm
from tapp.beach_scenario import build_beach
from tapp.beach_terrain import BEACH_TYPES
from tapp.config import DEFAULT_W, RESOLUTION, Robot
from tapp.directional import segment_cost_dir
from tapp.tour import (
    sample_waypoints,
    cost_matrix,
    euclid_matrix,
    solve_tour,
    tour_legs,
)
from tapp.metrics import evaluate
from tapp.collision import path_lethal_cells

OUT = Path(__file__).resolve().parent.parent / "results" / "multi_goal_tour"
METHODS = ["euclid", "terrain sym", "terrain dir", "terrain dir / TA*-S legs"]
KEY = ["kind", "side_m", "seed", "n_goals"]
KAPPA = 1 / Robot().rolling_coeff


def join_legs(order, paths):
    result = []
    for pair in tour_legs(order):
        leg = paths[pair]
        result.extend(leg if not result else leg[1:])
    return result


def plot_example(sc, points, tours):
    tm = sc["tmap"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 5), constrained_layout=True)
    extent = [0, sc["side_m"], 0, sc["side_m"]]
    for ax, name in zip(axs, ("euclid", "terrain dir")):
        image = ax.imshow(
            tm.slope.T, origin="lower", extent=extent, cmap="YlOrBr", vmin=0, vmax=25
        )
        ax.imshow(
            np.ma.masked_where(~tm.lethal.T, tm.lethal.T),
            origin="lower",
            extent=extent,
            cmap="gray",
            vmin=0,
            vmax=1,
            alpha=0.8,
        )
        ax.imshow(
            np.ma.masked_where(~sc["water"].T, sc["water"].T),
            origin="lower",
            extent=extent,
            cmap="Blues",
            vmin=0,
            vmax=1,
        )
        p = (np.array(tours[name]) + 0.5) * RESOLUTION
        ax.plot(p[:, 0], p[:, 1], color="#008b8b", lw=1.2)
        xy = (np.array(points) + 0.5) * RESOLUTION
        ax.scatter(xy[:, 0], xy[:, 1], s=15, c="white", edgecolors="black", zorder=4)
        for i, (x, y) in enumerate(xy):
            ax.annotate(
                str(i), (x, y), xytext=(3, 3), textcoords="offset points", fontsize=8
            )
        ax.set(title=name, xlabel="x [m]", ylabel="y [m]", aspect="equal")
        ax.grid(False)
    fig.colorbar(image, ax=axs, label="slope [deg]", shrink=0.65)
    fig.suptitle("beach_steep / 200 m / seed 0 / 12 goals (0 = base)")
    fig.savefig(OUT / "tour_example.png", dpi=160)
    plt.close(fig)


def run(args):
    kind, size, seed = args
    t0 = time.perf_counter()
    sc = build_beach(kind, size, seed)
    tm = sc["tmap"]
    points = [sc["start"]] + sample_waypoints(
        sc, 12, np.random.SeedSequence([seed, 3000, size, BEACH_TYPES.index(kind)])
    )
    points = [tuple(map(int, p)) for p in points]
    sym = cost_matrix(sc, points, w=DEFAULT_W, kappa=0)
    directed = cost_matrix(sc, points, w=DEFAULT_W, kappa=KAPPA)
    t = time.perf_counter()
    euclid = euclid_matrix(points)
    euclid_time = time.perf_counter() - t
    assert np.isfinite(directed["C"]).all() and np.isfinite(sym["C"]).all()
    base = dict(
        kind=kind,
        side_m=size,
        seed=seed,
        used_seed=sc["used_seed"],
        redraws=sc["redraws"],
    )
    pairs = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            a, b = directed["C"][i, j], directed["C"][j, i]
            pairs.append(
                dict(
                    base,
                    i=i,
                    j=j,
                    C_ij=a,
                    C_ji=b,
                    asymmetry=abs(a - b) / (a + b),
                    zero_kappa_asymmetry=abs(sym["C"][i, j] - sym["C"][j, i])
                    / (sym["C"][i, j] + sym["C"][j, i]),
                )
            )
    rows = []
    examples = {}
    for n in (5, 8, 12):
        solved = {}
        for name, C in zip(METHODS[:3], (euclid, sym["C"], directed["C"])):
            ts = time.perf_counter()
            order, cost = solve_tour(C[: n + 1, : n + 1])
            elapsed = time.perf_counter() - ts
            assert len(order) == n + 1
            solved[name] = (order, cost, elapsed)
        for method in METHODS:
            order, objective, solve_time = solved[
                "terrain dir" if method == METHODS[-1] else method
            ]
            paths = sym["paths"] if method == METHODS[-1] else directed["paths"]
            path = join_legs(order, paths)
            assert path[0] == path[-1] == sc["start"]
            lethal = len(path_lethal_cells(path, tm.lethal))
            assert lethal == 0
            physical = sum(
                segment_cost_dir(1 + DEFAULT_W * tm.cost, tm.elev, a, b, KAPPA)
                for a, b in zip(path, path[1:])
            )
            row = dict(
                base,
                n_goals=n,
                method=method,
                order=json.dumps(order),
                points=json.dumps(points[: n + 1]),
                cost_dir=physical,
                ordering_objective=objective,
                solve_time_s=solve_time,
                matrix_time_s=(
                    euclid_time
                    if method == "euclid"
                    else sym["time"] if method == "terrain sym" else directed["time"]
                ),
                execution_matrix_time_s=(
                    sym["time"] if method == METHODS[-1] else directed["time"]
                ),
                lethal_cells=lethal,
                **evaluate(path, tm),
            )
            rows.append(row)
            if kind == "beach_steep" and size == 200 and seed == 0 and n == 12:
                examples[method] = path
    if examples:
        plot_example(sc, points, examples)
    return (
        rows,
        pairs,
        dict(
            base,
            wall_time_s=time.perf_counter() - t0,
            sym_matrix_s=sym["time"],
            dir_matrix_s=directed["time"],
        ),
    )


def summaries(df, pairs, timing, wall, procs):
    print(
        f"kappa = {KAPPA:.12g}; w = {DEFAULT_W:g}; workers = {procs}; scenarios = {len(timing)}; tours = {len(df)}"
    )
    print(f"Experiment wall time [s]: {wall:.6f}")
    print(
        "Matrix times are for 13 points, reused by the 5/8/12-goal prefixes; solve times exclude matrix construction."
    )
    print(
        "Relative values are 100*(method/terrain dir - 1); energy is displayed only as percent."
    )

    def table(title, rows):
        print("\n" + title)
        print(
            pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:.6g}")
        )

    rows = []
    for n in (5, 8, 12):
        for method in METHODS:
            d = df[(df.n_goals == n) & (df.method == method)]
            row = dict(n_goals=n, method=method)
            for col in (
                "cost_rel_pct",
                "energy_rel_pct",
                "length_xy",
                "climb",
                "p95_roll",
                "steep_len",
            ):
                row[col + "_median"] = d[col].median()
                row[col + "_p90"] = d[col].quantile(0.9)
            rows.append(row)
    table("Tour metrics (length/climb/steep length [m], roll [deg])", rows)
    rows = []
    changes = []
    tests = []
    for n in (5, 8, 12):
        d = df[df.n_goals == n]
        cost = d.pivot(index=KEY[:-1], columns="method", values="cost_dir")
        orders = d.pivot(index=KEY[:-1], columns="method", values="order")
        for kind in BEACH_TYPES:
            c = cost.loc[kind]
            o = orders.loc[kind]
            rows.append(
                dict(
                    kind=kind,
                    n_goals=n,
                    dir_vs_euclid_cost_pct_median=(
                        100 * (c["terrain dir"] / c["euclid"] - 1)
                    ).median(),
                )
            )

            def canonical_cycle(text):
                p = json.loads(text)
                rev = [p[0]] + list(reversed(p[1:]))
                return min(p, rev)

            changes.append(
                dict(
                    kind=kind,
                    n_goals=n,
                    euclid_vs_dir_pct=100 * (o["euclid"] != o["terrain dir"]).mean(),
                    sym_vs_dir_pct=100 * (o["terrain sym"] != o["terrain dir"]).mean(),
                    euclid_vs_dir_cycle_pct=100
                    * np.mean(
                        [
                            canonical_cycle(a) != canonical_cycle(b)
                            for a, b in zip(o["euclid"], o["terrain dir"])
                        ]
                    ),
                    sym_vs_dir_cycle_pct=100
                    * np.mean(
                        [
                            canonical_cycle(a) != canonical_cycle(b)
                            for a, b in zip(o["terrain sym"], o["terrain dir"])
                        ]
                    ),
                )
            )
        for method in METHODS[:2]:
            p, r, delta = paired_test(cost[method], cost["terrain dir"])
            tests.append(
                dict(
                    n_goals=n,
                    comparison=method + " vs terrain dir",
                    n=len(cost),
                    p=p,
                    r=r,
                    median_cost_difference=delta,
                )
            )
    table("Directed cost relative to Euclidean ordering [%]", rows)
    table(
        "Changed orders [%]; cycle columns identify a tour with its reversal", changes
    )
    table(
        "Changed orders overall [%]",
        [
            dict(
                n_goals=n,
                euclid_vs_dir_pct=np.mean(
                    [r["euclid_vs_dir_pct"] for r in changes if r["n_goals"] == n]
                ),
                sym_vs_dir_pct=np.mean(
                    [r["sym_vs_dir_pct"] for r in changes if r["n_goals"] == n]
                ),
            )
            for n in (5, 8, 12)
        ],
    )
    table(
        "Pair-matrix asymmetry |Cij-Cji|/(Cij+Cji)",
        [
            dict(
                kind=k,
                pairs=len(d),
                median=d.asymmetry.median(),
                p90=d.asymmetry.quantile(0.9),
            )
            for k, d in pairs.groupby("kind", sort=False)
        ],
    )
    for row, p in zip(tests, holm([r["p"] for r in tests])):
        row["p_holm"] = p
    table(
        "Zero-kappa smoothing/sampling asymmetry audit",
        [
            dict(
                kind=k,
                median=d.zero_kappa_asymmetry.median(),
                p90=d.zero_kappa_asymmetry.quantile(0.9),
                maximum=d.zero_kappa_asymmetry.max(),
            )
            for k, d in pairs.groupby("kind", sort=False)
        ],
    )
    table("Paired two-sided Wilcoxon; Holm correction over all six comparisons", tests)
    pd.DataFrame(tests).to_csv(OUT / "paired_tests.csv", index=False)
    rows = []
    for size in (100, 200):
        t = timing[timing.side_m == size]
        e = df[(df.side_m == size) & (df.method == "euclid") & (df.n_goals == 12)]
        rows.append(
            dict(
                side_m=size,
                method="euclid",
                matrix_13points_median_s=e.matrix_time_s.median(),
                matrix_13points_max_s=e.matrix_time_s.max(),
            )
        )
        for name, col in (
            ("terrain sym", "sym_matrix_s"),
            ("terrain dir", "dir_matrix_s"),
        ):
            rows.append(
                dict(
                    side_m=size,
                    method=name,
                    matrix_13points_median_s=t[col].median(),
                    matrix_13points_max_s=t[col].max(),
                )
            )
    table("Matrix computation time [s] (200 m / 12 goals included)", rows)
    table(
        "Held-Karp solve time [s]",
        [
            dict(
                side_m=size,
                n_goals=n,
                method=method,
                median_s=d.solve_time_s.median(),
                max_s=d.solve_time_s.max(),
            )
            for (size, n, method), d in df[df.method != METHODS[-1]].groupby(
                ["side_m", "n_goals", "method"]
            )
        ],
    )
    print(f"\nSafety: maximum lethal cells per complete tour = {df.lethal_cells.max()}")
    print(
        "Closed-tour endpoint elevation potentials cancel: improvements cannot be attributed solely to matrix asymmetry."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--procs", type=int, default=min(5, os.cpu_count() or 1))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    jobs = [
        (kind, size, seed)
        for kind in BEACH_TYPES
        for size in (100, 200)
        for seed in range(10)
    ]
    rows = []
    pairs = []
    timing = []
    with Pool(args.procs) as pool:
        for i, (r, p, t) in enumerate(pool.imap_unordered(run, jobs), 1):
            rows.extend(r)
            pairs.extend(p)
            timing.append(t)
            print(
                f'completed {i}/{len(jobs)}: {t["kind"]} {t["side_m"]} seed {t["seed"]}',
                file=sys.stderr,
                flush=True,
            )
    df = pd.DataFrame(rows).sort_values(KEY + ["method"])
    pairs = pd.DataFrame(pairs).sort_values(["kind", "side_m", "seed", "i", "j"])
    timing = pd.DataFrame(timing).sort_values(KEY[:-1])
    ref = df[df.method == "terrain dir"].set_index(KEY)
    for source, target in (
        ("cost_dir", "cost_rel_pct"),
        ("energy_kj", "energy_rel_pct"),
    ):
        df[target] = [
            100 * (r[source] / ref.loc[tuple(r[k] for k in KEY), source] - 1)
            for _, r in df.iterrows()
        ]
    df.to_csv(OUT / "tours.csv", index=False)
    pairs.to_csv(OUT / "pair_costs.csv", index=False)
    timing.to_csv(OUT / "scenario_times.csv", index=False)
    wall = time.perf_counter() - start
    (OUT / "metadata.json").write_text(
        json.dumps(
            dict(
                kappa=KAPPA,
                w=DEFAULT_W,
                procs=args.procs,
                wall_time_s=wall,
                scenario_seeds=list(range(10)),
                waypoint_seed="SeedSequence([scenario_seed, 3000, side_m, BEACH_TYPES.index(kind)])",
                matrix_points=13,
                matrix_reuse="first 5, 8, 12 goals; two full matrices per scenario",
                python=sys.version,
                numpy=np.__version__,
                pandas=pd.__version__,
            ),
            indent=2,
        )
        + "\n"
    )
    output = io.StringIO()
    with redirect_stdout(output):
        summaries(df, pairs, timing, wall, args.procs)
    log = output.getvalue()
    (OUT / "multi_goal_tour_log.txt").write_text(log)
    print(log, end="")


if __name__ == "__main__":
    main()
