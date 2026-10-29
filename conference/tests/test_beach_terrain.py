"""Beach profile ordering, reproducibility, scarp coverage and exact planner safety."""

import numpy as np
from tapp.beach_terrain import BEACH_TYPES, generate_beach
from tapp.beach_scenario import build_beach
from tapp.exact_planners import run_planner_exact
from tapp.natural_terrain import generate_natural
from tapp.scenario import PLANNERS, run_planner
from tapp.planners import astar
from tapp.traversability import slope_deg
from tapp.collision import path_lethal_cells
from tapp.online import run_online
from tapp.prior import coarse_prior


def test_generation():
    for kind in BEACH_TYPES:
        a = generate_beach(kind, 50, 100)
        b = generate_beach(kind, 50, 100)
        c = generate_beach(kind, 50, 101)
        for key in ("elev", "rock", "water", "wet"):
            assert np.array_equal(a[key], b[key])
            assert a[key].shape == (100, 100)
        assert np.isfinite(a["elev"]).all() and not np.array_equal(a["elev"], c["elev"])
        assert not (a["water"] & a["wet"]).any()
        assert (
            np.array_equal(a["water"], a["elev"] < 0)
            if kind.startswith("beach")
            else not a["water"].any()
        )
    r = generate_beach("rolling", 50, 100)
    old = generate_natural("rolling", 50, 100)
    assert np.array_equal(r["elev"], old["elev"]) and np.array_equal(
        r["rock"], old["rock"]
    )
    print(
        "beach determinism, shapes, finite values, water/wet and unchanged rolling passed",
        flush=True,
    )


def test_profiles():
    for kind in ("beach_gentle", "beach_steep"):
        low, high = (1 / 30, 1 / 15) if kind == "beach_gentle" else (1 / 12, 1 / 6)
        for seed in range(100, 105):
            a = generate_beach(kind, 100, seed)
            p = a["elev"].mean(axis=0)
            ht = a["parameters"]["tide_height"]
            edge = a["parameters"]["land_edge"]
            ys = (np.arange(len(p)) + 0.5) * 0.5
            sea = np.flatnonzero(p < 0)
            wet = np.flatnonzero((p >= 0) & (p < ht))
            dry = np.flatnonzero((p >= ht) & (ys < edge))
            land = np.flatnonzero(ys >= edge)
            assert all(len(g) > 0 for g in (sea, wet, dry, land)), (kind, seed)
            assert np.median(sea) < np.median(wet) < np.median(dry) < np.median(land), (
                kind,
                seed,
            )
            front = (p > 0.05) & (p < 0.6 * ht)
            gradient = np.gradient(p, 0.5)[front].mean()
            assert 0.8 * low <= gradient <= 1.2 * high, (kind, seed, gradient)
            assert (slope_deg(a["elev"])[a["landward"]] > 25).all()
    print(
        "averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)",
        flush=True,
    )


def test_scarp():
    coverage = []
    for seed in range(100, 105):
        a = generate_beach("beach_scarp", 100, seed)
        observed = (slope_deg(a["elev"]) >= 45) & ~a["landward"] & ~a["water"]
        assert np.array_equal(observed, a["scarp"])
        coverage.append(observed.any(axis=1).mean())
    assert 0.3 <= np.median(coverage) <= 0.7, coverage
    print("scarp 45-degree coverage passed:", coverage, flush=True)


def test_scenarios_and_planners():
    for kind in BEACH_TYPES:
        for seed in range(3):
            sc = build_beach(kind, 50, seed)
            tm = sc["tmap"]
            assert astar(tm.lethal, sc["start"], sc["goal"])["success"]
            for p in (sc["start"], sc["goal"]):
                assert (
                    not tm.lethal[p]
                    and not sc["water"][p]
                    and not sc["terrain"]["landward"][p]
                )
            if seed == 0:
                for name in PLANNERS:
                    if name != "TA*-S":
                        assert (
                            run_planner(name, sc)["path"]
                            == run_planner_exact(name, sc)["path"]
                        )
            r = run_planner_exact("TA*-S", sc)
            assert r["success"] and len(path_lethal_cells(r["path"], tm.lethal)) == 0, (
                kind,
                seed,
            )
    print(
        "beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)",
        flush=True,
    )


def test_online():
    for kind in BEACH_TYPES[:3]:
        for seed in range(3):
            sc = build_beach(kind, 50, seed)
            tm = sc["tmap"]
            r = run_online(
                tm,
                sc["start"],
                sc["goal"],
                prior_map=coarse_prior(tm, 10),
                sense_radius_m=5,
                exact_los=True,
            )
            assert len(path_lethal_cells(r["traj"], tm.lethal)) == 0, (kind, seed)
    print("exact beach online safety passed (9 trajectories)", flush=True)


if __name__ == "__main__":
    test_generation()
    test_profiles()
    test_scarp()
    test_scenarios_and_planners()
    test_online()
    print("all beach-terrain tests passed")
