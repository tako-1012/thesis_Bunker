"""Versioned NPZ maps with raw obstacle masks and lossless elevation round trips."""

from pathlib import Path
import numpy as np

from .config import RESOLUTION, CostWeights, Robot
from .real_beach import fill_nodata
from .traversability import TraversabilityMap


def save_map(
    path,
    elev,
    *,
    resolution=0.5,
    obstacle=None,
    water=None,
    nodata=None,
    start_xy=None,
    name="",
    kind="",
    source="",
    attribution=""
):
    z = np.asarray(elev, dtype=np.float64)
    if z.ndim != 2 or min(z.shape) < 2 or np.isinf(z).any() or not np.isfinite(z).any():
        raise ValueError("標高は有限値を含む2次元配列にしてください（NaN可）")
    if resolution != RESOLUTION:
        raise ValueError("既存プランナーが対応する解像度は0.5mです")
    packed = z.astype(np.float32)
    if np.isinf(packed).any():
        raise ValueError("標高がfloat32の範囲を超えています")
    arrays = dict(elev=packed, resolution=float(resolution), format_version=1)
    for key, value in (("obstacle", obstacle), ("water", water), ("nodata", nodata)):
        mask = (
            np.zeros(z.shape, bool) if value is None else np.asarray(value, dtype=bool)
        )
        if mask.shape != z.shape:
            raise ValueError("標高とマスクの形状が異なります")
        arrays[key] = mask | np.isnan(z) if key == "nodata" else mask
    # float32 alone changes the protected float64 terrain's cost. Store its exact
    # residual, rather than saving derived cost/lethal masks or inflating twice.
    residual = np.where(np.isfinite(z), z - packed.astype(np.float64), 0.0)
    if np.any(residual):
        arrays["elev_residual"] = residual
    if start_xy is None:
        tm = TraversabilityMap(
            fill_nodata(z), arrays["obstacle"] | arrays["water"] | arrays["nodata"]
        )
        free = np.argwhere(~tm.lethal)
        if not len(free):
            raise ValueError("通れる開始地点がありません")
        start_xy = free[0] * resolution
    start_xy = np.asarray(start_xy, dtype=float)
    if (
        start_xy.shape != (2,)
        or not np.isfinite(start_xy).all()
        or (start_xy < 0).any()
        or (start_xy > (np.array(z.shape) - 1) * resolution).any()
    ):
        raise ValueError("開始地点は地図内の有限なメートル座標にしてください")
    arrays.update(
        start_xy=start_xy,
        name=str(name),
        kind=str(kind),
        source=str(source),
        attribution=str(attribution),
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        np.savez_compressed(stream, **arrays)


def load_map_file(path, weights=CostWeights(), robot=Robot()) -> dict:
    with np.load(path, allow_pickle=False) as data:
        if int(data["format_version"]) != 1 or float(data["resolution"]) != RESOLUTION:
            raise ValueError("地図の形式または解像度に対応していません")
        packed = data["elev"]
        if packed.dtype != np.float32 or packed.ndim != 2 or min(packed.shape) < 2:
            raise ValueError("標高は2次元のfloat32配列にしてください")
        raw = packed.astype(np.float64)
        if "elev_residual" in data:
            residual = data["elev_residual"]
            if residual.shape != raw.shape or not np.isfinite(residual).all():
                raise ValueError("標高の精度補助データが不正です")
            raw += residual
        if np.isinf(raw).any():
            raise ValueError("無限大の標高は使えません")
        masks = {}
        for key in ("obstacle", "water", "nodata"):
            mask = data[key]
            if mask.dtype != bool or mask.shape != raw.shape:
                raise ValueError("地図のマスクが不正です")
            masks[key] = mask.copy()
        masks["nodata"] |= np.isnan(raw)
        metadata = {
            k: str(data[k].item()) for k in ("name", "kind", "source", "attribution")
        }
        start_xy = np.asarray(data["start_xy"], dtype=float)
    if (
        start_xy.shape != (2,)
        or not np.isfinite(start_xy).all()
        or (start_xy < 0).any()
        or (start_xy > (np.array(raw.shape) - 1) * RESOLUTION).any()
    ):
        raise ValueError("開始地点が地図の外です")
    start = tuple(round(float(v) / RESOLUTION) for v in start_xy)
    filled = fill_nodata(raw)
    tm = TraversabilityMap(
        filled, masks["obstacle"] | masks["water"] | masks["nodata"], robot, weights
    )
    if tm.lethal[start]:
        raise ValueError("開始地点は通れないマスです")
    return dict(
        **metadata,
        tmap=tm,
        start=start,
        start_xy=start_xy.tolist(),
        goal=None,
        resolution=RESOLUTION,
        side_m=raw.shape[0] * RESOLUTION,
        raw_elev=raw,
        **masks,
        format_version=1,
        terrain=dict(
            elev=filled,
            rock=masks["obstacle"],
            water=masks["water"],
            nodata=masks["nodata"],
        ),
    )


def scenario_to_mapfile(sc, path, name, kind, source, attribution):
    tm = sc["tmap"]
    terrain = sc.get("terrain", {})
    blank = np.zeros(tm.shape, bool)
    obstacle = sc.get("obstacle", terrain.get("rock", blank))
    if "rock" not in terrain and "obstacle" not in sc and tm.rock.any():
        raise ValueError("膨張前の障害物マスクが必要です")
    water = sc.get("water", terrain.get("water", blank))
    nodata = sc.get("nodata", terrain.get("nodata", blank))
    raw = sc.get("raw_elev", tm.elev)
    if not np.array_equal(fill_nodata(raw), tm.elev):
        raise ValueError("元の標高を再現できません")
    save_map(
        path,
        raw,
        obstacle=obstacle,
        water=water,
        nodata=nodata,
        start_xy=np.asarray(sc["start"]) * RESOLUTION,
        name=name,
        kind=kind,
        source=source,
        attribution=attribution,
    )
