"""
Anytime Hierarchical A* (AHA*) implementation using Weighted A* at fine resolution.
The planner builds a coarse guide path then refines it with decreasing epsilon values.
"""
import time
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from .base_planner import BasePlanner3D
from .planning_result import PlanningResult
from .weighted_astar import WeightedAStar, TerrainCostFn

logger = logging.getLogger(__name__)


class AnytimeHierarchicalAStar(BasePlanner3D):
    """Simple AHA* implementation backed by Weighted A* search."""

    def __init__(
        self,
        config,
        coarse_factor: int = 3,
        initial_epsilon: float = 2.0,
        epsilon_decay: float = 0.8,
        min_epsilon: float = 1.0,
        terrain_cost_fn: Optional[TerrainCostFn] = None,
    ):
        super().__init__(config)
        self.coarse_factor = max(1, coarse_factor)
        self.initial_epsilon = max(1.0, initial_epsilon)
        self.epsilon_decay = min(max(0.5, epsilon_decay), 0.99)
        self.min_epsilon = max(1.0, min_epsilon)
        self.low_level = WeightedAStar(config, epsilon=self.initial_epsilon, terrain_cost_fn=terrain_cost_fn)
        self.coarse_voxel = self.voxel_size * self.coarse_factor

    def plan_path(
        self,
        start: List[float],
        goal: List[float],
        terrain_data: Optional[Dict] = None,
        timeout: Optional[float] = None,
    ) -> PlanningResult:
        start_time = time.time()
        time_limit = timeout if timeout is not None else self._calculate_timeout()

        coarse_path_idx = self._coarse_guide(start, goal)
        best_result: Optional[PlanningResult] = None
        current_epsilon = self.initial_epsilon

        # Anytime loop with early-exit heuristics
        best_cost = float('inf')
        previous_cost = float('inf')
        no_improvement_count = 0
        improvement_threshold = 0.01  # 1% relative improvement
        iteration = 0
        initial_cost = None
        iter_times: List[float] = []
        early_exit_reason = None

        while current_epsilon >= self.min_epsilon - 1e-6:
            iter_start = time.time()
            elapsed = iter_start - start_time
            remaining = time_limit - elapsed
            if remaining <= 0.0:
                early_exit_reason = 'time_limit'
                logger.info("AHA*: time limit reached before iteration start")
                break

            # If not enough time left for a meaningful iteration, stop
            if remaining < 1.0:
                early_exit_reason = 'insufficient_time'
                logger.info(f"AHA*: insufficient remaining time ({remaining:.2f}s), stopping")
                break

            # Estimate whether we can perform another iteration based on past timings
            if iteration > 0:
                avg_iter = sum(iter_times) / len(iter_times)
                if remaining < avg_iter * 1.5:
                    early_exit_reason = 'not_enough_time_for_next_iter'
                    logger.info(f"AHA*: not enough time for another iteration (rem={remaining:.2f}s, avg_iter={avg_iter:.2f}s)")
                    break

            # Run one refinement pass
            path, nodes = self._refine_with_segments(
                coarse_path_idx,
                start,
                goal,
                terrain_data,
                epsilon=current_epsilon,
                time_budget=remaining,
            )

            iter_time = time.time() - iter_start
            iter_times.append(iter_time)

            cost = float('inf')
            if path:
                cost = self._calculate_path_length(path)
                # record initial solution cost
                if iteration == 0:
                    initial_cost = cost

                # update best
                if cost < best_cost:
                    improvement = (previous_cost - cost) / previous_cost if previous_cost != float('inf') else 1.0
                    if improvement < improvement_threshold:
                        no_improvement_count += 1
                    else:
                        no_improvement_count = 0

                    previous_cost = best_cost
                    best_cost = cost
                    best_result = PlanningResult(
                        success=True,
                        path=path,
                        computation_time=time.time() - start_time,
                        path_length=cost,
                        nodes_explored=nodes,
                        algorithm_name="AnytimeHierarchicalAStar",
                    )
                else:
                    no_improvement_count += 1

                logger.info(f"Iteration {iteration}: weight={current_epsilon:.2f}, cost={cost:.2f}, nodes={nodes}, iter_time={iter_time:.2f}s, remaining={remaining:.2f}s")
            else:
                no_improvement_count += 1
                logger.info(f"Iteration {iteration}: weight={current_epsilon:.2f}, no path found, iter_time={iter_time:.2f}s, remaining={remaining:.2f}s")

            # Early termination: no significant improvement in consecutive iterations
            if no_improvement_count >= 2:
                early_exit_reason = 'no_improvement'
                logger.info(f"Early termination: no improvement for {no_improvement_count} iterations")
                break

            # Early termination: if initial solution is already good (<=110% of initial)
            if initial_cost is not None and best_cost != float('inf') and iteration > 0:
                if best_cost <= initial_cost * 1.1:
                    early_exit_reason = 'good_solution'
                    logger.info(f"Early termination: solution within 10% of initial (best={best_cost:.2f}, initial={initial_cost:.2f})")
                    break

            # Early termination: weight small enough (near-optimal)
            if current_epsilon <= 1.2 and best_result is not None:
                early_exit_reason = 'epsilon_low'
                logger.info(f"Early termination: epsilon sufficiently low ({current_epsilon:.2f})")
                break

            # Update epsilon (multiplicative decay)
            next_epsilon = max(self.min_epsilon, current_epsilon * self.epsilon_decay)
            # If no change in epsilon (already at min), stop
            if abs(next_epsilon - current_epsilon) < 1e-6:
                early_exit_reason = 'epsilon_min'
                logger.info("AHA*: epsilon reached minimum")
                break
            current_epsilon = next_epsilon
            iteration += 1

        # attach diagnostics
        if best_result is not None:
            try:
                best_result.iterations = iteration
                best_result.early_exit_reason = early_exit_reason or 'none'
            except Exception:
                pass

        if best_result is not None:
            best_result.computation_time = time.time() - start_time
            return best_result

        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0.0,
            nodes_explored=0,
            error_message="AHA* failed to find a path",
            algorithm_name="AnytimeHierarchicalAStar",
        )

    # Compatibility wrapper used by some benchmark harnesses
    def plan(self, start: List[float], goal: List[float], terrain_data: Optional[Dict] = None, timeout: Optional[float] = None) -> PlanningResult:
        return self.plan_path(start, goal, terrain_data=terrain_data, timeout=timeout)

    def _coarse_guide(self, start: List[float], goal: List[float]) -> List[Tuple[int, int, int]]:
        start_idx = self._to_coarse_index(start)
        goal_idx = self._to_coarse_index(goal)
        guide = self._straight_line_indices(start_idx, goal_idx)
        logger.info(f"AHA* coarse guide: start_idx={start_idx}, goal_idx={goal_idx}, guide_length={len(guide)}")
        return guide

    def _straight_line_indices(self, start_idx: Tuple[int, int, int], goal_idx: Tuple[int, int, int]) -> List[Tuple[int, int, int]]:
        path = []
        x0, y0, z0 = start_idx
        x1, y1, z1 = goal_idx
        steps = int(max(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)))
        if steps == 0:
            return [start_idx]
        for i in range(steps + 1):
            t = i / steps
            xi = int(round(x0 + (x1 - x0) * t))
            yi = int(round(y0 + (y1 - y0) * t))
            zi = int(round(z0 + (z1 - z0) * t))
            if not path or (xi, yi, zi) != path[-1]:
                path.append((xi, yi, zi))
        return path

    def _refine_with_segments(
        self,
        coarse_indices: List[Tuple[int, int, int]],
        start: List[float],
        goal: List[float],
        terrain_data: Optional[Dict],
        epsilon: float,
        time_budget: float,
    ) -> Tuple[List[Tuple[float, float, float]], int]:
        segments = self._coarse_segments(coarse_indices, start, goal)
        logger.info(f"AHA* refine: coarse_indices={len(coarse_indices)}, segments={len(segments)}, epsilon={epsilon:.2f}, time_budget={time_budget:.2f}s")
        if not segments:
            logger.warning("AHA* refine: no segments generated!")
            return [], 0

        combined: List[Tuple[float, float, float]] = []
        nodes_total = 0
        per_segment_time = max(1.0, time_budget / max(1, len(segments)))

        for i, (seg_start, seg_goal) in enumerate(segments):
            remaining_segments = len(segments) - i
            budget = per_segment_time if remaining_segments <= 1 else per_segment_time * remaining_segments
            logger.info(f"AHA* segment {i+1}/{len(segments)}: start={seg_start}, goal={seg_goal}, budget={budget:.2f}s")
            result = self.low_level.plan_path(
                list(seg_start),
                list(seg_goal),
                terrain_data=terrain_data,
                timeout=budget,
                epsilon=epsilon,
            )
            logger.info(f"AHA* segment {i+1} result: success={result.success}, nodes={result.nodes_explored}, path_len={len(result.path)}")
            nodes_total += result.nodes_explored
            if not result.success:
                logger.warning(f"AHA* segment {i+1} failed")
                return [], nodes_total
            if combined:
                combined.extend(result.path[1:])
            else:
                combined.extend(result.path)
        return combined, nodes_total

    def _coarse_segments(
        self,
        coarse_indices: List[Tuple[int, int, int]],
        start: List[float],
        goal: List[float],
    ) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
        """Generate fine segments from coarse guide, interpolating Z between start and goal."""
        if not coarse_indices:
            return [(tuple(start), tuple(goal))]

        # Generate waypoints with Z interpolation
        waypoints = []
        total_segments = len(coarse_indices) - 1
        for i, idx in enumerate(coarse_indices):
            x = self.min_bound[0] + idx[0] * self.coarse_voxel
            y = self.min_bound[1] + idx[1] * self.coarse_voxel
            # Linearly interpolate Z between start and goal
            if total_segments > 0:
                t = i / total_segments
                z = start[2] * (1 - t) + goal[2] * t
            else:
                z = start[2]
            waypoints.append((x, y, z))
        
        if not waypoints:
            return [(tuple(start), tuple(goal))]
        
        # Override first and last waypoints with exact start/goal
        waypoints[0] = tuple(start)
        waypoints[-1] = tuple(goal)
        
        segments = []
        for i in range(len(waypoints) - 1):
            segments.append((waypoints[i], waypoints[i + 1]))
        return segments

    def _to_coarse_index(self, pos: List[float]) -> Tuple[int, int, int]:
        p = np.array(pos)
        rel = (p - self.min_bound) / self.coarse_voxel
        return tuple(int(round(v)) for v in rel)

    def _coarse_to_world(self, idx: Tuple[int, int, int]) -> Tuple[float, float, float]:
        x = self.min_bound[0] + idx[0] * self.coarse_voxel
        y = self.min_bound[1] + idx[1] * self.coarse_voxel
        z = self.min_bound[2] + idx[2] * self.coarse_voxel
        return (float(x), float(y), float(z))
