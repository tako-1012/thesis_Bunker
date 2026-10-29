"""D* Lite optimality, incremental updates, online regressions and safety.

Run: python3 -m tests.test_dstar (from conference/).
"""
import math

import numpy as np

from tapp.config import DEFAULT_W, RESOLUTION
from tapp.dstar_lite import DStarLite
from tapp.metrics import evaluate
from tapp.online import run_online
from tapp.planners import astar, line_of_sight
from tapp.prior import coarse_prior
from tapp.scenario import build


def check(ds, blocked, mult, start, goal):
    stats = ds.compute()
    ref = astar(blocked, start, goal, mult)
    assert stats["success"] == ref["success"]
    assert stats["time"] >= 0 and stats["expansions"] >= 0
    path = ds.path()
    if not ref["success"]:
        assert path is None and math.isinf(ds.cost)
        return None
    assert abs(ds.cost - ref["cost"] / RESOLUTION) <= 1e-9, (ds.cost, ref["cost"] / RESOLUTION)
    assert path[0] == start and path[-1] == goal
    assert not any(blocked[p] for p in path)
    cost = 0.0
    for a, b in zip(path[:-1], path[1:]):
        assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
        assert line_of_sight(blocked, a, b), (a, b)
        cost += math.dist(a, b) * 0.5 * (mult[a] + mult[b])
    assert abs(cost - ds.cost) <= 1e-9, (cost, ds.cost)
    return path


def test_static():
    rng = np.random.default_rng(0)
    for _ in range(20):
        blocked = rng.random((25, 25)) < 0.2
        mult = 1.0 + 5.0 * rng.random((25, 25))
        start, goal = (0, 0), (24, 24)
        blocked[start] = blocked[goal] = False
        ds = DStarLite(blocked, mult, start, goal)
        path = check(ds, blocked, mult, start, goal)
        again = ds.compute()
        assert again["expansions"] == 0
        assert ds.path() == path
    print("static agreement passed (20 random grids, tolerance 1e-9)", flush=True)


def test_dynamic():
    seeds = (0, 1, 2, 100, 101)
    for seed in seeds:
        rng = np.random.default_rng(seed)
        blocked = rng.random((25, 25)) < 0.2
        mult = 1.0 + 5.0 * rng.random((25, 25))
        start, goal = (0, 0), (24, 24)
        blocked[start] = blocked[goal] = False
        ds = DStarLite(blocked, mult, start, goal)
        path = check(ds, blocked, mult, start, goal)
        for _ in range(20):
            if path is not None:
                moved = path[min(int(rng.integers(1, 4)), len(path) - 1)]
            else:
                moved = start
            cells = rng.integers(0, 25, size=(15, 2))
            for x, y in cells:
                blocked[x, y] = not blocked[x, y]
                mult[x, y] = rng.uniform(1, 6)
            blocked[moved] = blocked[goal] = False
            changed = list(map(tuple, cells)) + [moved, goal]
            ds.update_cells(changed, blocked, mult)
            km = ds.k_m
            ds.move_start(moved)
            assert abs(ds.k_m - km - math.dist(start, moved)) <= 1e-12
            start = moved
            path = check(ds, blocked, mult, start, goal)
    print(f"dynamic agreement passed ({len(seeds)} seeds x 20 updates, tolerance 1e-9)", flush=True)


def test_corner_and_reopening():
    blocked = np.zeros((5, 5), dtype=bool)
    mult = np.ones(blocked.shape)
    start, goal = (0, 0), (4, 4)
    ds = DStarLite(blocked, mult, start, goal)
    check(ds, blocked, mult, start, goal)
    # This side cell invalidates the (0, 0)->(1, 1) diagonal, not just its own edges.
    blocked[0, 1] = True
    ds.update_cells([(0, 1)], blocked, mult)
    check(ds, blocked, mult, start, goal)
    mult[1, 0] = 6.0
    ds.update_cells([(1, 0)], blocked, mult)
    check(ds, blocked, mult, start, goal)
    blocked[2, :] = True
    cells = [(2, y) for y in range(5)]
    ds.update_cells(cells, blocked, mult)
    assert check(ds, blocked, mult, start, goal) is None
    blocked[2, 3] = False
    ds.update_cells([(2, 3)], blocked, mult)
    assert check(ds, blocked, mult, start, goal) is not None
    # Restore the original graph, and exercise a zero-length start-goal path.
    blocked[:] = False
    mult[:] = 1.0
    ds.update_cells(np.argwhere(np.ones(blocked.shape, dtype=bool)), blocked, mult)
    path = check(ds, blocked, mult, start, goal)
    other = DStarLite(blocked, mult, start, goal)
    assert check(other, blocked, mult, start, goal) == path
    ds.move_start(goal)
    assert check(ds, blocked, mult, goal, goal) == [goal]
    print("corner constraints, cost decreases, unreachable/reopened routes and ties passed", flush=True)


def test_regression():
    cases = (("ridge", 7, "soft", 95.218208, 67), ("hills", 2, "hard", 85.493375, 60))
    for kind, seed, mode, length, plans in cases:
        sc = build(kind, 100, seed)
        tm = sc["tmap"]
        r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                       sense_radius_m=15.0, prior_map=coarse_prior(tm, 5.0), prior_lethal=mode)
        assert r["success"], (kind, r["reason"])
        actual = evaluate(r["traj"], tm)["length_xy"]
        assert abs(actual - length) <= 1e-6, (kind, actual)
        assert r["n_plans"] == plans, (kind, r["n_plans"])
        assert "plan_times" not in r  # default result fields are unchanged
    print("task 001 regression passed (ridge soft and hills hard, search omitted)", flush=True)


def test_safety():
    count = 0
    for kind in ("ridge", "craters"):
        for seed in range(5):
            sc = build(kind, 50, seed)
            tm = sc["tmap"]
            for every in (10.0, 1.0):
                r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                               sense_radius_m=15.0, prior_map=coarse_prior(tm, 5.0),
                               prior_lethal="soft", search="dstar_lite", replan_every_m=every,
                               record_plan_times=True)
                assert r["success"], (kind, seed, every, r["reason"])
                m = evaluate(r["traj"], tm)
                assert m["steep_len"] == 0 and not m["rock_hit"], (kind, seed, every, m)
                assert len(r["plan_times"]) == r["n_plans"]
                assert sum(r["plan_times"]) == r["plan_time"]
                assert max(r["plan_times"]) == r["max_plan_time"]
                count += 1
    print(f"D* Lite safety passed ({count} trajectories, normal and every-step replanning)", flush=True)


def test_errors_and_fixed_cost():
    sc = build("ridge", 50, 100)
    tm = sc["tmap"]
    for kwargs, error in ((dict(unknown_cost="adaptive"), ValueError),
                          (dict(planner="A*-HC"), NotImplementedError)):
        try:
            run_online(tm, sc["start"], sc["goal"], search="dstar_lite", **kwargs)
        except error:
            pass
        else:
            raise AssertionError(kwargs)
    # Fixed scalar priors are supported, not just coarse maps.
    r = run_online(tm, sc["start"], sc["goal"], unknown_cost=0.3, search="dstar_lite")
    assert r["success"], r["reason"]
    m = evaluate(r["traj"], tm)
    assert m["steep_len"] == 0 and not m["rock_hit"]
    # Adaptive is ignored when an explicit map fixes unknown costs.
    r = run_online(tm, sc["start"], sc["goal"], unknown_cost="adaptive",
                   prior_map=coarse_prior(tm, 5.0), search="dstar_lite")
    assert r["success"], r["reason"]
    for search in ("astar", "dstar_lite"):
        r = run_online(tm, sc["start"], sc["goal"], prior_map=coarse_prior(tm, 5.0),
                       search=search, record_plan_times=True)
        assert r["success"], r["reason"]
        assert len(r["plan_times"]) == r["n_plans"]
        assert sum(r["plan_times"]) >= r["plan_time"]
        assert max(r["plan_times"]) >= r["max_plan_time"]
        if search == "dstar_lite":
            assert sum(r["plan_times"]) == r["plan_time"]
            assert max(r["plan_times"]) == r["max_plan_time"]
    print("error handling and fixed/adaptive-with-map prior handling passed", flush=True)


if __name__ == "__main__":
    test_static()
    test_dynamic()
    test_corner_and_reopening()
    test_regression()
    test_safety()
    test_errors_and_fixed_cost()
    print("all D* Lite tests passed")
