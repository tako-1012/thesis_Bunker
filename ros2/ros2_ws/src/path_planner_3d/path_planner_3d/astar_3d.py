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
        
        # 26-neighbor offsets (3x3x3 - center)
        self.neighbor_offsets = self._generate_26_neighbors()
        
        self.get_logger().info(f'AStar3D initialized with voxel_size={voxel_size}m, max_iterations={max_iterations}')
    
    def plan_path(self, start: Tuple[int, int, int], goal: Tuple[int, int, int], 
                  voxel_grid: np.ndarray, cost_function) -> Optional[List[Tuple[int, int, int]]]:
        """
        Plan path using A* algorithm.
        
        Args:
            start: Start position (x, y, z) in voxel coordinates
            goal: Goal position (x, y, z) in voxel coordinates
            voxel_grid: 3D voxel grid (0: empty, 1: ground, 2: obstacle, 255: unknown)
            cost_function: Cost function for evaluating path costs
            
        Returns:
            List of voxel coordinates representing the path, or None if no path found
        """
        try:
            self.get_logger().info(f'Planning path from {start} to {goal}')
            
            # Validate inputs
            if not self._is_valid_position(start, voxel_grid):
                self.get_logger().error(f'Invalid start position: {start}')
                return None
            
            if not self._is_valid_position(goal, voxel_grid):
                self.get_logger().error(f'Invalid goal position: {goal}')
                return None
            
            # Initialize A* data structures
            open_set = []  # Priority queue: (f_cost, position)
            closed_set: Set[Tuple[int, int, int]] = set()
            came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
            
            # Cost tracking
            g_cost: Dict[Tuple[int, int, int], float] = {start: 0.0}
            f_cost: Dict[Tuple[int, int, int], float] = {start: self._heuristic(start, goal)}
            
            # Add start to open set
            heapq.heappush(open_set, (f_cost[start], start))
            
            iterations = 0
            
            while open_set and iterations < self.max_iterations:
                iterations += 1
                
                # Get node with lowest f_cost
                current_f, current = heapq.heappop(open_set)
                
                # Check if we reached the goal
                if current == goal:
                    self.get_logger().info(f'Path found in {iterations} iterations')
                    return self._reconstruct_path(came_from, current)
                
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
                        
                        # Add to open set if not already there
                        if neighbor not in [pos for _, pos in open_set]:
                            heapq.heappush(open_set, (f_cost[neighbor], neighbor))
            
            self.get_logger().warn(f'Path planning failed after {iterations} iterations')
            return None
            
        except Exception as e:
            self.get_logger().error(f'Error in A* path planning: {e}')
            return None
    
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
        # TODO: Implement proper edge cost calculation
        # This is a placeholder implementation
        
        # Basic distance cost
        distance = self._heuristic(from_pos, to_pos)
        
        # Get voxel values
        from_voxel = voxel_grid[from_pos]
        to_voxel = voxel_grid[to_pos]
        
        # Calculate additional costs based on voxel types
        base_cost = distance * self.voxel_size
        
        # Add cost for different voxel types
        if to_voxel == 1:  # Ground
            base_cost *= 1.0
        elif to_voxel == 0:  # Empty
            base_cost *= 1.2
        elif to_voxel == 255:  # Unknown
            base_cost *= 2.0
        
        return base_cost
    
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
        # TODO: Implement proper logging
        import logging
        return logging.getLogger(__name__)
