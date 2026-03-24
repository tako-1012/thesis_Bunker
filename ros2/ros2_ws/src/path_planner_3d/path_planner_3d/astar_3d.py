#!/usr/bin/env python3
"""
A* 3D Algorithm Implementation
3D path planning using A* algorithm with 26-neighbor exploration.
"""

import numpy as np
import heapq
from typing import List, Tuple, Optional, Dict, Any, Set
import math


class AStar3D:
    """
    A* algorithm implementation for 3D path planning.
    
    This class implements the A* algorithm with 26-neighbor exploration
    for finding optimal paths in 3D voxel grids.
    """
    
    def __init__(self, voxel_size: float = 0.1, max_iterations: int = 10000):
        """
        Initialize A* 3D planner.
        
        Args:
            voxel_size: Size of each voxel in meters
            max_iterations: Maximum number of iterations for path planning
        """
        self.voxel_size = voxel_size
        self.max_iterations = max_iterations
        self.nodes_explored = 0
        
        # 26-neighbor offsets (3x3x3 - center)
        self.neighbor_offsets = self._generate_26_neighbors()
    
    def plan_path(self, start: Tuple[int, int, int], goal: Tuple[int, int, int], 
                  voxel_grid: np.ndarray, cost_function) -> Optional['PlanningResult']:
        """
        Plan path using A* algorithm.
        
        Args:
            start: Start position (x, y, z) in voxel coordinates
            goal: Goal position (x, y, z) in voxel coordinates
            voxel_grid: 3D voxel grid (0: empty, 1: ground, 2: obstacle, 255: unknown)
            cost_function: Cost function for evaluating path costs
            
        Returns:
            PlanningResult object with path and metadata
        """
        try:
            # Validate inputs
            if not self._is_valid_position(start, voxel_grid):
                return PlanningResult(success=False, path=[], nodes_explored=0)
            
            if not self._is_valid_position(goal, voxel_grid):
                return PlanningResult(success=False, path=[], nodes_explored=0)
            
            # Initialize A* data structures
            open_set = []  # Priority queue: (f_cost, position)
            open_set_nodes = set()  # O(1) membership check
            closed_set: Set[Tuple[int, int, int]] = set()
            came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
            
            # Cost tracking
            g_cost: Dict[Tuple[int, int, int], float] = {start: 0.0}
            f_cost: Dict[Tuple[int, int, int], float] = {start: self._heuristic(start, goal)}
            
            # Add start to open set
            heapq.heappush(open_set, (f_cost[start], start))
            open_set_nodes.add(start)
            
            iterations = 0
            self.nodes_explored = 0  # Reset counter
            
            while open_set and iterations < self.max_iterations:
                iterations += 1
                self.nodes_explored += 1  # Count explored nodes
                
                # Get node with lowest f_cost
                current_f, current = heapq.heappop(open_set)
                open_set_nodes.discard(current)  # Remove from set
                
                # Check if we reached the goal
                if current == goal:
                    path = self._reconstruct_path(came_from, current)
                    return PlanningResult(success=True, path=path, nodes_explored=self.nodes_explored)
                
                # Add current to closed set
                closed_set.add(current)
                
                # Explore neighbors
                for neighbor in self._get_neighbors(current, voxel_grid):
                    if neighbor in closed_set:
                        continue
                    
                    # Calculate tentative g_cost
                    tentative_g = g_cost[current] + self._get_edge_cost(current, neighbor, voxel_grid, cost_function)
                    
                    # Check if this path to neighbor is better
                    if neighbor not in g_cost or tentative_g < g_cost[neighbor]:
                        came_from[neighbor] = current
                        g_cost[neighbor] = tentative_g
                        f_cost[neighbor] = tentative_g + self._heuristic(neighbor, goal)
                        
                        # Add to open set if not already there (O(1) check)
                        if neighbor not in open_set_nodes:
                            heapq.heappush(open_set, (f_cost[neighbor], neighbor))
                            open_set_nodes.add(neighbor)
            
            return PlanningResult(success=False, path=[], nodes_explored=self.nodes_explored)
            
        except Exception as e:
            return PlanningResult(success=False, path=[], nodes_explored=0)
    
    def _generate_26_neighbors(self) -> List[Tuple[int, int, int]]:
        """Generate 26-neighbor offsets for 3D grid."""
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue  # Skip center
                    neighbors.append((dx, dy, dz))
        return neighbors
    
    def _get_neighbors(self, position: Tuple[int, int, int], voxel_grid: np.ndarray) -> List[Tuple[int, int, int]]:
        """
        Get valid neighbors for a given position.
        
        Args:
            position: Current position (x, y, z)
            voxel_grid: 3D voxel grid
            
        Returns:
            List of valid neighbor positions
        """
        neighbors = []
        x, y, z = position
        
        for dx, dy, dz in self.neighbor_offsets:
            neighbor = (x + dx, y + dy, z + dz)
            
            if self._is_valid_position(neighbor, voxel_grid):
                neighbors.append(neighbor)
        
        return neighbors
    
    def _is_valid_position(self, position: Tuple[int, int, int], voxel_grid: np.ndarray) -> bool:
        """
        Check if position is valid (within bounds and not obstacle).
        
        Args:
            position: Position to check (x, y, z)
            voxel_grid: 3D voxel grid
            
        Returns:
            True if position is valid
        """
        x, y, z = position
        
        # Check bounds
        if (x < 0 or x >= voxel_grid.shape[0] or
            y < 0 or y >= voxel_grid.shape[1] or
            z < 0 or z >= voxel_grid.shape[2]):
            return False
        
        # Check if not obstacle
        voxel_value = voxel_grid[x, y, z]
        if voxel_value == 2:  # Obstacle
            return False
        
        return True
    
    def _heuristic(self, pos1: Tuple[int, int, int], pos2: Tuple[int, int, int]) -> float:
        """
        Calculate heuristic cost (Euclidean distance).
        
        Args:
            pos1: First position (x, y, z)
            pos2: Second position (x, y, z)
            
        Returns:
            Heuristic cost
        """
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        dz = pos1[2] - pos2[2]
        
        return math.sqrt(dx*dx + dy*dy + dz*dz)
    
    def _get_edge_cost(self, from_pos: Tuple[int, int, int], to_pos: Tuple[int, int, int],
                      voxel_grid: np.ndarray, cost_function) -> float:
        """
        Calculate edge cost between two positions.
        
        Args:
            from_pos: From position (x, y, z)
            to_pos: To position (x, y, z)
            voxel_grid: 3D voxel grid
            cost_function: Cost function for evaluating costs
            
        Returns:
            Edge cost
        """
        # Euclidean distance
        distance = self._heuristic(from_pos, to_pos)
        return distance * self.voxel_size
    
    def _reconstruct_path(self, came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]],
                         current: Tuple[int, int, int]) -> List[Tuple[int, int, int]]:
        """
        Reconstruct path from came_from dictionary.
        
        Args:
            came_from: Dictionary mapping each position to its parent
            current: Current position
            
        Returns:
            List of positions representing the path
        """
        path = [current]
        
        while current in came_from:
            current = came_from[current]
            path.append(current)
        
        path.reverse()
        return path
    
    def get_logger(self):
        """Get logger instance."""
        import logging
        return logging.getLogger(__name__)


class PlanningResult:
    """Container for path planning results."""
    def __init__(self, success: bool, path: List[Tuple[int, int, int]], nodes_explored: int):
        self.success = success
        self.path = path
        self.nodes_explored = nodes_explored
