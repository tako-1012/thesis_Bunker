"""Task034 LiDAR adapters; task028 escape/retry definitions remain unchanged."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/thesis_bunker_mission'))
from tapp.online_safety import SafetyOnlinePlanner, validate_fixes
from thesis_bunker_mission.online_safety import SafetyRuntimeMixin
from .lidar_runtime import LidarOnlineMission
from .endpoint_runtime import EndpointRuntime, EndpointPlanner, make_lidar_runtime, RetryState
from .overlap_goal import handoff_lethal


class SafetyLidarMixin(SafetyRuntimeMixin):
    def _observe_join(self, planner, position):
        self.observations = []
        self._observe(planner)

    def _join_blocked(self, planner):
        return handoff_lethal(planner)

    def _plan_work(self, state, position):
        if state['planner'] is None:
            mission = state['mission']
            state['tour'] = dict(order=mission['order'], stops=[tuple(p) for p in mission['stops_cells']])
            state['planner'] = self._new_planner(SafetyOnlinePlanner, state['tour']['stops'])
        result = self._force_safety_plan(state, position, self._observe)
        return result if result is not None else super()._plan_work(state, position)


class SafetyLidarOnlineMission(SafetyLidarMixin, LidarOnlineMission):
    pass


class SafetyEndpointPlanner(SafetyOnlinePlanner, EndpointPlanner):
    """Retain the diagnostics-only EndpointPlanner._plan via cooperative super."""
    pass


class SafetyDiagnosticRuntime(SafetyLidarMixin, EndpointRuntime):
    def _plan_work(self, state, position):
        if state['planner'] is None:
            mission = state['mission']
            state['tour'] = dict(order=mission['order'], stops=[tuple(p) for p in mission['stops_cells']])
            planner = self._new_planner(SafetyEndpointPlanner, state['tour']['stops'])
            planner.owner, planner.policy = self, 'none'
            state['planner'], state['retry'] = planner, RetryState()
        return super()._plan_work(state, position)


def make_safety_lidar_runtime(prior, mapper, *, online_fixes='none', goal_region='none', **kwargs):
    from tapp.goal_region import validate_goal_region

    validate_goal_region(goal_region, kwargs.get('endpoint_policy', 'none'))
    validate_fixes(online_fixes)
    if online_fixes == 'none':
        options = dict(goal_region=goal_region) if goal_region != 'none' else {}
        return make_lidar_runtime(prior, mapper, **kwargs, **options)
    if kwargs.get('endpoint_policy', 'none') != 'none':
        raise ValueError(f'online fixes {online_fixes} uses endpoint-policy none; task028 is unchanged')
    diagnostics = kwargs.pop('diagnostics', False)
    kwargs.pop('endpoint_policy', None)
    if goal_region == 'ring':
        from .goal_region_runtime import RingRuntimeMixin

        class SafetyRingRuntime(RingRuntimeMixin, SafetyDiagnosticRuntime):
            pass

        return SafetyRingRuntime(prior, mapper, endpoint_policy='none', diagnostics=diagnostics,
                                 online_fixes=online_fixes, **kwargs)
    if diagnostics or kwargs.get('save_plan_maps'):
        return SafetyDiagnosticRuntime(prior, mapper, endpoint_policy='none', diagnostics=diagnostics, online_fixes=online_fixes, **kwargs)
    return SafetyLidarOnlineMission(prior, mapper, online_fixes=online_fixes, **kwargs)
