"""Cached validation maps and metre-coordinate missions using the unchanged tour solver."""

import functools
import math
import struct
import threading
import time
import zlib
from pathlib import Path

import numpy as np
from scipy.ndimage import label

from .beach_scenario import build_beach
from .beach_terrain import BEACH_TYPES
from .collision import path_lethal_cells
from .config import DEFAULT_W, RESOLUTION
from .metrics import evaluate
from .real_beach import build_real, list_patches
from .tour import cost_matrix, euclid_matrix, solve_tour, tour_legs
from .mapfile import load_map_file

_MAP_LOCK = threading.Lock()
MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
_NAMES = dict(
    zip(BEACH_TYPES, ("緩やかな砂浜", "急な砂浜", "浜崖のある砂浜", "起伏地", "丘陵"))
)


def list_maps() -> list:
    return (
        [
            dict(
                id=f"synthetic/{kind}/200/100", name=f"人工：{_NAMES[kind]}", side_m=200
            )
            for kind in BEACH_TYPES
        ]
        + [
            dict(
                id=f'real/{row["name"]}/200', name=f'静岡県：{row["name"]}', side_m=200
            )
            for row in list_patches("validation")
        ]
        + _file_maps()
    )


def _file_maps():
    maps = []
    for path in sorted(MAPS_DIR.glob("*.npz")):
        with np.load(path, allow_pickle=False) as data:
            maps.append(
                dict(
                    id="file/" + path.name,
                    name=str(data["name"].item()),
                    side_m=data["elev"].shape[0] * float(data["resolution"]),
                )
            )
    return maps


@functools.lru_cache(maxsize=64)
def _load_map(map_id):
    if map_id not in {row["id"] for row in list_maps()}:
        raise ValueError("地図が見つかりません")
    parts = map_id.split("/")
    if parts[0] == "file":
        sc = load_map_file(MAPS_DIR / parts[1])
    elif parts[0] == "synthetic":
        sc = build_beach(parts[1], 200, 100)
    else:
        sc = build_real(parts[1], 200, 100)
    return dict(sc, id=map_id)


def load_map(map_id) -> dict:
    # lru_cache alone may call the builder twice on simultaneous first requests.
    with _MAP_LOCK:
        return _load_map(map_id)


def render_map_png(sc) -> bytes:
    """One cell per pixel, x to the right and y upwards; encode RGB with stdlib."""
    tm = sc["tmap"]
    gx, gy = np.gradient(tm.elev, RESOLUTION)
    shade = np.clip((0.65 - 0.4 * gx + 0.3 * gy) / np.sqrt(1 + gx**2 + gy**2), 0.15, 1)
    rgb = np.repeat(shade[..., None], 3, axis=2) * 255
    slope = np.clip(tm.slope / 25, 0, 1)[..., None]
    rgb = 0.65 * rgb + 0.35 * ((1 - slope) * [240, 225, 160] + slope * [230, 35, 35])
    rgb[tm.slope >= 25] = [230, 35, 35]
    rgb[tm.lethal] = 0.5 * rgb[tm.lethal] + 0.5 * np.array([240, 30, 30])
    water = sc.get("water", np.zeros(tm.shape, bool))
    nodata = sc.get("nodata", np.zeros(tm.shape, bool))
    rgb[water] = [55, 140, 220]
    rgb[nodata] = [145, 145, 145]
    # PNG rows run top-down; array axes are (x, y), with cell centres at i*R.
    pixels = np.ascontiguousarray(np.swapaxes(rgb, 0, 1)[::-1], dtype=np.uint8)
    height, width = pixels.shape[:2]

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    raw = b"".join(b"\x00" + row.tobytes() for row in pixels)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _cell(xy, shape):
    try:
        point = np.asarray(xy, dtype=float)
    except (TypeError, ValueError):
        return None, "座標は有限な数値の x, y で指定してください"
    if point.shape != (2,) or not np.isfinite(point).all():
        return None, "座標は有限な数値の x, y で指定してください"
    if (point < 0).any() or (point > (np.asarray(shape) - 1) * RESOLUTION).any():
        return None, "地図の外です"
    return tuple(round(float(v) / RESOLUTION) for v in point), None


def _metres(path):
    return [[float(x) * RESOLUTION, float(y) * RESOLUTION] for x, y in path]


def plan_mission(sc, start_xy, points_xy, method="terrain", w=DEFAULT_W) -> dict:
    """Input numbers are 1-based; base is 0. Order omits the repeated closing base.

    Invalid starts return an empty mission. Invalid destinations are omitted without
    renumbering. Duplicate destinations are allowed, including the base itself.
    Directional tour_cost is in the existing solver's cell-cost units, for both methods.
    """
    if not 1 <= len(points_xy) <= 12:
        raise ValueError("地点は1〜12個で指定してください")
    if method not in ("terrain", "euclid"):
        raise ValueError("順番の決め方が不正です")
    if not math.isfinite(w) or w < 0:
        raise ValueError("地形の重みが不正です")
    began = time.perf_counter()
    tm = sc["tmap"]
    rejected = []

    def validate(xy, index):
        cell, reason = _cell(xy, tm.shape)
        if reason is None and tm.lethal[cell]:
            if sc.get("water", np.zeros(tm.shape, bool))[cell]:
                reason = "水の上です"
            elif sc.get("nodata", np.zeros(tm.shape, bool))[cell]:
                reason = "標高データがありません"
            else:
                reason = "通れないマスです（急斜面・障害物・安全余白）"
        if reason:
            rejected.append(dict(index=index, reason=reason))
            return None
        return cell

    start = validate(start_xy, 0)
    result = dict(
        method=method,
        order=[],
        path=[],
        legs=[],
        metrics=None,
        tour_cost=None,
        ordering_cost=None,
        path_lethal_cells=0,
        rejected=rejected,
        timing=dict(matrix_s=0.0, solve_s=0.0, total_s=0.0),
    )
    if start is None:
        for index in range(1, len(points_xy) + 1):
            rejected.append(
                dict(index=index, reason="スタートが無効なため計画できません")
            )
        result["timing"]["total_s"] = time.perf_counter() - began
        return result
    # Four-connectivity equals reachability of the existing no-corner-cut graph.
    components, _ = label(~tm.lethal)
    cells, numbers = [start], [0]
    for index, xy in enumerate(points_xy, 1):
        cell = validate(xy, index)
        if cell is None:
            continue
        if components[cell] != components[start]:
            rejected.append(dict(index=index, reason="スタートから到達できません"))
        else:
            cells.append(cell)
            numbers.append(index)
    kappa = 1 / tm.robot.rolling_coeff
    matrix = cost_matrix(sc, cells, w=w, kappa=kappa)
    C = matrix["C"] if method == "terrain" else euclid_matrix(cells)
    tick = time.perf_counter()
    order, ordering_cost = solve_tour(C)
    solve_s = time.perf_counter() - tick
    if not order:
        raise RuntimeError("巡回の経路を計算できませんでした")
    path, legs = [start], []
    total_cost = 0.0
    for a, b in tour_legs(order):
        leg = matrix["paths"][a, b]
        length = float(
            np.linalg.norm(np.diff(np.asarray(leg), axis=0), axis=1).sum() * RESOLUTION
        )
        legs.append(
            dict(
                start=numbers[a],
                end=numbers[b],
                path=_metres(leg),
                length_m=length,
                cost=float(matrix["C"][a, b]),
            )
        )
        path.extend(leg[1:])
        total_cost += float(matrix["C"][a, b])
    hits = len(path_lethal_cells(path, tm.lethal))
    if hits:
        raise RuntimeError("安全性検査に失敗しました")
    metrics = evaluate(path if len(path) > 1 else [start, start], tm)
    result.update(
        order=[numbers[i] for i in order],
        path=_metres(path),
        legs=legs,
        metrics=metrics,
        tour_cost=total_cost,
        ordering_cost=float(ordering_cost),
        path_lethal_cells=hits,
        timing=dict(
            matrix_s=float(matrix["time"]),
            solve_s=solve_s,
            total_s=time.perf_counter() - began,
        ),
    )
    return result
