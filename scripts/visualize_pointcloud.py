#!/usr/bin/env python3
"""Visualize heightmap (.npy) as a point cloud and save images.

Usage:
  python scripts/visualize_pointcloud.py --height PATH --obstacles PATH --resolution 0.1 --output out

Produces `out_3d.png` and `out_topdown.png`.
"""
import argparse
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def load_npy(path):
    return np.load(path)


def to_pointcloud(height, resolution=0.1):
    h, w = height.shape
    xs = (np.arange(w) * resolution)
    ys = (np.arange(h) * resolution)
    X, Y = np.meshgrid(xs, ys)
    Z = height
    pts = np.column_stack((X.ravel(), Y.ravel(), Z.ravel()))
    return pts, X, Y, Z


def plot_3d(pts, colors=None, out_path="out_3d.png", subsample=200000):
    if pts.shape[0] > subsample:
        idx = np.linspace(0, pts.shape[0] - 1, subsample).astype(int)
        pts_plot = pts[idx]
        cols = colors[idx] if colors is not None else None
    else:
        pts_plot = pts
        cols = colors

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(pts_plot[:, 0], pts_plot[:, 1], pts_plot[:, 2], c=cols, s=0.5)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_topdown(Z, resolution, out_path="out_topdown.png", cmap='terrain'):
    fig, ax = plt.subplots(figsize=(6, 6))
    extent = [0, Z.shape[1] * resolution, 0, Z.shape[0] * resolution]
    im = ax.imshow(Z, origin='lower', cmap=cmap, extent=extent)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    fig.colorbar(im, ax=ax, label='height')
    plt.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--height', required=True, help='Path to height .npy file (2D array)')
    p.add_argument('--obstacles', required=False, help='Path to obstacles .npy file (same shape, bool/int mask)')
    p.add_argument('--resolution', type=float, default=0.1, help='Grid resolution (m per cell)')
    p.add_argument('--output', default='out', help='Output prefix for images')
    args = p.parse_args()

    height = load_npy(args.height)
    if height.ndim != 2:
        raise SystemExit('height array must be 2D')

    pts, X, Y, Z = to_pointcloud(height, resolution=args.resolution)

    colors = None
    if args.obstacles:
        obs = load_npy(args.obstacles)
        if obs.shape != height.shape:
            print('Warning: obstacles shape != height shape; ignoring obstacles')
        else:
            mask = obs.ravel() != 0
            # color obstacles red, others by height (blue->green)
            colors = np.empty((pts.shape[0], 3))
            colors[mask] = np.array([1.0, 0.0, 0.0])
            # normalize height for color map for non-obstacles
            hmin, hmax = np.nanmin(Z), np.nanmax(Z)
            norm = (Z.ravel() - hmin) / max(1e-6, (hmax - hmin))
            cmap = plt.get_cmap('viridis')
            colors[~mask] = cmap(norm[~mask])[:, :3]

    out3d = f"{args.output}_3d.png"
    outtop = f"{args.output}_topdown.png"

    plot_3d(pts, colors=colors, out_path=out3d)
    plot_topdown(Z, args.resolution, out_path=outtop)

    print('Saved', out3d, 'and', outtop)


if __name__ == '__main__':
    main()
