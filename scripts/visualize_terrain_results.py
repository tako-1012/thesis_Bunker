#!/usr/bin/env python3
"""Visualize terrain scenarios and overlay both paths (with/without terrain cost).
Saves PNGs under `figures/terrain_comparison_{scenario}.png`.
"""
import os
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / 'terrain_test_scenarios'
OUT_DIR = ROOT / 'figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)
RES_FILE = ROOT / 'benchmark_results' / 'terrain_cost_effectiveness.json'


def load_scenario(name):
    meta = json.load(open(SCEN_DIR / f"{name}_meta.json"))
    npz = np.load(SCEN_DIR / f"{name}_data.npz")
    return meta, npz


def plot_scenario(name, rec):
    meta, npz = load_scenario(name)
    elev = npz['elevation']
    rough = npz['roughness']
    # use layer 0 for 2D plotting
    elev2 = elev[:, :, 0].T
    rough2 = rough[:, :, 0].T

    path_a = rec['without_terrain'].get('path')
    path_b = rec['with_terrain'].get('path')

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    ax = axes[0]
    im = ax.imshow(elev2, origin='lower', cmap='terrain')
    if path_a:
        pa = np.array(path_a)
        # convert world->grid indexing: assume center at grid middle
        gsx, gsy = elev.shape[0], elev.shape[1]
        cx = gsx / 2.0
        cy = gsy / 2.0
        xs = (pa[:,0] / 0.2 + cx)
        ys = (pa[:,1] / 0.2 + cy)
        ax.plot(xs, ys, '-r', label='no terrain')
    if path_b:
        pb = np.array(path_b)
        gsx, gsy = elev.shape[0], elev.shape[1]
        cx = gsx / 2.0
        cy = gsy / 2.0
        xs = (pb[:,0] / 0.2 + cx)
        ys = (pb[:,1] / 0.2 + cy)
        ax.plot(xs, ys, '-g', label='with terrain')
    ax.set_title('Elevation + Paths')
    ax.legend()
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax2 = axes[1]
    im2 = ax2.imshow(rough2, origin='lower', cmap='gray')
    if path_a:
        ax2.plot(xs, ys, '-r')
    if path_b:
        ax2.plot(xs, ys, '-g')
    ax2.set_title('Roughness + Paths')
    fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)

    plt.suptitle(name)
    plt.tight_layout()
    outp = OUT_DIR / f'terrain_comparison_{name}.png'
    plt.savefig(outp, dpi=300)
    plt.close()
    print('Saved', outp)


if __name__ == '__main__':
    if not RES_FILE.exists():
        print('No results file', RES_FILE)
        raise SystemExit(1)
    recs = json.load(open(RES_FILE))
    for rec in recs:
        plot_scenario(rec['scenario'], rec)
    print('All visualizations saved to', OUT_DIR)
