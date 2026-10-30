"""Fixed task-014 LAS tours: idealized radius sensing, prior-fixed order and exact TA*-S."""

import argparse
from contextlib import redirect_stdout
import io
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.collision import path_lethal_cells
from tapp.real_beach import build_real, list_patches
from tapp.prior import coarse_prior, coarse_elevation, PriorMap
from tapp.traversability import TraversabilityMap
from tapp.tour import sample_waypoints
from tapp.online_mission import ordered_tour, run_online_mission, run_fixed_mission
from experiments.beach_terrain import metrics

OUT = ROOT / "results/online_mission"


def scenarios(row):
    clean = build_real(row["name"], 200, 0, dataset="shizuoka_beach_las")
    stale = build_real(row["name"], 200, 0, debris=True, dataset="shizuoka_beach_las")
    points = {}
    # Use the first five of the same 12-point draw as task 009(D).
    for name, sc in [("clean", clean), ("stale", stale)]:
        seed = np.random.SeedSequence([0, 3000, 200, sc["patch_index"]])
        points[name] = sample_waypoints(sc, 12, seed)[:5]
    return clean, stale, points


def run_patch(row):
    began = time.perf_counter()
    clean, stale, points = scenarios(row)
    coarse = coarse_prior(clean["tmap"], 10)
    coarse_tm = TraversabilityMap(
        coarse_elevation(clean["tmap"], 10),
        np.zeros(clean["tmap"].shape, bool),
        clean["tmap"].robot,
        clean["tmap"].weights,
    )
    rows, plans, traces, details = [], [], {}, {}
    references = {}
    for name, sc in [("clean", clean), ("stale", stale)]:
        tm = sc["tmap"]
        tour = ordered_tour(tm, sc["start"], points[name])
        result = run_online_mission(
            tm,
            PriorMap(tm.cost, tm.lethal, RESOLUTION),
            sc["start"],
            tour["stops"],
            radius_m=10,
            prior_lethal_mode="hard",
        )
        if not result["success"]:
            raise RuntimeError("full-truth oracle failed: " + row["name"] + " " + name)
        references[name] = metrics(result["traj"], tm)["J"]
        details[name] = dict(
            start=sc["start"],
            points=points[name],
            oracle_order=tour["order"],
            oracle_J=references[name],
            oracle_plan_times=result["plan_times"],
        )
    for prior_name in ["oracle", "coarse c10", "stale"]:
        sc = stale if prior_name == "stale" else clean
        truth = sc["tmap"]
        prior_tm = (
            clean["tmap"]
            if prior_name == "stale"
            else (coarse_tm if prior_name == "coarse c10" else truth)
        )
        prior = (
            coarse
            if prior_name == "coarse c10"
            else PriorMap(prior_tm.cost, prior_tm.lethal, RESOLUTION)
        )
        terrain_name = "stale" if prior_name == "stale" else "clean"
        try:
            tour = ordered_tour(prior_tm, sc["start"], points[terrain_name])
        except ValueError as exc:
            tour = None
            ordering_error = str(exc)
        details[prior_name + "_order"] = None if tour is None else tour["order"]
        for radius in [5, 10, 15]:
            for mode in (["online", "fixed"] if prior_name == "stale" else ["online"]):
                key = prior_name.replace(" ", "_") + f"_R{radius}_{mode}"
                base = dict(
                    patch=row["name"],
                    side_m=200,
                    seed=0,
                    prior=prior_name,
                    radius_m=radius,
                    mode=mode,
                )
                if tour is None:
                    rows.append(
                        dict(
                            base,
                            success=False,
                            reason="prior_order: " + ordering_error,
                            n_plans=0,
                            n_replans=0,
                            lethal_cells=0,
                            contact_audited=False,
                            oracle_J=references[terrain_name],
                        )
                    )
                    continue
                if mode == "fixed":
                    result = run_fixed_mission(prior_tm, sc["start"], tour["stops"])
                else:
                    result = run_online_mission(
                        truth,
                        prior,
                        sc["start"],
                        tour["stops"],
                        radius_m=radius,
                        prior_lethal_mode="hard" if prior_name == "oracle" else "soft",
                    )
                hits = len(path_lethal_cells(result["traj"], truth.lethal))
                # Count contact with inflated debris separately from other lethal cells.
                debris_mask = (
                    truth.rock & ~clean["tmap"].rock
                    if prior_name == "stale"
                    else np.zeros(truth.shape, bool)
                )
                debris_hits = len(path_lethal_cells(result["traj"], debris_mask))
                out = dict(
                    base,
                    success=result["success"],
                    reason=result["reason"],
                    n_plans=result["n_plans"],
                    n_replans=result["n_replans"],
                    lethal_cells=hits,
                    debris_cells=debris_hits,
                    contact_audited=True,
                    oracle_J=references[terrain_name],
                    order=json.dumps(tour["order"]),
                )
                if result["success"]:
                    out.update(metrics(result["traj"], truth))
                    out["dJ"] = 100 * (out["J"] / references[terrain_name] - 1)
                rows.append(out)
                plans.extend(
                    dict(base, call=i, seconds=value)
                    for i, value in enumerate(result["plan_times"])
                )
                traces[key] = np.asarray(result["traj"], float)
                details[key + "_legs"] = result["legs"]
    return dict(
        rows=rows,
        plans=plans,
        traces=traces,
        details=details,
        elapsed_s=time.perf_counter() - began,
    )


def table(title, frame):
    print("\n" + title)
    print(frame.to_string(index=False, float_format=lambda x: f"{x:.6g}"))


def summarize(folder, runtime):
    data = pd.read_csv(folder / "missions.csv")
    timings = pd.concat(
        [pd.read_csv(p) for p in sorted(folder.glob("plan_times_*.csv"))],
        ignore_index=True,
    )
    rows = []
    for key, g in data.groupby(["prior", "radius_m", "mode"], sort=False):
        prior, radius, mode = key
        times = timings[
            (timings.prior == prior)
            & (timings.radius_m == radius)
            & (timings["mode"] == mode)
        ].seconds
        ok = g[g.success]
        rows.append(
            dict(
                prior=prior,
                radius_m=radius,
                mode=mode,
                runs=len(g),
                completed=int(g.success.sum()),
                failed=int((~g.success).sum()),
                contact_audited=int(g.contact_audited.sum()),
                touching=int((g.lethal_cells > 0).sum()),
                debris_touching=int((g.debris_cells.fillna(0) > 0).sum()),
                dJ_median=ok.dJ.median(),
                dJ_p90=ok.dJ.quantile(0.9),
                dJ_max=ok.dJ.max(),
                replans_median=g.n_replans.median(),
                replans_max=g.n_replans.max(),
                plan_calls=len(times),
                plan_s_median=times.median(),
                plan_s_p95=times.quantile(0.95),
                plan_s_max=times.max(),
                calls_over_1s=int((times > 1).sum()),
            )
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(folder / "summary.csv", index=False)
    table(
        "Task 014: J vs full-truth oracle, same truth/waypoints; bad tail=p90; metres/grid=0.5",
        summary,
    )
    failure = (
        data[~data.success]
        .groupby(["prior", "radius_m", "mode", "reason"])
        .size()
        .reset_index(name="runs")
    )
    failure.to_csv(folder / "failures.csv", index=False)
    table("Incomplete tours and reasons", failure)
    table(
        "Stale map: fixed prior-only paths versus online replanning; contacts include failed runs",
        summary[summary.prior == "stale"],
    )
    table("Measured wall times [s]", pd.DataFrame([runtime]))
    print(
        "Sensing is perfect radius visibility of the fixed truth map, without LiDAR, occlusion or sensor error. Movement follows the polyline exactly; asynchronous latency, tracking and physics are not modeled here."
    )
    print(
        "Tour order is fixed on each prior before departure. Stale uses debris truth waypoints; its denominator is a separately executed full-truth oracle on those same waypoints. Oracle uses hard truth obstacles; coarse/stale use the unchanged soft-prior policy."
    )
    print(
        "Planning times cover A* search and exact cost-aware smoothing, excluding map assembly, sensing and tour ordering. At 1m/s, planning_s seconds corresponds to planning_s metres travelled; these CPU-load-dependent measurements alone do not prove real-time safety."
    )


def figures(folder, results):
    candidates = []
    for result in results:
        row = next(
            r
            for r in result["rows"]
            if r["prior"] == "stale" and r["radius_m"] == 10 and r["mode"] == "fixed"
        )
        if row["contact_audited"]:
            candidates.append((row["debris_cells"], row["patch"], result))
    for index, (_, name, result) in enumerate(
        sorted(candidates, key=lambda a: (-a[0], a[1]))[:3], 1
    ):
        sc = build_real(name, 200, 0, debris=True, dataset="shizuoka_beach_las")
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True)
        for ax, mode in zip(axes, ["fixed", "online"]):
            tm = sc["tmap"]
            ax.imshow(
                tm.cost.T,
                origin="lower",
                extent=[0, 200, 0, 200],
                cmap="YlOrBr",
                vmin=0,
                vmax=1,
            )
            ax.contour(
                tm.lethal.T,
                levels=[0.5],
                colors=["gray"],
                linewidths=0.3,
                extent=[0, 200, 0, 200],
            )
            path = result["traces"][f"stale_R10_{mode}"] * RESOLUTION
            ax.plot(
                path[:, 0],
                path[:, 1],
                color="tab:blue" if mode == "online" else "tab:red",
                lw=1,
            )
            row = next(
                r
                for r in result["rows"]
                if r["prior"] == "stale" and r["radius_m"] == 10 and r["mode"] == mode
            )
            ax.set_title(
                f'{mode}: contacts={row["lethal_cells"]}, debris={row["debris_cells"]}'
            )
            ax.set(xlabel="x [m]", ylabel="y [m]")
        fig.suptitle(name + ": prior-fixed order, stale R10")
        fig.tight_layout()
        fig.savefig(folder / f"stale_example_{index:02}.png", dpi=130)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=min(5, os.cpu_count() or 1))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    rows = list_patches("test", dataset="shizuoka_beach_las")
    results = []
    with Pool(args.workers) as pool:
        for row, result in zip(rows, pool.imap(run_patch, rows)):
            results.append(result)
            print(
                f'{row["name"]}: {len(results)}/{len(rows)} ({time.perf_counter()-start:.1f}s)',
                file=sys.stderr,
                flush=True,
            )
            traces = OUT / "traces"
            traces.mkdir(exist_ok=True)
            np.savez_compressed(traces / (row["name"] + ".npz"), **result["traces"])
            (traces / (row["name"] + ".json")).write_text(
                json.dumps(result["details"], indent=2) + "\n"
            )
    compute_s = time.perf_counter() - start
    data = pd.DataFrame([r for result in results for r in result["rows"]])
    data.to_csv(OUT / "missions.csv", index=False)
    plans = pd.DataFrame([r for result in results for r in result["plans"]])
    for prior, g in plans.groupby("prior"):
        g.to_csv(OUT / ("plan_times_" + prior.replace(" ", "_") + ".csv"), index=False)
    before = time.perf_counter()
    figures(OUT, results)
    runtime = dict(
        compute_wall_s=compute_s,
        figures_wall_s=time.perf_counter() - before,
        total_wall_s=time.perf_counter() - start,
        workers=args.workers,
    )
    (OUT / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
    stream = io.StringIO()
    with redirect_stdout(stream):
        summarize(OUT, runtime)
    log = stream.getvalue()
    (OUT / "online_mission_log.txt").write_text(log)
    print(log, end="")


if __name__ == "__main__":
    main()
