"""Sanity tests: A*/TA* optimality against scipy Dijkstra, Theta* <= A* length.

Run: python3 -m tests.test_planners   (from conference/)
"""
import math

import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.csgraph import dijkstra

from tapp.planners import astar, lazy_theta, smooth_cost_aware, segment_cost, line_of_sight, NBRS


def dijkstra_ref(blocked, s, g, mult):
    n = blocked.shape[0]
    A = lil_matrix((n * n, n * n))
    for x in range(n):
        for y in range(n):
            if blocked[x, y]:
                continue
            for dx, dy, d in NBRS:
                vx, vy = x + dx, y + dy
                if not (0 <= vx < n and 0 <= vy < n) or blocked[vx, vy]:
                    continue
                if dx and dy and (blocked[x, vy] or blocked[vx, y]):
                    continue
                A[x * n + y, vx * n + vy] = d * 0.5 * (mult[x, y] + mult[vx, vy])
    dist = dijkstra(A.tocsr(), indices=s[0] * n + s[1])
    return dist[g[0] * n + g[1]]


def path_cost(path, mult):
    c = 0.0
    for (ax, ay), (bx, by) in zip(path[:-1], path[1:]):
        c += math.hypot(ax - bx, ay - by) * 0.5 * (mult[ax, ay] + mult[bx, by])
    return c


def main():
    rng = np.random.default_rng(0)
    for trial in range(20):
        n = 25
        blocked = rng.random((n, n)) < 0.2
        s, g = (0, 0), (n - 1, n - 1)
        blocked[s] = blocked[g] = False
        mult = 1.0 + 5.0 * rng.random((n, n))
        ref = dijkstra_ref(blocked, s, g, mult)
        r = astar(blocked, s, g, mult)
        if not np.isfinite(ref):
            assert not r["success"]
            continue
        assert r["success"]
        assert abs(path_cost(r["path"], mult) - ref) < 1e-6, (trial, path_cost(r["path"], mult), ref)
        # path is valid
        assert not any(blocked[p] for p in r["path"])
        # Theta* length never exceeds the grid-optimal length
        ra = astar(blocked, s, g)
        rt = lazy_theta(blocked, s, g)
        la = sum(math.dist(a, b) for a, b in zip(ra["path"][:-1], ra["path"][1:]))
        lt = sum(math.dist(a, b) for a, b in zip(rt["path"][:-1], rt["path"][1:]))
        assert lt <= la + 1e-9, (lt, la)
        for a, b in zip(rt["path"][:-1], rt["path"][1:]):
            assert line_of_sight(blocked, a, b)
        # cost-aware smoothing never increases integrated cost
        sp, _ = smooth_cost_aware(r["path"], blocked, mult)
        c0 = sum(segment_cost(mult, a, b) for a, b in zip(r["path"][:-1], r["path"][1:]))
        c1 = sum(segment_cost(mult, a, b) for a, b in zip(sp[:-1], sp[1:]))
        assert c1 <= c0 + 1e-9, (c1, c0)
    print("all planner tests passed")


if __name__ == "__main__":
    main()
