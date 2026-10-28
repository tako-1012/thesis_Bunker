"""Roll-aware (heading-dependent) extension of TA* and TA*-S.

On a slope with gradient g, moving in unit direction u gives
    tan(pitch) = |g . u|      (along the direction of travel)
    tan(roll)  = |g x u|      (across it)
The slope term of the cost becomes the larger utilisation of the two limits,
    s_dir = min(max(pitch / theta_pitch, roll / theta_roll), 1),
so no new weight is introduced, and a move is forbidden if it exceeds either
limit. Because pitch/roll depend only on the move direction (not on a heading
state), the 8-connected grid graph is kept: for each of the 8 directions we
precompute a per-cell multiplier and a per-cell "forbidden" mask, and an edge
u->v in direction k uses the mean multiplier of u and v and is forbidden if
either end is forbidden in direction k. Opposite directions share arrays since
|pitch| and roll are symmetric.

With c >= 0 the multiplier is >= 1, so the Euclidean heuristic stays
admissible and consistent and the search returns a minimum-cost path.
"""
import heapq
import math
import time

import numpy as np

from .config import RESOLUTION
from .planners import NBRS, PlanResult, _reconstruct


class DirectionalCost:
    def __init__(self, tmap, w, alpha=None, beta=None, roll_limit=None):
        r = tmap.robot
        alpha = tmap.weights.alpha if alpha is None else alpha
        beta = tmap.weights.beta if beta is None else beta
        self.theta_p = r.max_slope_deg
        self.theta_r = r.max_roll_deg if roll_limit is None else roll_limit
        self.tmap, self.w = tmap, w
        self.alpha, self.beta = alpha, beta
        self.r_term = np.clip(tmap.rough / r.rough_sat, 0, 1)
        self.mult, self.block = [], []
        for dx, dy, _ in NBRS:
            m, b = self.field(dx, dy)
            self.mult.append(m.ravel().tolist())
            self.block.append(b.ravel().tolist())

    def attitude(self, ux, uy, gx, gy):
        pitch = np.degrees(np.arctan(np.abs(gx * ux + gy * uy)))
        roll = np.degrees(np.arctan(np.abs(gx * uy - gy * ux)))
        return pitch, roll

    def field(self, dx, dy):
        n = math.hypot(dx, dy)
        tm = self.tmap
        pitch, roll = self.attitude(dx / n, dy / n, tm.gx, tm.gy)
        s_dir = np.clip(np.maximum(pitch / self.theta_p, roll / self.theta_r), 0, 1)
        mult = 1.0 + self.w * (self.alpha * s_dir + self.beta * self.r_term)
        block = tm.rock | (pitch > self.theta_p) | (roll > self.theta_r)
        return mult, block

    # --- straight segments (for shortcutting) ---
    def segment(self, a, b, step=0.25, eps=1e-6):
        """(feasible, integrated cost) of the straight segment a-b (cell units)."""
        (ax, ay), (bx, by) = a, b
        L = math.hypot(bx - ax, by - ay)
        if L == 0:
            return True, 0.0
        k = max(int(math.ceil(L / step)), 1)
        t = np.linspace(0.0, 1.0, k + 1)
        x = ax + (bx - ax) * t
        y = ay + (by - ay) * t
        tm = self.tmap
        n0, n1 = tm.shape
        ux, uy = (bx - ax) / L, (by - ay) / L
        xs = np.rint(x).astype(np.int64)
        ys = np.rint(y).astype(np.int64)
        p, r = self.attitude(ux, uy, tm.gx[xs, ys], tm.gy[xs, ys])
        s_dir = np.clip(np.maximum(p / self.theta_p, r / self.theta_r), 0, 1)
        m = 1.0 + self.w * (self.alpha * s_dir + self.beta * self.r_term[xs, ys])
        cost = L * (m.sum() - 0.5 * (m[0] + m[-1])) / max(len(m) - 1, 1)
        # conservative: every cell touched by a boundary sample must be admissible
        for ox in (-eps, eps):
            xs = np.clip(np.rint(x + ox).astype(np.int64), 0, n0 - 1)
            for oy in (-eps, eps):
                ys = np.clip(np.rint(y + oy).astype(np.int64), 0, n1 - 1)
                p, r = self.attitude(ux, uy, tm.gx[xs, ys], tm.gy[xs, ys])
                if (tm.rock[xs, ys] | (p > self.theta_p) | (r > self.theta_r)).any():
                    return False, cost
        return True, cost


def astar_roll(dc, start, goal, max_expansions=10_000_000):
    """TA* with heading-dependent cost and constraints (TA*-R)."""
    t0 = time.perf_counter()
    n = dc.tmap.shape[0]
    rock = dc.tmap.rock.ravel().tolist()
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
    dirs = [(dx, dy, d, dc.mult[k], dc.block[k]) for k, (dx, dy, d) in enumerate(NBRS)]
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
        for dx, dy, d, mk, bk in dirs:
            vx, vy = ux + dx, uy + dy
            if vx < 0 or vy < 0 or vx >= n or vy >= n:
                continue
            v = vx * n + vy
            if closed[v] or bk[u] or bk[v]:
                continue
            if dx and dy and (rock[ux * n + vy] or rock[vx * n + uy]):
                continue
            ng = gu + d * 0.5 * (mk[u] + mk[v])
            if ng < g[v]:
                g[v] = ng
                parent[v] = u
                heapq.heappush(heap, (ng + math.hypot(vx - gx, vy - gy), v))
    dt = time.perf_counter() - t0
    if not found:
        return PlanResult(success=False, path=None, time=dt, expansions=exp)
    return PlanResult(success=True, path=_reconstruct(parent, gl, n), time=dt,
                      expansions=exp, cost=g[gl] * RESOLUTION)


def smooth_roll(path, dc):
    """Cost-aware shortcutting with heading-dependent cost and constraints."""
    t0 = time.perf_counter()
    pts = list(path)
    seg = [dc.segment(pts[i], pts[i + 1])[1] for i in range(len(pts) - 1)]
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        best = i + 1
        acc = seg[i]
        j = i + 1
        while j < len(pts) - 1:
            acc += seg[j]
            ok, c = dc.segment(pts[i], pts[j + 1])
            if not ok:
                break
            if c <= acc + 1e-9:
                best = j + 1
            j += 1
        out.append(pts[best])
        i = best
    return out, time.perf_counter() - t0
