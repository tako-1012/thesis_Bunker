"""Offline first-hit, localization, and task075/078 metadata checks."""

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from experiments.localizability_rays import LandmarkSurfaces, RayScanner, TerrainMesh
from experiments.localizability_scan import (
    PATCHES, comparison_status, compare_recorded, evaluate_scan, initial_path, measurement_noise,
    path_lengths, placement, prepare_manifest, recorded_index, sample_path, selected_scenario,
)
from experiments.offline_localization import (
    MIN_INFORMATION, MapRegistration, MissingLocalizationPackages, load_backends,
)
from ros2_jazzy.gz_checks import lidar_checks
from tapp.landmark_world import Landmark, landmark_mask, landmark_points, terrain_points
from tapp.sensor_geometry import REAL_MOUNTS


def test_shadow_and_spec():
    spec = lidar_checks.LidarSpec(min_range_m=.9)
    mesh = TerrainMesh(np.zeros((121, 121)))
    scanner = RayScanner(mesh, spec)
    _, _, height = REAL_MOUNTS['lidar'].xyz
    origin = scanner.pose(20., 20.)[:3, 3]
    np.testing.assert_allclose(origin, [19.76, 20., height])
    pitch_rad = np.arctan2(scanner.directions[0, :, 2], np.hypot(*scanner.directions[0, :, :2].T))
    np.testing.assert_allclose(np.rad2deg(pitch_rad), np.linspace(-15., 15., 16))
    heading = np.unwrap(np.arctan2(scanner.directions[:, 0, 1], scanner.directions[:, 0, 0]))
    np.testing.assert_allclose(heading, np.linspace(-np.pi, np.pi, 1800))
    noise = np.zeros(scanner.slopes.shape)
    ground = scanner.ground_ranges(origin)
    plane = scanner.scan(origin, LandmarkSurfaces([]), noise, ground=ground)
    assert plane.shape == (16, 1800, 3)
    beam, column = 3, 900  # -9 degrees, almost +x
    expected_ground = height/-np.sin(pitch_rad[beam])
    assert abs(np.linalg.norm(plane[beam, column])-expected_ground) < 1e-10
    assert np.isnan(plane[7, column]).all()  # -1 degree, ground past 30 m
    assert np.isnan(plane[8:, column]).all()  # above horizon

    box = Landmark('shadow', 'box', 24., 20., 0., 1., 2., 1.2, 0.)
    tube = replace(box, name='cylinder', shape='cylinder', depth_m=1.)
    for obj in (box, tube):
        shadow = scanner.scan(origin, LandmarkSurfaces([obj]), noise, ground=ground)
        face = origin+shadow[beam, column]
        assert 23.49 < face[0] < 23.51
        assert 0. < face[2] < obj.height_m
        assert np.linalg.norm(shadow[beam, column]) < .6*expected_ground
        np.testing.assert_array_equal(shadow[beam, 450], plane[beam, 450])
    too_close = replace(box, x_m=origin[0]+.7, height_m=2.)
    shadow = scanner.scan(origin, LandmarkSurfaces([too_close]), noise, ground=ground)
    assert np.isnan(shadow[beam, column]).all()  # near object occludes farther terrain

    shifted = scanner.scan(origin, LandmarkSurfaces([]), noise+1., ground=ground)
    assert abs(np.linalg.norm(shifted[beam, column])-expected_ground-.02) < 1.e-10
    print('1 PASS: 16 × 1800 rays, ±15°, mount, 0.9–30 m span, 0.02 m radial noise and box/cylinder shadows')


def test_triangle_intersections():
    """Check a ridge with an independent triangle-plane/barycentric oracle."""
    elevation = np.random.default_rng(101).uniform(-.1, .65, (8, 8))
    mesh = TerrainMesh(elevation)
    faces = []
    for i, j in np.ndindex(7, 7):
        a, b, c, d = [(x/2, y/2, np.round(elevation[x, y], 4))
                      for x, y in [(i, j), (i+1, j), (i+1, j+1), (i, j+1)]]
        faces.extend((np.array([a, b, c]), np.array([a, c, d])))
    rng = np.random.default_rng(102)
    az = rng.uniform(-np.pi, np.pi, 110)
    xy = np.column_stack([np.cos(az), np.sin(az)])
    slopes = rng.uniform(-.8, .1, size=(len(xy), 1))
    for origin in [np.array([1.7, 1.4, .87]), np.array([4.1, 1.8, .52]), np.array([.1, .2, -.3])]:
        expected = np.full(len(xy), np.inf)
        for i, direction in enumerate(np.column_stack((xy, slopes))):
            for triangle in faces:
                a, b, c = triangle
                matrix = np.column_stack((direction, a-b, a-c))
                if abs(np.linalg.det(matrix)) < 1e-12:
                    continue
                t, u, v = np.linalg.solve(matrix, a-origin)
                if 0 <= t <= 6 and u >= 0 and v >= 0 and u+v <= 1:
                    expected[i] = min(t, expected[i])
        actual = mesh.ranges_xy(origin, xy, slopes, 6).ravel()
        np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=0)
    print('1 PASS: first mesh hit agrees with independent triangle oracle, including outside origin and multiple surfaces')


def test_information():
    try:
        _, _, backend = load_backends()
    except MissingLocalizationPackages as exc:
        print(f'2 SKIP: {exc}')
        return
    zenith = np.zeros((141, 141))
    scanner = RayScanner(TerrainMesh(zenith), lidar_checks.LidarSpec(min_range_m=.9))
    pose = scanner.pose(35., 35.)
    ground = scanner.ground_ranges(pose[:3, 3])
    noise = measurement_noise(PATCHES[0], (35., 35.), scanner.slopes.shape)
    ground_points = terrain_points(zenith)
    objects = [
        Landmark(f'box{i}', 'box', 35.+6.*np.cos(az), 35.+6.*np.sin(az),
                 0., 1.2, 1.4, 2.8, .4*az)
        for i, az in enumerate(np.linspace(0., 2*np.pi, 12, endpoint=False))
    ]
    for case in ([], objects):
        reference = np.concatenate([ground_points, *(landmark_points(o).astype(np.float32) for o in case)])
        scan = scanner.scan(pose[:3, 3], LandmarkSurfaces(case), noise, ground=ground)
        info = evaluate_scan(MapRegistration(reference, backend), scan, pose)
        if not case:
            assert info['minimum_scaled_eigenvalue'] <= MIN_INFORMATION
            assert info['weak_axis'] in ('alongshore', 'cross_shore')
            assert abs(info['weak_tz']) < .05
        else:
            assert info['minimum_scaled_eigenvalue'] > MIN_INFORMATION and info['converged']
        print(f'2 PASS: {"landmarks" if case else "plane"} λmin={info["minimum_scaled_eigenvalue"]:.6f}, '
              f'weak={info["weak_axis"]}, status={info["status"]}')


def test_manifest(root):
    prepared = prepare_manifest(PATCHES[0], 10, 1)
    case, scenario = selected_scenario(prepared)
    assert case['patch'] == PATCHES[0] and prepared['lidar_spec']['min_range_m'] == .9
    assert prepared['landmark_world']['seed'] == 1 and prepared['landmark_world']['density_per_ha'] == 10
    assert 'landmarks' not in case  # the actual 075 CLI prepare-only stops before the geometry step
    truth, prior = lidar_checks.case_world_inputs(case, scenario, prepared)
    area, objects = placement(truth, case, scenario, prepared)
    footprint = landmark_mask(truth['tmap'].shape, objects)
    path = initial_path(prior, scenario, objects, footprint)
    assert path[0] == (np.array(scenario['start'])*.5).tolist()
    actual_xyz = np.concatenate([terrain_points(truth['tmap'].elev),
                                *(landmark_points(o).astype(np.float32) for o in objects)])
    geometry = [asdict(obj) for obj in objects]

    # Exercise the production Gazebo runner's pure world-creation step separately.
    raw = root/'raw'/case['patch']
    raw.mkdir(parents=True)
    _, _, made = lidar_checks.add_landmark_world(raw, case, scenario, prepared['landmark_world'], truth, prior)
    assert objects == made and case['landmarks'] == geometry and case['landmark_land_area_m2'] == area
    prepared['cases'] = [dict(case, run_folder=str(raw.relative_to(root)))]
    mock = root/'manifest.json'
    mock.write_text(json.dumps(prepared))
    (raw/'mission.json').write_text(json.dumps({'path': path}))
    digest = hashlib.sha256(actual_xyz).hexdigest()
    records = recorded_index([root])
    candidates = records[(case['patch'], 10, 1)]
    checks = compare_recorded(candidates, geometry, path, digest)
    assert all(checks[0][k] == 'match' for k in ('placement', 'path', 'reference'))
    assert comparison_status(compare_recorded(candidates, geometry[1:], path, digest), 'placement') == 'mismatch'
    assert comparison_status(compare_recorded([], geometry, path, digest), 'reference') == 'unavailable'
    print(f'3 PASS: 078 prepare-only inputs, {len(objects)} placements and full reference XYZ match the 075 world builder')


def test_route_intervals():
    distances, xy = sample_path([[0, 0], [0, 0], [1.4, 0], [1.4, 1.2]])
    np.testing.assert_allclose(distances, [0., 1., 2., 2.6])
    np.testing.assert_allclose(xy, [[0., 0.], [1., 0.], [1.4, .6], [1.4, 1.2]])
    rows = [dict(distance_m=x, converged=True, at_or_below_1=1) for x in distances]
    del rows[1]['at_or_below_1']
    rows[1]['converged'] = False
    summary = path_lengths(rows)
    np.testing.assert_allclose([summary[k] for k in ('path_m', 'weak_m', 'max_weak_m', 'unavailable_m',
                                                     'not_converged_m')], [2.6, 1.6, 1., 1., 1.])
    assert path_lengths([])['path_m'] is None
    print('route PASS: exact end retained; a missing sample breaks weak intervals')


def main():
    test_shadow_and_spec()
    test_triangle_intersections()
    test_information()
    with TemporaryDirectory() as temp:
        test_manifest(Path(temp))
    test_route_intervals()
    print('all localizability scan tests passed (optional backend skip shown above if absent)')


if __name__ == '__main__':
    main()
