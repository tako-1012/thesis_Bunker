"""Task024 default-byte parity, margin-only sampling and mixed record provenance."""

from contextlib import redirect_stdout
from copy import deepcopy
import csv
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd

from tapp.config import RESOLUTION
from tapp.planners import astar
from tapp.real_beach import build_real
from tapp.tour import sample_waypoints
from tapp.traversability import TraversabilityMap
from tapp.run_log import FIELDS
from ros2_jazzy.gz_checks import edge_margin_checks as checks
from ros2_jazzy.gz_checks.online_batch_runtime import case_metadata
from experiments import edge_margin_report as report

ROOT = Path(__file__).resolve().parents[1]


def test_sampling():
    previous = json.loads((ROOT/'results/edge_margin/verification/legacy_waypoints.json').read_text())
    for old in previous:
        truth = build_real(old['patch'], 200, 0, debris=True, dataset='shizuoka_beach_las')
        for kwargs in [{}, dict(edge_margin_m=0)]:
            points = sample_waypoints(truth, 12, np.random.SeedSequence(old['seed']), **kwargs)
            assert json.dumps(points, separators=(',', ':')) == old['json_bytes']
        points = sample_waypoints(truth, 12, np.random.SeedSequence(old['seed']), edge_margin_m=10)
        chosen = [truth['start']]
        for p in points:
            # Independently check metre coordinates against the grid's extrema.
            x, y = np.asarray(p)*RESOLUTION
            xmax, ymax = (np.asarray(truth['tmap'].shape)-1)*RESOLUTION
            assert min(x, y, xmax-x, ymax-y) >= 10
            assert all(math.dist(p, q)*RESOLUTION >= 5 for q in chosen)
            assert not truth['tmap'].lethal[p]
            assert astar(truth['tmap'].lethal, truth['start'], p)['success']
            chosen.append(p)
    tm = TraversabilityMap(np.zeros((11, 11)), np.zeros((11, 11), bool))
    sc = dict(tmap=tm, start=(0, 0))
    assert sample_waypoints(sc, 0, 100) == []
    for margin in [-1, np.inf, np.nan]:
        try:
            sample_waypoints(sc, 1, 100, edge_margin_m=margin)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid margin accepted')
    # Exactly the fixed margin is allowed; the start itself is not snapped.
    tm = TraversabilityMap(np.zeros((41, 41)), np.zeros((41, 41), bool))
    points = sample_waypoints(dict(tmap=tm, start=(0, 0)), 1, 100, edge_margin_m=10)
    assert points == [(20, 20)]
    print('sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability')
    print('sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed')


def test_cohort():
    cohort = checks.build_cohort()
    old = {s['patch']: s for s in checks.archived_metadata()}
    expected = {'08OB86_00294', '08OB87_-0706', '08OB88_01832', '08OB89_00152', '08OB89_-0347'}
    changed = {a['patch'] for a in cohort['waypoint_audit'] if a['points_changed']}
    assert changed == expected
    assert {s['patch'] for s in cohort['reruns']} == changed
    for meta, audit in zip(cohort['scenarios'], cohort['waypoint_audit']):
        assert meta['start'] == old[meta['patch']]['start'] == audit['start']
        assert audit['start_edge_m'] >= 10 and min(audit['new_edge_m']) >= 10
        assert audit['eligible']
        if not audit['points_changed']:
            assert meta == old[meta['patch']]  # All endpoints/order/path, not just a point count.
        else:
            sc = next(s for s in cohort['reruns'] if s['patch'] == meta['patch'])
            assert case_metadata(sc) == meta
            reference = ROOT/audit['world_reference']
            with np.load(reference, allow_pickle=False) as arrays:
                assert sc['truth']['tmap'].elev.tobytes() == arrays['truth_elev'].tobytes()
                assert sc['clean']['tmap'].elev.tobytes() == arrays['prior_elev'].tobytes()
    print('cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained', flush=True)
    return cohort


def test_excluded_start():
    sc = dict(tmap=TraversabilityMap(np.zeros((100, 100)), np.zeros((100, 100), bool)), start=(1, 50), patch_index=100)
    seed = [0, 3000, 200, 100]
    points = sample_waypoints(sc, 12, np.random.SeedSequence(seed))[:5]
    old = dict(patch='synthetic_start_fixture', start=[1, 50], points=[list(p) for p in points], planning_status='planned')
    with patch.object(checks, 'archived_metadata', return_value=[old]), \
         patch.object(checks, 'build_real', return_value=sc), \
         patch.object(checks, 'matched_task022_maps', return_value=(sc, sc, 'synthetic_reference')), \
         patch.object(checks, 'verify_inputs', return_value={}), \
         patch.object(checks, 'sample_waypoints', side_effect=AssertionError('excluded start must not sample targets')), \
         patch.object(checks, 'ordered_tour', side_effect=AssertionError('excluded start must not be planned')):
        cohort = checks.build_cohort()
    assert cohort['reruns'] == []
    assert cohort['waypoint_audit'][0]['eligible'] is False
    assert cohort['scenarios'][0]['start'] == [1, 50]
    assert cohort['scenarios'][0]['planning_status'] == 'excluded_start'
    print('synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it')


def write_record(folder, metadata, mode):
    folder.mkdir(parents=True)
    cells = [metadata['start']]+metadata['stops']
    (folder/'mission.json').write_text(json.dumps(dict(status='completed', data_source='gazebo',
                                                     started_t=0, finished_t=len(cells)-1)))
    with (folder/'trajectory.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for t, p in enumerate(cells):
            writer.writerow(dict(zip(FIELDS, [t, p[0]*RESOLUTION, p[1]*RESOLUTION, 0, 0, 0, 0, 0, 0])))
    (folder/'plans.csv').write_text('reason,plan_time_s\nstart_leg,0.2\nnew_obstacle,0.4\n')
    if mode in ('lidar', 'fine'):
        (folder/'map_updates.csv').write_text('status,update_s\nok,0.1\nok,0.2\n')


def test_reports(cohort):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest, _ = checks.prepare_cases(root, cohort=cohort)
        original_bytes = {name: (ROOT/name).read_bytes() for name in manifest['archive_sha256']}
        with redirect_stdout(io.StringIO()):
            data, summary, _ = report.summarize(root)
        assert len(data) == 40 and len(summary) == 4
        for mode in checks.MODES:
            assert summary.set_index('mode').loc[mode, 'reused'] == 5
            assert summary.set_index('mode').loc[mode, 'rerun_requested'] == 5
        for case in manifest['cases']:
            row = data[(data.patch == case['patch']) & (data['mode'] == case['mode'])].iloc[0]
            if case['record_origin'] == 'reused':
                cached = report.cached_row(case)
                fields = [f for f in report.PHYSICAL+report.QUALITY if f in cached]
                pd.testing.assert_series_equal(row[fields], cached[fields], check_names=False, check_dtype=False, check_exact=True)
            else:
                assert row['status'] == '未実行' and pd.isna(row['completed']) and pd.isna(row['map_update_s_max'])
        assert not list(root.glob('trajectory_*.png'))
        # Add synthetic records for one changed beach, retaining real cached
        # rows for unchanged beaches. These are test inputs, not new trials.
        patch_name = cohort['reruns'][0]['patch']
        metadata = next(s for s in manifest['scenarios'] if s['patch'] == patch_name)
        for case in manifest['cases']:
            if case['patch'] == patch_name:
                case['run_folder'] = 'raw/'+case['mode']
                write_record(root/case['run_folder'], metadata, case['mode'])
        checks.save_manifest(root, manifest)
        tm = TraversabilityMap(np.zeros((400, 400)), np.zeros((400, 400), bool))
        maps = (dict(tmap=tm), dict(tmap=tm))
        with patch.object(report, 'load_maps', return_value=maps), redirect_stdout(io.StringIO()):
            data, summary, pairs = report.summarize(root, figures=False)
        measured = data[data.patch == patch_name]
        assert measured.record_origin.eq('rerun').all() and measured.execution.eq('実走').all()
        assert measured.completed.eq(True).all() and measured.goals_reached.eq(5).all()
        assert measured.lethal_cells.eq(0).all() and measured.debris_cells.eq(0).all()
        assert measured[measured['mode'].isin(['lidar', 'fine'])].map_update_s_max.eq(.2).all()
        assert summary.executed.eq(6).all() and summary.rerun_recorded.eq(1).all()
        assert not any('energy' in name.lower() for name in data.columns)
        assert not any('p_value' in name.lower() for name in pairs.columns)
        assert (pairs[pairs.metric == 'goals_reached'].dropna().delta_median == 0).all()
        assert all((ROOT/name).read_bytes() == content for name, content in original_bytes.items())
        # A manifest may not relabel changed points as an archived tour.
        manifest['cases'][0]['record_origin'] = 'reused'
        checks.save_manifest(root, manifest)
        try:
            with redirect_stdout(io.StringIO()):
                report.summarize(root)
        except ValueError:
            pass
        else:
            raise AssertionError('a changed tour was reused')
    print('report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance')


def test_dispatch(cohort):
    calls = []
    def controls(output, planner, **kwargs):
        assert planner == checks.PLANNER and kwargs['finalize_report'] is False
        actual = kwargs['scenarios']
        calls.append(('controls', {s['patch'] for s in actual}))
        Path(output).mkdir(parents=True)
        rows = [dict(patch=s['patch'], mode=m, run_folder=None) for s in actual for m in ('fixed', 'online')]
        checks.save_manifest(output, dict(cases=rows))
    def lidar(output, **kwargs):
        assert kwargs['finalize_report'] is False and kwargs['matched_world'] is True
        assert kwargs['scenarios'] == cohort['scenarios']
        assert kwargs['patch_count'] == 10
        calls.append((kwargs['map_method'], set(kwargs['selected_patches'])))
        Path(output).mkdir(parents=True)
        checks.save_manifest(output, dict(cases=[dict(patch=s['patch'], mode='lidar', run_folder=None) for s in kwargs['scenarios']]))
    with tempfile.TemporaryDirectory() as temporary, \
         patch.object(checks, 'build_cohort', return_value=cohort), \
         patch('ros2_jazzy.gz_checks.online_batch_checks.run_checks', side_effect=controls), \
         patch('ros2_jazzy.gz_checks.lidar_checks.run_checks', side_effect=lidar), \
         patch.dict(os.environ, {'THESIS_REAL_TIME_FACTOR': '.3', 'THESIS_STALE_TIMEOUT_S': '1.0'}), \
         redirect_stdout(io.StringIO()):
        checks.run_checks(Path(temporary)/'output')
    expected = {a['patch'] for a in cohort['waypoint_audit'] if a['points_changed'] and a['eligible']}
    assert [name for name, _ in calls] == ['controls', 'coarse', 'fine']
    assert all(patches == expected for _, patches in calls)
    print('dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer')


def test_adapter_preparation(cohort):
    from ros2_jazzy.gz_checks.online_batch_checks import prepare_cases as prepare_controls
    from ros2_jazzy.gz_checks.lidar_checks import prepare_cases as prepare_lidar
    selected = {s['patch'] for s in cohort['reruns']}
    with tempfile.TemporaryDirectory() as temporary, \
         patch.dict(os.environ, {'THESIS_REAL_TIME_FACTOR': '.3', 'THESIS_STALE_TIMEOUT_S': '1.0'}):
        root = Path(temporary)
        controls, _ = prepare_controls(root/'controls', scenarios=cohort['reruns'])
        expected = [s for s in cohort['scenarios'] if s['patch'] in selected]
        assert controls['scenarios'] == expected
        assert len(controls['cases']) == 2*len(selected)
        for method in ('coarse', 'fine'):
            lidar = prepare_lidar(root/method, patch_count=10, map_method=method,
                                  scenarios=cohort['scenarios'], selected_patches=selected)
            assert lidar['scenarios'] == cohort['scenarios']
            assert {c['patch'] for c in lidar['cases'] if c['selected']} == selected
    print('real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS')


def test_docker_wrapper():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        docker = root/'docker'
        docker.write_text('#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ["EDGE_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n')
        docker.chmod(0o755)
        env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'], EDGE_ARGS=str(root/'args.json'))
        env.pop('THESIS_REAL_TIME_FACTOR', None)
        env.pop('THESIS_STALE_TIMEOUT_S', None)
        script = ROOT/'ros2_jazzy/gz_checks/run_edge_margin_checks.sh'
        subprocess.run(['bash', str(script), str(root/'output')], env=env, check=True, capture_output=True)
        args = json.loads((root/'args.json').read_text())
        assert '--pull=never' in args and str(ROOT)+':/conference:ro' in args
        assert 'THESIS_REAL_TIME_FACTOR=0.3' in args and 'THESIS_STALE_TIMEOUT_S=1.0' in args
        assert 'edge_margin_checks.py' in ' '.join(args)
        (root/'output/manifest.json').write_text('{}')
        refused = subprocess.run(['bash', str(script), str(root/'output')], env=env, capture_output=True)
        assert refused.returncode == 2
    print('Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest')


if __name__ == '__main__':
    test_sampling()
    cohort = test_cohort()
    test_excluded_start()
    test_reports(cohort)
    test_adapter_preparation(cohort)
    test_dispatch(cohort)
    test_docker_wrapper()
    print('all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)')
