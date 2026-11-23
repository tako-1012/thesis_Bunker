"""Re-evaluate saved goal-cell failures without opening blocked cells."""

import argparse
from ast import literal_eval
from collections import defaultdict
import csv
from functools import lru_cache
from pathlib import Path

import numpy as np

from experiments.eval_runs import read_csv as read_chunks, read_trajectory
from results.distance_clearance import replay as distance
from results.steep_near_obstacle import replay as steep_archive
from results.terrain_from_prior import replay as archive
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
from tapp.collision import line_of_sight_exact, path_lethal_cells
from tapp.config import RESOLUTION, Robot
from tapp.endpoint_policy import audit_path, load_snapshot
from tapp.goal_region import blocked_reason, choose_goal
from tapp.online_mission import OnlinePlanner
from tapp.planners import astar, smooth_cost_aware
from tapp.pointcloud_map_fine import PointCloudMapFine, steep_inflation_sources
from tapp.real_beach import load_patch
from tapp.traversability import TraversabilityMap, inflate, slope_deg

ROOT, RESULTS = archive.ROOT, archive.RESULTS
ROBOT = Robot()
RADIUS = ROBOT.footprint_radius


def is_final(file):
    return file.name == 'pointcloud_map.npz'


@lru_cache(maxsize=6)
def records(file, patch):
    physical = file.parents[2 if is_final(file) else 3]
    _, prior, truth = archive.load_reference(ROOT/physical, patch)
    if is_final(file):
        with np.load(ROOT/file, allow_pickle=False) as data:
            fine_shape = tuple(data['fine_shape'])
            sample = {key: data[key] for key in ('elev', 'cost', 'seen', 'lethal')}
            sample['fine_obstacle'] = np.unpackbits(data['fine_obstacle_bits'], count=int(np.prod(fine_shape))
                                                    ).reshape(fine_shape).astype(bool)
        dem = load_patch(patch, dataset='shizuoka_beach_las')
        raw_rock = ~np.isfinite(dem) | (dem < 0)
    else:
        sample = load_snapshot(ROOT/file)
        raw_rock = sample['prior_raw']
    assert np.array_equal(inflate(raw_rock, RADIUS), prior.rock)
    raw_boxes = distance.truth_obstacles(patch)
    assert np.array_equal(inflate(raw_boxes | raw_rock, RADIUS), truth.rock)
    return prior, truth, sample, raw_rock, raw_boxes


def scenario(file, patch, goal, terrain, clearance, steep_mode):
    prior, truth, sample, raw_rock, raw_boxes = records(file, patch)
    mapper = PointCloudMapFine(prior.elev, raw_rock, terrain_source=terrain, obstacle_clearance=clearance)
    prior_tm = TraversabilityMap(prior.elev, raw_rock)
    if terrain == 'sensor':
        mapper.tm.steep = slope_deg(sample['elev']) > ROBOT.max_slope_deg
        if is_final(file):
            mapper.tm.cost = sample['cost']
    mapper.seen = sample['seen']
    distance.install_mask(mapper, sample['fine_obstacle'])
    seeds = mapper.tm.steep
    if steep_mode == 'no_inflate':
        seeds = steep_inflation_sources(seeds, mapper._inflated_coarse)
    mapper._dilated_steep = inflate(seeds, RADIUS)
    mapper.lethal = mapper.tm.lethal | mapper._dilated_steep
    runtime = LidarOnlineMission(dict(tmap=prior_tm), mapper)
    try:
        planner = runtime._new_planner(OnlinePlanner, (goal,))
        runtime._observe(planner)
        lethal, cost = planner.planning_maps()
        original_open = not lethal[goal] or not getattr(planner, 'goal_overrides', {}).get(goal, True)
        if terrain == 'sensor' and clearance == 'centre':
            if steep_mode == 'keep':
                effective = mapper.lethal if is_final(file) else lethal
                recorded = sample.get('pre_policy_lethal', sample['lethal'])
                assert np.array_equal(effective, recorded), file
            if not is_final(file):
                cost = sample['cost']  # Saved weighted planning multiplier, not raw terrain cost.
        smooth = planner.distance_geometry.smooth if clearance == 'distance' else smooth_cost_aware
        return lethal, cost, original_open, mapper, truth, raw_boxes, smooth
    finally:
        runtime.close()


def run(info, file, start, goal, *, terrain='sensor', clearance='centre', steep_mode='keep'):
    lethal, cost, original_open, mapper, truth, raw_boxes, smooth = scenario(
        file, info['patch'], goal, terrain, clearance, steep_mode)
    full_halo = inflate(mapper.tm.steep, RADIUS)
    row = dict(info, record=str(file), start=str(start), original=str(goal), terrain=terrain,
               clearance=clearance, steep_mode=steep_mode, original_open=original_open,
               start_blocked=bool(lethal[start]), status='no_candidate')
    if original_open:
        row['status'] = 'original_open'
        blocked = lethal
        if lethal[goal]:
            assert clearance == 'overlap_goal'
            blocked = lethal.copy()
            blocked[goal] = False  # Existing centre clearance at the original waypoint.
        result = astar(blocked, start, goal, cost)
        if not result['success']:
            return dict(row, status='original_no_path')
        chosen = goal
    else:
        row['reason'] = blocked_reason(dict(obstacle_halo=mapper._inflated_coarse, steep=mapper.tm.steep,
            steep_halo=mapper._dilated_steep, prior_inflated=mapper._prior_rock,
            retained_lethal=lethal & ~mapper.seen), goal)
        choice = choose_goal(start, goal, lethal, cost, mapper.seen, full_halo)
        if choice is None:
            return row
        chosen, result = choice
        row['status'] = 'substitute'
        blocked = lethal
    path, _ = smooth(result['path'], blocked, cost, los=line_of_sight_exact)
    hits = path_lethal_cells(path, blocked)
    if row['status'] == 'substitute':
        assert not len(hits)
    steep = slope_deg(truth.elev) > ROBOT.max_slope_deg
    halo = inflate(steep, RADIUS)
    debris = truth.rock & ~mapper._prior_rock
    xy = np.asarray(path)*RESOLUTION
    return dict(row, chosen=str(chosen), shift_m=float(np.linalg.norm(np.subtract(chosen, goal))*RESOLUTION),
                target_truth_lethal=bool(truth.lethal[chosen]), target_true_steep=bool(steep[chosen]),
                target_true_steep_halo=bool(halo[chosen]), target_debris_map=bool(debris[chosen]),
                target_debris_raw=bool(raw_boxes[chosen]),
                path_truth_lethal_cells=len(path_lethal_cells(path, truth.lethal)),
                path_true_steep_cells=len(path_lethal_cells(path, steep)),
                path_true_steep_m=audit_path(xy, steep)['relaxed_length_m'],
                path_true_steep_halo_m=audit_path(xy, halo)['relaxed_length_m'],
                path_current_lethal_cells=len(hits),
                **distance.safety_metrics(path, *distance.rectangles(raw_boxes, RESOLUTION), debris))


def published_rows():
    keys = ('experiment', 'patch', 'condition', 'rep', 'visit_number')
    for row in archive.read_csv(RESULTS/'steep_near_obstacle/goal_runs.csv'):
        info = {k: row[k] for k in keys}
        stage = row['stage']
        if stage == 'missing':
            yield dict(info, series='046_047_055', stage=stage, status='missing', reason=row['reason'])
            continue
        file = Path(row['record'])
        start, goal = (tuple(int(row[f'{name}_{axis}']) for axis in 'xy') for name in ('start', 'goal'))
        for steep_mode in ('keep', 'no_inflate'):
            result = run(dict(info, series='046_047_055', stage=stage), file, start, goal, steep_mode=steep_mode)
            assert str(result['original_open']) == row[f'{steep_mode}_goal_open']
            yield result
        if stage == 'final' or info['experiment'] == '035':
            yield run(dict(info, series='047_prior', stage=stage), file, start, goal, terrain='prior')
    for file, series in [('runs.csv', '060'), ('supplement_00332_runs.csv', '060_00332')]:
        for row in archive.read_csv(RESULTS/'distance_clearance'/file):
            if row['goal_blocked'] != 'True':
                continue
            result = run(dict(series=series, stage='final', experiment='030' if series == '060' else '',
                              patch=row['patch'], condition=row['condition'], rep=row['rep'], visit_number=row['visit']),
                         Path(row['archive'])/'pointcloud_map.npz', literal_eval(row['start']), literal_eval(row['goal']),
                         terrain=row['terrain'], clearance=row['mode'])
            assert not result['original_open']
            yield result


def rollover_rows():
    patch = '08OB88_-0167'
    for rep in (1, 2, 3):
        raw = Path('results/eval_ground_endpoint/runs')/patch/f'C2_r{rep}'/'physical_1'/'raw'/patch
        replans = read_chunks(ROOT/raw/'replans.csv')[1]
        first = next(r for r in replans if r['leg_index'] == '4')
        t = float(first['t'])
        trace, _, _ = read_trajectory(ROOT/raw)
        sample = trace[np.searchsorted(trace[:, 0], t, side='right')-1]
        start = tuple(map(int, np.rint(sample[1:]/RESOLUTION)))
        info = dict(series='030_0167_C2', experiment='030', patch=patch, condition='C2', rep=rep, visit_number=5)
        goal = (137, 294)
        yield run(dict(info, stage='end_map_at_leg_entry_pose', pose_time_s=float(sample[0]),
                       leg_first_dispatch_s=t), raw/'pointcloud_map.npz', start, goal)
        for file in sorted((ROOT/raw/'diag').glob('plan_fail_*.npz')):
            snapshot = load_snapshot(file)
            if tuple(snapshot['goal']) == goal:
                yield run(dict(info, stage='failure_snapshot', pose_time_s=float(snapshot['sim_time']),
                               leg_first_dispatch_s=t), file.relative_to(ROOT), tuple(map(int, snapshot['start'])), goal)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        if row['status'] == 'missing':
            continue
        groups[tuple(row[k] for k in ('series', 'stage', 'terrain', 'clearance', 'steep_mode'))].append(row)
    result = []
    for key, group in groups.items():
        selected = [r for r in group if r['status'] == 'substitute']
        result.append(dict(zip(('series', 'stage', 'terrain', 'clearance', 'steep_mode'), key),
            truth_lethal_targets=sum(r['target_truth_lethal'] for r in selected),
            true_steep_targets=sum(r['target_true_steep'] for r in selected),
            debris_targets=sum(r['target_debris_map'] for r in selected),
            routes_touching_truth_lethal=sum(r['path_truth_lethal_cells'] > 0 for r in selected),
            routes_touching_true_steep=sum(r['path_true_steep_cells'] > 0 for r in selected),
            cases=len(group), blocked=sum(not r['original_open'] for r in group), substituted=len(selected),
            shift_050=sum(r['shift_m'] == .5 for r in selected),
            shift_diagonal=sum(.5 < r['shift_m'] < 1 for r in selected),
            shift_100=sum(r['shift_m'] == 1 for r in selected)))
    return result


def write_table(file, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with file.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main(output):
    rows = list(published_rows()) + list(rollover_rows())
    output.mkdir(parents=True, exist_ok=True)
    write_table(output/'runs.csv', rows)
    write_table(output/'summary.csv', summarize(rows))
    print((output/'summary.csv').read_text(), end='')
    print(f"Missing recorded grids: {sum(r['status'] == 'missing' for r in rows)}")
    for row in rows:
        if row['series'] == '030_0167_C2':
            print(row)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
