#!/usr/bin/env python3
"""Illustrative figure for the roll-aware extension (not used in the paper).

Top view of the slope map with the isotropic TA*-S and the roll-aware TA*-S-R
paths, and the roll angle along each path.

Usage (from conference/):  python3 experiments/demo_roll.py [kind] [seed]
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402
from matplotlib.colors import ListedColormap         # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp.aniso import DirectionalCost, astar_roll, smooth_roll   # noqa: E402
from tapp.config import DEFAULT_W, RESOLUTION                      # noqa: E402
from tapp.metrics import resample                                  # noqa: E402
from tapp.scenario import build, run_planner                       # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "paper", "figures", "demo")
COLOR = {"TA*-S (isotropic)": "#2a78d6", "TA*-S-R (roll-aware)": "#eb6834"}
INK, MUTED = "#222222", "#6b6b6b"
SLOPE_CMAP = ListedColormap(plt.get_cmap("Blues")(np.linspace(0.08, 0.75, 256)))


def roll_along(path, tm):
    x, y = resample(path)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))]) * RESOLUTION
    hx, hy = np.diff(x), np.diff(y)
    hn = np.maximum(np.hypot(hx, hy), 1e-12)
    xi = np.clip(np.rint(x[:-1]).astype(int), 0, tm.shape[0] - 1)
    yi = np.clip(np.rint(y[:-1]).astype(int), 0, tm.shape[1] - 1)
    roll = np.degrees(np.arctan(np.abs(tm.gx[xi, yi] * hy / hn - tm.gy[xi, yi] * hx / hn)))
    return x, y, s[:-1], roll


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "craters"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    sc = build(kind, 100, seed)
    tm = sc["tmap"]
    iso = run_planner("TA*-S", sc, w=DEFAULT_W)["path"]
    dc = DirectionalCost(tm, w=DEFAULT_W)
    r = astar_roll(dc, sc["start"], sc["goal"])
    rr, _ = smooth_roll(r["path"], dc)
    paths = {"TA*-S (isotropic)": iso, "TA*-S-R (roll-aware)": rr}
    lim = tm.robot.max_roll_deg

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    L = tm.shape[0] * RESOLUTION
    im = a1.imshow(np.clip(tm.slope, 0, 40).T, origin="lower", extent=[0, L, 0, L], cmap=SLOPE_CMAP,
                   vmin=0, vmax=40)
    a1.imshow(np.ma.masked_where(~tm.lethal.T, tm.lethal.T), origin="lower", extent=[0, L, 0, L],
              cmap=ListedColormap(["#3a3a3a"]), alpha=0.85)
    fig.colorbar(im, ax=a1, fraction=0.046, pad=0.02).set_label("slope [deg]")
    for name, p in paths.items():
        x, y, s, roll = roll_along(p, tm)
        X, Y = (x + 0.5) * RESOLUTION, (y + 0.5) * RESOLUTION
        a1.plot(X, Y, color="white", lw=4)
        a1.plot(X, Y, color=COLOR[name], lw=2, label=name)
        bad = np.concatenate([roll > lim, [False]])
        if bad.any():
            a1.plot(X[bad], Y[bad], "x", color="#d03b3b", ms=4, mew=1.2)
        a2.plot(s, roll, color=COLOR[name], lw=1.4,
                label=f"{name}: max roll {roll.max():.0f} deg, length {s[-1]:.0f} m")
    a1.plot([], [], "x", color="#d03b3b", label=f"roll > {lim:g} deg")
    for c, mk in ((sc["start"], "o"), (sc["goal"], "*")):
        a1.plot((c[0] + 0.5) * RESOLUTION, (c[1] + 0.5) * RESOLUTION, mk, color="white", mec=INK, ms=11, mew=1.2)
    a1.set_xlabel("x [m]")
    a1.set_ylabel("y [m]")
    a1.set_title("(a) slope map and paths", color=INK)
    a1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=8, frameon=False)
    a2.axhline(lim, color="#d03b3b", ls="--", lw=1)
    a2.text(0.99, lim + 0.5, f"assumed roll limit {lim:g} deg", color="#d03b3b", ha="right",
            transform=a2.get_yaxis_transform(), fontsize=8)
    a2.set_xlabel("distance along path [m]")
    a2.set_ylabel("roll angle [deg]")
    a2.set_title("(b) roll along each path", color=INK)
    a2.grid(True, color="#e4e4e4", lw=0.5)
    a2.spines[["top", "right"]].set_visible(False)
    a2.legend(loc="upper right", fontsize=8, frameon=False, bbox_to_anchor=(1.0, 0.92))
    fig.suptitle(f"Roll-aware planning: {kind} (100 m x 100 m)", color=INK)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, f"demo_roll_{kind}.png"), dpi=200)
    print("wrote", os.path.join(OUT, f"demo_roll_{kind}.png"))


if __name__ == "__main__":
    main()
