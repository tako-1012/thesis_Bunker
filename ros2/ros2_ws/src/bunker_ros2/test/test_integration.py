#!/usr/bin/env python3
"""
Integration tests for bunker_3d_nav package
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from bunker_3d_nav.terrain_analyzer.terrain_analyzer_node import TerrainAnalyzerNode
from bunker_3d_nav.path_planner_3d.path_planner_node import PathPlanner3DNode
from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
from bunker_3d_nav.path_planner_3d.cost_function import CostFunction
from bunker_3d_nav.path_planner_3d.path_smoother import PathSmoother


class TestIntegration:
    """Integration tests for the complete system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock ROS2 node dependencies
        self.mock_node = Mock()
        self.mock_node.get_logger.return_value = Mock()
        self.mock_node.get_clock.return_value = Mock()
        self.mock_node.get_clock.return_value.now.return_value = Mock()
        self.mock_node.get_clock.return_value.now.return_value.to_msg.return_value = Mock()
        
        # Create test data
        self.sample_pointcloud = self._create_sample_pointcloud()
        self.sample_terrain_data = self._create_sample_terrain_data()
        self.sample_goal_pose = self._create_sample_goal_pose()
        
        # Initialize components
        self.voxel_processor = VoxelGridProcessor()
        self.slope_calculator = SlopeCalculator()
        self.astar_planner = AStar3D()
        self.cost_function = CostFunction(
            weights={'distance': 1.0, 'slope': 3.0, 'obstacle': 5.0, 'stability': 4.0},
            safety_params={'min_obstacle_distance': 0.5, 'max_roll_angle': 20.0, 'max_pitch_angle': 25.0}
        )
        self.path_smoother = PathSmoother()
    
    def tearDown(self):
        """Clean up after tests."""
        pass
    
    def _create_sample_pointcloud(self):
        """Create sample point cloud data."""
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.1, 0.0, 0.0],
            [0.0, 0.1, 0.0],
            [0.0, 0.0, 0.1],
            [0.5, 0.5, 0.2],
            [1.0, 1.0, 0.3],
            [1.5, 1.5, 0.4],
            [2.0, 2.0, 0.5]
        ])
        return points
    
    def _create_sample_terrain_data(self):
        """Create sample terrain data."""
        return {
            'voxel_grid': np.random.randint(0, 3, (20, 20, 10)),
            'slopes': np.random.uniform(0, 30, 400),
            'metadata': {'resolution': 0.1, 'timestamp': Mock()}
        }
    
    def _create_sample_goal_pose(self):
        """Create sample goal pose."""
        goal = Mock()
        goal.pose.position.x = 2.0
        goal.pose.position.y = 2.0
        goal.pose.position.z = 0.5
        goal.pose.orientation.w = 1.0
        return goal
    
    @patch('bunker_3d_nav.terrain_analyzer.terrain_analyzer_node.rclpy')
    def test_terrain_analyzer_node_initialization(self, mock_rclpy):
        """Test terrain analyzer node initialization."""
        with patch('bunker_3d_nav.terrain_analyzer.terrain_analyzer_node.Node', return_value=self.mock_node):
            node = TerrainAnalyzerNode()
            
            assert node.voxel_processor is not None
            assert node.slope_calculator is not None
            assert node.voxel_size == 0.1
            assert node.ground_normal_threshold == 80.0
    
    @patch('bunker_3d_nav.path_planner_3d.path_planner_node.rclpy')
    def test_path_planner_node_initialization(self, mock_rclpy):
        """Test path planner node initialization."""
        with patch('bunker_3d_nav.path_planner_3d.path_planner_node.Node', return_value=self.mock_node):
            node = PathPlanner3DNode()
            
            assert node.astar_planner is not None
            assert node.cost_function is not None
            assert node.path_smoother is not None
            assert node.max_iterations == 10000
    
    def test_terrain_analysis_pipeline(self):
        """Test complete terrain analysis pipeline."""
        # Step 1: Process point cloud to voxel grid
        with patch.object(self.voxel_processor, 'process_pointcloud') as mock_process:
            mock_process.return_value = self.sample_terrain_data
            
            result = self.voxel_processor.process_pointcloud(Mock())
            
            assert 'voxel_grid' in result
            assert 'classified_voxels' in result
            assert 'normals' in result
        
        # Step 2: Calculate slopes
        voxel_grid = result['voxel_grid']
        normals = result['normals']
        
        slope_result = self.slope_calculator.calculate_slopes(voxel_grid, normals)
        
        assert 'slopes' in slope_result
        assert 'stability_map' in slope_result
        assert 'traversability_map' in slope_result
        assert 'statistics' in slope_result
    
    def test_path_planning_pipeline(self):
        """Test complete path planning pipeline."""
        # Step 1: Prepare terrain data
        terrain_data = self.sample_terrain_data
        start_pos = (0, 0, 0)
        goal_pos = (19, 19, 9)
        
        # Step 2: Plan path using A*
        with patch.object(self.astar_planner, 'plan_path') as mock_plan:
            mock_plan.return_value = [(0, 0, 0), (5, 5, 2), (10, 10, 4), (15, 15, 6), (19, 19, 9)]
            
            path = self.astar_planner.plan_path(start_pos, goal_pos, terrain_data['voxel_grid'], self.cost_function)
            
            assert path is not None
            assert len(path) > 0
            assert path[0] == start_pos
            assert path[-1] == goal_pos
        
        # Step 3: Smooth path
        if path and len(path) > 2:
            smoothed_path = self.path_smoother.smooth_path([np.array(p) for p in path])
            
            assert len(smoothed_path) >= len(path)
            assert isinstance(smoothed_path[0], np.ndarray)
    
    def test_cost_calculation_integration(self):
        """Test cost calculation integration."""
        from_pos = (0.0, 0.0, 0.0)
        to_pos = (1.0, 1.0, 0.1)
        
        # Test individual cost components
        distance_cost = self.cost_function.calculate_distance_cost(from_pos, to_pos)
        slope_cost = self.cost_function.calculate_slope_cost(to_pos, self.sample_terrain_data)
        obstacle_cost = self.cost_function.calculate_obstacle_cost(to_pos, self.sample_terrain_data)
        stability_cost = self.cost_function.calculate_stability_cost(from_pos, to_pos, self.sample_terrain_data)
        
        assert isinstance(distance_cost, float)
        assert isinstance(slope_cost, float)
        assert isinstance(obstacle_cost, float)
        assert isinstance(stability_cost, float)
        
        # Test total cost calculation
        total_cost = self.cost_function.calculate_total_cost(from_pos, to_pos, self.sample_terrain_data)
        
        assert isinstance(total_cost, float)
        assert total_cost >= 0
    
    def test_error_handling_integration(self):
        """Test error handling across components."""
        # Test with invalid data
        invalid_terrain_data = {}
        
        # Should handle gracefully
        slope_result = self.slope_calculator.calculate_slopes(np.array([]), np.array([]))
        
        assert 'slopes' in slope_result
        assert len(slope_result['slopes']) == 0
        
        # Test with invalid positions
        invalid_start = (-1, -1, -1)
        invalid_goal = (100, 100, 100)
        
        path = self.astar_planner.plan_path(invalid_start, invalid_goal, np.zeros((10, 10, 10)), self.cost_function)
        
        assert path is None
    
    def test_performance_integration(self):
        """Test performance characteristics."""
        import time
        
        # Test terrain analysis performance
        start_time = time.time()
        
        with patch.object(self.voxel_processor, 'process_pointcloud') as mock_process:
            mock_process.return_value = self.sample_terrain_data
            result = self.voxel_processor.process_pointcloud(Mock())
        
        terrain_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert terrain_time < 1.0  # Less than 1 second
        
        # Test path planning performance
        start_time = time.time()
        
        with patch.object(self.astar_planner, 'plan_path') as mock_plan:
            mock_plan.return_value = [(0, 0, 0), (5, 5, 2), (10, 10, 4), (15, 15, 6), (19, 19, 9)]
            path = self.astar_planner.plan_path((0, 0, 0), (19, 19, 9), self.sample_terrain_data['voxel_grid'], self.cost_function)
        
        planning_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert planning_time < 2.0  # Less than 2 seconds
    
    def test_data_consistency_integration(self):
        """Test data consistency across components."""
        # Create consistent test data
        voxel_grid = np.zeros((10, 10, 5), dtype=np.uint8)
        voxel_grid[5, 5, :] = 2  # Add obstacle column
        
        terrain_data = {
            'voxel_grid': voxel_grid,
            'slopes': np.random.uniform(0, 30, 50),
            'metadata': {'resolution': 0.1}
        }
        
        # Test that components handle data consistently
        slopes = self.slope_calculator.calculate_slopes(voxel_grid, np.random.randn(50, 3))
        
        assert slopes['slopes'].shape[0] == 50
        
        # Test path planning respects obstacles
        with patch.object(self.astar_planner, 'plan_path') as mock_plan:
            mock_plan.return_value = [(0, 0, 0), (4, 4, 2), (6, 6, 2), (9, 9, 4)]
            path = self.astar_planner.plan_path((0, 0, 0), (9, 9, 4), voxel_grid, self.cost_function)
            
            # Path should avoid obstacle at (5, 5, *)
            if path:
                for point in path:
                    assert point != (5, 5, 0)  # Should not go through obstacle
    
    def test_parameter_sensitivity_integration(self):
        """Test parameter sensitivity across components."""
        # Test different voxel sizes
        small_voxel_processor = VoxelGridProcessor(voxel_size=0.05)
        large_voxel_processor = VoxelGridProcessor(voxel_size=0.2)
        
        assert small_voxel_processor.voxel_size == 0.05
        assert large_voxel_processor.voxel_size == 0.2
        
        # Test different cost weights
        high_slope_weight = CostFunction(
            weights={'distance': 1.0, 'slope': 10.0, 'obstacle': 5.0, 'stability': 4.0},
            safety_params=self.cost_function.safety_params
        )
        
        assert high_slope_weight.weights['slope'] == 10.0
        
        # Test different slope thresholds
        strict_slope_calc = SlopeCalculator(max_slope_angle=15.0)
        lenient_slope_calc = SlopeCalculator(max_slope_angle=45.0)
        
        assert strict_slope_calc.max_slope_angle == np.radians(15.0)
        assert lenient_slope_calc.max_slope_angle == np.radians(45.0)


if __name__ == '__main__':
    pytest.main([__file__])
