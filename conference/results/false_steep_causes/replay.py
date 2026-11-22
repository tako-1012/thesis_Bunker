"""Compare raw slope classifications and their features in committed LiDAR runs."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
from scipy.ndimage import convolve, distance_transform_edt

from results.terrain_from_prior import replay as archive
from ros2_jazzy.gz_checks.online_batch_runtime import map_signature
from tapp.config import RESOLUTION, Robot
from tapp.endpoint_policy import load_snapshot
from tapp.pointcloud_map import transform_points
from tapp.pointcloud_map_fine import FINE_RESOLUTION, RATIO, PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.real_beach import load_patch
from tapp.sensor_geometry import transform_sensor_points
from tapp.traversability import inflate, slope_deg

ROOT = archive.ROOT
ROBOT = Robot()
BOX_NEAR_M = .5
SPARSE_MAX_POINTS = 8
NEAR_LIMIT_DEG = 20.
RELIEF_STD_M = .15
SHORE_NEAR_M = 1.
GOAL_RADIUS_M = 2.
LONG_RANGE_M = 15.
SIDE_OR_REAR_DEG = 90.
TYPES = ('box_near', 'sparse_first_lidar', 'near_slope_limit', 'high_truth_relief', 'sea_or_nodata_near')
CLASSES = ('false_steep', 'true_steep', 'true_nonsteep', 'missed_steep')
WINDOW = np.ones((3, 3), dtype=np.int32)
INPUT_FILES = ('pointcloud_map.npz', 'first_cloud.npz')
PRIMARY = '047_048'
TRACKED_SOURCES = {'035': 'eval_035', '037': 'real_sensors_compare', '039': 'rtf_compare'}


class MissingRecord(ValueError):
    """An input is absent or outside the archived comparison conditions."""


def window_sum(values):
    return convolve(values, WINDOW, mode='constant', cval=0)


def height_std(elevation, nodata):
    """Population standard deviation in the clipped, known 3x3 window."""
    values = np.where(nodata, 0., elevation)
    count = window_sum((~nodata).astype(np.int32))
    safe_count = np.maximum(count, 1)
    mean = window_sum(values) / safe_count
    variance = window_sum(values**2) / safe_count - mean**2
    return np.where(count > 0, np.sqrt(np.maximum(variance, 0.)), np.nan)


def distance_to(mask, spacing=RESOLUTION):
    if not mask.any():
        return np.full(mask.shape, np.inf)
    return distance_transform_edt(~mask, sampling=spacing)


def fine_distance(mask):
    return distance_to(mask, FINE_RESOLUTION)[RATIO//2::RATIO, RATIO//2::RATIO].copy()


def stencil_missing(seen):
    """Whether any cell used by np.gradient is unobserved, including edges."""
    x = np.arange(seen.shape[0])
    y = np.arange(seen.shape[1])
    return ~(seen[np.maximum(x-1, 0), :] & seen[np.minimum(x+1, len(x)-1), :]
             & seen[:, np.maximum(y-1, 0)] & seen[:, np.minimum(y+1, len(y)-1)])


def terrain_features(truth, water, nodata, pose, sensor_origin):
    x, y = np.ogrid[:truth.shape[0], :truth.shape[1]]
    x, y = x*RESOLUTION, y*RESOLUTION
    dx, dy = x-pose[0], y-pose[1]
    distance = np.hypot(dx, dy)
    bearing = (np.degrees(np.arctan2(dy, dx)-pose[5])+180) % 360-180
    gx, gy = np.gradient(truth, RESOLUTION)
    rx, ry, rz = sensor_origin[0]-x, sensor_origin[1]-y, sensor_origin[2]-truth
    norm = np.sqrt((rx**2+ry**2+rz**2)*(1.+gx**2+gy**2))
    cosine = np.divide(np.abs(rz-gx*rx-gy*ry), norm, out=np.full_like(truth, np.nan), where=norm > 0)
    return dict(truth_slope_deg=slope_deg(truth), truth_height_std_m=height_std(truth, nodata),
                sea_m=distance_to(water), nodata_m=distance_to(nodata), first_robot_xy_m=distance,
                first_bearing_deg=np.where(distance > 0, bearing, np.nan),
                first_incidence_deg=np.degrees(np.arcsin(np.clip(cosine, 0, 1))))


def first_counts(mapper):
    counts = np.zeros(mapper.elev.shape, np.int32)
    ground = np.zeros_like(counts)
    for key, samples in mapper.samples.items():
        counts.flat[key] = len(samples)
        ground.flat[key] = (len(samples) if mapper.ground_estimate == 'all_returns' else
                            np.count_nonzero(samples[:, 1] < mapper.obstacle_height_m))
    nearby = window_sum(counts)
    return dict(first_cell_points=counts, first_other8_points=nearby-counts, first_3x3_points=nearby,
                first_cell_ground_points=ground, first_3x3_ground_points=window_sum(ground))


def map_features(terrain, counts, elevation, seen, obstacle, halo, nodata):
    return dict(terrain, **counts, estimated_slope_deg=slope_deg(elevation),
                estimated_height_std_m=height_std(elevation, nodata), box_m=fine_distance(obstacle),
                box_halo_m=fine_distance(halo), stencil_has_unseen=stencil_missing(seen))


def classify(features):
    true_slope = features['truth_slope_deg']
    real = true_slope > ROBOT.max_slope_deg
    estimated = features['estimated_slope_deg'] > ROBOT.max_slope_deg
    classes = dict(zip(CLASSES, (estimated & ~real, estimated & real, ~estimated & ~real, ~estimated & real)))
    points = features['first_3x3_points']
    types = dict(zip(TYPES, (features['box_halo_m'] <= BOX_NEAR_M, (points > 0) & (points <= SPARSE_MAX_POINTS),
                            (true_slope >= NEAR_LIMIT_DEG) & ~real, features['truth_height_std_m'] >= RELIEF_STD_M,
                            np.minimum(features['sea_m'], features['nodata_m']) <= SHORE_NEAR_M)))
    return classes, types


def json_file(path):
    return json.loads(path.read_text())


def committed_inputs(root):
    dem = Path('data/shizuoka_beach_las')
    files = subprocess.check_output(
        ['git', 'ls-tree', '-rz', '--name-only', 'HEAD', '--', 'results', str(dem)], cwd=root)
    names = (*INPUT_FILES, 'evaluation_reference.npz', 'manifest.json')
    paths = (Path(name.decode()) for name in files.split(b'\0') if name)
    return frozenset(path for path in paths if path.name in names or path.parent == dem
                     or path.match('*/diag/plan_fail_*.npz'))


def discover(root, tracked):
    prior_rows = archive.read_csv(root/'results/terrain_from_prior/runs.csv')
    primary = {Path(row['archive_map']).parent: row for row in prior_rows if row['map_source'] == 'final'}
    raw_dirs = {path.parent for path in tracked if path.name in INPUT_FILES} | primary.keys()
    for raw in sorted(raw_dirs):
        yield raw, primary.get(raw), ''
    for row in prior_rows:
        if row['map_source'] == 'final':
            continue
        source = TRACKED_SOURCES[row['experiment']]
        run = f"{row['patch']}/{row['condition']}_r{row['rep']}"
        evidence = ('failure snapshot only; no final map or first LiDAR cloud'
                    if row['map_source'] == 'failure_snapshot' else 'no committed final map or first LiDAR cloud')
        yield Path('results')/source/run, None, evidence


def require(root, tracked, *paths):
    missing = [str(path) for path in paths if path not in tracked or not (root/path).is_file()]
    if missing:
        raise MissingRecord('missing committed input: '+', '.join(missing))


def read_reference(root, path, signatures):
    with np.load(root/path, allow_pickle=False) as data:
        layers = [SimpleNamespace(**{key: data[f'{name}_{key}'] for key in ('elev', 'rock', 'lethal')})
                  for name in ('prior', 'truth')]
    for name, layer in zip(('prior', 'truth'), layers):
        if map_signature(dict(tmap=layer)) != signatures[name]:
            raise ValueError(f'{name} reference signature mismatch: {path}')
    return layers


def read_record(root, tracked, raw, primary):
    run = [raw/name for name in INPUT_FILES]
    require(root, tracked, *run)
    physical = raw.parents[1]
    manifest_path = physical/'manifest.json'
    require(root, tracked, manifest_path)
    manifest = json_file(root/manifest_path)
    if manifest.get('map_method') != 'fine':
        raise MissingRecord('coarse map has no fine obstacle and halo masks')
    if manifest.get('prior_variant', 'exact') != 'exact' or manifest.get('terrain_source', 'sensor') != 'sensor':
        raise MissingRecord('requires exact prior and sensor terrain')
    if manifest.get('obstacle_reference_mode', 'prior') != 'prior' or manifest.get('obstacle_clearance', 'centre') != 'centre':
        raise MissingRecord('requires prior-referenced obstacle detection and centre clearance')
    if manifest['dataset'] != 'shizuoka_beach_las' or manifest['side_m'] != 200:
        raise MissingRecord('requires the uncropped 200 m LAS DEM')
    patch = raw.name
    cases = [c for c in manifest['cases'] if c.get('selected') and c['patch'] == patch
             and c.get('run_folder') and physical/c['run_folder'] == raw]
    if len(cases) != 1:
        raise MissingRecord('no unique selected manifest case for this raw folder')
    case = cases[0]
    if not case.get('world_reference') or not case.get('input_audit', {}).get('signatures'):
        raise MissingRecord('no signed world reference in the manifest')
    reference = Path(case['world_reference'])
    if primary and Path(primary['reference']) != reference:
        raise ValueError('047 reference differs from the manifest')
    require(root, tracked, reference, Path('data/shizuoka_beach_las')/(patch+'.npz'),
            Path('data/shizuoka_beach_las/index.json'))
    prior, truth = read_reference(root, reference, case['input_audit']['signatures'])
    raw_dem = load_patch(patch, dataset=manifest['dataset'])
    nodata = ~np.isfinite(raw_dem)
    water = ~nodata & (raw_dem < 0)
    if not np.array_equal(inflate(water | nodata, ROBOT.footprint_radius), prior.rock):
        raise ValueError('sea/nodata mask does not reconstruct signed prior obstacles')
    ground = manifest.get('ground_estimate', 'all_returns')
    sensors = manifest.get('sensors', 'legacy')
    if sensors == 'legacy':
        spec = manifest['lidar_spec']
        mapper = PointCloudMapFine(prior.elev, water | nodata, ground_estimate=ground,
                                   sensor_height_m=manifest['sensor_height_m'], min_range_m=spec['min_range_m'],
                                   max_range_m=spec['max_range_m'], range_resolution_m=spec['range_resolution_m'])
    else:
        mapper = PointCloudMapMulti(prior.elev, water | nodata, sensors=sensors, ground_estimate=ground)
    with np.load(root/run[1], allow_pickle=False) as cloud:
        mapper.update(cloud['points'], cloud['pose'])
        pose = cloud['pose']
    zero = np.zeros((1, 3))
    sensor_origin = (transform_points(zero, pose, mapper.sensor_height_m) if sensors == 'legacy' else
                     transform_sensor_points(zero, pose, mapper.mounts['lidar']))[0]

    with np.load(root/run[0], allow_pickle=False) as data:
        final = {key: data[key] for key in ('seen', 'elev', 'lethal', 'version')}
        fine_shape = tuple(data['fine_shape'])
        if (fine_shape != mapper.fine_shape or data['fine_resolution_m'] != FINE_RESOLUTION or
                not np.array_equal(data['fine_origin_xy'], [-RESOLUTION/2]*2)):
            raise ValueError('final fine-grid coordinates differ')
        for key in ('fine_obstacle', 'fine_inflated'):
            final[key] = np.unpackbits(data[key+'_bits'], count=int(np.prod(fine_shape))).reshape(fine_shape).astype(bool)
    if (final['seen'].shape != truth.elev.shape or final['elev'].shape != truth.elev.shape or
            not np.isfinite(final['elev']).all()):
        raise ValueError('final map grid differs from finite truth grid')
    if (mapper.seen & ~final['seen']).any():
        raise ValueError('first LiDAR coverage is outside final coverage')
    steep = slope_deg(final['elev']) > ROBOT.max_slope_deg
    reconstructed = (prior.rock | final['fine_inflated'][RATIO//2::RATIO, RATIO//2::RATIO]
                     | inflate(steep, ROBOT.footprint_radius))
    if not np.array_equal(reconstructed, final['lethal']):
        raise ValueError('reconstructed final lethal map differs')
    if primary and (int(final['version']) != int(primary['map_version']) or
                    np.count_nonzero(final['seen']) != int(primary['seen_cells'])):
        raise ValueError('047 final map version or coverage differs')
    return (reference, ground, sensors, manifest['real_time_factor'], truth, water, nodata, mapper, final,
            terrain_features(truth.elev, water, nodata, pose, sensor_origin))


def summarize_stage(pool, key, features, seen, water, nodata):
    classes, types = classify(features)
    valid = seen & ~(water | nodata)
    counts = {name: int((mask & valid).sum()) for name, mask in classes.items()}
    for name, mask in classes.items():
        pool[key+(name,)].append(features, types, mask & valid)
    false = seen & classes['false_steep']
    return dict(seen=int(seen.sum()), seen_sea=int((seen & water).sum()), seen_nodata=int((seen & nodata).sum()),
                false_steep_all_seen=int(false.sum()), sea_raw_false_steep=int((false & water).sum()),
                nodata_filled_false_steep=int((false & nodata).sum()),
                **counts)


class Summary:
    def __init__(self):
        self.metrics = defaultdict(list)
        self.flags = Counter()
        self.patterns = np.zeros(1 << len(TYPES), dtype=np.int64)
        self.n = 0

    def append(self, features, types, mask):
        self.n += int(mask.sum())
        pattern = np.zeros(int(mask.sum()), np.uint8)
        for bit, name in enumerate(TYPES):
            matched = types[name][mask]
            pattern |= matched.astype(np.uint8) << bit
            self.flags[name] += int(matched.sum())
        self.patterns += np.bincount(pattern, minlength=len(self.patterns))
        points = features['first_3x3_points'][mask]
        self.flags['first_neighborhood_has_points'] += int((points > 0).sum())
        self.flags['no_first_cell_points'] += int((features['first_cell_points'][mask] == 0).sum())
        self.flags['long_first_range'] += int((features['first_robot_xy_m'][mask] >= LONG_RANGE_M).sum())
        self.flags['side_or_rear_first_bearing'] += int((np.abs(features['first_bearing_deg'][mask]) >= SIDE_OR_REAR_DEG).sum())
        self.flags['stencil_has_unseen'] += int(features['stencil_has_unseen'][mask].sum())
        for name, data in features.items():
            if name != 'stencil_has_unseen':
                self.metrics[name].append(data[mask].astype(np.float32))
        self.metrics['first_abs_bearing_deg'].append(np.abs(features['first_bearing_deg'][mask]).astype(np.float32))


def percent(n, denominator):
    return round(n*100/denominator, 4) if denominator else None


def summary_rows(pool):
    features, types, overlaps = [], [], []
    for (cohort, stage, label), summary in sorted(pool.items()):
        key = dict(cohort=cohort, stage=stage, classification=label)
        for name, parts in summary.metrics.items():
            values = np.concatenate(parts)
            finite = values[np.isfinite(values)]
            q10, median, q90 = (np.round(np.quantile(finite, [.1, .5, .9]), 6) if len(finite) else (None,)*3)
            features.append(dict(key, feature=name, n=summary.n, defined=len(finite), q10=q10, median=median, q90=q90))
        for name, n in summary.flags.items():
            types.append(dict(key, feature=name, count=n, n=summary.n, percent=percent(n, summary.n)))
        n = summary.flags['sparse_first_lidar']
        supported = summary.flags['first_neighborhood_has_points']
        types.append(dict(key, feature='sparse_given_first_support', count=n, n=supported, percent=percent(n, supported)))
        for pattern in np.flatnonzero(summary.patterns):
            names = '+'.join(name for bit, name in enumerate(TYPES) if pattern & (1 << bit)) or 'none'
            n = int(summary.patterns[pattern])
            overlaps.append(dict(key, pattern=names, count=n, n=summary.n, percent=percent(n, summary.n)))
    return dict(features=features, types=types, overlaps=overlaps)


def goal_rows(raw, primary, stage, goal, features, elevation, seen, lethal, truth, water, nodata):
    x, y = np.ogrid[:seen.shape[0], :seen.shape[1]]
    distance = np.hypot(x-goal[0], y-goal[1])*RESOLUTION
    classes, types = classify(features)
    identity = {k: primary[k] for k in ('patch', 'condition', 'rep')}
    for cell in zip(*np.where(distance <= GOAL_RADIUS_M)):
        sample = {k: round(float(v[cell]), 6) if np.isfinite(v[cell]) else None for k, v in features.items()}
        yield dict(identity, raw=str(raw), stage=stage, x=cell[0], y=cell[1], goal_distance_m=round(distance[cell], 6),
                   seen=bool(seen[cell]), sea=bool(water[cell]), nodata=bool(nodata[cell]),
                   classification=next(name for name, mask in classes.items() if mask[cell]),
                   steep_can_block_goal=bool(distance[cell] <= ROBOT.footprint_radius and
                                             features['estimated_slope_deg'][cell] > ROBOT.max_slope_deg),
                   truth_lethal=bool(truth.lethal[cell]), lethal=bool(lethal[cell]),
                   elevation_m=round(float(elevation[cell]), 6), truth_elevation_m=round(float(truth.elev[cell]), 6),
                   **sample, **{name: bool(mask[cell]) for name, mask in types.items()})


def failure_features(root, tracked, raw, primary, mapper, terrain, counts, nodata, goal):
    paths = sorted(path for path in tracked if path.parent == raw/'diag' and path.name.startswith('plan_fail_'))
    for path in reversed(paths):
        snapshot = load_snapshot(root/path)
        if int(snapshot['version']) == int(primary['failure_version']) and tuple(snapshot['goal']) == goal:
            break
    else:
        raise MissingRecord('matching committed goal failure snapshot is absent')
    if not snapshot['lethal'][goal]:
        raise ValueError('archived goal is not blocked at failure')
    # Stamp the archived detections with the same fine inflation used in 047.
    halo = PointCloudMapFine(mapper.prior, mapper.raw_obstacle)
    halo._add_obstacles(np.flatnonzero(snapshot['fine_obstacle']).tolist())
    features = map_features(terrain, counts, snapshot['elev'], snapshot['seen'], snapshot['fine_obstacle'],
                            halo.fine_inflated, nodata)
    if not np.array_equal(features['estimated_slope_deg'] > ROBOT.max_slope_deg, snapshot['steep']):
        raise ValueError('archived failure uninflated steep mask differs')
    return features, snapshot['elev'], snapshot['seen'], snapshot['lethal']


def cohort_name(raw, primary, sensors):
    if primary:
        return PRIMARY
    return raw.parts[1] + ('_other' if raw.parts[1] == 'eval_ground_endpoint' else '') + ':' + sensors


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)


def analyze(root, output, *, tracked=None, records=None):
    tracked = committed_inputs(root) if tracked is None else tracked
    records = list(discover(root, tracked) if records is None else records)
    inventory, runs, goals = [], [], []
    pool = defaultdict(Summary)
    for raw, primary, excluded in records:
        try:
            if excluded:
                raise MissingRecord(excluded)
            reference, ground, sensors, rtf, truth, water, nodata, mapper, final, terrain = read_record(
                root, tracked, raw, primary)
        except (OSError, KeyError, ValueError) as exc:
            inventory.append(dict(raw=str(raw), cohort=PRIMARY if primary else '', status='skipped', reason=str(exc)))
            print(f'skipped {raw}: {exc}')
            continue
        cohort = cohort_name(raw, primary, sensors)
        inventory.append(dict(raw=str(raw), cohort=cohort, status='used', reason=''))
        counts = first_counts(mapper)
        goal = (137, 294)
        detail = primary and raw.name == '08OB88_-0167' and tuple(int(primary['goal_'+axis]) for axis in 'xy') == goal
        stages = [('first_lidar', mapper.elev, mapper.seen, mapper.fine_obstacle, mapper.fine_inflated, mapper.lethal),
                  ('final', final['elev'], final['seen'], final['fine_obstacle'], final['fine_inflated'], final['lethal'])]
        for stage, elevation, seen, obstacle, halo, lethal in stages:
            features = map_features(terrain, counts, elevation, seen, obstacle, halo, nodata)
            tally = summarize_stage(pool, (cohort, stage), features, seen, water, nodata)
            runs.append(dict(raw=str(raw), cohort=cohort, patch=raw.name, stage=stage, reference=str(reference),
                             ground_estimate=ground, sensors=sensors, requested_rtf=rtf,
                             version=int(final['version']) if stage == 'final' else mapper.version, **tally))
            if detail:
                goals.extend(goal_rows(raw, primary, stage, goal, features, elevation, seen, lethal, truth, water, nodata))
        if detail:
            try:
                features, elevation, seen, lethal = failure_features(
                    root, tracked, raw, primary, mapper, terrain, counts, nodata, goal)
            except (OSError, KeyError, ValueError) as exc:
                print(f'skipped goal failure detail {raw}: {exc}')
            else:
                goals.extend(goal_rows(raw, primary, 'goal_failure', goal, features, elevation, seen, lethal, truth, water, nodata))
    output.mkdir(parents=True, exist_ok=True)
    tables = dict(inventory=inventory, runs=runs, goal_cells=goals, **summary_rows(pool))
    for name, rows in tables.items():
        write_csv(output/(name+'.csv'), rows)
    cohorts = Counter(row['cohort'] for row in inventory if row['status'] == 'used')
    print(f'{sum(cohorts.values())} paired records used; {len(inventory)-sum(cohorts.values())} skipped')
    for cohort, n in sorted(cohorts.items()):
        for stage in ('first_lidar', 'final'):
            print(f'{cohort} {stage} runs={n} ' + ' '.join(
                f'{name}={pool[cohort, stage, name].n}' for name in CLASSES))
    return tables


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    analyze(ROOT, args.out)
