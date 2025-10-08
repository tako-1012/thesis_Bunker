#!/usr/bin/env python3
"""
Test cases for VoxelGridProcessor
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
except ImportError:
    # Fallback for development
    VoxelGridProcessor = None


class TestVoxelGridProcessor:
    """Test cases for VoxelGridProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = VoxelGridProcessor(voxel_size=0.1, ground_normal_threshold=80.0)
    
    def test_initialization(self):
        """Test VoxelGridProcessor initialization"""
        processor = VoxelGridProcessor(voxel_size=0.1, ground_normal_threshold=80.0)
        
        assert processor.voxel_size == 0.1
        assert processor.ground_normal_threshold == 80.0
        assert processor.max_slope_angle == 30.0
        assert processor.stability_threshold == 20.0
    
    def test_initialization_default_values(self):
        """Test VoxelGridProcessor initialization with default values"""
        processor = VoxelGridProcessor()
        
        assert processor.voxel_size == 0.1
        assert processor.ground_normal_threshold == 80.0
        assert processor.max_slope_angle == 30.0
        assert processor.stability_threshold == 20.0
    
    def test_process_pointcloud_empty(self):
        """Test processing empty point cloud"""
        # Create mock empty point cloud message
        mock_msg = Mock()
        mock_msg.data = b''
        mock_msg.width = 0
        mock_msg.height = 1
        mock_msg.point_step = 16
        mock_msg.row_step = 0
        mock_msg.fields = []
        
        result = self.processor.process_pointcloud(mock_msg)
        
        assert result['metadata']['point_count'] == 0
        assert 'voxel_grid' in result
        assert 'classified_voxels' in result
        assert 'normals' in result
    
    def test_process_pointcloud_valid(self):
        """Test processing valid point cloud"""
        # Create mock point cloud with sample data
        mock_msg = Mock()
        mock_msg.data = b'\x00' * 48  # 3 points * 16 bytes
        mock_msg.width = 3
        mock_msg.height = 1
        mock_msg.point_step = 16
        mock_msg.row_step = 48
        mock_msg.fields = [
            Mock(name='x', offset=0, datatype=7, count=1),
            Mock(name='y', offset=4, datatype=7, count=1),
            Mock(name='z', offset=8, datatype=7, count=1),
            Mock(name='intensity', offset=12, datatype=7, count=1)
        ]
        
        with patch.object(self.processor, '_ros_to_numpy') as mock_convert:
            mock_convert.return_value = np.array([
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0]
            ])
            
            result = self.processor.process_pointcloud(mock_msg)
            
            assert result['metadata']['point_count'] == 3
            assert 'voxel_grid' in result
            assert 'classified_voxels' in result
            assert 'normals' in result
    
    def test_ros_to_numpy_conversion(self):
        """Test ROS PointCloud2 to numpy conversion"""
        # Create mock point cloud message
        mock_msg = Mock()
        mock_msg.data = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        mock_msg.width = 1
        mock_msg.height = 1
        mock_msg.point_step = 16
        mock_msg.row_step = 16
        mock_msg.fields = [
            Mock(name='x', offset=0, datatype=7, count=1),
            Mock(name='y', offset=4, datatype=7, count=1),
            Mock(name='z', offset=8, datatype=7, count=1),
            Mock(name='intensity', offset=12, datatype=7, count=1)
        ]
        
        result = self.processor._ros_to_numpy(mock_msg)
        
        assert isinstance(result, np.ndarray)
        assert result.shape[1] == 3  # x, y, z coordinates
    
    def test_numpy_to_open3d_conversion(self):
        """Test numpy array to Open3D point cloud conversion"""
        points = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0]
        ])
        
        result = self.processor._numpy_to_open3d(points)
        
        assert hasattr(result, 'points')
        assert len(result.points) == 3
    
    def test_create_voxel_grid(self):
        """Test voxel grid creation"""
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.1, 0.1, 0.1],
            [0.2, 0.2, 0.2]
        ])
        
        with patch('open3d.geometry.PointCloud') as mock_pcd:
            mock_pcd_instance = Mock()
            mock_pcd_instance.points = Mock()
            mock_pcd_instance.points.__len__ = Mock(return_value=3)
            mock_pcd.return_value = mock_pcd_instance
            
            result = self.processor.create_voxel_grid(points)
            
            assert 'voxel_grid' in result
            assert 'classified_voxels' in result
            assert 'normals' in result
    
    def test_classify_voxels(self):
        """Test voxel classification"""
        voxel_grid = np.zeros((3, 3, 3), dtype=np.uint8)
        voxel_grid[0, 0, 0] = 1  # Ground voxel
        voxel_grid[1, 1, 1] = 2  # Obstacle voxel
        
        normals = np.random.rand(3, 3, 3, 3)
        
        result = self.processor.classify_voxels(voxel_grid, normals)
        
        assert isinstance(result, np.ndarray)
        assert result.shape == voxel_grid.shape
    
    def test_calculate_normals(self):
        """Test normal vector calculation"""
        voxel_grid = np.zeros((3, 3, 3), dtype=np.uint8)
        voxel_grid[0, 0, 0] = 1
        voxel_grid[1, 1, 1] = 1
        
        with patch('open3d.geometry.PointCloud') as mock_pcd:
            mock_pcd_instance = Mock()
            mock_pcd_instance.normals = Mock()
            mock_pcd_instance.normals.__len__ = Mock(return_value=2)
            mock_pcd.return_value = mock_pcd_instance
            
            result = self.processor.calculate_normals(voxel_grid)
            
            assert isinstance(result, np.ndarray)
    
    def test_invalid_parameters(self):
        """Test initialization with invalid parameters"""
        with pytest.raises(ValueError):
            VoxelGridProcessor(voxel_size=-0.1)
        
        with pytest.raises(ValueError):
            VoxelGridProcessor(ground_normal_threshold=200.0)
    
    def test_error_handling(self):
        """Test error handling in process_pointcloud"""
        # Test with None input
        with pytest.raises(AttributeError):
            self.processor.process_pointcloud(None)
        
        # Test with invalid message structure
        mock_msg = Mock()
        mock_msg.data = None
        
        with pytest.raises(AttributeError):
            self.processor.process_pointcloud(mock_msg)
    
    def test_performance_metrics(self):
        """Test performance metrics calculation"""
        voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
        voxel_grid[:, :, 0] = 1  # Ground layer
        voxel_grid[5, 5, :] = 2  # Obstacle column
        
        result = self.processor.calculate_performance_metrics(voxel_grid)
        
        assert 'total_voxels' in result
        assert 'ground_voxels' in result
        assert 'obstacle_voxels' in result
        assert 'empty_voxels' in result
        assert 'unknown_voxels' in result
        
        assert result['total_voxels'] == 1000
        assert result['ground_voxels'] == 100
        assert result['obstacle_voxels'] == 10


if __name__ == '__main__':
    pytest.main([__file__])