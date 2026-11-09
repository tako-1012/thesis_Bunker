"""Opt-in endpoint escape, immutable planning snapshots and offline safety audit.

All distances are fixed before evaluation. Truth is accepted only by audit_path,
never by the planner. Coordinates use the existing 0.5m cell-centre convention.
"""
from pathlib import Path
import io
import numpy as np
from .config import RESOLUTION, Robot
from .collision import line_of_sight_exact, segment_cells
from .planners import astar, smooth_cost_aware

START_RADIUS = Robot().footprint_radius
GOAL_RADIUS = 1.0
RETRY_SECONDS = 1.0


def raw_mask(snapshot):
    return np.logical_or.reduce([np.asarray(snapshot[k], bool) for k in
                                 ('detected', 'prior_raw', 'steep')])


def classify_failure(snapshot):
    try:
        blocked = np.asarray(snapshot['lethal'], bool)
        start, goal = (tuple(np.asarray(snapshot[k], int)) for k in ('start', 'goal'))
        if blocked.ndim != 2 or any(len(c) != 2 or any(v < 0 or v >= n for v, n in zip(c, blocked.shape)) for c in (start, goal)):
            return 'other'
        if blocked[goal]:
            return 'goal_cell'
        if blocked[start]:
            return 'start_cell'
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = (start[0]+dx, start[1]+dy)
                if (dx or dy) and all(0 <= v < n for v, n in zip(c, blocked.shape)) and line_of_sight_exact(blocked, start, c):
                    return 'corridor'
        return 'start_cell'
    except (KeyError, ValueError, TypeError, IndexError):
        return 'other'


def escape_maps(snapshot):
    blocked = np.asarray(snapshot['lethal'], bool).copy() | raw_mask(snapshot)
    cost = np.asarray(snapshot['cost'], float).copy()
    xy = np.asarray(snapshot['pose'][:2], float)
    x, y = np.ogrid[:blocked.shape[0], :blocked.shape[1]]
    relaxed = blocked & ~raw_mask(snapshot) & ((x*RESOLUTION-xy[0])**2+(y*RESOLUTION-xy[1])**2 <= START_RADIUS**2+1e-12)
    maximum = float(cost[~blocked & np.isfinite(cost)].max(initial=1.0))
    cost[relaxed], blocked[relaxed] = maximum, False
    return blocked, cost, relaxed


def plan_endpoint(snapshot, policy='none'):
    if policy not in ('none', 'escape'):
        raise ValueError('unknown endpoint policy')
    blocked = np.asarray(snapshot['lethal'], bool).copy()
    cost = np.asarray(snapshot['cost'], float).copy()
    start, goal = (tuple(np.asarray(snapshot[k], int)) for k in ('start', 'goal'))
    relaxed = np.zeros(blocked.shape, bool)
    original = goal
    if policy == 'escape':
        raw = raw_mask(snapshot)
        blocked, cost, relaxed = escape_maps(snapshot)
        x, y = np.ogrid[:blocked.shape[0], :blocked.shape[1]]
        if not all(0 <= v < n for v, n in zip(goal, blocked.shape)) or raw[goal]:
            return dict(success=False, path=[], goal=goal, outcome='unreachable', relaxed=relaxed, lethal=blocked, cost=cost)
        if blocked[goal]:
            candidates = np.argwhere(~blocked & ((x-goal[0])**2+(y-goal[1])**2 <= (GOAL_RADIUS/RESOLUTION)**2+1e-12))
            candidates = sorted(map(tuple, candidates), key=lambda c: ((c[0]-goal[0])**2+(c[1]-goal[1])**2, c))
        else:
            candidates = [goal]
    else:
        candidates = [goal]
    for candidate in candidates:
        result = astar(blocked, start, candidate, cost)
        if result['success']:
            path, _ = smooth_cost_aware(result['path'], blocked, cost, los=line_of_sight_exact)
            # A rounded start must also have a safe continuous connector.
            pos = np.asarray(snapshot['pose'][:2])/RESOLUTION
            joined = [pos.tolist()]+[list(p) for p in path]
            if not line_of_sight_exact(blocked, pos, start):
                continue
            return dict(success=True, path=joined, goal=candidate,
                        outcome='nearby' if candidate != original else 'arrived',
                        relaxed=relaxed, lethal=blocked, cost=cost)
    return dict(success=False, path=[], goal=original, outcome='unreachable', relaxed=relaxed, lethal=blocked, cost=cost)


class SnapshotStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.failure = self.periodic = 0
        self.last_time = None

    def save(self, snapshot, failure=False):
        data = {}
        for key, value in snapshot.items():
            value = np.asarray(value)
            if value.dtype == bool:
                data[key+'_bits'] = np.packbits(value)
                data[key+'_shape'] = value.shape
            else:
                data[key] = value
        buf = io.BytesIO()
        np.savez_compressed(buf, **data)
        if buf.tell() >= 5_000_000:
            raise ValueError('diagnostic snapshot exceeds 5MB')
        attr, prefix = ('failure', 'plan_fail') if failure else ('periodic', 'periodic')
        index = getattr(self, attr)+1
        setattr(self, attr, index)
        target = self.folder/f'{prefix}_{index:06d}.npz'
        if target.exists():
            raise FileExistsError(target)
        target.write_bytes(buf.getvalue())
        if not failure:
            for old in sorted(self.folder.glob('periodic_*.npz'))[:-3]:
                old.unlink()
        return target

    def tick(self, snapshot):
        now = float(snapshot['sim_time'])
        if self.last_time is None or now-self.last_time >= 10.0:
            self.save(snapshot)
            self.last_time = now


def load_snapshot(path):
    with np.load(path, allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files if not k.endswith(('_bits', '_shape'))}
        for key in z.files:
            if key.endswith('_bits'):
                name = key[:-5]
                shape = tuple(z[name+'_shape'])
                data[name] = np.unpackbits(z[key], count=int(np.prod(shape))).reshape(shape).astype(bool)
    return data


class RetryState:
    """One timed retry per stop. No dependence on wall time or endless map waits."""
    def __init__(self):
        self.wait_until = None
        self.retried = False
        self.retries = 0

    def failed(self, sim_time):
        if self.retried:
            return 'unreachable'
        self.wait_until = sim_time+RETRY_SECONDS
        self.retried = True
        self.retries += 1
        return 'waiting'

    def ready(self, sim_time):
        return self.wait_until is None or sim_time >= self.wait_until


def audit_path(path_m, relaxed, truth=None):
    """Exact union length of trajectory segments inside relaxed closed squares.

    Truth is evaluation-only. Shared cell boundaries do not double-count length.
    """
    length = truth_length = 0.0
    cells = set()
    for a, b in zip(np.asarray(path_m)[:-1], np.asarray(path_m)[1:]):
        a, b = a/RESOLUTION, b/RESOLUTION
        delta = b-a
        intervals, truth_intervals = [], []
        for c in segment_cells(a, b, relaxed.shape):
            if not relaxed[tuple(c)]:
                continue
            lo, hi = 0., 1.
            for axis in (0, 1):
                if delta[axis] == 0:
                    continue
                u, v = (c[axis]-.5-a[axis])/delta[axis], (c[axis]+.5-a[axis])/delta[axis]
                lo, hi = max(lo, min(u, v)), min(hi, max(u, v))
            if hi > lo:
                cells.add(tuple(map(int, c)))
                intervals.append((lo, hi))
                if truth is not None and truth[tuple(c)]:
                    truth_intervals.append((lo, hi))
        def union(values):
            end, total = -1., 0.
            for lo, hi in sorted(values):
                total += max(0., hi-max(end, lo))
                end = max(end, hi)
            return total*np.linalg.norm(delta)*RESOLUTION
        length += union(intervals)
        truth_length += union(truth_intervals)
    return dict(relaxed_length_m=float(length), truth_lethal_length_m=float(truth_length), cells=sorted(cells))
