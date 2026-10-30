"""LAS patch geometry/precision, unchanged defaults, deterministic scenarios and exact safety."""

from pathlib import Path
import tempfile
import numpy as np
from tapp.config import RESOLUTION
from tapp.real_beach import DATA, list_patches, load_patch, build_real
from tapp.mapfile import load_map_file
from tapp.planners import astar
from tapp.exact_planners import run_planner_exact
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.collision import path_lethal_cells

DATASET = "shizuoka_beach_las"


def test_data():
    old, new = list_patches(), list_patches(dataset=DATASET)
    assert len(new) == 60
    assert [(r["name"], r["split"]) for r in old] == [
        (r["name"], r["split"]) for r in new
    ]
    assert len(list_patches("validation", dataset=DATASET)) == 12
    assert len(list_patches("test", dataset=DATASET)) == 48
    quantized = []
    for row in new:
        name = row["name"]
        raw = load_patch(name, dataset=DATASET)
        assert (
            raw.shape == (400, 400)
            and raw.dtype == np.float32
            and not np.isinf(raw).any()
        )
        with np.load(DATA / (name + ".npz"), allow_pickle=False) as a, np.load(
            DATA.parent / DATASET / (name + ".npz"), allow_pickle=False
        ) as b:
            for key in ("origin_xy", "tangent", "normal", "res"):
                assert np.array_equal(a[key], b[key]), (name, key)
            assert b["npts"].shape == raw.shape and b["npts"].dtype == np.uint16

        def fraction(z):
            values = z[np.isfinite(z)].astype(float)
            # One micrometre in metres: float32 rounding tolerance, far below
            # the millimetre LAS source quantization, with no relative tolerance.
            return float(
                np.isclose(values * 10, np.rint(values * 10), atol=1e-5, rtol=0).mean()
            )

        old_fraction = fraction(load_patch(name))
        new_fraction = fraction(raw)
        assert new_fraction < 0.02 and old_fraction > 0.20, (
            name,
            new_fraction,
            old_fraction,
        )
        quantized.append((new_fraction, old_fraction))
        counts = np.isfinite(raw).sum(axis=0)
        profile = np.divide(
            np.nansum(raw, axis=0), counts, out=np.full(400, np.nan), where=counts > 0
        )
        assert profile[0] < 0 and np.nanmax(profile[100:201]) > 0, name
    print(
        "data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed",
        flush=True,
    )
    print(
        "quantized_0.1m_fraction: new_max",
        max(r[0] for r in quantized),
        "old_min",
        min(r[1] for r in quantized),
        flush=True,
    )
    for bad in ("../shizuoka_beach", "missing"):
        try:
            list_patches(dataset=bad)
        except ValueError:
            pass
        else:
            raise AssertionError("unsupported dataset accepted")


def test_defaults():
    for row in list_patches("test")[:3]:
        a = build_real(row["name"], 100, 0)
        b = build_real(row["name"], 100, 0, dataset="shizuoka_beach")
        for key in ("cost", "lethal", "elev"):
            assert np.array_equal(getattr(a["tmap"], key), getattr(b["tmap"], key))
        assert (
            a["start"] == b["start"]
            and a["goal"] == b["goal"]
            and a["used_seed"] == b["used_seed"]
        )
        assert np.array_equal(
            load_patch(row["name"]),
            load_patch(row["name"], dataset="shizuoka_beach"),
            equal_nan=True,
        )
    print(
        "defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches",
        flush=True,
    )


def test_scenarios():
    for row in list_patches("test", dataset=DATASET)[:5]:
        for side in (100, 200):
            for debris in (False, True):
                a = build_real(row["name"], side, 0, debris=debris, dataset=DATASET)
                b = build_real(row["name"], side, 0, debris=debris, dataset=DATASET)
                assert a["tmap"].shape == (int(side / RESOLUTION),) * 2
                for key in ("cost", "lethal", "elev"):
                    assert np.array_equal(
                        getattr(a["tmap"], key), getattr(b["tmap"], key)
                    )
                assert a["start"] == b["start"] and a["goal"] == b["goal"]
                assert (
                    a["crop_origin_cells"] == b["crop_origin_cells"]
                    and a["used_seed"] == b["used_seed"]
                )
                assert a["tmap"].lethal[a["water"] | a["nodata"]].all()
                assert astar(a["tmap"].lethal, a["start"], a["goal"])["success"]
        print(
            row["name"]
            + ": LAS 100/200m clean/debris repeatability, masks and reachability passed",
            flush=True,
        )


def test_safety():
    for row in list_patches("test", dataset=DATASET)[:5]:
        for debris in (False, True):
            sc = build_real(row["name"], 100, 0, debris=debris, dataset=DATASET)
            tm = sc["tmap"]
            offline = run_planner_exact("TA*-S", sc)
            assert (
                offline["success"]
                and len(path_lethal_cells(offline["path"], tm.lethal)) == 0
            )
            online = run_online(
                tm,
                sc["start"],
                sc["goal"],
                prior_map=coarse_prior(tm, 10),
                sense_radius_m=5,
                exact_los=True,
            )
            assert online["success"], (row["name"], debris, online["reason"])
            assert len(path_lethal_cells(online["traj"], tm.lethal)) == 0
        print(
            row["name"]
            + ": exact offline and coarse R5 c10 safety, clean/debris contact=0",
            flush=True,
        )


def test_mapfiles():
    from fastapi.testclient import TestClient
    from webui.server import app

    folder = Path(__file__).resolve().parent.parent / "maps"
    files = sorted(folder.glob("real_las_*_200m_0.npz"))
    rows = list_patches("validation", dataset=DATASET)
    assert len(files) == len(rows) == 12
    assert {p.name for p in files} == {f'real_las_{r["name"]}_200m_0.npz' for r in rows}
    with TestClient(app) as client:
        response = client.get("/api/maps")
        assert response.status_code == 200
        listed = {r["id"] for r in response.json() if r["id"].startswith("file/")}
        assert listed == {"file/" + p.name for p in folder.glob("*.npz")}
        assert {"file/" + p.name for p in files} <= listed
    for row in rows:
        path = folder / f'real_las_{row["name"]}_200m_0.npz'
        a = build_real(row["name"], 200, 0, dataset=DATASET)
        b = load_map_file(path)
        assert np.array_equal(a["tmap"].cost, b["tmap"].cost)
        assert np.array_equal(a["tmap"].lethal, b["tmap"].lethal)
        assert a["start"] == b["start"] and "Ground" in b["attribution"]
        assert path.stat().st_size < 5_000_000
    print(
        "mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution",
        flush=True,
    )


def test_comparison_and_png():
    import pandas as pd
    from experiments.compare_real_beach_las import paired
    from data_prep.compress_heightmap_png import compress_heightmap, read_rows
    from data_prep.export_gazebo import png16
    from matplotlib.image import imread

    old = pd.DataFrame(dict(key=["a", "b"], value=[3, 7]))
    new = pd.DataFrame(dict(key=["b", "a"], value=[70, 30]))
    joined = paired(old, new, ["key"])
    assert list(zip(joined.key, joined.value_old, joined.value_new)) == [
        ("a", 3, 30),
        ("b", 7, 70),
    ]
    for invalid in (new.iloc[:1], pd.concat([new, new.iloc[:1]], ignore_index=True)):
        try:
            paired(old, invalid, ["key"])
        except (ValueError, pd.errors.MergeError):
            pass
        else:
            raise AssertionError("missing/duplicate scenario identities accepted")
    with tempfile.TemporaryDirectory() as tmp:
        for index, pixels in enumerate(
            (
                np.arange(33 * 33, dtype=np.uint16).reshape(33, 33),
                np.tile(np.arange(33, dtype=np.uint16), (33, 1)),
            )
        ):
            path = Path(tmp) / f"{index}.png"
            path.write_bytes(png16(pixels))
            decoded_before = imread(path).copy()
            result = compress_heightmap(path)
            assert result["samples_unchanged"] and np.array_equal(
                decoded_before, imread(path)
            )
            assert np.array_equal(
                read_rows(path)[1].copy().view(">u2").reshape(pixels.shape), pixels
            )
    print(
        "comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples",
        flush=True,
    )


if __name__ == "__main__":
    for check in (
        test_data,
        test_defaults,
        test_scenarios,
        test_safety,
        test_mapfiles,
        test_comparison_and_png,
    ):
        check()
    print("all real-beach LAS tests passed", flush=True)
