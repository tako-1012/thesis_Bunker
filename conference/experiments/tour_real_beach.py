"""Compare exact and baseline closed tours on shared 008 legs over LAS terrain."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from itertools import product
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.ndimage import label

from tapp.collision import path_lethal_cells
from tapp.config import DEFAULT_W, RESOLUTION, Robot
from tapp.metrics import evaluate
from tapp.real_beach import build_real, list_patches
from tapp.tour import cost_matrix, euclid_matrix, sample_waypoints, solve_tour, tour_legs
from tapp.tracking import CORNER_LOOKAHEAD_M, MIN_SPEED_FRACTION, CornerSlowPursuit

DATASET = 'shizuoka_beach_las'
SIDE_M = 200
SEEDS = range(5)
GOAL_COUNTS = (5, 8, 12)
LAYOUTS = ('spread', 'clustered')
METHODS = ('selected', 'nearest', 'euclid', 'terrain', 'time')
CENTERS = 3
CENTER_SEPARATION_M = 20.
CLUSTER_RADIUS_M = 10.
GOAL_SEPARATION_M = 3.
V_MAX = 1.
KAPPA = 1/Robot().rolling_coeff


def clustered_waypoints(sc, n, seed):
    """Choose reachable centers as in 008 and assign successive goals round-robin."""
    rng = np.random.default_rng(seed)
    centers = sample_waypoints(sc, CENTERS, rng, min_sep_m=CENTER_SEPARATION_M)
    components, _ = label(~sc['tmap'].lethal)
    # A diagonal is legal only if both cardinal intermediate cells are open,
    # so 4-connected labels have exactly the same reachability as this graph.
    reachable = components == components[sc['start']]
    cells = np.argwhere(reachable)
    candidates = [
        iter(rng.permutation(cells[((cells - center)**2).sum(axis=1)
                                   <= (CLUSTER_RADIUS_M/RESOLUTION)**2]))
        for center in centers
    ]
    goals = []
    for k in range(n):
        for xy in candidates[k % CENTERS]:
            p = tuple(map(int, xy))
            if all(math.dist(p, q)*RESOLUTION >= GOAL_SEPARATION_M for q in goals):
                goals.append(p)
                break
        else:
            raise ValueError(f'cluster {k % CENTERS} has no separated reachable goal {k+1}')
    return goals, centers


def leg_seconds(path):
    """Integrate the CornerSlowPursuit corner speed along one 008 polyline."""
    controller = CornerSlowPursuit(np.asarray(path)*RESOLUTION, v_max=V_MAX)
    # The corners in (s, s + lookahead] change only at these breakpoints.
    turns = controller.turn_arc
    stops = np.unique(np.r_[0., controller.arc[-1], turns,
                            np.maximum(0., turns-CORNER_LOOKAHEAD_M)])
    mid = (stops[:-1]+stops[1:])/2
    first = turns.searchsorted(mid, side='right')
    end = turns.searchsorted(mid+CORNER_LOOKAHEAD_M, side='right')
    angle = np.minimum(np.pi, controller.turn_sum[end]-controller.turn_sum[first])
    speeds = controller.v_max*np.maximum(MIN_SPEED_FRACTION, np.cos(angle))
    return float(np.sum(np.diff(stops)/speeds))


def time_matrix(paths, n):
    durations = np.full((n, n), np.inf)
    for (i, j), path in paths.items():
        durations[i, j] = leg_seconds(path)
    return durations


def nearest_order(distances):
    remaining = set(range(1, len(distances)))
    order = [0]
    while remaining:
        source = order[-1]
        target = min(remaining, key=lambda j: (distances[source, j], j))
        remaining.remove(target)
        order.append(target)
    return order


def orderings(euclidean, terrain, durations):
    orders = dict(selected=list(range(len(euclidean))), nearest=nearest_order(euclidean))
    seconds = {}
    for name, matrix in zip(METHODS[2:], (euclidean, terrain, durations)):
        start = time.perf_counter()
        order, _ = solve_tour(matrix)
        seconds[name] = time.perf_counter()-start
        orders[name] = order
    return orders, seconds


def join_legs(order, paths):
    path = [paths[order[0], order[0]][0]]
    for pair in tour_legs(order):
        path.extend(paths[pair][1:])
    return path


def tour_sum(order, matrix):
    return float(sum(matrix[pair] for pair in tour_legs(order)))


def measure_layout(sc, goals, centers, layout):
    points = [sc['start'], *goals]
    pair = cost_matrix(sc, points, w=DEFAULT_W, kappa=KAPPA)
    costs, paths = pair['C'], pair['paths']
    if not np.isfinite(costs).all():
        raise RuntimeError('008 pair costs include unreachable goals')
    if any(len(path_lethal_cells(path, sc['tmap'].lethal)) for path in paths.values()):
        raise RuntimeError('008 pair path touches a lethal cell')
    start = time.perf_counter()
    durations = time_matrix(paths, len(points))
    clock_s = time.perf_counter()-start
    start = time.perf_counter()
    euclidean = euclid_matrix(points)
    euclidean_s = time.perf_counter()-start
    base = dict(patch=sc['kind'], seed=sc['seed'], layout=layout)
    rows, examples, solving = [], [], []
    for n in GOAL_COUNTS:
        scope = np.s_[:n+1, :n+1]
        orders, solve_s = orderings(euclidean[scope], costs[scope], durations[scope])
        case = dict(base, n_goals=n)
        solving.extend(dict(case, method=m, seconds=s) for m, s in solve_s.items())
        routes = {m: join_legs(order, paths) for m, order in orders.items()}
        comparison = []
        for method in METHODS:
            metrics = evaluate(routes[method], sc['tmap'])
            comparison.append(dict(case, method=method, order=orders[method],
                                   cost_dir=tour_sum(orders[method], costs),
                                   energy_kj=metrics['energy_kj'],
                                   travel_time_s=tour_sum(orders[method], durations),
                                   length_m=metrics['length_xy'], climb_m=metrics['climb']))
        energy = comparison[METHODS.index('terrain')]['energy_kj']
        fastest = comparison[METHODS.index('time')]['travel_time_s']
        best_cost = comparison[METHODS.index('terrain')]['cost_dir']
        for row in comparison:
            row.update(energy_delta_pct=100*(row['energy_kj']/energy-1),
                       time_delta_pct=100*(row['travel_time_s']/fastest-1),
                       cost_delta_pct=100*(row['cost_dir']/best_cost-1))
        rows.extend(comparison)
        examples.append(dict(comparison[METHODS.index('euclid')],
                             terrain=comparison[METHODS.index('terrain')],
                             points=points[:n+1], euclid_path=routes['euclid'],
                             terrain_path=routes['terrain']))
    timing = dict(base, matrix_points=len(points), directed_s=pair['time'],
                  time_s=clock_s, euclid_s=euclidean_s, points=points, centers=centers,
                  used_seed=sc['used_seed'], redraws=sc['redraws'], patch_index=sc['patch_index'])
    return rows, examples, solving, timing


def checkpoint(job):
    patch, seed, cache = job
    checkpoint_file = cache/f'{patch}_seed{seed}.json'
    if checkpoint_file.exists():
        return json.loads(checkpoint_file.read_text())
    failures = []
    records = []
    try:
        sc = build_real(patch, SIDE_M, seed, debris=False, dataset=DATASET)
    except RuntimeError as error:
        failures.extend(dict(patch=patch, seed=seed, layout=layout, reason=str(error))
                        for layout in LAYOUTS)
    else:
        waypoint_seed = np.random.SeedSequence([seed, 3000, SIDE_M, sc['patch_index']])
        n = max(GOAL_COUNTS)
        for layout in LAYOUTS:
            try:
                if layout == 'spread':
                    goals, centers = sample_waypoints(sc, n, waypoint_seed), []
                else:
                    goals, centers = clustered_waypoints(sc, n, waypoint_seed)
            except ValueError as error:
                failures.append(dict(patch=patch, seed=seed, layout=layout, reason=str(error)))
                continue
            records.append(measure_layout(sc, goals, centers, layout))
    data = dict(patch=patch, seed=seed, records=records, failures=failures)
    temporary = checkpoint_file.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, allow_nan=False))
    temporary.replace(checkpoint_file)
    return data


def distribution(values):
    return dict(median=float(np.median(values)), p90=float(np.quantile(values, .9)),
                maximum=float(np.max(values)))


def summarize(tours):
    for layout, n in product(LAYOUTS, GOAL_COUNTS):
        group = [row for row in tours if (row['layout'], row['n_goals']) == (layout, n)]
        if not group:
            continue
        for method in METHODS[:3]:
            rows = [row for row in group if row['method'] == method]
            summary = dict(layout=layout, n_goals=n, method=method, cases=len(rows))
            for metric in ('energy_delta_pct', 'time_delta_pct', 'cost_delta_pct'):
                summary.update({f'{metric}_{k}': v for k, v in
                                distribution([row[metric] for row in rows]).items()})
            yield summary


def compare_optimal_orders(tours):
    def canonical(order):
        return min(order, [order[0], *reversed(order[1:])])

    selected = {}
    for row in tours:
        if row['method'] in ('terrain', 'time'):
            key = tuple(row[k] for k in ('layout', 'n_goals', 'patch', 'seed'))
            selected.setdefault(key, {})[row['method']] = row['order']
    groups = {pair: [orders for key, orders in selected.items() if key[:2] == pair]
              for pair in product(LAYOUTS, GOAL_COUNTS)}
    groups['all', 'all'] = list(selected.values())
    for (layout, n), orders in groups.items():
        if not orders:
            continue
        different = sum(x['time'] != x['terrain'] for x in orders)
        different_cycle = sum(canonical(x['time']) != canonical(x['terrain']) for x in orders)
        yield dict(layout=layout, n_goals=n, cases=len(orders), changed_order=different,
                   changed_order_pct=100*different/len(orders), changed_cycle=different_cycle,
                   changed_cycle_pct=100*different_cycle/len(orders))


def summarize_times(matrix_times, solve_times):
    for layout in LAYOUTS:
        rows = [row for row in matrix_times if row['layout'] == layout]
        if rows:
            for metric in ('directed_s', 'time_s', 'euclid_s'):
                yield dict(layout=layout, stage='matrix', n_goals=max(GOAL_COUNTS),
                           method=metric.removesuffix('_s'), cases=len(rows),
                           **distribution([row[metric] for row in rows]))
    for layout, n, method in product(LAYOUTS, GOAL_COUNTS, METHODS[2:]):
        values = [row['seconds'] for row in solve_times if
                  (row['layout'], row['n_goals'], row['method']) == (layout, n, method)]
        if values:
            yield dict(layout=layout, stage='solve', n_goals=n, method=method, cases=len(values),
                       **distribution(values))


def write_csv(path, rows, fields=None):
    fields = fields if fields is not None else list(rows[0])
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, separators=(',', ':')) if isinstance(v, (list, tuple, dict))
                             else v for k, v in row.items()})


def blocked_links(order, other_order, points, tm):
    """Record changed undirected chords and lethal cells along their straight lines."""
    different = {tuple(sorted(pair)) for pair in tour_legs(order)} - {
        tuple(sorted(pair)) for pair in tour_legs(other_order)
    }
    observed = []
    for a, b in sorted(different):
        cells = path_lethal_cells([points[a], points[b]], tm.lethal)
        if len(cells):
            observed.append(dict(a=a, b=b, lethal=len(cells), steep=int(tm.steep[tuple(cells.T)].sum()),
                                 buffered_obstacle=int(tm.rock[tuple(cells.T)].sum())))
    return observed


def plot_top_case(example, rank, target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    terrain = example['terrain']
    name = example['patch']
    sc = build_real(name, SIDE_M, example['seed'], debris=False, dataset=DATASET)
    tm = sc['tmap']
    points = example['points']
    euclid_links = blocked_links(example['order'], terrain['order'], points, tm)
    terrain_links = blocked_links(terrain['order'], example['order'], points, tm)
    xy = (np.asarray(points)+.5)*RESOLUTION
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 6.0), sharex=True, sharey=True)
    extent = [0, SIDE_M, 0, SIDE_M]
    for ax, title, row, route, links in zip(
        axes, ('Straight-line order', 'Terrain order'), (example, terrain),
        (example['euclid_path'], example['terrain_path']), (euclid_links, terrain_links)
    ):
        image = ax.imshow(tm.slope.T, origin='lower', extent=extent, cmap='YlOrBr',
                          vmin=0, vmax=tm.robot.max_slope_deg, interpolation='nearest')
        ax.contourf(tm.lethal.T, levels=[.5, 1.5], colors=['#4e4e50'], extent=extent,
                    origin='lower', alpha=.85)
        ax.contourf(sc['water'].T, levels=[.5, 1.5], colors=['#cbdfe9'], extent=extent,
                    origin='lower')
        path = (np.asarray(route)+.5)*RESOLUTION
        ax.plot(*path.T, color='#007f82', linewidth=1.8, zorder=3)
        for link in links:
            ax.plot(*xy[[link['a'], link['b']]].T, color='#92373d', linestyle='--',
                    linewidth=1., alpha=.8, zorder=2)
        ax.scatter(*xy[1:].T, s=28, color='white', edgecolor='#303837', linewidth=.8, zorder=4)
        ax.scatter(*xy[0], s=47, color='#25506a', edgecolor='white', marker='s', zorder=5)
        for i, point in enumerate(xy):
            ax.annotate(str(i), point, xytext=(4, 2), textcoords='offset points',
                        fontsize=8, color='#1f2b2c', zorder=6,
                        bbox=dict(boxstyle='round,pad=.12', fc='white', ec='none', alpha=.8))
        args = (row['length_m'], row['climb_m'], row['energy_kj'])
        ax.set(title=title + '\n' + f'{args[0]:.0f} m  |  ascent {args[1]:.1f} m  |  {args[2]:.1f} kJ',
               xlabel='Alongshore (m)', aspect='equal')
        ax.tick_params(labelsize=8, length=2)
        ax.text(0, -.15, ' → '.join(map(str, [*row['order'], 0])), transform=ax.transAxes, fontsize=8)
    axes[0].set_ylabel('Sea to land (m)')
    fig.subplots_adjust(left=.075, right=.89, top=.83, bottom=.19, wspace=.12)
    fig.colorbar(image, cax=fig.add_axes([.914, .26, .014, .48]), label='Slope (°)')
    fig.suptitle(f"{name}  •  {example['layout']}  •  {example['n_goals']} goals  •  seed {example['seed']}",
                 x=.075, y=.96, ha='left', fontweight='semibold')
    fig.legend(handles=[
        Line2D([], [], color='#007f82', label='Planned route'),
        Line2D([], [], color='#92373d', linestyle='--', label='Blocked straight link unique to this order'),
        Line2D([], [], color='#4e4e50', linewidth=5, label='Impassable'),
        Line2D([], [], color='#cbdfe9', linewidth=5, label='Water'),
    ], loc='lower center', bbox_to_anchor=(.48, .018), ncols=4, frameon=False, fontsize=8)
    filename = f'{rank:02d}_{name}_{example["layout"]}_{example["n_goals"]}_seed{example["seed"]}.png'
    fig.savefig(target/'maps'/filename, dpi=175, facecolor='white')
    plt.close(fig)
    return dict(rank=rank, patch=name, seed=example['seed'], layout=example['layout'],
                n_goals=example['n_goals'], cost_delta_pct=example['cost_delta_pct'],
                energy_delta_pct=example['energy_delta_pct'],
                euclid_time_s=example['travel_time_s'], terrain_time_s=terrain['travel_time_s'],
                euclid_length_m=example['length_m'], terrain_length_m=terrain['length_m'],
                euclid_climb_m=example['climb_m'], terrain_climb_m=terrain['climb_m'],
                euclid_blocked_links=euclid_links, terrain_blocked_links=terrain_links,
                euclid_order=example['order'], terrain_order=terrain['order'], figure=f'maps/{filename}')


def save_outputs(target, batches):
    tours, examples, solving, timing, failures = [], [], [], [], []
    for batch in batches:
        failures.extend(batch['failures'])
        for rows, candidates, solve_times, matrix_time in batch['records']:
            tours.extend(rows)
            examples.extend(candidates)
            solving.extend(solve_times)
            timing.append(matrix_time)
    if not tours:
        raise RuntimeError(f'no complete scenarios: {failures}')
    top = sorted(examples, key=lambda row: (-row['cost_delta_pct'], row['patch'],
                                           row['layout'], row['n_goals'], row['seed']))[:10]
    write_csv(target/'tours.csv', tours)
    write_csv(target/'matrix_times.csv', timing)
    write_csv(target/'solve_times.csv', solving)
    write_csv(target/'failures.csv', failures, ['patch', 'seed', 'layout', 'reason'])
    write_csv(target/'penalties.csv', list(summarize(tours)))
    write_csv(target/'changed_orders.csv', list(compare_optimal_orders(tours)))
    write_csv(target/'timing_summary.csv', list(summarize_times(timing, solving)))
    (target/'maps').mkdir()
    write_csv(target/'top10.csv', [plot_top_case(row, i, target) for i, row in enumerate(top, 1)])
    print(f'Patch/seed cases: {len(batches)}; complete layouts: {len(timing)}; '
          f'failed layouts: {len(failures)}; tours: {len(tours)}')
    for filename in ('penalties.csv', 'changed_orders.csv', 'timing_summary.csv', 'top10.csv'):
        print(f'\n{filename}')
        print((target/filename).read_text(), end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='new output directory')
    parser.add_argument('--cache', type=Path, help='checkpoint folder for resuming the same experiment')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--patch', action='append', help='limit the run to a test patch (repeatable)')
    args = parser.parse_args(argv)
    names = [row['name'] for row in list_patches('test', dataset=DATASET)]
    if len(names) != 48:
        parser.error(f'expected 48 test patches, found {len(names)}')
    if args.patch:
        unknown = set(args.patch)-set(names)
        if unknown:
            parser.error(f'not a test patch: {", ".join(sorted(unknown))}')
        names = [name for name in names if name in args.patch]
    if args.workers < 1:
        parser.error('workers must be positive')
    args.out.mkdir(parents=True, exist_ok=False)
    cache = args.cache if args.cache is not None else args.out/'checkpoint'
    cache.mkdir(parents=True, exist_ok=True)
    jobs = list(product(names, SEEDS, [cache]))
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        batches = []
        for i, result in enumerate(pool.map(checkpoint, jobs), 1):
            batches.append(result)
            print(f"{i}/{len(jobs)} {result['patch']} seed {result['seed']}: "
                  f"{len(result['records'])} layouts; {result['failures']}", flush=True)
    save_outputs(args.out, batches)
    print(f'Elapsed time [s]: {time.perf_counter()-start:.3f}')


if __name__ == '__main__':
    main()
