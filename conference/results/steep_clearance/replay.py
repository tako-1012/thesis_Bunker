"""Replan the 060 cohort and synthetic steep corridors with the production planner."""

import argparse
from itertools import product
from pathlib import Path

import numpy as np

from experiments.eval_runs import contacts
from results.distance_clearance import replay as boxes
from results.false_steep_causes import replay as causes
from results.terrain_from_prior import replay as archive
from tapp.config import RESOLUTION
from tapp.distance_clearance import SegmentClearance
from tapp.obstacle_clearance import cell_boxes, path_clearance
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.traversability import inflate, slope_deg

ROOT = archive.ROOT
MODES = ('centre', 'distance')
RADIUS = causes.ROBOT.footprint_radius


def install_steep(mapper, steep):
    """Supply the archived/synthetic terrain classification in place of a scan stream."""
    mapper.tm.steep = steep
    mapper._dilated_steep = inflate(steep, RADIUS)
    if hasattr(mapper, 'steep_distance_field'):
        mapper.steep_distance_field.refresh(steep)


def risk_metrics(path, real, halo, geometry, obstacles=None):
    xy = np.asarray(path)*RESOLUTION
    lower, upper = geometry.lower, geometry.upper
    edges = zip(path, path[1:]) if len(path) > 1 else [(path[0], path[0])]
    data = dict(min_steep_m=min(geometry.segment(a, b) for a, b in edges),
                start_steep_m=geometry.segment(path[0], path[0]),
                goal_steep_m=geometry.segment(path[-1], path[-1]),
                steep_m=contacts(xy, real)[0], steep_or_grid_halo_m=contacts(xy, halo)[0],
                steep_below_05_m=boxes.distance_band_length(xy, lower, upper, .5),
                steep_below_10_m=boxes.distance_band_length(xy, lower, upper, 1.))
    if obstacles is not None:
        data['min_box_m'] = path_clearance(xy, *obstacles)
    return data


def replay_archives(tracked):
    cohort = [(raw, row) for raw, row, _ in causes.discover(ROOT, tracked) if row]
    if len(cohort) != 14:
        raise ValueError('expected the 14 primary 053/060 archives')
    controls = {(row['archive'], row['terrain'], row['mode']): row
                for row in archive.read_csv(ROOT/'results/distance_clearance/runs.csv')}
    for raw, row in cohort:
        _, _, _, _, truth, water, nodata, recorded, final, _ = causes.read_record(ROOT, tracked, raw, row)
        debris = boxes.truth_obstacles(raw.name)
        if not np.array_equal(inflate(debris | water | nodata, RADIUS), truth.rock):
            raise ValueError(f'{raw}: reconstructed truth rocks differ from signed reference')
        bounds = boxes.rectangles(debris, RESOLUTION)
        real = slope_deg(truth.elev) > causes.ROBOT.max_slope_deg
        halo = inflate(real, RADIUS)
        geometry = SegmentClearance(*cell_boxes(real, RESOLUTION, -RESOLUTION/2))
        control = PointCloudMapFine(recorded.prior, recorded.raw_obstacle)
        start, goal = (tuple(int(row[f'{key}_{axis}']) for axis in 'xy') for key in ('start', 'goal'))
        with np.load(ROOT/raw/'pointcloud_map.npz', allow_pickle=False) as data:
            saved_cost = data['cost']
        sensor_steep = slope_deg(final['elev']) > causes.ROBOT.max_slope_deg
        for terrain, obstacle, steep in product(('sensor', 'prior'), MODES, MODES):
            mapper = PointCloudMapFine(recorded.prior, recorded.raw_obstacle, terrain_source=terrain,
                                       obstacle_clearance=obstacle, steep_clearance=steep)
            if terrain == 'sensor':
                mapper.tm.cost = saved_cost
                install_steep(mapper, sensor_steep)
            mapper.seen = final['seen']
            boxes.install_mask(mapper, final['fine_obstacle'])
            if terrain == 'sensor':
                assert np.array_equal(mapper.lethal, final['lethal'])
            info, path = boxes.plan(mapper, control.tm, start, goal)
            safety = risk_metrics(path, real, halo, geometry, bounds) if path else {}
            if steep == 'centre':
                old = controls[(str(raw), terrain, obstacle)]
                assert all(str(info[k]) == old[k] for k in ('route', 'goal_blocked'))
                if path:
                    assert all(np.isclose(values[k], float(old[k]), rtol=0., atol=1e-10)
                               for k, values in [('path_m', info), ('terrain_cost_m', info), ('min_box_m', safety)])
            yield dict(archive=str(raw), patch=raw.name, condition=row['condition'], rep=row['rep'],
                       visit=row['visit_number'], start=str(start), goal=str(goal), terrain=terrain,
                       obstacle_clearance=obstacle, steep_clearance=steep, **info, **safety)


def synthetic_case(gap_m=None, *, forced=False):
    """Analytic steep strips, classified by sampling their 0.5 m cell centres."""
    shape = (36, 36)
    axis = np.arange(shape[0])*RESOLUTION
    if gap_m is None:
        lower = np.array([[5., 4.75]])
        upper = np.array([[12., 6.75]])
    else:
        lower = np.array([[6., 4.], [6., 7.5+gap_m/2]])
        upper = np.array([[9., 7.5-gap_m/2], [9., 11.]])
    steep = np.zeros(shape, bool)
    for (x0, y0), (x1, y1) in zip(lower, upper):
        steep |= ((x0 <= axis) & (axis <= x1))[:, None] & ((y0 <= axis) & (axis <= y1))[None, :]
    rock = np.zeros(shape, bool)
    if forced:
        rock[:, :9] = True
        rock[:, 22:] = True
    return steep, rock, lower, upper


def replay_synthetic(gap_m=None, *, forced=False):
    real, rock, lower, upper = synthetic_case(gap_m, forced=forced)
    grid_geometry = SegmentClearance(*cell_boxes(real, RESOLUTION, -RESOLUTION/2))
    real_geometry = SegmentClearance(lower, upper)
    prior = PointCloudMapFine(np.zeros(real.shape), rock).tm
    start, goal = (4, 15), (30, 15)
    for mode in MODES:
        mapper = PointCloudMapFine(np.zeros(real.shape), rock, steep_clearance=mode)
        mapper.seen[:] = True
        install_steep(mapper, real)
        boxes.install_mask(mapper, mapper.fine_obstacle)
        info, path = boxes.plan(mapper, prior, start, goal)
        risk = risk_metrics(path, real, mapper._dilated_steep, real_geometry) if path else {}
        if path:
            risk['min_raster_steep_m'] = min(grid_geometry.segment(a, b) for a, b in zip(path, path[1:]))
            info['detour_m'] = info['path_m']-(goal[0]-start[0])*RESOLUTION
        yield dict(case='beside' if gap_m is None else 'gap', gap_m=gap_m, forced=forced,
                   raster_gap_m=None if gap_m is None else RESOLUTION*(~real[15, 8:23]).sum(),
                   steep_clearance=mode, **info, **risk)


def summarize(rows):
    for terrain, obstacle, steep in product(('sensor', 'prior'), MODES, MODES):
        selected = [row for row in rows if (row['terrain'], row['obstacle_clearance'], row['steep_clearance'])
                    == (terrain, obstacle, steep)]
        paths = [row for row in selected if row['route']]
        summary = dict(terrain=terrain, obstacle_clearance=obstacle, steep_clearance=steep, maps=len(selected))
        for noun in ('steep', 'box'):
            values = [row[f'min_{noun}_m'] for row in paths]
            summary[f'min_{noun}_m'] = min(values, default=None)
            summary[f'median_{noun}_m'] = float(np.median(values)) if values else None
        fields = ('steep_m', 'steep_or_grid_halo_m', 'steep_below_05_m', 'steep_below_10_m')
        summary.update({key: sum(row[key] for row in paths) for key in fields})
        summary.update(blocked_goals=sum(row['goal_blocked'] for row in selected), routes=len(paths),
                       **{key+'_mean': float(np.mean([row[key] for row in paths])) if paths else None
                          for key in ('path_m', 'terrain_cost_m')})
        yield summary


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    rows = list(replay_archives(causes.committed_inputs(ROOT)))
    narrow = [row for gap in (1.2, 1.8, 2.5) for forced in (False, True)
              for row in replay_synthetic(gap, forced=forced)]
    visit = [row for row in rows if row['patch'] == '08OB88_-0167' and row['visit'] == '5']
    assert len(rows) == 112 and len(visit) == 32
    tables = dict(runs=rows, summary=list(summarize(rows)), visit_0167=visit,
                  synthetic=[*replay_synthetic(), *narrow])
    for name, records in tables.items():
        path = output/(name+'.csv')
        boxes.write_table(path, records)
        if name != 'runs':
            print(path.name)
            print(path.read_text(), end='')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
