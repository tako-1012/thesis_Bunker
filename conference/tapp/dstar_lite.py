"""Backward D* Lite on the TA* graph, with lazy heap updates and moving start."""
import heapq
import math
import time

import numpy as np

from .planners import NBRS


class DStarLite:
    def __init__(self, blocked, mult, start, goal):
        blocked = np.asarray(blocked, dtype=bool)
        mult = np.asarray(mult, dtype=float)
        if blocked.ndim != 2 or mult.shape != blocked.shape:
            raise ValueError("blocked and mult must be matching 2D arrays")
        if not np.isfinite(mult).all() or (mult < 1).any():
            raise ValueError("multipliers must be finite and at least one")
        self.shape = blocked.shape
        self._rows, self._cols = blocked.shape
        self._blocked = blocked.ravel().tolist()
        self._mult = mult.ravel().tolist()
        self._start = self._index(start)
        self._goal = self._index(goal)
        self.k_m = 0.0
        self._g = [math.inf] * blocked.size
        self._rhs = [math.inf] * blocked.size
        self._rhs[self._goal] = 0.0
        self._heap = []
        self._queued = {}
        self._serial = 0
        self._push(self._goal, self._key(self._goal))

    def _index(self, cell):
        x, y = cell
        if not (0 <= x < self._rows and 0 <= y < self._cols):
            raise ValueError("cell outside the map")
        return int(x) * self._cols + int(y)

    def _distance(self, a, b):
        ax, ay = divmod(a, self._cols)
        bx, by = divmod(b, self._cols)
        return math.hypot(ax - bx, ay - by)

    def _key(self, u):
        value = min(self._g[u], self._rhs[u])
        return value + self._distance(self._start, u) + self.k_m, value

    def _push(self, u, key):
        self._serial += 1
        entry = (key[0], key[1], self._serial, u)
        self._queued[u] = entry
        heapq.heappush(self._heap, entry)

    def _top(self):
        while self._heap and self._queued.get(self._heap[0][3]) != self._heap[0]:
            heapq.heappop(self._heap)
        return self._heap[0][:2] if self._heap else (math.inf, math.inf)

    def _neighbours(self, u):
        x, y = divmod(u, self._cols)
        for dx, dy, _ in NBRS:
            vx, vy = x + dx, y + dy
            if 0 <= vx < self._rows and 0 <= vy < self._cols:
                yield vx * self._cols + vy

    def _edges(self, u):
        if self._blocked[u]:
            return
        x, y = divmod(u, self._cols)
        mu = self._mult[u]
        for dx, dy, d in NBRS:
            vx, vy = x + dx, y + dy
            if not (0 <= vx < self._rows and 0 <= vy < self._cols):
                continue
            v = vx * self._cols + vy
            if self._blocked[v]:
                continue
            if dx and dy and (self._blocked[x * self._cols + vy] or
                              self._blocked[vx * self._cols + y]):
                continue
            yield v, d * 0.5 * (mu + self._mult[v])

    def _update_vertex(self, u):
        if u != self._goal:
            self._rhs[u] = min((c + self._g[v] for v, c in self._edges(u)), default=math.inf)
        self._update_queue(u)

    def _update_queue(self, u):
        self._queued.pop(u, None)
        if self._g[u] != self._rhs[u]:
            self._push(u, self._key(u))

    def update_cells(self, cells, blocked, mult):
        """Apply changed cells, including all incident and corner-dependent edges."""
        blocked, mult = np.asarray(blocked), np.asarray(mult)
        if blocked.shape != self.shape or mult.shape != self.shape:
            raise ValueError("updated arrays must match the original map")
        affected = set()
        for cell in cells:
            u = self._index(cell)
            b, m = bool(blocked[tuple(cell)]), float(mult[tuple(cell)])
            if not math.isfinite(m) or m < 1:
                raise ValueError("multipliers must be finite and at least one")
            if b != self._blocked[u] or m != self._mult[u]:
                self._blocked[u], self._mult[u] = b, m
                affected.add(u)
                affected.update(self._neighbours(u))
        for u in sorted(affected):
            self._update_vertex(u)

    def move_start(self, start):
        u = self._index(start)
        self.k_m += self._distance(self._start, u)
        self._start = u

    def compute(self):
        """Repair the shortest path; expansions count valid queue pops."""
        t0 = time.perf_counter()
        expansions = 0
        while self._top() < self._key(self._start) or self._rhs[self._start] != self._g[self._start]:
            if not self._heap:
                break
            k1, k2, _, u = heapq.heappop(self._heap)
            self._queued.pop(u)
            expansions += 1
            key = self._key(u)
            if (k1, k2) < key:
                self._push(u, key)
            elif self._g[u] > self._rhs[u]:
                self._g[u] = self._rhs[u]
                # A decrease only needs to relax the edge back to each predecessor.
                for v, c in self._edges(u):
                    value = c + self._g[u]
                    if v != self._goal and value < self._rhs[v]:
                        self._rhs[v] = value
                        self._update_queue(v)
            else:
                self._g[u] = math.inf
                self._update_vertex(u)
                for v in self._neighbours(u):
                    self._update_vertex(v)
        return {"success": math.isfinite(self.cost), "expansions": expansions,
                "time": time.perf_counter() - t0}

    def path(self):
        """Follow edge cost + g; equal candidates keep the first NBRS entry."""
        if not math.isfinite(self.cost):
            return None
        u = self._start
        path = [divmod(u, self._cols)]
        seen = {u}
        while u != self._goal:
            best, nxt = math.inf, None
            for v, c in self._edges(u):
                value = c + self._g[v]
                if value < best:
                    best, nxt = value, v
            if nxt is None or nxt in seen:
                raise RuntimeError("inconsistent D* Lite path; call compute after updates")
            u = nxt
            seen.add(u)
            path.append(divmod(u, self._cols))
        return path

    @property
    def cost(self):
        """Minimum cost from the current start in cell units (not metres)."""
        return self._g[self._start]
