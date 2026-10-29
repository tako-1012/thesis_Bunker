"""Reachable waypoint sets, directed pair costs and exact lexicographic Held-Karp tours."""

import math, time
import numpy as np
from .config import DEFAULT_W, RESOLUTION
from .planners import astar
from .directional import dijkstra_dir, path_from_parent, smooth_dir, segment_cost_dir


def sample_waypoints(sc, n, seed, min_sep_m=5.0):
    if n < 0:
        raise ValueError("n must be nonnegative")
    if n == 0:
        return []
    tm = sc["tmap"]
    rng = np.random.default_rng(seed)
    chosen = []
    for index in rng.permutation(np.flatnonzero(~tm.lethal)):
        p = tuple(int(x) for x in np.unravel_index(index, tm.shape))
        if any(
            math.dist(p, q) * RESOLUTION < min_sep_m for q in [sc["start"]] + chosen
        ):
            continue
        if not astar(tm.lethal, sc["start"], p)["success"]:
            continue
        chosen.append(p)
        if len(chosen) == n:
            return chosen
    raise ValueError("not enough separated reachable waypoints")


def cost_matrix(sc, points, w=DEFAULT_W, kappa=0.0):
    """Include base in points[0]; one Dijkstra per source, then smooth each target."""
    t = time.perf_counter()
    tm = sc["tmap"]
    mult = 1 + w * tm.cost
    points = [tuple(p) for p in points]
    parents = [dijkstra_dir(tm.lethal, tm.elev, p, mult, kappa)[1] for p in points]
    C = np.full((len(points), len(points)), np.inf)
    np.fill_diagonal(C, 0)
    paths = {(i, i): [p] for i, p in enumerate(points)}
    for i, source in enumerate(points):
        for j, target in enumerate(points):
            if i == j:
                continue
            path = path_from_parent(parents[i], source, target)
            if path is None:
                continue
            path, _ = smooth_dir(path, tm.lethal, mult, tm.elev, kappa)
            paths[i, j] = path
            C[i, j] = sum(
                segment_cost_dir(mult, tm.elev, u, v, kappa)
                for u, v in zip(path[:-1], path[1:])
            )
    return dict(C=C, paths=paths, time=time.perf_counter() - t)


def euclid_matrix(points):
    p = np.asarray(points, dtype=float)
    return np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)


def tour_legs(order):
    order = list(order)
    return list(zip(order, order[1:] + order[:1])) if len(order) > 1 else []


def solve_tour(C, start_index=0):
    """Held-Karp optimum, order without repeated base; tour_legs closes the tour.

    Absolute differences <=1e-12 are treated as floating-point ties.
    """
    C = np.asarray(C, dtype=float)
    n = len(C)
    if C.shape != (n, n) or n < 1 or n > 13 or not 0 <= start_index < n:
        raise ValueError("tour matrix must have size 1..13")
    if np.isnan(C).any():
        raise ValueError("NaN costs")
    if n == 1:
        return [start_index], 0.0
    nodes = [i for i in range(n) if i != start_index]
    dp = {}
    for j, v in enumerate(nodes):
        dp[1 << j, j] = (float(C[start_index, v]), (start_index, v))

    def better(candidate, best):
        if best is None:
            return True
        return candidate[0] < best[0] - 1e-12 or (
            abs(candidate[0] - best[0]) <= 1e-12 and candidate[1] < best[1]
        )

    for mask in range(1, 1 << len(nodes)):
        for last, v in enumerate(nodes):
            state = dp.get((mask, last))
            if state is None or not np.isfinite(state[0]):
                continue
            for nxt, u in enumerate(nodes):
                if mask & (1 << nxt):
                    continue
                key = (mask | (1 << nxt), nxt)
                candidate = (state[0] + C[v, u], state[1] + (u,))
                if better(candidate, dp.get(key)):
                    dp[key] = candidate
    best = None
    mask = (1 << len(nodes)) - 1
    for j, v in enumerate(nodes):
        state = dp.get((mask, j))
        if state is None:
            continue
        candidate = (state[0] + C[v, start_index], state[1])
        if better(candidate, best):
            best = candidate
    return (
        (list(best[1]), float(best[0]))
        if best is not None and np.isfinite(best[0])
        else ([], math.inf)
    )
