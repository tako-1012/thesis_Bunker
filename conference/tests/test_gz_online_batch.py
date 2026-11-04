"""Task021 parity and explicitly synthetic record fixtures, without ROS or Gazebo."""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
import pandas as pd

from tapp.config import RESOLUTION
from tapp.real_beach import build_real, list_patches
from tapp.tour import sample_waypoints
from tapp.online_mission import ordered_tour, run_fixed_mission
from tapp.footprint import with_inflated_steep
from tapp.traversability import TraversabilityMap
from ros2_jazzy.gz_checks.online_batch_checks import prepare_cases
from ros2_jazzy.gz_checks.online_batch_runtime import (
    scenario_cases, case_metadata, planning_map, make_runtime, CsvChunks, read_csv_parts,
    split_follower_logs, map_signature,
)
from experiments.gz_online_batch_report import analyze_record, reached_goals, summary_tables, summarize, MEASURES


def test_scenarios():
    cases = scenario_cases()
    expected = list_patches('test', dataset='shizuoka_beach_las')[:10]
    assert [c['patch'] for c in cases] == [r['name'] for r in expected]
    for case, row in zip(cases, expected):
        truth = build_real(row['name'], 200, 0, debris=True, dataset='shizuoka_beach_las')
        prior = build_real(row['name'], 200, 0, dataset='shizuoka_beach_las')
        seed = np.random.SeedSequence([0, 3000, 200, truth['patch_index']])
        points = sample_waypoints(truth, 12, seed)[:5]
        tour = ordered_tour(prior['tmap'], truth['start'], points)
        assert case['start'] == list(truth['start'])
        assert case['points'] == [list(p) for p in points]
        assert case['tour']['order'] == tour['order'] and case['tour']['stops'] == tour['stops']
        for side, original in [('truth', truth), ('clean', prior)]:
            for attr in ['elev', 'cost', 'lethal', 'rock', 'steep']:
                assert np.array_equal(getattr(case[side]['tmap'], attr), getattr(original['tmap'], attr))
        assert np.array_equal(case['truth_tm'].lethal, with_inflated_steep(truth, .5)['tmap'].lethal)
        assert np.array_equal(case['prior_tm'].lethal, with_inflated_steep(prior, .5)['tmap'].lethal)
        if case['planning_status'] == 'planned':
            fixed = run_fixed_mission(with_inflated_steep(prior)['tmap'], truth['start'], tour['stops'])
            assert np.array_equal(case['fixed']['traj'], fixed['traj'])
        assert planning_map(truth, 'TA*-S') is truth['tmap']
    print('scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls', flush=True)
    return cases


def test_runtime():
    tm = TraversabilityMap(np.zeros((70, 70)), np.zeros((70, 70), bool))
    tm.steep[30, 30] = True
    tm.lethal[30, 30] = True
    sc = dict(tmap=tm)
    stops = [(45, 5), (45, 45), (5, 45), (5, 30), (5, 20), (5, 5)]
    mission = dict(id=1, map_id='fixture', points=[], start_cells=[5, 5],
                   stops_cells=stops, order=[0, 4, 3, 2, 1, 5])
    runtime = make_runtime(sc, sc)
    try:
        runtime.start(mission)
        with patch('thesis_bunker_mission.online_runtime.ordered_tour', side_effect=AssertionError('tour was recomputed')):
            result = runtime._work(runtime.state, (2.5, 2.5))
        assert result['success']
        assert runtime.state['tour']['stops'] == stops
        assert runtime.state['tour']['order'] == mission['order']
        assert tuple(runtime.state['planner'].goal) == stops[0]
        assert runtime.truth.lethal[29, 30] and not tm.lethal[29, 30]
        assert runtime.truth.cost is tm.cost
    finally:
        runtime.close()
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / 'plans.csv'
        runtime = make_runtime(sc, sc, plan_log=target)
        try:
            runtime.start(mission)
            runtime._work(runtime.state, (2.5, 2.5))
            assert runtime.sent == 0  # No handoff was sent to the follower.
            events = read_csv_parts(target)
            assert len(events) == 1 and events[0]['n_plans'] == '1'
            assert float(events[0]['plan_time_s']) >= 0
        finally:
            runtime.close()
    runtime = make_runtime(sc, sc)
    try:
        bad = dict(mission, stops_cells=[(29, 30)])
        runtime.start(bad)
        assert runtime._work(runtime.state, (2.5, 2.5))['reason'] == 'blocked_endpoint'
    finally:
        runtime.close()
    print('runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified')


def test_records():
    tm = TraversabilityMap(np.zeros((70, 70)), np.zeros((70, 70), bool))
    prior = dict(tmap=tm)
    truth = dict(tmap=TraversabilityMap(np.zeros((70, 70)), np.zeros((70, 70), bool)))
    truth['tmap'].rock[20, 10] = True
    truth['tmap'].lethal[20, 10] = True
    points = [[5, 5], [10, 5], [15, 5], [20, 5], [25, 5], [5, 5]]
    metadata = dict(start=[10, 10], stops=(np.asarray(points) / RESOLUTION).astype(int).tolist())
    for status, rolls, count, expected in [
        ('completed', [0, 0, 0, 0, 0, 0], 5, 'completed'),
        ('stuck', [0, 90, -90], 3, 'stuck'),
        ('stuck', [0, 90, -91], 3, 'rollover'),
        ('simulation_timeout', [0, 0, 0], 3, 'timeout'),
    ]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mission = dict(status=status, data_source='synthetic_test_fixture')
            (root / 'mission.json').write_text(json.dumps(mission))
            trace = CsvChunks(root / 'trajectory.csv', ['t', 'x', 'y', 'z', 'roll', 'pitch', 'yaw', 'v', 'w'])
            for i, angle in enumerate(rolls):
                trace.write(dict(t=10+i, x=points[i][0], y=points[i][1], z=0,
                                 roll=np.radians(angle), pitch=np.radians(2*i), yaw=0, v=0, w=0))
            trace.close()
            calls = CsvChunks(root / 'plans.csv', ['n_plans', 'reason', 'success', 'plan_time_s'])
            for i, seconds in enumerate([.1, .2, 1.2]):
                calls.write(dict(n_plans=i+1, reason='start_leg' if i == 0 else 'blocked', success=True, plan_time_s=seconds))
            calls.close()
            paths = CsvChunks(root / 'path_revisions.csv', ['t', 'path'])
            paths.write(dict(t=10, path=json.dumps(points)))
            # Final path is deliberately far away: earlier deviation must retain the earlier path.
            paths.write(dict(t=12, path=json.dumps([[0, 10], [30, 10]])))
            paths.close()
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
            result, _ = analyze_record(root, metadata, truth, prior)
            assert result['status'] == expected and result['recorded_status'] == status
            assert result['goals_reached'] == count
            assert result['n_replans'] == 2 and result['n_plans'] == 3
            assert np.isclose(result['plan_s_median'], .2) and result['plan_s_max'] == 1.2
            assert result['calls_over_1s'] == 1
            assert result['debris_cells'] == result['lethal_cells'] == 1
            assert result['deviation_mean_m'] < 5 and result['deviation_max_m'] == 5
            assert result['rolled_over'] == (expected == 'rollover')
            if result['rolled_over']:
                assert result['rollover_t_s'] == 12 and result['rollover_x_m'] == 15
            assert not any('energy' in key.lower() for key in result)
            assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == h for name, h in before.items())
            (root / 'plans.csv').unlink()
            missing, _ = analyze_record(root, metadata, truth, prior)
            assert missing['n_plans'] is None and missing['n_replans'] is None and missing['calls_over_1s'] is None
    # Crossing the five circles in one segment counts; reverse traversal cannot reorder the targets.
    assert reached_goals([[0, 0], [10, 0]], [[2, 0], [4, 0], [6, 0], [8, 0], [9, 0]]) == 5
    assert reached_goals([[10, 0], [0, 0]], [[2, 0], [4, 0], [6, 0], [8, 0], [9, 0]]) == 1
    print('synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed')


def test_csv_chunks():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        writer = CsvChunks(root / 'trajectory.csv', ['i', 'value'], limit=220)
        values = [dict(i=str(i), value='0.' + '1' * 78) for i in range(12)]
        for row in values:
            writer.write(row)
        writer.close()
        assert read_csv_parts(root / 'trajectory.csv') == values
        assert len(list(root.glob('*.csv'))) > 1
        assert all(p.stat().st_size < 220 for p in root.iterdir())
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / 'trajectory.csv'
        writer = CsvChunks(target, ['i', 'value'])
        for row in values:
            writer.write(row)
        writer.close()
        split_follower_logs(temporary, limit=220)
        assert read_csv_parts(target) == values
        assert all(p.stat().st_size < 220 for p in Path(temporary).iterdir())
        (Path(temporary) / 'trajectory_part001.csv').unlink()
        try:
            read_csv_parts(target)
        except ValueError:
            pass
        else:
            raise AssertionError('missing raw CSV part was silently ignored')
    print('raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed')


def test_missing(cases):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest, _ = prepare_cases(root, scenarios=cases)
        with redirect_stdout(io.StringIO()):
            data, summary, pairs = summarize(root, figures=False)
        assert len(data) == 20 and len(summary) == 2
        assert summary.executed.eq(0).all() and summary.completed.isna().all()
        assert data.lethal_cells.isna().all() and data.rolled_over.isna().all()
        assert pairs.paired_completed.eq(0).all() and pairs.online_minus_fixed_median.isna().all()
        for name in ['runs.csv', 'summary.csv', 'paired_differences.csv']:
            assert not any('energy' in c.lower() for c in pd.read_csv(root / name).columns)
        assert not list(root.rglob('*.npz')) and not list(root.rglob('*.sdf'))
        try:
            prepare_cases(root, scenarios=cases)
        except FileExistsError:
            pass
        else:
            raise AssertionError('existing manifest overwritten')
    print('unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused')


def test_paired_counts():
    rows = []
    for site in ['fixture_a', 'fixture_b']:
        for mode in ['fixed', 'online']:
            completed = site == 'fixture_a'
            row = dict(patch=site, mode=mode, data_source='gazebo', completed=completed,
                       planning_status='planned', status='completed' if completed else ('stuck' if mode == 'fixed' else 'rollover'))
            # Synthetic in-memory values only; no table is emitted or saved.
            row.update({key: 1. if mode == 'fixed' else 3. for key in MEASURES})
            rows.append(row)
    summary, effects = summary_tables(pd.DataFrame(rows))
    assert summary.executed.eq(2).all() and summary.completed.eq(1).all()
    assert summary[summary['mode'] == 'online'].rollover.iloc[0] == 1
    assert summary[summary['mode'] == 'fixed'].stuck.iloc[0] == 1
    assert effects.paired_completed.eq(1).all() and effects.online_minus_fixed_median.eq(2).all()
    print('synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator')


if __name__ == '__main__':
    cases = test_scenarios()
    test_runtime()
    test_records()
    test_csv_chunks()
    test_missing(cases)
    test_paired_counts()
    print('all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)')
