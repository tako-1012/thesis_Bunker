#!/usr/bin/env python3
"""
Test cases for SlopeCalculator
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
except ImportError:
    # Fallback for development
    SlopeCalculator = None


class TestSlopeCalculator:
    """Test cases for SlopeCalculator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.calculator = SlopeCalculator(max_slope_angle=30.0, stability_threshold=20.0)
    
    def test_initialization(self):
        """Test SlopeCalculator initialization"""
        calculator = SlopeCalculator(max_slope_angle=30.0, stability_threshold=20.0)
        
        assert calculator.max_slope_angle == 30.0
        assert calculator.stability_threshold == 20.0
    
    def test_initialization_default_values(self):
        """Test SlopeCalculator initialization with default values"""
        calculator = SlopeCalculator()
        
        assert calculator.max_slope_angle == 30.0
        assert calculator.stability_threshold == 20.0
    
    def test_calculate_slopes_empty(self):
        """Test slope calculation with empty voxel grid"""
        voxel_grid = np.zeros((3, 3, 3), dtype=np.uint8)
        normals = np.zeros((3, 3, 3, 3))
        
        result = self.calculator.calculate_slopes(voxel_grid, normals)
        
        assert 'slopes' in result
        assert 'stability_map' in result
        assert 'traversability_map' in result
        assert 'statistics' in result
        
        assert len(result['slopes']) == 0
        assert result['statistics']['avg_slope'] == 0.0
        assert result['statistics']['max_slope'] == 0.0
    
    def test_calculate_slopes_valid(self):
        """Test slope calculation with valid data"""
        voxel_grid = np.zeros((3, 3, 3), dtype=np.uint8)
        voxel_grid[0, 0, 0] = 1  # Ground voxel
        
        normals = np.zeros((3, 3, 3, 3))
        normals[0, 0, 0] = [0.0, 0.0, 1.0]  # Vertical normal
        
        result = self.calculator.calculate_slopes(voxel_grid, normals)
        
        assert 'slopes' in result
        assert 'stability_map' in result
        assert 'traversability_map' in result
        assert 'statistics' in result
        
        assert len(result['slopes']) >= 0
        assert isinstance(result['statistics']['avg_slope'], float)
        assert isinstance(result['statistics']['max_slope'], float)
    
    def test_calculate_slope_angle(self):
        """Test individual slope angle calculation"""
        # Test vertical normal (0 degrees)
        normal_vertical = np.array([0.0, 0.0, 1.0])
        angle = self.calculator.calculate_slope_angle(normal_vertical)
        assert abs(angle) < 1e-6  # Should be close to 0
        
        # Test horizontal normal (90 degrees)
        normal_horizontal = np.array([1.0, 0.0, 0.0])
        angle = self.calculator.calculate_slope_angle(normal_horizontal)
        assert abs(angle - 90.0) < 1e-6  # Should be close to 90
        
        # Test 45-degree normal
        normal_45 = np.array([1.0, 0.0, 1.0])
        normal_45 = normal_45 / np.linalg.norm(normal_45)
        angle = self.calculator.calculate_slope_angle(normal_45)
        assert abs(angle - 45.0) < 1e-6  # Should be close to 45
    
    def test_calculate_robot_stability(self):
        """Test robot stability calculation"""
        robot_pose = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # x, y, z, roll, pitch, yaw
        terrain_slopes = np.array([10.0, 15.0, 20.0])
        
        result = self.calculator.calculate_robot_stability(robot_pose, terrain_slopes)
        
        assert 'roll_stability' in result
        assert 'pitch_stability' in result
        assert 'combined_stability' in result
        assert 'is_stable' in result
        
        assert isinstance(result['roll_stability'], float)
        assert isinstance(result['pitch_stability'], float)
        assert isinstance(result['combined_stability'], float)
        assert isinstance(result['is_stable'], bool)
    
    def test_calculate_traversability(self):
        """Test traversability calculation"""
        slopes = np.array([5.0, 15.0, 25.0, 35.0])
        
        result = self.calculator.calculate_traversability(slopes)
        
        assert len(result) == len(slopes)
        assert all(isinstance(x, bool) for x in result)
        
        # Slopes under threshold should be traversable
        assert result[0] == True   # 5 degrees
        assert result[1] == True   # 15 degrees
        
        # Slopes over threshold should not be traversable
        assert result[3] == False  # 35 degrees
    
    def test_calculate_statistics(self):
        """Test statistics calculation"""
        slopes = np.array([5.0, 10.0, 15.0, 20.0, 25.0])
        
        result = self.calculator.calculate_statistics(slopes)
        
        assert 'avg_slope' in result
        assert 'max_slope' in result
        assert 'min_slope' in result
        assert 'std_slope' in result
        assert 'traversable_ratio' in result
        
        assert result['avg_slope'] == 15.0
        assert result['max_slope'] == 25.0
        assert result['min_slope'] == 5.0
        assert result['traversable_ratio'] == 1.0  # All slopes under 30 degrees
    
    def test_invalid_parameters(self):
        """Test initialization with invalid parameters"""
        with pytest.raises(ValueError):
            SlopeCalculator(max_slope_angle=-10.0)
        
        with pytest.raises(ValueError):
            SlopeCalculator(stability_threshold=200.0)
    
    def test_error_handling(self):
        """Test error handling"""
        # Test with None input
        with pytest.raises(AttributeError):
            self.calculator.calculate_slopes(None, None)
        
        # Test with invalid array shapes
        voxel_grid = np.zeros((3, 3), dtype=np.uint8)  # Wrong shape
        normals = np.zeros((3, 3, 3, 3))
        
        with pytest.raises(ValueError):
            self.calculator.calculate_slopes(voxel_grid, normals)
    
    def test_edge_cases(self):
        """Test edge cases"""
        # Test with single voxel
        voxel_grid = np.zeros((1, 1, 1), dtype=np.uint8)
        voxel_grid[0, 0, 0] = 1
        
        normals = np.zeros((1, 1, 1, 3))
        normals[0, 0, 0] = [0.0, 0.0, 1.0]
        
        result = self.calculator.calculate_slopes(voxel_grid, normals)
        
        assert 'slopes' in result
        assert 'statistics' in result
        
        # Test with all zeros
        voxel_grid = np.zeros((3, 3, 3), dtype=np.uint8)
        normals = np.zeros((3, 3, 3, 3))
        
        result = self.calculator.calculate_slopes(voxel_grid, normals)
        
        assert result['statistics']['avg_slope'] == 0.0
        assert result['statistics']['max_slope'] == 0.0
    
    def test_performance(self):
        """Test performance with large data"""
        # Create large voxel grid
        voxel_grid = np.zeros((50, 50, 50), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        
        normals = np.random.rand(50, 50, 50, 3)
        normals[:, :, :, 2] = 1.0  # Mostly vertical normals
        
        import time
        start_time = time.time()
        
        result = self.calculator.calculate_slopes(voxel_grid, normals)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert processing_time < 1.0  # Should process in less than 1 second
        assert 'slopes' in result
        assert 'statistics' in result


if __name__ == '__main__':
    pytest.main([__file__])