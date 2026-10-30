"""Mission parity, exact safety, metre/image orientation and non-queueing API tests."""

import concurrent.futures
import math
import struct
import threading
import zlib
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from tapp.collision import path_lethal_cells
from tapp.config import DEFAULT_W, RESOLUTION
from tapp.mission import list_maps, load_map, plan_mission, render_map_png
from tapp.metrics import evaluate
from tapp.real_beach import list_patches
from tapp.tour import (
    cost_matrix,
    euclid_matrix,
    sample_waypoints,
    solve_tour,
    tour_legs,
)
from tapp.traversability import TraversabilityMap
from webui.server import app


def points_for(sc, n=5):
    return [[float(v) * RESOLUTION for v in p] for p in sample_waypoints(sc, n, 100)]


def test_maps():
    maps = list_maps()
    expected = {
        f"synthetic/{kind}/200/100"
        for kind in ("beach_gentle", "beach_steep", "beach_scarp", "rolling", "hills")
    }
    expected |= {f'real/{row["name"]}/200' for row in list_patches("validation")}
    assert len(maps) == 17 and {row["id"] for row in maps} == expected
    assert all(row["name"] and row["side_m"] == 200 for row in maps)
    sc = load_map(maps[0]["id"])
    assert load_map(maps[0]["id"]) is sc
    image = render_map_png(sc)
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", image[16:24])
    assert (width, height) == sc["tmap"].shape
    # Confirm water pixels are blue at (column=x, row=height-1-y).
    offset, data = 8, b""
    while offset < len(image):
        size = struct.unpack(">I", image[offset : offset + 4])[0]
        if image[offset + 4 : offset + 8] == b"IDAT":
            data += image[offset + 8 : offset + 8 + size]
        offset += size + 12
    pixels = np.frombuffer(zlib.decompress(data), np.uint8).reshape(
        height, width * 3 + 1
    )
    assert (pixels[:, 0] == 0).all()
    rgb = pixels[:, 1:].reshape(height, width, 3)
    x, y = np.argwhere(sc["water"])[0]
    assert np.array_equal(rgb[height - 1 - y, x], [55, 140, 220])
    # Non-square grids catch transposition hidden by the supplied square maps.
    tm = TraversabilityMap(np.zeros((7, 9)), np.zeros((7, 9), bool))
    assert struct.unpack(">II", render_map_png({"tmap": tm})[16:24]) == (7, 9)
    for bad in ("synthetic/beach_gentle/200/0", "real/../200", "missing"):
        try:
            load_map(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown map accepted")
    print(
        "maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed",
        flush=True,
    )


def test_parity():
    sc = load_map("synthetic/beach_gentle/200/100")
    points = points_for(sc)
    start = [v * RESOLUTION for v in sc["start"]]
    cells = [sc["start"]] + [tuple(round(v / RESOLUTION) for v in p) for p in points]
    direct = cost_matrix(
        sc, cells, w=DEFAULT_W, kappa=1 / sc["tmap"].robot.rolling_coeff
    )
    order, cost = solve_tour(direct["C"])
    terrain = plan_mission(sc, start, points)
    assert terrain["order"] == order
    assert math.isclose(terrain["tour_cost"], cost, rel_tol=1e-12, abs_tol=1e-9)
    assert math.isclose(terrain["ordering_cost"], cost, rel_tol=1e-12)
    assert terrain["rejected"] == []
    expected_path = [cells[0]]
    for a, b in tour_legs(order):
        expected_path.extend(direct["paths"][a, b][1:])
    assert np.array_equal(
        np.asarray(terrain["path"]), np.asarray(expected_path) * RESOLUTION
    )
    assert len(terrain["legs"]) == 6
    assert terrain["metrics"] == evaluate(expected_path, sc["tmap"])
    for leg, (a, b) in zip(terrain["legs"], tour_legs(order)):
        expected_length = (
            np.linalg.norm(
                np.diff(np.asarray(direct["paths"][a, b]), axis=0), axis=1
            ).sum()
            * RESOLUTION
        )
        assert math.isclose(leg["length_m"], expected_length, rel_tol=1e-12)
    euclid = plan_mission(sc, start, points, "euclid")
    euclid_order, euclid_cost = solve_tour(euclid_matrix(cells))
    assert euclid["order"] == euclid_order and math.isclose(
        euclid["ordering_cost"], euclid_cost
    )
    assert math.isclose(
        euclid["tour_cost"],
        sum(direct["C"][a, b] for a, b in tour_legs(euclid_order)),
        rel_tol=1e-12,
    )
    for result in (terrain, euclid):
        assert result["path"][0] == result["path"][-1] == start
        assert result["path_lethal_cells"] == 0
        assert result["timing"]["matrix_s"] > 0 and result["timing"]["solve_s"] >= 0
        assert np.isfinite(list(v for v in result["metrics"].values())).all()
    print(
        "parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed",
        flush=True,
    )


def test_validation():
    # A tiny divided map isolates validation without changing any protected fixture.
    rock = np.zeros((20, 20), bool)
    rock[10, :] = True
    water = np.zeros_like(rock)
    water[0, 0] = True
    rock |= water
    tm = TraversabilityMap(np.zeros(rock.shape), rock)
    sc = dict(tmap=tm, start=(3, 3), water=water)
    result = plan_mission(
        sc, [1.5, 1.5], [[2, 2], [-0.01, 2], [10, 2], [0, 0], [5, 4], [8, 4]]
    )
    assert result["order"] == [0, 1]
    rejected = {r["index"]: r["reason"] for r in result["rejected"]}
    assert set(rejected) == {2, 3, 4, 5, 6}
    assert "外" in rejected[2] and "外" in rejected[3]
    assert "水" in rejected[4] and "通れない" in rejected[5] and "到達" in rejected[6]
    assert result["path_lethal_cells"] == 0 and result["legs"]
    all_rejected = plan_mission(sc, [1.5, 1.5], [[0, 0]])
    assert all_rejected["order"] == [0] and all_rejected["path"] == [[1.5, 1.5]]
    assert all_rejected["metrics"]["length_xy"] == 0
    invalid_start = plan_mission(sc, [float("nan"), 0], [[2, 2]])
    assert invalid_start["path"] == [] and invalid_start["rejected"][0]["index"] == 0
    duplicates = plan_mission(sc, [1.5, 1.5], [[1.5, 1.5], [1.5, 1.5]])
    assert duplicates["order"] == [0, 1, 2] and duplicates["tour_cost"] == 0
    for points in ([], [[2, 2]] * 13):
        try:
            plan_mission(sc, [1.5, 1.5], points)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid number of points accepted")
    # Round ties follow Python round, with no translation of the local origin.
    rounded = plan_mission(sc, [1.25, 1.75], [[2.26, 2.26]])
    assert rounded["path"][0] == [1, 2] and [2.5, 2.5] in rounded["path"]
    print(
        "validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed",
        flush=True,
    )


def test_safety():
    ids = [
        f"synthetic/{kind}/200/100"
        for kind in ("beach_gentle", "beach_steep", "beach_scarp")
    ]
    ids += [f'real/{p["name"]}/200' for p in list_patches("validation")[:2]]
    for map_id in ids:
        sc = load_map(map_id)
        for method in ("terrain", "euclid"):
            result = plan_mission(
                sc, [v * RESOLUTION for v in sc["start"]], points_for(sc), method
            )
            assert not result["rejected"] and len(result["order"]) == 6
            assert result["path_lethal_cells"] == 0
            assert (
                len(
                    path_lethal_cells(
                        np.asarray(result["path"]) / RESOLUTION, sc["tmap"].lethal
                    )
                )
                == 0
            )
        print(f"safety: {map_id}, 5 points, terrain/euclid contact=0", flush=True)


def test_api():
    with TestClient(app) as client:
        maps = client.get("/api/maps")
        assert maps.status_code == 200 and len(maps.json()) == 17
        map_id = maps.json()[0]["id"]
        info = client.get(f"/api/maps/{map_id}")
        assert info.status_code == 200 and info.json()["resolution"] == RESOLUTION
        assert info.json()["bounds"] == [[-0.25, -0.25], [199.75, 199.75]]
        image = client.get(f"/api/maps/{map_id}/image.png")
        assert (
            image.status_code == 200
            and image.headers["content-type"] == "image/png"
            and image.content.startswith(b"\x89PNG")
        )
        request = dict(
            map_id=map_id,
            start=info.json()["start"],
            points=points_for(load_map(map_id), 1),
            method="terrain",
        )
        result = client.post("/api/plan", json=request)
        assert (
            result.status_code == 200
            and result.json()["path_lethal_cells"] == 0
            and result.json()["order"] == [0, 1]
        )
        assert client.get("/").status_code == 200
        assert client.get("/static/vendor/leaflet/leaflet.js").status_code == 200
        assert client.get("/api/maps/invalid").status_code == 404
        assert client.get("/api/maps/invalid/image.png").status_code == 404
        assert (
            client.post("/api/plan", json=dict(request, map_id="invalid")).status_code
            == 404
        )
        assert (
            client.post("/api/plan", json=dict(request, points=[])).status_code == 422
        )
        assert (
            client.post(
                "/api/plan", json=dict(request, points=[[1, 2]] * 13)
            ).status_code
            == 422
        )
        assert (
            client.post("/api/plan", json=dict(request, method="invalid")).status_code
            == 422
        )
        # Hold the worker while other API requests execute, without timing-based sleeps.
        entered, release = threading.Event(), threading.Event()

        def blocked(*args):
            entered.set()
            assert release.wait(20)
            return dict(done=True)

        with patch("webui.server.plan_mission", side_effect=blocked):
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pending = pool.submit(client.post, "/api/plan", json=request)
                try:
                    assert entered.wait(20)
                    assert client.get("/api/maps").status_code == 200
                    assert client.post("/api/plan", json=request).status_code == 409
                finally:
                    release.set()
                assert pending.result(timeout=20).status_code == 200
        # The guard must also release after an unexpected planner failure.
        with patch("webui.server.plan_mission", side_effect=ValueError("検査用の失敗")):
            assert client.post("/api/plan", json=request).status_code == 422
        assert (
            client.post("/api/plan", json=dict(request, method="invalid")).status_code
            == 422
        )
    print(
        "API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed",
        flush=True,
    )


if __name__ == "__main__":
    for check in (test_maps, test_parity, test_validation, test_safety, test_api):
        check()
    print("all mission tests passed", flush=True)
