"""Grid planners on an 8-connected 2.5D grid.

All planners share the same data structures and language (pure Python +
heapq), so their computation times are directly comparable.

* astar(blocked, s, g, mult=None)
    mult=None  -> shortest path (terrain-unaware A*)
    mult=1+w*c -> Terrain-Aware A* (TA*): edge cost d * (m_u + m_v) / 2.
  Because mult >= 1 the Euclidean heuristic stays admissible and consistent,
  so the returned path is optimal for the stated cost.
* lazy_theta(blocked, s, g)  -> any-angle shortest path (Lazy Theta*)
* smooth_cost_aware(path, blocked, mult)
    -> greedy shortcutting that never increases the integrated terrain cost
       and never enters a blocked cell (TA*-S).
"""
import heapq
import math
import time

import numpy as np

from .config import RESOLUTION

SQ2 = math.sqrt(2.0)
NBRS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, SQ2), (-1, 1, SQ2), (1, -1, SQ2), (1, 1, SQ2)]


class PlanResult(dict):
    pass


def _reconstruct(parent, goal, n):
    path = []
    u = goal
    while True:
        path.append((u // n, u % n))
        if parent[u] == u:
            break
        u = parent[u]
    path.reverse()
    return path


def astar(blocked, start, goal, mult=None, max_expansions=10_000_000):
    t0 = time.perf_counter()
    n = blocked.shape[0]
    blk = blocked.ravel().tolist()
    mlt = None if mult is None else mult.ravel().tolist()
    s = start[0] * n + start[1]
    gl = goal[0] * n + goal[1]
    gx, gy = goal
    INF = float("inf")
    g = [INF] * (n * n)
    parent = [-1] * (n * n)
    closed = bytearray(n * n)
    g[s] = 0.0
    parent[s] = s
    heap = [(math.hypot(start[0] - gx, start[1] - gy), s)]
    exp = 0
    found = False
    while heap:
        f, u = heapq.heappop(heap)
        if closed[u]:
            continue
        closed[u] = 1
        exp += 1
        if u == gl:
            found = True
            break
        if exp > max_expansions:
            break
        ux, uy = divmod(u, n)
        gu = g[u]
        mu = 1.0 if mlt is None else mlt[u]
        for dx, dy, d in NBRS:
            vx, vy = ux + dx, uy + dy
            if vx < 0 or vy < 0 or vx >= n or vy >= n:
                continue
            v = vx * n + vy
            if blk[v] or closed[v]:
                continue
            if dx and dy and (blk[ux * n + vy] or blk[vx * n + uy]):
                continue  # no corner cutting
            c = d if mlt is None else d * 0.5 * (mu + mlt[v])
            ng = gu + c
            if ng < g[v]:
                g[v] = ng
                parent[v] = u
                heapq.heappush(heap, (ng + math.hypot(vx - gx, vy - gy), v))
    dt = time.perf_counter() - t0
    if not found:
        return PlanResult(success=False, path=None, time=dt, expansions=exp)
    return PlanResult(success=True, path=_reconstruct(parent, gl, n), time=dt,
                      expansions=exp, cost=g[gl] * RESOLUTION)


def _line_cells(a, b, step=0.25):
    """Cells touched by the segment between cell centres a and b (sampled)."""
    (ax, ay), (bx, by) = a, b
    L = math.hypot(bx - ax, by - ay)
    k = max(int(math.ceil(L / step)), 1)
    t = np.linspace(0.0, 1.0, k + 1)
    xs = np.rint(ax + (bx - ax) * t).astype(np.int64)
    ys = np.rint(ay + (by - ay) * t).astype(np.int64)
    return xs, ys, L


def line_of_sight(blocked, a, b, step=0.25, eps=1e-6):
    """Conservative visibility: a sample lying on a cell boundary checks every
    cell it touches, so segments never squeeze between diagonal blockers."""
    (ax, ay), (bx, by) = a, b
    L = math.hypot(bx - ax, by - ay)
    k = max(int(math.ceil(L / step)), 1)
    t = np.linspace(0.0, 1.0, k + 1)
    x = ax + (bx - ax) * t
    y = ay + (by - ay) * t
    n0, n1 = blocked.shape
    for ox in (-eps, eps):
        xs = np.clip(np.rint(x + ox).astype(np.int64), 0, n0 - 1)
        for oy in (-eps, eps):
            ys = np.clip(np.rint(y + oy).astype(np.int64), 0, n1 - 1)
            if blocked[xs, ys].any():
                return False
    return True


def segment_cost(mult, a, b):
    """Integrated cost of the straight segment a-b in cell units."""
    xs, ys, L = _line_cells(a, b)
    m = mult[xs, ys]
    # trapezoidal integration over uniform samples
    return L * (m.sum() - 0.5 * (m[0] + m[-1])) / max(len(m) - 1, 1)


def lazy_theta(blocked, start, goal, max_expansions=10_000_000):
    t0 = time.perf_counter()
    n = blocked.shape[0]
    blk = blocked.ravel().tolist()
    s = start[0] * n + start[1]
    gl = goal[0] * n + goal[1]
    gx, gy = goal
    INF = float("inf")
    g = [INF] * (n * n)
    parent = [-1] * (n * n)
    closed = bytearray(n * n)
    g[s] = 0.0
    parent[s] = s
    heap = [(math.hypot(start[0] - gx, start[1] - gy), s)]
    exp = 0
    found = False

    def dist(a, b):
        ax, ay = divmod(a, n)
        bx, by = divmod(b, n)
        return math.hypot(ax - bx, ay - by)

    while heap:
        f, u = heapq.heappop(heap)
        if closed[u]:
            continue
        ux, uy = divmod(u, n)
        p = parent[u]
        if p != u and not line_of_sight(blocked, divmod(p, n), (ux, uy)):
            best, bp = INF, -1
            for dx, dy, d in NBRS:
                vx, vy = ux + dx, uy + dy
                if 0 <= vx < n and 0 <= vy < n:
                    v = vx * n + vy
                    if dx and dy and (blk[ux * n + vy] or blk[vx * n + uy]):
                        continue
                    if closed[v] and g[v] + d < best:
                        best, bp = g[v] + d, v
            g[u], parent[u] = best, bp
        closed[u] = 1
        exp += 1
        if u == gl:
            found = True
            break
        if exp > max_expansions:
            break
        pu = parent[u]
        for dx, dy, d in NBRS:
            vx, vy = ux + dx, uy + dy
            if vx < 0 or vy < 0 or vx >= n or vy >= n:
                continue
            v = vx * n + vy
            if blk[v] or closed[v]:
                continue
            if dx and dy and (blk[ux * n + vy] or blk[vx * n + uy]):
                continue
            ng = g[pu] + dist(pu, v)
            if ng < g[v]:
                g[v] = ng
                parent[v] = pu
                heapq.heappush(heap, (ng + math.hypot(vx - gx, vy - gy), v))
    dt = time.perf_counter() - t0
    if not found:
        return PlanResult(success=False, path=None, time=dt, expansions=exp)
    return PlanResult(success=True, path=_reconstruct(parent, gl, n), time=dt,
                      expansions=exp)


def smooth_cost_aware(path, blocked, mult, *, los=None):
    """Greedy shortcutting accepted only if collision-free and not costlier."""
    if los is None:
        los = line_of_sight
    t0 = time.perf_counter()
    pts = list(path)
    seg = [segment_cost(mult, pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        best = i + 1
        acc = seg[i]
        j = i + 1
        while j < len(pts) - 1:
            acc += seg[j]
            cand = pts[j + 1]
            if not los(blocked, pts[i], cand):
                break
            if segment_cost(mult, pts[i], cand) <= acc + 1e-9:
                best = j + 1
            j += 1
        out.append(pts[best])
        i = best
    return out, time.perf_counter() - t0
