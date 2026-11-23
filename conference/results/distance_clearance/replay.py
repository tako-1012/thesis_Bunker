"""Replan the 053 cohort and measure continuous paths against truth boxes."""

import argparse
import csv
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.ndimage import find_objects, label

from experiments.eval_runs import contacts, near_intervals
from results.false_steep_causes import replay as causes
from results.terrain_from_prior import replay as archive
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
from tapp.config import RESOLUTION
from tapp.obstacle_clearance import path_clearance, point_clearance
from tapp.online_mission import OnlinePlanner
from tapp.planners import segment_cost
from tapp.pointcloud_map_fine import FINE_CLEARANCE_MODES, FINE_RESOLUTION, PointCloudMapFine, RATIO
from tapp.real_beach import build_real
from tapp.traversability import inflate, slope_deg

ROOT = archive.ROOT
FOLDER = Path(__file__).resolve().parent


def distance_band_length(path, lower, upper, radius):
    # The common evaluator clips segments at 0.5 m. Uniform scaling
    # changes its radius without changing a segment's fractional interval.
    factor = causes.ROBOT.footprint_radius/radius
    length = 0.
    for a, b in zip(path, path[1:]):
        candidates = ((lower-radius < np.maximum(a, b)) & (upper+radius > np.minimum(a, b))).all(axis=1)
        for first, last in near_intervals(a*factor, b*factor, lower[candidates]*factor, upper[candidates]*factor):
            length += (last-first)*np.linalg.norm(b-a)
    return float(length)


def safety_metrics(path, lower, upper, debris=None):
    xy = np.asarray(path)*RESOLUTION
    return dict(min_box_m=path_clearance(xy, lower, upper),
                start_box_m=point_clearance(xy[0], lower, upper), goal_box_m=point_clearance(xy[-1], lower, upper),
                below_05_m=distance_band_length(xy, lower, upper, .5),
                below_10_m=distance_band_length(xy, lower, upper, 1.),
                debris_m=contacts(xy, debris)[0] if debris is not None else None)


@lru_cache(maxsize=4)
def truth_obstacles(patch):
    return build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')['terrain']['rock']


def rectangles(obstacles, resolution):
    components = [region for region in find_objects(label(obstacles)[0]) if region is not None]
    lower = np.array([[s.start*resolution-RESOLUTION/2 for s in region] for region in components]).reshape(-1, 2)
    upper = np.array([[s.stop*resolution-RESOLUTION/2 for s in region] for region in components]).reshape(-1, 2)
    return lower, upper


def install_mask(mapper, fine):
    mapper._add_obstacles(np.flatnonzero(fine).tolist())
    mapper.tm.rock = mapper._prior_rock | mapper._inflated_coarse
    mapper.tm.lethal = mapper.tm.rock | mapper.tm.steep
    mapper.lethal = mapper.tm.lethal | mapper._dilated_steep


def plan(mapper, prior_tm, start, goal):
    runtime = LidarOnlineMission(dict(tmap=prior_tm), mapper)
    try:
        planner = runtime._new_planner(OnlinePlanner, (goal,))
        runtime._observe(planner)
        result = planner.start_leg(start, goal)
        blocked, _ = planner.planning_maps()
        if goal in getattr(planner, 'goal_overrides', {}) and not planner.goal_overrides[goal]:
            blocked[goal] = False
        path = result['path']
        info = dict(goal_blocked=bool(blocked[goal]), route=result['success'])
        if path:
            terrain = np.where(planner.known, mapper.tm.cost,
                               np.where(planner.prior_lethal, 1., planner.prior_cost))
            info.update(path_m=float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum()*RESOLUTION),
                        terrain_cost_m=float(sum(segment_cost(terrain, a, b) for a, b in
                                                 zip(path, path[1:]))*RESOLUTION))
        return info, path
    finally:
        runtime.close()


def replay_map(raw, tracked, legs, primary=None):
    _, _, _, _, truth, water, nodata, recorded, final, _ = causes.read_record(ROOT, tracked, raw, primary)
    raw_rocks = truth_obstacles(raw.name)
    radius = recorded.robot.footprint_radius
    if not np.array_equal(inflate(raw_rocks | water | nodata, radius), truth.rock):
        raise ValueError(f'{raw}: reconstructed truth rocks differ from the signed reference')
    # The archives omit debris_footprints.csv. Recreate the exporter's
    # XY bounds from the same connected raw debris components.
    bounds = rectangles(raw_rocks, RESOLUTION)
    debris = truth.rock & ~recorded._prior_rock
    prior_tm = PointCloudMapFine(recorded.prior, recorded.raw_obstacle).tm
    with np.load(ROOT/raw/'pointcloud_map.npz', allow_pickle=False) as data:
        saved_terrain_cost = data['cost']
    for terrain in ('sensor', 'prior'):
        for mode in FINE_CLEARANCE_MODES:
            mapper = PointCloudMapFine(recorded.prior, recorded.raw_obstacle, obstacle_clearance=mode,
                                       terrain_source=terrain)
            if terrain == 'sensor':
                mapper.tm.cost = saved_terrain_cost
                mapper.tm.steep = slope_deg(final['elev']) > mapper.robot.max_slope_deg
                mapper._dilated_steep = inflate(mapper.tm.steep, radius)
            mapper.seen = final['seen']
            install_mask(mapper, final['fine_obstacle'])
            if terrain == 'sensor' and mode == 'centre':
                assert np.array_equal(mapper.lethal, final['lethal'])
            for visit, start, goal in legs:
                info, path = plan(mapper, prior_tm, start, goal)
                if primary is not None and mode == 'centre':
                    assert str(info['route']) == primary[f'{terrain}_route']
                yield dict(archive=str(raw), patch=raw.name, condition=primary['condition'] if primary else '',
                           rep=primary['rep'] if primary else '', visit=visit, start=str(start), goal=str(goal),
                           terrain=terrain, mode=mode, **info,
                           **(safety_metrics(path, *bounds, debris) if path else {}))


def replay_archives(tracked):
    runs = [(raw, row) for raw, row, _ in causes.discover(ROOT, tracked) if row]
    if len(runs) != 14:
        raise ValueError('expected the 14 primary 053 archives')
    for raw, row in runs:
        start, goal = (tuple(int(row[f'{key}_{axis}']) for axis in 'xy') for key in ('start', 'goal'))
        yield from replay_map(raw, tracked, [(row['visit_number'], start, goal)], row)


def replay_00332(tracked):
    # The primary cohort has no 00332 grid, and 050 raw maps are not
    # committed. Use the sole 00332 final grid accepted by 053 separately.
    patch = '08OB88_00332'
    row, = [row for row in archive.read_csv(ROOT/'results/false_steep_causes/runs.csv')
            if row['patch'] == patch and row['stage'] == 'final']
    raw = Path(row['raw'])
    manifest_path = raw.parents[1]/'manifest.json'
    causes.require(ROOT, tracked, manifest_path)
    manifest = causes.json_file(ROOT/manifest_path)
    case, = [case for case in manifest['scenarios'] if case['patch'] == patch]
    stops = [tuple(case['start']), *map(tuple, case['stops'])]
    legs = [(visit, a, b) for visit, (a, b) in enumerate(zip(stops, stops[1:]), 1)]
    yield from replay_map(raw, tracked, legs)


def narrow_case(gap_m, *, forced=False):
    shape = (36, 36)
    fine = np.zeros(tuple(n*RATIO for n in shape), bool)
    gap = round(gap_m/FINE_RESOLUTION)
    left = (155-gap)//2
    right = left+gap
    fine[60:90, left-25:left] = True
    fine[60:90, right:right+25] = True
    rock = np.zeros(shape, bool)
    if forced:
        # Prior-rock walls outside the boxes leave the gap as the only crossing.
        rock[:, :11] = True
        rock[:, 20:] = True
    start, goal = (4, 15), (30, 15)
    prior = PointCloudMapFine(np.zeros(shape), rock).tm
    for mode in FINE_CLEARANCE_MODES:
        mapper = PointCloudMapFine(np.zeros(shape), rock, obstacle_clearance=mode)
        mapper.seen[:] = True
        install_mask(mapper, fine)
        info, path = plan(mapper, prior, start, goal)
        if path:
            info.update(detour_m=info['path_m']-(goal[0]-start[0])*RESOLUTION,
                        **safety_metrics(path, *rectangles(fine, FINE_RESOLUTION)))
        yield dict(gap_m=gap_m, forced=forced, mode=mode, **info)


def summarize(rows, dimension='maps'):
    for terrain in ('sensor', 'prior'):
        for mode in FINE_CLEARANCE_MODES:
            selected = [row for row in rows if row['terrain'] == terrain and row['mode'] == mode]
            paths = [row for row in selected if row['route']]
            minimums = [row['min_box_m'] for row in paths]
            yield dict(terrain=terrain, mode=mode, **{dimension: len(selected)}, min_box_m=min(minimums, default=None),
                       median_box_m=float(np.median(minimums)) if paths else None,
                       **{key: sum(row[key] for row in paths) for key in ('below_05_m', 'below_10_m', 'debris_m')},
                       blocked_goals=sum(row['goal_blocked'] for row in selected), routes=len(paths),
                       **{key+'_mean': sum(row[key] for row in paths)/len(paths) if paths else None
                          for key in ('path_m', 'terrain_cost_m')})


def write_table(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    tracked = causes.committed_inputs(ROOT)
    rows = list(replay_archives(tracked))
    additional = list(replay_00332(tracked))
    tables = dict(runs=rows, summary=list(summarize(rows)),
                  supplement_00332_runs=additional, supplement_00332=list(summarize(additional, 'legs')),
                  narrow=[row for gap in (1.2, 1.8, 2.5) for forced in (False, True)
                          for row in narrow_case(gap, forced=forced)])
    for name, records in tables.items():
        path = output/(name+'.csv')
        write_table(path, records)
        if not name.endswith('runs'):
            print(path.name)
            print(path.read_text(), end='')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=FOLDER)
    main(parser.parse_args().out)
