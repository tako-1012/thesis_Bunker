"""Nonnegative uphill penalties on the TA* graph and exact cost-aware shortcuts."""

import heapq
import math
import time
import numpy as np
from .config import DEFAULT_W, RESOLUTION
from .planners import NBRS, _line_cells
from .collision import line_of_sight_exact


def _search(blocked, elev, source, mult, kappa, target=None, max_expansions=10_000_000):
    if kappa < 0 or not np.isfinite(kappa):
        raise ValueError("kappa must be finite and nonnegative")
    if blocked.shape != elev.shape or blocked.shape != mult.shape:
        raise ValueError("map shapes differ")
    if not np.isfinite(mult).all() or (mult < 1).any():
        raise ValueError("multipliers must be finite and >=1")
    rows, cols = blocked.shape
    size = rows * cols
    s = int(source[0]) * cols + int(source[1])
    goal = None if target is None else int(target[0]) * cols + int(target[1])
    dist = [math.inf] * size
    parent = [-1] * size
    closed = bytearray(size)
    blk = blocked.ravel().tolist()
    z = elev.ravel().tolist()
    m = mult.ravel().tolist()
    if blk[s]:
        return (
            np.array(dist).reshape(blocked.shape),
            np.array(parent).reshape(blocked.shape),
            0,
        )

    def heuristic(u):
        if goal is None:
            return 0.0
        x, y = divmod(u, cols)
        gx, gy = divmod(goal, cols)
        return math.hypot(x - gx, y - gy)

    dist[s] = 0.0
    parent[s] = s
    heap = [(heuristic(s), s)]
    exp = 0
    while heap:
        f, u = heapq.heappop(heap)
        if goal is not None and math.isfinite(dist[goal]) and f > dist[goal] + 1e-10:
            break
        if closed[u]:
            continue
        closed[u] = 1
        exp += 1
        if exp > max_expansions:
            if goal is not None:
                parent[goal] = -1
                dist[goal] = math.inf
            break
        x, y = divmod(u, cols)
        gu = dist[u]
        for dx, dy, d in NBRS:
            vx, vy = x + dx, y + dy
            if not (0 <= vx < rows and 0 <= vy < cols):
                continue
            v = vx * cols + vy
            if blk[v] or (dx and dy and (blk[x * cols + vy] or blk[vx * cols + y])):
                continue
            ng = gu + d * 0.5 * (m[u] + m[v]) + kappa * max(z[v] - z[u], 0) / RESOLUTION
            if ng < dist[v]:
                dist[v] = ng
                parent[v] = u
                heapq.heappush(heap, (ng + heuristic(v), v))
            elif ng == dist[v] and u < parent[v] and v != s:
                parent[v] = u
    return (
        np.array(dist).reshape(blocked.shape),
        np.array(parent).reshape(blocked.shape),
        exp,
    )


def path_from_parent(parent, source, target):
    cols = parent.shape[1]
    s = source[0] * cols + source[1]
    u = target[0] * cols + target[1]
    flat = parent.ravel()
    path = []
    seen = set()
    if flat[u] < 0:
        return None
    while u not in seen:
        seen.add(u)
        path.append(divmod(int(u), cols))
        if u == s:
            return path[::-1]
        u = int(flat[u])
        if u < 0:
            return None
    raise RuntimeError("parent cycle")


def astar_dir(blocked, elev, start, goal, mult, kappa, max_expansions=10_000_000):
    """Optimal grid cost in cell units (unlike legacy A*, which returns metres)."""
    t = time.perf_counter()
    dist, parent, exp = _search(blocked, elev, start, mult, kappa, goal, max_expansions)
    path = path_from_parent(parent, start, goal)
    return dict(
        path=path,
        success=path is not None,
        cost_dir=float(dist[goal]),
        cost=float(dist[goal]),
        time=time.perf_counter() - t,
        expansions=exp,
    )


def dijkstra_dir(blocked, elev, source, mult, kappa):
    """All-target cell costs and a 2-D array of flattened predecessor indices."""
    dist, parent, _ = _search(blocked, elev, source, mult, kappa)
    return dist, parent


def segment_cost_dir(mult, elev, a, b, kappa):
    """Quarter-cell trapezoidal terrain integral plus sampled positive ascent / R."""
    xs, ys, length = _line_cells(a, b)
    values = mult[xs, ys]
    base = (
        length
        * (values.sum() - 0.5 * (values[0] + values[-1]))
        / max(len(values) - 1, 1)
    )
    heights = elev[xs, ys]
    return float(base + kappa * np.maximum(np.diff(heights), 0).sum() / RESOLUTION)


def smooth_dir(path, blocked, mult, elev, kappa):
    """Exact-LOS, nonincreasing greedy shortcuts in the requested direction."""
    t = time.perf_counter()
    pts = list(path)
    seg = [segment_cost_dir(mult, elev, a, b, kappa) for a, b in zip(pts[:-1], pts[1:])]
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        best = i + 1
        acc = seg[i]
        j = i + 1
        while j < len(pts) - 1:
            acc += seg[j]
            candidate = pts[j + 1]
            if not line_of_sight_exact(blocked, pts[i], candidate):
                break
            if segment_cost_dir(mult, elev, pts[i], candidate, kappa) <= acc + 1e-9:
                best = j + 1
            j += 1
        out.append(pts[best])
        i = best
    return out, time.perf_counter() - t


def plan_leg(sc, a, b, w=DEFAULT_W, kappa=0.0):
    """Plan one requested direction using its Dijkstra tree, then exact smoothing."""
    t = time.perf_counter()
    tm = sc["tmap"]
    mult = 1 + w * tm.cost
    _, parent = dijkstra_dir(tm.lethal, tm.elev, a, mult, kappa)
    path = path_from_parent(parent, a, b)
    if path is None:
        return dict(
            path=None, cost_dir=math.inf, success=False, time=time.perf_counter() - t
        )
    path, _ = smooth_dir(path, tm.lethal, mult, tm.elev, kappa)
    cost = sum(
        segment_cost_dir(mult, tm.elev, u, v, kappa)
        for u, v in zip(path[:-1], path[1:])
    )
    return dict(path=path, cost_dir=cost, success=True, time=time.perf_counter() - t)
