"""Recompute steep inflation and reachability on the committed 053/046/047 grids."""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from results.false_steep_causes import replay as causes
from results.terrain_from_prior import replay as archive
from tapp.endpoint_policy import classify_failure, load_snapshot
from tapp.pointcloud_map_fine import PointCloudMapFine, RATIO, steep_inflation_sources
from tapp.traversability import inflate, slope_deg

FOLDER = Path(__file__).resolve().parent
ROOT = archive.ROOT
RADIUS = causes.ROBOT.footprint_radius
RESULTS = ROOT/'results'
KEYS = ('experiment', 'patch', 'condition', 'rep')


def grids(steep, obstacle, rock):
    base = steep | obstacle | rock
    keep = base | inflate(steep, RADIUS)
    new = base | inflate(steep_inflation_sources(steep, obstacle), RADIUS)
    return keep, new


def map_scores(keep, new, seen, truth, steep, obstacle):
    real = slope_deg(truth.elev) > causes.ROBOT.max_slope_deg
    truth_halo = inflate(real, RADIUS)
    row = dict(observed=int(seen.sum()), suppressed_steep_sources=int((seen & steep & obstacle).sum()))
    checks = {
        'miss_steep': real,
        'miss_halo_only': truth_halo & ~real,
        'miss_steep_or_halo': truth_halo,
        'miss_steep_map': real,
        'miss_steep_or_halo_map': truth_halo,
    }
    for suffix, area in checks.items():
        scope = area if suffix.endswith('_map') else area & seen
        row[f'keep_{suffix}'] = int((scope & ~keep).sum())
        row[f'no_inflate_{suffix}'] = int((scope & ~new).sum())
        row[f'delta_{suffix}'] = row[f'no_inflate_{suffix}']-row[f'keep_{suffix}']
    old_steep, new_steep = inflate(steep, RADIUS), steep | inflate(steep_inflation_sources(steep, obstacle), RADIUS)
    false_023 = seen & ~truth.lethal
    same_clearance = false_023 & ~truth_halo
    for suffix, valid in [('023', false_023), ('same_clearance', same_clearance)]:
        for measure, blocked_old, blocked_new in [('fp_steep', keep & old_steep, new & new_steep),
                                                   ('fp_blocked', keep, new)]:
            key = f'{measure}_{suffix}'
            row[f'keep_{key}'] = int((blocked_old & valid).sum())
            row[f'no_inflate_{key}'] = int((blocked_new & valid).sum())
            row[f'delta_{key}'] = row[f'no_inflate_{key}']-row[f'keep_{key}']
    return row, same_clearance & old_steep & ~new_steep, same_clearance & keep & ~new


def typed_scores(features, seen, water, nodata, obstacle, lost_steep, freed):
    classes, kinds = causes.classify(features)
    false = classes['false_steep'] & seen & ~(water | nodata)
    false_suppressed = false & obstacle
    kinds = dict(kinds, any_053_type=np.logical_or.reduce(list(kinds.values())))
    kinds['no_053_type'] = ~kinds['any_053_type']
    kinds['any_false_source'] = np.ones_like(false)
    rows = {}
    for name, area in kinds.items():
        affected = inflate(false_suppressed & area, RADIUS)
        rows[name] = dict(raw_false_steep=int((false & area).sum()),
                          suppressed_false_sources=int((false_suppressed & area).sum()),
                          lost_fp_steep_in_source_halo=int((lost_steep & affected).sum()),
                          freed_fp_in_source_halo=int((freed & affected).sum()))
    outside = ~inflate(false_suppressed, RADIUS)
    rows['outside_053_false_sources_only'] = dict(
        lost_fp_steep_in_source_halo=int((lost_steep & outside).sum()),
        freed_fp_in_source_halo=int((freed & outside).sum()))
    return rows


def read_failure(tracked, raw, row):
    goal = tuple(int(row[f'goal_{axis}']) for axis in 'xy')
    for file in sorted(tracked, reverse=True):
        if file.parent != raw/'diag':
            continue
        snapshot = load_snapshot(ROOT/file)
        if (int(snapshot['version']) == int(row['failure_version']) and tuple(snapshot['goal']) == goal
                and classify_failure(snapshot) == 'goal_cell'):
            if tuple(snapshot['start']) != tuple(int(row[f'start_{axis}']) for axis in 'xy'):
                raise ValueError(f'047 start disagrees with {file}')
            return file, snapshot
    raise ValueError(f'No committed failure matching 047 version and goal: {raw}')


def goal_result(row, stage, path, mapper, sample, obstacle, snapshot):
    start, goal = (tuple(snapshot[field]) for field in ('start', 'goal'))
    steep = slope_deg(sample['elev']) > mapper.robot.max_slope_deg
    keep, new = grids(steep, obstacle, mapper._prior_rock)
    actual_failure = stage == 'failure_snapshot'
    known = snapshot['known'] if actual_failure else sample['seen']
    assert np.array_equal(keep & known if actual_failure else keep, sample['lethal'])
    if actual_failure:
        assert np.array_equal(steep, snapshot['steep'])
    cost = sample['cost'] if not actual_failure else mapper.tm.cost
    multiplier = snapshot['cost'] if actual_failure else None
    header = {key: row[key] for key in (*KEYS, 'visit_number', 'goal_x', 'goal_y')}
    result = dict(header, stage=stage, record=str(path), version=int(sample['version']), reason='',
                  start_x=int(start[0]), start_y=int(start[1]),
                  obstacle_halo_at_goal=bool(obstacle[goal]), steep_at_goal=bool(steep[goal]))
    for mode, blocked in [('keep', keep), ('no_inflate', new)]:
        route = archive.route(mapper, known, cost, blocked, start, goal, saved_multiplier=multiplier)
        result.update({f'{mode}_{key}': value for key, value in route.items()})
        seeds = steep if mode == 'keep' else steep_inflation_sources(steep, obstacle)
        result[f'{mode}_steep_halo_at_goal'] = bool(inflate(seeds, RADIUS)[goal])
    baseline = 'final' if row['map_source'] == 'final' else 'failure_snapshot'
    if stage == baseline:
        for key in ('goal_open', 'start_blocked', 'route'):
            assert str(result[f'keep_{key}']) == row[f'sensor_{key}']
    result['opened_goal'] = result['no_inflate_goal_open'] and not result['keep_goal_open']
    result['recovered_route'] = result['no_inflate_route'] and not result['keep_route']
    return result


def verify_cohort(rows):
    prior = archive.read_csv(RESULTS/'terrain_from_prior/runs.csv')
    failures = archive.read_csv(RESULTS/'waypoint_feasibility/goal_cell.csv')
    identity = (*KEYS, 'visit_number', 'goal_x', 'goal_y')
    if len(prior) != 35 or {tuple(r[k] for k in identity) for r in prior} != {
            tuple(r[k] for k in identity) for r in failures}:
        raise ValueError('046 and 047 do not identify the same 35 failures')
    goals = archive.read_csv(RESULTS/'terrain_from_prior/goals.csv')
    for goal in goals:
        fields = ('patch', 'visit_number', 'goal_x', 'goal_y')
        counts = Counter(r['map_source'] for r in prior if all(r[k] == goal[k] for k in fields))
        assert all(counts[stage] == int(goal[stage+'_n']) for stage in ('final', 'failure_snapshot', 'missing'))
    assert len(rows) == sum(row['map_source'] == 'final' for row in prior) == 14
    return prior


def cases(tracked, primary, prior):
    metrics, types, goals = [], {}, []
    for row in prior:
        source = row['map_source']
        if source == 'missing':
            goals.append(dict({k: row[k] for k in (*KEYS, 'visit_number', 'goal_x', 'goal_y')},
                              stage='missing', reason=row['reason']))
            continue
        path = Path(row['archive_map'])
        raw = path.parent if source == 'final' else path.parent.parent
        causes.require(ROOT, tracked, path)
        file, snapshot = read_failure(tracked, raw, row)
        if source == 'final':
            _, _, _, _, truth, water, nodata, mapper, final, terrain = causes.read_record(
                ROOT, tracked, raw, primary[raw])
            obstacle = final['fine_inflated'][RATIO//2::RATIO, RATIO//2::RATIO]
            steep = slope_deg(final['elev']) > mapper.robot.max_slope_deg
            keep, new = grids(steep, obstacle, mapper._prior_rock)
            assert np.array_equal(keep, final['lethal'])
            scores, lost_steep, freed = map_scores(keep, new, final['seen'], truth, steep, obstacle)
            metrics.append(dict({k: row[k] for k in KEYS}, record=str(path), **scores))
            features = causes.map_features(terrain, causes.first_counts(mapper), final['elev'], final['seen'],
                                           final['fine_obstacle'], final['fine_inflated'], nodata)
            for name, tally in typed_scores(features, final['seen'], water, nodata, obstacle, lost_steep, freed).items():
                types.setdefault(name, Counter()).update(tally)
            planning_prior = PointCloudMapFine(mapper.prior, mapper.raw_obstacle, terrain_source='prior')
            with np.load(ROOT/path, allow_pickle=False) as arrays:
                final['cost'] = arrays['cost']
            goals.append(goal_result(row, 'final', path, planning_prior, final, obstacle, snapshot))
            # The first-scan mapper has accumulated evidence; the failure grid needs exactly its own detections.
            prior_elev = mapper.prior
        else:
            causes.require(ROOT, tracked, Path(row['reference']), raw.parents[1]/'manifest.json')
            reference, prior_map, _ = archive.load_reference(ROOT/raw.parents[1], row['patch'])
            assert reference == ROOT/row['reference']
            prior_elev = prior_map.elev
        mapper = PointCloudMapFine(prior_elev, snapshot['prior_raw'])
        mapper._add_obstacles(np.flatnonzero(snapshot['fine_obstacle']).tolist())
        goals.append(goal_result(row, 'failure_snapshot', file, mapper, snapshot, mapper._inflated_coarse, snapshot))
    return metrics, [dict(type=name, **tally) for name, tally in types.items()], goals


def goal_summary(goals):
    rows = []
    for stage in ('final', 'failure_snapshot'):
        subset = [row for row in goals if row['stage'] == stage]
        for patch in ('all', *sorted({row['patch'] for row in subset})):
            group = [row for row in subset if patch == 'all' or row['patch'] == patch]
            fields = ('keep_goal_open', 'no_inflate_goal_open', 'keep_route', 'no_inflate_route', 'recovered_route')
            rows.append(dict(stage=stage, patch=patch, records=len(group),
                             **{key: sum(row[key] for row in group) for key in fields}))
    return rows


def main(output):
    tracked = causes.committed_inputs(ROOT)
    primary = {raw: meta for raw, meta, _ in causes.discover(ROOT, tracked) if meta}
    prior = verify_cohort(primary)
    metrics, types, goals = cases(tracked, primary, prior)
    fields = list(metrics[0])[5:]
    totals = [dict(patch=patch, maps=len(group), **{k: sum(row[k] for row in group) for k in fields})
              for patch in ('all', *sorted({row['patch'] for row in metrics}))
              for group in [[row for row in metrics if patch == 'all' or row['patch'] == patch]]]
    output.mkdir(parents=True, exist_ok=True)
    tables = dict(map_errors=totals, map_runs=metrics, types=types, goals=goal_summary(goals), goal_runs=goals)
    for name, rows in tables.items():
        path = output/(name+'.csv')
        columns = list(dict.fromkeys(k for row in rows for k in row))
        causes.write_csv(path, [{k: row.get(k) for k in columns} for row in rows])
        if name not in ('map_runs', 'goal_runs'):
            print(name)
            print(path.read_text(), end='')
    print('046/047 runs without a committed grid:', sum(row['stage'] == 'missing' for row in goals))
    print('0167 visit 5', ', '.join(f"{row['stage']}/{row['condition']}_r{row['rep']}: "
          f"goal {row['keep_goal_open']}->{row['no_inflate_goal_open']}, "
          f"route {row['keep_route']}->{row['no_inflate_route']}"
          for row in goals if row['patch'] == '08OB88_-0167' and row['visit_number'] == '5' and row['stage'] != 'missing'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=FOLDER)
    main(parser.parse_args().out)
