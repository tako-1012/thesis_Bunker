"""Synthetic geometry/registration fixtures only; no ROS/Gazebo dependencies."""

from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
import numpy as np

from tapp.pointcloud_map import PointCloudMap, PoseBuffer, decode_xyz, transform_points
from tapp.traversability import TraversabilityMap
from tapp.footprint import inflate_steep
from tapp.config import RESOLUTION

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_jazzy/src/thesis_bunker_gz'))
from thesis_bunker_gz.model import make_model
from thesis_bunker_gz.lidar import LidarSpec
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission


def test_flat_and_unknown():
    prior = np.full((31, 31), 2.)
    mapper = PointCloudMap(prior)
    x, y = np.meshgrid(np.arange(10, 21)*RESOLUTION, np.arange(10, 21)*RESOLUTION, indexing='ij')
    floor = np.column_stack((x.ravel()-5, y.ravel()-5, np.full(x.size, -.8)))
    points = np.vstack([floor+[0, 0, dz] for dz in [-.005, 0, .005]])
    result = mapper.update(points, [5, 5, 2, 0, 0, 0])
    seen, cost, lethal = mapper.snapshot()
    expected = np.zeros(prior.shape, bool)
    expected[10:21, 10:21] = True
    assert np.array_equal(seen, expected)
    assert result['observed_cells'] == expected.sum() and result['update_s'] >= 0
    assert np.allclose(mapper.elev, 2, atol=1e-12, rtol=0)
    assert np.max(mapper.tm.slope) < 1e-10 and np.max(cost) < 1e-10
    assert not lethal.any() and not mapper.detected_obstacle.any()
    assert np.array_equal(prior, np.full(prior.shape, 2.))
    mapper.update(np.empty((0, 3)), [5, 5, 2, 0, 0, 0])
    assert np.array_equal(mapper.snapshot()[0], seen)
    # No ray carving: intervening cells and empty returns do not become observed.
    assert not seen[5, 5] and not seen[25, 25]
    print('flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed')


def test_boxes_and_formulas():
    prior = np.zeros((31, 31))
    raw = np.zeros_like(prior, bool)
    raw[4, 4] = True
    mapper = PointCloudMap(prior, raw)
    reference = TraversabilityMap(prior, raw)
    assert np.array_equal(mapper.tm.rock, reference.rock)  # Prior obstacles not inflated twice.
    points = np.array([[5, 0, -.2], [5.01, .01, -.19], [4.99, -.01, -.21]])
    mapper.update(points, [0, 5, 0, 0, 0, 0])
    assert mapper.detected_obstacle[10, 10] and mapper.lethal[10, 10]
    assert mapper.elev[10, 10] > .5
    seen, cost, lethal = mapper.snapshot()
    direct = TraversabilityMap(mapper.elev, raw | mapper.detected_obstacle)
    assert np.array_equal(cost, direct.cost)
    assert np.array_equal(lethal, inflate_steep(direct))
    assert seen.sum() == 1 and not seen[9, 10]
    assert mapper.tm.slope[9, 10] > 0  # Neighbour features recomputed without becoming seen.
    isolated = PointCloudMap(prior)
    isolated.update(np.array([[5., 0, -.1]]), [0, 5, 0, 0, 0, 0])
    assert not isolated.detected_obstacle.any()
    # Returns below the declared threshold do not form a detected cluster.
    low = PointCloudMap(prior)
    low.update(np.repeat([[5., 0, -.6]], 4, axis=0), [0, 5, 0, 0, 0, 0])
    assert not low.detected_obstacle.any()
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / 'estimated_map.npz'
        mapper.save(path)
        with np.load(path, allow_pickle=False) as data:
            assert np.array_equal(data['seen'], seen) and np.array_equal(data['lethal'], lethal)
    print('box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed')


def test_registration():
    points = np.array([[1, 0, -.8]])
    world = transform_points(points, [1, 2, 3, 0, 0, np.pi/2])
    assert np.allclose(world, [[1, 3, 3]], atol=1e-12)
    world = transform_points([[0, 0, 0]], [1, 2, 3, np.pi/2, 0, 0])
    assert np.allclose(world, [[1, 1.2, 3]], atol=1e-12)
    buffer = PoseBuffer()
    buffer.add(1., [0, 0, 0, 0, 0, np.radians(179)])
    buffer.add(1.05, [1, 2, 3, 0, 0, np.radians(-179)])
    pose = buffer.at(1.025)
    assert np.allclose(pose[:3], [.5, 1, 1.5]) and abs(abs(pose[5])-np.pi) < 1e-12
    assert buffer.at(.9) is None and buffer.at(1.1) is None
    assert buffer.at(1.025, max_gap_s=.01) is None
    try:
        buffer.add(.5, np.zeros(6))
    except ValueError:
        pass
    else:
        raise AssertionError('time reset accepted')
    print('registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed')


def test_pointcloud_layouts_and_filtering():
    fields = [dict(name=name, offset=4+4*i, datatype=7, count=1) for i, name in enumerate(['x', 'y', 'z'])]
    expected = np.arange(12, dtype=float).reshape(4, 3)
    for endian in ['<', '>']:
        raw = bytearray(2*48)
        dtype = np.dtype(dict(names=['x', 'y', 'z'], formats=[endian+'f4']*3, offsets=[4, 8, 12], itemsize=20))
        values = np.ndarray((2, 2), dtype=dtype, buffer=raw, strides=(48, 20))
        for i, name in enumerate(['x', 'y', 'z']):
            values[name] = expected[:, i].reshape(2, 2)
        actual = decode_xyz(raw, fields, point_step=20, row_step=48, width=2, height=2, is_bigendian=endian == '>')
        assert np.array_equal(actual, expected)
    try:
        decode_xyz(b'bad', fields, point_step=20, row_step=48, width=2, height=2)
    except ValueError:
        pass
    else:
        raise AssertionError('truncated cloud accepted')
    mapper = PointCloudMap(np.zeros((20, 20)))
    invalid = np.array([[np.nan, 0, 0], [np.inf, 0, 0], [100, 0, 0], [-10, -10, 0]])
    result = mapper.update(invalid, [0, 0, 0, 0, 0, 0])
    assert result['accepted_points'] == 0 and not mapper.seen.any()
    saturated = PointCloudMap(np.zeros((100, 100)))
    result = saturated.update([[30., 0, 0]], [0, 0, 0, 0, 0, 0])
    assert result['accepted_points'] == 0 and not saturated.seen.any()
    print('PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed')


def test_model_defaults_and_lidar():
    verification = ROOT / 'results/gazebo_lidar/verification'
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        default = make_model(root / 'default.sdf')
        mass = make_model(root / 'mass.sdf', mass_kg=170.)
        assert default.read_bytes() == (verification / 'model_default_before.sdf').read_bytes()
        assert mass.read_bytes() == (verification / 'model_mass_before.sdf').read_bytes()
        path = make_model(root / 'lidar.sdf', lidar=True)
        sensor = ET.parse(path).find('.//sensor[@name="lidar"]')
        assert sensor.attrib['type'] == 'gpu_lidar'
        vertical = sensor.find('lidar/scan/vertical')
        angles = np.degrees(np.linspace(float(vertical.findtext('min_angle')), float(vertical.findtext('max_angle')), int(vertical.findtext('samples'))))
        assert np.allclose(angles, np.arange(-15, 16, 2))
        assert float(sensor.findtext('update_rate')) == 10
        assert float(sensor.findtext('lidar/range/max')) == 30
        assert abs(float(sensor.findtext('pose').split()[2])+.35-.8) < 1e-12
        assert sensor.findtext('gz_frame_id') == 'lidar'
        custom = make_model(root / 'custom.sdf', lidar=True, lidar_height_m=1.2,
                            lidar_spec=replace(LidarSpec(), noise_stddev_m=0.))
        other = ET.parse(custom).find('.//sensor[@name="lidar"]')
        assert abs(float(other.findtext('pose').split()[2])+.35-1.2) < 1e-12
        assert float(other.findtext('lidar/noise/stddev')) == 0
    print('model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed')


def test_no_truth_runtime():
    from unittest.mock import patch
    tm = TraversabilityMap(np.zeros((50, 50)), np.zeros((50, 50), bool))
    mapper = PointCloudMap(tm.elev)
    mapper.update([[0, 0, -.8]], [2.5, 2.5, 0, 0, 0, 0])
    runtime = LidarOnlineMission(dict(tmap=tm), mapper)
    mission = dict(id=1, map_id='fixture', order=[0, 1], stops_cells=[[40, 40], [5, 5]])
    try:
        runtime.start(mission)
        with patch('thesis_bunker_mission.online_runtime.virtual_sense', side_effect=AssertionError('truth leak')):
            result = runtime._work(runtime.state, (2.5, 2.5))
            assert result['success']
            joined = runtime._join(runtime.state, result, (2.5, 2.5))
        assert joined and runtime.truth is None
        planner = runtime.state['planner']
        assert np.array_equal(planner.known, mapper.seen)
        assert planner.known.sum() == 1
    finally:
        runtime.close()
    print('LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable')


def test_quality_and_three_method_report():
    import json
    from contextlib import redirect_stdout
    import io
    import pandas as pd
    from experiments.gz_lidar_report import map_quality, summarize, MEASURES
    from ros2_jazzy.gz_checks.online_batch_runtime import CsvChunks
    from ros2_jazzy.gz_checks.lidar_checks import prepare_cases
    truth = dict(tmap=TraversabilityMap(np.ones((10, 10)), np.zeros((10, 10), bool)))
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        assert all(value is None for value in map_quality(folder, truth).values())
        seen = np.zeros((10, 10), bool)
        seen[1, 1:4] = True
        height = np.full((10, 10), 1e6)
        height[1, 1:4] = [1.1, .8, 1.3]
        np.savez_compressed(folder/'pointcloud_map.npz', elev=height, seen=seen)
        log = CsvChunks(folder/'map_updates.csv', ['status', 'update_s'])
        for row in [dict(status='ok', update_s=.02), dict(status='error', update_s=''), dict(status='ok', update_s=.04)]:
            log.write(row)
        log.close()
        (folder/'sensor_status.json').write_text(json.dumps(dict(queue_drops=2)))
        result = map_quality(folder, truth)
        assert result['height_cells'] == 3
        assert abs(result['height_abs_error_median_m']-.2) < 1e-12
        assert abs(result['height_abs_error_p95_m']-.29) < 1e-12
        assert result['map_updates'] == 2 and result['map_failed_updates'] == 1
        assert result['map_update_s_median'] == .03 and result['queue_drops'] == 2
        no_truth = map_quality(folder)
        assert no_truth['height_cells'] == 3 and no_truth['height_abs_error_median_m'] is None
        assert no_truth['map_updates'] == 2
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        manifest = prepare_cases(folder, patch_count=3)
        with redirect_stdout(io.StringIO()):
            data, summary, pairs = summarize(folder, figures=False)
        baseline = pd.read_csv(ROOT/'results/gazebo_online/physical_run/runs.csv', float_precision='round_trip')
        assert len(data) == 30 and len(summary) == 3
        for field in MEASURES:
            pd.testing.assert_series_equal(data.iloc[:20][field], baseline[field], check_dtype=False, check_names=False, check_exact=True)
        lidar = data[data['mode'] == 'lidar']
        assert lidar.selected.sum() == 3 and lidar.completed.isna().all()
        assert lidar.height_abs_error_median_m.isna().all() and lidar.map_update_s_median.isna().all()
        assert summary[summary['mode'] == 'lidar'].executed.iloc[0] == 0
        assert summary[summary['mode'] == 'lidar'].completed.isna().all()
        assert pairs[pairs.method == 'lidar'].paired_completed.eq(0).all()
        assert not any('energy' in name.lower() for name in data.columns)
        assert manifest['scenarios'] == json.loads((ROOT/'results/gazebo_online/physical_run/manifest.json').read_text())['scenarios']
    print('quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed')


if __name__ == '__main__':
    test_flat_and_unknown()
    test_boxes_and_formulas()
    test_registration()
    test_pointcloud_layouts_and_filtering()
    test_model_defaults_and_lidar()
    test_no_truth_runtime()
    test_quality_and_three_method_report()
    print('all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)')
