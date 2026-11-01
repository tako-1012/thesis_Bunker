"""Build thesis figures from archived results; only F1 reruns offline planning."""

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.exact_planners import run_planner_exact
from tapp.mapfile import load_map_file
from tapp.metrics import evaluate, resample
from tapp.real_beach import build_real, list_patches

METRICS = ("mean_cost", "climb", "p95_roll", "length_xy")
LABELS = ("Mean terrain cost", "Climb [m]", "95th-percentile roll [deg]")


def patch_pairs(root=ROOT):
    """Average both sizes within each beach, retaining paired identities."""
    data = pd.read_csv(root / "results/real_beach_las/offline.csv")
    data = data[data.planner.isin(["A*", "TA*-S exact"])]
    keys = ["kind", "debris", "side_m", "planner"]
    if data.duplicated(keys).any() or not data.success.all():
        raise ValueError("offline pairs must be unique and successful")
    expected = {r["name"] for r in list_patches("test", dataset="shizuoka_beach_las")}
    for _, group in data.groupby(["debris", "planner"]):
        if set(group.kind) != expected or len(group) != 2 * len(expected):
            raise ValueError("missing beach/size pairs")
        if not group.groupby("kind").side_m.agg(set).map(lambda s: s == {100, 200}).all():
            raise ValueError("each beach needs both 100m and 200m")
    return data.groupby(["kind", "debris", "planner"])[list(METRICS)].mean()


def comparison(root=ROOT):
    paired = patch_pairs(root)
    rows = []
    for debris in (False, True):
        group = paired.xs(debris, level="debris")
        for metric in METRICS:
            values = group[metric].unstack("planner")
            a, b = values["A*"], values["TA*-S exact"]
            delta = b.to_numpy() - a.to_numpy()
            p = float(wilcoxon(delta, alternative="two-sided").pvalue) if np.any(delta) else 1.0
            rows.append(dict(debris=debris, metric=metric, n=len(values),
                             A_median=float(a.median()) if metric != "length_xy" else np.nan,
                             TAS_median=float(b.median()) if metric != "length_xy" else np.nan,
                             delta_median=float(np.median(delta)), p=p))
    frame = pd.DataFrame(rows)
    # One Holm family: all four metrics in both debris conditions.
    order = np.argsort(frame.p.to_numpy())
    adjusted = np.minimum(1, np.maximum.accumulate((len(frame) - np.arange(len(frame))) * frame.p.to_numpy()[order]))
    frame["p_holm"] = np.empty(len(frame))
    frame.loc[order, "p_holm"] = adjusted
    return frame


def mission_summary(root=ROOT):
    missions = pd.read_csv(root / "results/online_mission/missions.csv")
    plans = pd.concat([pd.read_csv(p) for p in sorted((root / "results/online_mission").glob("plan_times_*.csv"))])
    rows = []
    for (radius, mode), g in missions[missions.prior == "stale"].groupby(["radius_m", "mode"]):
        times = plans[(plans.prior == "stale") & (plans.radius_m == radius) & (plans["mode"] == mode)].seconds
        ok = g[g.success]
        rows.append(dict(radius_m=radius, mode=mode, runs=len(g), completed=int(g.success.sum()),
                         touching=int((g.lethal_cells > 0).sum()), dJ_median=ok.dJ.median(),
                         dJ_p90=ok.dJ.quantile(.9), replans_median=g.n_replans.median(),
                         plan_s_median=times.median(), plan_s_p95=times.quantile(.95), plan_s_max=times.max()))
    return pd.DataFrame(rows), plans


def savefig(fig, output, name):
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(output / f"{name}.{ext}", dpi=160)
    plt.close(fig)


def table(frame, output, name):
    def fmt(value):
        if isinstance(value, (float, np.floating)):
            return "--" if not np.isfinite(value) else f"{value:.9g}"
        return str(value)
    header = list(frame.columns)
    rows = [[fmt(x) for x in row] for row in frame.itertuples(index=False, name=None)]
    markdown = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    markdown += ["| " + " | ".join(row) + " |" for row in rows]
    (output / f"{name}.md").write_text("\n".join(markdown) + "\n")
    escape = lambda s: s.replace("_", r"\_").replace("%", r"\%")
    latex = [r"\begin{tabular}{" + "l" * len(header) + "}", r"\hline",
             " & ".join(map(escape, header)) + r" \\", r"\hline"]
    latex += [" & ".join(map(escape, row)) + r" \\" for row in rows]
    latex += [r"\hline", r"\end{tabular}"]
    (output / f"{name}.tex").write_text("\n".join(latex) + "\n")
    frame.to_csv(output / f"{name}.csv", index=False)
    print("\n" + name)
    print(frame.to_string(index=False, float_format=lambda v: f"{v:.9g}"))


def f1(output):
    fig, axes = plt.subplots(2, 2, figsize=(10, 9))
    patches = list_patches("test", dataset="shizuoka_beach_las")[:2]
    for row, debris in enumerate((False, True)):
        for col, patch in enumerate(patches):
            sc = build_real(patch["name"], 200, 0, debris=debris, dataset="shizuoka_beach_las")
            tm, ax = sc["tmap"], axes[row, col]
            shade = LightSource(315, 45).hillshade(tm.elev.T, dx=RESOLUTION, dy=RESOLUTION)
            ax.imshow(shade, origin="lower", cmap="gray", extent=[-.25, 199.75, -.25, 199.75])
            for name in ("A*", "TA*-S"):
                result = run_planner_exact(name, sc)
                if not result["success"]:
                    raise RuntimeError("F1 planning failed")
                path = np.asarray(result["path"]) * RESOLUTION
                ax.plot(*path.T, label=name, lw=1.5)
            ax.set(title=patch["name"] + (" / debris" if debris else " / clean"), xlabel="x [m]", ylabel="y [m]")
            ax.legend()
    savefig(fig, output, "F1")


def f2(output):
    pairs = patch_pairs()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, metric, label in zip(axes, METRICS, LABELS):
        groups = []
        for debris in (False, True):
            values = pairs.xs(debris, level="debris")[metric].unstack("planner")
            groups.append((values["TA*-S exact"] - values["A*"]).to_numpy())
        ax.boxplot(groups, tick_labels=["Clean", "Debris"], showfliers=True)
        ax.axhline(0, color="gray", ls="--")
        ax.set(ylabel="TA*-S minus A*: " + label)
    savefig(fig, output, "F2")


def f3(output):
    data = pd.read_csv(ROOT / "results/real_beach_las/compare_C_online.csv")
    data.to_csv(output / "F3_statistics.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(data))
    for offset, source, label in [(-.15, "old", "Previous gridded data"), (.15, "new", "LAS point cloud")]:
        ax.plot(x + offset, data[source + "_median"], "o", label=label + " median")
        ax.plot(x + offset, data[source + "_p90"], "x", label=label + " p90")
    ax.set_xticks(x, [f"{r.variant}\n{r.side_m}m / {'debris' if r.debris else 'clean'}" for r in data.itertuples()], rotation=70, ha="right")
    ax.set_ylabel("dJ [%] vs full-truth plan")
    ax.legend(ncol=2)
    savefig(fig, output, "F3")


def f4_f5(summary, plans, output):
    fig, ax = plt.subplots(figsize=(6, 4))
    radii = sorted(summary.radius_m.unique())
    for offset, mode in [(-.18, "fixed"), (.18, "online")]:
        g = summary[summary["mode"] == mode].set_index("radius_m").loc[radii]
        ax.bar(np.arange(len(radii)) + offset, g.touching, width=.36, label=mode)
    ax.set_xticks(np.arange(len(radii)), radii)
    ax.set(xlabel="Sensing radius [m]", ylabel="Runs contacting lethal cells")
    ax.legend()
    savefig(fig, output, "F4")
    fig, ax = plt.subplots(figsize=(8, 4))
    labels, values = [], []
    stats = []
    for (prior, mode), group in plans.groupby(["prior", "mode"]):
        labels.append(prior + " / " + mode)
        values.append(group.seconds.to_numpy())
        stats.append(dict(prior=prior, mode=mode, calls=len(group), median_s=group.seconds.median(), p95_s=group.seconds.quantile(.95), max_s=group.seconds.max()))
    ax.boxplot(values, tick_labels=labels, whis=(0, 100), showfliers=False)
    ax.plot(np.arange(1, len(stats) + 1), [s["p95_s"] for s in stats], "rx", label="95th percentile")
    ax.set(ylabel="Planning time [s]", yscale="log")
    ax.secondary_yaxis("right", functions=(lambda x: x, lambda x: x)).set_ylabel("Distance travelled at 1 m/s [m]")
    ax.legend()
    savefig(fig, output, "F5")
    pd.DataFrame(stats).to_csv(output / "F5_statistics.csv", index=False)


def gazebo(output):
    online = ROOT / "results/online_mission/gazebo_claude"
    baseline = ROOT / "ros2_jazzy/gz_checks/results/claude_docker_run_las"
    old = json.loads((baseline / "results.json").read_text())
    rows = []
    columns = ["completed", "path_lethal_cells", "elapsed_s", "roll_p95_actual_deg", "pitch_p95_actual_deg", "roll_p95_map_deg", "pitch_p95_map_deg"]
    for run in old["tours"]:
        rows.append(dict(world=run["map_id"], mode="offline tour", **{k: run[k] for k in columns}))
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for run in json.loads((online / "results.json").read_text())["runs"]:
        folder = online / run["run_folder"]
        data = pd.read_csv(folder / "trajectory.csv")
        tm = load_map_file(ROOT / "maps/real_las_08OB87_-0206_200m_0_debris.npz")["tmap"]
        cells = data[["x", "y"]].to_numpy() / RESOLUTION
        predicted = evaluate(cells, tm)
        rx, ry = resample(cells)
        xi, yi = np.clip(np.rint(rx[:-1]).astype(int), 0, tm.shape[0]-1), np.clip(np.rint(ry[:-1]).astype(int), 0, tm.shape[1]-1)
        dx, dy = np.diff(rx), np.diff(ry)
        norm = np.maximum(np.hypot(dx, dy), 1e-12)
        pitch = np.degrees(np.arctan(np.abs((tm.gx[xi, yi]*dx + tm.gy[xi, yi]*dy) / norm)))
        rows.append(dict(world="real_las_08OB87_-0206 / debris", mode=run["mode"], completed=run["completed"],
                         path_lethal_cells=run["lethal_cells"], elapsed_s=float(data.t.iloc[-1]-data.t.iloc[0]),
                         roll_p95_actual_deg=float(np.percentile(np.abs(np.degrees(data.roll)), 95)),
                         pitch_p95_actual_deg=float(np.percentile(np.abs(np.degrees(data.pitch)), 95)),
                         roll_p95_map_deg=predicted["p95_roll"], pitch_p95_map_deg=float(np.percentile(pitch,95))))
        axes[0, 0].plot(data.x, data.y, label=run["mode"])
        axes[0, 1].plot(data.t-data.t.iloc[0], np.degrees(data.roll), label=run["mode"]+" roll")
        axes[0, 1].plot(data.t-data.t.iloc[0], np.degrees(data.pitch), ls="--", label=run["mode"]+" pitch")
    clean = next((baseline / "runs").glob("*_file_real_las_*"))
    data = pd.read_csv(clean / "trajectory.csv")
    mission = json.loads((clean / "mission.json").read_text())
    path = np.asarray(mission["path"])
    axes[1, 0].plot(*path.T, label="planned")
    axes[1, 0].plot(data.x, data.y, label="Gazebo LAS clean")
    for key in ("roll", "pitch"):
        axes[1, 1].plot(data.t-data.t.iloc[0], np.degrees(data[key]), label=key)
    for ax in axes[:, 0]:
        ax.set(xlabel="x [m]", ylabel="y [m]", aspect="equal")
        ax.legend()
    for ax in axes[:, 1]:
        ax.set(xlabel="Time [s]", ylabel="Attitude [deg]")
        ax.legend(fontsize=8)
    axes[0, 0].set_title("Stale map: fixed vs replanning")
    axes[1, 0].set_title("LAS clean: archived offline tour")
    savefig(fig, output, "F6")
    return pd.DataFrame(rows)


def f7(output):
    data = pd.read_csv(ROOT / "results/weight_opt.csv")
    keys = ["split", "kind", "side_m", "seed"]
    reference = data[data.planner == "A*"][keys + ["length_xy"]]
    chosen = data[(data.planner == "TA*-S") & (data.split == "test")].merge(reference, on=keys, validate="many_to_one", suffixes=("", "_A"))
    chosen["alpha"] = chosen.alpha.fillna(-1)
    chosen["length_delta_pct"] = 100 * (chosen.length_xy / chosen.length_xy_A - 1)
    summary = chosen.groupby(["w", "alpha"])[["length_delta_pct", "p95_slope"]].median().reset_index()
    fig, ax = plt.subplots(figsize=(7, 5))
    for w, group in summary.groupby("w"):
        ax.plot(group.length_delta_pct, group.p95_slope, "o-", label=f"w={w:g}")
        for row in group.itertuples():
            if row.alpha >= 0:
                ax.annotate(f"{row.alpha:g}", (row.length_delta_pct, row.p95_slope), fontsize=7)
    ax.set(xlabel="Path length difference vs A* [%] (median)", ylabel="95th-percentile slope [deg] (median)")
    ax.legend(title="Numbers: alpha", ncol=2)
    savefig(fig, output, "F7")
    summary.to_csv(output / "F7_statistics.csv", index=False)


def make_all(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    capture = io.StringIO()
    with redirect_stdout(capture):
        t1 = comparison()
        t2, plans = mission_summary()
        f1(output)
        f2(output)
        f3(output)
        f4_f5(t2, plans, output)
        t3 = gazebo(output)
        f7(output)
        for name, frame in [("T1", t1), ("T2", t2), ("T3", t3)]:
            table(frame, output, name)
        commands = []
        def letters(index):
            return letters(index // 26 - 1) + chr(65 + index % 26) if index >= 26 else chr(65 + index)
        for name, frame in [("TOne", t1), ("TTwo", t2), ("TThree", t3), ("FThree", pd.read_csv(output / "F3_statistics.csv")), ("FFive", pd.read_csv(output / "F5_statistics.csv")), ("FSeven", pd.read_csv(output / "F7_statistics.csv"))]:
            for index, row in frame.iterrows():
                for col, value in row.items():
                    if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(value):
                        key = name + letters(index) + "".join(s.title() for s in col.split("_"))
                        for digit, word in enumerate(("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine")):
                            key = key.replace(str(digit), word)
                        commands.append(f"\\newcommand{{\\{key}}}{{{float(value):.9g}}}")
        (output / "numbers.tex").write_text("\n".join(commands) + "\n")
        sources = [ROOT / "results/real_beach_las/offline.csv", ROOT / "results/real_beach_las/compare_C_online.csv", ROOT / "results/weight_opt.csv"]
        sources += [ROOT / "data/shizuoka_beach_las/index.json"]
        sources += [ROOT / "data/shizuoka_beach_las" / (row["name"] + ".npz") for row in list_patches("test", dataset="shizuoka_beach_las")[:2]]
        sources += sorted((ROOT / "results/online_mission").glob("*.csv"))
        for folder in [ROOT / "results/online_mission/gazebo_claude", ROOT / "ros2_jazzy/gz_checks/results/claude_docker_run_las"]:
            sources += sorted(folder.rglob("trajectory.csv")) + sorted(folder.rglob("mission.json")) + [folder / "results.json"]
        (output / "sources.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2) + "\n")
    log = capture.getvalue()
    (output / "figures_log.txt").write_text(log)
    print(log, end="")
    return t1, t2, t3


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "thesis/out")
    make_all(parser.parse_args().output)
