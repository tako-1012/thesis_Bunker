"""Task023 four-way cached/recorded comparisons and observed-cell map audits."""

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation, label, find_objects

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.real_beach import build_real
from tapp.config import Robot
from tapp.traversability import slope_deg, inflate
from experiments.gz_online_batch_report import analyze_record, PHYSICAL
from experiments.gz_lidar_report import map_quality, QUALITY
from ros2_jazzy.gz_checks.lidar_checks import verify_inputs
from ros2_jazzy.gz_checks.online_batch_runtime import map_signature

BASELINE = ROOT/'results/gazebo_lidar/physical_10'
MODES = ('fixed', 'online', 'lidar', 'fine')
MAP_FIELDS = ['map_seen_cells', 'map_lethal_cells', 'truth_lethal_cells', 'map_fp_cells', 'map_fn_cells',
              'map_fp_box_adjacent_cells', 'clearance_fp_cells', 'clearance_fn_cells',
              'detected_obstacle_cells', 'truth_obstacle_cells', 'detector_fp_cells', 'detector_fn_cells',
              'detector_fp_box_adjacent_cells', 'detector_on_unusable_cells']


def box_footprints(raw_obstacle):
    """Same connected-component bounding rectangles as export_gazebo's boxes."""
    boxes = np.zeros(raw_obstacle.shape, bool)
    for region in find_objects(label(raw_obstacle)[0]):
        if region is not None:
            boxes[region] = True
    return boxes


def map_audit(path, truth_tm, terrain):
    result = dict.fromkeys(MAP_FIELDS)
    path = Path(path)
    if not path.exists():
        return result
    with np.load(path, allow_pickle=False) as data:
        seen, lethal, detected = data['seen'], data['lethal'], data['obstacle']
        for value in [seen, lethal, detected]:
            if value.dtype != bool or value.shape != truth_tm.shape:
                raise ValueError('invalid stored map mask')
        raw = terrain['rock']
        unusable = terrain['water'] | terrain['nodata']
        boxes = box_footprints(raw)
        cross = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
        adjacent = binary_dilation(boxes, structure=cross) & ~boxes
        fp = seen & lethal & ~truth_tm.lethal
        fn = seen & ~lethal & truth_tm.lethal
        eligible = seen & ~unusable
        detector_fp = eligible & detected & ~raw
        detector_fn = eligible & ~detected & raw
        clearance = truth_tm.lethal | inflate(slope_deg(truth_tm.elev) > Robot().max_slope_deg, Robot().footprint_radius)
        result.update(map_seen_cells=int(seen.sum()), map_lethal_cells=int((seen & lethal).sum()),
                      truth_lethal_cells=int((seen & truth_tm.lethal).sum()),
                      map_fp_cells=int(fp.sum()), map_fn_cells=int(fn.sum()),
                      map_fp_box_adjacent_cells=int((fp & adjacent).sum()),
                      clearance_fp_cells=int((seen & lethal & ~clearance).sum()),
                      clearance_fn_cells=int((seen & ~lethal & clearance).sum()),
                      detected_obstacle_cells=int((eligible & detected).sum()),
                      truth_obstacle_cells=int((eligible & raw).sum()),
                      detector_fp_cells=int(detector_fp.sum()), detector_fn_cells=int(detector_fn.sum()),
                      detector_fp_box_adjacent_cells=int((detector_fp & adjacent).sum()),
                      detector_on_unusable_cells=int((seen & unusable & detected).sum()))
    return result


def evaluation_maps(folder, truth, prior, case):
    """Read actual-run reference bits when available; do not edit old snapshots."""
    path = Path(folder)/'evaluation_reference.npz'
    if not path.exists():
        return truth, prior, False
    loaded = []
    with np.load(path, allow_pickle=False) as data:
        for name in ['truth', 'prior']:
            z, rock, lethal = (data[name+'_'+field].copy() for field in ['elev', 'rock', 'lethal'])
            if z.shape != truth['tmap'].shape or not np.isfinite(z).all() or any(v.shape != z.shape or v.dtype != bool for v in [rock, lethal]):
                raise ValueError('invalid evaluation reference')
            loaded.append(dict(tmap=SimpleNamespace(elev=z, rock=rock, lethal=lethal, shape=z.shape)))
    if case.get('input_audit'):
        for name, sc in zip(['truth', 'prior'], loaded):
            if map_signature(sc) != case['input_audit']['signatures'][name]:
                raise ValueError('evaluation reference checksum mismatch')
    return *loaded, True


def summary_table(data):
    rows = []
    for mode in MODES:
        group = data[data['mode'] == mode]
        measured = group[group.data_source.eq('gazebo')]
        row = dict(mode=mode, execution='記録あり' if len(measured) else '未実行',
                   scheduled=len(group), executed=len(measured), unexecuted=len(group)-len(measured))
        for status in ['completed', 'stuck', 'rollover', 'no_path', 'timeout', 'runtime_error', 'incomplete_waypoints']:
            row[status] = int(measured.status.eq(status).sum()) if len(measured) else None
        contacts = pd.to_numeric(measured.debris_cells).dropna()
        row['debris_audited_runs'] = len(contacts)
        row['debris_touching_runs'] = int((contacts > 0).sum()) if len(contacts) else None
        for field in MAP_FIELDS+['map_update_s_median', 'map_update_s_p95', 'map_update_s_max']:
            values = pd.to_numeric(measured[field]).dropna()
            row[field+'_median'] = values.median() if len(values) else None
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(output):
    output = Path(output).resolve()
    manifest = json.loads((output/'manifest.json').read_text())
    archived = json.loads((BASELINE/'manifest.json').read_text())
    if manifest.get('map_method') != 'fine' or manifest['scenarios'] != archived['scenarios']:
        raise ValueError('expected the unchanged task022 cohort with --map fine')
    if (manifest['real_time_factor'], manifest['stale_timeout_s'], manifest['terrain_visual']) != (.3, 1., 'triangle_mesh'):
        raise ValueError('fine run conditions differ from task022')
    if len(manifest['cases']) != 10 or len({c['patch'] for c in manifest['cases']}) != 10:
        raise ValueError('retain all ten scenarios, including unexecuted cases')
    old = pd.read_csv(BASELINE/'runs.csv', float_precision='round_trip')
    if len(old) != 30 or set(old['mode']) != {'fixed', 'online', 'lidar'}:
        raise ValueError('expected thirty cached task021/022 rows')
    for field in MAP_FIELDS:
        old[field] = None
    metadata = {s['patch']: s for s in manifest['scenarios']}
    old_cases = {c['patch']: c for c in archived['cases']}
    rows, inputs = [], []
    for case in manifest['cases']:
        patch = case['patch']
        meta = metadata[patch]
        truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
        prior = build_real(patch, 200, 0, dataset='shizuoka_beach_las')
        inputs.append(verify_inputs(patch, meta, truth, prior))
        terrain = truth['terrain']
        previous_case = old_cases[patch]
        if previous_case.get('run_folder'):
            previous_folder = BASELINE/previous_case['run_folder']
            old_truth, _, _ = evaluation_maps(previous_folder, truth, prior, previous_case)
            metrics = map_audit(previous_folder/'pointcloud_map.npz', old_truth['tmap'], terrain)
            index = old.index[(old.patch == patch) & (old['mode'] == 'lidar')]
            if len(index) != 1:
                raise ValueError('cached LiDAR row is not unique')
            for field, value in metrics.items():
                old.loc[index, field] = value
        row = dict(patch=patch, mode='fine', planner='TA*-S+inflate', selected=case['selected'],
                   planning_status=case['planning_status'], status='未実行', recorded_status=None,
                   completed=None, data_source=None, error=case.get('error', ''), sensor_error=None,
                   **dict.fromkeys(PHYSICAL+QUALITY+MAP_FIELDS))
        if case.get('run_folder'):
            folder = output/case['run_folder']
            try:
                new_truth, new_prior, exact = evaluation_maps(folder, truth, prior, case)
                measured, _ = analyze_record(folder, meta, new_truth, new_prior)
                row.update(measured)
            except (ValueError, OSError, KeyError) as exc:
                row.update(status='記録不完全', error=type(exc).__name__+': '+str(exc))
            else:
                try:
                    row.update(map_quality(folder, new_truth if exact else None))
                    row.update(map_audit(folder/'pointcloud_map.npz', new_truth['tmap'], terrain))
                except (ValueError, OSError, KeyError) as exc:
                    row['error'] += '; mapping audit: '+type(exc).__name__+': '+str(exc)
        rows.append(row)
    data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
    summary = summary_table(data)
    data.to_csv(output/'runs.csv', index=False)
    summary.to_csv(output/'summary.csv', index=False)
    (output/'input_audit.json').write_text(json.dumps(inputs, indent=2)+'\n')
    display = ['patch', 'mode', 'status', 'map_seen_cells', 'map_lethal_cells', 'truth_lethal_cells',
               'map_fp_cells', 'map_fn_cells', 'map_fp_box_adjacent_cells', 'detected_obstacle_cells',
               'detector_fp_cells', 'detector_fn_cells', 'detector_fp_box_adjacent_cells',
               'map_update_s_median', 'map_update_s_p95', 'map_update_s_max', 'debris_cells']
    stream = io.StringIO()
    with redirect_stdout(stream):
        print('Task023: fixed / perfect R10 / task022 LiDAR / fine-grid LiDAR; identical ten-beach cohort.')
        print('First three methods are cached measurements. New fine-grid physical outcomes are 未実行 when missing.')
        print(data[display].to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nCounts and per-run metric medians; all contact counts use recorded centre trajectories.')
        print(summary.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('Map FP/FN use unique seen cells against original truth lethal; CSV also reports same-steep-clearance FP/FN.')
        print('Detector FP/FN compare uninflated detections to raw obstacles, excluding water/nodata; these differ from final lethal FP/FN.')
        print('Box adjacency is one four-connected cell outside the actual exported component bounding rectangles.')
        print('Missing task021 map snapshots are unrecorded, not zero. New fine-grid values are not inferred from fixtures.')
        print('Grid=0.1m, height threshold=0.3m, cluster=3, radius=0.5m were fixed in advance; no tuning or hypothesis tests.')
    log = stream.getvalue()
    (output/'lidar_fine_log.txt').write_text(log)
    print(log, end='')
    return data, summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT/'results/lidar_fine')
    summarize(parser.parse_args().output)
