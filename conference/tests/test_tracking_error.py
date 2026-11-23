"""Check task061 geometry, causal revisions and the committed archive adapter."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from experiments.eval_runs import box_metrics, deviation_metrics, read_csv
from results.tracking_error import replay


def test_geometry():
    path = np.array([[0., 0.], [1., 0.], [1., 1.]])
    t = np.arange(2.)
    xy = np.array([[.4, -.3], [1.2, .8]])
    d, kappa, _ = replay.errors(t, xy, [0.], [path])
    np.testing.assert_allclose(d, [.3, .2])
    np.testing.assert_allclose(kappa, np.sqrt(2.))

    x = np.arange(10.)[:, None] * replay.RESOLUTION
    elev = x * np.tan(np.deg2rad(15.)) + np.zeros((1, 10))
    xy = np.array([[1., 1.], [2., 1.], [1., 1.], [1., 2.], [1., 2.], [-3., 2.]])
    t = np.arange(len(xy), dtype=float)
    slopes, direction = replay.motion_features(xy, t, elev)
    np.testing.assert_allclose(slopes[:5], [15.]*5)
    assert np.isnan(slopes[-1])
    assert direction.tolist() == ['unknown', 'uphill', 'downhill', 'cross_slope', 'unknown', 'unknown']
    groups = replay.conditions(t, xy, np.array([0., .15, .3, .6, np.nan, 1.]),
                               np.array([0., .02, .10, 1., 0., np.nan]), np.zeros(len(t), int),
                               np.array([0.]), elev, np.full(len(t), np.nan), None)
    assert groups['slope'].tolist() == ['10-20']*5+['unknown']
    assert groups['command'].tolist() == ['near_zero', 'slow', 'medium', 'fast', 'unknown', 'fast']
    assert groups['curvature'].tolist() == ['straight', 'gentle', 'sharp', 'sharp', 'straight', 'unknown']
    print('1 PASS: full-path distance, Menger curvature, slope, motion direction and command bins')


def test_revision_switch():
    rows = [dict(t='0', path='[[0,0],[2,0]]'), dict(t='1', path='[[0,2],[2,2]]'),
            dict(t='1', path='[[0,1],[0,1],[2,1]]')]
    times, paths = replay.revision_data(rows)
    t = np.array([-.1, 0., .9, 1., 1.2, 3.])
    xy = np.tile([1., .9], (len(t), 1))
    errors, kappa, index = replay.errors(t, xy, times, paths)
    np.testing.assert_array_equal(index, [-1, 0, 0, 2, 2, 2])
    np.testing.assert_allclose(errors, [np.nan, .9, .9, .1, .1, .1])
    expected = deviation_metrics(t, xy, rows)
    stats = replay.stats(errors[index >= 0], 1)
    assert stats['samples'] == expected['deviation_samples']
    np.testing.assert_allclose([stats['p95_m'], stats['max_m']],
                               [expected['deviation_p95_m'], expected['deviation_max_m']])
    groups = replay.conditions(t, xy, np.ones(len(t)), kappa, index, times, None,
                               np.full(len(t), np.nan), None)
    assert groups['switch'][1:].tolist() == ['first_path', 'first_path', 'under_2s', 'under_2s', 'at_least_2s']
    print('2 PASS: pre-path samples, same-time revisions, causal switches and task042 percentile parity')


def test_approaches():
    boxes = np.array([[0., 0.]]), np.array([[1., 1.]])
    coords = np.array([[-1., 1.25], [-.1, 1.25], [.5, 1.25], [1.1, 1.25], [2., 1.25]])
    t = np.arange(len(coords), dtype=float)
    for y, kind in ((1.3, 'path_too_close'), (1.8, 'tracking_deviation')):
        path = np.array([[-1., y], [2., y]])
        near = replay.box_distances(coords, boxes)
        event, = replay.events(t, coords, np.array([0.]), [path], boxes, near)
        expected = box_metrics(t, coords, [dict(xmin='0', ymin='0', xmax='1', ymax='1')])
        assert expected['truth_below_radius_entries'] == 1
        np.testing.assert_allclose([event['min_box_m'], event['duration_s']],
                                   [expected['min_truth_clearance_m'], expected['truth_below_radius_s']])
        assert event['classification'] == kind
        np.testing.assert_allclose(event['projected_point_to_box_m'], y-1)
    boundary = coords.copy()
    boundary[:, 1] = 1.5
    assert not list(replay.events(t, boundary, np.array([0.]), [path], boxes,
                                  replay.box_distances(boundary, boxes)))
    print('approaches PASS: interpolated strict clearance and same-box attribution')


def test_archive():
    root = replay.ROOT
    tracked = replay.committed(root)
    published = replay.ledgers(root, tracked)
    actual = next(raw for raw, (study, _) in published.items() if study == '030')
    absent = next(raw for raw, (study, _) in published.items() if study == '050')
    signals, _ = replay.discover(root, tracked, published)
    fixed = next(raw for raw in sorted(signals) if raw.parts[1] == 'gazebo_compare')
    _, _, _, _, _, method, mission = replay.read_run(root, tracked, fixed, signals[fixed])
    terrain, boxes, world = replay.terrain_from_run(root, tracked, fixed, mission)
    assert method == 'fixed_mission' and terrain.ndim == 2 and boxes is not None
    assert Path(world) in tracked
    with TemporaryDirectory() as directory, redirect_stdout(StringIO()) as log:
        output = Path(directory)
        inventory, runs, summary, _, _ = replay.analyze(root, output, tracked=tracked, selected=[absent, actual])
        assert [r['status'] for r in inventory] == ['skipped', 'used']
        assert 'trajectory not committed' in log.getvalue() and str(absent) in log.getvalue()
        assert len(runs) == 1 and runs[0]['boxes'] and runs[0]['slope_available']
        t, xy, *_ = replay.read_run(root, tracked, actual, {'trajectory', 'path_revisions'})
        expected = deviation_metrics(t, xy, read_csv(root/actual/'path_revisions.csv')[1])
        totals = next(r for r in summary if r['feature'] == 'all')
        assert totals['samples'] == expected['deviation_samples'] > 0
        assert totals['runs'] == 1
        np.testing.assert_allclose([totals['p95_m'], totals['max_m']],
                                   [expected['deviation_p95_m'], expected['deviation_max_m']])
        assert (output/'inventory.csv').stat().st_size and (output/'distribution.csv').stat().st_size
    saved, unresolved = replay.known_approaches(root, tracked, published, set())
    assert {r['classification'] for r in saved if r['study'] == '044'} == {'path_too_close', 'tracking_deviation'}
    assert sum(r['intervals'] for r in unresolved if r['study'] == '050') == sum(
        int(row['truth_below_radius_entries']) for study, row in published.values() if study == '050')
    print('3 PASS: committed archive tables, explicit skipped input and published event-evidence coverage')


if __name__ == '__main__':
    test_geometry()
    test_revision_switch()
    test_approaches()
    test_archive()
    print('all task061 tracking-error tests passed')
