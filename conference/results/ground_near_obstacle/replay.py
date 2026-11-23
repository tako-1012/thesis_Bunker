"""Compare first-LiDAR ground medians on the 14 committed 053 runs."""

import argparse
from pathlib import Path

import numpy as np

from results.distance_clearance.replay import rectangles, truth_obstacles
from results.false_steep_causes import replay as causes
from results.steep_near_obstacle import replay as steep_archive
from results.terrain_from_prior import replay as archive
from tapp.config import RESOLUTION
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.traversability import inflate, slope_deg

ROOT = archive.ROOT
RESULTS = ROOT/'results'
IDENTITY = (*steep_archive.KEYS, 'visit_number', 'goal_x', 'goal_y')
RADIUS = causes.ROBOT.footprint_radius
MODES = ('keep', 'exclude')


def new_mapper(recorded, sensors, mode):
    settings = dict(ground_estimate='non_obstacle', ground_near_obstacle=mode,
                    robot=recorded.robot, weights=recorded.weights)
    args = recorded.prior, recorded.raw_obstacle
    if sensors == 'legacy':
        return PointCloudMapFine(*args, **settings, sensor_height_m=recorded.sensor_height_m,
                                 min_range_m=recorded.min_range_m, max_range_m=recorded.max_range_m,
                                 range_resolution_m=recorded.range_resolution_m)
    return PointCloudMapMulti(*args, **settings, sensors=sensors)


def box_near(patch, truth, water, nodata):
    debris = truth_obstacles(patch)
    if not np.array_equal(inflate(debris | water | nodata, RADIUS), truth.rock):
        raise ValueError(f'{patch}: box render inputs disagree with signed truth rocks')
    lower, upper = rectangles(debris, RESOLUTION)
    x, y = np.ogrid[:debris.shape[0], :debris.shape[1]]
    nearby = np.zeros(debris.shape, bool)
    for (x0, y0), (x1, y1) in zip(lower, upper):
        dx = np.maximum(np.maximum(x0 - x*RESOLUTION, x*RESOLUTION - x1), 0.)
        dy = np.maximum(np.maximum(y0 - y*RESOLUTION, y*RESOLUTION - y1), 0.)
        nearby |= np.hypot(dx, dy) <= RADIUS
    return nearby


def safety(seen, lethal, real, real_halo, near):
    missed = seen & ~lethal
    return dict(
        observed_cells=int(seen.sum()),
        true_steep_seen=int((seen & real).sum()),
        true_halo_only_seen=int((seen & real_halo & ~real).sum()),
        true_steep_or_halo_near_true_box_seen=int((seen & real_halo & near).sum()),
        true_steep_near_true_box_seen=int((seen & real & near).sum()),
        passable_true_steep=int((missed & real).sum()),
        passable_true_halo_only=int((missed & real_halo & ~real).sum()),
        passable_true_steep_or_halo=int((missed & real_halo).sum()),
        passable_true_steep_or_halo_near_true_box=int((missed & real_halo & near).sum()),
        passable_true_steep_near_true_box=int((missed & real & near).sum()),
        passable_true_halo_only_near_true_box=int((missed & real_halo & near & ~real).sum()),
    )


def accuracy(features, seen, lethal, truth, water, nodata):
    classes, kinds = causes.classify(features)
    raw_false = classes['false_steep'] & seen & ~(water | nodata)
    classified = np.logical_or.reduce(tuple(kinds.values()))
    real_halo = inflate(features['truth_slope_deg'] > causes.ROBOT.max_slope_deg, RADIUS)
    domain = seen & ~truth.lethal & ~real_halo
    steep_halo = inflate(features['estimated_slope_deg'] > causes.ROBOT.max_slope_deg, RADIUS)
    return dict(raw_false_steep=int(raw_false.sum()),
                **{f'raw_false_{kind}': int((raw_false & mask).sum()) for kind, mask in kinds.items()},
                raw_false_no_type=int((raw_false & ~classified).sum()),
                false_steep_blocked=int((lethal & steep_halo & domain).sum()),
                false_all_layers_blocked=int((lethal & domain).sum()))


def metrics(row, stage, mode, recorded_ground, truth, terrain, counts, water, nodata, near, sample):
    seen, lethal = sample['seen'], sample['lethal']
    features = causes.map_features(terrain, counts, sample['elev'], seen, sample['fine_obstacle'],
                                  sample['fine_inflated'], nodata)
    real = terrain['truth_slope_deg'] > causes.ROBOT.max_slope_deg
    return dict(**{k: row[k] for k in steep_archive.KEYS}, stage=stage, mode=mode,
                recorded_ground=recorded_ground, version=int(sample['version']),
                fine_obstacle_cells=int(sample['fine_obstacle'].sum()),
                **safety(seen, lethal, real, inflate(real, RADIUS), near),
                **accuracy(features, seen, lethal, truth, water, nodata))


def summarize_maps(rows):
    totals = []
    for stage, mode in [('first_lidar', 'keep'), ('first_lidar', 'exclude'), ('recorded_final', 'recorded')]:
        for patch in ('all', *sorted({r['patch'] for r in rows})):
            group = [r for r in rows if r['stage'] == stage and r['mode'] == mode
                     and (patch == 'all' or r['patch'] == patch)]
            fields = list(group[0])[list(group[0]).index('fine_obstacle_cells'):]
            totals.append(dict(stage=stage, mode=mode, patch=patch, maps=len(group),
                               **{key: sum(r[key] for r in group) for key in fields}))
    return totals


def exclusion_effect(keep, exclude):
    affected_cells = excluded_returns = held_cells = 0
    for key, history in exclude.samples.items():
        low = history[:, 1] < exclude.obstacle_height_m
        masked = low & exclude._ground_excluded.flat[exclude._fine_ids[key]]
        if masked.any():
            affected_cells += 1
            excluded_returns += int(masked.sum())
            held_cells += int(not (low & ~masked).any())
    return dict(excluded_low_returns=excluded_returns, cells_with_excluded_returns=affected_cells,
                held_cells=held_cells, heights_different_from_keep=int((exclude.elev != keep.elev).sum()),
                steep_cells_different_from_keep=int((exclude.tm.steep ^ keep.tm.steep).sum()),
                lethal_cells_different_from_keep=int((exclude.lethal ^ keep.lethal).sum()))


def replay_first(row, raw, tracked):
    _, recorded_ground, sensors, _, truth, water, nodata, recorded, final, terrain = causes.read_record(
        ROOT, tracked, raw, row)
    first = raw/'first_cloud.npz'
    with np.load(ROOT/first, allow_pickle=False) as cloud:
        points, pose = cloud['points'], cloud['pose']
    mappers = {mode: new_mapper(recorded, sensors, mode) for mode in MODES}
    for mapper in mappers.values():
        mapper.update(points, pose)
    keep, exclude = (mappers[mode] for mode in MODES)
    for field in ('seen', 'fine_obstacle', 'fine_inflated', 'detected_obstacle'):
        assert np.array_equal(getattr(keep, field), getattr(exclude, field))
    assert np.array_equal(keep.fine_obstacle, recorded.fine_obstacle)
    if recorded_ground == 'non_obstacle':
        assert np.array_equal(keep.elev, recorded.elev)
    counts = causes.first_counts(keep)
    near = box_near(row['patch'], truth, water, nodata)
    map_rows = [metrics(row, 'first_lidar', mode, recorded_ground, truth, terrain, counts, water, nodata,
                        near, vars(mapper)) for mode, mapper in mappers.items()]
    map_rows[1].update(exclusion_effect(keep, exclude))
    map_rows.append(metrics(row, 'recorded_final', 'recorded', recorded_ground, truth, terrain, counts, water,
                            nodata, near, final))

    start = tuple(int(row[f'start_{a}']) for a in 'xy')
    goal = tuple(int(row[f'goal_{a}']) for a in 'xy')
    base = new_mapper(recorded, sensors, 'keep')
    x, y = np.ogrid[:keep.prior.shape[0], :keep.prior.shape[1]]
    nearby = ((x-goal[0])*RESOLUTION)**2+((y-goal[1])*RESOLUTION)**2
    goal_row = dict(**{k: row[k] for k in IDENTITY}, stage='first_lidar', record=str(first),
                    start_x=start[0], start_y=start[1], start_seen=bool(keep.seen[start]),
                    goal_seen=bool(keep.seen[goal]), seen_within_2m=int((keep.seen & (nearby <= 4.)).sum()),
                    changed_heights_within_2m=int(((keep.elev != exclude.elev) & (nearby <= 4.)).sum()))
    for mode, mapper in mappers.items():
        result = archive.route(base, mapper.seen, mapper.tm.cost, mapper.lethal, start, goal)
        goal_row.update({f'{mode}_{key}': value for key, value in result.items()})
        goal_row[f'{mode}_steep_in_goal_halo'] = int((mapper.tm.steep & (nearby <= RADIUS**2)).sum())
        goal_row[f'{mode}_measured_lethal_at_goal'] = bool(mapper.lethal[goal] and mapper.seen[goal])
    return map_rows, goal_row


def observed_goals():
    for row in archive.read_csv(RESULTS/'steep_near_obstacle/goal_runs.csv'):
        stage = row['stage']
        # These are the original maps' masks and the 055 baseline search.
        # The history needed to recompute the ground median is absent.
        yield dict(**{k: row[k] for k in IDENTITY}, stage=stage, record=row['record'],
                   recorded_goal_open=row['keep_goal_open'], recorded_route=row['keep_route'],
                   recorded_steep_inflation_at_goal=row['keep_steep_halo_at_goal'],
                   reason=('no committed grid or first scan' if stage == 'missing' else 'no retained point history'))


def summarize_goals(rows):
    for stage in ('first_lidar', 'recorded_final', 'failure_snapshot', 'missing'):
        subset = [r for r in rows if r['stage'] == stage]
        for patch in ('all', *sorted({r['patch'] for r in subset})):
            group = [r for r in subset if patch == 'all' or r['patch'] == patch]
            if stage == 'first_lidar':
                keys = ('start_seen', 'goal_seen', 'keep_goal_open', 'exclude_goal_open', 'keep_route', 'exclude_route')
                counts = {k: sum(r[k] for r in group) for k in keys}
            elif stage != 'missing':
                counts = {k: sum(r[k] == 'True' for r in group) for k in ('recorded_goal_open', 'recorded_route')}
            else:
                counts = {}
            yield dict(stage=stage, patch=patch, records=len(group), **counts)


def main(output):
    tracked = causes.committed_inputs(ROOT)
    primary = {raw: row for raw, row, _ in causes.discover(ROOT, tracked) if row}
    steep_archive.verify_cohort(primary)
    maps, goals = [], []
    for raw, row in sorted(primary.items()):
        map_rows, goal = replay_first(row, raw, tracked)
        maps.extend(map_rows)
        goals.append(goal)
    for row in observed_goals():
        if row['stage'] == 'final':
            row = dict(row, stage='recorded_final')
        goals.append(row)
    output.mkdir(parents=True, exist_ok=True)
    tables = dict(map_runs=maps, maps=summarize_maps(maps), goal_runs=goals, goals=list(summarize_goals(goals)))
    for name, rows in tables.items():
        columns = list(dict.fromkeys(k for row in rows for k in row))
        path = output/(name+'.csv')
        causes.write_csv(path, [{k: row.get(k) for k in columns} for row in rows])
        if name in ('maps', 'goals'):
            print(name)
            print(path.read_text(), end='')
    print('0167 visit 5, first LiDAR only')
    for row in goals:
        if row['stage'] == 'first_lidar' and row['patch'] == '08OB88_-0167' and row['visit_number'] == '5':
            print(f"{row['condition']}_r{row['rep']}: goal seen={row['goal_seen']}, "
                  f"heights changed within 2m={row['changed_heights_within_2m']}, "
                  f"steep seeds={row['keep_steep_in_goal_halo']}->{row['exclude_steep_in_goal_halo']}, "
                  f"open={row['keep_goal_open']}->{row['exclude_goal_open']}, "
                  f"route={row['keep_route']}->{row['exclude_route']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    main(parser.parse_args().out)
