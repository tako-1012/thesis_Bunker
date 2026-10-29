#!/usr/bin/env python3
"""Beach statistics, legacy/exact smoothing and safe alongshore online replanning."""
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
from tapp.beach_terrain import BEACH_TYPES
from tapp.natural_terrain import spectrum_slope
from tapp.exact_planners import run_planner_exact
from tapp.beach_scenario import build_beach
from tapp.scenario import run_planner
from tapp.config import DEFAULT_W, RESOLUTION
from tapp.traversability import slope_deg
from tapp.metrics import evaluate
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.collision import path_lethal_cells

OUT = Path(__file__).resolve().parent.parent / "results" / "beach_terrain"
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


def run(args):
    kind, size, seed, split = args
    ast = time.perf_counter()
    sc = build_beach(kind, size, seed)
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
        water=t["water"].mean(),
        wet=t["wet"].mean(),
        landward=t["landward"].mean(),
        driftwood=t["driftwood"].mean(),
        scarp_coverage=t["scarp"].any(axis=1).mean(),
        land_steep=np.mean(tm.slope[~t["water"] & ~t["landward"]] > 25),
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
        for name in ("A*", "A*-HC", "TA*", "TA*-S", "TA*-S exact"):
            r = (
                run_planner_exact("TA*-S", sc, w=DEFAULT_W)
                if name == "TA*-S exact"
                else run_planner(name, sc, w=DEFAULT_W)
            )
            row = dict(base, planner=name, success=r["success"], time=r["time"])
            if r["success"]:
                row.update(metrics(r["path"], tm))
                row["lethal_cells"] = (
                    len(path_lethal_cells(r["path"], tm.lethal))
                    if name in ("TA*", "TA*-S", "TA*-S exact")
                    else np.nan
                )
            off.append(row)
            refs[name] = (r, row)
        refs["TA*-S"] = refs["TA*-S exact"]
        stat["offline_elapsed_s"] = time.perf_counter() - bt
        ct = time.perf_counter()
        if size in (50, 100):
            for name in ("A*", "TA*-S"):
                row = dict(refs[name][1])
                row["lethal_cells"] = len(
                    path_lethal_cells(refs[name][0]["path"], tm.lethal)
                )
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
                cache = Path("/tmp/beach-terrain-traces")
                cache.mkdir(exist_ok=True)
                np.savez(
                    cache / f"{kind}_{size}_{seed}.npz",
                    elev=tm.elev,
                    lethal=tm.lethal,
                    paths=np.array(paths, dtype=object),
                )
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
    fig, axes = plt.subplots(5, 3, figsize=(15, 20))
    light = LightSource(315, 45)
    for i, kind in enumerate(BEACH_TYPES):
        sc = build_beach(kind, 100, 100)
        tm = sc["tmap"]
        t = sc["terrain"]
        axes[i, 0].imshow(
            light.hillshade(tm.elev.T, dx=RESOLUTION, dy=RESOLUTION),
            origin="lower",
            cmap="gray",
        )
        axes[i, 1].imshow(tm.slope.T, origin="lower", cmap="viridis", vmin=0, vmax=25)
        axes[i, 1].imshow(
            np.ma.masked_where(tm.slope.T < 25, np.ones(tm.shape)),
            origin="lower",
            cmap="Reds",
            vmin=0,
            vmax=1,
        )
        rgb = np.ones((*tm.shape, 3)) * 0.9
        rgb[t["wet"]] = [0.2, 0.85, 0.9]
        rgb[tm.lethal] = [0.9, 0.15, 0.1]
        rgb[t["water"]] = [0.1, 0.25, 0.9]
        axes[i, 2].imshow(rgb.transpose(1, 0, 2), origin="lower")
        for j, label in enumerate(
            ("hillshade", "slope; >=25deg red", "water blue / wet cyan / lethal red")
        ):
            axes[i, j].set_title(kind + ": " + label)
            axes[i, j].set_xlabel("x alongshore [cells]")
            axes[i, j].set_ylabel("y inland [cells]")
    fig.tight_layout()
    fig.savefig(OUT / "beach_terrain_gallery.png", dpi=100)
    plt.close(fig)


def render_detours():
    frame = pd.read_csv(OUT / "online_relative.csv")
    high = frame[(frame.dJ > 25) & ~frame.variant.str.startswith("oracle")]
    cases = (
        high.groupby(KEY)
        .dJ.max()
        .reset_index()
        .sort_values(["dJ"] + KEY, ascending=[False, True, True, True])
        .head(20)
    )
    for row in cases.itertuples(index=False):
        with np.load(
            f"/tmp/beach-terrain-traces/{row.kind}_{row.side_m}_{row.seed}.npz",
            allow_pickle=True,
        ) as data:
            fig, ax = plt.subplots(figsize=(7, 6))
            ax.imshow(data["elev"].T, origin="lower", cmap="terrain")
            ax.contour(data["lethal"].T, levels=[0.5], colors=["red"], linewidths=0.4)
            for label, path in data["paths"]:
                p = np.asarray(path)
                ax.plot(p[:, 0], p[:, 1], label=label, lw=1.2)
            ax.legend(fontsize=7)
            ax.set_title(f"{row.kind}, {row.side_m}m, seed {row.seed}")
            ax.set_xlabel("x alongshore [cells]")
            ax.set_ylabel("y inland [cells]")
            fig.tight_layout()
            fig.savefig(OUT / f"detour_{row.kind}_{row.side_m}_{row.seed}.png", dpi=130)
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
    ref_b = b[b.planner == "A*"].set_index(KEY).energy_kj
    b = b.join(ref_b.rename("energy_A"), on=KEY)
    b["energy_rel"] = 100 * (b.energy_kj / b.energy_A - 1)
    tests = []
    for col in ("steep_len", "mean_cost", "climb", "energy_rel", "length_xy"):
        p = b.pivot(index=KEY, columns="planner", values=col)[
            ["TA*-S exact", "A*"]
        ].dropna()
        pv, r, delta = paired_test(p["TA*-S exact"], p["A*"])
        tests.append(dict(metric=col, n=len(p), p=pv, r=r, delta=delta))
    for t, adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = adj
    output = io.StringIO()
    with redirect_stdout(output):
        print("A: terrain statistics (medians, validation and test shown separately)")
        cols = [
            "water",
            "wet",
            "landward",
            "driftwood",
            "scarp_coverage",
            "land_steep",
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
                energy_vs_A_pct=("energy_rel", "median"),
                max_roll=("max_roll", "median"),
                p95_roll=("p95_roll", "median"),
                roll_frac=("roll_frac", "median"),
                length=("length_xy", "median"),
                time=("time", "median"),
            )
            .round(6)
            .to_string()
        )
        print("\nB: TA* / TA*-S paths touching lethal cells")
        print(
            b[b.planner.isin(["TA*", "TA*-S", "TA*-S exact"])]
            .groupby("planner")
            .lethal_cells.agg(lambda x: (x > 0).sum())
            .to_string()
        )
        print("\nB: TA*-S exact minus A*, two-sided Wilcoxon; Holm over five metrics")
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
    (OUT / "beach_terrain_log.txt").write_text(text)
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
            for k in BEACH_TYPES
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
        render_detours()
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
