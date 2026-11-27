"""Stage 081B geometry and registration checks without ROS or Gazebo."""

import numpy as np

from experiments.drone_map_localizability import (
    SPEC, median_coarsen, scan_sites, select_crops, terrain_reference,
)
from experiments.drone_map_rays import RasterTerrain
from experiments.localizability_rays import LandmarkSurfaces, RayScanner, TerrainMesh
from experiments.localizability_scan import evaluate_scan, measurement_noise
from experiments.offline_localization import (
    MIN_INFORMATION, MapRegistration, MissingLocalizationPackages, load_backends,
)


def test_legacy_ranges():
    rng = np.random.default_rng(101)
    z = rng.uniform(-.1, 1.5, (21, 26))
    legacy, scaled = RayScanner(TerrainMesh(z), SPEC), RayScanner(RasterTerrain(z, .5), SPEC)
    for origin in ([4.1, 7.7, .9], [11., 1.61, .44], [.12, .21, -.4], [-2., -5., -.3]):
        np.testing.assert_allclose(scaled.ground_ranges(np.array(origin)),
                                   legacy.ground_ranges(np.array(origin)), rtol=0, atol=1e-10)
    print('1 PASS: variable grid agrees with 079 at 0.5 m, including entry from outside')


def test_missing_ranges():
    z = np.zeros((32, 32))
    z[12:19, 12:19] = np.nan
    mesh = RasterTerrain(z, .1, origin_xy=(.05, .05))
    east = np.array([[1., 0.]])
    slopes = np.array([[-.5, -.25, -.125]])
    actual = mesh.ranges_xy((.05, 1.55, .5), east, slopes, 5.)
    np.testing.assert_allclose(actual, [[1., 2., np.inf]])
    actual = mesh.ranges_xy((.55, 1.55, .5), east, slopes, 5.)
    np.testing.assert_allclose(actual, [[np.inf, 2., np.inf]])
    assert np.isnan(mesh.height(1.55, 1.55)) and np.isnan(mesh.height(3.25, 1.55))
    assert (1.75, 1.75) not in {(x, y) for x, y, *_ in scan_sites(mesh, (3.2, 3.2))}
    print('2 PASS: no hits in holes or outside; finite triangles past holes remain visible')


def test_information_at_10cm():
    try:
        _, _, backend = load_backends()
    except MissingLocalizationPackages as exc:
        print(f'3 SKIP: {exc}')
        return
    pos = (12.75, 12.75)
    x, y = np.ogrid[:25:.1, :25:.1]
    rough = .7*np.sin(.79*x+.2*y)+.5*np.cos(.96*y-.17*x)+.4*np.sin(1.05*x-1.14*y)
    for name, z in [('plane', np.zeros_like(rough)), ('rough', rough)]:
        mesh = RasterTerrain(z, .1, origin_xy=(.05, .05))
        scanner = RayScanner(mesh, SPEC)
        pose = scanner.pose(*pos)
        scan = scanner.scan(pose[:3, 3], LandmarkSurfaces([]), measurement_noise('test081', pos, scanner.slopes.shape))
        row = evaluate_scan(MapRegistration(terrain_reference(mesh), backend), scan, pose)
        lam = row['minimum_scaled_eigenvalue']
        assert (lam > MIN_INFORMATION) == (name == 'rough'), (name, row)
        assert row['converged'], row
        print(f'3 PASS: {name} at 0.1 m, minimum eigenvalue {lam:.6f}, status={row["status"]}')


def test_coarsening():
    z = np.arange(121., dtype=float).reshape(11, 11)
    z[:5, :5] = np.nan
    z[0, 5] = np.nan
    np.testing.assert_array_equal(median_coarsen(z),
                                  [[np.nan, np.nanmedian(z[:5, 5:10])],
                                   [np.median(z[5:10, :5]), np.median(z[5:10, 5:10])]])
    print('4 PASS: medians of finite 5 × 5 blocks, all-empty stays empty, incomplete block omitted')


def test_crop_sampling():
    z = np.zeros((35, 40))
    z[:8] = -.01
    z[17:20, 20:30] = np.nan
    cuts = select_crops(z, (7, 10))
    assert len({tuple(pair) for pair in cuts}) == 5
    for i, j in cuts:
        assert (z[i:i+7, j:j+10] >= 0).all()
    np.testing.assert_array_equal(cuts, select_crops(z, (7, 10)))
    print('crop PASS: five deterministic distinct land-only origins')


if __name__ == '__main__':
    test_legacy_ranges()
    test_missing_ranges()
    test_information_at_10cm()
    test_coarsening()
    test_crop_sampling()
    print('all drone map localizability tests passed (optional backend skip shown above if absent)')
