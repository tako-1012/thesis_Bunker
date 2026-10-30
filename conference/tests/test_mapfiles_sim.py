"""Lossless maps, pursuit tracking/contact audits, SDF/PNG geometry and file-map APIs."""

import json
import csv
import math
from pathlib import Path
import struct
import tempfile
import concurrent.futures
import threading
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from scipy.ndimage import map_coordinates
from fastapi.testclient import TestClient

from tapp.beach_scenario import build_beach
from tapp.real_beach import build_real, list_patches
from tapp.mapfile import save_map, load_map_file, scenario_to_mapfile
from tapp.mission import list_maps, load_map, plan_mission
from tapp.pure_pursuit import PurePursuit
from tapp.robot_sim import simulate, initial_pose
from tapp.tour import sample_waypoints
from data_prep.export_gazebo import export_gazebo
from webui.server import app

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "mapfiles_sim"
AUDIT = []


def test_maps():
    scenarios = [
        build_beach(k, 200, 100) for k in ("beach_gentle", "beach_steep", "beach_scarp")
    ]
    scenarios += [build_real(p["name"], 200, 0) for p in list_patches("validation")[:2]]
    with tempfile.TemporaryDirectory() as folder:
        for i, sc in enumerate(scenarios):
            path = Path(folder) / f"{i}.npz"
            scenario_to_mapfile(sc, path, "検証", sc["kind"], "test", "credit")
            other = load_map_file(path)
            for key in ("elev", "cost", "lethal", "rock"):
                assert np.array_equal(
                    getattr(sc["tmap"], key), getattr(other["tmap"], key)
                ), key
            assert other["start"] == tuple(sc["start"]) and other["goal"] is None
            with np.load(path, allow_pickle=False) as data:
                assert (
                    data["elev"].dtype == np.float32
                    and int(data["format_version"]) == 1
                )
                assert all(
                    data[k].dtype == bool for k in ("obstacle", "water", "nodata")
                )
        # NaN remains encoded as NaN; nearest fill and blocked mask survive loading.
        path = Path(folder) / "nan.npz"
        z = np.zeros((30, 30))
        z[20, 20] = np.nan
        save_map(path, z, start_xy=[2, 2])
        loaded = load_map_file(path)
        assert np.isnan(loaded["raw_elev"][20, 20]) and loaded["nodata"][20, 20]
        assert np.isfinite(loaded["tmap"].elev).all() and loaded["tmap"].lethal[20, 20]
        try:
            save_map(path, z, resolution=1, start_xy=[2, 2])
        except ValueError:
            pass
        else:
            raise AssertionError("unsupported resolution accepted")
    files = sorted((ROOT / "maps").glob("*.npz"))
    assert len(files) == 23
    for path in files:
        sc = load_map_file(path)
        assert np.isfinite(sc["tmap"].cost).all() and not sc["tmap"].lethal[sc["start"]]
        assert sc["name"]
        if path.name.startswith("real_"):
            assert "静岡県" in sc["attribution"]
    old = {
        f"synthetic/{k}/200/100"
        for k in ("beach_gentle", "beach_steep", "beach_scarp", "rolling", "hills")
    }
    old |= {f'real/{p["name"]}/200' for p in list_patches("validation")}
    rows = list_maps()
    assert {r["id"] for r in rows} == old | {"file/" + p.name for p in files}
    assert [r["id"] for r in rows[:17]] == [
        r["id"] for r in rows if not r["id"].startswith("file/")
    ]
    assert (
        sum(p.stat().st_size for p in (ROOT / "maps").rglob("*") if p.is_file())
        < 15_000_000
    )
    print(
        "maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed",
        flush=True,
    )


def test_controller():
    sc = load_map_file(ROOT / "maps" / "flat_test_100m.npz")
    for name, path, limit in [
        ("straight", [[10, 10], [30, 10]], 0.05),
        ("right_angle", [[10, 10], [30, 10], [30, 30]], 1.0),
        ("closed", [[10, 10], [30, 10], [30, 30], [10, 10]], 1.0),
    ]:
        r = simulate(sc, path, initial_pose(path))
        assert r["completed"] and r["deviation_max_m"] <= limit, (name, r)
        assert np.all(np.diff(np.asarray(r["trajectory"])[:, 0]) > 0)
        print(
            name,
            "completed",
            r["completed"],
            "max_deviation_m",
            r["deviation_max_m"],
            "elapsed_s",
            r["elapsed_s"],
            flush=True,
        )
    controller = PurePursuit([[10, 10], [30, 10]])
    pose = np.array([10.0, 10.0, math.pi])
    spins = 0
    advanced = False
    for _ in range(200):
        v, w, done = controller.command(pose)
        assert not done and abs(w) <= 1 and 0 <= v <= 1
        if v == 0:
            spins += 1
            assert np.array_equal(pose[:2], [10, 10])
        else:
            advanced = True
            break
        pose[2] += w * 0.05
    assert spins > 0 and advanced
    # Saturation preserves requested curvature instead of clipping yaw alone.
    v, w, _ = PurePursuit([[0, 0], [0, 10]], lookahead_m=0.5, w_max=0.4).command(
        [0, 0, 0]
    )
    assert 0 < v < 1 and math.isclose(w, 0.4) and math.isclose(w / v, 4)
    r = simulate(sc, [[10, 10], [90, 10]], [10, 10, 0], max_time_s=0.1)
    assert not r["completed"] and math.isclose(r["elapsed_s"], 0.1)
    print(
        "controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed",
        flush=True,
    )


def test_tours():
    for name in ("flat_test_100m.npz", "beach_gentle_200m_100.npz"):
        sc = load_map_file(ROOT / "maps" / name)
        points = np.asarray(sample_waypoints(sc, 5, 100)) * 0.5
        plan = plan_mission(sc, np.asarray(sc["start"]) * 0.5, points)
        assert len(plan["order"]) == 6 and plan["path_lethal_cells"] == 0
        result = simulate(sc, plan["path"], initial_pose(plan["path"]))
        assert result["completed"], name
        record = dict(
            map=name,
            elapsed_s=result["elapsed_s"],
            deviation_mean_m=result["deviation_mean_m"],
            deviation_max_m=result["deviation_max_m"],
            path_lethal_cells=result["path_lethal_cells"],
            out_of_bounds_samples=result["out_of_bounds_samples"],
            completed=result["completed"],
        )
        AUDIT.append(dict(**record, lethal_cells=result["lethal_cells"]))
        np.savez_compressed(
            RESULTS / (name[:-4] + "_tracking.npz"),
            path=np.asarray(plan["path"]),
            trajectory=np.asarray(result["trajectory"]),
            lethal_cells=np.asarray(result["lethal_cells"], int).reshape(-1, 2),
            points=points,
        )
        print("tour", *(f"{k}={v}" for k, v in record.items()), flush=True)
        print(
            "contact_cells_xy_m",
            (np.asarray(result["lethal_cells"], float) * 0.5).tolist(),
            flush=True,
        )
    (RESULTS / "tour_audit.json").write_text(
        json.dumps(AUDIT, ensure_ascii=False, indent=2) + "\n"
    )


def read_png16(path):
    raw = Path(path).read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, depth, color = struct.unpack(">IIBB", raw[16:26])
    assert depth == 16 and color == 0
    offset = 8
    parts = []
    while offset < len(raw):
        size = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        part = raw[offset + 8 : offset + 8 + size]
        assert (
            zlib.crc32(kind + part)
            == struct.unpack(">I", raw[offset + 8 + size : offset + 12 + size])[0]
        )
        if kind == b"IDAT":
            parts.append(part)
        offset += size + 12
    rows = np.frombuffer(zlib.decompress(b"".join(parts)), np.uint8).reshape(
        height, 1 + 2 * width
    )
    assert (rows[:, 0] == 0).all()
    return rows[:, 1:].copy().view(">u2").reshape(height, width)


def test_gazebo():
    for name in ("flat_test_100m.npz", "real_08OB87_-0206_200m_0.npz"):
        with tempfile.TemporaryDirectory() as folder:
            result = export_gazebo(ROOT / "maps" / name, folder)
            pixels = read_png16(Path(folder) / "heightmap.png")
            n = pixels.shape[0]
            assert pixels.shape == (n, n) and ((n - 1) & (n - 2)) == 0
            xml = ET.parse(Path(folder) / "world.sdf")
            hm = xml.find('.//model[@name="terrain"]/link/collision/geometry/heightmap')
            size = np.fromstring(hm.findtext("size"), sep=" ")
            pos = np.fromstring(hm.findtext("pos"), sep=" ")
            model_pose = np.fromstring(
                xml.findtext('.//model[@name="terrain"]/pose'), sep=" "
            )
            assert np.array_equal(pos, [0, 0, 0])
            assert np.array_equal(model_pose[3:], [0, 0, 0])
            pos = pos + model_pose[:3]
            sc = load_map_file(ROOT / "maps" / name)
            z = sc["tmap"].elev
            side = z.shape[0] * 0.5
            assert np.array_equal(size[:2], [side, side]) and np.allclose(
                pos[:2], side / 2 - 0.25
            )
            height = pixels[::-1].T.astype(float) / 65535 * size[2] + pos[2]
            axis = (np.arange(z.shape[0]) + 0.5) / z.shape[0] * (n - 1)
            xx, yy = np.meshgrid(axis, axis, indexing="ij")
            error = float(
                np.max(
                    np.abs(
                        map_coordinates(height, [xx, yy], order=1, mode="nearest") - z
                    )
                )
            )
            assert error <= 0.1 and math.isclose(
                error, result["max_error_m"], abs_tol=1e-12
            )
            boxes = xml.findall(".//model")
            assert (
                sum(b.attrib["name"].startswith("obstacle_") for b in boxes)
                == result["obstacle_boxes"]
            )
            if sc["water"].any():
                assert xml.find('.//model[@name="water"]/link/collision') is None
            print(
                "gazebo",
                name,
                "pixels",
                n,
                "size_m",
                side,
                "max_error_m",
                error,
                "boxes",
                result["obstacle_boxes"],
                flush=True,
            )


def test_api():
    with TestClient(app) as client:
        rows = client.get("/api/maps").json()
        assert len(rows) == 40
        map_id = "file/flat_test_100m.npz"
        assert any(r["id"] == map_id for r in rows)
        info = client.get("/api/maps/" + map_id)
        assert info.status_code == 200 and info.json()["side_m"] == 100
        assert client.get("/api/maps/" + map_id + "/image.png").content.startswith(
            b"\x89PNG"
        )
        sc = load_map(map_id)
        points = (np.asarray(sample_waypoints(sc, 5, 100)) * 0.5).tolist()
        plan = client.post(
            "/api/plan",
            json=dict(
                map_id=map_id,
                start=info.json()["start"],
                points=points,
                method="terrain",
            ),
        )
        assert plan.status_code == 200 and plan.json()["path_lethal_cells"] == 0
        request = dict(map_id=map_id, path=plan.json()["path"], lookahead_m=1.0)
        r = client.post("/api/simulate", json=request)
        assert r.status_code == 200 and r.json()["completed"]
        assert (
            client.post("/api/simulate", json=dict(request, path=[])).status_code == 422
        )
        assert (
            client.post(
                "/api/simulate", json=dict(request, lookahead_m=0.4)
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/simulate", json=dict(request, lookahead_m=3.1)
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/simulate", json=dict(request, map_id="file/../bad.npz")
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/simulate", json=dict(request, path=[[-1, 0], [1, 0]])
            ).status_code
            == 422
        )
        entered, release = threading.Event(), threading.Event()

        def held(*args, **kwargs):
            entered.set()
            assert release.wait(20)
            return dict(completed=True)

        with patch("webui.server.simulate", side_effect=held):
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pending = pool.submit(client.post, "/api/simulate", json=request)
                try:
                    assert entered.wait(20)
                    assert client.get("/api/maps").status_code == 200
                    assert client.post("/api/simulate", json=request).status_code == 409
                    assert (
                        client.post(
                            "/api/plan",
                            json=dict(
                                map_id=map_id, start=info.json()["start"], points=points
                            ),
                        ).status_code
                        == 409
                    )
                finally:
                    release.set()
                assert pending.result(timeout=20).status_code == 200
        with patch("webui.server.simulate", side_effect=ValueError("検査用の失敗")):
            assert client.post("/api/simulate", json=request).status_code == 422
        assert (
            client.post(
                "/api/simulate", json=dict(request, map_id="invalid")
            ).status_code
            == 404
        )
    print(
        "API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed",
        flush=True,
    )


if __name__ == "__main__":
    RESULTS.mkdir(parents=True, exist_ok=True)
    for check in (test_maps, test_controller, test_tours, test_gazebo, test_api):
        check()
    with (RESULTS / "tour_summary.csv").open("w", newline="") as stream:
        fields = [k for k in AUDIT[0] if k != "lethal_cells"]
        writer = csv.DictWriter(
            stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(AUDIT)
    print("all mapfiles/simulation tests passed", flush=True)
