"""Replay the 074 clustered tours and compare two cluster-by-cluster orders."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from itertools import product
import json
import math
from pathlib import Path
import time

import numpy as np

from experiments import tour_real_beach as beach

ARCHIVE = Path(__file__).resolve().parents[1]/'results'/'tour_real_beach'
COMPARISONS = ('human', 'human_nearest', 'nearest', 'euclid')
LAYOUT = 'clustered'
NUMERIC_FIELDS = ('cost_dir', 'energy_kj', 'travel_time_s', 'length_m', 'climb_m',
                  'energy_delta_pct', 'time_delta_pct', 'cost_delta_pct')
ABS_TOL = 1e-10
REL_TOL = 1e-12


def human_orders(points, centers, distances):
    """Visits centers by nearest remaining center and exhausts each cluster."""
    center_distances = beach.euclid_matrix([points[0], *centers])
    center_order = beach.nearest_order(center_distances)[1:]
    placed = [0]
    nearest = [0]
    for center in center_order:
        # Goal indices start at 1; 074 assigns them to centers round-robin.
        goals = list(range(center, len(points), len(centers)))
        placed.extend(goals)
        # Enter the cluster from the previous visited waypoint (or the base).
        nodes = [nearest[-1], *goals]
        local_order = beach.nearest_order(distances[np.ix_(nodes, nodes)])
        nearest.extend(nodes[i] for i in local_order[1:])
    return dict(human=placed, human_nearest=nearest)


def evaluate_orders(sc, points, centers):
    pair = beach.cost_matrix(sc, points, w=beach.DEFAULT_W, kappa=beach.KAPPA)
    costs, paths = pair['C'], pair['paths']
    if not np.isfinite(costs).all():
        raise ValueError('074-style matrix contains an unreachable pair')
    if any(len(beach.path_lethal_cells(path, sc['tmap'].lethal)) for path in paths.values()):
        raise ValueError('074-style matrix contains a path that touches a lethal cell')
    distances = beach.euclid_matrix(points)
    durations = beach.time_matrix(paths, len(points))
    all_rows = []
    for n in beach.GOAL_COUNTS:
        scope = np.s_[:n+1, :n+1]
        orders, _ = beach.orderings(distances[scope], costs[scope], durations[scope])
        orders.update(human_orders(points[:n+1], centers, distances[scope]))
        rows = {}
        for method, order in orders.items():
            metrics = beach.evaluate(beach.join_legs(order, paths), sc['tmap'])
            rows[method] = dict(
                patch=sc['kind'], seed=sc['seed'], n_goals=n, method=method, order=order,
                cost_dir=beach.tour_sum(order, costs), energy_kj=metrics['energy_kj'],
                travel_time_s=beach.tour_sum(order, durations), length_m=metrics['length_xy'],
                climb_m=metrics['climb'],
            )
        terrain, fastest = rows['terrain'], rows['time']
        for row in rows.values():
            row.update(energy_delta_pct=100*(row['energy_kj']/terrain['energy_kj']-1),
                       time_delta_pct=100*(row['travel_time_s']/fastest['travel_time_s']-1),
                       cost_delta_pct=100*(row['cost_dir']/terrain['cost_dir']-1))
        all_rows.extend(rows.values())
    return all_rows, dict(cost_dir=costs.tolist(), travel_time_s=durations.tolist(),
                          euclidean_cells=distances.tolist())


def rebuild(patch, seed):
    sc = beach.build_real(patch, beach.SIDE_M, seed, debris=False, dataset=beach.DATASET)
    waypoint_seed = np.random.SeedSequence([seed, 3000, beach.SIDE_M, sc['patch_index']])
    goals, centers = beach.clustered_waypoints(sc, max(beach.GOAL_COUNTS), waypoint_seed)
    points = [sc['start'], *goals]
    tours, matrices = evaluate_orders(sc, points, centers)
    return dict(patch=patch, seed=seed, points=points, centers=centers,
                used_seed=sc['used_seed'], redraws=sc['redraws'], patch_index=sc['patch_index'],
                tours=tours, matrices=matrices)


def checkpoint(job):
    patch, seed, directory = job
    path = directory/f'{patch}_seed{seed}.json'
    if path.is_file():
        return json.loads(path.read_text())
    case = rebuild(patch, seed)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(case, allow_nan=False))
    temporary.replace(path)
    return case


def read_074():
    with (ARCHIVE/'matrix_times.csv').open(newline='') as stream:
        layouts = {(r['patch'], int(r['seed'])): r for r in csv.DictReader(stream) if r['layout'] == LAYOUT}
    with (ARCHIVE/'tours.csv').open(newline='') as stream:
        tours = {(r['patch'], int(r['seed']), int(r['n_goals']), r['method']): r
                 for r in csv.DictReader(stream) if r['layout'] == LAYOUT}
    return layouts, tours


def check_074(case, archived_layout, archived_tours):
    identity = (case['patch'], case['seed'])
    for field in ('points', 'centers', 'used_seed', 'redraws', 'patch_index'):
        actual = json.loads(json.dumps(case[field]))
        archived = json.loads(archived_layout[field])
        if actual != archived:
            raise ValueError(f'{identity}: 074 {field} mismatch')
    if len(case['points']) != int(archived_layout['matrix_points']):
        raise ValueError(f'{identity}: 074 matrix size mismatch')

    audit = []
    for row in case['tours']:
        if row['method'] not in beach.METHODS:
            continue
        n, method = row['n_goals'], row['method']
        key = (*identity, n, method)
        expected = archived_tours[key]
        if row['order'] != json.loads(expected['order']):
            raise ValueError(f'{key}: 074 visit order mismatch')
        record = dict(patch=identity[0], seed=identity[1], n_goals=n, method=method)
        for field in NUMERIC_FIELDS:
            baseline = float(expected[field])
            value = row[field]
            if not math.isclose(value, baseline, rel_tol=REL_TOL, abs_tol=ABS_TOL):
                raise ValueError(f'{key}: 074 {field} mismatch ({value} versus {baseline})')
            record['absdiff_'+field] = abs(value-baseline)
        audit.append(record)
    required = set(product(beach.GOAL_COUNTS, beach.METHODS))
    if len(audit) != len(required) or {(r['n_goals'], r['method']) for r in audit} != required:
        raise ValueError(f'{identity}: missing or duplicate 074 comparison')
    return audit


def summarize(tours):
    summary = []
    for n, method in product(beach.GOAL_COUNTS, COMPARISONS):
        rows = [row for row in tours if row['n_goals'] == n and row['method'] == method]
        result = dict(n_goals=n, method=method, cases=len(rows))
        for metric in ('energy_delta_pct', 'time_delta_pct'):
            statistics = beach.distribution([r[metric] for r in rows])
            result.update({f'{metric}_{k}': value for k, value in statistics.items()})
        summary.append(result)
    return summary


def write_outputs(out, cases, audit):
    tours = [row for case in cases for row in case['tours']]
    beach.write_csv(out/'tours.csv', tours)
    beach.write_csv(out/'comparison.csv', summarize(tours))
    beach.write_csv(out/'archive_checks.csv', audit)
    with (out/'matrices.npz').open('xb') as stream:
        data = {key: np.array([case[key] for case in cases]) for key in ('patch', 'seed', 'points', 'centers')}
        data.update({key: np.array([case['matrices'][key] for case in cases])
                     for key in ('cost_dir', 'travel_time_s', 'euclidean_cells')})
        np.savez_compressed(stream, **data)
    print(f'Validated 074 layouts: {len(cases)}; validated 074 tours: {len(audit)}; '
          f'all tours: {len(tours)}')
    for field in NUMERIC_FIELDS:
        gaps = [r['absdiff_'+field] for r in audit]
        print(f'{field}: exactly equal {gaps.count(0.)}/{len(gaps)}; maximum absolute difference={max(gaps):.16g}')
    print()
    print((out/'comparison.csv').read_text(), end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new output folder')
    parser.add_argument('--cache', type=Path, help='checkpoint folder for this fixed 080 run')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error('workers must be positive')
    layouts, tours_074 = read_074()
    names = [p['name'] for p in beach.list_patches('test', dataset=beach.DATASET)]
    if len(names) != 48 or set(layouts) != set(product(names, beach.SEEDS)):
        raise ValueError('expected the 48 test patches and five clustered seeds from task074')
    if set(tours_074) != set(product(names, beach.SEEDS, beach.GOAL_COUNTS, beach.METHODS)):
        raise ValueError('expected all 3,600 archived task074 clustered tours')

    args.out.mkdir(parents=True, exist_ok=False)
    cache = args.cache if args.cache is not None else args.out/'checkpoints'
    cache.mkdir(parents=True, exist_ok=True)
    jobs = list(product(names, beach.SEEDS, [cache]))
    start = time.perf_counter()
    cases, audit = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (job, result) in enumerate(zip(jobs, pool.map(checkpoint, jobs), strict=True), 1):
            patch, seed = job[:2]
            if (result['patch'], result['seed']) != (patch, seed):
                raise ValueError(f'{patch}, {seed}: checkpoint identity mismatch')
            audit.extend(check_074(result, layouts[patch, seed], tours_074))
            cases.append(result)
            print(f'{i}/{len(jobs)} {patch} seed {seed}: 074 verified', flush=True)
    write_outputs(args.out, cases, audit)
    print(f'Elapsed time [s]: {time.perf_counter()-start:.3f}')


if __name__ == '__main__':
    main()
