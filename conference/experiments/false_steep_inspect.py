"""Inspect the saved steepness layers of completed LiDAR runs without replanning."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from zipfile import BadZipFile

import numpy as np

from experiments.eval_runs import discover, label_record, map_metrics, read_csv, reference_data
from results.false_steep_causes import replay as archive
from tapp.config import RESOLUTION, Robot
from tapp.pointcloud_map_fine import FINE_RESOLUTION, GROUND_EXCLUSION_M, RATIO
from tapp.real_beach import load_patch
from tapp.traversability import inflate, slope_deg

ROBOT = Robot()
RADIUS = ROBOT.footprint_radius
ERRORS = (OSError, ValueError, KeyError, TypeError, IndexError, BadZipFile, EOFError)
ID = ('run', 'patch', 'condition', 'rep')
PLAN_FIELDS = (*ID, 'plan', 'sim_time', 'version', 'false_steep_only', 'false_steep_inclusive',
               'overlaps_obstacle', 'overlaps_prior')
H0_FIELDS = ('plan_count', 'plan_first_id', 'plan_middle_id', 'plan_last_id', 'plan_incomplete',
             'plan_first', 'plan_middle', 'plan_last', 'plan_max', 'legacy_final',
             'final_steep_only_proxy')
DISTANCE_KEYS = ('within_02', 'over_02_within_05', 'over_05', 'no_detections', 'unknown')
PAIR_KEYS = ('pairs', 'high_over', 'low_under', 'high_dominates', 'low_dominates', 'tie', 'neither')


def mask(data, key, shape, *, shape_key=None):
    if key in data:
        array = data[key]
    else:
        bits = data[key+'_bits']
        packed_shape = tuple(data[shape_key or key+'_shape'])
        if packed_shape != shape or bits.dtype != np.uint8 or bits.size != (int(np.prod(shape))+7)//8:
            raise ValueError(f'invalid {key} packed mask')
        array = np.unpackbits(bits, count=int(np.prod(shape))).reshape(shape).astype(bool)
    if array.shape != shape or array.dtype != bool:
        raise ValueError(f'invalid {key} mask')
    return array


def planning_false_counts(plan, truth_halo):
    shape = truth_halo.shape
    steep = mask(plan, 'steep', shape) | mask(plan, 'steep_halo', shape)
    false = mask(plan, 'lethal', shape) & steep & ~truth_halo
    obstacle = mask(plan, 'obstacle_halo', shape)
    prior = mask(plan, 'prior_inflated', shape)
    return dict(false_steep_only=int((false & ~(obstacle | prior)).sum()),
                false_steep_inclusive=int(false.sum()), overlaps_obstacle=int((false & obstacle).sum()),
                overlaps_prior=int((false & prior).sum()))


def inspect_plans(folder, truth_halo):
    files = sorted(folder.glob('plan_*.npz'))
    if not files:
        raise ValueError('no saved search maps; cannot measure planning steepness')
    rows = []
    for i, path in enumerate(files, 1):
        if path.name != f'plan_{i:06d}.npz':
            raise ValueError(f'missing preceding search map before {path.name}')
        # Mask evidence is self-contained. Avoid loading the unrelated cost delta.
        with np.load(path, allow_pickle=False) as plan:
            rows.append(dict(plan=i, sim_time=float(plan['sim_time']), version=int(plan['version']),
                             **planning_false_counts(plan, truth_halo)))
    first, middle, last = rows[0], rows[(len(rows)-1)//2], rows[-1]
    profile = {f'plan_{name}': r['false_steep_only'] for name, r in
               [('first', first), ('middle', middle), ('last', last)]}
    profile.update(plan_count=len(rows), plan_first_id=first['plan'], plan_middle_id=middle['plan'],
                   plan_last_id=last['plan'], plan_incomplete=(folder/'incomplete.json').is_file(),
                   plan_max=max(r['false_steep_only'] for r in rows))
    return profile, rows


def distance_bins(distance):
    """Classify centre-to-centre distances. An empty known detection map is distinct from missing data."""
    answer = np.full(distance.shape, 'unknown', dtype='U19')
    answer[distance <= GROUND_EXCLUSION_M+1e-12] = 'within_02'
    answer[(distance > GROUND_EXCLUSION_M+1e-12) & (distance <= RADIUS+1e-12)] = 'over_02_within_05'
    answer[np.isfinite(distance) & (distance > RADIUS+1e-12)] = 'over_05'
    answer[np.isposinf(distance)] = 'no_detections'
    return answer


def stencil(elevation, truth, seen, land, cells):
    """Endpoint evidence for each actual numpy.gradient axis; indices are (x,y)."""
    x, y = np.asarray(cells).T
    result = {}
    for axis, pair in enumerate(((x, y), (y, x))):
        centres, other = pair
        left = np.maximum(centres-1, 0)
        right = np.minimum(centres+1, elevation.shape[axis]-1)
        a, b = ((left, other), (right, other)) if axis == 0 else ((other, left), (other, right))
        a_high = elevation[a] >= elevation[b]
        high = tuple(np.where(a_high, i, j) for i, j in zip(a, b))
        low = tuple(np.where(a_high, j, i) for i, j in zip(a, b))
        result['xy'[axis]] = dict(
            high=high, low=low, gradient=(elevation[b]-elevation[a])/((right-left)*RESOLUTION),
            high_error_m=elevation[high]-truth[high], low_error_m=elevation[low]-truth[low],
            valid=seen[high] & seen[low] & land[high] & land[low])
    return result


def quantiles(values):
    return tuple(float(v) for v in np.quantile(values, [0., .5, 1.])) if len(values) else (None,)*3


def pair_summary(high, low, valid):
    high, low = high[valid], low[valid]
    up, down = np.maximum(high, 0.), np.maximum(-low, 0.)
    same = np.isclose(up, down, rtol=0., atol=1e-12)
    row = dict(pairs=len(up), high_over=int((up > 0).sum()), low_under=int((down > 0).sum()),
               high_dominates=int(((up > down) & ~same).sum()), low_dominates=int(((down > up) & ~same).sum()),
               tie=int((same & ((up > 0) | (down > 0))).sum()), neither=int((same & (up == 0) & (down == 0)).sum()))
    for name, values in [('high_error_m', high), ('low_error_m', low)]:
        row.update({f'{name}_{stat}': value for stat, value in zip(('min', 'median', 'max'), quantiles(values))})
    return row


def final_features(elevation, truth, seen, land, obstacle, inflated, point_counts):
    ge, gt = slope_deg(elevation), slope_deg(truth)
    true_nonsteep = seen & land & (gt <= ROBOT.max_slope_deg)
    distance = archive.fine_distance(obstacle) if obstacle is not None else np.full(seen.shape, np.nan)
    distances = distance_bins(distance)
    # This separate measure repeats 053's inflated-mask distance and domain.
    near_053 = archive.fine_distance(inflated) <= RADIUS if inflated is not None else None
    rows = []
    for name, select in [('false_steep', true_nonsteep & (ge > ROBOT.max_slope_deg)),
                         ('true_nonsteep', true_nonsteep & (ge <= ROBOT.max_slope_deg))]:
        distance_counts = {key: int((distances[select] == key).sum()) for key in DISTANCE_KEYS}
        distance_n = int(select.sum())-distance_counts['unknown']
        outside = sum(distance_counts[k] for k in DISTANCE_KEYS[1:4])
        row = dict(classification=name, cells=int(select.sum()), **distance_counts,
                   distance_n=distance_n, outside_02=outside,
                   outside_02_share=outside/distance_n if distance_n else None,
                   near_053=int(near_053[select].sum()) if near_053 is not None else None,
                   point_count_source='point_counts' if point_counts is not None else 'none')
        for stat, value in zip(('min', 'median', 'max'), quantiles(point_counts[select] if point_counts is not None else [])):
            row[f'points_{stat}'] = value
        pairs = stencil(elevation, truth, seen, land, np.argwhere(select))
        strongest_x = np.abs(pairs['x']['gradient']) >= np.abs(pairs['y']['gradient'])
        dominant = {k: np.where(strongest_x, pairs['x'][k], pairs['y'][k])
                    for k in ('high_error_m', 'low_error_m', 'valid')}
        for axis, pair in (*pairs.items(), ('dominant', dominant)):
            layer = pair_summary(pair['high_error_m'], pair['low_error_m'], pair['valid'])
            row.update({f'{axis}_{key}': value for key, value in layer.items()})
        rows.append(row)
    return rows


def cell_details(elevation, truth, seen, land, cell, *, distance=None, points=None):
    if any(not 0 <= i < n for i, n in zip(cell, seen.shape)):
        raise ValueError(f'cell is outside grid: {cell}')
    pairs = stencil(elevation, truth, seen, land, [cell])
    d = distance[cell] if distance is not None else np.nan
    position = dict(x=cell[0], y=cell[1], slope_est_deg=float(slope_deg(elevation)[cell]),
                    slope_truth_deg=float(slope_deg(truth)[cell]), distance_m=float(d) if np.isfinite(d) else None,
                    distance_bin=distance_bins(np.asarray(d)).item(), points=points[cell] if points is not None else None)
    for axis, row in pairs.items():
        result = {}
        for side in ('high', 'low'):
            xy = tuple(int(i[0]) for i in row[side])
            result.update({f'{side}_x': xy[0], f'{side}_y': xy[1], f'{side}_seen': bool(seen[xy]),
                           f'{side}_estimate_m': float(elevation[xy]), f'{side}_truth_m': float(truth[xy]),
                           f'{side}_error_m': float(row[f'{side}_error_m'][0]),
                           f'{side}_points': points[xy] if points is not None else None})
        yield dict(position, axis=axis, observed_land_pair=bool(row['valid'][0]), **result)


def read_final(path, shape):
    with np.load(path, allow_pickle=False) as data:
        result = {key: data[key] for key in ('elev', 'seen', 'lethal', 'obstacle')}
        if (result['elev'].shape != shape or not np.isfinite(result['elev']).all()
                or any(result[k].shape != shape or result[k].dtype != bool for k in ('seen', 'lethal', 'obstacle'))):
            raise ValueError('invalid final map or a different grid from the truth')
        result['point_counts'] = data['point_counts'] if 'point_counts' in data else None
        counts = result['point_counts']
        if counts is not None and (counts.shape != shape or counts.dtype.kind not in 'iu' or (counts < 0).any()):
            raise ValueError('invalid point_counts grid')
        fine_shape = tuple(n*RATIO for n in shape)
        if 'fine_obstacle_bits' in data:
            if (float(data['fine_resolution_m']) != FINE_RESOLUTION
                    or not np.array_equal(data['fine_origin_xy'], [-RESOLUTION/2]*2)):
                raise ValueError('unexpected fine grid coordinates')
            for key in ('fine_obstacle', 'fine_inflated'):
                if key+'_bits' in data:
                    result[key] = mask(data, key, fine_shape, shape_key='fine_shape')
    return result


def land_mask(patch, prior_rock):
    """Match 053's land mask when the committed raw LAS DEM is on this grid."""
    if patch and archive.ROOT.joinpath('data/shizuoka_beach_las', patch+'.npz').is_file():
        dem = load_patch(patch, dataset='shizuoka_beach_las')
        land = np.isfinite(dem) & (dem >= 0)
        if land.shape == prior_rock.shape and np.array_equal(inflate(~land, RADIUS), prior_rock):
            return land, 'observed_land'
    return np.ones_like(prior_rock), 'observed_only'


class Inspection:
    def __init__(self):
        self.runs, self.plans, self.features, self.cells, self.skipped = [], [], [], [], []

    def skip(self, identity, analysis, reason):
        self.skipped.append(dict(identity, analysis=analysis, reason=str(reason)))
        print(f"{identity['run']} [{analysis}] skipped: {reason}")

    def final(self, identity, fmap, ref, land, domain):
        elevation, truth, seen = fmap['elev'], ref['truth_elev'], fmap['seen']
        obstacle, inflated, counts = (fmap.get(k) for k in ('fine_obstacle', 'fine_inflated', 'point_counts'))
        if obstacle is None:
            self.skip(identity, 'H1', 'fine obstacle map missing; distance bins unavailable')
        if counts is None:
            self.skip(identity, 'H3', 'none: final map does not store point_counts')
        self.features.extend(dict(identity, domain=domain, **row)
                             for row in final_features(elevation, truth, seen, land, obstacle, inflated, counts))
        legacy = map_metrics(fmap, 'pointcloud_map.npz', ref, {}, identity['patch'])
        return dict(legacy_final=int(legacy['map_fp_steep_cells']))

    def inspect(self, raw, reference_root, cells):
        identity, _, _, _ = label_record(raw, '069', {})
        identity = {key: identity[key] for key in ID}
        row = dict(identity)
        self.runs.append(row)
        try:
            _, ref = reference_data(raw, reference_root, identity['patch'])
            truth = ref['truth_elev']
            if not np.isfinite(truth).all():
                raise ValueError('non-finite reference heights')
        except ERRORS as error:
            for task in ('H0', 'H1–H3'):
                self.skip(identity, task, str(error))
            return
        try:
            profile, plans = inspect_plans(raw/'plan_maps', inflate(slope_deg(truth) > ROBOT.max_slope_deg, RADIUS))
            self.plans.extend(dict(identity, **plan) for plan in plans)
            row.update(profile)
            if profile['plan_incomplete']:
                self.skip(identity, 'H0 coverage', 'search recording incomplete; summary uses the saved prefix')
        except ERRORS as error:
            self.skip(identity, 'H0', str(error))
        try:
            fmap = read_final(raw/'pointcloud_map.npz', truth.shape)
            land, domain = land_mask(identity['patch'], ref['prior_rock'])
            row.update(self.final(identity, fmap, ref, land, domain))
        except ERRORS as error:
            self.skip(identity, 'H1–H3 and legacy H0', str(error))
            return
        distance = archive.fine_distance(fmap['fine_obstacle']) if cells and 'fine_obstacle' in fmap else None
        for cell in cells:
            try:
                self.cells.extend(dict(identity, stage='final', **r)
                                  for r in cell_details(fmap['elev'], truth, fmap['seen'], land, tuple(cell),
                                                        distance=distance, points=fmap['point_counts']))
            except ValueError as error:
                self.skip(identity, 'cell details', error)


def inspect_archive(result):
    root = archive.ROOT
    tracked = archive.committed_inputs(root)
    cohort = [(raw, meta) for raw, meta, _ in archive.discover(root, tracked) if meta]
    if len(cohort) != 14:
        raise ValueError('expected the fourteen 053/062 primary records')
    for raw, meta in cohort:
        identity = dict(run=str(raw), **{k: meta[k] for k in ID[1:]})
        row = dict(identity)
        result.runs.append(row)
        result.skip(identity, 'H0', 'no saved search sequence in the 053/062 cohort')
        try:
            _, _, _, _, truth, water, nodata, mapper, _, terrain = archive.read_record(root, tracked, raw, meta)
            fmap = read_final(root/raw/'pointcloud_map.npz', truth.elev.shape)
            land = ~(water | nodata)
            ref = dict(truth_elev=truth.elev, truth_lethal=truth.lethal)
            row.update(result.final(identity, fmap, ref, land, 'observed_land'))
            true_halo = inflate(slope_deg(truth.elev) > ROBOT.max_slope_deg, RADIUS)
            steep = slope_deg(fmap['elev']) > ROBOT.max_slope_deg
            proxy = dict(steep=steep, steep_halo=inflate(steep, RADIUS), lethal=fmap['seen'] & fmap['lethal'],
                         obstacle_halo=fmap['fine_inflated'][RATIO//2::RATIO, RATIO//2::RATIO],
                         prior_inflated=mapper._prior_rock)
            row['final_steep_only_proxy'] = planning_false_counts(proxy, true_halo)['false_steep_only']
            counts = archive.first_counts(mapper)
            features = archive.map_features(terrain, counts, fmap['elev'], fmap['seen'],
                                            fmap['fine_obstacle'], fmap['fine_inflated'], nodata)
            classes, types = archive.classify(features)
            for report_row in result.features[-2:]:
                selected = classes[report_row['classification']] & fmap['seen'] & land
                report_row['sparse_first_053'] = int((selected & types['sparse_first_lidar']).sum())
                counts_3x3 = counts['first_3x3_points'][selected]
                report_row['first_3x3_zero_053'] = int((counts_3x3 == 0).sum())
            if meta['patch'] == '08OB88_-0167':
                cell, goal = (137, 293), (137, 294)
                result.cells.extend(dict(identity, stage='final', **r)
                                    for r in cell_details(fmap['elev'], truth.elev, fmap['seen'], land, cell,
                                                          distance=features['box_m']))
                at_failure, elev, seen, _ = archive.failure_features(
                    root, tracked, raw, meta, mapper, terrain, counts, nodata, goal)
                result.cells.extend(dict(identity, stage='goal_failure', **r)
                                    for r in cell_details(elev, truth.elev, seen, land, cell,
                                                          distance=at_failure['box_m']))
        except ERRORS as error:
            result.skip(identity, 'archive analysis', str(error))


def strata(rows):
    groups = defaultdict(list)
    for row in rows:
        groups['all', 'all'].append(row)
        groups['all', row['condition']].append(row)
        groups[row['patch'], row['condition']].append(row)
    return groups.items()


def summaries(rows, fields, hypothesis, classification='all'):
    for (patch, condition), group in strata(rows):
        for field in fields:
            values = [r[field] for r in group if r.get(field) is not None]
            lo, median, hi = quantiles(values)
            total = sum(values) if values and all(isinstance(v, (int, np.integer)) for v in values) else None
            yield dict(hypothesis=hypothesis, patch=patch, condition=condition, classification=classification,
                       metric=field, n=len(values), total=total,
                       min=lo, median=median, max=hi)


def hypothesis_rows(result):
    yield from summaries(result.runs, ('plan_first', 'plan_middle', 'plan_last', 'plan_max', 'legacy_final',
                                      'final_steep_only_proxy'), 'H0')
    for kind in ('false_steep', 'true_nonsteep'):
        rows = [row for row in result.features if row['classification'] == kind]
        yield from summaries(rows, ('cells', 'distance_n', *DISTANCE_KEYS, 'outside_02', 'outside_02_share',
                                    'near_053'), 'H1', kind)
        yield from summaries(rows, tuple(f'dominant_{key}' for key in (*PAIR_KEYS, 'high_error_m_median',
                                                                    'low_error_m_median')), 'H2', kind)
        yield from summaries(rows, ('points_median', 'sparse_first_053', 'first_3x3_zero_053'), 'H3', kind)


def recorded_metrics(path):
    _, records = read_csv(path)
    rows = []
    for r in records:
        value = r['map_fp_steep_cells']
        rows.append(dict(patch=r['patch'], condition=r['condition'], legacy_final=int(float(value)) if value else None))
    return list(summaries(rows, ('legacy_final',), 'H0'))


def write_table(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--runs', type=Path, help='root of the run tree or one raw beach directory')
    inputs.add_argument('--archive-053', action='store_true', help='use the fourteen tracked 053/062 records')
    parser.add_argument('--reference-root', type=Path, help='fallback truth files under <patch>/evaluation_reference.npz')
    parser.add_argument('--cell', nargs=2, type=int, action='append', default=[], metavar=('X', 'Y'))
    parser.add_argument('--recorded-metrics', type=Path, help='optional common_eval runs.csv for legacy H0 medians')
    parser.add_argument('--out', required=True, type=Path, help='new directory for CSV outputs')
    args = parser.parse_args(argv)
    if args.runs is not None and not args.runs.is_dir():
        parser.error('runs directory does not exist')
    args.out.mkdir(parents=True, exist_ok=False)
    result = Inspection()
    if args.archive_053:
        inspect_archive(result)
    else:
        root = args.runs.resolve()
        records = [root] if (root/'plan_maps').is_dir() else list(discover(root))
        if not records:
            result.skip(dict(run=str(root), patch=None, condition=None, rep=None), 'H0–H3', 'no run records found')
        for raw in records:
            try:
                result.inspect(raw, args.reference_root, args.cell)
            except ERRORS as error:
                result.skip(dict(run=str(raw), patch=None, condition=None, rep=None), 'run metadata', error)
    summary = list(hypothesis_rows(result))
    tables = [
        ('runs', result.runs, (*ID, *H0_FIELDS)), ('plans', result.plans, PLAN_FIELDS),
        ('features', result.features, None), ('cells', result.cells, None),
        ('hypotheses', summary, None), ('skipped', result.skipped, (*ID, 'analysis', 'reason')),
    ]
    if args.recorded_metrics is not None:
        tables.append(('legacy_metrics', recorded_metrics(args.recorded_metrics), None))
    for name, rows, fields in tables:
        write_table(args.out/(name+'.csv'), rows, fields)
        print(f'{name}: {len(rows)} rows')
    for r in summary:
        if r['patch'] == r['condition'] == 'all':
            print(f"{r['hypothesis']} {r['classification']} {r['metric']} n={r['n']} "
                  f"total={r['total']} min/median/max={r['min']}/{r['median']}/{r['max']}")


if __name__ == '__main__':
    main()
