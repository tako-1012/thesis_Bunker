#!/usr/bin/env python3
"""Statistics, ICAROB planner claims and exact online replanning on natural terrain."""
import argparse, csv, io, json, os, sys, time
from pathlib import Path
from contextlib import redirect_stdout
from multiprocessing import Pool
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from experiments.analyze import paired_test, holm
from tapp.natural_terrain import NATURAL_TYPES, spectrum_slope
from tapp.natural_scenario import build_natural
from tapp.scenario import PLANNERS, run_planner
from tapp.config import DEFAULT_W, RESOLUTION
from tapp.traversability import slope_deg
from tapp.metrics import evaluate
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.collision import path_lethal_cells

OUT = Path(__file__).resolve().parent.parent / "results" / "natural_terrain"
KEY = ["kind", "side_m", "seed"]
VARIANTS = [
    ("online adaptive R15", 15, None),
    ("coarse R15 c5", 15, 5),
    ("coarse R10 c10", 10, 10),
    ("coarse R5 c10", 5, 10),
    ("coarse R5 c20", 5, 20),
]
ORDER = ["oracle A*", "oracle TA*-S"] + [v[0] for v in VARIANTS]


def metrics(path, tm):
    m = evaluate(path, tm)
    return dict(m, J=m["length_xy"] * (1 + DEFAULT_W * m["mean_cost"]))


def path_figure(sc, paths, name):
    tm = sc["tmap"]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(tm.elev.T, origin="lower", cmap="terrain")
    ax.contour(tm.lethal.T, levels=[0.5], colors=["red"], linewidths=0.4)
    for label, path in paths:
        p = np.asarray(path)
        ax.plot(p[:, 0], p[:, 1], label=label, lw=1.2)
    ax.legend(fontsize=7)
    ax.set_title(name)
    ax.set_xlabel("x [cells]")
    ax.set_ylabel("y [cells]")
    fig.tight_layout()
    fig.savefig(OUT / f'detour_{sc["kind"]}_{sc["side_m"]}_{sc["seed"]}.png', dpi=130)
    plt.close(fig)


def run(args):
    kind, size, seed, split = args
    ast = time.perf_counter()
    sc = build_natural(kind, size, seed)
    tm = sc["tmap"]
    t = sc["terrain"]
    base = dict(
        kind=kind,
        side_m=size,
        seed=seed,
        used_seed=sc["used_seed"],
        redraws=sc["redraws"],
    )
    stat = dict(
        base,
        split=split,
        slope50=np.median(tm.slope),
        slope90=np.percentile(tm.slope, 90),
        slope99=np.percentile(tm.slope, 99),
        steep=np.mean(tm.slope > 25),
        rock=t["rock"].mean(),
        rough=np.median(tm.rough),
        spectrum_before=spectrum_slope(t["pre_elev"]),
        spectrum_after=spectrum_slope(tm.elev),
        generation_time=sc["generation_time"],
    )
    stat["statistics_elapsed_s"] = time.perf_counter() - ast
    stat["offline_elapsed_s"] = stat["online_elapsed_s"] = 0.0
    off, on = [], []
    if split == "test":
        bt = time.perf_counter()
        refs = {}
        for name in PLANNERS:
            r = run_planner(name, sc, w=DEFAULT_W)
            row = dict(base, planner=name, success=r["success"], time=r["time"])
            if r["success"]:
                row.update(metrics(r["path"], tm))
                row["lethal_cells"] = (
                    len(path_lethal_cells(r["path"], tm.lethal))
                    if name in ("TA*", "TA*-S")
                    else np.nan
                )
            off.append(row)
            refs[name] = (r, row)
        stat["offline_elapsed_s"] = time.perf_counter() - bt
        ct = time.perf_counter()
        if size in (50, 100):
            for name in ("A*", "TA*-S"):
                row = dict(refs[name][1])
                row["lethal_cells"] = len(path_lethal_cells(refs[name][0]["path"], tm.lethal))
                row["variant"] = "oracle " + name
                row["plan_time"] = row.pop("time")
                row["n_plans"] = 1
                on.append(row)
            jo = refs["TA*-S"][1]["J"]
            paths = []
            for name, radius, cell in VARIANTS:
                r = run_online(
                    tm,
                    sc["start"],
                    sc["goal"],
                    planner="TA*-S",
                    w=DEFAULT_W,
                    exact_los=True,
                    prior_lethal="soft",
                    unknown_cost="adaptive",
                    sense_radius_m=radius,
                    prior_map=None if cell is None else coarse_prior(tm, cell),
                )
                row = dict(
                    base,
                    variant=name,
                    success=r["success"],
                    reason=r["reason"],
                    n_plans=r["n_plans"],
                    plan_time=r["plan_time"],
                    lethal_cells=len(path_lethal_cells(r["traj"], tm.lethal)),
                )
                if r["success"]:
                    row.update(metrics(r["traj"], tm))
                    dj = 100 * (row["J"] / jo - 1)
                    if dj > 25:
                        paths.append((f"{name}: dJ={dj:.1f}%", r["traj"]))
                on.append(row)
            if paths:
                paths.insert(0, ("oracle TA*-S", refs["TA*-S"][0]["path"]))
                path_figure(sc, paths, f"{kind}, {size}m, seed {seed}")
        stat["online_elapsed_s"] = time.perf_counter() - ct
    return stat, off, on


def write_csv(name, rows):
    with open(OUT / name, "w", newline="") as f:
        wr = csv.DictWriter(
            f, fieldnames=sorted({k for r in rows for k in r}), lineterminator="\n"
        )
        wr.writeheader()
        wr.writerows(rows)


def gallery():
    fig, axes = plt.subplots(5, 2, figsize=(10, 20))
    light = LightSource(315, 45)
    for i, kind in enumerate(NATURAL_TYPES):
        sc = build_natural(kind, 100, 100)
        tm = sc["tmap"]
        axes[i, 0].imshow(
            light.hillshade(tm.elev.T, dx=RESOLUTION, dy=RESOLUTION),
            origin="lower",
            cmap="gray",
        )
        axes[i, 1].imshow(tm.slope.T, origin="lower", cmap="viridis", vmin=0, vmax=25)
        axes[i, 1].imshow(
            np.ma.masked_where(tm.slope.T <= 25, np.ones(tm.shape)),
            origin="lower",
            cmap="Reds",
            vmin=0,
            vmax=1,
        )
        for j in range(2):
            axes[i, j].set_title(
                f"{kind}: " + ("hillshade" if j == 0 else "slope; >25deg red")
            )
    fig.tight_layout()
    fig.savefig(OUT / "natural_terrain_gallery.png", dpi=120)
    plt.close(fig)


def summary():
    a = pd.read_csv(OUT / "statistics.csv")
    b = pd.read_csv(OUT / "offline.csv")
    c = pd.read_csv(OUT / "online.csv")
    ref = c[c.variant == "oracle TA*-S"].set_index(KEY)
    c = c.join(ref[["J", "length_xy", "energy_kj"]].add_suffix("_O"), on=KEY)
    ra = c[c.variant == "oracle A*"].set_index(KEY).energy_kj
    c = c.join(ra.rename("energy_A"), on=KEY)
    for name, col in (("dJ", "J"), ("dL", "length_xy"), ("dE", "energy_kj")):
        c[name] = 100 * (c[col] / c[col + "_O"] - 1)
    c["dE_A"] = 100 * (c.energy_kj / c.energy_A - 1)
    tests = []
    for col in ("steep_len", "mean_cost", "climb", "energy_kj", "length_xy"):
        p = b.pivot(index=KEY, columns="planner", values=col)[["TA*-S", "A*"]].dropna()
        pv, r, delta = paired_test(p["TA*-S"], p["A*"])
        tests.append(dict(metric=col, n=len(p), p=pv, r=r, delta=delta))
    for t, adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = adj
    output = io.StringIO()
    with redirect_stdout(output):
        print("A: terrain statistics (medians, validation and test shown separately)")
        cols = [
            "slope50",
            "slope90",
            "slope99",
            "steep",
            "rock",
            "rough",
            "spectrum_before",
            "spectrum_after",
            "redraws",
            "generation_time",
        ]
        print(
            a.groupby(["split", "kind", "side_m"])[cols].median().round(6).to_string()
        )
        print("\nB: offline planner medians")
        print(
            b.groupby("planner")
            .agg(
                success=("success", "mean"),
                exposed=("steep_len", lambda x: (x > 0).mean()),
                steep_len=("steep_len", "median"),
                cost=("mean_cost", "median"),
                climb=("climb", "median"),
                energy=("energy_kj", "median"),
                length=("length_xy", "median"),
                time=("time", "median"),
            )
            .round(6)
            .to_string()
        )
        print("\nB: TA* / TA*-S paths touching lethal cells")
        print(
            b[b.planner.isin(["TA*", "TA*-S"])]
            .groupby("planner")
            .lethal_cells.agg(lambda x: (x > 0).sum())
            .to_string()
        )
        print("\nB: TA*-S minus A*, two-sided Wilcoxon; Holm over five metrics")
        print(
            pd.DataFrame(tests).to_string(
                index=False, float_format=lambda x: f"{x:.6g}"
            )
        )
        print("\nC: online medians")
        print(
            c.groupby("variant")
            .agg(
                success=("success", "mean"),
                exposed=("steep_len", lambda x: (x > 0).mean()),
                dJ=("dJ", "median"),
                dL=("dL", "median"),
                dE=("dE", "median"),
                dE_A=("dE_A", "median"),
                slope95=("p95_slope", "median"),
                plans=("n_plans", "median"),
                plan_time=("plan_time", "median"),
                touching=("lethal_cells", lambda x: (x > 0).sum()),
            )
            .reindex(ORDER)
            .round(6)
            .to_string()
        )
        print("\nC: upper tails [%]")
        print(
            c.groupby("variant")
            .agg(
                dJ90=("dJ", lambda x: x.quantile(0.9)),
                dJmax=("dJ", "max"),
                dL90=("dL", lambda x: x.quantile(0.9)),
                dLmax=("dL", "max"),
            )
            .reindex(ORDER)
            .round(6)
            .to_string()
        )
        print("\nC: per terrain median dJ [%]")
        print(
            c.pivot_table(
                index="variant", columns="kind", values="dJ", aggfunc="median"
            )
            .reindex(ORDER)
            .round(6)
            .to_string()
        )
        print("\nC: dJ > 25% trajectories (figures: detour_<kind>_<side_m>_<seed>.png)")
        high = c[(c.dJ > 25) & ~c.variant.str.startswith("oracle")]
        print(
            high[KEY + ["variant", "dJ", "dL", "n_plans"]]
            .round(6)
            .to_string(index=False)
        )
        print("\nfailures:")
        print(c[~c.success][KEY + ["variant", "reason"]].to_string(index=False))
    text = output.getvalue()
    print(text, end="", flush=True)
    (OUT / "natural_terrain_log.txt").write_text(text)
    c.to_csv(OUT / "online_relative.csv", index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.summary_only:
        start = time.perf_counter()
        stats = []
        off = []
        on = []
        tasks = [
            (k, s, sd, split)
            for split, seeds in [("validation", range(100, 105)), ("test", range(10))]
            for k in NATURAL_TYPES
            for s in (50, 100, 200)
            for sd in seeds
        ]
        tasks.sort(key=lambda t: (t[3] != "validation", -t[1]))
        with Pool(args.workers) as pool:
            for i, (st, b, c) in enumerate(pool.imap_unordered(run, tasks), 1):
                stats.append(st)
                off.extend(b)
                on.extend(c)
                if i % 5 == 0:
                    print(
                        f"{i}/{len(tasks)} ({time.perf_counter()-start:.0f}s)",
                        flush=True,
                    )
        for name, rows in [
            ("statistics.csv", stats),
            ("offline.csv", off),
            ("online.csv", on),
        ]:
            rows.sort(
                key=lambda r: (
                    r["kind"],
                    r["side_m"],
                    r["seed"],
                    r.get("variant", r.get("planner", "")),
                )
            )
            write_csv(name, rows)
        experiments_done = time.perf_counter()
        gallery()
        summary()
        runtime = dict(
            experiments_s=experiments_done - start,
            total_s=time.perf_counter() - start,
            workers=args.workers,
            generation_sum_s=sum(r["generation_time"] for r in stats),
            statistics_sum_s=sum(r["statistics_elapsed_s"] for r in stats),
            offline_sum_s=sum(r["offline_elapsed_s"] for r in stats),
            online_sum_s=sum(r["online_elapsed_s"] for r in stats),
        )
        (OUT / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
        print("runtime:", runtime, flush=True)
    else:
        summary()


if __name__ == "__main__":
    main()
