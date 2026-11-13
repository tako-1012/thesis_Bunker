"""Task032 sensor-only planes, immutable defaults and explicit experiment inputs."""

import ast
import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import patch
import numpy as np
from scipy.ndimage import label, find_objects

from tapp.config import RESOLUTION
from tapp.local_ground import local_planes
from tapp.mapfile import save_map
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.prior_variants import prior_variant
from tapp.sensor_geometry import REAL_MOUNTS
from tapp.traversability import TraversabilityMap
from data_prep.export_gazebo import export_gazebo
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from tests.test_real_sensors import local_cloud

ROOT = Path(__file__).resolve().parents[1]
BOX = (10, 10)


def cloud(slope_deg=0., box=False):
    x, y = np.meshgrid(np.arange(3., 7.01, .1), np.arange(3., 7.01, .1), indexing='ij')
    xyz = np.column_stack((x.ravel(), y.ravel(), (x.ravel()-5)*np.tan(np.deg2rad(slope_deg))))
    if box:
        cells = np.floor(xyz[:, :2]/RESOLUTION+.5).astype(int)
        top = (cells == BOX).all(axis=1)
        xyz[top, 2] += .4
    return np.repeat(xyz, 3, axis=0)


def mapper_for(slope_deg=0., shift=0., reference='local'):
    prior = (np.indices((24, 24))[0]*RESOLUTION-5)*np.tan(np.deg2rad(slope_deg))+shift
    return PointCloudMapFine(prior, obstacle_reference=reference, ground_estimate='non_obstacle')


def update(mapper, world):
    return mapper.update(world-[0., 0., .8], np.zeros(6))


def errors(mapper, has_box):
    expected = np.zeros(mapper.prior.shape, bool)
    if has_box:
        expected[BOX] = True
    return int(np.count_nonzero(mapper.detected_obstacle & ~expected)), int(np.count_nonzero(expected & ~mapper.detected_obstacle))


def test_default_bytes():
    capture = runpy.run_path(str(ROOT/'results/prior_free/verification/capture_defaults.py'))['capture']
    expected = json.loads((ROOT/'results/prior_free/verification/defaults_before.json').read_text())
    assert capture() == expected
    for mode in ('legacy', 'lidar_real', 'lidar_real+depth2'):
        options = dict(map_method='fine', sensors=mode)
        a = make_pointcloud_map(np.zeros((24, 24)), **options)
        b = make_pointcloud_map(np.zeros((24, 24)), obstacle_reference='prior', **options)
        if mode == 'legacy':
            update(a, cloud(box=True)); update(b, cloud(box=True))
        else:
            pose = np.array([2., 5., 0., 0., 0., 0.])
            for name, mount in a.mounts.items():
                points = local_cloud(cloud(box=True), pose, mount)
                a.update(points, pose, sensor=name); b.update(points, pose, sensor=name)
        assert all(x.tobytes() == y.tobytes() for x, y in zip(a.snapshot(), b.snapshot()))
        with tempfile.TemporaryDirectory() as tmp:
            a.save(Path(tmp)/'a.npz'); b.save(Path(tmp)/'b.npz')
            assert (Path(tmp)/'a.npz').read_bytes() == (Path(tmp)/'b.npz').read_bytes()
    print('1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default')


def test_clouds():
    rows = []
    for slope in (0., 20.):
        for box in (False, True):
            for shift in (0., -.4, .4):
                for reference in ('prior', 'local'):
                    mapper = mapper_for(slope, shift, reference)
                    update(mapper, cloud(slope, box))
                    fp, fn = errors(mapper, box)
                    if reference == 'local':
                        assert fp == fn == 0, (slope, box, shift, fp, fn)
                        if box:
                            assert mapper.lethal[BOX]
                            # The top-only cell falls back to its SENSOR plane,
                            # rather than retaining the shifted stale DEM.
                            assert abs(mapper.elev[BOX]) < 1e-12
                    elif shift == -.4:
                        assert fp > 0
                    elif shift == .4 and box:
                        assert fn == 1
                    rows.append(dict(slope_deg=slope, box=box, prior_shift_m=shift,
                                     reference=reference, false_positive_cells=fp, missed_cells=fn))
    print('2-4 PASS: flat/20deg plane and 0.4m boxes, with exact and +/-0.4m shifted priors')
    print('slope_deg box prior_shift_m reference false_positive_cells missed_cells')
    for row in rows:
        print(*row.values())
    return rows


def test_unknown_and_multi():
    for support in (np.empty((0, 3)), np.array([[1., 1., 0.], [1.1, 1., 0.]]),
                    np.array([[1., 1., 0.], [1.1, 1., 0.], [1.2, 1., 0.]])):
        assert np.isnan(local_planes(support, np.array([[1., 1., 0.]]))).all()
    mapper = mapper_for(shift=-.4)
    update(mapper, np.array([[5., 5., .4]]*3))
    assert not mapper.detected_obstacle.any()  # One fine-cell minimum cannot define a plane.
    a, b = mapper_for(20.), mapper_for(20.)
    b.prior.fill(12.)
    b.elev.fill(12.)
    for candidate in (a, b):
        update(candidate, cloud(20., box=True))
    assert np.array_equal(a.detected_obstacle, b.detected_obstacle)
    assert np.array_equal(a.seen, b.seen)
    assert np.array_equal(a.elev[a.seen], b.elev[b.seen])
    for sensors in ('lidar_real', 'lidar_real+depth2'):
        pose = np.array([2., 5., 0., 0., 0., 0.])
        mapper = PointCloudMapMulti(np.full((24, 24), .4), sensors=sensors, obstacle_reference='local')
        # LiDAR and the outward cameras use the same local rule and history.
        for name in mapper.mounts:
            mapper.update(local_cloud(cloud(box=True), pose, REAL_MOUNTS[name]), pose, sensor=name, stamp=1.)
        assert errors(mapper, True) == (0, 0)
        assert mapper.first_detections and all(sum(d['supporting_returns'].values()) >= 3 for d in mapper.first_detections)
        assert mapper.sensor_counts['lidar']['high_returns'] > 0
    print('local support PASS: fewer than 3/collinear minima remain unclassified; both real sensor modes fuse sensor-only evidence and attribution')


def test_true_boxes():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        z = np.indices((16, 16))[0]*.01
        obstacle = np.zeros(z.shape, bool); obstacle[8:10, 8:10] = True; obstacle[12, 12] = True
        z[obstacle] += .4
        save_map(root/'input.npz', z, obstacle=obstacle, start_xy=[1., 1.])
        before = (root/'input.npz').read_bytes()
        for mode in ('true', 'plus_half'):
            result = export_gazebo(root/'input.npz', root/mode, debris_box_height=mode)
            tree = ET.parse(root/mode/'world.sdf')
            labels, _ = label(obstacle)
            for i, region in enumerate(find_objects(labels), 1):
                model = tree.find(f"world/model[@name='obstacle_{i}']")
                pose = np.fromstring(model.findtext('pose'), sep=' ')
                sizes = [np.fromstring(s.text, sep=' ') for s in model.findall('.//box/size')]
                assert len(sizes) == 2 and np.array_equal(sizes[0], sizes[1])
                actual_top, actual_bottom = pose[2]+sizes[0][2]/2, pose[2]-sizes[0][2]/2
                values = z[region][labels[region] == i]
                assert np.isclose(actual_top, values.max()+(0. if mode == 'true' else .5))
                assert np.isclose(actual_bottom, values.min()-.1)
                assert np.array_equal(sizes[0][:2], [s.stop-s.start for s in region]*np.array([.5, .5]))
            if mode == 'true':
                assert result['debris_box_height'] == 'true'
                assert 'task032 debris_box_height=true' in (root/mode/'world.sdf').read_text()
        export_gazebo(root/'input.npz', root/'default')
        assert {p.name: p.read_bytes() for p in (root/'default').iterdir()} == {p.name: p.read_bytes() for p in (root/'plus_half').iterdir()}
        assert (root/'input.npz').read_bytes() == before
    print('5 PASS: true world box tops equal component maximum; lower edges/footprints/collision-visual sizes and truth NPZ unchanged')


def test_prior_variants():
    z = np.indices((32, 32)).sum(axis=0)*.01
    water = np.zeros(z.shape, bool); water[:2] = True
    nodata = np.zeros(z.shape, bool); nodata[:, -1] = True
    rock = np.zeros(z.shape, bool); rock[8, 8] = True
    terrain = dict(elev=z, rock=rock, water=water, nodata=nodata)
    scenario = dict(tmap=TraversabilityMap(z, rock | water | nodata), terrain=terrain,
                    patch_index=100, raw_elev=z, start=(10, 10))
    before = [v.tobytes() for v in terrain.values()]
    assert prior_variant(scenario)[0] is scenario
    a, stats = prior_variant(scenario, 'perturbed'); b, _ = prior_variant(scenario, 'perturbed')
    assert a['tmap'].elev.tobytes() == b['tmap'].elev.tobytes()
    assert a['tmap'].elev.tobytes() != prior_variant(dict(scenario, patch_index=101), 'perturbed')[0]['tmap'].elev.tobytes()
    mask = water | nodata
    assert np.array_equal(a['tmap'].elev[mask], z[mask])
    assert np.array_equal(a['terrain']['rock'], rock)
    # Independently sum the prescribed hills at a single valid grid centre.
    rng = np.random.default_rng(np.random.SeedSequence([32, 100]))
    terms = []
    for _ in range(20):
        centre = [rng.uniform(0., 15.5), rng.uniform(0., 15.5)]
        amplitude = rng.uniform(-.3, .3)
        terms.append(amplitude*np.exp(-sum((v-5.)**2 for v in centre)/50.))
    assert np.isclose(a['tmap'].elev[10, 10]-z[10, 10], sum(terms), atol=1e-15, rtol=0)
    assert stats['max_abs_m'] > 0 and stats['mean_abs_m'] > 0
    none, _ = prior_variant(scenario, 'none')
    assert np.all(none['tmap'].elev == np.median(z[~mask]))
    assert not none['terrain']['rock'].any()
    assert np.array_equal(none['terrain']['water'], water) and np.array_equal(none['terrain']['nodata'], nodata)
    assert [v.tobytes() for v in terrain.values()] == before
    print('6 PASS: SeedSequence reproducibility, distinct patch seeds, preserved sea/nodata, flat none and immutable input arrays')


def test_cli():
    from ros2_jazzy.gz_checks import lidar_checks
    with tempfile.TemporaryDirectory() as tmp:
        for sensors in ('legacy', 'lidar_real', 'lidar_real+depth2'):
            for variant in ('exact', 'perturbed', 'none'):
                manifest = lidar_checks.prepare_cases(Path(tmp)/(sensors+variant), map_method='fine', sensors=sensors,
                    obstacle_reference='local', debris_box_height='true', prior_variant_name=variant)
                assert manifest['obstacle_reference_mode'] == 'local'
                assert manifest['debris_box_height'] == 'true' and manifest['prior_variant'] == variant
                assert '1.5m' in manifest['obstacle_reference'] and 'local' in manifest['height_definition']
        with patch('sys.argv', ['lidar_checks.py', '--map', 'fine', '--obstacle-reference', 'local',
                                '--debris-box-height', 'true', '--prior-variant', 'none']), patch.object(lidar_checks, 'run_checks') as run:
            lidar_checks.main()
            assert run.call_args.kwargs['obstacle_reference'] == 'local'
            assert run.call_args.kwargs['debris_box_height'] == 'true'
            assert run.call_args.kwargs['prior_variant_name'] == 'none'
        for options in (dict(obstacle_reference='bad'), dict(obstacle_reference='local')):
            try:
                make_pointcloud_map(np.zeros((12, 12)), **options)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid/coarse local accepted')
    # Exercise the actual ROS parameter command extension, without ROS import.
    tree = ast.parse(Path(lidar_checks.__file__).read_text())
    extension = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and 'obstacle_reference_mode' in ast.unparse(n.test)
                     and any(isinstance(k, ast.Name) and k.id == 'commands' for statement in n.body for k in ast.walk(statement)))
    commands = [['python', 'lidar_planner.py']]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[extension], type_ignores=[])), '<ROS command>', 'exec'),
         dict(commands=commands, manifest=dict(obstacle_reference_mode='local')))
    assert commands[0][-2:] == ['-p', 'obstacle_reference:=local']
    planner = ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    node_main = next(n for n in ast.parse(planner.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    import argparse
    import sys
    from types import SimpleNamespace
    calls = []
    dummy = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kwargs: calls.append(kwargs), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kwargs: (calls.append(kwargs) or dummy))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node_main], type_ignores=[])), str(planner), 'exec'), scope)
    scope['main'](['--obstacle-reference', 'local', '--ground-estimate', 'non_obstacle', '--ros-args', '-p', 'use_sim_time:=true'])
    assert calls == [dict(args=['--ros-args', '-p', 'use_sim_time:=true']),
                     dict(ground_estimate='non_obstacle', obstacle_reference='local')]
    # Execute the production initial-prior branch: exact paths must not leak
    # into a none/perturbed trial. No sensor or ROS process is involved.
    initial_branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and 'prior_variant' in ast.unparse(n.test)
                          and any(isinstance(k, ast.Name) and k.id == 'mission' for statement in n.body for k in ast.walk(statement)))
    z = np.zeros((24, 24)); blank = np.zeros(z.shape, bool)
    sc = dict(tmap=TraversabilityMap(z, blank), terrain=dict(elev=z, rock=blank, water=blank, nodata=blank), patch_index=100)
    mission = dict(path=[[999., 999.]])
    context = dict(manifest=dict(prior_variant='none'), prior=sc, case={}, prior_variant=prior_variant,
                   mission=mission, meta=dict(start=[5, 5], stops=[[10, 10]]), np=np, RESOLUTION=RESOLUTION,
                   save_run=lambda: None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[initial_branch], type_ignores=[])), '<initial prior>', 'exec'), context)
    assert mission['path'][0] == [2.5, 2.5] and mission['path'][-1] == [5., 5.]
    assert context['case']['prior_variant_statistics']['variant'] == 'none'
    print('configuration PASS: factory/CLI/manifest/ROS command forwarding; invalid coarse/local rejected; Gazebo not started')


if __name__ == '__main__':
    with patch.dict(os.environ):
        for key in ('THESIS_FINE_PROTOCOL', 'THESIS_ONLY_PATCH', 'THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S'):
            os.environ.pop(key, None)
        for test in (test_default_bytes, test_clouds, test_unknown_and_multi, test_true_boxes, test_prior_variants, test_cli):
            test()
    print('all prior-free tests passed; requirement 7 is checked by the separate complete test-module run')
