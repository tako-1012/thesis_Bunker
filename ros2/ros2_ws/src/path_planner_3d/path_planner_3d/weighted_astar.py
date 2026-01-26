"""
Weighted A* planner aligned with BasePlanner3D.
Uses grid indices for robustness against floating errors.
"""
import heapq
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .base_planner import BasePlanner3D
from .planning_result import PlanningResult
from .search_node import SearchNode

logger = logging.getLogger(__name__)

TerrainCostFn = Callable[[Tuple[float, float, float], Tuple[float, float, float], Optional[Dict]], float]


class WeightedAStar(BasePlanner3D):
    """Weighted A* search on a regular voxel grid."""

    def __init__(self, config, epsilon: float = 1.5, terrain_cost_fn: Optional[TerrainCostFn] = None):
        super().__init__(config)
        self.epsilon = max(1.0, epsilon)
        self.terrain_cost_fn = terrain_cost_fn

    def plan_path(
        self,
        start: List[float],
        goal: List[float],
        terrain_data: Optional[Dict] = None,
        timeout: Optional[float] = None,
        epsilon: Optional[float] = None,
    ) -> PlanningResult:
        start_time = time.time()
        time_limit = timeout if timeout is not None else self._calculate_timeout()
        eps = max(1.0, epsilon if epsilon is not None else self.epsilon)

        start_idx = self._to_index(start)
        goal_idx = self._to_index(goal)
        logger.info(f"WeightedAStar: start={start} -> idx={start_idx}, goal={goal} -> idx={goal_idx}, eps={eps}")

        open_heap: List[Tuple[float, int, SearchNode]] = []
        g_scores = {start_idx: 0.0}
        closed: set = set()

        h0 = self._heuristic(start_idx, goal_idx)
        start_node = SearchNode(f=h0, position=start_idx, g=0.0, h=h0, parent=None)
        heapq.heappush(open_heap, (start_node.f, id(start_node), start_node))

        nodes_explored = 0

        while open_heap:
            if time.time() - start_time > time_limit:
                return self._timeout_result(nodes_explored, start_time)

            _, _, current = heapq.heappop(open_heap)
            if current.position in closed:
                continue
            closed.add(current.position)
            nodes_explored += 1

            if current.position == goal_idx or self._is_goal(self._index_to_world(current.position), goal):
                path = self._reconstruct_path(current)
                path_length = self._calculate_path_length(path)
                logger.info(f"WeightedAStar success: nodes_explored={nodes_explored}, path_length={path_length:.2f}")
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=path_length,
                    nodes_explored=nodes_explored,
                    algorithm_name="WeightedAStar",
                )

            valid_neighbors = 0
            inf_neighbors = 0
            inf_reasons = []
            for neighbor_idx in self._neighbors(current.position):
                if neighbor_idx in closed:
                    continue
                if not self._is_valid_index(neighbor_idx):
                    continue

                from_world = self._index_to_world(current.position)
                to_world = self._index_to_world(neighbor_idx)

                move_cost = self._movement_cost(from_world, to_world)
                if move_cost == float("inf"):
                    inf_neighbors += 1
                    if nodes_explored == 1:
                        inf_reasons.append(f"{neighbor_idx}:slope")
                    continue
                
                terrain_cost = 0.0
                if self.terrain_cost_fn is not None:
                    terrain_cost = self.terrain_cost_fn(from_world, to_world, terrain_data)
                    if terrain_cost == float("inf"):
                        inf_neighbors += 1
                        if nodes_explored == 1:
                            inf_reasons.append(f"{neighbor_idx}:terrain")
                        continue
                
                valid_neighbors += 1
                tentative_g = current.g + move_cost + terrain_cost

                if tentative_g >= g_scores.get(neighbor_idx, float("inf")):
                    continue

                h_score = self._heuristic(neighbor_idx, goal_idx)
                f_score = tentative_g + eps * h_score
                g_scores[neighbor_idx] = tentative_g
                neighbor_node = SearchNode(f=f_score, position=neighbor_idx, g=tentative_g, h=h_score, parent=current)
                heapq.heappush(open_heap, (neighbor_node.f, id(neighbor_node), neighbor_node))
            
            if nodes_explored <= 3:
                logger.info(f"  Node {nodes_explored}: pos={current.position}, valid={valid_neighbors}, inf={inf_neighbors}")
                if nodes_explored == 1:
                    logger.info(f"    inf_reasons (sample): {inf_reasons[:10]}")

        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0.0,
            nodes_explored=nodes_explored,
            error_message="No path found",
            algorithm_name="WeightedAStar",
        )

    def _movement_cost(self, pos_from: Tuple[float, float, float], pos_to: Tuple[float, float, float]) -> float:
        dx = pos_to[0] - pos_from[0]
        dy = pos_to[1] - pos_from[1]
        dz = pos_to[2] - pos_from[2]
        distance = float(np.sqrt(dx * dx + dy * dy + dz * dz))

        slope = self._calculate_slope(pos_from, pos_to)
        if slope > self.max_slope_rad:
            return float("inf")
        slope_penalty = (slope / self.max_slope_rad) * 1.5
        return distance + slope_penalty

    def _neighbors(self, idx: Tuple[int, int, int]) -> List[Tuple[int, int, int]]:
        x, y, z = idx
        res = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    res.append((x + dx, y + dy, z + dz))
        return res

    def _heuristic(self, idx: Tuple[int, int, int], goal_idx: Tuple[int, int, int]) -> float:
        ix, iy, iz = idx
        gx, gy, gz = goal_idx
        return float(np.sqrt((ix - gx) ** 2 + (iy - gy) ** 2 + (iz - gz) ** 2)) * self.voxel_size

    def _is_valid_index(self, idx: Tuple[int, int, int]) -> bool:
        wx, wy, wz = self._index_to_world(idx)
        return self._is_valid_position((wx, wy, wz))

    def _to_index(self, pos: List[float]) -> Tuple[int, int, int]:
        p = np.array(pos)
        rel = (p - self.min_bound) / self.voxel_size
        return tuple(int(round(v)) for v in rel)

    def _index_to_world(self, idx: Tuple[int, int, int]) -> Tuple[float, float, float]:
        x = self.min_bound[0] + idx[0] * self.voxel_size
        y = self.min_bound[1] + idx[1] * self.voxel_size
        z = self.min_bound[2] + idx[2] * self.voxel_size
        return (float(x), float(y), float(z))

    def _reconstruct_path(self, node: SearchNode) -> List[Tuple[float, float, float]]:
        path_idx: List[Tuple[int, int, int]] = []
        current = node
        while current is not None:
            path_idx.append(current.position)
            current = current.parent
        path_idx.reverse()
        return [self._index_to_world(idx) for idx in path_idx]

    def _timeout_result(self, nodes_explored: int, start_time: float) -> PlanningResult:
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0.0,
            nodes_explored=nodes_explored,
            error_message="Timeout",
            algorithm_name="WeightedAStar",
        )
