"""Compare slope uncertainty on the committed first LiDAR clouds of 053 and 062."""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

from results.false_steep_causes import replay as causes
from results.ground_near_obstacle import replay as ground_archive
from results.terrain_from_prior import replay as archive
from tapp.config import RESOLUTION
from tapp.endpoint_policy import audit_path, load_snapshot
from tapp.online_mission import OnlinePlanner
from tapp.planners import astar, smooth_cost_aware
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.slope_uncertainty import LOWER_95_Z, slope_standard_error
from tapp.traversability import inflate

ROOT = causes.ROOT
RESULTS = ROOT/'results'
RADIUS = causes.ROBOT.footprint_radius
LIMIT_DEG = causes.ROBOT.max_slope_deg
LIMIT_TAN = np.tan(np.deg2rad(LIMIT_DEG))
TARGET_PATCH = '08OB88_-0167'
CELLS = ((137, 293), (137, 294))
MODES = ('none', 'soft')
TYPE_NAMES = ('all', *causes.TYPES, 'no_type')


def mapper_like(original, sensors, estimate, obstacle_filter, mode):
    settings = dict(ground_estimate=estimate, ground_near_obstacle=obstacle_filter, slope_uncertainty=mode,
                    robot=original.robot, weights=original.weights)
    args = original.prior, original.raw_obstacle
    if sensors != 'legacy':
        return PointCloudMapMulti(*args, sensors=sensors, **settings)
    return PointCloudMapFine(*args, sensor_height_m=original.sensor_height_m, min_range_m=original.min_range_m,
                             max_range_m=original.max_range_m, range_resolution_m=original.range_resolution_m,
                             **settings)


def terrain_metrics(identity, baseline, soft, terrain):
    seen = baseline.seen
    true_steep = terrain['truth_slope_deg'] > LIMIT_DEG
    true_halo_only = inflate(true_steep, RADIUS) & ~true_steep
    released = baseline.lethal & ~soft.lethal
    assert not (soft.lethal & ~baseline.lethal).any()
    assert np.array_equal(baseline.elev, soft.elev)
    for layer in ('seen', 'fine_obstacle', 'fine_inflated', 'detected_obstacle'):
        assert np.array_equal(getattr(baseline, layer), getattr(soft, layer))
    result = dict(identity, observed_cells=int(seen.sum()), uncertainty_seeds_all=int(soft.uncertain_steep.sum()),
                  reclassified_true_steep_seen=int((true_steep & seen & soft.uncertain_steep).sum()))
    route_masks = {}
    for label, region in [('true_steep', true_steep), ('true_halo_only', true_halo_only)]:
        result[f'{label}_seen'] = int((seen & region).sum())
        result[f'none_passable_{label}_seen'] = int((seen & ~baseline.lethal & region).sum())
        result[f'soft_passable_{label}_seen'] = int((seen & ~soft.lethal & region).sum())
        result[f'released_{label}_seen'] = int((seen & released & region).sum())
        result[f'released_{label}_all'] = int((released & region).sum())
        route_masks[label] = region
        route_masks[f'released_{label}_seen'] = seen & released & region
        route_masks[f'released_{label}_all'] = released & region
    return result, route_masks


def false_types(identity, baseline, soft, terrain, water, nodata):
    features = dict(terrain, estimated_slope_deg=baseline.tm.slope,
                    box_halo_m=causes.fine_distance(baseline.fine_inflated),
                    first_3x3_points=causes.first_counts(baseline)['first_3x3_points'])
    classes, kinds = causes.classify(features)
    false_steep = classes['false_steep'] & baseline.seen & ~(water | nodata)
    kinds.update(all=np.ones_like(false_steep), no_type=~np.logical_or.reduce(tuple(kinds.values())))
    rows = []
    for kind in TYPE_NAMES:
        domain = false_steep & kinds[kind]
        rows.append(dict(identity, kind=kind, false_steep=int(domain.sum()),
                         reclassified=int((domain & soft.uncertain_steep).sum())))
    return rows


def planner_route(initial, mapper, start, goal, route_masks):
    planner = OnlinePlanner(initial.tm.cost, initial.lethal, initial.weights, prior_lethal_mode='soft')
    planner.observe(*mapper.planning_snapshot())
    blocked, cost = planner.planning_maps()
    row = dict(goal_open=not bool(blocked[goal]), start_blocked=bool(blocked[start]), route=False)
    if blocked[goal]:
        return row
    result = astar(blocked, start, goal, cost)
    if not result['success']:
        return row
    path, _ = smooth_cost_aware(result['path'], blocked, cost, los=planner.los)
    xy = np.asarray(path)*RESOLUTION
    return dict(row, route=True, route_length_m=float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum()),
                **{f'{label}_m': audit_path(xy, mask)['relaxed_length_m'] for label, mask in route_masks.items()})


def replay_first(raw, primary, tracked, target_identities):
    reference, recorded_ground, sensors, _, _, water, nodata, base, _, terrain = causes.read_record(
        ROOT, tracked, raw, primary)
    with np.load(ROOT/raw/'first_cloud.npz', allow_pickle=False) as cloud:
        points, pose = cloud['points'], cloud['pose']
    configs = [('recorded', recorded_ground, 'keep')]
    if primary:
        configs += [('062_keep', 'non_obstacle', 'keep'), ('062_exclude', 'non_obstacle', 'exclude')]
    map_rows, type_rows, goal_rows, details = [], [], [], []
    cohort = causes.cohort_name(raw, primary, sensors)
    for config, estimate, obstacle_filter in configs:
        original_config = (estimate, obstacle_filter) == (recorded_ground, 'keep')
        baseline = base if original_config else mapper_like(base, sensors, estimate, obstacle_filter, 'none')
        soft = mapper_like(base, sensors, estimate, obstacle_filter, 'soft')
        if not original_config:
            baseline.update(points, pose)
        soft.update(points, pose)
        identity = dict(raw=str(raw), patch=raw.name, cohort=cohort, config=config,
                        ground_estimate=estimate, ground_near_obstacle=obstacle_filter, reference=str(reference))
        metrics, route_masks = terrain_metrics(identity, baseline, soft, terrain)
        map_rows.append(metrics)
        type_rows.extend(false_types(identity, baseline, soft, terrain, water, nodata))
        if not primary:
            continue
        start, goal = (tuple(int(primary[f'{key}_{axis}']) for axis in 'xy') for key in ('start', 'goal'))
        initial = mapper_like(base, sensors, estimate, obstacle_filter, 'none')
        for mode, mapper in zip(MODES, (baseline, soft)):
            row = dict(**{key: primary[key] for key in ground_archive.IDENTITY}, stage='first_lidar',
                       config=config, mode=mode, record=str(raw/'first_cloud.npz'),
                       start_seen=bool(mapper.seen[start]), goal_seen=bool(mapper.seen[goal]),
                       **planner_route(initial, mapper, start, goal, route_masks))
            goal_rows.append(row)
        run_key = tuple(primary[key] for key in ('condition', 'rep'))
        if raw.name == TARGET_PATCH and config == 'recorded' and run_key in target_identities:
            sigma_s = slope_standard_error(soft.tm.gx, soft.tm.gy, soft.sigma_h)
            for cell in CELLS:
                details.append(dict(patch=raw.name, condition=primary['condition'], rep=primary['rep'],
                                    stage='first_lidar', x=cell[0], y=cell[1], seen=bool(soft.seen[cell]),
                                    angle_deg=float(soft.tm.slope[cell]),
                                    truth_angle_deg=float(terrain['truth_slope_deg'][cell]),
                                    sigma_h_m=float(soft.sigma_h[cell]), sigma_s=float(sigma_s[cell]),
                                    none_steep=bool(baseline.tm.steep[cell]), soft_steep=bool(soft.tm.steep[cell]),
                                    uncertain_steep=bool(soft.uncertain_steep[cell]), record=str(raw/'first_cloud.npz')))
    return map_rows, type_rows, goal_rows, details


def archived_goals():
    for row in archive.read_csv(RESULTS/'steep_near_obstacle/goal_runs.csv'):
        keys = ('stage', 'record', *ground_archive.IDENTITY)
        yield dict(**{key: row[key] for key in keys}, config='recorded', mode='none',
                   goal_open=row['keep_goal_open'], route=row['keep_route'], start_blocked=row['keep_start_blocked'],
                   soft_missing=('no committed grid' if row['stage'] == 'missing' else 'no retained ground point history'))


def archived_cells(prior_goals, tracked):
    for row in prior_goals:
        if row['patch'] != TARGET_PATCH or row['stage'] not in ('final', 'failure_snapshot'):
            continue
        path = Path(row['record'])
        causes.require(ROOT, tracked, path)
        if row['stage'] == 'final':
            with np.load(ROOT/path, allow_pickle=False) as saved:
                elev, seen = saved['elev'], saved['seen']
        else:
            saved = load_snapshot(ROOT/path)
            elev, seen = saved['elev'], saved['seen']
        gx, gy = np.gradient(elev, RESOLUTION)
        tangent = np.hypot(gx, gy)
        angle = np.degrees(np.arctan(tangent))
        for cell in CELLS:
            needed = (tangent[cell]-LIMIT_TAN)/LOWER_95_Z if angle[cell] > LIMIT_DEG else None
            yield dict(patch=row['patch'], condition=row['condition'], rep=row['rep'], experiment=row['experiment'],
                       stage=row['stage'], x=cell[0], y=cell[1], seen=bool(seen[cell]),
                       angle_deg=float(angle[cell]), none_steep=bool(angle[cell] > LIMIT_DEG),
                       sigma_s_needed_for_soft=needed, record=row['record'], soft_missing=row['soft_missing'])


def summarize(rows, group_keys, totals):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
    for key, group in sorted(groups.items()):
        yield dict(zip(group_keys, key), maps=len(group),
                   **{column: sum(row[column] for row in group) for column in totals})


def route_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['stage'], row['config'], row['mode']].append(row)
    for (stage, config, mode), group in sorted(groups.items()):
        result = dict(stage=stage, config=config, mode=mode, records=len(group))
        if stage != 'missing':
            result.update(goal_open=sum(row['goal_open'] in (True, 'True') for row in group),
                          route=sum(row['route'] in (True, 'True') for row in group))
        if stage == 'first_lidar':
            for key in ('true_steep_m', 'true_halo_only_m', 'released_true_steep_seen_m',
                        'released_true_halo_only_seen_m', 'released_true_steep_all_m',
                        'released_true_halo_only_all_m'):
                lengths = [row.get(key, 0.) for row in group]
                result[key] = sum(lengths)
                result[key.removesuffix('_m')+'_routes'] = sum(value > 0. for value in lengths)
        yield result


def main(output):
    tracked = causes.committed_inputs(ROOT)
    primary = {raw: row for raw, row, _ in causes.discover(ROOT, tracked) if row}
    inventory = archive.read_csv(RESULTS/'false_steep_causes/inventory.csv')
    target_rows = archive.read_csv(RESULTS/'false_steep_causes/goal_cells.csv')
    target_identities = {(row['condition'], row['rep']) for row in target_rows if row['stage'] == 'first_lidar'}
    maps, types, goals, details = [], [], [], []
    for evidence in inventory:
        raw = Path(evidence['raw'])
        if evidence['status'] != 'used':
            print(f"skipped {raw}: {evidence['reason']}")
            continue
        for rows, new in zip((maps, types, goals, details), replay_first(raw, primary.get(raw), tracked, target_identities)):
            rows.extend(new)
    historical = list(archived_goals())
    goals.extend(historical)
    details.extend(archived_cells(historical, tracked))
    recorded = sum(row['config'] == 'recorded' for row in maps)
    print(f'{recorded} first LiDAR archives reprocessed; {len(inventory)-recorded} previously excluded archives')
    print('Final and failure snapshots lack adopted ground point histories; soft is uncalculated.')
    safety_columns = list(maps[0])[list(maps[0]).index('observed_cells'):]
    type_summary = list(summarize(types, ('cohort', 'config', 'kind'), ('false_steep', 'reclassified')))
    for row in type_summary:
        row['reclassified_percent'] = causes.percent(row['reclassified'], row['false_steep'])
    tables = dict(map_runs=maps, safety=list(summarize(maps, ('cohort', 'config'), safety_columns)),
                  types=type_summary, goal_runs=goals, goals=list(route_summary(goals)), goal_cells=details)
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        columns = list(dict.fromkeys(k for row in rows for k in row))
        path = output/(name+'.csv')
        causes.write_csv(path, [{key: row.get(key) for key in columns} for row in rows])
        if name in ('safety', 'types', 'goals', 'goal_cells'):
            print(name)
            print(path.read_text(), end='')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
