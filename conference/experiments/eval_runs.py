"""Evaluate retained Gazebo run records offline, with per-field missing reasons."""

import argparse
import csv
from functools import lru_cache
import gzip
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace

import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.endpoint_audit import audit_run
from experiments.eval_ground_endpoint_report import FAILURE_CLASSES, contacts, final_map
from experiments.gz_online_batch_report import reached_goals
from experiments.lidar_fine_report import map_audit
from tapp.collision import path_lethal_cells, segment_cells
from tapp.config import RESOLUTION, Robot
from tapp.obstacle_clearance import path_clearance, point_clearance
from tapp.pure_pursuit import prepare_path
from tapp.real_beach import build_real
from tapp.traversability import inflate, slope_deg


RADIUS = Robot().footprint_radius
SENSORS = ('lidar', 'camera1', 'camera2')
OUTCOMES = ('completed', 'partial', 'no_path', 'stuck', 'rollover', 'other_error', 'unknown')
BOARD = dict(completed='完走', partial='一部', no_path='経路なし', stuck='止まったまま', rollover='転倒')
TAG = re.compile(r'(?P<condition>.+)_r(?P<rep>[1-9]\d*)$')
INPUT_MARKERS = {'mission.json', 'pointcloud_map.npz', 'endpoint_status.json', 'evaluation_reference.npz'}
INPUT_CSV = {'trajectory', 'map_updates', 'plans', 'path_revisions', 'debris_footprints', 'clearance', 'safety_events'}


def number(value):
    if value is None or value == '':
        return None
    value = float(value)
    if not np.isfinite(value):
        raise ValueError('non-finite numeric field')
    return value


def read_csv(path):
    """Return the header and rows, including split and gzip-compressed CSVs."""
    if path is None:
        return None, []
    candidates = [path, path.with_suffix('.csv.gz'),
                  *path.parent.glob(path.stem + '_part[0-9][0-9][0-9].csv*')]
    parts = {}
    for file in sorted(p for p in candidates if p.is_file()):
        match = re.fullmatch(re.escape(path.stem) + r'(?:_part([0-9]{3}))?\.csv(?:\.gz)?', file.name)
        if match:
            parts.setdefault(int(match[1] or 0), file)  # Prefer plain CSV if both exist.
    header, rows = None, []
    for expected, (index, file) in enumerate(sorted(parts.items())):
        if index != expected:
            raise ValueError(f'{path.name}: missing CSV part {expected}')
        opener = gzip.open if file.suffix == '.gz' else open
        with opener(file, 'rt', encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or (header is not None and header != reader.fieldnames):
                raise ValueError(f'{path.name}: invalid or inconsistent headers')
            header = reader.fieldnames
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f'{file.name}:{reader.line_num}: incomplete CSV row')
                rows.append(row)
    return header, rows


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def discover(root):
    """Yield one record per raw beach, or per retained trial stub."""
    for folder, dirs, files in os.walk(root):
        path = Path(folder)
        dirs.sort()
        has_record = INPUT_MARKERS.intersection(files) or any(
            f.split('.csv')[0].split('_part')[0] in INPUT_CSV for f in files if f.endswith(('.csv', '.csv.gz')))
        if (path.parent.name == 'raw' or has_record
                or ('run_conditions.txt' in files and not any(d.startswith('physical_') for d in dirs))):
            dirs[:] = []
            yield path


def read_conditions(path):
    if path is None:
        return {}
    header, rows = read_csv(path)
    if not header or not {'path', 'condition'} <= set(header):
        raise ValueError('conditions CSV requires path,condition columns')
    pairs = {}
    for row in rows:
        folder = (path.parent / row['path']).resolve()
        if folder in pairs or not row['condition'].strip():
            raise ValueError(f'duplicate path or empty condition: {folder}')
        pairs[folder] = row['condition'].strip()
    return pairs


def label_record(raw, experiment, conditions):
    physical = next((p for p in raw.parents if p.name.startswith('physical_')), None)
    trial = physical.parent if physical else raw
    settings = trial/'run_conditions.txt'
    tags = dict(re.findall(r'(?:^|\s)(patch|condition|rep)=([^\s]+)', settings.read_text())) if settings.is_file() else {}
    match = TAG.fullmatch(trial.name)
    run = raw.relative_to(Path.cwd()) if raw.is_relative_to(Path.cwd()) else raw
    row = dict(run=str(run), experiment=experiment,
               patch=tags.get('patch') or (raw.name if raw.parent.name == 'raw' else None),
               condition=next((conditions[p] for p in (raw, *raw.parents) if p in conditions), None)
               or tags.get('condition') or (match['condition'] if match else None),
               rep=None)
    rep = tags.get('rep') or (match['rep'] if match else '')
    issues = {}
    if rep.isdecimal() and int(rep) > 0:
        row['rep'] = int(rep)
    elif rep:
        issues['rep'] = 'invalid repetition number in run_conditions.txt'
    exit_file = trial/'exit.txt'
    if not exit_file.is_file() and physical:
        exit_file = physical/'exit.txt'
    if exit_file.is_file():
        try:
            row['exit_code'] = int(exit_file.read_text().strip())
        except (ValueError, OSError) as error:
            issues['exit_code'] = f'exit.txt: {error}'
    manifest_path = (physical or raw)/'manifest.json'
    if not manifest_path.is_file() and raw.parent.name == 'raw':
        manifest_path = raw.parents[1]/'manifest.json'
    return row, trial, manifest_path, issues


def nearest_path(xy, path):
    """Distances and the closest segment per sample of one path revision."""
    if len(path) == 1:
        return np.linalg.norm(xy-path[0], axis=1), np.zeros(len(xy), int), xy*0 + path[0]
    starts, delta = path[:-1], np.diff(path, axis=0)
    offset = xy[:, None]-starts
    fraction = np.clip(np.sum(offset*delta, axis=-1)/np.sum(delta**2, axis=-1), 0, 1)
    projected = starts+fraction[..., None]*delta
    distance = np.linalg.norm(xy[:, None]-projected, axis=-1)
    index = distance.argmin(axis=1)
    return distance[np.arange(len(xy)), index], index, projected[np.arange(len(xy)), index]


def curvature(path, segment, projection):
    """Unsigned Menger curvature at the nearest incident interior vertex."""
    vertices = [i for i in (segment, segment+1) if 0 < i < len(path)-1]
    if not vertices:
        return None
    i = min(vertices, key=lambda j: np.linalg.norm(path[j]-projection))
    a, b = np.diff(path[i-1:i+2], axis=0)
    lengths = np.linalg.norm(a)*np.linalg.norm(b)*np.linalg.norm(a+b)
    return 2*abs(a[0]*b[1]-a[1]*b[0])/lengths if lengths else None


def deviation_metrics(t, xy, revisions):
    times = np.array([number(r['t']) for r in revisions], dtype=float)
    if not np.isfinite(times).all() or (np.diff(times) < 0).any():
        raise ValueError('path revision time missing or decreased')
    paths = [prepare_path(json.loads(r['path'])) for r in revisions]
    bounds = np.searchsorted(t, times)
    distances = []
    peak = -1.
    result = {}
    for path, revision_t, first, end in zip(paths, times, bounds, [*bounds[1:], len(t)]):
        for start in range(first, end, 256):
            stop = min(start+256, end)
            distance, nearest, projected = nearest_path(xy[start:stop], path)
            distances.append(distance)
            i = int(distance.argmax())
            if distance[i] > peak:
                peak = distance[i]
                sample = start+i
                result.update(deviation_max_t_s=t[sample], deviation_max_x_m=xy[sample, 0],
                              deviation_max_y_m=xy[sample, 1], deviation_max_path_t_s=revision_t,
                              deviation_max_curvature_inv_m=curvature(path, nearest[i], projected[i]))
    if distances:
        values = np.concatenate(distances)
        result.update(deviation_samples=len(values), deviation_mean_m=np.mean(values),
                      deviation_max_m=peak, deviation_p95_m=np.percentile(values, 95),
                      deviation_over_075_samples=np.count_nonzero(values > .75))
    else:
        result['deviation_samples'] = 0
    return result


def open_box_interval(a, d, lower, upper):
    lo, hi = 0., 1.
    for p, step, left, right in zip(a, d, lower, upper):
        if step == 0:
            if not left < p < right:
                return None
        else:
            first, last = sorted(((left-p)/step, (right-p)/step))
            lo, hi = max(lo, first), min(hi, last)
    return (lo, hi) if hi > lo else None


def near_intervals(a, b, lower, upper):
    """Open radius neighbourhood of rectangles, intersected with a segment."""
    d = b-a
    length2 = d @ d
    intervals = []
    for lo, hi in zip(lower, upper):
        # Two open bands plus the four open corner discs form the offset.
        for margin in ([RADIUS, 0], [0, RADIUS]):
            hit = open_box_interval(a, d, lo-margin, hi+margin)
            if hit:
                intervals.append(hit)
        for p in ((lo[0], lo[1]), (lo[0], hi[1]), (hi[0], lo[1]), (hi[0], hi[1])):
            offset = np.asarray(p)-a
            if not length2:
                if offset @ offset < RADIUS**2:
                    intervals.append((0., 1.))
                continue
            centre = (offset @ d)/length2
            perpendicular = offset-centre*d
            width_sq = (RADIUS**2-perpendicular @ perpendicular)/length2
            if width_sq > 0:
                width = np.sqrt(width_sq)
                start, end = max(0., centre-width), min(1., centre+width)
                if start < end:
                    intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and (start < merged[-1][1] or (start == merged[-1][1]
                       and point_clearance(a+start*d, lower, upper) < RADIUS)):
            merged[-1] = merged[-1][0], max(merged[-1][1], end)
        else:
            merged.append((start, end))
    return merged


def box_metrics(t, xy, rows):
    bounds = np.array([[float(row[k]) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
                       for row in rows]).reshape(-1, 4)
    lower, upper = bounds[:, :2], bounds[:, 2:]
    if not np.isfinite(bounds).all() or np.any(upper <= lower):
        raise ValueError('invalid debris footprint')
    best = path_clearance(xy, lower, upper)
    count = int(best is not None and len(xy) == 1 and best < RADIUS)
    duration, continued = 0., False
    for a, b, dt in zip(xy[:-1], xy[1:], np.diff(t)):
        nearby = ((lower-RADIUS < np.maximum(a, b)) & (upper+RADIUS > np.minimum(a, b))).all(axis=1)
        lo, hi = lower[nearby], upper[nearby]
        intervals = near_intervals(a, b, lo, hi)
        for start, end in intervals:
            duration += dt*(end-start)
            count += not (start == 0 and continued)
        continued = bool(intervals and intervals[-1][1] == 1
                         and point_clearance(b, lo, hi) < RADIUS)
    return dict(truth_footprints=len(lower), min_truth_clearance_m=best,
                truth_below_radius_s=duration, truth_below_radius_entries=count)


def read_trajectory(raw):
    header, rows = read_csv(raw/'trajectory.csv')
    if not rows:
        raise ValueError('trajectory.csv(.gz) missing' if header is None else 'trajectory has no pose samples')
    trace = np.array([[number(r[k]) for k in ('t', 'x', 'y')] for r in rows], dtype=float)
    if not np.isfinite(trace).all() or (np.diff(trace[:, 0]) < 0).any():
        raise ValueError('invalid position or decreasing trajectory time')
    return trace, header, rows


def pose_metrics(t, xy, header, rows):
    moved = np.flatnonzero(np.linalg.norm(xy - xy[-1], axis=1) > .05)
    result = dict(sim_end_t=t[-1], stationary_tail_s=t[-1]-t[moved[-1]+1 if len(moved) else 0])
    for axis in ('roll', 'pitch'):
        if axis not in header or any(not r[axis] for r in rows):
            continue
        angle = np.abs([number(r[axis]) for r in rows])
        degrees = np.degrees(angle)
        result[f'{axis}_p95_deg'] = np.percentile(degrees, 95)
        result[f'{axis}_max_deg'] = degrees.max()
        if axis == 'roll':
            hits = np.flatnonzero(angle > np.pi/2)
            result['rolled_over'] = bool(len(hits))
            if len(hits):
                i = hits[0]
                result.update(rollover_t_s=t[i], rollover_elapsed_s=t[i]-t[0],
                              rollover_x_m=xy[i, 0], rollover_y_m=xy[i, 1])
    return result


def recording_status(row, mission, case, endpoint, metadata, t, xy):
    recorded = mission.get('status') or case.get('termination')
    out = dict(recorded_status=recorded, data_source=mission.get('data_source'),
               online_error=mission.get('online_error') or mission.get('error') or case.get('error'))
    begin, end, wall = (number(mission.get(k)) for k in ('started_t', 'finished_t', 'wall_elapsed_s'))
    if begin is not None and end is not None and end >= begin:
        out['elapsed_s'] = end-begin
        if wall is not None and wall > 0:
            out['sim_to_wall_ratio'] = (end-begin)/wall
    elif len(t):
        start = begin if begin is not None else t[0]
        finish = end if end is not None else t[-1]
        if finish >= start:
            out['elapsed_s'] = finish-start
    start = metadata.get('start', mission.get('start_cells'))
    stops = metadata.get('stops', mission.get('stops_cells'))
    if len(t) and start is not None and stops is not None and len(stops) >= 5:
        out['goals_reached'] = reached_goals(xy, np.asarray(stops[:5])*RESOLUTION)
        out['returned_to_start'] = bool(np.linalg.norm(xy[-1]-np.asarray(start)*RESOLUTION) <= .3)
    status = 'timeout' if recorded == 'simulation_timeout' else recorded
    if row.get('rolled_over') or recorded == 'rollover':
        status = 'rollover'
    elif row.get('exit_code') in (124, 137):
        status = 'wall_timeout'
    elif row.get('ev_unsafe_tilt_repeat') or recorded == 'unsafe_tilt_repeat':
        status = 'unsafe_tilt_repeat'
    elif row.get('ev_join_rejected_timeout') or 'join_rejected' in (out['online_error'] or ''):
        status = 'join_rejected'
    elif status == 'completed' and 'goals_reached' in out:
        if out['goals_reached'] != 5 or not out['returned_to_start']:
            status = 'incomplete_waypoints'
    outcome = 'partial' if status in ('incomplete_waypoints', 'partial') else status
    if outcome in ('running', 'pending', 'unrun'):
        outcome = None
    if status == 'completed' and any(s.get('outcome') in ('nearby', 'unreachable') for s in endpoint.get('stops', [])):
        outcome = 'partial'
    out.update(status=status, outcome=outcome, completed=outcome == 'completed' if outcome else None)
    return out


def measure_times(result, prefix, times):
    if times:
        result.update({f'{prefix}_median': np.median(times), f'{prefix}_p95': np.percentile(times, 95),
                       f'{prefix}_max': max(times)})


def plan_metrics(header, rows):
    result = dict(n_plans=len(rows))
    if 'reason' in header and all(r['reason'] for r in rows):
        result.update(n_replans=sum(r['reason'] != 'start_leg' for r in rows),
                      replans_lethal_changed=sum(r['reason'] == 'lethal_changed' for r in rows))
    if 'plan_time_s' in header and all(r['plan_time_s'] for r in rows):
        times = [number(r['plan_time_s']) for r in rows]
        if min(times, default=0) < 0:
            raise ValueError('negative planning duration')
        measure_times(result, 'plan_s', times)
        result['calls_over_1s'] = sum(s > 1 for s in times)
    if 'success' in header and all(r['success'] in ('True', 'False') for r in rows):
        failures = [r for r in rows if r['success'] == 'False']
        result['failed_plans'] = len(failures)
        if 'failure_class' in header:
            for name in FAILURE_CLASSES:
                result['fail_'+name] = sum(r['failure_class'] == name for r in failures)
            result['fail_unclassified'] = sum(r['failure_class'] not in FAILURE_CLASSES for r in failures)
            if failures:
                result['last_failure_class'] = failures[-1]['failure_class'] or None
    return result


EVENTS = ('join_accepted', 'join_rejected', 'join_rejected_timeout', 'unsafe_tilt',
          'off_path', 'safety_replanned', 'unsafe_tilt_repeat')


def safety_metrics(rows, t, xy):
    events = [(number(r['sim_time']), r['event'], json.loads(r.get('detail') or '{}')) for r in rows]
    if any(t is None or not event or not isinstance(detail, dict) for t, event, detail in events):
        raise ValueError('invalid safety event')
    result = {'ev_'+kind: sum(event == kind for _, event, _ in events) for kind in EVENTS}
    result['join_accepted_with_blocked'] = sum(bool(detail.get('blocked_cells'))
                                              for _, kind, detail in events if kind == 'join_accepted')
    stops = [(stamp, kind) for stamp, kind, _ in events if kind in ('off_path', 'unsafe_tilt')]
    replans = [stamp for stamp, kind, _ in events if kind == 'safety_replanned']
    result['stops_replanned_30s'] = sum(any(s <= r <= s+30 for r in replans) for s, _ in stops)
    if stops and not len(t):
        return result
    details, recovered = [], 0
    for stamp, kind in stops:
        later = [r for r in replans if stamp <= r <= stamp+30]
        i = np.searchsorted(t, stamp)
        if i == len(t):
            return result
        distance = np.linalg.norm(xy[i:]-xy[i], axis=1)
        within = t[i:] <= stamp+30
        afterwards = (t[i:] >= min(later)) & within if later else np.zeros_like(within)
        recovered += bool((distance[afterwards] > 1).any())
        details.append(dict(t=stamp, kind=kind, replanned_30s=bool(later),
                            moved_30s_m=round(float(distance[within].max(initial=0)), 2),
                            moved_until_end_m=round(float(distance.max(initial=0)), 2),
                            seconds_to_end=round(float(t[-1]-stamp), 1)))
    result.update(stops_detail=json.dumps(details), stops_replanned_and_moved_30s=recovered,
                  stops_then_moved=sum(d['moved_until_end_m'] > 1 for d in details),
                  stops_then_stationary=sum(d['moved_until_end_m'] <= 1 for d in details))
    return result


def update_metrics(header, rows, ratio, elapsed_window):
    result = {}
    groups = [('', rows)]
    if 'sensor' in header:
        groups.extend((s+'_', [r for r in rows if r['sensor'] == s])
                      for s in sorted({r['sensor'] for r in rows} & set(SENSORS)))
    elif all('sensor' not in r for r in rows):
        groups.append(('lidar_', rows))
    for prefix, group in groups:
        if 'status' not in header or any(not r['status'] for r in group):
            continue
        ok = [r for r in group if r['status'] == 'ok']
        result[prefix+'map_updates'] = len(ok)
        result[prefix+'map_failed_updates'] = len(group)-len(ok)
        if 'update_s' in header and all(r['update_s'] for r in ok):
            times = [number(r['update_s']) for r in ok]
            if min(times, default=0) < 0:
                raise ValueError('negative map update duration')
            measure_times(result, prefix+'map_update_s', times)
            if (times and ratio is not None and ratio > 0 and elapsed_window is not None
                    and 'stamp' in header and all(r['stamp'] for r in ok)):
                begin, end = elapsed_window
                mission_times = [v for r, v in zip(ok, times) if begin <= number(r['stamp']) <= end]
                if mission_times:
                    count = sum(v > .1/ratio for v in mission_times)
                    result[prefix+'update_over_period_count'] = count
                    result[prefix+'update_over_period_share'] = count/len(mission_times)
        if prefix and 'queue_drops' in header:
            drops = [number(r['queue_drops']) for r in group if r['queue_drops']]
            if drops:
                result[prefix+'queue_drops_last'] = int(drops[-1])
    return result


def probe_metrics(rows):
    result = {}
    running = [r for r in rows if r.get('status') == 'running' and r.get('sim_t')]
    ages = [number(r['cloud_age_sim_s']) for r in running if r.get('cloud_age_sim_s')]
    if ages:
        result['cloud_age_sim_max_s'] = max(ages)
    if len(running) < 2:
        return result
    sim = np.array([number(r['sim_t']) for r in running])
    if (np.diff(sim) < 0).any() or sim[-1] <= sim[0]:
        return result
    # The probe resets cmd_count after every record. Exclude the count
    # accumulated before the first running timestamp in the denominator.
    if all(r.get('cmd_count') for r in running[1:]):
        result['cmd_vel_hz_sim'] = sum(number(r['cmd_count']) for r in running[1:])/(sim[-1]-sim[0])
    if all(r.get('wall_s') for r in running):
        wall = np.array([number(r['wall_s']) for r in running])
        if (np.diff(wall) > 0).all():
            result['probe_rtf'] = (sim[-1]-sim[0])/(wall[-1]-wall[0])
    return result


def reference_data(raw, reference_root, patch):
    path = raw/'evaluation_reference.npz'
    if not path.is_file() and reference_root is not None and patch:
        path = reference_root/patch/'evaluation_reference.npz'
    if not path.is_file():
        raise ValueError('evaluation_reference.npz missing')
    with np.load(path, allow_pickle=False) as archive:
        ref = {key: archive[key] for key in ('truth_elev', 'truth_rock', 'truth_lethal', 'prior_rock')}
    shape = ref['truth_elev'].shape
    if len(shape) != 2 or min(shape) < 2 or not all(ref[k].dtype == bool and ref[k].shape == shape
                                                     for k in ('truth_rock', 'truth_lethal', 'prior_rock')):
        raise ValueError('invalid evaluation grid')
    return path, ref


def cell_metrics(xy, ref):
    result = {}
    debris = ref['truth_rock'] & ~ref['prior_rock']
    for mask, length, entries, cells in ((ref['truth_lethal'], 'truth_lethal_len_m', 'truth_lethal_entries', 'lethal_cells'),
                                         (debris, 'debris_len_m', 'debris_entries', 'debris_cells')):
        result[length], result[entries] = contacts(xy, mask)
        result[cells] = len(path_lethal_cells(xy/RESOLUTION, mask))
    cells = xy/RESOLUTION
    result['out_of_bounds_samples'] = np.any((cells < 0) | (cells > np.asarray(debris.shape)-1), axis=1).sum()
    return result


@lru_cache(maxsize=16)
def terrain_for(patch, size, seed):
    return build_real(patch, size, seed, debris=True, dataset='shizuoka_beach_las')['terrain']


def map_metrics(fmap, source, ref, manifest, patch):
    shape = ref['truth_elev'].shape
    truth = SimpleNamespace(elev=ref['truth_elev'], lethal=ref['truth_lethal'], shape=shape)
    seen, lethal, detected, elev = (fmap[k] for k in ('seen', 'lethal', 'obstacle', 'elev'))
    if not all(a.dtype == bool and a.shape == shape for a in (seen, lethal, detected)) or elev.shape != shape:
        raise ValueError('estimate and reference grids differ')
    fp, fn = seen & lethal & ~truth.lethal, seen & ~lethal & truth.lethal
    steep = inflate(slope_deg(elev) > Robot().max_slope_deg, RADIUS)
    clearance = truth.lethal | inflate(slope_deg(truth.elev) > Robot().max_slope_deg, RADIUS)
    result = dict(map_seen_cells=seen.sum(), map_lethal_cells=(seen & lethal).sum(),
                  truth_lethal_cells=(seen & truth.lethal).sum(), map_fp_cells=fp.sum(), map_fn_cells=fn.sum(),
                  map_fp_steep_cells=(fp & steep).sum(), map_fp_obstacle_only_cells=(fp & ~steep).sum(),
                  clearance_fp_cells=(seen & lethal & ~clearance).sum(), clearance_fn_cells=(seen & ~lethal & clearance).sum())
    if source == 'pointcloud_map.npz' and seen.any() and np.isfinite(elev[seen]).all():
        errors = np.abs(elev[seen]-truth.elev[seen])
        result.update(height_abs_error_median_m=np.median(errors), height_abs_error_p95_m=np.percentile(errors, 95))
    if manifest.get('dataset') == 'shizuoka_beach_las' and patch and {'side_m', 'seed'} <= manifest.keys():
        terrain = terrain_for(patch, manifest['side_m'], manifest['seed'])
        expected = inflate(terrain['rock'] | terrain['water'] | terrain['nodata'], RADIUS)
        if np.array_equal(expected, ref['truth_rock']):
            # Legacy map_audit reads NPZ. Keep the evaluation view strictly outside the inputs.
            with tempfile.TemporaryDirectory() as tmp:
                file = Path(tmp)/'map.npz'
                np.savez(file, seen=seen, lethal=lethal, obstacle=detected)
                result.update(map_audit(file, truth, terrain))
    return result


def relaxed_metrics(raw, header, rows, ref):
    # Reuse the endpoint auditor with a plain CSV view of compressed records.
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        write_csv(folder/'endpoint_trajectory.csv', header, rows)
        (folder/'endpoint_masks').symlink_to(raw/'endpoint_masks', target_is_directory=True)
        audit = audit_run(folder, ref['truth_lethal'] if ref is not None else None)
    return dict(relaxed_len_m=audit['relaxed_length_m'], relaxed_applied_plans=audit['applied_plans'],
                relaxed_truth_lethal_len_m=audit['truth_lethal_length_m'] if ref is not None else None)


def handoff_metrics(files, revisions):
    timed = [(number(r['t']), prepare_path(json.loads(r['path']))/RESOLUTION) for r in revisions]
    times = [t for t, _ in timed]
    counts = dict(snapshots=0, snap_handoff_n=0, snap_handoff_with_lethal=0, snap_any_with_lethal=0)
    for file in files:
        with np.load(file, allow_pickle=False) as data:
            t = float(data['sim_time'])
            i = np.searchsorted(times, t, side='right')-1
            if i < 0:
                continue
            revision_t, path = timed[i]
            shape = tuple(data['lethal_shape'])
            lethal = np.unpackbits(data['lethal_bits'], count=int(np.prod(shape))).reshape(shape).astype(bool)
            pose = data['pose'][:2]/RESOLUTION
        cell = tuple(round(v) for v in pose)
        if all(0 <= c < n for c, n in zip(cell, shape)):
            lethal[cell] = False
        _, nearest, _ = nearest_path(pose[None], path)
        remaining = np.vstack([pose, path[nearest[0]+1:] if len(path) > 1 else path])
        cells = np.concatenate([segment_cells(a, b, shape) for a, b in zip(remaining[:-1], remaining[1:])])
        blocked = bool(lethal[tuple(cells.T)].any())
        at_handoff = t-revision_t <= 1
        counts['snapshots'] += 1
        counts['snap_any_with_lethal'] += blocked
        counts['snap_handoff_n'] += at_handoff
        counts['snap_handoff_with_lethal'] += at_handoff and blocked
    return counts


# The schema drives CSV order, field-level missing reasons, and documentation.
IDENTITY = {
    'run': '記録ディレクトリ。作業ディレクトリ内は相対パス。',
    'experiment': '実験名。--experiment または入力ディレクトリ名。',
    'patch': '砂浜。走行メタデータ、raw の直下のフォルダ名の順。',
    'condition': '条件。対応表、run_conditions、<条件>_r<反復番号>、manifest の設定の順。',
    'rep': '反復番号。run_conditions またはフォルダ名。',
    'exit_code': 'exit.txt のプロセス終了コード。0 から完走は推定しない。',
    'target_rtf': '目標倍率。manifest または run_conditions。',
}
MISSION = {
    'recorded_status': 'mission.json の status（なければ manifest の termination）。',
    'status': '転倒、壁時計打ち切り、v2 の傾き反復、合流拒否、地点不足を反映した終了状態。',
    'outcome': 'status に加えて、028b で近くまで・回れない地点が残った完走を partial に分類した結果。',
    'completed': 'outcome が completed なら true。',
    'data_source': 'mission.json の data_source。',
    'goals_reached': '順に指定された最初の5地点のうち、中心軌跡が半径0.3 mの円に入った地点の数。',
    'returned_to_start': '最後の中心位置と指定の出発点の距離が0.3 m以下。',
    'elapsed_s': '走行時間（sim s）。mission の時刻を優先し、欠けた端点は軌跡で補う。',
    'sim_to_wall_ratio': 'mission の開始・終了の sim 時刻差 ÷ wall_elapsed_s。軌跡からは補わない。',
    'record_error': '軌跡の読み取りまたは検証エラー。',
    'online_error': 'mission または manifest のエラー文字列（空は明示的なエラーなし、欠落は欠測）。',
    'no_path_type': '結果が no_path のときの最後の失敗計画の型。空の型は欠測、既知4分類外は other。',
    'board_outcome': 'ボード集計で用いる分類。wall_timeout は静止が記録された場合に stuck とする。',
}
POSE = {
    'sim_end_t': '軌跡の最後の時刻（sim s）。',
    'stationary_tail_s': '最後の位置から5 cm超離れた最後の標本の次から終了まで（sim s）。',
    'rolled_over': '軌跡の roll の絶対値が90°を超えた標本がある。',
    'rollover_t_s': '最初の転倒標本の時刻（sim s）。',
    'rollover_elapsed_s': '軌跡の先頭から転倒標本まで（sim s）。',
    'rollover_x_m': '最初の転倒標本の x（m）。',
    'rollover_y_m': '最初の転倒標本の y（m）。',
    **{f'{axis}_{stat}_deg': f'軌跡の |{axis}| の {stat}（度）。'
       for axis in ('roll', 'pitch') for stat in ('p95', 'max')},
}
DEVIATION = {
    'deviation_mean_m': '有効な経路がある軌跡標本の偏差の平均（m）。',
    'deviation_max_m': '有効な経路がある軌跡標本の偏差の最大（m）。',
    'deviation_p95_m': '有効な経路がある軌跡標本の偏差の95%値（m）。',
    'deviation_samples': '対応する経路のあった軌跡標本数。',
    'deviation_over_075_samples': '偏差が0.75 mを超えた標本数。',
    'deviation_max_t_s': '最大偏差の最初の標本時刻（sim s）。',
    'deviation_max_x_m': '最大偏差の標本の x（m）。',
    'deviation_max_y_m': '最大偏差の標本の y（m）。',
    'deviation_max_path_t_s': '最大偏差の標本に対応する経路版の時刻（sim s）。',
    'deviation_max_curvature_inv_m': '最近線分の端点にある内点のうち、射影点に最も近い頂点とその前後の3点で求めた符号なし Menger 曲率（1/m）。内点がないか退化した場合は空欄。',
}
CELLS = {
    'truth_reference': '照合した評価用NPZのパス。',
    'lethal_cells': '中心軌跡の線分が交差した真値通行不可のユニーク粗格子数。',
    'debris_cells': '中心軌跡の線分が交差した漂着物のユニーク粗格子数。',
    'out_of_bounds_samples': '中心座標が粗格子の中心の範囲外にある軌跡標本数。',
    'truth_lethal_len_m': '真値通行不可マス内の中心軌跡の線分長（m）。',
    'truth_lethal_entries': '真値通行不可マスへの標本ベースの連続進入回数。開始時に内側なら1回。',
    'debris_len_m': '漂着物マス内の中心軌跡の線分長（m）。',
    'debris_entries': '漂着物マスへの標本ベースの連続進入回数。開始時に内側なら1回。',
}
BOXES = {
    'truth_footprints': 'debris_footprints.csv に記録された衝突箱の数。',
    'min_truth_clearance_m': '中心軌跡の全線分と実際の閉じた衝突箱のXY投影との最短距離（m）。箱0個の場合は空欄。',
    'truth_below_radius_s': '真値箱までの中心の距離が厳密に0.5 m未満の時間（sim s、線形補間、重複区間は一度）。',
    'truth_below_radius_entries': '真値箱までの中心の距離が厳密に0.5 m未満の連続区間の数。',
    'min_observed_clearance_m': 'clearance.csv にある細粒度検出障害物への距離の最小標本値（m）。',
}
PLANS = {
    'n_plans': 'plans.csv の計画呼び出し数。',
    'n_replans': 'plans.csv の reason が start_leg 以外の呼び出し数。',
    'replans_lethal_changed': 'plans.csv の lethal_changed 呼び出し数。',
    'failed_plans': 'plans.csv の success=False の数。',
    'last_failure_class': 'plans.csv の最後の失敗呼び出しの failure_class。',
    **{'fail_'+name: f'plans.csv の失敗呼び出しのうち、型が {name} の件数。'
       for name in [*FAILURE_CLASSES, 'unclassified']},
    **{'plan_s_'+stat: f'plans.csv の全呼び出しの実時間 {stat}（s）。' for stat in ('median', 'p95', 'max')},
    'calls_over_1s': '1秒（実時間）を超えた計画呼び出し数。',
    'plan_fail_snapshots': 'diag の plan_fail_*.npz の数。',
}
SAFETY = {
    **{'ev_'+event: f'safety_events.csv の {event} の出現回数。' for event in EVENTS},
    'join_accepted_with_blocked': '合流受理ログの blocked_cells が空でない件数。',
    'stops_replanned_30s': 'off_path・unsafe_tilt の停止から30 sim s以内に safety_replanned があった停止数。',
    'stops_replanned_and_moved_30s': '同じ30 sim sの窓で再計画後の標本が停止位置から1 m超離れた停止数。',
    'stops_detail': '停止ごとの時刻・型・30秒以内の再計画と最大移動・終了までの最大移動のJSON。035と同じ丸め。',
    'stops_then_moved': '035と同じく、終了までの丸め後の最大移動が1 mを超えた停止数。',
    'stops_then_stationary': '035と同じく、終了までの丸め後の最大移動が1 m以下の停止数。',
}
HANDOFF = {
    'snapshots': 'diag_all の周期保存で、有効な経路版が存在した地図の数。',
    'snap_handoff_n': '上記のうち、経路引き渡し後1 sim s以内だった数。',
    'snap_handoff_with_lethal': '引き渡し後1 sim s以内で、残経路が地図の通行不可マス（車体中心のマスを除く）と交差した数。',
    'snap_any_with_lethal': '残経路が地図の通行不可マス（車体中心のマスを除く）と交差した地図の数。',
}
ENDPOINT = {
    **{'stops_'+kind: f'endpoint_status.json の {kind} の地点数。帰着分を含む。'
       for kind in ('arrived', 'nearby', 'unreachable')},
    **{key: f'endpoint_status.json に記録された {key}。'
       for key in ('retries', 'start_applications', 'goal_applications', 'relaxed_cells')},
    'relaxed_len_m': 'endpoint_trajectory.csv と endpoint_masks の有効時刻を合わせた、許可マス内の中心軌跡長（m）。',
    'relaxed_truth_lethal_len_m': '許可マス内の中心軌跡長のうち、真値通行不可マスの長さ（m）。',
    'relaxed_applied_plans': 'endpoint_masks で applied が true の数。',
}
MAP = {
    'map_source': '最終 pointcloud_map.npz、なければ diag の最新周期保存。',
    'map_seen_cells': '保存地図で観測したセル数。',
    'map_lethal_cells': '観測済みで推定が通行不可のセル数。',
    'truth_lethal_cells': '観測済みで真値が通行不可のセル数。',
    'map_fp_cells': '023の誤って通行不可。観測済みで推定は不可、真値は可。',
    'map_fn_cells': '023の見落とし。観測済みで推定は可、真値は不可。',
    'map_fp_steep_cells': '誤って通行不可のうち、推定標高の急斜面の0.5 m膨張内のセル数。',
    'map_fp_obstacle_only_cells': '誤って通行不可のうち、推定急斜面の膨張外のセル数。',
    'map_fp_box_adjacent_cells': '誤って通行不可のうち、真値の漂着物箱の4近傍の数。',
    'clearance_fp_cells': '真値不可に真値急斜面の0.5 m膨張を足した場合の観測済み偽陽性。',
    'clearance_fn_cells': '真値不可に真値急斜面の0.5 m膨張を足した場合の観測済み偽陰性。',
    'detected_obstacle_cells': '観測済みかつ水・欠測域外の推定検出セル数。',
    'truth_obstacle_cells': '観測済みかつ水・欠測域外の真値漂着物セル数。',
    'detector_fp_cells': '観測済みかつ水・欠測域外で、真値漂着物のない検出セル数。',
    'detector_fn_cells': '観測済みかつ水・欠測域外で、検出しなかった真値漂着物セル数。',
    'detector_fp_box_adjacent_cells': '上記の検出偽陽性のうち真値箱の4近傍。',
    'detector_on_unusable_cells': '観測済みで水・欠測域内の検出セル数。',
    **{f'height_abs_error_{stat}_m': f'最終保存地図の観測済みセルの絶対標高誤差の {stat}（m）。'
       for stat in ('median', 'p95')},
}
TIMING = {
    'queue_drops': 'sensor_status.json の全センサー累積キュー落ち数。なければ mission.perception。',
    'sensor_error': 'sensor_status.json または mission.perception のエラー。',
    'cloud_age_sim_max_s': 'probe.csv の点群の古さの最大（sim s）。',
    'cmd_vel_hz_sim': 'probe.csv の running 区間の cmd_count 合計 ÷ sim 時間差（Hz）。最初の標本の区間は除く。',
    'probe_rtf': 'probe.csv の running の最初と最後の sim 時間差 ÷ wall 時間差。',
}
for sensor in ('', *(s+'_' for s in SENSORS)):
    TIMING.update({
        sensor+'map_updates': 'map_updates.csv の status=ok の数。',
        sensor+'map_failed_updates': 'map_updates.csv の status が ok 以外の数。',
        **{sensor+'map_update_s_'+stat: f'map_updates.csv の status=ok の更新処理時間の {stat}（実時間 s）。'
           for stat in ('median', 'p95', 'max')},
        sensor+'update_over_period_count': 'ミッションの開始から終了までに受信した点群の成功更新で、処理時間が0.1 sim s ÷ 実測倍率の実時間周期を超えた件数。',
        sensor+'update_over_period_share': '実測周期を超えた件数 ÷ 同じミッション区間の有効な成功更新数（0–1）。',
    })
    if sensor:
        TIMING[sensor+'queue_drops_last'] = 'センサーの更新ログの最後の累積キュー落ち数。'
        TIMING[sensor+'updates_over_target_period'] = '成功更新時間が0.1 sim s ÷ 目標倍率を超えた件数（035互換）。'

SCHEMA = {**IDENTITY, **MISSION, **POSE, **CELLS, **BOXES, **DEVIATION, **PLANS, **SAFETY,
          **HANDOFF, **ENDPOINT, **MAP, **TIMING}
TEXT = set(IDENTITY) - {'rep', 'exit_code', 'target_rtf'} | {
    'status', 'data_source', 'recorded_status', 'outcome', 'board_outcome', 'no_path_type',
    'online_error', 'record_error', 'truth_reference', 'last_failure_class', 'stops_detail', 'map_source', 'sensor_error'}
NUMERIC = [field for field in SCHEMA if field not in TEXT and field not in ('rep', 'exit_code')]
DATA_ERRORS = (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError, RuntimeError)


def evaluate_run(raw, experiment, conditions=None, reference_root=None):
    row, trial, manifest_path, missing = label_record(raw, experiment, conditions or {})

    def collect(fields, evaluate, reason):
        try:
            values = evaluate()
        except DATA_ERRORS as error:
            values = {}
            reason = str(error)
        row.update(values)
        for field in fields:
            if row.get(field) is None:
                missing[field] = reason

    def table(name, transform, parent=raw, required=()):
        header, rows = read_csv(parent/(name+'.csv'))
        if header is None:
            raise ValueError(name+'.csv(.gz) missing')
        absent = set(required)-set(header)
        if absent:
            raise ValueError(f"{name}.csv: missing columns {', '.join(sorted(absent))}")
        return transform(header, rows)

    def metadata_json(path):
        try:
            record = read_json(path)
            if not isinstance(record, dict):
                raise ValueError('expected a JSON object')
            return record
        except DATA_ERRORS as error:
            missing['@'+path.name] = str(error)
            return {}

    manifest = metadata_json(manifest_path)
    mission = metadata_json(raw/'mission.json')
    endpoint = metadata_json(raw/'endpoint_status.json')
    row['patch'] = row['patch'] or mission.get('patch') or manifest.get('only_patch')
    patch = row['patch']
    case = next((c for c in manifest.get('cases', []) if c.get('patch') == patch), {})
    metadata = next((s for s in manifest.get('scenarios', []) if s.get('patch') == patch), {})
    if not row.get('condition'):
        axes = ('real_time_factor', 'obstacle_clearance', 'sensors', 'online_fixes',
                'obstacle_reference', 'ground_estimate', 'endpoint_policy')
        row['condition'] = ','.join(f'{key}={manifest[key]}' for key in axes if key in manifest) or None
    row['target_rtf'] = manifest.get('real_time_factor')
    settings = trial/'run_conditions.txt'
    if row['target_rtf'] is None and settings.is_file():
        target = re.search(r'\brtf=(?:default\()?([0-9.]+)', settings.read_text())
        if target:
            row['target_rtf'] = number(target[1])

    trace, t, xy = None, np.empty(0), np.empty((0, 2))
    trajectory_error = 'trajectory.csv missing'
    try:
        trace, header, poses = read_trajectory(raw)
        t, xy = trace[:, 0], trace[:, 1:]
        collect(POSE, lambda: pose_metrics(t, xy, header, poses), 'pose field absent or no rollover')
    except DATA_ERRORS as error:
        trajectory_error = str(error)
        row['record_error'] = trajectory_error
        missing.update(dict.fromkeys(POSE, trajectory_error))

    collect(PLANS, lambda: table('plans', plan_metrics), 'required plan field absent or no applicable plan')
    if (raw/'diag').is_dir():
        row['plan_fail_snapshots'] = len(list((raw/'diag').glob('plan_fail_*.npz')))
    collect(SAFETY, lambda: table('safety_events', lambda h, events: safety_metrics(events, t, xy), required=('event', 'sim_time')),
            'trajectory unavailable for stop follow-up')
    collect(MISSION, lambda: recording_status(row, mission, case, endpoint, metadata, t, xy),
            'mission timestamps/status, trajectory or applicable event not recorded')
    if row.get('outcome') == 'no_path' and row.get('last_failure_class'):
        kind = row['last_failure_class']
        row['no_path_type'] = kind if kind in FAILURE_CLASSES else 'other'
    outcome = row.get('outcome')
    if outcome == 'wall_timeout' and row.get('stationary_tail_s', -1) >= mission.get('controller', {}).get('stall_timeout_s', 10):
        row['board_outcome'] = 'stuck'
    elif outcome and outcome not in ('running', 'pending', 'unrun'):
        row['board_outcome'] = outcome if outcome in BOARD else 'other_error'

    ref = None
    reference_error = 'evaluation_reference.npz missing'
    try:
        path, ref = reference_data(raw, reference_root, patch)
        row['truth_reference'] = os.path.relpath(path, Path.cwd())
    except DATA_ERRORS as error:
        reference_error = str(error)
    if trace is not None and ref is not None:
        collect(CELLS, lambda: cell_metrics(xy, ref), 'evaluation grid or pose field absent')
    else:
        missing.update(dict.fromkeys(CELLS, reference_error if ref is None else trajectory_error))

    # Independent logs remain usable when the trajectory or final map is absent.
    if trace is not None:
        collect(DEVIATION, lambda: table('path_revisions', lambda h, r: deviation_metrics(t, xy, r), required=('t', 'path')),
                'no matched path samples or no valid curvature vertex')
        collect(BOXES, lambda: table('debris_footprints', lambda h, r: box_metrics(t, xy, r), required=('xmin', 'ymin', 'xmax', 'ymax')),
                'no saved collision boxes')
    else:
        missing.update(dict.fromkeys((*DEVIATION, *BOXES), trajectory_error))
        collect(('truth_footprints',), lambda: table('debris_footprints', lambda h, r: {'truth_footprints': len(r)}, required=('xmin', 'ymin', 'xmax', 'ymax')),
                'debris footprints unavailable')
    collect(('min_observed_clearance_m',),
            lambda: table('clearance', lambda h, r: {'min_observed_clearance_m':
                        min((number(x['clearance_m']) for x in r if x['clearance_m']), default=None)}, required=('clearance_m',)),
            'no finite clearance sample')

    snaps = sorted((trial/'diag_all').glob('periodic_*.npz'))
    if snaps:
        collect(HANDOFF, lambda: table('path_revisions', lambda h, r: handoff_metrics(snaps, r)),
                'no matched revision')
    else:
        missing.update(dict.fromkeys(HANDOFF, 'diag_all/periodic_*.npz missing'))

    outcomes = [s.get('outcome') for s in endpoint.get('stops', [])]
    row.update({key: endpoint.get(key) for key in ('retries', 'start_applications', 'goal_applications', 'relaxed_cells')})
    if 'stops' in endpoint:
        row.update({'stops_'+kind: outcomes.count(kind) for kind in ('arrived', 'nearby', 'unreachable')})
    if (raw/'endpoint_masks').is_dir():
        collect(('relaxed_len_m', 'relaxed_truth_lethal_len_m', 'relaxed_applied_plans'),
                lambda: table('endpoint_trajectory', lambda h, r: relaxed_metrics(raw, h, r, ref)), reference_error)

    def saved_map():
        fmap, source = final_map(raw)
        if fmap is None:
            raise ValueError('final map and diag periodic snapshots missing')
        row['map_source'] = source
        seen, lethal = fmap['seen'], fmap['lethal']
        if seen.dtype == bool and lethal.dtype == bool and seen.shape == lethal.shape:
            row.update(map_seen_cells=seen.sum(), map_lethal_cells=(seen & lethal).sum())
        if ref is None:
            raise ValueError(reference_error)
        return map_metrics(fmap, source, ref, manifest, patch)

    collect(MAP, saved_map, 'LAS terrain masks not verified, no final map, or no observed heights')

    def updates(header, rows):
        ratio = row.get('sim_to_wall_ratio')
        window = (number(mission['started_t']), number(mission['finished_t'])) if ratio is not None else None
        result = update_metrics(header, rows, ratio, window)
        target = row.get('target_rtf')
        if target is not None and target > 0 and 'update_s' in header and 'status' in header:
            for sensor in SENSORS:
                if sensor+'_map_updates' not in result:
                    continue
                values = [number(r['update_s']) for r in rows if r.get('sensor', 'lidar') == sensor and r['status'] == 'ok']
                if values and None not in values:
                    result[sensor+'_updates_over_target_period'] = sum(v > .1/target for v in values)
        return result

    update_fields = [key for key in TIMING if key not in
                     ('queue_drops', 'sensor_error', 'cloud_age_sim_max_s', 'cmd_vel_hz_sim', 'probe_rtf')]
    collect(update_fields, lambda: table('map_updates', updates),
            'sensor, update durations, counter or applicable time ratio missing')
    perception = metadata_json(raw/'sensor_status.json') or mission.get('perception') or {}
    row.update(queue_drops=perception.get('queue_drops'), sensor_error=perception.get('error'))
    probe = next((p for p in (raw, raw.parent.parent, trial) if (p/'probe.csv').is_file()
                  or (p/'probe.csv.gz').is_file()), raw)
    collect(('cloud_age_sim_max_s', 'cmd_vel_hz_sim', 'probe_rtf'), lambda: table('probe', lambda h, r: probe_metrics(r), probe),
            'no usable probe samples')
    row['missing_reasons'] = json.dumps(
        {**{f: missing.get(f, 'source field or applicable event not recorded')
             for f in SCHEMA if row.get(f) is None}, **{k: v for k, v in missing.items() if k.startswith('@')}},
        ensure_ascii=False, sort_keys=True)
    return row


def write_csv(path, fields, rows):
    with path.open('x', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    groups = {}
    for row in rows:
        key = tuple(row.get(k) for k in ('experiment', 'patch', 'condition'))
        groups.setdefault(key, []).append(row)
    summary, board = [], []
    for (experiment, patch, condition), group in sorted(groups.items(), key=lambda item: tuple(
            str(x or '') for x in item[0])):
        outcomes = [r.get('board_outcome') or 'unknown' for r in group]
        counts = {name: outcomes.count(name) for name in OUTCOMES}
        stats = dict(experiment=experiment, patch=patch, condition=condition, n=len(group), **counts)
        for key in NUMERIC:
            values = [int(r[key]) if isinstance(r[key], (bool, np.bool_)) else r[key]
                      for r in group if r.get(key) is not None]
            if values:
                stats.update({key+'_count': len(values), key+'_min': min(values),
                              key+'_median': np.median(values), key+'_max': max(values)})
            else:
                stats[key+'_count'] = 0
        summary.append(stats)
        board.append({'実験': experiment, '砂浜': patch, '条件': condition,
                      **{ja: counts[en] if counts['unknown'] < len(group) else None for en, ja in BOARD.items()}})
    return summary, board


def definitions():
    lines = ['# 共通走行集計の定義', '',
             'CSV の空欄は欠測または適用外。runs.csv の missing_reasons に列別の理由を JSON で記録する。'
             '0 は、対応する記録で件数や長さがゼロと確認できた場合。分位値は NumPy の線形補間。',
             '', '## runs.csv', '', '| 列 | 定義 |', '|---|---|']
    lines.extend(f'| `{key}` | {definition} |' for key, definition in SCHEMA.items())
    lines.extend([
        '| `missing_reasons` | 空欄の理由の JSON。@ で始まるキーは JSON ファイル単位のエラー。 |', '',
        '偏差は、時刻が標本以下の最新 path_revisions の折れ線全体への最短距離。版の切替時刻が同じ場合は最後の版を使用する。'
        '往復や経路の交差では、残経路を測る追従器内部の偏差と異なりうる。035・037 の runs.csv の最大・平均と同じ定義。',
        '曲率は最近線分につながる局所の3点から求め、符号は付けない。等距離はログ順、線分順、頂点順を優先する。',
        '停止位置は停止時刻以降の最初の姿勢標本。停止通知は safety_events の実測を数え、0.75 m の標本超過数からは推定しない。',
        '', '真値の粗格子では030・035と同じく truth_rock & ~prior_rock を漂着物マスとする。'
        'ユニーク数には線分と閉じた格子の交差を数える。進入回数は粗格子に丸めた標本の連続区間を数えるため、'
        '標本の間だけを横切ると長さが正でも回数が0になる。037の個別接触分析では丸めと範囲外の扱いが異なる。',
        '真値箱の時間と回数には、0.5 m の開いた近傍と区分線形の中心軌跡との交差を使う。'
        '車体接触を物理的に測った値ではない。箱CSVがない場合、粗格子で代用せず箱の列を空欄にする。',
        '', '検出地図までの距離は、その時点のマスを使った診断標本の最小値。真値箱との連続軌跡の最小値とは集計方法が異なる。',
        'センサー列がない更新ログは旧式の単一 LiDAR として扱う。センサー列がある場合、行がないセンサーの列は空欄。'
        '実測倍率による周期超過と、035 の目標倍率による超過は別の列。',
        '生ログに軌跡がない完走は、mission の記録済み状態を集計する。到達地点数・帰着・転倒の軌跡による再検証は空欄。',
        '壁時計打ち切りは、停止時間が記録上の stall_timeout_s（従来の既定10 sim s）以上のとき、ボード上で「止まったまま」。'
        'runs.csv の outcome には旧集計と同じ wall_timeout が残る。',
        '観測地図は記録の評価用真値と比較する。検出誤りの内訳は LAS の元地形から再現した真値障害物マスクの膨張が'
        '保存真値と一致する場合のみ算出する。--reference-root は同じ走行真値を別に保存した場合にだけ指定する。',
        '', '## summary.csv', '',
        '`experiment,patch,condition` ごとの `n` とボード分類の件数。'
        '`other_error` は既知のその他終了、`unknown` は結果が判定できない走行。'
        '数値列の `_count` は有効値の数、`_min/_median/_max` は有効値の最小・中央値・最大。'
        '真偽値は真を1、偽を0として要約する。有効値がない統計は空欄。',
        '', '## outcomes_board.csv', '',
        '実験・砂浜・条件と、完走・一部・経路なし・止まったまま・転倒の各件数。その他・未確定の走行数は summary.csv で確認できる。',
        '同一群で結果が一件も分からないときは5つの件数を空欄とする。', ''])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path, help='raw run directories or containing roots')
    parser.add_argument('--out', required=True, type=Path, help='separate output directory')
    parser.add_argument('--experiment', help='label for all input roots (default: directory name)')
    parser.add_argument('--conditions', type=Path, help='CSV with path,condition; paths relative to that CSV')
    parser.add_argument('--reference-root', type=Path, help='explicit reference directory containing <patch>/evaluation_reference.npz')
    args = parser.parse_args(argv)
    try:
        conditions = read_conditions(args.conditions.resolve() if args.conditions else None)
        inputs = [path.resolve() for path in args.inputs]
        dest = args.out.resolve()
        if any(not path.is_dir() for path in inputs):
            raise ValueError('input must be an existing directory')
        if any(dest.is_relative_to(path) for path in inputs):
            raise ValueError('--out must be outside the input record directories')
        output_files = ('runs.csv', 'summary.csv', 'outcomes_board.csv', 'definitions_ja.md')
        if any((dest/name).exists() for name in output_files):
            raise FileExistsError(f'output files already exist in {dest}')
        rows, seen = [], set()
        for path in inputs:
            found = list(discover(path))
            if not found:
                raise ValueError(f'no run records in {path}')
            for run in found:
                if run in seen:
                    continue
                seen.add(run)
                rows.append(evaluate_run(run, args.experiment or path.name, conditions, args.reference_root))
        summary, board = summarize(rows)
        dest.mkdir(parents=True, exist_ok=True)
        write_csv(dest/'runs.csv', [*SCHEMA, 'missing_reasons'], rows)
        write_csv(dest/'summary.csv', ['experiment', 'patch', 'condition', 'n', *OUTCOMES,
                                      *(f'{key}_{stat}' for key in NUMERIC
                                        for stat in ('count', 'min', 'median', 'max'))], summary)
        write_csv(dest/'outcomes_board.csv', ['実験', '砂浜', '条件', *BOARD.values()], board)
        with (dest/'definitions_ja.md').open('x', encoding='utf-8') as stream:
            stream.write(definitions())
        for group in summary:
            counts = ' '.join(f'{k}={group[k]}' for k in OUTCOMES if group[k])
            print(f"{group['experiment']} {group['patch'] or '-'} {group['condition'] or '-'} n={group['n']} {counts}")
        print(f'{len(rows)} runs -> {dest}')
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
