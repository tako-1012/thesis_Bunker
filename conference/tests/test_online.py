"""Regression, prior construction and ground-truth safety for online planning.

Run: python3 -m tests.test_online (from conference/).
"""
from unittest.mock import patch

import numpy as np

from tapp.config import DEFAULT_W, RESOLUTION, CostWeights, Robot
from tapp.metrics import evaluate
from tapp.online import run_online
from tapp.planners import astar
from tapp.prior import PriorMap, coarse_prior
from tapp.scenario import build, run_planner
from tapp.terrain import TERRAIN_TYPES
from tapp.traversability import TraversabilityMap


def test_regression():
    for seed, length, plans in ((0, 154.688509, 81), (7, 215.530174, 103)):
        sc = build("ridge", 100, seed)
        r = run_online(sc["tmap"], sc["start"], sc["goal"], planner="TA*-S",
                       unknown_cost="adaptive", sense_radius_m=15.0, w=8.0, prior_map=None)
        assert r["success"], (seed, r["reason"])
        m = evaluate(r["traj"], sc["tmap"])
        assert abs(m["length_xy"] - length) <= 1e-6, (seed, m["length_xy"])
        assert r["n_plans"] == plans, (seed, r["n_plans"])
    print("regression passed (ridge/100 m, seeds 0 and 7)", flush=True)


def test_perfect_prior():
    for kind in TERRAIN_TYPES:
        sc = build(kind, 50, 0)
        tm = sc["tmap"]
        pm = PriorMap(tm.cost.copy(), tm.lethal.copy(), RESOLUTION)
        oracle = run_planner("TA*-S", sc, w=DEFAULT_W)
        r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                       sense_radius_m=15.0, prior_map=pm, prior_lethal="hard")
        assert oracle["success"] and r["success"], (kind, r["reason"])
        length = evaluate(r["traj"], tm)["length_xy"]
        ref = evaluate(oracle["path"], tm)["length_xy"]
        assert abs(length / ref - 1) <= 0.02, (kind, length, ref)
    print("perfect prior passed (all terrain kinds/50 m/seed 0)", flush=True)


def test_coarse_prior():
    tm = build("rocky", 50, 0)["tmap"]
    for cell_m in (5.0, 10.0):
        pm = coarse_prior(tm, cell_m)
        assert pm.cell_m == cell_m
        assert pm.cost.shape == tm.shape and pm.lethal.shape == tm.shape
        assert np.issubdtype(pm.cost.dtype, np.floating) and pm.lethal.dtype == bool
        assert np.isfinite(pm.cost).all()
        assert (pm.cost >= 0).all() and (pm.cost <= 1).all()
    no_rocks = TraversabilityMap(tm.elev, np.zeros(tm.shape, dtype=bool), tm.robot, tm.weights)
    pm = coarse_prior(tm, RESOLUTION)
    np.testing.assert_allclose(pm.cost, no_rocks.cost, rtol=0, atol=1e-9)
    np.testing.assert_array_equal(pm.lethal, no_rocks.lethal)
    assert tm.rock.any()
    # A hand-computed interpolation of block means checks partial edge blocks.
    elev = np.arange(35, dtype=float).reshape(5, 7) / 10
    rock = np.ones(elev.shape, dtype=bool)
    robot, weights = Robot(max_slope_deg=35), CostWeights(alpha=0.7, beta=0.3)
    small = TraversabilityMap(elev, rock, robot, weights)
    coarse = np.array([[elev[i:i + 2, j:j + 2].mean() for j in range(0, 7, 2)]
                       for i in range(0, 5, 2)])
    centres_x, centres_y = [0.5, 2.5, 4.0], [0.5, 2.5, 4.5, 6.0]
    def reference(noise):
        rows = np.array([np.interp(np.arange(7), centres_y, row) for row in coarse + noise])
        up = np.array([np.interp(np.arange(5), centres_x, col) for col in rows.T]).T
        return TraversabilityMap(up, np.zeros(elev.shape, dtype=bool), robot, weights)
    expected = reference(0.0)
    pm = coarse_prior(small, 1.0)
    np.testing.assert_allclose(pm.cost, expected.cost, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(pm.lethal, expected.lethal)
    noise = np.random.default_rng(100).normal(0, 0.5, coarse.shape)
    expected = reference(noise)
    noisy = coarse_prior(small, 1.0, z_noise_m=0.5, seed=100)
    np.testing.assert_allclose(noisy.cost, expected.cost, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(noisy.lethal, expected.lethal)
    np.testing.assert_array_equal(noisy.cost, coarse_prior(small, 1.0, 0.5, seed=100).cost)
    assert not np.array_equal(noisy.cost, coarse_prior(small, 1.0, 0.5, seed=101).cost)
    # A single coarse block has constant elevation even on a rectangular grid.
    one = coarse_prior(small, 10.0)
    np.testing.assert_array_equal(one.cost, np.zeros(elev.shape))
    assert not one.lethal.any()
    for cell_m, noise in ((0, 0), (-1, 0), (0.1, 0), (np.nan, 0), (1, -1), (1, np.inf)):
        try:
            coarse_prior(small, cell_m, z_noise_m=noise)
        except ValueError:
            pass
        else:
            raise AssertionError((cell_m, noise))
    print("coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)", flush=True)


def test_prior_policies():
    tm = TraversabilityMap(np.zeros((21, 21)), np.zeros((21, 21), dtype=bool))
    start, goal = (2, 10), (18, 10)
    pm = PriorMap(np.full(tm.shape, 0.2), np.zeros(tm.shape, dtype=bool), 5.0)
    pm.lethal[8, 11] = True  # off the straight route, but eventually sensed
    for mode in ("soft", "hard", "ignore"):
        calls = []
        def record(lethal, cell, target, mult=None):
            calls.append((lethal.copy(), mult.copy()))
            return astar(lethal, cell, target, mult)
        with patch("tapp.online.astar", side_effect=record):
            r = run_online(tm, start, goal, sense_radius_m=1.0, step_m=0.5,
                           replan_every_m=100.0, prior_map=pm, prior_lethal=mode,
                           unknown_cost="ignored when a prior is provided")
        assert r["success"], (mode, r["reason"])
        lethal, mult = calls[0]
        assert not lethal[start] and mult[start] == 1.0  # true local cost overrides prior
        assert mult[goal] == 1 + DEFAULT_W * pm.cost[goal]
        assert lethal[8, 11] == (mode == "hard")
        assert mult[8, 11] == 1 + DEFAULT_W * (1.0 if mode == "soft" else 0.2)
        assert r["n_plans"] == (2 if mode == "hard" else 1), (mode, r["n_plans"])
        if mode == "hard":
            assert not calls[-1][0][8, 11]  # newly cleared prior obstacle opens the map
    # Compare true cost against each cell's own assumption, including soft lethal.
    tm.cost[8, 10] = 0.4
    for mode, cost, flagged, expect_trigger in (("ignore", 0.3, False, True),
                                               ("ignore", 0.38, False, False),
                                               ("soft", 0.0, True, False)):
        pm = PriorMap(np.full(tm.shape, cost), np.zeros(tm.shape, dtype=bool), 5.0)
        pm.lethal[8, 10] = flagged
        r = run_online(tm, start, goal, sense_radius_m=1.0, step_m=0.5,
                       replan_every_m=100.0, prior_map=pm, prior_lethal=mode)
        assert r["success"]
        assert (r["n_plans"] > 1) == expect_trigger, (mode, cost, r["n_plans"])
    print("prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)", flush=True)


def test_safety():
    count = 0
    for kind in ("ridge", "craters"):
        for seed in range(5):
            sc = build(kind, 50, seed)
            tm = sc["tmap"]
            variants = [
                ("online adaptive", None, "soft"),
                ("online prior5 soft", coarse_prior(tm, 5.0), "soft"),
                ("online prior5 hard", coarse_prior(tm, 5.0), "hard"),
                ("online prior10 soft", coarse_prior(tm, 10.0), "soft"),
                ("online prior5 soft noisy", coarse_prior(tm, 5.0, 0.5, seed=seed), "soft"),
            ]
            # The slope-unconstrained oracle A* is an energy reference, not a
            # driven online variant; the constrained oracle must also be safe.
            oracle = run_planner("TA*-S", sc, w=DEFAULT_W)
            assert oracle["success"]
            paths = [("oracle TA*-S", oracle["path"])]
            for name, pm, mode in variants:
                r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                               unknown_cost="adaptive", sense_radius_m=15.0,
                               prior_map=pm, prior_lethal=mode)
                assert r["success"], (kind, seed, name, r["reason"])
                assert r["n_plans"] >= 1
                assert 0 <= r["max_plan_time"] <= r["plan_time"]
                paths.append((name, r["traj"]))
            for name, path in paths:
                m = evaluate(path, tm)
                assert m["steep_len"] == 0 and not m["rock_hit"], (kind, seed, name, m)
                count += 1
    print(f"safety passed ({count} trajectories: five online variants and constrained oracle)", flush=True)


if __name__ == "__main__":
    test_regression()
    test_perfect_prior()
    test_coarse_prior()
    test_prior_policies()
    test_safety()
    print("all online tests passed")
