"""Compare terrain sources with fixed obstacle evidence from archived goal_cell runs."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from results.waypoint_feasibility.check_archives import read_csv, write_csv
from ros2_jazzy.gz_checks.online_batch_runtime import map_signature
from tapp.endpoint_policy import classify_failure, load_snapshot
from tapp.online_mission import OnlinePlanner
from tapp.planners import astar
from tapp.pointcloud_map_fine import PointCloudMapFine, RATIO
from tapp.traversability import inflate, slope_deg

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT/'results'
SOURCES = {'030': 'eval_ground_endpoint', '035': 'eval_035'}
ERROR_FIELDS = ('fp_steep_023', 'fp_steep_same_clearance', 'fn_steep_cells', 'fn_steep_halo')
NEW_MISSES = ('new_fn_steep_cells', 'new_fn_steep_halo')


def terrain_errors(seen, lethal, steep_halo, truth_lethal, truth_steep, truth_halo):
    fp = seen & lethal & ~truth_lethal & steep_halo
    missed = seen & ~lethal
    return dict(fp_steep_023=int(fp.sum()), fp_steep_same_clearance=int((fp & ~truth_halo).sum()),
                fn_steep_cells=int((missed & truth_steep).sum()), fn_steep_halo=int((missed & truth_halo).sum()))


def route(mapper, known, cost, lethal, start, goal, *, saved_multiplier=None):
    """Replay the same soft-prior A* search without the handoff or robot motion."""
    planner = OnlinePlanner(mapper.tm.cost, mapper.lethal, mapper.weights, prior_lethal_mode='soft')
    planner.observe(known, cost, lethal)
    blocked, mult = planner.planning_maps()
    # Goal passability is explicit even if start and goal happen to coincide.
    if saved_multiplier is not None:
        mult = saved_multiplier
    reachable = not blocked[goal] and astar(blocked, start, goal, mult)['success']
    return dict(goal_open=not bool(blocked[goal]), start_blocked=bool(blocked[start]), route=bool(reachable))


def load_reference(physical, patch):
    manifest = json.loads((physical/'manifest.json').read_text())
    if manifest.get('map_method') != 'fine' or manifest.get('obstacle_clearance', 'centre') != 'centre':
        raise ValueError('archive does not use fine centre clearance')
    case, = [c for c in manifest['cases'] if c['selected'] and c['patch'] == patch]
    reference = ROOT/case['world_reference']
    with np.load(reference, allow_pickle=False) as data:
        prior, truth = [SimpleNamespace(**{field: data[f'{name}_{field}']
                        for field in ('elev', 'lethal', 'rock')}) for name in ('prior', 'truth')]
    for name, tm in [('prior', prior), ('truth', truth)]:
        if map_signature(dict(tmap=tm)) != case['input_audit']['signatures'][name]:
            raise ValueError(f'{physical}: mismatched {name} reference signature')
    return reference, prior, truth


def reconstruct(mapper, snapshot, final):
    if final is not None:
        with np.load(final, allow_pickle=False) as arrays:
            shape = tuple(arrays['fine_shape'])
            if shape != mapper.fine_shape:
                raise ValueError(f'{final}: fine grid differs')
            fine = np.unpackbits(arrays['fine_inflated_bits'], count=int(np.prod(shape))).reshape(shape).astype(bool)
            halo = fine[RATIO//2::RATIO, RATIO//2::RATIO]
            sensor = {k: arrays[k] for k in ('seen', 'elev', 'cost', 'lethal', 'version')}
        return sensor, halo

    # 035 archived only the failure-time evidence. Stamp the original centre-clearance obstacle halo.
    mapper._add_obstacles(np.flatnonzero(snapshot['fine_obstacle']).tolist())
    halo = mapper._inflated_coarse
    if not np.array_equal(snapshot['seen'], snapshot['known']):
        raise ValueError('failure snapshot includes an unexpected knowledge mask')
    return snapshot, halo


def evaluate(row, final, failure):
    patch = row['patch']
    snapshot = load_snapshot(failure)
    goal = int(row['goal_x']), int(row['goal_y'])
    if tuple(snapshot['goal']) != goal or classify_failure(snapshot) != 'goal_cell':
        raise ValueError(f'{failure}: disagrees with the terminal goal_cell entry')
    start = tuple(map(int, snapshot['start']))
    reference, prior, truth = load_reference(failure.parents[3], patch)
    mapper = PointCloudMapFine(prior.elev, snapshot['prior_raw'], terrain_source='prior')
    if not np.array_equal(mapper.tm.rock, prior.rock) or not np.array_equal(mapper.tm.lethal, prior.lethal):
        raise ValueError(f'{failure}: prior rock or lethal differs from the reference')
    sensor, halo = reconstruct(mapper, snapshot, final)
    robot = mapper.robot
    seen = sensor['seen']
    sensor_steep = inflate(slope_deg(sensor['elev']) > robot.max_slope_deg, robot.footprint_radius)
    sensor_lethal = mapper.tm.rock | halo | sensor_steep
    expected = sensor_lethal if final is not None else seen & sensor_lethal
    if not np.array_equal(expected, sensor['lethal']):
        raise ValueError(f'{failure}: reconstruction disagrees with the saved sensor lethal mask')
    if final is not None and bool(sensor_lethal[goal]) != (row['final_goal_lethal'] == 'True'):
        raise ValueError(f'{final}: goal flag disagrees with 046')
    if int(sensor['version']) < int(snapshot['version']):
        raise ValueError(f'{failure}: final map predates the failure')

    prior_steep = mapper._dilated_steep
    prior_lethal = mapper.lethal | halo
    truth_steep = slope_deg(truth.elev) > robot.max_slope_deg
    truth_halo = inflate(truth_steep, robot.footprint_radius)
    # Diagnostic snapshots store the exact planning multiplier, not mapper cost.
    sensor_cost = sensor['cost'] if final is not None else mapper.tm.cost
    multiplier = sensor['cost'] if final is None else None
    old = route(mapper, seen, sensor_cost, sensor_lethal, start, goal, saved_multiplier=multiplier)
    new = route(mapper, mapper.planning_seen(seen), mapper.tm.cost, prior_lethal, start, goal)
    result = dict(final_map_status='available' if final is not None else 'missing',
                  map_source='final' if final is not None else 'failure_snapshot',
                  archive_map=str((final or failure).relative_to(ROOT)), reference=str(reference.relative_to(ROOT)),
                  start_x=start[0], start_y=start[1], failure_sim_s=float(snapshot['sim_time']),
                  failure_version=int(snapshot['version']), map_version=int(sensor['version']),
                  seen_cells=int(seen.sum()), detected_halo_cells=int(halo.sum()),
                  detected_halo_at_goal=bool(halo[goal]), recovered=new['route'] and not old['route'])
    opened = seen & sensor_lethal & ~prior_lethal
    result.update(new_fn_steep_cells=int((opened & truth_steep).sum()),
                  new_fn_steep_halo=int((opened & truth_halo).sum()))
    for name, path, lethal, steep in [('sensor', old, sensor_lethal, sensor_steep),
                                      ('prior', new, prior_lethal, prior_steep)]:
        scores = terrain_errors(seen, lethal, steep, truth.lethal, truth_steep, truth_halo)
        result.update({f'{name}_{key}': value for key, value in dict(path, **scores).items()})
    return result


def run(row):
    experiment, patch, condition, rep = (row[k] for k in ('experiment', 'patch', 'condition', 'rep'))
    result = {key: row[key] for key in ('experiment', 'patch', 'condition', 'rep', 'visit_number',
                                        'goal_x', 'goal_y', 'failure_steep_inflated')}
    if experiment not in SOURCES:
        return dict(result, final_map_status='missing', map_source='missing',
                    reason='final map omitted from repository; no committed failure grid for this run')
    raw = RESULTS/SOURCES[experiment]/'runs'/patch/f'{condition}_r{rep}'/'physical_1'/'raw'/patch
    final = (ROOT/row['final_map']) if row['final_map'] else None
    if final is not None and final != raw/'pointcloud_map.npz':
        raise ValueError(f'unexpected final map path: {final}')
    if not final and experiment != '035':
        return dict(result, final_map_status='missing', map_source='missing', reason='046 has no final map for this run')
    failure = max((raw/'diag').glob('plan_fail_*.npz'))
    return dict(result, reason='' if final else 'final map omitted; using committed failure-time grid',
                **evaluate(row, final, failure))


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in ('patch', 'visit_number', 'goal_x', 'goal_y'))].append(row)
    summary = []
    for (patch, visit, x, y), group in sorted(groups.items()):
        row = dict(patch=patch, visit_number=visit, goal_x=x, goal_y=y, total=len(group))
        for source in ('final', 'failure_snapshot', 'missing'):
            subset = [r for r in group if r['map_source'] == source]
            row[source+'_n'] = len(subset)
            if source != 'missing':
                for key in ('sensor_route', 'prior_route', 'recovered'):
                    row[f'{source}_{key}'] = sum(r[key] for r in subset)
        summary.append(row)
    return summary


def main(output):
    failures = read_csv(RESULTS/'waypoint_feasibility/goal_cell.csv')
    keys = {(r['experiment'], r['patch'], r['condition'], r['rep']) for r in failures}
    if len(failures) != 35 or len(keys) != len(failures):
        raise ValueError('expected 35 unique failures from 046')
    rows = [run(row) for row in failures]
    summary = summarize(rows)
    output.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    write_csv(output/'runs.csv', [{key: row.get(key) for key in fields} for row in rows])
    write_csv(output/'goals.csv', summary)
    scores = []
    for source in ('final', 'failure_snapshot'):
        group = [r for r in rows if r['map_source'] == source]
        for patch in ('all', *sorted({r['patch'] for r in group})):
            subset = [r for r in group if patch == 'all' or r['patch'] == patch]
            row = dict(map_source=source, patch=patch, maps=len(subset),
                       seen_cells=sum(r['seen_cells'] for r in subset))
            for field in ERROR_FIELDS:
                old, new = (sum(r[f'{mode}_{field}'] for r in subset) for mode in ('sensor', 'prior'))
                row.update({f'sensor_{field}': old, f'prior_{field}': new, f'delta_{field}': new-old})
            row.update({field: sum(r[field] for r in subset) for field in NEW_MISSES})
            scores.append(row)
    write_csv(output/'map_errors.csv', scores)
    for name, data in [('goals', summary), ('map_errors', scores)]:
        print(name)
        print(','.join(data[0]))
        for row in data:
            print(','.join(map(str, row.values())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    main(parser.parse_args().out)
