"""First-hit rays on the 075 triangular height field and solid landmark shapes."""

import numpy as np
from scipy.spatial.transform import Rotation

from tapp.config import RESOLUTION
from tapp.sensor_geometry import REAL_MOUNTS


def slab(offset, direction, half_width):
    """Parameter interval inside a slab centred at zero."""
    moving = np.abs(direction) > 1e-14
    safe = np.where(moving, direction, 1.)
    a, b = (-half_width-offset)/safe, (half_width-offset)/safe
    inside = np.abs(offset) <= half_width
    return (np.where(moving, np.minimum(a, b), np.where(inside, -np.inf, np.inf)),
            np.where(moving, np.maximum(a, b), np.where(inside, np.inf, -np.inf)))


class TerrainMesh:
    def __init__(self, elevation, *, flip_diagonal=False):
        self.z = np.round(np.asarray(elevation, dtype=float), 4)
        self.bounds = (np.asarray(self.z.shape)-1)*RESOLUTION
        self.flip_diagonal = flip_diagonal

    def height(self, x, y):
        x = np.clip(x, 0., self.bounds[0])/RESOLUTION
        y = np.clip(y, 0., self.bounds[1])/RESOLUTION
        i = np.minimum(x.astype(int), self.z.shape[0]-2)
        j = np.minimum(y.astype(int), self.z.shape[1]-2)
        u, v = x-i, y-j
        a, b, c, d = self.z[i, j], self.z[i+1, j], self.z[i+1, j+1], self.z[i, j+1]
        if self.flip_diagonal:
            return np.maximum(1-u-v, 0)*a + np.minimum(u, 1-v)*b + np.maximum(u+v-1, 0)*c + np.minimum(v, 1-u)*d
        return (1-np.maximum(u, v))*a + np.maximum(u-v, 0)*b + np.minimum(u, v)*c + np.maximum(v-u, 0)*d

    def ranges_xy(self, origin, bearings, slopes, limit):
        """First intersection, parameterized by horizontal travel.

        Breakpoints are the grid lines and all parallel triangle diagonals.
        The height residual is linear between them. Prefix extrema of the
        height/origin ratios let all elevation channels share the traversal.
        """
        near, far = slab(origin[:2]-self.bounds/2, bearings, self.bounds/2)
        start = np.maximum(0., near.max(axis=1))
        stop = np.minimum(limit, far.min(axis=1))
        active = start <= stop
        start, stop = np.where(active, start, 0.), np.where(active, stop, 0.)
        sign = 1 if self.flip_diagonal else -1
        origin_grid = (*origin[:2], origin[0]+sign*origin[1])
        axes = (*bearings.T, bearings[:, 0]+sign*bearings[:, 1])
        breaks = [start[:, None], stop[:, None]]
        for position, direction in zip(origin_grid, axes):
            step = np.where(direction >= 0, 1, -1)
            line = np.where(direction >= 0, np.ceil(position/RESOLUTION), np.floor(position/RESOLUTION))
            n = int(np.ceil(limit*np.abs(direction).max()/RESOLUTION)) + 1
            travel = ((line[:, None]+step[:, None]*np.arange(n))*RESOLUTION-position)
            crossings = np.divide(travel, direction[:, None], out=np.full_like(travel, np.inf),
                                  where=np.abs(direction[:, None]) > 1e-14)
            breaks.append(np.clip(crossings, start[:, None], stop[:, None]))
        distances = np.sort(np.concatenate(breaks, axis=1), axis=1)
        x = origin[0] + distances*bearings[:, :1]
        y = origin[1] + distances*bearings[:, 1:2]
        delta_z = self.height(x, y)-origin[2]
        ratio_at_zero = np.where(delta_z < 0, -np.inf, np.where(delta_z > 0, np.inf, 0.))
        ratios = np.divide(delta_z, distances, out=ratio_at_zero, where=distances > 0)

        first = delta_z[:, :1] - slopes*start[:, None]
        above = first < 0.
        high = np.maximum.accumulate(ratios, axis=1)
        low = np.minimum.accumulate(ratios, axis=1)
        rows = np.arange(len(bearings))[:, None]
        n = distances.shape[1]
        left, right = np.zeros(first.shape, dtype=int), np.full(first.shape, n)
        while np.any(left < right):
            middle = (left+right)//2
            index = np.minimum(middle, n-1)
            crossed = np.where(above, high[rows, index] >= slopes, low[rows, index] <= slopes)
            searching = left < right
            right = np.where(searching & crossed, middle, right)
            left = np.where(searching & ~crossed, middle+1, left)
        index = np.minimum(left, n-1)
        previous = np.maximum(index-1, 0)
        a, b = distances[rows, previous], distances[rows, index]
        fa = delta_z[rows, previous]-slopes*a
        fb = delta_z[rows, index]-slopes*b
        fraction = np.divide(fa, fa-fb, out=np.zeros_like(fa), where=fa != fb)
        result = np.where(first == 0., start[:, None], a+(b-a)*fraction)
        return np.where(active[:, None] & ((index == left) | (first == 0.)), result, np.inf)


class LandmarkSurfaces:
    def __init__(self, landmarks):
        self.centre = np.array([(p.x_m, p.y_m) for p in landmarks], dtype=float).reshape(-1, 2)
        self.radius = np.array([p.radius_m for p in landmarks])
        self.box = np.array([p.shape == 'box' for p in landmarks], dtype=bool)
        self.half_xy = np.array([(p.width_m/2, p.depth_m/2) for p in landmarks]).reshape(-1, 2)
        self.half_z = np.array([p.height_m/2 for p in landmarks])
        self.centre_z = np.array([p.bottom_z_m+p.height_m/2 for p in landmarks])
        angles = np.array([p.yaw_rad for p in landmarks])
        self.cos, self.sin = np.cos(angles), np.sin(angles)

    def occlude(self, ranges, origin, bearings, slopes, limit):
        """Replace ranges with closer box/cylinder hits, including all caps."""
        delta = self.centre-origin[:2]
        objects = np.flatnonzero(np.linalg.norm(delta, axis=1) <= limit+self.radius)
        if not len(objects):
            return ranges
        xy = delta[objects]
        dot = bearings @ xy.T
        side = bearings[:, :1]*xy[:, 1] - bearings[:, 1:]*xy[:, 0]
        radius = self.radius[objects]
        beam, column = np.nonzero((np.abs(side) <= radius) & (dot >= -radius))
        ids = objects[column]
        v, d = bearings[beam], -delta[ids]

        def rotate(xy):
            c, s = self.cos[ids], self.sin[ids]
            return np.column_stack((xy[:, 0]*c+xy[:, 1]*s, -xy[:, 0]*s+xy[:, 1]*c))

        near, far = slab(rotate(d), rotate(v), self.half_xy[ids])
        around = np.sqrt(np.maximum(0., self.radius[ids]**2 - side[beam, column]**2))
        first = np.where(self.box[ids], near.max(axis=1), dot[beam, column]-around)
        last = np.where(self.box[ids], far.min(axis=1), dot[beam, column]+around)

        z_near, z_far = slab((origin[2]-self.centre_z[ids])[:, None], slopes[beam], self.half_z[ids, None])
        first, last = np.maximum(first[:, None], z_near), np.minimum(last[:, None], z_far)
        hits = np.where((first <= last) & (last >= 0), np.where(first >= 0, first, last), np.inf)
        np.minimum.at(ranges, beam, hits)
        return ranges


class RayScanner:
    """Level sensor pose, with 075's axes and unoccluded XYZ in LiDAR coordinates."""

    def __init__(self, mesh, spec):
        self.mesh, self.spec = mesh, spec
        azimuth = np.linspace(-np.pi, np.pi, spec.horizontal_samples)
        elevation = np.deg2rad(np.linspace(spec.vertical_min_deg, spec.vertical_max_deg, spec.vertical_samples))
        self.bearings = np.column_stack((np.cos(azimuth), np.sin(azimuth)))
        self.cos = np.cos(elevation)
        self.slopes = np.broadcast_to(np.tan(elevation), (len(azimuth), len(elevation)))
        self.directions = np.empty((*self.slopes.shape, 3))
        self.directions[..., :2] = self.bearings[:, None, :]*self.cos[None, :, None]
        self.directions[..., 2] = np.sin(elevation)

    def pose(self, x, y):
        mount = REAL_MOUNTS['lidar']
        pose = np.eye(4)
        pose[:3, :3] = Rotation.from_euler('xyz', mount.rpy).as_matrix()
        pose[:3, 3] = (x, y, self.mesh.height(x, y)) + np.array(mount.xyz)
        return pose

    def ground_ranges(self, origin):
        return self.mesh.ranges_xy(origin, self.bearings, self.slopes, self.spec.max_range_m)

    def scan(self, origin, landmarks, normal, *, ground=None):
        ground = self.ground_ranges(origin) if ground is None else ground.copy()
        ranges = landmarks.occlude(ground, origin, self.bearings, self.slopes, self.spec.max_range_m)/self.cos
        seen = (ranges >= self.spec.min_range_m) & (ranges <= self.spec.max_range_m)
        noisy = ranges[seen] + self.spec.noise_stddev_m*normal[seen]
        valid = (noisy >= self.spec.min_range_m) & (noisy <= self.spec.max_range_m)
        # Gazebo PointCloud2 has vertical rows, with azimuth varying first.
        scan = np.full_like(self.directions, np.nan)
        scan[seen] = self.directions[seen]*np.where(valid, noisy, np.nan)[:, None]
        return scan.transpose(1, 0, 2)
