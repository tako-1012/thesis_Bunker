"""Convert the 2024-04-24 ODM LAZ to voxel centroids and an exact elevation grid."""

import argparse
from fractions import Fraction
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import tempfile

import laspy
import numpy as np

LAZ_NAME = "odm_georeferenced_model.laz"
SOURCE_NAMES = (
    LAZ_NAME, "coords.txt", "proj.txt", "odm_georeferenced_model.info.json",
    "odm_orthophoto.tif", "report.pdf",
)
EPSG = 32652
VOXEL_M = 0.05
CELL_M = 0.10
MAX_OUTPUT_BYTES = 30_000_000
MAX_FILE_BYTES = 5_000_000
ROWS_PER_PART = 160_000


def source_metadata(source):
    """Read the CRS sidecars and collect the source file checksums."""
    coords = (source / "coords.txt").read_text(encoding="utf-8").splitlines()
    proj = (source / "proj.txt").read_text(encoding="utf-8").strip()
    required = {"+proj=utm", "+zone=52", "+datum=WGS84", "+units=m"}
    tokens = set(proj.split())
    if coords[0].strip() != "WGS84 UTM 52N" or not required <= tokens or "+south" in tokens:
        raise ValueError("coords.txt and proj.txt must identify WGS 84 / UTM zone 52N.")
    easting, northing = map(float, coords[1].split())
    files = {}
    for name in SOURCE_NAMES:
        path = source / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        files[name] = {"sha256": digest, "bytes": path.stat().st_size}
    return {
        "epsg": EPSG,
        "crs": "WGS 84 / UTM zone 52N",
        "coords_crs": coords[0].strip(),
        "odm_xy_offset_m": [easting, northing],
        "proj": proj,
        "source_files": files,
    }


def voxel_indices(delta, ratios):
    # Bin the LAS integer coordinates before conversion to metres. This keeps
    # exact grid boundaries stable even when UTM northings are in the millions.
    return tuple(values * ratio.numerator // ratio.denominator
                 for values, ratio in zip(delta, ratios))


def read_cloud(path, chunk_points=500_000):
    """Accumulate exact integer sums and pack height samples for each XY cell."""
    with laspy.open(path, laz_backend=laspy.LazBackend.Lazrs) as reader:
        header = reader.header
        header_min = np.asarray(header.mins, dtype=np.float64)
        header_max = np.asarray(header.maxs, dtype=np.float64)
        scales = np.asarray(header.scales, dtype=np.float64)
        offsets = np.asarray(header.offsets, dtype=np.float64)
        # The ODM header retains the bounds from before rounding to the LAS scale.
        # Check the integer bounds against the decoded points, then use their coordinates.
        raw_min = np.rint((header_min - offsets) / scales).astype(np.int64)
        raw_max = np.rint((header_max - offsets) / scales).astype(np.int64)
        span = raw_max - raw_min
        origin = raw_min * scales + offsets
        upper = raw_max * scales + offsets
        projected_codes = {key.value_offset for vlr in header.vlrs
                           for key in getattr(vlr, "geo_keys", ())
                           if key.id == 3072 and key.tiff_tag_location == 0}
        if projected_codes and projected_codes != {EPSG}:
            raise ValueError("The embedded LAS projection and the expected UTM zone differ.")
        count = header.point_count
        if not 0 < count <= np.iinfo(np.uint32).max or np.any(span < 0):
            raise ValueError("Invalid LAS point count or coordinate bounds.")
        ratios = tuple(Fraction(str(scale)) / Fraction(str(VOXEL_M)) for scale in scales)
        nx, ny, nz = (int(index) + 1 for index in voxel_indices(tuple(map(int, span)), ratios))
        grid_x, grid_y = (nx + 1) // 2, (ny + 1) // 2
        cells = grid_x * grid_y
        z_stride = int(span[2]) + 1
        packed_max = cells * z_stride - 1
        if packed_max > np.iinfo(np.int64).max or math.prod((nx, ny, nz)) > np.iinfo(np.int64).max:
            raise ValueError("LAS extent is too large for the grid indices.")
        rgb_present = {"red", "green", "blue"} <= set(header.point_format.dimension_names)
        sums = np.zeros((nx * ny * nz, 7 if rgb_present else 4), dtype=np.uint64)
        counts = np.zeros(cells, dtype=np.int64)
        packed = np.empty(count, dtype=np.min_scalar_type(packed_max))
        observed_min = span.copy()
        observed_max = np.zeros(3, dtype=np.int64)
        consumed = 0

        for points in reader.chunk_iterator(chunk_points):
            delta = tuple(np.asarray(values, dtype=np.int64) - minimum
                          for values, minimum in zip((points.X, points.Y, points.Z), raw_min))
            chunk_min = [values.min() for values in delta]
            chunk_max = [values.max() for values in delta]
            if np.any(np.asarray(chunk_min) < 0) or np.any(np.asarray(chunk_max) > span):
                raise ValueError("A decoded point falls outside the LAS header bounds.")
            observed_min = np.minimum(observed_min, chunk_min)
            observed_max = np.maximum(observed_max, chunk_max)
            ix, iy, iz = voxel_indices(delta, ratios)
            voxel = (ix * ny + iy) * nz + iz
            np.add.at(sums[:, 0], voxel, 1)
            values = (*delta, points.red, points.green, points.blue) if rgb_present else delta
            for column, values_for_axis in zip(sums.T[1:], values):
                np.add.at(column, voxel, np.asarray(values_for_axis, dtype=np.uint64))

            cell = (iy // 2) * grid_x + (ix // 2)
            counts += np.bincount(cell, minlength=cells)
            end = consumed + len(points)
            packed[consumed:end] = cell * z_stride + delta[2]
            consumed = end

        if (consumed != count or observed_min.any() or not np.array_equal(observed_max, span)
                or sums[:, 0].sum() != count or counts.sum() != count):
            raise ValueError("Decoded point totals or bounds differ from the LAS header.")

        occupied = sums[sums[:, 0] > 0]
        voxel_counts = occupied[:, 0].astype(np.uint32)
        means = occupied[:, 1:] / voxel_counts[:, None]
        cloud = {
            "xyz": (means[:, :3] * scales).astype(np.float32),
            "point_count": voxel_counts,
        }
        if rgb_present:
            cloud["rgb"] = means[:, 3:].astype(np.float32)

        del sums, occupied, means
        packed.sort()
        occupied_cells = counts > 0
        n = counts[occupied_cells]
        end = counts.cumsum()[occupied_cells]
        start = end - n
        positions = {
            "z_min": (start, start),
            "z_max": (end - 1, end - 1),
            "z_median": (start + (n - 1) // 2, start + n // 2),
        }
        grid = {"point_count": counts.reshape(grid_y, grid_x).astype(np.uint32)}
        for name, (left, right) in positions.items():
            heights = np.full(cells, np.nan, dtype=np.float32)
            a = (packed[left] % z_stride).astype(np.float64)
            b = (packed[right] % z_stride).astype(np.float64)
            heights[occupied_cells] = (a + b) * (scales[2] / 2.0)
            grid[name] = heights.reshape(grid_y, grid_x)

        metadata = {
            "original_point_count": count,
            "utm_min_xyz_m": origin.tolist(),
            "utm_max_xyz_m": upper.tolist(),
            "local_min_xyz_m": [0.0, 0.0, 0.0],
            "local_max_xyz_m": (span * scales).tolist(),
            "las_header_min_xyz_m": header_min.tolist(),
            "las_header_max_xyz_m": header_max.tolist(),
            "las_projected_epsg": next(iter(projected_codes), None),
            "las_version": str(header.version),
            "las_point_format": header.point_format.id,
            "las_scale_xyz_m": scales.tolist(),
            "las_offset_xyz_m": offsets.tolist(),
            "voxel_size_m": VOXEL_M,
            "voxel_count": len(voxel_counts),
            "rgb_present": rgb_present,
            "elevation_cell_size_m": CELL_M,
            "elevation_shape_yx": [grid_y, grid_x],
            "empty_elevation_cells": int(np.count_nonzero(~occupied_cells)),
            "empty_elevation_fraction": float(np.mean(~occupied_cells)),
        }
    return cloud, grid, metadata


def write_cloud(folder, cloud, coordinates):
    """Save one compressed cloud, or contiguous point ranges under the Git size limit."""
    path = folder / "point_cloud_5cm.npz"
    fixed = dict(coordinates, voxel_size_m=np.float64(VOXEL_M))
    np.savez_compressed(path, **cloud, **fixed)
    rows = len(cloud["xyz"])
    if path.stat().st_size < MAX_FILE_BYTES:
        return [{"name": path.name, "bytes": path.stat().st_size, "points": rows}]
    path.unlink()
    parts = []
    for number, start in enumerate(range(0, rows, ROWS_PER_PART)):
        path = folder / f"point_cloud_5cm_{number:03d}.npz"
        piece = {name: values[start:start + ROWS_PER_PART] for name, values in cloud.items()}
        np.savez_compressed(path, **piece, **fixed)
        parts.append({"name": path.name, "bytes": path.stat().st_size, "points": len(piece["xyz"])})
    return parts


def readme(info):
    """Render the dataset record from measured bounds, counts and file sizes."""
    xyz = ("X（東）", "Y（北）", "Z（上）")
    bounds = "\n".join(
        f"| {axis} | {lo:.3f} ～ {hi:.3f} | 0 ～ {span:.3f} |"
        for axis, lo, hi, span in zip(xyz, info["utm_min_xyz_m"], info["utm_max_xyz_m"],
                                      info["local_max_xyz_m"])
    )
    checksums = "\n".join(
        f"| {name} | {record['bytes']:,} | `{record['sha256']}` |"
        for name, record in info["source_files"].items()
    )
    parts = "\n".join(
        f"| `{part['name']}` | {part['bytes']:,} | {part['points']:,} ボクセル |"
        for part in info["point_cloud_parts"]
    )
    ny, nx = info["elevation_shape_yx"]
    empty = info["empty_elevation_cells"]
    offset_x, offset_y = info["odm_xy_offset_m"]
    return f"""# 081 段階 A　2024-04-24 の ODM 点群

研究室の OpenDroneMap 点群 **{info['original_point_count']:,} 点**を、5 cm の立方体で集約した。
10 cm の標高地図も同じ元点群から作成した。元の 6 ファイルは研究 PC の
`~/thesis_data/drone_odm/2024-04-24/` に保管している。

## 座標と範囲

水平座標系は WGS 84 / UTM zone 52N（EPSG:{info['epsg']}）。`coords.txt` の
基準は `{info['coords_crs']}`、次の行の ODM 平面オフセットは
`{offset_x:.0f} {offset_y:.0f}`。`proj.txt` は `{info['proj']}`。
LAZ は地理参照済みなので、局所原点には実際に格納された点の各軸の最小値を使った。
LAZ の埋め込み座標系も EPSG:{info['las_projected_epsg']}。ヘッダーの境界値は
丸め前の値で、出力の境界値は実際の 1 mm 刻みの点から確認した。

| 軸 | 元の座標 (m) | 局所座標 (m) |
| --- | ---: | ---: |
{bounds}

局所値に各 NPZ の `origin_utm_xyz_m`（float64）を加えると元の座標系に戻る。
原点は XYZ の成分ごとの最小で、元の 1 点に一致するとは限らない。
Z は LAZ の高さを使い、鉛直基準の変換は行っていない。

## 出力

| ファイル | バイト | 内容 |
| --- | ---: | --- |
{parts}
| `elevation_10cm.npz` | {info['elevation_bytes']:,} | X {nx} × Y {ny} マス |

- 5 cm 点群は **{info['voxel_count']:,} 点**。`xyz` は局所 m の float32、
  `point_count` は元点数の uint32。RGB 付き入力では `rgb` に元 LAS の
  チャンネル単位で各格子の平均色を float32 で格納する。分割時はファイル名順に
  配列を連結できる。
- 10 cm 地図の配列は `[y, x]`。各セルの `z_min`、`z_max`、`z_median` は
  局所 m の float32、`point_count` は元点数の uint32。各マスの全元点で
  計算し、偶数点の中央値は中央 2 点の平均。点なしは高さ NaN・点数 0。
  点のないマスは **{empty:,}/{nx * ny:,}（{info['empty_elevation_fraction']:.4%}）**。
  分母は点群の外接長方形全体で、撮影範囲外の端のマスも含む。
- セルは局所 0 m から増える軸に沿い、下端を含む。出力の高さには地面以外の点も含む。

## 元ファイルの SHA-256

| ファイル | バイト | SHA-256 |
| --- | ---: | --- |
{checksums}

## 作り方

`conference/` から実行する。Python 3.12 の専用 venv に
`requirements_localization.txt` と `requirements_drone_map.txt` を入れる。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1
nice -n 19 ionice -c 3 .venv-localization/bin/python -m experiments.drone_map_downsample \\
  --source "$HOME/thesis_data/drone_odm/2024-04-24" \\
  --out data/drone_odm/2024-04-24
```

LAZ は単一スレッドの lazrs でチャンク読み込みする。整数の LAS 座標で
格子番号を求め、各ボクセルで元点の座標と色の和・点数を集計する。
標高は、10 cm セルと元の Z の組を整列して最大・最小・中央値を求める。
座標系、点数、範囲、依存の版は [summary.json](summary.json) に保存している。
"""


def convert(source, out):
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}")
    provenance = source_metadata(source)
    cloud, grid, info = read_cloud(source / LAZ_NAME)
    stats = json.loads((source / "odm_georeferenced_model.info.json").read_text(encoding="utf-8"))["stats"]
    box = stats["bbox"]["native"]["bbox"]
    if (any(item["count"] != info["original_point_count"] for item in stats["statistic"])
            or any(not np.allclose(info[f"utm_{bound}_xyz_m"],
                                   [box[bound + axis] for axis in "xyz"], atol=1e-6, rtol=0)
                   for bound in ("min", "max"))):
        raise ValueError("The PDAL sidecar and decoded LAZ counts or bounds disagree.")
    info.update(provenance)
    info["packages"] = {name: version(name) for name in ("numpy", "laspy", "lazrs")}
    coordinates = {
        "origin_utm_xyz_m": np.asarray(info["utm_min_xyz_m"], dtype=np.float64),
        "epsg": np.int32(info["epsg"]),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        folder = Path(tmp) / "converted"
        folder.mkdir()
        info["point_cloud_parts"] = write_cloud(folder, cloud, coordinates)
        elevation = folder / "elevation_10cm.npz"
        np.savez_compressed(elevation, **grid, **coordinates, cell_size_m=np.float64(CELL_M))
        info["elevation_bytes"] = elevation.stat().st_size
        (folder / "summary.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        (folder / "README_ja.md").write_text(readme(info), encoding="utf-8")
        sizes = {path.name: path.stat().st_size for path in folder.iterdir()}
        if sum(sizes.values()) > MAX_OUTPUT_BYTES or max(sizes.values()) >= MAX_FILE_BYTES:
            raise ValueError(f"Output exceeds the size limit ({sum(sizes.values()):,} bytes): {sizes}")
        if out.exists():
            raise FileExistsError(f"Output already exists: {out}")
        folder.rename(out)
    print(json.dumps(dict(info, output_bytes=sum(sizes.values())), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Folder containing the six ODM source files.")
    parser.add_argument("--out", type=Path, required=True, help="New output directory.")
    args = parser.parse_args()
    convert(args.source, args.out)


if __name__ == "__main__":
    main()
