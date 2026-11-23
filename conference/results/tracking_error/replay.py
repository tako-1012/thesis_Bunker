"""Describe tracking error from committed poses and timed path revisions."""

import argparse
from collections import Counter, defaultdict
import csv
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

import numpy as np
from scipy.ndimage import find_objects, label

from experiments.eval_runs import curvature, near_intervals, nearest_path, number, read_csv
from results.eval_044.audit044 import closest_fraction
from ros2_jazzy.gz_checks.online_batch_runtime import map_signature
from tapp.config import RESOLUTION, Robot
from tapp.mapfile import load_map_file
from tapp.obstacle_clearance import path_clearance, point_clearance
from tapp.pure_pursuit import prepare_path
from tapp.real_beach import build_real
from tapp.traversability import slope_deg

ROOT = Path(__file__).resolve().parents[2]
HARD = Robot().footprint_radius
BOX_NEAR = 1.5
SWITCH_S = 2.
STEP_M = .01
COS_45 = np.sqrt(.5)
LOG = re.compile(r'(trajectory|path_revisions|debris_footprints)(?:_part[0-9]{3})?\.csv(?:\.gz)?')
LEDGERS = {
    '030': 'eval_ground_endpoint/runs.csv',
    '035': 'eval_035/runs.csv',
    '037': 'real_sensors_compare/runs.csv',
    '039': 'rtf_compare/stage_b/common_eval/runs.csv',
    '044': 'eval_044/common_eval/runs.csv',
    '050': 'eval_050/common_eval/runs.csv',
    '057': 'eval_057/common_eval/runs.csv',
}
GROUPS = {
    'curvature': ('straight', 'gentle', 'sharp', 'unknown'),
    'slope': ('0-10', '10-20', '20-25', '>25', 'unknown'),
    'direction': ('uphill', 'downhill', 'cross_slope', 'unknown'),
    'command': ('near_zero', 'slow', 'medium', 'fast', 'unknown'),
    'switch': ('first_path', 'under_2s', 'at_least_2s'),
    'box': ('within_1.5m', 'beyond_1.5m', 'no_boxes', 'unknown'),
}
EVENT_FIELDS = ('study', 'run', 'source', 'classification', 'entered_s', 'exited_s', 'duration_s',
                'nearest_t_s', 'x', 'y', 'box_xyxy', 'min_box_m', 'path_t_s', 'deviation_at_nearest_m',
                'path_to_same_box_m', 'nearest_path_segment_to_box_m', 'projected_point_to_box_m')


def committed(root):
    listing = subprocess.check_output(['git', 'ls-tree', '-rz', '--name-only', 'HEAD', '--',
                                       'results', 'maps'], cwd=root)
    return {Path(p.decode()) for p in listing.split(b'\0') if p}


def table(root, tracked, raw, stem):
    # Use the common CSV parser on a clean checkout. Reject worktree-only parts.
    path = root/raw/(stem+'.csv')
    extra = set(path.parent.glob(stem+'*.csv*'))
    if any(p.is_file() and LOG.fullmatch(p.name) and p.relative_to(root) not in tracked for p in extra):
        raise ValueError(f'{stem}: CSV files not committed')
    return read_csv(path)


def ledgers(root, tracked):
    records = {}
    for study, name in LEDGERS.items():
        path = Path('results')/name
        if path not in tracked:
            continue
        for row in read_csv(root/path)[1]:
            raw = (Path(row['run']) if row.get('run') else path.parent/'runs'/row['patch']
                   /f"{row['condition']}_r{row['rep']}"/'physical_1'/'raw'/row['patch'])
            records[raw] = (study, row)
    return records


def discover(root, tracked, published):
    signals = defaultdict(set)
    for path in tracked:
        match = LOG.fullmatch(path.name)
        if match and 'follower' not in path.parts:
            signals[path.parent].add(match[1])
    folders = set(signals) | published.keys()
    for file in sorted(p for p in tracked if p.name == 'not_committed.txt'):
        for line in (root/file).read_text().splitlines():
            if line.startswith('#') or not line.strip():
                continue
            name = Path(line.split()[-1])
            if (LOG.fullmatch(name.name) and 'raw' in name.parts and 'follower' not in name.parts
                    and name.name.startswith(('trajectory', 'path_revisions'))):
                folders.add(name.parent if name.parts[0] == 'results' else file.parent/name.parent)
    return signals, sorted(folders)


def revision_data(rows):
    times = np.asarray([number(row['t']) for row in rows], float)
    if not np.isfinite(times).all() or (np.diff(times) < 0).any():
        raise ValueError('revision times missing or decreasing')
    return times, [prepare_path(json.loads(row['path'])) for row in rows]


def active(times, stamps):
    return np.searchsorted(times, stamps, side='right')-1


def read_run(root, tracked, raw, signals):
    if 'trajectory' not in signals:
        missing = 'trajectory not committed'
        if 'path_revisions' not in signals:
            missing += '; path revisions not committed'
        raise ValueError(missing)
    _, rows = table(root, tracked, raw, 'trajectory')
    if not rows:
        raise ValueError('trajectory has no position samples')
    values = np.asarray([[number(r[k]) for k in ('t', 'x', 'y')] for r in rows], float)
    t, xy = values[:, 0], values[:, 1:]
    if not np.isfinite(values).all() or (np.diff(t) < 0).any():
        raise ValueError('invalid positions or decreasing trajectory time')
    mission_path = raw/'mission.json'
    mission = json.loads((root/mission_path).read_text()) if mission_path in tracked else {}
    if 'path_revisions' in signals:
        times, paths = revision_data(table(root, tracked, raw, 'path_revisions')[1])
        if not len(times):
            raise ValueError('path revision log is empty')
        source = 'revisions'
    elif (raw.parts[1] == 'gazebo_compare' or raw.parts[:4] == ('results', 'online_mission', 'gazebo_claude', 'fixed')):
        times, paths = np.array([t[0]]), [prepare_path(mission['path'])]
        source = 'fixed_mission'
    else:
        raise ValueError('synthetic fixture' if mission.get('data_source') == 'synthetic_robot_sim'
                         else 'timed path revisions not committed')
    v = np.array([number(row.get('v')) for row in rows], float)
    return t, xy, v, times, paths, source, mission


def motion_features(xy, t, elev):
    slope = np.full(len(xy), np.nan)
    dirs = np.full(len(xy), 'unknown', dtype='<U12')
    if elev is None:
        return slope, dirs
    grid = np.floor(xy/RESOLUTION+.5).astype(int)
    inside = ((grid >= 0) & (grid < elev.shape)).all(axis=1)
    cell = tuple(grid[inside].T)
    slope[inside] = slope_deg(elev)[cell]
    gx, gy = np.gradient(elev, RESOLUTION)
    gradients = np.zeros_like(xy)
    gradients[inside] = np.column_stack((gx[cell], gy[cell]))
    delta = np.diff(xy, axis=0, prepend=xy[:1])
    travelled = np.linalg.norm(delta, axis=1)
    grad = np.linalg.norm(gradients, axis=1)
    moving = (travelled >= STEP_M) & (np.diff(t, prepend=t[0]) > 0) & (grad > 0) & inside
    cosine = np.sum(delta[moving]*gradients[moving], axis=1)/(travelled[moving]*grad[moving])
    dirs[moving] = np.where(cosine >= COS_45, 'uphill',
                           np.where(cosine <= -COS_45, 'downhill', 'cross_slope'))
    return slope, dirs


def curvature_samples(path, indices, projected):
    if len(path) <= 2:
        return np.full(len(indices), 0. if len(path) == 2 else np.nan)
    values = np.asarray([curvature(path[i-1:i+2], 0, path[i]) for i in range(1, len(path)-1)], float)
    left, right = np.clip(indices, 1, len(path)-2), np.clip(indices+1, 1, len(path)-2)
    near = np.where(np.linalg.norm(projected-path[left], axis=1) <=
                    np.linalg.norm(projected-path[right], axis=1), left, right)
    return values[near-1]


def errors(t, xy, times, paths):
    index = active(times, t)
    distance = np.full(len(t), np.nan)
    kappa = distance.copy()
    ends = np.r_[np.searchsorted(t, times), len(t)]
    for path, first, end in zip(paths, ends[:-1], ends[1:]):
        for start in range(first, end, 256):
            section = slice(start, min(start+256, end))
            d, seg, projected = nearest_path(xy[section], path)
            distance[section] = d
            kappa[section] = curvature_samples(path, seg, projected)
    return distance, kappa, index


def bounds_from_mask(mask):
    regions = find_objects(label(mask)[0])
    lo = np.array([[s.start for s in region] for region in regions]).reshape(-1, 2)
    hi = np.array([[s.stop for s in region] for region in regions]).reshape(-1, 2)
    centre = (lo+hi-1)*RESOLUTION/2
    size = (hi-lo)*RESOLUTION
    return centre-size/2, centre+size/2


@lru_cache(maxsize=20)
def world_scenario(patch, side, seed, dataset):
    return build_real(patch, side, seed, debris=True, dataset=dataset)


@lru_cache(maxsize=24)
def reference(path):
    with np.load(path, allow_pickle=False) as data:
        return SimpleNamespace(**{k: data['truth_'+k] for k in ('elev', 'rock', 'lethal')})


def signed_case(manifest, patch):
    data = json.loads(manifest.read_text())
    case, = [c for c in data['cases'] if c['patch'] == patch]
    return case['input_audit']['signatures']['truth']


def terrain_from_run(root, tracked, raw, mission):
    map_name = mission.get('map_id', '').removeprefix('file/')
    if map_name and '/' not in map_name and 'path' in mission:
        filename = Path(map_name).with_suffix('.npz')
        for parent in raw.parents:
            file = parent/'maps'/filename
            if file in tracked:
                terrain = load_map_file(root/file)
                return terrain['tmap'].elev, bounds_from_mask(terrain['obstacle']), str(file)
    physical = raw.parents[1]
    manifest = physical/'manifest.json'
    if manifest not in tracked:
        raise ValueError('runtime world manifest absent')
    data = json.loads((root/manifest).read_text())
    cases = [c for c in data['cases'] if c.get('run_folder') and physical/c['run_folder'] == raw]
    if not cases:
        # An interrupted observer can have retained logs before the manifest
        # was rewritten with its raw folder and actual reference signature.
        cases = [c for c in data['cases'] if c.get('selected') and c['patch'] == raw.name]
    if len(cases) != 1:
        raise ValueError('no unique world case for the archived trajectory')
    case = cases[0]
    patch = case['patch']
    meta, = [s for s in data['scenarios'] if s['patch'] == patch]
    baseline = Path('results/gazebo_lidar/physical_10')
    signature = (case.get('input_audit') or {}).get('signatures', {}).get('truth')
    if signature is None and data.get('world_input', '').startswith('task022 actual-run'):
        signature = signed_case(root/baseline/'manifest.json', patch)
    signature = signature or meta['truth_signature']
    scenario = world_scenario(patch, data['side_m'], data['seed'], data['dataset'])
    preferred = [raw/'evaluation_reference.npz']
    if case.get('world_reference'):
        preferred.append(Path(case['world_reference']))
    preferred.append(baseline/'raw'/patch/'evaluation_reference.npz')
    layers = scenario['tmap']
    note = 'reproduced '+str(manifest)
    for file in preferred:
        if file in tracked:
            candidate = reference(root/file)
            if map_signature(dict(tmap=candidate)) == signature:
                layers, note = candidate, str(file)
                break
    observed = map_signature(dict(tmap=layers))
    if observed['rock'] != signature['rock']:
        raise ValueError('reproduced obstacle mask does not match signed runtime mask')
    if not np.array_equal(layers.rock, scenario['tmap'].rock):
        raise ValueError('reference and reproduced obstacle masks differ')
    elev = layers.elev if observed == signature else None
    if elev is None:
        note += ' (verified obstacle mask; elevation signature disagrees)'
    return elev, bounds_from_mask(scenario['terrain']['rock']), note


def read_boxes(root, tracked, raw):
    header, rows = table(root, tracked, raw, 'debris_footprints')
    if header is None or not {'xmin', 'ymin', 'xmax', 'ymax'}.issubset(header):
        raise ValueError('box footprint columns missing')
    values = np.array([[number(row[k]) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
                       for row in rows], float).reshape(-1, 4)
    lo, hi = values[:, :2], values[:, 2:]
    if not np.isfinite(values).all() or np.any(hi <= lo):
        raise ValueError('invalid box bounds')
    return lo, hi


def box_distances(xy, boxes):
    if boxes is None or not len(boxes[0]):
        return np.full(len(xy), np.nan)
    lo, hi = boxes
    out = np.empty(len(xy))
    for start in range(0, len(xy), 256):
        part = slice(start, start+256)
        points = xy[part, None]
        d = np.maximum(np.maximum(lo-points, points-hi), 0.)
        out[part] = np.hypot(d[..., 0], d[..., 1]).min(axis=1)
    return out


def conditions(t, xy, v, kappa, index, times, elev, box_m, boxes):
    slope, direction = motion_features(xy, t, elev)
    speed = np.abs(v)
    return {
        'curvature': np.select([kappa < .02, kappa < .10, kappa >= .10],
                               GROUPS['curvature'][:-1], 'unknown'),
        'slope': np.select([slope < 10, slope < 20, slope <= 25, slope > 25],
                           GROUPS['slope'][:-1], 'unknown'),
        'direction': direction,
        'command': np.select([speed <= .05, speed < .30, speed < .60, speed >= .60],
                             GROUPS['command'][:-1], 'unknown'),
        'switch': np.select([index == 0, t-times[index] < SWITCH_S],
                            GROUPS['switch'][:2], 'at_least_2s'),
        'box': (np.full(len(t), 'unknown' if boxes is None else 'no_boxes') if np.isnan(box_m).all()
                else np.where(box_m <= BOX_NEAR, 'within_1.5m', 'beyond_1.5m')),
    }


def classification(projected_m):
    if projected_m is None:
        return 'unclassified'
    return 'path_too_close' if projected_m < HARD else 'tracking_deviation'


def approach_segments(t, xy, boxes, distances):
    """Yield continuous strict-near intervals and their closest samples."""
    lo, hi = boxes
    if len(t) == 1 and distances[0] < HARD:
        gaps = np.maximum(np.maximum(lo-xy[0], xy[0]-hi), 0.)
        j = int(np.linalg.norm(gaps, axis=1).argmin())
        yield t[0], t[0], (distances[0], t[0], j, xy[0])
        return
    previous = None
    length = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    # Clearance is 1-Lipschitz along a segment. Screen segments without near points.
    possible = np.flatnonzero(np.minimum(distances[:-1], distances[1:])-length/2 < HARD)
    for i in possible:
        a, b = xy[i:i+2]
        dt = t[i+1]-t[i]
        nearby = np.flatnonzero(((lo-HARD < np.maximum(a, b)) &
                                 (hi+HARD > np.minimum(a, b))).all(axis=1))
        for left, right in near_intervals(a, b, lo[nearby], hi[nearby]):
            enter, leave = t[i]+left*dt, t[i]+right*dt
            start, stop = a+left*(b-a), a+right*(b-a)
            choices = []
            for j in nearby:
                u = closest_fraction(start, stop, lo[j], hi[j])
                point = start+u*(stop-start)
                d = point_clearance(point, lo[j:j+1], hi[j:j+1])
                choices.append((d, enter+u*(leave-enter), int(j), point))
            best = min(choices, key=lambda hit: hit[:3])
            if previous and previous[3] == i-1 and left == 0 and distances[i] < HARD:
                begin, _, old_best, _ = previous
                previous = (begin, leave, min((old_best, best), key=lambda hit: hit[:3]), i)
            else:
                if previous:
                    yield previous[:3]
                previous = (enter, leave, best, i)
        # Nonconsecutive segments cannot extend a previous interval.
    if previous:
        yield previous[:3]


def event_geometry(stamp, point, times, paths, lo, hi):
    i = active(times, stamp)
    if i < 0:
        return {}
    path = paths[i]
    errors, segment, projection = nearest_path(point[None], path)
    j = segment[0]
    return dict(path_t_s=times[i], deviation_at_nearest_m=errors[0],
                path_to_same_box_m=path_clearance(path, lo, hi),
                nearest_path_segment_to_box_m=path_clearance(path[j:j+2], lo, hi),
                projected_point_to_box_m=point_clearance(projection[0], lo, hi))


def events(t, xy, times, paths, boxes, distances):
    if boxes is None or not len(boxes[0]):
        return
    lo, hi = boxes
    for enter, leave, (d, stamp, j, point) in approach_segments(t, xy, boxes, distances):
        box = lo[j:j+1], hi[j:j+1]
        geometry = event_geometry(stamp, point, times, paths, *box)
        yield dict(entered_s=enter, exited_s=leave, duration_s=leave-enter, nearest_t_s=stamp,
                   x=point[0], y=point[1], box_xyxy=json.dumps([*lo[j], *hi[j]]), min_box_m=d,
                   classification=classification(geometry.get('projected_point_to_box_m')), **geometry)


def stats(values, runs):
    quantiles = np.percentile(values, [50, 90, 95, 99]) if len(values) else [None]*4
    return dict(samples=len(values), runs=runs, **dict(zip(('p50_m', 'p90_m', 'p95_m', 'p99_m'), quantiles)),
                max_m=values.max() if len(values) else None,
                hard_plus_p95_m=HARD+quantiles[2] if len(values) else None)


def summarize(bins):
    return [dict(feature=feature, bin=group, **stats(np.concatenate(chunks) if chunks else [],
                                                    len(chunks)))
            for (feature, group), chunks in bins.items()]


def add_values(bins, study, source, distance, valid, features):
    errors_valid = distance[valid]
    for key in [('all', 'all'), ('study', study), ('path_source', source)]:
        bins[key].append(errors_valid)
    for key, labels in features.items():
        for group in GROUPS[key]:
            matches = valid & (labels == group)
            if matches.any():
                bins[key, group].append(distance[matches])
    for slope in GROUPS['slope']:
        for direction in GROUPS['direction']:
            matches = valid & (features['slope'] == slope) & (features['direction'] == direction)
            if matches.any():
                bins['slope_direction', slope+'/'+direction].append(distance[matches])


def digest_run(t, xy, times, paths):
    h = hashlib.sha256()
    for a in (t, xy, times, *paths):
        h.update(np.asarray(a.shape, '<i8').tobytes())
        h.update(np.asarray(a, '<f8').tobytes())
    return h.digest()


def known_approaches(root, tracked, published, used):
    """Carry through older event evidence when raw positions were omitted."""
    evidence = Path('results/eval_044/approach_evidence.csv')
    rows, covered = [], Counter()
    if evidence in tracked:
        lookup = {(r['patch'], r['condition'], int(r['rep'])): raw
                  for raw, (study, r) in published.items() if study == '044'}
        for row in read_csv(root/evidence)[1]:
            raw = lookup[row['patch'], row['condition'], int(row['rep'])]
            if raw in used:
                continue
            fields = {k: row[k] for k in EVENT_FIELDS if k in row}
            rows.append(dict(fields, study='044', run=str(raw), source=str(evidence),
                             classification=classification(number(row['projected_point_to_box_m']))))
            covered[raw] += 1
    unresolved = []
    for raw, (study, row) in published.items():
        value = number(row.get('truth_below_radius_entries'))
        if value and raw not in used and value > covered[raw]:
            unresolved.append(dict(study=study, run=str(raw), intervals=int(value)-covered[raw],
                                   total_near_duration_s=row.get('truth_below_radius_s'),
                                   run_min_box_m=row.get('min_truth_clearance_m'),
                                   reason='event trajectory or active polyline not committed'))
    return rows, unresolved


def write(path, rows, columns=None):
    if columns is None:
        columns = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def study_key(raw):
    if raw.parts[1] == 'rtf_check':
        return '/'.join(raw.parts[1:3])
    return raw.parts[1]


def analyze(root, output, *, tracked=None, selected=None):
    tracked = committed(root) if tracked is None else tracked
    published = ledgers(root, tracked)
    signals, folders = discover(root, tracked, published)
    inventory, results, episodes = [], [], []
    bins = defaultdict(list, {(key, group): [] for key, names in GROUPS.items() for group in names})
    prior_digests = {}
    used = set()
    for raw in folders if selected is None else selected:
        study, _ = published.get(raw, (study_key(raw), {}))
        identity = dict(study=study, run=str(raw))
        try:
            t, xy, v, times, paths, source, mission = read_run(root, tracked, raw, signals[raw])
            digest = digest_run(t, xy, times, paths)
            if digest in prior_digests:
                raise ValueError(f'duplicate trajectory and revisions of {prior_digests[digest]}')
            distance, kappa, index = errors(t, xy, times, paths)
            valid = index >= 0
            if not valid.any():
                raise ValueError('no position sample has a corresponding path')
        except (OSError, ValueError, KeyError) as exc:
            print(f'skipped {raw}: {exc}')
            inventory.append(dict(identity, status='skipped', reason=str(exc)))
            continue
        prior_digests[digest] = raw
        inventory.append(dict(identity, status='used', reason=''))
        issue = ''
        try:
            elev, boxes, world = terrain_from_run(root, tracked, raw, mission)
        except (OSError, ValueError, KeyError) as exc:
            elev = boxes = world = None
            issue = str(exc)
        box_source = world if boxes is not None else None
        if 'debris_footprints' in signals[raw]:
            try:
                boxes = read_boxes(root, tracked, raw)
                box_source = 'debris_footprints'
            except (OSError, ValueError, KeyError) as exc:
                issue = '; '.join(filter(None, (issue, str(exc))))
        near = box_distances(xy, boxes)
        features = conditions(t, xy, v, kappa, index, times, elev, near, boxes)
        add_values(bins, study, source, distance, valid, features)
        run_events = list(events(t, xy, times, paths, boxes, near))
        episodes.extend(dict(identity, source='recomputed', **event) for event in run_events)
        if boxes is not None:
            used.add(raw)
        peak = int(np.nanargmax(distance))
        results.append(dict(identity, path_source=source, versions=len(times), pose_samples=len(t),
                            samples_without_path=int((~valid).sum()), terrain_source=world,
                            slope_available=elev is not None, box_source=box_source,
                            boxes=None if boxes is None else len(boxes[0]), missing_world_reason=issue,
                            near_intervals=None if boxes is None else len(run_events), max_t_s=t[peak],
                            max_x_m=xy[peak, 0], max_y_m=xy[peak, 1], max_path_t_s=times[index[peak]],
                            max_command_mps=v[peak] if np.isfinite(v[peak]) else None,
                            **stats(distance[valid], 1)))
    evidence, unresolved = known_approaches(root, tracked, published, used) if selected is None else ([], [])
    episodes.extend(evidence)
    summary = summarize(bins)
    output.mkdir(parents=True, exist_ok=True)
    write(output/'inventory.csv', inventory)
    write(output/'runs.csv', results)
    write(output/'distribution.csv', summary)
    write(output/'approaches.csv', episodes, EVENT_FIELDS)
    write(output/'unclassified_approaches.csv', unresolved)
    print(f'{len(results)} runs analysed; {len(inventory)-len(results)} skipped; '
          f'{len(episodes)} near-box intervals with event records; {sum(r["intervals"] for r in unresolved)} aggregate-only intervals')
    for source in Counter(row['study'] for row in inventory):
        group = [row for row in inventory if row['study'] == source]
        print(f'{source}: {sum(r["status"] == "used" for r in group)}/{len(group)} runs analysed')
    print((output/'distribution.csv').read_text(), end='')
    return inventory, results, summary, episodes, unresolved


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    analyze(ROOT, args.out)
