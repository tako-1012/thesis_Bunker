"""Exact first hits on a triangular raster with arbitrary spacing and holes."""

import numpy as np

from experiments.localizability_rays import slab


class RasterTerrain:
    """A terrain vertex at origin_xy + spacing*(i, j), with NaN for missing data."""

    def __init__(self, elevation, spacing, *, origin_xy=(0., 0.)):
        self.z = np.round(np.asarray(elevation, dtype=float), 4)
        if self.z.ndim != 2 or min(self.z.shape) < 2 or np.isinf(self.z).any():
            raise ValueError('terrain must be a 2-D raster with finite or NaN vertices')
        self.spacing = float(spacing)
        self.origin_xy = np.asarray(origin_xy, dtype=float)
        if (not np.isfinite(self.spacing) or self.spacing <= 0
                or self.origin_xy.shape != (2,) or not np.isfinite(self.origin_xy).all()):
            raise ValueError('invalid terrain spacing or origin')
        self.bounds = (np.asarray(self.z.shape)-1)*self.spacing
        a, b, c, d = self.z[:-1, :-1], self.z[1:, :-1], self.z[1:, 1:], self.z[:-1, 1:]
        # Same lower-left to upper-right diagonal and vertex quantization as 079.
        self.dx = np.stack((b-a, c-d))
        self.dy = np.stack((c-b, d-a))

    def height(self, x, y):
        gx, gy = np.broadcast_arrays((np.asarray(x)-self.origin_xy[0])/self.spacing,
                                     (np.asarray(y)-self.origin_xy[1])/self.spacing)
        # Floating-point representations of a vertex should keep its identity.
        gx = np.where(abs(gx-np.rint(gx)) < 1e-10, np.rint(gx), gx)
        gy = np.where(abs(gy-np.rint(gy)) < 1e-10, np.rint(gy), gy)
        nx, ny = self.z.shape
        inside = (0 <= gx) & (gx <= nx-1) & (0 <= gy) & (gy <= ny-1)
        i = np.clip(np.floor(gx).astype(int), 0, nx-2)
        j = np.clip(np.floor(gy).astype(int), 0, ny-2)
        u, v = gx-i, gy-j
        weights = (1-np.maximum(u, v), np.maximum(u-v, 0), np.minimum(u, v), np.maximum(v-u, 0))
        vertices = (self.z[i, j], self.z[i+1, j], self.z[i+1, j+1], self.z[i, j+1])
        result = sum(weight*np.where(weight != 0., z, 0.) for weight, z in zip(weights, vertices))
        return np.where(inside, result, np.nan)

    def breakpoints(self, xy, bearings, start, stop):
        """Grid and parallel-diagonal crossings; each open interval is in one facet."""
        h = self.spacing
        pieces = [start[:, None], stop[:, None]]
        longest = stop.max()
        for pos, direction in zip((*xy, xy[0]-xy[1]), (*bearings.T, bearings[:, 0]-bearings[:, 1])):
            step = np.where(direction >= 0., 1, -1)
            line = np.where(direction >= 0., np.ceil(pos/h), np.floor(pos/h))
            num = int(np.ceil(longest*np.abs(direction).max()/h))+1
            offset = (line[:, None]+step[:, None]*np.arange(num))*h-pos
            crossings = np.divide(offset, direction[:, None], out=np.full_like(offset, np.inf),
                                  where=np.abs(direction[:, None]) > 1e-14)
            pieces.append(np.clip(crossings, start[:, None], stop[:, None]))
        return np.sort(np.concatenate(pieces, axis=1), axis=1)

    def ranges_xy(self, origin, bearings, slopes, limit):
        """Return horizontal ranges, never treating an absence of terrain as a surface."""
        xy = np.asarray(origin[:2])-self.origin_xy
        near, far = slab(xy-self.bounds/2, bearings, self.bounds/2)
        start = np.maximum(0., near.max(axis=1))
        stop = np.minimum(limit, far.min(axis=1))
        result = np.full(slopes.shape, np.inf)
        active = np.flatnonzero(start < stop)
        if len(active):
            result[active] = self.first_hits(xy, origin[2], bearings[active], slopes[active],
                                             start[active], stop[active])
        tangent = np.flatnonzero(start == stop)
        if len(tangent):
            positions = np.asarray(origin[:2])+start[tangent, None]*bearings[tangent]
            altitude = self.height(*positions.T)
            hit = altitude[:, None] == origin[2]+start[tangent, None]*slopes[tangent]
            result[tangent] = np.where(hit, start[tangent, None], np.inf)
        return result

    def first_hits(self, xy, origin_z, bearings, slopes, start, stop):
        distances = self.breakpoints(xy, bearings, start, stop)
        left, right = distances[:, :-1], distances[:, 1:]
        mid = (left+right)*.5
        base = xy/self.spacing
        rate = bearings/self.spacing
        gx, gy = (base[0]+rate[:, :1]*mid), (base[1]+rate[:, 1:]*mid)
        i = np.clip(np.floor(gx).astype(int), 0, self.z.shape[0]-2)
        j = np.clip(np.floor(gy).astype(int), 0, self.z.shape[1]-2)
        upper = ((gx-i) < (gy-j)).astype(int)
        dx, dy = self.dx[upper, i, j], self.dy[upper, i, j]
        height_at_zero = self.z[i, j] + dx*(base[0]-i) + dy*(base[1]-j) - origin_z
        along = dx*rate[:, :1] + dy*rate[:, 1:]
        valid = (right-left > 1e-12) & np.isfinite(height_at_zero)

        # Select each channel's first occupied interval by its range of slopes.
        # Ratios are never connected across two intervals separated by a hole.
        zero = np.where(height_at_zero >= 0., np.inf, -np.inf)
        before = along+np.divide(height_at_zero, left, out=zero, where=left > 0.)
        after = along+np.divide(height_at_zero, right, out=np.zeros_like(right), where=right > 0.)
        lower, upper = np.minimum(before, after), np.maximum(before, after)
        at_origin = (left == 0.) & (height_at_zero == 0.)
        result = np.full(slopes.shape, np.inf)
        for channel, s in enumerate(slopes.T):
            crosses = valid & (((lower <= s[:, None]) & (s[:, None] <= upper)) | at_origin)
            rows = np.flatnonzero(crosses.any(axis=1))
            columns = np.argmax(crosses[rows], axis=1)
            index = (rows, columns)
            diff = s[rows]-along[index]
            crossing = np.divide(height_at_zero[index], diff, out=left[index].copy(), where=diff != 0.)
            result[rows, channel] = np.clip(crossing, left[index], right[index])
        return result
