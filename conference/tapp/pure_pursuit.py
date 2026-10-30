"""Monotone arc-length Pure Pursuit with spin-in-place and curvature-preserving caps."""

import math
import numpy as np


def prepare_path(path_xy):
    path = np.asarray(path_xy, dtype=float)
    if (
        path.ndim != 2
        or path.shape[1] != 2
        or not len(path)
        or not np.isfinite(path).all()
    ):
        raise ValueError("経路は有限な(x,y)の点列にしてください")
    keep = np.r_[True, np.any(np.diff(path, axis=0) != 0, axis=1)]
    return path[keep]


def path_distance(point, path):
    if len(path) == 1:
        return float(np.linalg.norm(point - path[0]))
    delta = np.diff(path, axis=0)
    t = np.clip(
        np.sum((point - path[:-1]) * delta, axis=1) / np.sum(delta**2, axis=1), 0, 1
    )
    return float(np.linalg.norm(point - (path[:-1] + t[:, None] * delta), axis=1).min())


class PurePursuit:
    def __init__(self, path_xy, lookahead_m=1.0, v_max=1.0, w_max=1.0, goal_tol_m=0.3):
        if any(
            not math.isfinite(v) or v <= 0
            for v in (lookahead_m, v_max, w_max, goal_tol_m)
        ):
            raise ValueError("追従パラメータは正の有限値にしてください")
        self.path = prepare_path(path_xy)
        self.lookahead_m, self.v_max, self.w_max, self.goal_tol_m = (
            lookahead_m,
            v_max,
            w_max,
            goal_tol_m,
        )
        self.lengths = np.linalg.norm(np.diff(self.path, axis=0), axis=1)
        self.arc = np.r_[0.0, np.cumsum(self.lengths)]
        self.progress = 0.0

    def command(self, pose):
        pose = np.asarray(pose, dtype=float)
        if pose.shape != (3,) or not np.isfinite(pose).all():
            raise ValueError("姿勢は有限な(x,y,yaw)にしてください")
        if len(self.path) > 1:
            # Restrict projection to a forward window, preventing shortcuts to the
            # final base of a closed tour or to distant self-intersections.
            upper = min(self.arc[-1], self.progress + 2 * self.lookahead_m)
            indices = np.flatnonzero(
                (self.arc[1:] >= self.progress) & (self.arc[:-1] <= upper)
            )
            delta = self.path[indices + 1] - self.path[indices]
            low = np.maximum(
                0, (self.progress - self.arc[indices]) / self.lengths[indices]
            )
            high = np.minimum(1, (upper - self.arc[indices]) / self.lengths[indices])
            fractions = np.clip(
                np.sum((pose[:2] - self.path[indices]) * delta, axis=1)
                / self.lengths[indices] ** 2,
                low,
                high,
            )
            projections = self.path[indices] + fractions[:, None] * delta
            best = int(np.argmin(np.linalg.norm(projections - pose[:2], axis=1)))
            self.progress = max(
                self.progress,
                float(
                    self.arc[indices[best]]
                    + fractions[best] * self.lengths[indices[best]]
                ),
            )
        goal_distance = float(np.linalg.norm(self.path[-1] - pose[:2]))
        if (
            self.progress >= self.arc[-1] - self.goal_tol_m
            and goal_distance <= self.goal_tol_m
        ):
            return 0.0, 0.0, True
        target_s = min(self.arc[-1], self.progress + self.lookahead_m)
        target = np.array(
            [np.interp(target_s, self.arc, self.path[:, i]) for i in (0, 1)]
        )
        vector = target - pose[:2]
        alpha = (math.atan2(vector[1], vector[0]) - pose[2] + math.pi) % (
            2 * math.pi
        ) - math.pi
        if abs(alpha) > math.pi / 2:
            return 0.0, math.copysign(self.w_max, alpha), False
        curvature = 2 * math.sin(alpha) / max(float(np.linalg.norm(vector)), 1e-12)
        raw_w = self.v_max * curvature
        scale = min(1.0, self.w_max / max(abs(raw_w), 1e-12))
        return self.v_max * scale, raw_w * scale, False
