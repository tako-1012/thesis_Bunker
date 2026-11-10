"""ICAROB abstract figure: A* vs TA*-S exact on one real (LAS) beach, 200 m, no debris.

Scenario choice follows rules fixed before drawing (recorded in the log):
  rule_first : first test patch, in list_patches order, whose A* path crosses >25 deg cells
               (steep_len > 0 in results/real_beach_las/offline.csv)  -- the requested rule
  rule_max   : test patch whose A* path crosses the longest >25 deg distance (worst case),
               drawn only as a clearly labelled alternative
Paths are recomputed with the task013 settings and checked against offline.csv.
Existing results are read only.  No energy values are reported.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.real_beach import list_patches, build_real
from tapp.config import DEFAULT_W, RESOLUTION, CostWeights, Robot
from tapp.exact_planners import run_planner_exact
from tapp.scenario import run_planner
from experiments.beach_terrain import metrics

DATASET, SIDE = "shizuoka_beach_las", 200
OUT = ROOT / "results/abstract_figure"
OFFLINE = ROOT / "results/real_beach_las/offline.csv"
KEYS = ["length_xy", "mean_cost", "climb", "steep_len", "J"]
STEEP = Robot().max_slope_deg


def choose(offline):
    order = [r["name"] for r in list_patches("test", dataset=DATASET)]
    a = offline[(offline.side_m == SIDE) & (~offline.debris) & (offline.planner == "A*") & offline.success]
    a = a.set_index("kind").loc[[n for n in order if n in set(a.kind)]]
    first = next(n for n in a.index if a.loc[n, "steep_len"] > 0)
    worst = a["steep_len"].idxmax()
    return dict(rule_first=first, rule_max=worst), a["steep_len"]


def paths_for(name, offline):
    sc = build_real(name, SIDE, 0, debris=False, dataset=DATASET)
    tm = sc["tmap"]
    out = {}
    for label, run in [("A*", lambda: run_planner("A*", sc, w=DEFAULT_W)),
                       ("TA*-S", lambda: run_planner_exact("TA*-S", sc, w=DEFAULT_W))]:
        r = run()
        if not r["success"]:
            raise RuntimeError(f"{name} {label}: no path")
        m = metrics(r["path"], tm)
        ref = offline[(offline.kind == name) & (offline.side_m == SIDE) & (~offline.debris)
                      & (offline.planner == ("A*" if label == "A*" else "TA*-S exact"))].iloc[0]
        check = {k: (float(m[k]), float(ref[k]), bool(np.isclose(m[k], ref[k], rtol=1e-9, atol=1e-9))) for k in KEYS}
        out[label] = dict(path=np.asarray(r["path"], float), metrics={k: float(m[k]) for k in KEYS}, check=check)
    return sc, out


def square_window(paths, n, margin_m=8.0):
    pts = np.vstack([(p["path"] + 0.5) * RESOLUTION for p in paths.values()])
    lo, hi = pts.min(axis=0) - margin_m, pts.max(axis=0) + margin_m
    side = max(hi - lo)
    centre = (lo + hi) / 2
    lo = np.clip(centre - side / 2, 0, n * RESOLUTION - side)
    return lo, lo + side


def draw(sc, paths, path_png, path_pdf):
    tm = sc["tmap"]
    n = tm.shape[0]
    extent = [0, n * RESOLUTION, 0, n * RESOLUTION]
    plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans"})
    # Drawn at print size: the abstract box is about 4.5 cm (1.8 in) wide.
    fig, ax = plt.subplots(figsize=(1.8, 1.8))
    slope = np.clip(tm.slope, 0, STEEP)
    ax.imshow(slope.T, origin="lower", extent=extent, cmap="Greys", vmin=0, vmax=STEEP * 1.25)
    layers = [(tm.slope > STEEP, "#d62728"),        # steep > 25 deg: red
              (sc["water"], "#9ecae1"),             # sea: light blue
              (sc["nodata"], "#c7b9e3")]            # no data: light purple
    for mask, colour in layers:
        ax.imshow(np.ma.masked_where(~mask.T, mask.T), origin="lower", extent=extent,
                  cmap=ListedColormap([colour]), vmin=0, vmax=1, interpolation="nearest")
    style = {"A*": dict(color="#0072B2", ls=(0, (3, 1.5)), lw=1.4), "TA*-S": dict(color="#E69F00", ls="-", lw=1.4)}
    for label in ["A*", "TA*-S"]:
        p = (paths[label]["path"] + 0.5) * RESOLUTION
        ax.plot(p[:, 0], p[:, 1], label=label, **style[label])
    start = (paths["A*"]["path"][0] + 0.5) * RESOLUTION
    goal = (paths["A*"]["path"][-1] + 0.5) * RESOLUTION
    ax.plot(*start, marker="o", ms=5, mfc="white", mec="black", mew=1.0, ls="none")
    ax.plot(*goal, marker="*", ms=8, mfc="black", mec="white", mew=0.5, ls="none")
    ax.annotate("S", start, xytext=(3, 3), textcoords="offset points", fontsize=8, weight="bold")
    ax.annotate("G", goal, xytext=(3, 3), textcoords="offset points", fontsize=8, weight="bold")
    lo, hi = square_window(paths, n)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    side = hi[0] - lo[0]
    bar = 20.0 if side > 60 else 10.0
    x0, y0 = lo[0] + 0.05 * side, lo[1] + 0.05 * side
    ax.plot([x0, x0 + bar], [y0, y0], color="black", lw=2, solid_capstyle="butt")
    ax.text(x0 + bar / 2, y0 + 0.025 * side, f"{bar:.0f} m", ha="center", va="bottom", fontsize=7,
            bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9, handlelength=2.0, borderpad=0.3, labelspacing=0.2)
    fig.tight_layout(pad=0.05)
    fig.savefig(path_png, dpi=300)
    fig.savefig(path_pdf)
    plt.close(fig)
    return lo, hi


def _background(ax, sc):
    tm = sc["tmap"]
    n = tm.shape[0]
    extent = [0, n * RESOLUTION, 0, n * RESOLUTION]
    ax.imshow(np.clip(tm.slope, 0, STEEP).T, origin="lower", extent=extent, cmap="Greys", vmin=0, vmax=STEEP * 1.25)
    for mask, colour in [(tm.slope > STEEP, "#d62728"), (sc["water"], "#9ecae1"), (sc["nodata"], "#c7b9e3")]:
        ax.imshow(np.ma.masked_where(~mask.T, mask.T), origin="lower", extent=extent,
                  cmap=ListedColormap([colour]), vmin=0, vmax=1, interpolation="nearest")


def _scalebar(ax, lo, hi, bar, right=False):
    w, h = hi[0] - lo[0], hi[1] - lo[1]
    x0, y0 = (hi[0] - 0.04 * w - bar if right else lo[0] + 0.04 * w), lo[1] + 0.08 * h
    ax.plot([x0, x0 + bar], [y0, y0], color="black", lw=2, solid_capstyle="butt")
    ax.text(x0 + bar / 2, y0 + 0.04 * h, f"{bar:.0f} m", ha="center", va="bottom", fontsize=7,
            bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.5))


def draw_zoom(sc, paths, path_png, path_pdf, zoom_lo, zoom_hi, margin_m=10.0):
    """Square panel: whole route as a strip (top) and an enlarged window where the paths part (bottom)."""
    pts = np.vstack([(p["path"] + 0.5) * RESOLUTION for p in paths.values()])
    lo, hi = pts.min(axis=0) - margin_m, pts.max(axis=0) + margin_m
    zoom_lo, zoom_hi = np.asarray(zoom_lo, float), np.asarray(zoom_hi, float)
    plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans"})
    top_h = (hi[1] - lo[1]) / (hi[0] - lo[0])
    bottom_h = (zoom_hi[1] - zoom_lo[1]) / (zoom_hi[0] - zoom_lo[0])
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(1.8, 1.8), gridspec_kw=dict(height_ratios=[top_h, bottom_h]))
    style = {"A*": dict(color="#0072B2", ls=(0, (3, 1.5)), lw=1.4), "TA*-S": dict(color="#E69F00", ls="-", lw=1.4)}
    for ax, (a, b) in [(top, (lo, hi)), (bottom, (zoom_lo, zoom_hi))]:
        _background(ax, sc)
        for label in ["A*", "TA*-S"]:
            p = (paths[label]["path"] + 0.5) * RESOLUTION
            ax.plot(p[:, 0], p[:, 1], label=label, **dict(style[label], lw=style[label]["lw"] * (0.8 if ax is top else 1)))
        ax.set_xlim(a[0], b[0])
        ax.set_ylim(a[1], b[1])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    start = (paths["A*"]["path"][0] + 0.5) * RESOLUTION
    goal = (paths["A*"]["path"][-1] + 0.5) * RESOLUTION
    top.plot(*start, marker="o", ms=4, mfc="white", mec="black", mew=0.8, ls="none")
    top.plot(*goal, marker="*", ms=6, mfc="black", mec="white", mew=0.4, ls="none")
    top.annotate("S", start, xytext=(1, -3), textcoords="offset points", ha="left", va="top", fontsize=7, weight="bold")
    top.annotate("G", goal, xytext=(2, 2), textcoords="offset points", fontsize=7, weight="bold")
    # Outline of the enlarged window, clipped to the strip so all four edges show.
    r_lo = np.maximum(zoom_lo, lo + 0.6)
    r_hi = np.minimum(zoom_hi, hi - 0.6)
    top.add_patch(plt.Rectangle(r_lo, *(r_hi - r_lo), fill=False, ec="black", lw=0.8))
    _scalebar(top, lo, hi, 20.0)
    _scalebar(bottom, zoom_lo, zoom_hi, 10.0, right=True)
    bottom.legend(loc="upper right", fontsize=8, framealpha=0.9, handlelength=2.0, borderpad=0.3, labelspacing=0.2)
    fig.tight_layout(pad=0.05, h_pad=0.2)
    fig.savefig(path_png, dpi=300)
    fig.savefig(path_pdf)
    plt.close(fig)
    return lo, hi


# Enlarged window for the requested rule-1 figure: where the paths part and >25 deg cells lie
# (steep cells near the route are at x 60-120 m); fixed by geometry, not by any result.
ZOOM = dict(rule_first=((55.0, 99.0), (125.0, 149.0)))


def main_zoom():
    offline = pd.read_csv(OFFLINE)
    chosen, _ = choose(offline)
    name = chosen["rule_first"]
    sc, paths = paths_for(name, offline)
    if not all(c[2] for p in paths.values() for c in p["check"].values()):
        raise RuntimeError("recomputed paths differ from offline.csv")
    stem = OUT / f"astar_vs_tas_rule_first_{name}_zoom"
    lo, hi = draw_zoom(sc, paths, stem.with_suffix(".png"), stem.with_suffix(".pdf"), *ZOOM["rule_first"])
    zl, zh = ZOOM["rule_first"]
    text = (f"[rule_first zoom] {name}: same paths as rule_first (offline.csv match True).\n"
            f"  top strip: path bounding box + 10 m, x {lo[0]:.1f}-{hi[0]:.1f} m, y {lo[1]:.1f}-{hi[1]:.1f} m (20 m bar)\n"
            f"  bottom: enlarged x {zl[0]:.0f}-{zh[0]:.0f} m, y {zl[1]:.0f}-{zh[1]:.0f} m (10 m bar), rectangle on the strip\n"
            "  A 1:1 crop of the path bounding box + 10 m would be about 169 m square (paths span ~149 m x ~21 m),\n"
            "  no larger than the original figure, so the route is shown as a strip plus an enlarged window.\n")
    (OUT / "abstract_figure_zoom_log.txt").write_text(text)
    print(text)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    offline = pd.read_csv(OFFLINE)
    chosen, steep = choose(offline)
    lines = ["Task: ICAROB abstract figure (A* vs TA*-S exact), shizuoka_beach_las test, 200 m, seed 0, no debris.",
             f"Settings as task013: w={DEFAULT_W}, alpha={CostWeights().alpha}, steep threshold {STEEP} deg.",
             "Rules fixed before drawing:",
             "  rule_first: first test patch (list_patches order) whose A* path crosses >25 deg cells (offline.csv steep_len > 0).",
             "  rule_max  : test patch whose A* path crosses the longest >25 deg distance (alternative; worst case, label as such).",
             "A* steep_len [m] per test patch in order: " + json.dumps({k: round(float(v), 2) for k, v in steep.items()}),
             f"Selected: rule_first={chosen['rule_first']}, rule_max={chosen['rule_max']}", ""]
    record = {}
    for rule, name in chosen.items():
        sc, paths = paths_for(name, offline)
        stem = OUT / f"astar_vs_tas_{rule}_{name}"
        lo, hi = draw(sc, paths, stem.with_suffix(".png"), stem.with_suffix(".pdf"))
        lines.append(f"[{rule}] {name}  window x {lo[0]:.1f}-{hi[0]:.1f} m, y {lo[1]:.1f}-{hi[1]:.1f} m")
        lines.append(f"  {'planner':8s} {'length_xy[m]':>12s} {'mean_cost':>10s} {'climb[m]':>9s} {'steep_len[m]':>12s} {'J':>9s}  offline.csv match")
        for label, p in paths.items():
            m = p["metrics"]
            ok = all(c[2] for c in p["check"].values())
            lines.append(f"  {label:8s} {m['length_xy']:12.2f} {m['mean_cost']:10.4f} {m['climb']:9.2f} {m['steep_len']:12.2f} {m['J']:9.1f}  {ok}")
            if not ok:
                lines.append("    mismatch: " + json.dumps(p["check"]))
        record[rule] = dict(patch=name, **{k: p["metrics"] for k, p in paths.items()})
        lines.append("")
    lines.append("mean_cost = mean robot-normalised terrain cost along the path; J = length_xy*(1+w*mean_cost); climb = summed ascent;")
    lines.append("steep_len = path length on >25 deg cells. Colours: grey slope, red >25 deg, light blue sea, light purple no data;")
    lines.append("A* blue dashed, TA*-S orange solid (Okabe-Ito). No energy values.")
    (OUT / "abstract_figure_log.txt").write_text("\n".join(lines) + "\n")
    (OUT / "abstract_figure_values.json").write_text(json.dumps(record, indent=2) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main_zoom() if "--zoom" in sys.argv else main()
