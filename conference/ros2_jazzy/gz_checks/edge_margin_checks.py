"""Task024: filter waypoint candidates once, reuse equal tours, rerun changed tours."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.real_beach import build_real, list_patches
from tapp.tour import sample_waypoints
from tapp.online_mission import ordered_tour, run_fixed_mission
from tapp.footprint import blocked_endpoints
from ros2_jazzy.gz_checks.online_batch_runtime import planning_map, case_metadata
from ros2_jazzy.gz_checks.online_batch_checks import save_manifest
from ros2_jazzy.gz_checks.lidar_checks import verify_inputs
from ros2_jazzy.gz_checks.lidar_map import matched_task022_maps, fine_protocol

MARGIN_M = 10.
PLANNER = 'TA*-S+inflate'
MODES = ('fixed', 'online', 'lidar', 'fine')
ARCHIVES = dict(fixed='results/gazebo_online/physical_run', online='results/gazebo_online/physical_run',
                lidar='results/gazebo_lidar/physical_10', fine='results/lidar_fine/physical_10')


def edge_distance_m(point, shape):
    """Distance to the outermost grid centres (0..199.5m on a 400-cell map)."""
    point = np.asarray(point)
    return float(np.minimum(point, np.asarray(shape)-1-point).min()*RESOLUTION)


def archived_metadata():
    original = json.loads((ROOT/ARCHIVES['fixed']/'manifest.json').read_text())['scenarios']
    expected = [r['name'] for r in list_patches('test', dataset='shizuoka_beach_las')[:10]]
    if [s['patch'] for s in original] != expected:
        raise ValueError('expected the original first ten LAS test patches')
    for path in set(ARCHIVES.values()):
        other = json.loads((ROOT/path/'manifest.json').read_text())['scenarios']
        if other != original:
            raise ValueError('task021/022/023 endpoints or tour order differ')
    return original


def build_cohort():
    metadata, reruns, audit = [], [], []
    for old in archived_metadata():
        patch = old['patch']
        truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
        clean = build_real(patch, 200, 0, dataset='shizuoka_beach_las')
        truth, clean, reference = matched_task022_maps(patch, truth, clean)
        inputs = verify_inputs(patch, old, truth, clean)
        if list(truth['start']) != old['start']:
            raise ValueError('never move the archived start: '+patch)
        seed = [0, 3000, 200, truth['patch_index']]
        start_margin = edge_distance_m(truth['start'], truth['tmap'].shape)
        eligible = start_margin >= MARGIN_M
        draw, points = [], deepcopy(old['points'])
        if eligible:
            original = sample_waypoints(truth, 12, np.random.SeedSequence(seed))[:5]
            if [list(p) for p in original] != old['points']:
                raise ValueError('the default sampler changed task021 points: '+patch)
            draw = sample_waypoints(truth, 12, np.random.SeedSequence(seed), edge_margin_m=MARGIN_M)
            points = [list(p) for p in draw[:5]]
        changed = points != old['points']
        meta = deepcopy(old)
        if changed:
            meta.update(points=points, initial_path=[], fixed_plan_times=[])
        if not eligible:
            meta.update(planning_status='excluded_start', order=[], stops=[])
        elif changed:
            try:
                tour = ordered_tour(clean['tmap'], truth['start'], points)
            except ValueError:
                tour = dict(order=[], stops=[])
            prior_tm, truth_tm = planning_map(clean, PLANNER), planning_map(truth, PLANNER)
            bt = blocked_endpoints(truth_tm, truth['start'], tour['stops'])
            bp = blocked_endpoints(prior_tm, truth['start'], tour['stops'])
            fixed = run_fixed_mission(prior_tm, truth['start'], tour['stops']) if tour['stops'] and not (bt or bp) else None
            status = 'blocked_endpoint' if bt or bp else ('planned' if fixed and fixed['success'] else 'no_path')
            sc = dict(patch=patch, patch_index=truth['patch_index'], planner=PLANNER, truth=truth, clean=clean,
                      truth_tm=truth_tm, prior_tm=prior_tm, start=old['start'], points=points,
                      tour=tour, fixed=fixed, planning_status=status, blocked_truth=bt, blocked_prior=bp)
            meta = case_metadata(sc)
            reruns.append(sc)
        metadata.append(meta)
        audit.append(dict(patch=patch, shape=list(truth['tmap'].shape), seed=seed,
                          start=old['start'], start_edge_m=start_margin, eligible=eligible,
                          points_changed=changed, old_points=old['points'], new_points=points,
                          old_edge_m=[edge_distance_m(p, truth['tmap'].shape) for p in old['points']],
                          new_edge_m=[edge_distance_m(p, truth['tmap'].shape) for p in points],
                          sampled_twelve=[list(p) for p in draw], world_reference=reference, input_audit=inputs))
    return dict(scenarios=metadata, reruns=reruns, waypoint_audit=audit)


def prepare_cases(output, *, cohort=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output/'manifest.json').exists():
        raise FileExistsError('choose a new output; original and new recordings are never overwritten')
    protocol = fine_protocol()
    cohort = build_cohort() if cohort is None else cohort
    cases = []
    for meta, audit in zip(cohort['scenarios'], cohort['waypoint_audit']):
        action = 'excluded' if not audit['eligible'] else ('rerun' if audit['points_changed'] else 'reused')
        for mode in MODES:
            cases.append(dict(patch=meta['patch'], mode=mode, record_origin=action,
                              planning_status=meta['planning_status'], run_folder=None,
                              archive_csv=ARCHIVES[mode]+'/runs.csv' if action == 'reused' else None,
                              archive_mode=mode, termination=None, error=''))
    sources = {}
    for archive in sorted(set(ARCHIVES.values())):
        for filename in ['manifest.json', 'runs.csv']:
            path = ROOT/archive/filename
            sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(task=24, dataset='shizuoka_beach_las', split='test', side_m=200, seed=0,
                    planner=PLANNER, footprint_radius_m=.5, sense_radius_m=10., edge_margin_m=MARGIN_M,
                    edge_definition='outermost grid centres: [0,199.5]m on each axis; inclusive 10m',
                    selection='same permutation; reject candidates below margin; draw 12, use first 5',
                    execution='not_started', world_max_pixels=4097,
                    world_input='task022 actual-run elevation and unchanged raw masks for all four methods',
                    controls=dict(real_time_factor=1., terrain_visual='heightmap', terrain_collision='heightmap'),
                    lidar=dict(real_time_factor=protocol['real_time_factor'], stale_timeout_s=protocol['stale_timeout_s'],
                               terrain_visual=protocol['terrain_visual'], terrain_collision='heightmap',
                               sensor_source='results/gazebo_lidar/physical_10/manifest.json'),
                    archive_sha256=sources, scenarios=cohort['scenarios'], waypoint_audit=cohort['waypoint_audit'], cases=cases)
    save_manifest(output, manifest)
    return manifest, cohort


def run_checks(output):
    from ros2_jazzy.gz_checks import online_batch_checks, lidar_checks
    output = Path(output).resolve()
    manifest, cohort = prepare_cases(output)
    manifest['execution'] = 'started'
    save_manifest(output, manifest)
    selected = [s['patch'] for s in cohort['reruns']]
    jobs = [('controls', ('fixed', 'online')), ('lidar', ('lidar',)), ('fine', ('fine',))]
    errors = []
    for name, modes in jobs:
        child = output/'physical'/name
        try:
            if selected:
                if name == 'controls':
                    online_batch_checks.run_checks(child, PLANNER, scenarios=cohort['reruns'], finalize_report=False)
                else:
                    # Both LiDAR methods keep the task022/023 physical settings.
                    if float(os.environ.get('THESIS_REAL_TIME_FACTOR', '.3')) != .3 or float(os.environ.get('THESIS_STALE_TIMEOUT_S', '1.')) != 1.:
                        raise ValueError('task024 fixes LiDAR real_time_factor=0.3 and stale_timeout_s=1.0')
                    os.environ['THESIS_REAL_TIME_FACTOR'], os.environ['THESIS_STALE_TIMEOUT_S'] = '.3', '1.0'
                    lidar_checks.run_checks(child, patch_count=10, map_method='fine' if name == 'fine' else 'coarse',
                                            scenarios=cohort['scenarios'], selected_patches=selected,
                                            matched_world=True, finalize_report=False)
        except Exception as exc:
            errors.append(name+': '+type(exc).__name__+': '+str(exc))
            for case in manifest['cases']:
                if case['record_origin'] == 'rerun' and case['mode'] in modes:
                    case['error'] = errors[-1]
        finally:
            if (child/'manifest.json').exists():
                recorded = json.loads((child/'manifest.json').read_text())['cases']
                for case in manifest['cases']:
                    if case['record_origin'] != 'rerun' or case['mode'] not in modes:
                        continue
                    matches = [c for c in recorded if c['patch'] == case['patch'] and
                               (name != 'controls' or c['mode'] == case['mode'])]
                    if len(matches) != 1:
                        raise ValueError('child cohort differs from requested tours')
                    c = matches[0]
                    if c.get('run_folder'):
                        case['run_folder'] = str((child/c['run_folder']).relative_to(output))
                    case['termination'] = c.get('termination')
                    case['error'] = c.get('error', '') or (case['error'] if not c.get('run_folder') else '')
            save_manifest(output, manifest)
    manifest.update(execution='finished_with_errors' if errors else 'finished', job_errors=errors)
    save_manifest(output, manifest)
    from experiments.edge_margin_report import summarize
    summarize(output)
    if errors:
        raise RuntimeError('; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results/edge_margin')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.prepare_only:
        prepare_cases(args.output)
        from experiments.edge_margin_report import summarize
        summarize(args.output)
    else:
        run_checks(args.output)


if __name__ == '__main__':
    main()
