"""Keep overlap observations intact and apply centre clearance to the active goal."""

from contextlib import contextmanager


class OverlapGoalPlanner:
    def set_goal_overrides(self, overrides):
        # The base safety planner compares overlap observations. It also
        # needs a transition where only the centre changed to blocked.
        pending = getattr(self, 'pending_changed', None)
        if pending is not None and not self.goal_overrides.get(self.goal, True) and overrides.get(self.goal, True):
            pending[self.goal] |= self.lethal[self.goal]
        self.goal_overrides = overrides

    def goals_to_check(self):
        # Include a nearby substitute if an endpoint policy selected one.
        return self.goal_cells if self.goal is None else self.goal_cells | {self.goal}

    @contextmanager
    def _goal_clearance(self, goal):
        if self.goal_overrides.get(goal, True):
            yield
            return
        was_blocked = self.lethal[goal]
        self.lethal[goal] = False
        try:
            yield
        finally:
            self.lethal[goal] = was_blocked

    def _plan(self, reason, initial=False):
        goal = self.target if getattr(self, 'policy', 'none') != 'none' else self.goal
        with self._goal_clearance(goal):
            return super()._plan(reason, initial=initial)

    def update(self, pos_xy, *, distance_m=None):
        with self._goal_clearance(self.goal):
            return super().update(pos_xy, distance_m=distance_m)


def handoff_lethal(planner):
    blocked = planner.known & planner.lethal
    if not getattr(planner, 'goal_overrides', {}).get(planner.goal, True):
        blocked[planner.goal] = False
    margin = getattr(planner, 'tracking_clearance', None)
    if margin is not None:
        blocked |= margin.protected(planner.tracking_relaxed_layers)
    return blocked


def goal_snapshot(planner, snapshot, goal):
    """Project a captured overlap map for this search, keeping it for later legs."""
    overrides = getattr(planner, 'goal_overrides', {})
    if goal not in overrides:
        return snapshot
    actual = dict(snapshot)
    if not overrides[goal]:
        actual['lethal'] = snapshot['lethal'].copy()
        actual['lethal'][goal] = False
    if 'obstacle_halo' in snapshot:
        actual['obstacle_halo'] = snapshot['obstacle_halo'].copy()
        actual['obstacle_halo'][goal] = False
    return actual
