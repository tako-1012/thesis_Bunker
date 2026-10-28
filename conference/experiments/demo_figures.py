#!/usr/bin/env python3
"""Illustrative figures: what the planners actually do on one map per terrain.

For each terrain (100 m map, test seed 0) and for one infeasible 'wall' map:
  (a) top view of the slope map with lethal cells and the A* / TA*-S paths,
  (b) 3D view of the terrain with both paths,
  (c) slope under the robot along each path, with the 25 deg limit.

Usage (from conference/):  python3 experiments/demo_figures.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402
from matplotlib.colors import ListedColormap         # noqa: E402
from scipy.ndimage import map_coordinates            # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp.config import RESOLUTION                                       # noqa: E402
from tapp.config import DEFAULT_W                                   # noqa: E402
from tapp.metrics import resample                                        # noqa: E402
from tapp.scenario import build, build_infeasible, run_planner           # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "paper", "figures", "demo")
W = DEFAULT_W
COLOR = {"A*": "#eda100", "TA*-S": "#eb6834"}
INK, MUTED = "#222222", "#6b6b6b"
TITLE = {"hills": "Hills", "ridge": "Ridge with passes", "craters": "Craters",
         "rocky": "Rocky", "wall": "Wall without pass (infeasible)"}

plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.labelcolor": INK, "savefig.dpi": 200,
                     "axes.spines.top": False, "axes.spines.right": False})

# sequential single-hue ramp for slope (light -> dark blue)
SLOPE_CMAP = ListedColormap(plt.get_cmap("Blues")(np.linspace(0.08, 0.75, 256)))


def along(path, tm):
    x, y = resample(path)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))]) * RESOLUTION
    z = map_coordinates(tm.elev, [x, y], order=1, mode="nearest")
    xi = np.clip(np.rint(x).astype(int), 0, tm.shape[0] - 1)
    yi = np.clip(np.rint(y).astype(int), 0, tm.shape[1] - 1)
    return x, y, z, s, tm.slope[xi, yi]


def figure(sc, name):
    tm = sc["tmap"]
    n = tm.shape[0]
    L = n * RESOLUTION
    res = {p: run_planner(p, sc, w=W) for p in ("A*", "TA*-S")}

    fig = plt.figure(figsize=(13, 4.9))
    ax1 = fig.add_subplot(1, 3, 1)
    ax2 = fig.add_subplot(1, 3, 2, projection="3d")
    ax3 = fig.add_subplot(1, 3, 3)

    # (a) top view
    ext = [0, L, 0, L]
    im = ax1.imshow(np.clip(tm.slope, 0, 40).T, origin="lower", extent=ext, cmap=SLOPE_CMAP, vmin=0, vmax=40)
    ax1.imshow(np.ma.masked_where(~tm.lethal.T, tm.lethal.T), origin="lower", extent=ext,
               cmap=ListedColormap(["#3a3a3a"]), alpha=0.85)
    cb = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.02)
    cb.set_label("slope [deg]")
    for p, r in res.items():
        if not r["success"]:
            continue
        x, y, z, s, sl = along(r["path"], tm)
        X, Y = (x + 0.5) * RESOLUTION, (y + 0.5) * RESOLUTION
        ax1.plot(X, Y, color="white", lw=4.0, solid_capstyle="round")
        ax1.plot(X, Y, color=COLOR[p], lw=2.0, label=p, solid_capstyle="round")
        if p == "A*":
            bad = sl > tm.robot.max_slope_deg
            ax1.plot(X[bad], Y[bad], "x", color="#d03b3b", ms=4, mew=1.2,
                     label="A* on slope > 25 deg")
    for c, mk, lab in ((sc["start"], "o", "start"), (sc["goal"], "*", "goal")):
        ax1.plot((c[0] + 0.5) * RESOLUTION, (c[1] + 0.5) * RESOLUTION, mk, color="white",
                 mec=INK, ms=11, mew=1.2, label=lab)
    ax1.plot([], [], "s", color="#3a3a3a", ms=8, label="not traversable")
    ax1.set_xlabel("x [m]")
    ax1.set_ylabel("y [m]")
    ax1.set_title("(a) slope map and paths", color=INK)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, fontsize=7.5, frameon=False)

    # (b) 3D view
    step = max(n // 100, 1)
    g = (np.arange(0, n, step) + 0.5) * RESOLUTION
    GX, GY = np.meshgrid(g, g, indexing="ij")
    Z = tm.elev[::step, ::step]
    ax2.plot_surface(GX, GY, Z, cmap="Greys", linewidth=0, antialiased=True, alpha=0.75,
                     rstride=1, cstride=1, vmin=Z.min() - 0.3 * np.ptp(Z), vmax=Z.max())
    for p, r in res.items():
        if r["success"]:
            x, y, z, s, sl = along(r["path"], tm)
            ax2.plot((x + 0.5) * RESOLUTION, (y + 0.5) * RESOLUTION, z + 0.03 * L, color=COLOR[p], lw=2.6,
                     zorder=10)
    ax2.set_xlabel("x [m]")
    ax2.set_ylabel("y [m]")
    ax2.zaxis.set_major_locator(plt.MaxNLocator(3))
    ax2.tick_params(labelsize=7)
    ax2.view_init(elev=38, azim=-60)
    ax2.set_box_aspect((1, 1, 0.35))
    ax2.set_title("(b) 3D view (z: height [m])", color=INK)

    # (c) slope along path
    for p, r in res.items():
        if r["success"]:
            x, y, z, s, sl = along(r["path"], tm)
            ax3.plot(s, sl, color=COLOR[p], lw=1.4,
                     label=f"{p} (length {s[-1]:.0f} m, max {sl.max():.0f} deg)")
        else:
            ax3.text(0.03, 0.72, f"{p}: no feasible path\n(reported after {r['time']:.2f} s)",
                     transform=ax3.transAxes, ha="left", va="top", color=INK,
                     bbox=dict(boxstyle="round", fc="white", ec=COLOR[p]))
    ax3.axhline(tm.robot.max_slope_deg, color="#d03b3b", lw=1.0, ls="--")
    ax3.text(0.99, tm.robot.max_slope_deg + 0.8, "robot limit 25 deg", color="#d03b3b",
             ha="right", transform=ax3.get_yaxis_transform(), fontsize=8)
    ax3.set_xlabel("distance along path [m]")
    ax3.set_ylabel("slope under robot [deg]")
    ax3.set_ylim(0, max(55, ax3.get_ylim()[1]))
    ax3.set_title("(c) slope along each path", color=INK)
    ax3.grid(True, color="#e4e4e4", lw=0.5)
    ax3.legend(loc="upper left", fontsize=7.5, frameon=False)

    fig.suptitle(TITLE[sc["kind"]] + f"  ({L:.0f} m x {L:.0f} m)", color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(OUT, f"demo_{name}.png"))
    plt.close(fig)
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    for kind in ("hills", "ridge", "craters", "rocky"):
        figure(build(kind, 100, 0), kind)
        print("wrote", kind)
    figure(build_infeasible(100, 0), "wall_infeasible")
    print("wrote wall_infeasible")


if __name__ == "__main__":
    main()
