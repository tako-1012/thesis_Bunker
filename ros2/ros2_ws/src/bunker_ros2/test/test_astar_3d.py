#!/usr/bin/env python3
"""
Test cases for AStar3D
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
except ImportError:
    # Fallback for development
    AStar3D = None


class TestAStar3D:
    """Test cases for AStar3D class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.planner = AStar3D(voxel_size=0.1, max_iterations=1000)
        self.cost_function = Mock()
    
    def test_initialization(self):
        """Test AStar3D initialization"""
        planner = AStar3D(voxel_size=0.1, max_iterations=1000)
        
        assert planner.voxel_size == 0.1
        assert planner.max_iterations == 1000
    
    def test_initialization_default_values(self):
        """Test AStar3D initialization with default values"""
        planner = AStar3D()
        
        assert planner.voxel_size == 0.1
        assert planner.max_iterations == 10000
    
    def test_plan_path_simple(self):
        """Test path planning with simple scenario"""
        # Create simple voxel grid (10x10x10)
        voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        
        start_pos = (0, 0, 0)
        goal_pos = (9, 9, 0)
        
        # Mock cost function
        self.cost_function.calculate_total_cost.return_value = 1.0
        
        result = self.planner.plan_path(start_pos, goal_pos, voxel_grid, self.cost_function)
        
        assert result is not None
        assert len(result) > 0
        assert result[0] == start_pos
        assert result[-1] == goal_pos
    
    def test_plan_path_no_path(self):
        """Test path planning when no path exists"""
        # Create voxel grid with obstacles blocking the path
        voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        voxel_grid[5, :, :] = 2  # Obstacle wall
        
        start_pos = (0, 0, 0)
        goal_pos = (9, 9, 0)
        
        # Mock cost function to return infinite cost for obstacles
        def mock_cost(from_pos, to_pos, terrain_data):
            if voxel_grid[to_pos[0], to_pos[1], to_pos[2]] == 2:
                return float('inf')
            return 1.0
        
        self.cost_function.calculate_total_cost.side_effect = mock_cost
        
        result = self.planner.plan_path(start_pos, goal_pos, voxel_grid, self.cost_function)
        
        assert result is None
    
    def test_get_neighbors(self):
        """Test neighbor calculation"""
        voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
        position = (5, 5, 5)
        
        neighbors = self.planner._get_neighbors(position, voxel_grid)
        
        assert len(neighbors) <= 26  # Maximum 26 neighbors in 3D
        assert all(isinstance(n, tuple) and len(n) == 3 for n in neighbors)
        
        # Check that all neighbors are within bounds
        for neighbor in neighbors:
            x, y, z = neighbor
            assert 0 <= x < voxel_grid.shape[0]
            assert 0 <= y < voxel_grid.shape[1]
            assert 0 <= z < voxel_grid.shape[2]
    
    def test_heuristic(self):
        """Test heuristic function"""
        pos1 = (0, 0, 0)
        pos2 = (3, 4, 0)
        
        heuristic_value = self.planner._heuristic(pos1, pos2)
        
        expected_distance = np.sqrt(3**2 + 4**2 + 0**2)
        assert abs(heuristic_value - expected_distance) < 1e-6
    
    def test_is_valid_position(self):
        """Test position validation"""
        voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
        
        # Valid positions
        assert self.planner._is_valid_position((0, 0, 0), voxel_grid) == True
        assert self.planner._is_valid_position((9, 9, 9), voxel_grid) == True
        
        # Invalid positions (out of bounds)
        assert self.planner._is_valid_position((-1, 0, 0), voxel_grid) == False
        assert self.planner._is_valid_position((10, 0, 0), voxel_grid) == False
        assert self.planner._is_valid_position((0, -1, 0), voxel_grid) == False
        assert self.planner._is_valid_position((0, 10, 0), voxel_grid) == False
        assert self.planner._is_valid_position((0, 0, -1), voxel_grid) == False
        assert self.planner._is_valid_position((0, 0, 10), voxel_grid) == False
    
    def test_reconstruct_path(self):
        """Test path reconstruction"""
        came_from = {
            (1, 1, 1): (0, 0, 0),
            (2, 2, 2): (1, 1, 1),
            (3, 3, 3): (2, 2, 2)
        }
        
        start_pos = (0, 0, 0)
        goal_pos = (3, 3, 3)
        
        path = self.planner._reconstruct_path(came_from, start_pos, goal_pos)
        
        expected_path = [(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)]
        assert path == expected_path
    
    def test_invalid_parameters(self):
        """Test initialization with invalid parameters"""
        with pytest.raises(ValueError):
            AStar3D(voxel_size=-0.1)
        
        with pytest.raises(ValueError):
            AStar3D(max_iterations=-100)
    
    def test_error_handling(self):
        """Test error handling"""
        # Test with None inputs
        with pytest.raises(AttributeError):
            self.planner.plan_path(None, None, None, None)
        
        # Test with invalid voxel grid
        invalid_grid = np.zeros((3, 3), dtype=np.uint8)  # Wrong shape
        start_pos = (0, 0, 0)
        goal_pos = (2, 2, 0)
        
        with pytest.raises(ValueError):
            self.planner.plan_path(start_pos, goal_pos, invalid_grid, self.cost_function)
    
    def test_performance(self):
        """Test performance with large grid"""
        # Create large voxel grid
        voxel_grid = np.zeros((50, 50, 50), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        
        start_pos = (0, 0, 0)
        goal_pos = (49, 49, 0)
        
        # Mock cost function
        self.cost_function.calculate_total_cost.return_value = 1.0
        
        import time
        start_time = time.time()
        
        result = self.planner.plan_path(start_pos, goal_pos, voxel_grid, self.cost_function)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert processing_time < 5.0  # Should complete in less than 5 seconds
        assert result is not None
        assert len(result) > 0
    
    def test_edge_cases(self):
        """Test edge cases"""
        voxel_grid = np.zeros((3, 3, 3), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        
        # Same start and goal
        start_pos = (1, 1, 0)
        goal_pos = (1, 1, 0)
        
        self.cost_function.calculate_total_cost.return_value = 1.0
        
        result = self.planner.plan_path(start_pos, goal_pos, voxel_grid, self.cost_function)
        
        assert result is not None
        assert len(result) == 1
        assert result[0] == start_pos
    
    def test_obstacle_avoidance(self):
        """Test obstacle avoidance"""
        voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        voxel_grid[5, 5, :] = 2  # Obstacle column
        
        start_pos = (0, 0, 0)
        goal_pos = (9, 9, 0)
        
        # Mock cost function
        def mock_cost(from_pos, to_pos, terrain_data):
            if voxel_grid[to_pos[0], to_pos[1], to_pos[2]] == 2:
                return float('inf')
            return 1.0
        
        self.cost_function.calculate_total_cost.side_effect = mock_cost
        
        result = self.planner.plan_path(start_pos, goal_pos, voxel_grid, self.cost_function)
        
        assert result is not None
        assert len(result) > 0
        
        # Check that path avoids obstacles
        for pos in result:
            x, y, z = pos
            assert voxel_grid[x, y, z] != 2


if __name__ == '__main__':
    pytest.main([__file__])