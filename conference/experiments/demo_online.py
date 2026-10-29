#!/usr/bin/env python3
"""Illustrative figure for online replanning (exploratory, not in the paper).

Usage (from conference/):  python3 experiments/demo_online.py [kind] [seed]
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402
from matplotlib.colors import ListedColormap         # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tapp.config import DEFAULT_W, RESOLUTION         # noqa: E402
from tapp.metrics import evaluate                     # noqa: E402
from tapp.online import run_online                    # noqa: E402
from tapp.scenario import build, run_planner          # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "paper", "figures", "demo")
INK = "#222222"
SLOPE_CMAP = ListedColormap(plt.get_cmap("Blues")(np.linspace(0.08, 0.75, 256)))
RUNS = [  # label, colour, linestyle, kwargs (None = full map known)
    ("full map known (TA*-S)", "#222222", "--", None),
    ("online, sensor 15 m, optimistic", "#eda100", "-", dict(unknown_cost=0.0, sense_radius_m=15.0)),
    ("online, sensor 15 m, adaptive", "#eb6834", "-", dict(unknown_cost="adaptive", sense_radius_m=15.0)),
    ("online, sensor 30 m, adaptive", "#2a78d6", "-", dict(unknown_cost="adaptive", sense_radius_m=30.0)),
]


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "ridge"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    sc = build(kind, 100, seed)
    tm = sc["tmap"]
    L = tm.shape[0] * RESOLUTION
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    im = ax.imshow(np.clip(tm.slope, 0, 40).T, origin="lower", extent=[0, L, 0, L], cmap=SLOPE_CMAP,
                   vmin=0, vmax=40)
    ax.imshow(np.ma.masked_where(~tm.lethal.T, tm.lethal.T), origin="lower", extent=[0, L, 0, L],
              cmap=ListedColormap(["#3a3a3a"]), alpha=0.85)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02).set_label("slope [deg]")
    for label, col, ls, kw in RUNS:
        if kw is None:
            path = run_planner("TA*-S", sc, w=DEFAULT_W)["path"]
            extra = ""
        else:
            r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W, **kw)
            path = r["traj"]
            extra = f", {r['n_plans']} plans"
        m = evaluate(path, tm)
        p = (np.asarray(path, dtype=float) + 0.5) * RESOLUTION
        ax.plot(p[:, 0], p[:, 1], color="white", lw=3.6)
        ax.plot(p[:, 0], p[:, 1], color=col, lw=1.8, ls=ls, label=f"{label}: {m['length_xy']:.0f} m{extra}")
    for c, mk in ((sc["start"], "o"), (sc["goal"], "*")):
        ax.plot((c[0] + 0.5) * RESOLUTION, (c[1] + 0.5) * RESOLUTION, mk, color="white", mec=INK, ms=12, mew=1.2)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(f"Online replanning with limited sensing: {kind} (seed {seed})", color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=1, fontsize=8.5, frameon=False)
    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, f"demo_online_{kind}_{seed}.png")
    fig.savefig(fn, dpi=180)
    print("wrote", fn)


if __name__ == "__main__":
    main()
