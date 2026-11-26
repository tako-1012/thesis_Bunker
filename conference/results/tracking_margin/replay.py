"""Compare task070 on the fourteen archived task065 maps and forced corridors."""

import argparse
from itertools import product
from pathlib import Path

import numpy as np

from results.distance_clearance import replay as boxes
from results.false_steep_causes import replay as causes
from results.steep_clearance import replay as slopes
from results.terrain_from_prior import replay as archive
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
from tapp.config import RESOLUTION
from tapp.distance_clearance import SegmentClearance
from tapp.obstacle_clearance import cell_boxes
from tapp.online_mission import OnlinePlanner
from tapp.planners import segment_cost
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.tracking_margin import FIXED_HARD_M, TRACKING_MARGINS
from tapp.traversability import inflate, slope_deg

ROOT = archive.ROOT
RADIUS = slopes.RADIUS
TERRAINS = ('sensor', 'prior')


def plan(mapper, prior_tm, start, goal):
    runtime = LidarOnlineMission(dict(tmap=prior_tm), mapper)
    try:
        planner = runtime._new_planner(OnlinePlanner, (goal,))
        runtime._observe(planner)
        result = planner.start_leg(start, goal)
        blocked, cost = planner.planning_maps()
        margin = planner.tracking_clearance
        original = blocked
        if margin is not None:
            original = blocked | margin.protected(())
            blocked, _, labels, _, _ = margin.project(blocked, cost, start, goal, planner.w)
            assert labels == result['tracking_margin_relaxed']
        labels = result.get('tracking_margin_relaxed', '').split('|')
        info = dict(start_blocked=bool(blocked[start]), goal_blocked=bool(blocked[goal]),
                    raw_start_blocked=bool(original[start]), raw_goal_blocked=bool(original[goal]),
                    relaxed_start='start' in labels, relaxed_goal='goal' in labels,
                    route=result['success'])
        path = result['path']
        if path:
            terrain = np.where(planner.known, mapper.tm.cost,
                               np.where(planner.prior_lethal, 1., planner.prior_cost))
            info.update(path_m=float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum()*RESOLUTION),
                        terrain_cost_m=float(sum(segment_cost(terrain, a, b) for a, b in
                                                 zip(path, path[1:]))*RESOLUTION))
        return info, path
    finally:
        runtime.close()


def reference_rows():
    return {(row['archive'], row['terrain']): row for row in
            archive.read_csv(ROOT/'results/steep_clearance/runs.csv')
            if row['obstacle_clearance'] == row['steep_clearance'] == 'distance'}


def compare_none(row, reference):
    for key, expected in reference.items():
        if expected == '':
            assert key not in row, (key, row)
            continue
        actual = row[key]
        if isinstance(actual, (float, np.floating)):
            assert np.isclose(actual, float(expected), rtol=0., atol=1e-10), (key, actual, expected)
        else:
            assert str(actual) == expected, (key, actual, expected)


def archived_cases(tracked):
    cohort = [(raw, row) for raw, row, _ in causes.discover(ROOT, tracked) if row]
    reference = reference_rows()
    assert len(cohort) == 14 and len(reference) == 28
    for raw, row in cohort:
        _, _, _, _, truth, water, nodata, recorded, final, _ = causes.read_record(ROOT, tracked, raw, row)
        debris = boxes.truth_obstacles(raw.name)
        assert np.array_equal(inflate(debris | water | nodata, RADIUS), truth.rock)
        bounds = boxes.rectangles(debris, RESOLUTION)
        real = slope_deg(truth.elev) > causes.ROBOT.max_slope_deg
        halo = inflate(real, RADIUS)
        geometry = SegmentClearance(*cell_boxes(real, RESOLUTION, -RESOLUTION/2))
        start, goal = (tuple(int(row[f'{key}_{axis}']) for axis in 'xy') for key in ('start', 'goal'))
        with np.load(ROOT/raw/'pointcloud_map.npz', allow_pickle=False) as data:
            saved_cost = data['cost']
        sensor_slope = slope_deg(final['elev'])
        control = PointCloudMapFine(recorded.prior, recorded.raw_obstacle)
        for terrain, mode in product(TERRAINS, TRACKING_MARGINS):
            mapper = PointCloudMapFine(recorded.prior, recorded.raw_obstacle, terrain_source=terrain,
                                       obstacle_clearance='distance', steep_clearance='distance',
                                       tracking_margin=mode)
            if terrain == 'sensor':
                mapper.tm.slope = sensor_slope
                mapper.tm.cost = saved_cost
                slopes.install_steep(mapper, sensor_slope > mapper.robot.max_slope_deg)
            mapper.seen = final['seen']
            boxes.install_mask(mapper, final['fine_obstacle'])
            if terrain == 'sensor':
                assert np.array_equal(mapper.lethal, final['lethal'])
            info, path = plan(mapper, control.tm, start, goal)
            values = {}
            if path:
                xy = np.asarray(path)*RESOLUTION
                values = slopes.risk_metrics(path, real, halo, geometry, bounds)
                values.update(box_below_05_m=boxes.distance_band_length(xy, *bounds, RADIUS),
                              box_below_0774_m=boxes.distance_band_length(xy, *bounds, FIXED_HARD_M),
                              steep_below_0774_m=boxes.distance_band_length(
                                  xy, geometry.lower, geometry.upper, FIXED_HARD_M))
            data = dict(archive=str(raw), patch=raw.name, condition=row['condition'], rep=row['rep'],
                        visit=row['visit_number'], start=str(start), goal=str(goal), terrain=terrain,
                        obstacle_clearance='distance', steep_clearance='distance', tracking_margin=mode,
                        **info, **values)
            if mode == 'none':
                compare_none(data, reference[(str(raw), terrain)])
            yield data


def narrow_cases():
    for gap, angle, mode in product((1.2, 1.8, 2.5), (9., 11.), TRACKING_MARGINS):
        real, rock, _, _ = slopes.synthetic_case(gap, forced=True)
        mapper = PointCloudMapFine(np.zeros(real.shape), rock, steep_clearance='distance', tracking_margin=mode)
        control = PointCloudMapFine(mapper.prior, rock)
        mapper.seen[:] = True
        mapper.tm.slope[:] = angle
        slopes.install_steep(mapper, real)
        boxes.install_mask(mapper, mapper.fine_obstacle)
        info, _ = plan(mapper, control.tm, (4, 15), (30, 15))
        yield dict(gap_m=gap, raster_gap_m=RESOLUTION*(~real[15, 8:23]).sum(),
                   slope_deg=angle, tracking_margin=mode, **info)


def summarize(rows):
    for terrain, mode in product(TERRAINS, TRACKING_MARGINS):
        group = [row for row in rows if (row['terrain'], row['tracking_margin']) == (terrain, mode)]
        paths = [row for row in group if row['route']]
        common = ('raw_start_blocked', 'raw_goal_blocked', 'start_blocked', 'goal_blocked',
                  'relaxed_start', 'relaxed_goal', 'route')
        values = {key: sum(row[key] for row in group) for key in common}
        lengths = ('path_m', 'box_below_05_m', 'box_below_0774_m', 'steep_below_05_m', 'steep_below_0774_m')
        values.update({key: sum(row[key] for row in paths) if paths else None for key in lengths})
        values['path_m_mean'] = values['path_m']/len(paths) if paths else None
        for layer in ('box', 'steep'):
            distances = [row[f'min_{layer}_m'] for row in paths]
            values[f'min_{layer}_m'] = min(distances, default=None)
            values[f'median_{layer}_m'] = float(np.median(distances)) if distances else None
        yield dict(terrain=terrain, tracking_margin=mode, maps=len(group), **values)


def main(output):
    rows = list(archived_cases(causes.committed_inputs(ROOT)))
    assert len(rows) == 84
    print('All 28 none rows match every task065 field (atol=1e-10, rtol=0).')
    output.mkdir(parents=True, exist_ok=True)
    for name, results in [('runs', rows), ('summary', list(summarize(rows))), ('narrow', list(narrow_cases()))]:
        path = output/(name+'.csv')
        boxes.write_table(path, results)
        if name != 'runs':
            print(path.name)
            print(path.read_text(), end='')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    main(parser.parse_args().out)
