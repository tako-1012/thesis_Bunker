"""Test task053 features and archive screening without ROS2 or Gazebo."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from results.false_steep_causes import replay
from tapp.pointcloud_map_fine import PointCloudMapFine


def test_features():
    x, y = np.mgrid[:7, :7] * replay.RESOLUTION
    truth = x * np.tan(np.deg2rad(22))
    truth[-1] += .5
    water = y == 0.
    nodata = y == 2.5
    pose = [0., 0., 0., 0., 0., np.pi/2]
    origin = [0., 0., .8]
    terrain = replay.terrain_features(truth, water, nodata, pose, origin)
    mixer = PointCloudMapFine(truth, ground_estimate='non_obstacle')
    # One return in (3,2), one ground and one high return in (3,3).
    points = [[1.5, 1., truth[3, 2]-.8], [1.5, 1.5, truth[3, 3]-.8],
              [1.5, 1.5, truth[3, 3]-.8+.5]]
    mixer.update(points, [0.]*6)
    centre_index = tuple(3*replay.RATIO+replay.RATIO//2 for _ in range(2))
    mixer._add_obstacles([int(np.ravel_multi_index(centre_index, mixer.fine_shape))])
    counts = replay.first_counts(mixer)
    seen = np.ones(truth.shape, bool)
    seen[4, 2] = False
    estimated = truth.copy()
    estimated[3, 3] += .7
    f = replay.map_features(terrain, counts, estimated, seen, mixer.fine_obstacle, mixer.fine_inflated, nodata)
    labels, types = replay.classify(f)
    cell = (3, 2)
    assert labels['false_steep'][cell]
    assert labels['true_steep'][6, 2]
    assert labels['true_nonsteep'][2, 0]
    assert not labels['missed_steep'].any()
    assert f['box_m'][cell] == .5 and f['box_halo_m'][cell] == 0
    assert f['box_halo_m'][3, 1] == .5 and types['box_near'][3, 1]
    assert not types['box_near'][3, 0]
    assert f['first_cell_points'][cell] == 1 and f['first_other8_points'][cell] == 2
    assert f['first_3x3_points'][cell] == 3 and f['first_3x3_ground_points'][cell] == 2
    assert f['first_cell_ground_points'][3, 3] == 1
    assert types['sparse_first_lidar'][cell] and not types['sparse_first_lidar'][0, 6]
    np.testing.assert_allclose(f['truth_slope_deg'][cell], 22.)
    np.testing.assert_allclose(f['truth_height_std_m'][cell], np.std(truth[2:5, 1:4]))
    np.testing.assert_allclose(f['truth_height_std_m'][3, 4], np.std(truth[2:5, 3:5]))
    assert types['near_slope_limit'][cell] and f['stencil_has_unseen'][cell]
    assert types['high_truth_relief'][5, 2]
    assert f['sea_m'][cell] == 1. and f['nodata_m'][cell] == 1.5
    assert types['sea_or_nodata_near'][cell] and types['sea_or_nodata_near'][3, 3]
    np.testing.assert_allclose(f['first_robot_xy_m'][cell], np.hypot(1.5, 1.))
    np.testing.assert_allclose(f['first_bearing_deg'][cell], np.degrees(np.arctan2(1., 1.5))-90)
    delta = np.asarray(origin)-[1.5, 1., truth[cell]]
    normal = [-np.tan(np.deg2rad(22)), 0, 1.]
    angle = np.degrees(np.arcsin(abs(delta @ normal) / (np.linalg.norm(delta)*np.linalg.norm(normal))))
    np.testing.assert_allclose(f['first_incidence_deg'][cell], angle)
    assert np.isinf(replay.distance_to(np.zeros_like(nodata))).all()
    assert np.isnan(replay.height_std(truth, np.ones_like(nodata))).all()
    f['truth_slope_deg'][cell] = f['estimated_slope_deg'][cell] = 25.
    labels, types = replay.classify(f)
    assert labels['true_nonsteep'][cell] and types['near_slope_limit'][cell]
    print('1 PASS: geometry, exact slope labels, box halo, point counts, missing stencil, relief, sea/nodata and view angles')


def test_archive_and_missing_record():
    root = replay.ROOT
    tracked = replay.committed_inputs(root)
    actual = next(record for record in replay.discover(root, tracked)
                  if record[1] and record[0].name == '08OB88_-0167')
    _, primary, _ = actual
    missing = Path('results/fixture/physical_1/raw/missing')
    tracked = tracked | {missing/'pointcloud_map.npz'}
    with TemporaryDirectory() as tmp, redirect_stdout(StringIO()) as message:
        output = Path(tmp)
        tables = replay.analyze(root, output, tracked=tracked, records=[(missing, primary, ''), actual])
        assert 'skipped' in message.getvalue() and str(missing/'first_cloud.npz') in message.getvalue()
        assert [row['status'] for row in tables['inventory']] == ['skipped', 'used']
        assert len(tables['runs']) == 2
        end = next(row for row in tables['runs'] if row['stage'] == 'final')
        assert end['seen'] == int(primary['seen_cells'])
        assert end['seen'] == end['seen_sea'] + end['seen_nodata'] + sum(end[k] for k in replay.CLASSES)
        assert all((output/(name+'.csv')).stat().st_size > 0 for name in tables)
        end_false = [row for row in tables['overlaps']
                     if row['stage'] == 'final' and row['classification'] == 'false_steep']
        assert sum(row['count'] for row in end_false) == end['false_steep'] > 0
        goal = [row for row in tables['goal_cells']
                if row['stage'] == 'goal_failure' and row['goal_distance_m'] == 0.]
        assert len(goal) == 1 and goal[0]['lethal']
        assert any(row['stage'] == 'goal_failure' and row['steep_can_block_goal'] for row in tables['goal_cells'])
    print('2 PASS: committed final/first/failure data produce CSVs and a missing run is explicitly skipped')


if __name__ == '__main__':
    test_features()
    test_archive_and_missing_record()
    print('all task053 false-steep-cause tests passed')
