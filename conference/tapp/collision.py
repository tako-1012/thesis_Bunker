"""Closed-cell segment intersections using exact slab clipping, not sampling."""
import numpy as np

EPS = 1e-9


def segment_cells(a, b, shape) -> np.ndarray:
    """Clip against each intersected row slab, then enumerate its touched columns.

    Squares are expanded by EPS on every side. This includes edge/corner
    contact conservatively without scanning the whole bounding rectangle.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != (2,) or b.shape != (2,) or not np.isfinite([a, b]).all():
        raise ValueError("endpoints must be finite 2D coordinates")
    empty = np.empty((0, 2), dtype=int)
    lo = max(0, int(np.ceil(min(a[0], b[0]) - 0.5 - EPS)))
    hi = min(shape[0] - 1, int(np.floor(max(a[0], b[0]) + 0.5 + EPS)))
    if lo > hi or shape[1] <= 0:
        return empty
    rows = np.arange(lo, hi + 1)
    delta = b - a
    if delta[0] == 0:
        t0, t1 = np.zeros(len(rows)), np.ones(len(rows))
    else:
        left = (rows - 0.5 - EPS - a[0]) / delta[0]
        right = (rows + 0.5 + EPS - a[0]) / delta[0]
        t0 = np.maximum(0, np.minimum(left, right))
        t1 = np.minimum(1, np.maximum(left, right))
    valid = t0 <= t1
    rows, t0, t1 = rows[valid], t0[valid], t1[valid]
    y0, y1 = a[1] + delta[1] * t0, a[1] + delta[1] * t1
    first = np.maximum(0, np.ceil(np.minimum(y0, y1) - 0.5 - EPS)).astype(int)
    last = np.minimum(shape[1] - 1, np.floor(np.maximum(y0, y1) + 0.5 + EPS)).astype(int)
    counts = np.maximum(last - first + 1, 0)
    total = int(counts.sum())
    if total == 0:
        return empty
    offsets = np.cumsum(counts) - counts
    xs = np.repeat(rows, counts)
    ys = np.repeat(first, counts) + np.arange(total) - np.repeat(offsets, counts)
    return np.column_stack((xs, ys))


def line_of_sight_exact(blocked, a, b) -> bool:
    cells = segment_cells(a, b, blocked.shape)
    return not bool(blocked[cells[:, 0], cells[:, 1]].any())


def path_lethal_cells(path, blocked) -> np.ndarray:
    points = np.asarray(path, dtype=float)
    hits = []
    segments = zip(points[:-1], points[1:]) if len(points) > 1 else ((p, p) for p in points)
    for a, b in segments:
        cells = segment_cells(a, b, blocked.shape)
        lethal = cells[blocked[cells[:, 0], cells[:, 1]]]
        if len(lethal):
            hits.append(lethal)
    return np.unique(np.concatenate(hits), axis=0) if hits else np.empty((0, 2), dtype=int)
