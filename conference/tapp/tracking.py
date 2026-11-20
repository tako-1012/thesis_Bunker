"""Opt-in corner speed control layered on Pure Pursuit's existing progress."""

import math

import numpy as np

from .online_safety import make_follower
from .pure_pursuit import PurePursuit

TRACKINGS = ('default', 'corner_slow')
CORNER_LOOKAHEAD_M = 2.
MIN_SPEED_FRACTION = .3
SPIN_ANGLE_RAD = math.pi/4


def validate_tracking(tracking):
    if tracking not in TRACKINGS:
        raise ValueError('unknown path tracking')
    return tracking


def corner_turns(path):
    delta = np.diff(path, axis=0)
    heading = np.arctan2(delta[:, 1], delta[:, 0])
    return np.abs((np.diff(heading)+np.pi) % (2*np.pi)-np.pi)


class CornerSlowPursuit(PurePursuit):
    """Retain projection and target arc, with a corner-limited speed command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.turn_arc = self.arc[1:-1]
        self.turn_sum = np.r_[0., np.cumsum(corner_turns(self.path))]

    def command(self, pose):
        _, _, done = super().command(pose)
        if done:
            return 0., 0., True
        xy = np.asarray(pose, float)
        target_s = min(self.arc[-1], self.progress+self.lookahead_m)
        dx = np.interp(target_s, self.arc, self.path[:, 0])-xy[0]
        dy = np.interp(target_s, self.arc, self.path[:, 1])-xy[1]
        alpha = (math.atan2(dy, dx)-xy[2]+math.pi) % (2*math.pi)-math.pi
        if abs(alpha) > SPIN_ANGLE_RAD:
            return 0., math.copysign(self.w_max, alpha), False

        first, end = np.searchsorted(self.turn_arc, [self.progress, self.progress+CORNER_LOOKAHEAD_M], side='right')
        # Accumulate absolute changes so an S-bend still slows the robot.
        angle = min(math.pi, float(self.turn_sum[end]-self.turn_sum[first]))
        speed = self.v_max*max(MIN_SPEED_FRACTION, math.cos(angle))
        curvature = 2*math.sin(alpha)/max(math.hypot(dx, dy), 1e-12)
        omega = speed*curvature
        scale = min(1., self.w_max/max(abs(omega), 1e-12))
        return speed*scale, omega*scale, False


def make_tracking_follower(*args, online_fixes='none', tracking='default', **kwargs):
    validate_tracking(tracking)
    follower = make_follower(*args, online_fixes=online_fixes, **kwargs)
    if tracking == 'corner_slow':
        steady = follower.controller
        follower.controller = CornerSlowPursuit(steady.path, steady.lookahead_m, steady.v_max,
                                                 steady.w_max, steady.goal_tol_m)
    return follower
