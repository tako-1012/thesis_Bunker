"""Task034 LiDAR adapters; task028 escape/retry definitions remain unchanged."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/thesis_bunker_mission'))
from tapp.online_safety import SafetyOnlinePlanner, validate_fixes
from thesis_bunker_mission.online_safety import SafetyRuntimeMixin
from .lidar_runtime import LidarOnlineMission
from .endpoint_runtime import EndpointRuntime, EndpointPlanner, make_lidar_runtime, RetryState


class SafetyLidarMixin(SafetyRuntimeMixin):
    def _observe_join(self, planner, position):
        self.observations = []
        self._observe(planner)

    def _plan_work(self, state, position):
        if state['planner'] is None:
            mission = state['mission']
            state['tour'] = dict(order=mission['order'], stops=[tuple(p) for p in mission['stops_cells']])
            state['planner'] = SafetyOnlinePlanner(self.prior.cost, self.prior.lethal,
                                                    self.prior_tm.weights, prior_lethal_mode=self.mode)
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
            planner = SafetyEndpointPlanner(self.prior.cost, self.prior.lethal,
                                           self.prior_tm.weights, prior_lethal_mode=self.mode)
            planner.owner, planner.policy = self, 'none'
            state['planner'], state['retry'] = planner, RetryState()
        return super()._plan_work(state, position)


def make_safety_lidar_runtime(prior, mapper, *, online_fixes='none', **kwargs):
    validate_fixes(online_fixes)
    if online_fixes == 'none':
        return make_lidar_runtime(prior, mapper, **kwargs)
    if kwargs.get('endpoint_policy', 'none') != 'none':
        raise ValueError('online fixes v1 uses endpoint-policy none; task028 is unchanged')
    diagnostics = kwargs.pop('diagnostics', False)
    kwargs.pop('endpoint_policy', None)
    if diagnostics:
        return SafetyDiagnosticRuntime(prior, mapper, endpoint_policy='none', diagnostics=True, **kwargs)
    return SafetyLidarOnlineMission(prior, mapper, **kwargs)
