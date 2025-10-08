#!/usr/bin/env python3
"""
Test cases for CostFunction
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from bunker_3d_nav.path_planner_3d.cost_function import CostFunction
except ImportError:
    # Fallback for development
    CostFunction = None


class TestCostFunction:
    """Test cases for CostFunction class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.weights = {
            'distance': 1.0,
            'slope': 3.0,
            'obstacle': 5.0,
            'stability': 4.0
        }
        
        self.safety_params = {
            'min_obstacle_distance': 0.5,
            'max_roll_angle': 20.0,
            'max_pitch_angle': 25.0
        }
        
        self.cost_function = CostFunction(self.weights, self.safety_params)
    
    def test_initialization(self):
        """Test CostFunction initialization"""
        weights = {
            'distance': 1.0,
            'slope': 3.0,
            'obstacle': 5.0,
            'stability': 4.0
        }
        
        safety_params = {
            'min_obstacle_distance': 0.5,
            'max_roll_angle': 20.0,
            'max_pitch_angle': 25.0
        }
        
        cost_function = CostFunction(weights, safety_params)
        
        assert cost_function.weights == weights
        assert cost_function.safety_params == safety_params
    
    def test_calculate_total_cost(self):
        """Test total cost calculation"""
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (1.0, 1.0, 0.1)
        
        terrain_data = {
            'voxel_grid': np.zeros((10, 10, 10), dtype=np.uint8),
            'slopes': np.array([10.0]),
            'metadata': {'resolution': 0.1}
        }
        
        total_cost = self.cost_function.calculate_total_cost(from_pos, to_pos, terrain_data)
        
        assert isinstance(total_cost, float)
        assert total_cost >= 0.0
    
    def test_calculate_distance_cost(self):
        """Test distance cost calculation"""
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (1.0, 1.0, 0.0)
        
        distance_cost = self.cost_function.calculate_distance_cost(from_pos, to_pos)
        
        expected_distance = np.sqrt(1.0**2 + 1.0**2 + 0.0**2)
        expected_cost = self.weights['distance'] * expected_distance
        
        assert abs(distance_cost - expected_cost) < 1e-6
    
    def test_calculate_slope_cost(self):
        """Test slope cost calculation"""
        position = (5.0, 5.0, 0.0)
        
        terrain_data = {
            'voxel_grid': np.zeros((10, 10, 10), dtype=np.uint8),
            'slopes': np.array([15.0]),
            'metadata': {'resolution': 0.1}
        }
        
        slope_cost = self.cost_function.calculate_slope_cost(position, terrain_data)
        
        assert isinstance(slope_cost, float)
        assert slope_cost >= 0.0
    
    def test_calculate_obstacle_cost(self):
        """Test obstacle cost calculation"""
        position = (5.0, 5.0, 0.0)
        
        terrain_data = {
            'voxel_grid': np.zeros((10, 10, 10), dtype=np.uint8),
            'obstacle_map': np.zeros((10, 10, 10), dtype=np.uint8),
            'metadata': {'resolution': 0.1}
        }
        
        obstacle_cost = self.cost_function.calculate_obstacle_cost(position, terrain_data)
        
        assert isinstance(obstacle_cost, float)
        assert obstacle_cost >= 0.0
    
    def test_calculate_stability_cost(self):
        """Test stability cost calculation"""
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (1.0, 1.0, 0.1)
        
        terrain_data = {
            'voxel_grid': np.zeros((10, 10, 10), dtype=np.uint8),
            'slopes': np.array([10.0]),
            'metadata': {'resolution': 0.1}
        }
        
        stability_cost = self.cost_function.calculate_stability_cost(from_pos, to_pos, terrain_data)
        
        assert isinstance(stability_cost, float)
        assert stability_cost >= 0.0
    
    def test_slope_cost_function(self):
        """Test slope cost function with different angles"""
        # Test small angle (should be low cost)
        cost_small = self.cost_function._slope_cost_function(5.0)
        assert cost_small == 1.0
        
        # Test medium angle
        cost_medium = self.cost_function._slope_cost_function(15.0)
        assert cost_medium == 2.0
        
        # Test large angle (should be high cost)
        cost_large = self.cost_function._slope_cost_function(25.0)
        assert cost_large == 5.0
        
        # Test very large angle (should be infinite)
        cost_very_large = self.cost_function._slope_cost_function(35.0)
        assert cost_very_large == float('inf')
    
    def test_obstacle_cost_function(self):
        """Test obstacle cost function with different distances"""
        # Test safe distance (should be low cost)
        cost_safe = self.cost_function._obstacle_cost_function(1.0)
        assert cost_safe == 1.0
        
        # Test close distance (should be high cost)
        cost_close = self.cost_function._obstacle_cost_function(0.3)
        assert cost_close == float('inf')
        
        # Test minimum safe distance
        cost_min_safe = self.cost_function._obstacle_cost_function(0.5)
        assert cost_min_safe == 2.0
    
    def test_stability_cost_function(self):
        """Test stability cost function with different angles"""
        # Test stable angles (should be low cost)
        cost_stable = self.cost_function._stability_cost_function(10.0, 10.0)
        assert cost_stable == 10.0
        
        # Test unstable angles (should be high cost)
        cost_unstable = self.cost_function._stability_cost_function(30.0, 30.0)
        assert cost_unstable == 300.0
        
        # Test critical angles (should be infinite)
        cost_critical = self.cost_function._stability_cost_function(50.0, 50.0)
        assert cost_critical == float('inf')
    
    def test_invalid_parameters(self):
        """Test initialization with invalid parameters"""
        # Test invalid weights
        invalid_weights = {
            'distance': -1.0,
            'slope': 3.0,
            'obstacle': 5.0,
            'stability': 4.0
        }
        
        with pytest.raises(ValueError):
            CostFunction(invalid_weights, self.safety_params)
        
        # Test invalid safety parameters
        invalid_safety = {
            'min_obstacle_distance': -0.5,
            'max_roll_angle': 20.0,
            'max_pitch_angle': 25.0
        }
        
        with pytest.raises(ValueError):
            CostFunction(self.weights, invalid_safety)
    
    def test_error_handling(self):
        """Test error handling"""
        # Test with None inputs
        with pytest.raises(AttributeError):
            self.cost_function.calculate_total_cost(None, None, None)
        
        # Test with invalid terrain data
        invalid_terrain = {
            'voxel_grid': None,
            'slopes': None,
            'metadata': None
        }
        
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (1.0, 1.0, 0.0)
        
        with pytest.raises(AttributeError):
            self.cost_function.calculate_total_cost(from_pos, to_pos, invalid_terrain)
    
    def test_edge_cases(self):
        """Test edge cases"""
        # Test with same start and end position
        same_pos = (0.0, 0.0, 0.0)
        
        terrain_data = {
            'voxel_grid': np.zeros((10, 10, 10), dtype=np.uint8),
            'slopes': np.array([0.0]),
            'metadata': {'resolution': 0.1}
        }
        
        total_cost = self.cost_function.calculate_total_cost(same_pos, same_pos, terrain_data)
        
        assert total_cost == 0.0
        
        # Test with very small distances
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (0.001, 0.001, 0.001)
        
        total_cost = self.cost_function.calculate_total_cost(from_pos, to_pos, terrain_data)
        
        assert total_cost >= 0.0
        assert total_cost < 1.0
    
    def test_performance(self):
        """Test performance with multiple calculations"""
        terrain_data = {
            'voxel_grid': np.zeros((100, 100, 100), dtype=np.uint8),
            'slopes': np.random.uniform(0, 30, 1000),
            'metadata': {'resolution': 0.1}
        }
        
        import time
        start_time = time.time()
        
        # Perform multiple cost calculations
        for i in range(100):
            from_pos = (float(i), float(i), 0.0)
            to_pos = (float(i + 1), float(i + 1), 0.1)
            
            cost = self.cost_function.calculate_total_cost(from_pos, to_pos, terrain_data)
            assert isinstance(cost, float)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert processing_time < 1.0  # Should complete in less than 1 second
    
    def test_cost_consistency(self):
        """Test cost calculation consistency"""
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (1.0, 1.0, 0.1)
        
        terrain_data = {
            'voxel_grid': np.zeros((10, 10, 10), dtype=np.uint8),
            'slopes': np.array([10.0]),
            'metadata': {'resolution': 0.1}
        }
        
        # Calculate cost multiple times
        costs = []
        for _ in range(10):
            cost = self.cost_function.calculate_total_cost(from_pos, to_pos, terrain_data)
            costs.append(cost)
        
        # All costs should be the same
        assert all(abs(cost - costs[0]) < 1e-6 for cost in costs)


if __name__ == '__main__':
    pytest.main([__file__])