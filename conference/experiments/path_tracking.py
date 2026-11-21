"""Paired tracking experiment on LAS validation beaches using two motion models."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from tapp.config import RESOLUTION
from tapp.exact_planners import run_planner_exact
from tapp.footprint import with_inflated_steep
from tapp.pure_pursuit import prepare_path
from tapp.real_beach import build_real, list_patches
from tapp.robot_sim import initial_pose, simulate
from tapp.tour import sample_waypoints
from tapp.tracking import TRACKINGS, corner_turns
from tapp.tracking_sim import simulate_tracking

DATASET = 'shizuoka_beach_las'
SEEDS = range(100, 105)
SIDE_M = 200
TERRAIN_SEED = 100
MODELS = ('no_lag', 'lagged')
THRESHOLDS = (.5, .75)


def deviation_and_curvature(xy, path):
    """Closest-polyline distance and absolute turning per metre near that point."""
    delta = np.diff(path, axis=0)
    lengths = np.linalg.norm(delta, axis=1)
    if not len(lengths):
        return np.linalg.norm(xy-path[0], axis=1), np.zeros(len(xy))
    arc = np.r_[0., np.cumsum(lengths)]
    turns = np.r_[0., np.cumsum(corner_turns(path))]
    distances, curvatures = [], []
    for points in np.array_split(xy, max(1, (len(xy)+511)//512)):
        offset = points[:, None, :]-path[:-1]
        t = np.clip(np.einsum('nji,ji->nj', offset, delta)/lengths**2, 0, 1)
        gap = offset-t[..., None]*delta
        squared = np.sum(gap**2, axis=-1)
        nearest = squared.argmin(axis=1)
        index = np.arange(len(points))
        distances.extend(np.sqrt(squared[index, nearest]))
        s = arc[nearest]+t[index, nearest]*lengths[nearest]
        lo, hi = np.maximum(0., s-1.), np.minimum(arc[-1], s+1.)
        left = np.searchsorted(arc[1:-1], lo, side='right')
        right = np.searchsorted(arc[1:-1], hi, side='right')
        curvatures.extend(np.rad2deg(turns[right]-turns[left])/(hi-lo))
    return np.asarray(distances), np.asarray(curvatures)


def exceedances(distance, time, threshold):
    above = distance > threshold
    episodes = np.count_nonzero(above & ~np.r_[False, above[:-1]])
    return float(np.diff(time)[above[:-1]].sum()), int(episodes)


def evaluate_patch(patch):
    sc = with_inflated_steep(build_real(patch, SIDE_M, TERRAIN_SEED, debris=True, dataset=DATASET))
    plans, runs, samples = [], [], []
    for seed in SEEDS:
        goal, = sample_waypoints(sc, 1, np.random.SeedSequence([seed, 3000, SIDE_M, sc['patch_index']]))
        plan = run_planner_exact('TA*-S', dict(sc, goal=goal))
        if not plan['success']:
            plans.append(dict(patch=patch, seed=seed, start=list(sc['start']), goal=list(goal), status='no_path'))
            continue
        route = prepare_path(np.asarray(plan['path'])*RESOLUTION)
        pose = initial_pose(route)
        plans.append(dict(patch=patch, seed=seed, start=list(sc['start']), goal=list(goal), status='planned',
                          path_m=route.tolist()))
        for model in MODELS:
            for tracking in TRACKINGS:
                if model == 'no_lag' and tracking == 'default':
                    run = simulate(sc, route, pose)
                else:
                    run = simulate_tracking(route, pose, tracking=tracking, lagged=model == 'lagged')
                trace = np.asarray(run['trajectory'])
                distance, curvature = deviation_and_curvature(trace[:, 1:3], route)
                metrics = dict(patch=patch, seed=seed, model=model, tracking=tracking,
                               completed=run['completed'], elapsed_s=run['elapsed_s'], samples=len(trace),
                               deviation_max_m=float(distance.max()), deviation_p95_m=float(np.percentile(distance, 95)))
                for label, threshold in zip(('05', '075'), THRESHOLDS, strict=True):
                    seconds, episodes = exceedances(distance, trace[:, 0], threshold)
                    metrics.update({f'over_{label}_s': seconds, f'over_{label}_episodes': episodes})
                runs.append(metrics)
                samples.append((model, tracking, distance, curvature if tracking == 'default' else None))
    return plans, runs, samples


def summarize(runs, samples):
    rows = []
    for model in MODELS:
        for tracking in TRACKINGS:
            group = [row for row in runs if (row['model'], row['tracking']) == (model, tracking)]
            completed = [row['elapsed_s'] for row in group if row['completed']]
            distances = np.concatenate([distance for m, t, distance, _ in samples if (m, t) == (model, tracking)])
            row = dict(model=model, tracking=tracking, runs=len(group), completed=len(completed),
                       median_completed_s=float(np.median(completed)) if completed else None,
                       deviation_max_m=float(distances.max()), deviation_p95_m=float(np.percentile(distances, 95)))
            for label in ('05', '075'):
                for unit in ('s', 'episodes'):
                    key = f'over_{label}_{unit}'
                    row[key] = sum(run[key] for run in group)
            rows.append(row)
    return rows


def plot_and_bin(samples, path):
    edges = np.array([0., 5., 15., 30., 45., 60., 90., 135., 180., np.inf])
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True, layout='constrained')
    for model, ax in zip(MODELS, axes, strict=True):
        selected = [(d, k) for m, t, d, k in samples if (m, t) == (model, 'default')]
        deviation, curvature = (np.concatenate(items) for items in zip(*selected, strict=True))
        x, p95, peak = [], [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            subset = deviation[(curvature >= lo) & (curvature < hi)]
            if not len(subset):
                continue
            centre = (lo+hi)/2 if np.isfinite(hi) else lo+22.5
            q95, maximum = float(np.percentile(subset, 95)), float(subset.max())
            x.append(centre)
            p95.append(q95)
            peak.append(maximum)
            rows.append(dict(model=model, curvature_min_deg_per_m=lo, curvature_max_deg_per_m=hi,
                             samples=len(subset), deviation_p95_m=q95, deviation_max_m=maximum,
                             samples_over_05=int(np.count_nonzero(subset > .5)),
                             samples_over_075=int(np.count_nonzero(subset > .75))))
        ax.plot(x, p95, marker='o', label='95th percentile')
        ax.plot(x, peak, marker='s', label='Maximum')
        ax.axhline(.5, color='0.5', linestyle=':', linewidth=1)
        ax.axhline(.75, color='0.5', linestyle='--', linewidth=1)
        ax.set_title('No actuator lag' if model == 'no_lag' else 'Actuator lag and 80% turn response')
        ax.set_xlabel('Local path curvature bin (degrees/m)')
        ax.grid(alpha=.2)
        ax.legend()
    axes[0].set_ylabel('Cross-track distance (m)')
    fig.suptitle('Default tracking on LAS validation routes')
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return rows


def write_csv(path, rows):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ('plans.json', 'runs.csv', 'summary.csv', 'curvature.csv', 'deviation_curvature.png'):
        if (args.output/name).exists():
            raise FileExistsError(args.output/name)
    patches = [row['name'] for row in list_patches('validation', dataset=DATASET)]
    plans, runs, samples = [], [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for patch, (p, r, s) in zip(patches, pool.map(evaluate_patch, patches), strict=True):
            plans.extend(p)
            runs.extend(r)
            samples.extend(s)
            print(f'{patch} planned={sum(row["status"] == "planned" for row in p)}/{len(p)}', flush=True)
    summary = summarize(runs, samples)
    (args.output/'plans.json').write_text(json.dumps(plans, indent=2)+'\n')
    write_csv(args.output/'runs.csv', runs)
    write_csv(args.output/'summary.csv', summary)
    write_csv(args.output/'curvature.csv', plot_and_bin(samples, args.output/'deviation_curvature.png'))
    writer = csv.DictWriter(sys.stdout, fieldnames=list(summary[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(summary)
    for model in MODELS:
        paired = {}
        for row in runs:
            if row['model'] == model and row['completed']:
                paired.setdefault((row['patch'], row['seed']), {})[row['tracking']] = row['elapsed_s']
        deltas = [(times['corner_slow']-times['default'], times['corner_slow']/times['default']-1)
                  for times in paired.values() if len(times) == 2]
        if deltas:
            seconds, share = np.median(deltas, axis=0)
            print(f'{model} completed_pairs={len(deltas)} median_delta_s={seconds:.3f} median_delta_pct={100*share:.3f}')


if __name__ == '__main__':
    main()
