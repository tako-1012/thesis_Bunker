"""ALB data orientation, deterministic crops/masks and exact real-beach safety."""

import numpy as np
from tapp.real_beach import list_patches, load_patch, fill_nodata, build_real
from tapp.config import RESOLUTION
from tapp.planners import astar
from tapp.exact_planners import run_planner_exact
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.collision import path_lethal_cells


def test_data():
    rows = list_patches()
    assert len(rows) == 60
    assert len(list_patches("validation")) == 12 and len(list_patches("test")) == 48
    for row in rows:
        raw = load_patch(row["name"])
        assert raw.shape == (400, 400)
        filled = fill_nodata(raw)
        assert np.isfinite(filled).all()
        assert np.array_equal(filled[np.isfinite(raw)], raw[np.isfinite(raw)])
    # Known nearest neighbour, no-data-only rejection and path validation.
    a = np.array([[1.0, np.nan], [np.nan, 4.0]])
    f = fill_nodata(a)
    assert f[0, 0] == 1 and f[1, 1] == 4 and set(f.ravel()) == {1.0, 4.0}
    try:
        fill_nodata(np.full((2, 2), np.nan))
    except ValueError:
        pass
    else:
        raise AssertionError("all-NaN input accepted")
    try:
        load_patch("../index")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown patch accepted")
    print(
        "all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed",
        flush=True,
    )


def test_orientation():
    violations = []
    for row in list_patches():
        raw = load_patch(row["name"])
        counts = np.isfinite(raw).sum(axis=0)
        profile = np.divide(
            np.nansum(raw, axis=0), counts, out=np.full(400, np.nan), where=counts > 0
        )
        if not (profile[0] < 0 and np.nanmax(profile[100:201]) > 0):
            violations.append(
                (row["name"], float(profile[0]), float(np.nanmax(profile[100:201])))
            )
    assert (
        not violations
    ), f"supplied data violate requested orientation (name, sea-side mean, max mean in y=0..50m): {violations}"
    print("all 60 patches satisfy sea-to-land orientation", flush=True)


def test_scenarios():
    for row in list_patches("test")[:5]:
        name = row["name"]
        for size in (100, 200):
            a = build_real(name, size, 0)
            b = build_real(name, size, 0)
            tm = a["tmap"]
            assert tm.shape == (int(size / RESOLUTION),) * 2
            assert (
                a["start"] == b["start"]
                and a["goal"] == b["goal"]
                and a["crop_origin_cells"] == b["crop_origin_cells"]
            )
            assert np.array_equal(tm.elev, b["tmap"].elev) and np.array_equal(
                tm.lethal, b["tmap"].lethal
            )
            assert not tm.lethal[a["start"]] and not tm.lethal[a["goal"]]
            assert (
                tm.lethal[a["water"] | a["nodata"]].all() and np.isfinite(tm.elev).all()
            )
            assert astar(tm.lethal, a["start"], a["goal"])["success"]
            if size == 100:
                i, j = a["crop_origin_cells"]
                assert 0 <= i <= 200 and j == 60
                assert np.array_equal(
                    a["raw_elev"], load_patch(name)[i : i + 200, 60:260], equal_nan=True
                )
            else:
                assert np.array_equal(a["raw_elev"], load_patch(name), equal_nan=True)
            c = build_real(name, size, 0, debris=True)
            d = build_real(name, size, 0, debris=True)
            assert c["start"] == d["start"] and c["goal"] == d["goal"]
            assert np.array_equal(c["tmap"].elev, d["tmap"].elev) and np.array_equal(
                c["tmap"].lethal, d["tmap"].lethal
            )
            rock = c["terrain"]["rock"]
            land = np.isfinite(c["raw_elev"]) & (c["raw_elev"] >= 0)
            assert rock.any() and not (rock & ~land).any()
            assert not (c["terrain"]["driftwood"] & ~rock).any()
            # Compare debris with a clean map of the identical crop, even after redraws.
            from tapp.traversability import TraversabilityMap

            clean = TraversabilityMap(
                fill_nodata(c["raw_elev"]), c["water"] | c["nodata"]
            )
            assert c["tmap"].lethal.sum() > clean.lethal.sum()
        print(
            f"{name}: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed",
            flush=True,
        )


def test_safety():
    for row in list_patches("test")[:5]:
        for debris in (False, True):
            sc = build_real(row["name"], 100, 0, debris=debris)
            tm = sc["tmap"]
            r = run_planner_exact("TA*-S", sc)
            assert r["success"]
            assert len(path_lethal_cells(r["path"], tm.lethal)) == 0
            r = run_online(
                tm,
                sc["start"],
                sc["goal"],
                prior_map=coarse_prior(tm, 10),
                sense_radius_m=5,
                exact_los=True,
            )
            assert r["success"], (row["name"], debris, r["reason"])
            assert len(path_lethal_cells(r["traj"], tm.lethal)) == 0
        print(
            f'{row["name"]}: exact offline and coarse R5 c10 online safety passed, clean/debris',
            flush=True,
        )


if __name__ == "__main__":
    import sys, traceback

    failed = 0
    for check in (test_data, test_orientation, test_scenarios, test_safety):
        try:
            check()
        except Exception:
            failed += 1
            traceback.print_exc()
    print(f"real-beach test groups failed: {failed}", flush=True)
    if not failed:
        print("all real-beach tests passed", flush=True)
    sys.exit(bool(failed))
