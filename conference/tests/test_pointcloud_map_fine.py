"""Task023 fixed synthetic box/radius tests; ROS and Gazebo are not required."""

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
from unittest.mock import patch
import numpy as np
from scipy.ndimage import binary_dilation

from tapp.config import RESOLUTION
from tapp.pointcloud_map import PointCloudMap
from tapp.pointcloud_map_fine import PointCloudMapFine, FINE_RESOLUTION, RATIO, coarse_overlap
from tapp.traversability import TraversabilityMap
from tapp.footprint import inflate_steep
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map

ROOT = Path(__file__).resolve().parents[1]


def box_cloud(seed):
    """0.4m-high box, footprint [4.75,5.25]^2; 0.02m RADIAL range noise.

    Dense top returns retain the true box; sparse side returns cross coarse
    borders. Ground returns outside the box keep the terrain-height statistic
    distinct from evidence for a vertical obstacle. This is an artificial
    multi-surface fixture, not a ray/occlusion or VLP-16 simulation.
    """
    pose = np.array([2., 2., 0., 0., 0., 0.])
    top = [[x, y, .4] for x in [4.9, 5., 5.1] for y in [4.9, 5., 5.1] for _ in range(3)]
    sides = []
    for a in [4.8, 4.9, 5., 5.1, 5.2]:
        for _ in range(2):
            sides.extend([[4.75, a, .4], [5.25, a, .4], [a, 4.75, .4], [a, 5.25, .4]])
    ground = [[x, y, 0.] for x, y in [(4.5, 5), (5.5, 5), (5, 4.5), (5, 5.5)] for _ in range(16)]
    world = np.asarray(top+sides+ground)
    local = world-pose[:3]-[0, 0, .8]
    rng = np.random.default_rng(seed)
    local += local/np.linalg.norm(local, axis=1)[:, None]*rng.normal(0, .02, (len(local), 1))
    return local, pose


def clearance_oracle(raw, *, coarse):
    """Exhaustively measure query points against every closed obstacle square.

    Coordinates are integer multiples of 0.05m, so no distance rounding or
    floating tolerance affects the <=0.5m contact boundary.
    """
    if coarse:
        shape = tuple(n//RATIO for n in raw.shape)
        query = np.indices(shape)*2*RATIO
    else:
        shape = raw.shape
        query = np.indices(shape)*2+1-RATIO
    blocked = np.zeros(shape, bool)
    for cell in np.argwhere(raw):
        lo = 2*cell-RATIO
        hi = lo+2
        dx = np.maximum(np.maximum(lo[0]-query[0], query[0]-hi[0]), 0)
        dy = np.maximum(np.maximum(lo[1]-query[1], query[1]-hi[1]), 0)
        blocked |= dx*dx+dy*dy <= 100  # (0.5m / 0.05m)**2
    return blocked


def test_flat():
    z = np.zeros((25, 25))
    fine = PointCloudMapFine(z)
    world = np.array([[x*.5, y*.5, 0.] for x in range(6, 15) for y in range(6, 15)])
    fine.update(world-[2, 2, .8], [2, 2, 0, 0, 0, 0])
    assert not fine.fine_obstacle.any() and not fine.snapshot()[2].any()
    assert fine.seen.sum() == len(world)
    assert not fine.seen[0, 0]
    print('flat: no obstacles; only hit cells become known')


def test_noisy_box():
    counts = []
    for seed in range(100, 105):
        cloud, pose = box_cloud(seed)
        coarse = PointCloudMap(np.zeros((40, 40)))
        fine = PointCloudMapFine(np.zeros((40, 40)))
        coarse.update(cloud, pose)
        fine.update(cloud, pose)
        assert coarse.elev.tobytes() == fine.elev.tobytes()
        assert coarse.tm.cost.tobytes() == fine.tm.cost.tobytes()
        assert coarse.seen.tobytes() == fine.seen.tobytes()
        assert coarse.lethal[10, 10] and fine.lethal[10, 10]
        outside = np.ones((40, 40), bool)
        outside[10, 10] = False
        old_count = int((coarse.lethal & outside).sum())
        new_count = int((fine.lethal & outside).sum())
        assert new_count < old_count, (seed, old_count, new_count)
        counts.append((seed, old_count, new_count))
        # Cost formula, prior inflation, and steep-cell dilation remain exact.
        terrain = TraversabilityMap(fine.elev, fine.raw_obstacle)
        expected = inflate_steep(terrain) | clearance_oracle(fine.fine_obstacle, coarse=True)
        assert np.array_equal(fine.lethal, expected)
    print('noisy box fixture (seed, coarse outside lethal, fine outside lethal):', counts)
    print('box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged')


def test_one_dilation():
    fine = PointCloudMapFine(np.zeros((30, 30)))
    # Isolate the geometric operation, independent of slope and beam sampling.
    key = int(np.ravel_multi_index((70, 72), fine.fine_shape))
    fine._add_obstacles([key])
    raw = fine.fine_obstacle.copy()
    expected = clearance_oracle(raw, coarse=False)
    assert np.array_equal(fine.fine_inflated, expected)
    assert np.array_equal(fine._inflated_coarse, clearance_oracle(raw, coarse=True))
    assert np.array_equal(fine.detected_obstacle, coarse_overlap(raw))
    blocked = fine._inflated_coarse
    fine._add_obstacles([key])
    assert np.array_equal(fine.fine_inflated, expected)  # Repeated observations cannot grow a second halo.
    obstacle_lo = -.25+np.array([70, 72])*.1
    obstacle_hi = obstacle_lo+.1
    for cell in np.argwhere(blocked):
        centre = cell*.5
        separation = np.maximum(np.maximum(obstacle_lo-centre, centre-obstacle_hi), 0)
        assert np.linalg.norm(separation) <= .5+1e-12
    other = int(np.ravel_multi_index((75, 76), fine.fine_shape))
    fine._add_obstacles([other])
    expected = clearance_oracle(fine.fine_obstacle, coarse=False)
    assert np.array_equal(fine.fine_inflated, expected)
    assert np.array_equal(fine._inflated_coarse, clearance_oracle(fine.fine_obstacle, coarse=True))
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary)/'map.npz'
        fine.save(path)
        with np.load(path, allow_pickle=False) as data:
            restored = np.unpackbits(data['fine_inflated_bits'])[:np.prod(data['fine_shape'])].reshape(data['fine_shape'])
            assert np.array_equal(restored, expected)
        assert path.stat().st_size < 5_000_000
    print('one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed')


def test_side_spill_and_centre_clearance():
    fine = PointCloudMapFine(np.zeros((30, 30)))
    # The true side is x=5.25. Side hits at x=5.35 spill by 0.1m into the
    # adjacent coarse cell; ground support avoids unrelated steep labels.
    world = np.array([[5.35, 5., .4]]*3+[[5.5, 5., 0.]]*16)
    fine.update(world-[2, 2, .8], [2, 2, 0, 0, 0, 0])
    assert fine.detected_obstacle[11, 10] and fine.lethal[11, 10]
    assert not fine.lethal[12, 10]  # x=6.0 is 0.65m from the square's edge.
    x, y = np.mgrid[-5:6, -5:6]
    previous = coarse_overlap(binary_dilation(fine.fine_obstacle, structure=x*x+y*y <= 25))
    assert previous[12, 10]  # The old area-overlap projection caused the regression.
    assert np.array_equal(fine.lethal, clearance_oracle(fine.fine_obstacle, coarse=True))
    # Check all 25 fine-cell phases within a coarse cell, plus map clipping.
    seeds = [(50+i, 50+j) for i in range(5) for j in range(5)]
    seeds += [(0, 0), (0, 149), (149, 0), (149, 149)]
    for cell in seeds:
        mapper = PointCloudMapFine(np.zeros((30, 30)))
        mapper._add_obstacles([int(np.ravel_multi_index(cell, mapper.fine_shape))])
        expected = clearance_oracle(mapper.fine_obstacle, coarse=True)
        assert np.array_equal(mapper._inflated_coarse, expected), cell
    # Diagonal clearance must use a square edge/corner, not its centre or
    # a scalar half-cell subtraction from an EDT centre distance.
    mapper = PointCloudMapFine(np.zeros((30, 30)))
    mapper._add_obstacles([int(np.ravel_multi_index((47, 50), mapper.fine_shape))])
    assert np.hypot(.5, .2) > .5 and np.hypot(.45, .15) < .5
    assert mapper._inflated_coarse[10, 10]
    assert not mapper._inflated_coarse[10, 11]
    print('centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked')
    print('boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed')


def test_legacy_bytes():
    cloud, pose = box_cloud(100)
    legacy = PointCloudMap(np.zeros((40, 40)))
    default = make_pointcloud_map(np.zeros((40, 40)))
    selected = make_pointcloud_map(np.zeros((40, 40)), map_method='coarse')
    assert type(default) is type(selected) is PointCloudMap
    outputs = []
    with tempfile.TemporaryDirectory() as temporary:
        for i, mapper in enumerate([legacy, default, selected]):
            # Wall time is nondeterministic even for two legacy calls: control it
            # in this fixture, then compare the entire update result as bytes.
            with patch('tapp.pointcloud_map.time.perf_counter', side_effect=[1., 1.25]):
                result = mapper.update(cloud, pose)
            path = Path(temporary)/(str(i)+'.npz')
            mapper.save(path)
            outputs.append((json.dumps(result, sort_keys=True).encode(), path.read_bytes()))
        assert outputs[0] == outputs[1] == outputs[2]
    print('legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical')


def test_selection_protocol():
    from ros2_jazzy.gz_checks.lidar_checks import prepare_cases
    reference_bytes = (ROOT/'results/lidar_fine/verification/legacy_manifest_before.json').read_bytes()
    reference_metadata = json.loads(reference_bytes)
    # Compare the old serializer output in the SAME runtime, independently of
    # the new function's output; machine provenance is not experiment data.
    import sys
    reference_metadata['input_environment'] = dict(python=sys.version, numpy=np.__version__)
    original = (json.dumps(reference_metadata, ensure_ascii=False, indent=2)+'\n').encode()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name, kwargs in [('default', {}), ('coarse', dict(map_method='coarse'))]:
            prepare_cases(root/name, patch_count=10, **kwargs)
            assert (root/name/'manifest.json').read_bytes() == original
        with patch.dict(os.environ, {'THESIS_REAL_TIME_FACTOR': '.3', 'THESIS_STALE_TIMEOUT_S': '1.0'}):
            fine = prepare_cases(root/'fine', patch_count=10, map_method='fine')
        reference = json.loads((ROOT/'results/gazebo_lidar/physical_10/manifest.json').read_text())
        assert fine['scenarios'] == reference['scenarios']
        assert fine['lidar_spec'] == reference['lidar_spec']
        assert fine['real_time_factor'] == reference['real_time_factor'] == .3
        assert fine['stale_timeout_s'] == reference['stale_timeout_s'] == 1.
        assert fine['terrain_visual'] == 'triangle_mesh' and fine['terrain_collision'] == 'heightmap'
        from tapp.real_beach import build_real
        from ros2_jazzy.gz_checks.lidar_map import matched_task022_maps
        name = reference['scenarios'][0]['patch']
        truth = build_real(name, 200, 0, debris=True, dataset='shizuoka_beach_las')
        prior = build_real(name, 200, 0, dataset='shizuoka_beach_las')
        matched_truth, matched_prior, source = matched_task022_maps(name, truth, prior)
        with np.load(ROOT/source, allow_pickle=False) as snapshot:
            assert matched_truth['tmap'].elev.tobytes() == snapshot['truth_elev'].tobytes()
            assert matched_prior['tmap'].elev.tobytes() == snapshot['prior_elev'].tobytes()
        with patch.dict(os.environ, {'THESIS_REAL_TIME_FACTOR': '1'}):
            try:
                prepare_cases(root/'invalid', map_method='fine')
            except ValueError:
                pass
            else:
                raise AssertionError('changed fine-run conditions accepted')
    print('selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol')


def test_docker_arguments():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        binary = root/'docker'
        binary.write_text('#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ["TASK023_DOCKER_ARGUMENTS"],"w").write(json.dumps(sys.argv[1:]))\n')
        binary.chmod(0o755)
        env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'], TASK023_DOCKER_ARGUMENTS=str(root/'args.json'))
        env.pop('THESIS_REAL_TIME_FACTOR', None)
        env.pop('THESIS_STALE_TIMEOUT_S', None)
        script = ROOT/'ros2_jazzy/gz_checks/run_lidar_checks.sh'
        for i, (args, factor, stale) in enumerate([([], '1', '0.5'), (['--map', 'coarse'], '1', '0.5'),
                                                  (['--map', 'fine'], '0.3', '1.0'), (['--map=fine'], '0.3', '1.0')]):
            subprocess.run(['bash', str(script), str(root/('out'+str(i))), *args], env=env, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            recorded = json.loads((root/'args.json').read_text())
            assert 'THESIS_REAL_TIME_FACTOR='+factor in recorded
            assert 'THESIS_STALE_TIMEOUT_S='+stale in recorded
            if args:
                assert recorded[-len(args):] == args
    print('Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings')


def test_map_audits_and_four_methods():
    from types import SimpleNamespace
    import pandas as pd
    from experiments.lidar_fine_report import map_audit, summarize
    from experiments.gz_online_batch_report import MEASURES
    from ros2_jazzy.gz_checks.lidar_checks import prepare_cases
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rock = np.zeros((10, 10), bool)
        rock[4, 4] = True
        terrain = dict(rock=rock, water=np.zeros_like(rock), nodata=np.zeros_like(rock))
        true_tm = TraversabilityMap(np.zeros(rock.shape), rock)
        seen = np.ones(rock.shape, bool)
        predicted = true_tm.lethal.copy()
        predicted[3, 4] = False
        predicted[6, 4] = True
        detected = rock.copy()
        detected[5, 4] = True
        path = root/'map.npz'
        np.savez_compressed(path, seen=seen, lethal=predicted, obstacle=detected)
        audit = map_audit(path, true_tm, terrain)
        assert audit['map_fp_cells'] == audit['map_fn_cells'] == 1
        assert audit['map_fp_box_adjacent_cells'] == 0
        assert audit['detector_fp_cells'] == audit['detector_fp_box_adjacent_cells'] == 1
        assert audit['detector_fn_cells'] == 0
        assert all(value is None for value in map_audit(root/'absent.npz', true_tm, terrain).values())
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with patch.dict(os.environ, {'THESIS_REAL_TIME_FACTOR': '.3', 'THESIS_STALE_TIMEOUT_S': '1.0'}):
            prepare_cases(root, patch_count=10, map_method='fine')
        with redirect_stdout(io.StringIO()):
            data, summary = summarize(root)
        cached = pd.read_csv(ROOT/'results/gazebo_lidar/physical_10/runs.csv', float_precision='round_trip')
        assert len(data) == 40 and len(summary) == 4
        for field in MEASURES:
            pd.testing.assert_series_equal(data.iloc[:30][field], cached[field], check_exact=True, check_dtype=False, check_names=False)
        new = data[data['mode'] == 'fine']
        assert new.completed.isna().all() and new.map_fp_cells.isna().all()
        assert new.map_update_s_max.isna().all() and new.status.eq('未実行').all()
        assert data[data['mode'] == 'lidar'].map_fp_cells.notna().all()
        assert data[data['mode'].isin(['fixed', 'online'])].map_fp_cells.isna().all()
        assert summary[summary['mode'] == 'fine'].completed.isna().all()
        assert not any('energy' in name.lower() for name in data.columns)
    print('map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes')


if __name__ == '__main__':
    test_flat()
    test_noisy_box()
    test_one_dilation()
    test_side_spill_and_centre_clearance()
    test_legacy_bytes()
    test_selection_protocol()
    test_docker_arguments()
    test_map_audits_and_four_methods()
    print('all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)')
