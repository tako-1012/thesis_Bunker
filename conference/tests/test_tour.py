"""Independent graph/tour oracles, reproducible waypoints and exact leg safety."""

import itertools
import math
import numpy as np
from tapp.config import DEFAULT_W, RESOLUTION, Robot
from tapp.planners import astar, NBRS, segment_cost, _line_cells
from tapp.directional import (
    astar_dir,
    dijkstra_dir,
    path_from_parent,
    segment_cost_dir,
    smooth_dir,
    plan_leg,
)
from tapp.tour import (
    sample_waypoints,
    cost_matrix,
    euclid_matrix,
    solve_tour,
    tour_legs,
)
from tapp.beach_scenario import build_beach
from tapp.beach_terrain import BEACH_TYPES
from tapp.collision import path_lethal_cells


def test_zero():
    for seed in range(20):
        rng = np.random.default_rng(seed)
        blocked = rng.random((25, 25)) < 0.2
        blocked[0, 0] = blocked[-1, -1] = False
        z = rng.normal(size=blocked.shape)
        mult = 1 + 8 * rng.random(blocked.shape)
        old = astar(blocked, (0, 0), (24, 24), mult)
        new = astar_dir(blocked, z, (0, 0), (24, 24), mult, 0)
        assert new["success"] == old["success"]
        if old["success"]:
            assert abs(new["cost_dir"] - old["cost"] / RESOLUTION) < 1e-9
    print("kappa=0 agrees with legacy A* (20 random 25x25 grids)", flush=True)


def exhaustive_paths(blocked, z, m, s, k):
    # Enumerate every simple path on a 3x3 graph; positive costs rule out cycles.
    best = np.full(blocked.shape, np.inf)

    def visit(u, seen, cost):
        best[u] = min(best[u], cost)
        for dx, dy, d in NBRS:
            v = (u[0] + dx, u[1] + dy)
            if not (0 <= v[0] < len(z) and 0 <= v[1] < len(z)):
                continue
            if v in seen or blocked[v]:
                continue
            if dx and dy and (blocked[u[0], v[1]] or blocked[v[0], u[1]]):
                continue
            edge = d * (m[u] + m[v]) / 2 + k * max(z[v] - z[u], 0) / RESOLUTION
            visit(v, seen | {v}, cost + edge)

    visit(s, {s}, 0.0)
    return best


def test_graph():
    for seed in range(10):
        rng = np.random.default_rng(1000 + seed)
        z = rng.normal(size=(3, 3))
        m = 1 + rng.random((3, 3))
        b = rng.random((3, 3)) < 0.15
        b[0, 0] = False
        k = 1 / Robot().rolling_coeff
        ref = exhaustive_paths(b, z, m, (0, 0), k)
        dist, parent = dijkstra_dir(b, z, (0, 0), m, k)
        assert np.allclose(ref, dist, atol=1e-9, rtol=0)
        for target in itertools.product(range(3), repeat=2):
            r = astar_dir(b, z, (0, 0), target, m, k)
            assert r["success"] == np.isfinite(ref[target])
            if r["success"]:
                assert abs(r["cost_dir"] - dist[target]) < 1e-9
                p = path_from_parent(parent, (0, 0), target)
                assert p[0] == (0, 0) and p[-1] == target
    b = np.array([[False, True], [True, False]])
    z = np.zeros((2, 2))
    m = np.ones((2, 2))
    assert not astar_dir(b, z, (0, 0), (1, 1), m, 1)["success"]
    assert path_from_parent(dijkstra_dir(b, z, (0, 0), m, 1)[1], (0, 0), (1, 1)) is None
    assert not astar_dir(np.zeros_like(b), z, (0, 0), (1, 1), m, 1, max_expansions=0)[
        "success"
    ]
    print(
        "directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed",
        flush=True,
    )


def test_segments():
    b = np.zeros((20, 20), bool)
    m = np.ones((20, 20))
    z = np.indices((20, 20))[0] * 0.1
    k = 1 / Robot().rolling_coeff
    a, c = (2, 4), (17, 11)
    assert (
        abs(
            segment_cost_dir(m, z, a, c, k)
            - segment_cost_dir(m, z, c, a, k)
            - k * (z[c] - z[a]) / RESOLUTION
        )
        < 1e-9
    )
    assert abs(segment_cost_dir(m, z, a, c, 0) - segment_cost(m, a, c)) < 1e-9
    rng = np.random.default_rng(123)
    mrandom = 1 + 8 * rng.random((40, 40))
    zrandom = rng.normal(size=(40, 40))
    for _ in range(3000):
        u = tuple(rng.integers(0, 40, 2))
        v = tuple(rng.integers(0, 40, 2))
        assert segment_cost_dir(mrandom, zrandom, u, v, 0) == segment_cost(
            mrandom, u, v
        )
        xs, ys, _ = __import__("tapp.planners", fromlist=["_line_cells"])._line_cells(
            u, v
        )
        expected = (
            segment_cost(mrandom, u, v)
            + k * np.maximum(np.diff(zrandom[xs, ys]), 0).sum() / RESOLUTION
        )
        assert abs(segment_cost_dir(mrandom, zrandom, u, v, k) - expected) < 1e-9
    raw = [(i, 4) for i in range(2, 18)] + [(17, j) for j in range(5, 12)]
    p, _ = smooth_dir(raw, b, m, z, k)
    measure = lambda path: sum(
        segment_cost_dir(m, z, u, v, k) for u, v in zip(path, path[1:])
    )
    assert measure(p) <= measure(raw) + 1e-9
    assert len(path_lethal_cells(p, b)) == 0
    print(
        "uphill/downhill identity, segment units and nonincreasing exact smoothing passed",
        flush=True,
    )


def test_held_karp():
    rng = np.random.default_rng(6000)
    for destinations in range(2, 9):
        for trial in range(30):
            n = destinations + 1
            C = rng.integers(1, 1000, size=(n, n)).astype(float)
            np.fill_diagonal(C, 0)
            ref = min(
                (sum(C[a, b] for a, b in tour_legs((0,) + p)), (0,) + p)
                for p in itertools.permutations(range(1, n))
            )
            order, cost = solve_tour(C)
            assert (cost, tuple(order)) == ref
            assert solve_tour(C) == (order, cost)
    C = np.ones((5, 5))
    np.fill_diagonal(C, 0)
    assert solve_tour(C) == ([0, 1, 2, 3, 4], 5.0)
    assert solve_tour(C, 2) == ([2, 0, 1, 3, 4], 5.0)
    assert solve_tour(np.array([[0, np.inf], [np.inf, 0]])) == ([], math.inf)
    assert solve_tour(np.zeros((1, 1))) == ([0], 0.0)
    assert np.array_equal(euclid_matrix([(0, 0), (3, 4)]), [[0, 5], [5, 0]])
    print(
        "Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed",
        flush=True,
    )


def test_waypoints_and_legs():
    k = 1 / Robot().rolling_coeff
    for kind_index, kind in enumerate(BEACH_TYPES[:3]):
        sc = build_beach(kind, 100, 0)
        tm = sc["tmap"]
        seed = lambda: np.random.SeedSequence([0, 3000, 100, kind_index])
        pts = sample_waypoints(sc, 5, seed())
        assert pts == sample_waypoints(sc, 5, seed())
        points = [sc["start"]] + pts
        assert len(set(points)) == 6
        for a, b in itertools.combinations(points, 2):
            assert math.dist(a, b) * RESOLUTION >= 5
        for p in pts:
            assert not tm.lethal[p] and astar(tm.lethal, sc["start"], p)["success"]
        for kap in (0, k):
            matrix = cost_matrix(sc, points, kappa=kap)
            for i, a in enumerate(points):
                for j, b in enumerate(points):
                    leg = plan_leg(sc, a, b, kappa=kap)
                    assert (
                        leg["success"]
                        and len(path_lethal_cells(leg["path"], tm.lethal)) == 0
                    )
                    assert abs(leg["cost_dir"] - matrix["C"][i, j]) < 1e-9, (
                        kind,
                        kap,
                        i,
                        j,
                        leg["cost_dir"],
                        matrix["C"][i, j],
                    )
                    assert leg["path"] == matrix["paths"][i, j], (kind, kap, i, j)
                    mult = 1 + DEFAULT_W * tm.cost
                    ar = astar_dir(tm.lethal, tm.elev, a, b, mult, kap)
                    assert ar["success"]
                    ap, _ = smooth_dir(ar["path"], tm.lethal, mult, tm.elev, kap)
                    ac = sum(
                        segment_cost_dir(mult, tm.elev, u, v, kap)
                        for u, v in zip(ap[:-1], ap[1:])
                    )
                    assert ap == matrix["paths"][i, j], (
                        "A* path vs matrix",
                        kind,
                        kap,
                        i,
                        j,
                    )
                    assert abs(ac - matrix["C"][i, j]) < 1e-9, (
                        "A* cost vs matrix",
                        kind,
                        kap,
                        i,
                        j,
                    )
        print(
            f"{kind}: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)",
            flush=True,
        )


if __name__ == "__main__":
    test_zero()
    test_graph()
    test_segments()
    test_held_karp()
    test_waypoints_and_legs()
    print("all multi-goal tour tests passed", flush=True)
