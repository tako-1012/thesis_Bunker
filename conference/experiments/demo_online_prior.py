#!/usr/bin/env python3
"""Illustrate coarse-map guidance on ridge/100 m/seed 7, outside the paper."""
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
from tapp.prior import coarse_prior                   # noqa: E402
from tapp.scenario import build, run_planner          # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "online_prior")
INK = "#222222"
SLOPE_CMAP = ListedColormap(plt.get_cmap("Blues")(np.linspace(0.08, 0.75, 256)))
RUNS = [  # label, colour, linestyle, coarse cell size (None = adaptive)
    ("full map known (TA*-S)", "#222222", "--", None),
    ("online adaptive", "#eb6834", "-", None),
    ("online prior5 soft", "#eda100", "-", 5.0),
    ("online prior10 soft", "#2a78d6", "-", 10.0),
]


def main():
    sc = build("ridge", 100, 7)
    tm = sc["tmap"]
    L = tm.shape[0] * RESOLUTION
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    im = ax.imshow(np.clip(tm.slope, 0, 40).T, origin="lower", extent=[0, L, 0, L], cmap=SLOPE_CMAP,
                   vmin=0, vmax=40)
    ax.imshow(np.ma.masked_where(~tm.lethal.T, tm.lethal.T), origin="lower", extent=[0, L, 0, L],
              cmap=ListedColormap(["#3a3a3a"]), alpha=0.85)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02).set_label("slope [deg]")
    for i, (label, col, ls, cell_m) in enumerate(RUNS):
        if i == 0:
            r = run_planner("TA*-S", sc, w=DEFAULT_W)
            path = r["path"]
            extra = ""
        else:
            pm = None if cell_m is None else coarse_prior(tm, cell_m)
            r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                           unknown_cost="adaptive", sense_radius_m=15.0,
                           prior_map=pm, prior_lethal="soft")
            path = r["traj"]
            extra = f", {r['n_plans']} plans"
        if not r["success"]:
            raise RuntimeError(f"{label} failed: {r.get('reason', 'no_path')}")
        m = evaluate(path, tm)
        p = (np.asarray(path, dtype=float) + 0.5) * RESOLUTION
        ax.plot(p[:, 0], p[:, 1], color="white", lw=3.6)
        ax.plot(p[:, 0], p[:, 1], color=col, lw=1.8, ls=ls, label=f"{label}: {m['length_xy']:.0f} m{extra}")
    for c, mk in ((sc["start"], "o"), (sc["goal"], "*")):
        ax.plot((c[0] + 0.5) * RESOLUTION, (c[1] + 0.5) * RESOLUTION, mk, color="white", mec=INK, ms=12, mew=1.2)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Online replanning with a coarse prior: ridge (seed 7)", color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=1, fontsize=8.5, frameon=False)
    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, "demo_online_prior_ridge_7.png")
    fig.savefig(fn, dpi=180)
    plt.close(fig)
    print("wrote", fn)


if __name__ == "__main__":
    main()
