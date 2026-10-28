"""Terrain-aware comparison planners (exploratory; not used in the paper).

All share the hard constraints of TA* (lethal cells = rocks or slope > limit),
the 8-connected grid without corner cutting and the pure-Python search loop.

* energy_astar   : minimises the energy model of the metrics,
                   k(u,v) = mu * d_xy + max(z_v - z_u, 0)   [m, times m g]
                   (in the spirit of energy-efficient planners, e.g. Ganganath
                   et al. 2015). Heuristic mu * Euclidean distance (admissible).
* surface_astar  : minimises the 3D surface length sqrt(d_xy^2 + dz^2).
* terrain_theta  : Basic Theta* on the TA* cost field: a successor is reached
                   either along the grid edge or by a straight segment from
                   the current node's parent, whichever has the lower
                   integrated cost (segment must be collision-free).
"""
import heapq
import math
import time

from .config import RESOLUTION
from .planners import NBRS, PlanResult, _reconstruct, line_of_sight, segment_cost


def _astar_generic(blocked, elev, start, goal, mode, mu=0.15):
    t0 = time.perf_counter()
    n = blocked.shape[0]
    blk = blocked.ravel().tolist()
    z = elev.ravel().tolist()
    s = start[0] * n + start[1]
    gl = goal[0] * n + goal[1]
    gx, gy = goal
    INF = float("inf")
    g = [INF] * (n * n)
    parent = [-1] * (n * n)
    closed = bytearray(n * n)
    g[s] = 0.0
    parent[s] = s
    hw = mu if mode == "energy" else 1.0          # heuristic weight [per metre]
    R = RESOLUTION
    heap = [(hw * R * math.hypot(start[0] - gx, start[1] - gy), s)]
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
        ux, uy = divmod(u, n)
        gu, zu = g[u], z[u]
        for dx, dy, d in NBRS:
            vx, vy = ux + dx, uy + dy
            if vx < 0 or vy < 0 or vx >= n or vy >= n:
                continue
            v = vx * n + vy
            if blk[v] or closed[v]:
                continue
            if dx and dy and (blk[ux * n + vy] or blk[vx * n + uy]):
                continue
            dxy = d * R
            dz = z[v] - zu
            if mode == "energy":
                c = mu * dxy + (dz if dz > 0 else 0.0)
            else:
                c = math.sqrt(dxy * dxy + dz * dz)
            ng = gu + c
            if ng < g[v]:
                g[v] = ng
                parent[v] = u
                heapq.heappush(heap, (ng + hw * R * math.hypot(vx - gx, vy - gy), v))
    dt = time.perf_counter() - t0
    if not found:
        return PlanResult(success=False, path=None, time=dt, expansions=exp)
    return PlanResult(success=True, path=_reconstruct(parent, gl, n), time=dt, expansions=exp)


def energy_astar(tmap, start, goal):
    return _astar_generic(tmap.lethal, tmap.elev, start, goal, "energy", tmap.robot.rolling_coeff)


def surface_astar(tmap, start, goal):
    return _astar_generic(tmap.lethal, tmap.elev, start, goal, "surface")


def terrain_theta(blocked, mult, start, goal, max_expansions=10_000_000):
    t0 = time.perf_counter()
    n = blocked.shape[0]
    blk = blocked.ravel().tolist()
    mlt = mult.ravel().tolist()
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
        pu = parent[u]
        px, py = divmod(pu, n)
        for dx, dy, d in NBRS:
            vx, vy = ux + dx, uy + dy
            if vx < 0 or vy < 0 or vx >= n or vy >= n:
                continue
            v = vx * n + vy
            if blk[v] or closed[v]:
                continue
            if dx and dy and (blk[ux * n + vy] or blk[vx * n + uy]):
                continue
            # path 1: along the grid edge
            best = g[u] + d * 0.5 * (mlt[u] + mlt[v])
            bp = u
            # path 2: straight from u's parent, if visible and cheaper
            if pu != u and line_of_sight(blocked, (px, py), (vx, vy)):
                c2 = g[pu] + segment_cost(mult, (px, py), (vx, vy))
                if c2 < best:
                    best, bp = c2, pu
            if best < g[v]:
                g[v] = best
                parent[v] = bp
                heapq.heappush(heap, (best + math.hypot(vx - gx, vy - gy), v))
    dt = time.perf_counter() - t0
    if not found:
        return PlanResult(success=False, path=None, time=dt, expansions=exp)
    return PlanResult(success=True, path=_reconstruct(parent, gl, n), time=dt, expansions=exp)
