"""Independent checks for task 081 synthetic and published grids."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import laspy
import numpy as np

from experiments.drone_map_downsample import read_cloud

with TemporaryDirectory() as folder:
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.scales = [0.001, 0.001, 0.001]
    header.offsets = [655213, 3725181, 77]
    record = laspy.LasData(header)
    raw = np.array([[0, 0, 0], [49, 49, 10], [50, 49, 30], [99, 99, 50],
                    [100, 0, 20], [300, 100, 90]])
    record.X, record.Y, record.Z = raw.T
    colors = np.array([[0, 2, 4], [3, 5, 7], [9, 10, 11],
                       [20, 21, 22], [30, 31, 32], [40, 41, 42]], dtype=np.uint16)
    record.red, record.green, record.blue = colors.T
    path = Path(folder) / "tiny.laz"
    record.write(path, laz_backend=laspy.LazBackend.Lazrs)
    cloud, grid, meta = read_cloud(path, chunk_points=1)
    np.testing.assert_array_equal(cloud["point_count"], [2, 1, 1, 1, 1])
    np.testing.assert_allclose(cloud["xyz"][0], [0.0245, 0.0245, 0.005])
    np.testing.assert_allclose(cloud["rgb"][0], [1.5, 3.5, 5.5])
    np.testing.assert_allclose(cloud["xyz"][1], [0.050, 0.049, 0.030])
    np.testing.assert_array_equal(grid["point_count"], [[4, 1, 0, 0], [0, 0, 0, 1]])
    np.testing.assert_allclose([grid[name][0, 0] for name in ("z_min", "z_max", "z_median")],
                               [0, 0.050, 0.020])
    assert np.isnan(grid["z_median"][0, 2])
    np.testing.assert_allclose(meta["utm_min_xyz_m"], header.offsets, atol=1e-9, rtol=0)
    print("synthetic LAZ: voxel boundaries, cross-chunk means and mean RGB, exact even median, empty cells PASS")

directory = Path("data/drone_odm/2024-04-24")
source = Path.home() / "thesis_data/drone_odm/2024-04-24"
info = json.loads((directory / "summary.json").read_text())
for name, record in info["source_files"].items():
    with (source / name).open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"]
    assert (source / name).stat().st_size == record["bytes"]
print("all six original SHA-256 values still match")

point_sum = voxel_sum = 0
for part in info["point_cloud_parts"]:
    path = directory / part["name"]
    assert path.stat().st_size == part["bytes"] < 5_000_000
    with np.load(path, allow_pickle=False) as cloud:
        xyz, count, rgb = (cloud[name] for name in ("xyz", "point_count", "rgb"))
        assert xyz.dtype == rgb.dtype == np.float32 and count.dtype == np.uint32
        assert xyz.shape == rgb.shape == (len(count), 3)
        assert (count > 0).all() and np.all((0 <= rgb) & (rgb <= 65535))
        assert np.all((xyz >= 0) & (xyz <= np.array(info["local_max_xyz_m"]) + 0.000004))
        assert cloud["epsg"] == 32652
        np.testing.assert_array_equal(cloud["origin_utm_xyz_m"], info["utm_min_xyz_m"])
        point_sum += int(count.sum(dtype=np.uint64))
        voxel_sum += len(count)
assert point_sum == info["original_point_count"] and voxel_sum == info["voxel_count"]

with np.load(directory / "elevation_10cm.npz", allow_pickle=False) as grid:
    count = grid["point_count"].ravel()
    ny, nx = grid["point_count"].shape
    occupied = count > 0
    lows, highs, medians = [grid[name].ravel() for name in ("z_min", "z_max", "z_median")]
    assert (ny, nx) == tuple(info["elevation_shape_yx"])
    assert count.sum(dtype=np.uint64) == point_sum
    assert np.count_nonzero(~occupied) == info["empty_elevation_cells"]
    assert all(np.array_equal(np.isnan(heights), ~occupied) for heights in (lows, highs, medians))
    assert np.all(lows[occupied] <= medians[occupied]) and np.all(medians[occupied] <= highs[occupied])

    candidates = np.flatnonzero(occupied)
    samples = np.unique(np.r_[candidates[np.linspace(0, len(candidates) - 1, 9, dtype=int)],
                              np.argmax(count), np.argmin(np.where(occupied, count, np.inf))])
    from_raw = {cell: [] for cell in samples}
    independent_counts = np.zeros(nx * ny, dtype=np.int64)
    with laspy.open(source / "odm_georeferenced_model.laz", laz_backend=laspy.LazBackend.Lazrs) as reader:
        assert np.all(reader.header.scales == 0.001)
        raw_orig = np.rint((grid["origin_utm_xyz_m"] - reader.header.offsets) /
                           reader.header.scales).astype(np.int64)
        measured_min = np.full(3, np.iinfo(np.int64).max)
        measured_max = np.full(3, np.iinfo(np.int64).min)
        for points in reader.chunk_iterator(750_000):
            x, y, z = raw_xyz = tuple(np.asarray(v, dtype=np.int64)
                                      for v in (points.X, points.Y, points.Z))
            measured_min = np.minimum(measured_min, [v.min() for v in raw_xyz])
            measured_max = np.maximum(measured_max, [v.max() for v in raw_xyz])
            cell = ((y - raw_orig[1]) // 100) * nx + (x - raw_orig[0]) // 100
            independent_counts += np.bincount(cell, minlength=nx * ny)
            for hit in np.unique(cell[np.isin(cell, samples)]):
                from_raw[hit].append((z[cell == hit] - raw_orig[2]) * 0.001)
        np.testing.assert_array_equal(measured_min, raw_orig)
        np.testing.assert_allclose(measured_max * reader.header.scales + reader.header.offsets,
                                   info["utm_max_xyz_m"], rtol=0, atol=1e-9)
    np.testing.assert_array_equal(independent_counts, count)
    for cell, chunks in from_raw.items():
        raw_z = np.concatenate(chunks)
        assert len(raw_z) == count[cell]
        np.testing.assert_allclose([lows[cell], highs[cell], medians[cell]],
                                   [raw_z.min(), raw_z.max(), np.median(raw_z)],
                                   rtol=0, atol=3e-8)
    print(f"original LAZ replay: both bounds, counts of all {nx * ny:,} cells, and height statistics in {len(samples)} cells PASS")
print(f"NPZ: {voxel_sum:,} voxels, both sums are {point_sum:,} points, size/CRS/float32 PASS")
