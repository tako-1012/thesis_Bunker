#!/usr/bin/env python3
"""
Terrain Analyzer Node
Processes 3D point cloud data from RTAB-Map and generates terrain information
including voxel grids, slope maps, and terrain statistics.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from visualization_msgs.msg import MarkerArray
from std_msgs.msg import Header
from typing import Optional, Dict, Any
import numpy as np
import yaml
import os

# Custom messages (will be defined later)
# from bunker_3d_nav.msg import VoxelGrid3D, TerrainInfo

try:
    from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
    from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
except ImportError:
    # Fallback for development
    VoxelGridProcessor = None
    SlopeCalculator = None


class TerrainAnalyzerNode(Node):
    """
    ROS2 node for terrain analysis from 3D point cloud data.
    
    This node subscribes to RTAB-Map point cloud data and publishes:
    - Voxel grid representation of terrain
    - Slope map (2D projection)
    - Terrain statistics
    - Visualization markers for Rviz
    """
    
    def __init__(self) -> None:
        super().__init__('terrain_analyzer')
        
        # Declare parameters
        self._declare_parameters()
        
        # Load configuration
        self._load_config()
        
        # Initialize components
        self.voxel_processor = VoxelGridProcessor(
            voxel_size=self.voxel_size,
            ground_normal_threshold=self.ground_normal_threshold
        )
        
        self.slope_calculator = SlopeCalculator(
            max_slope_angle=self.max_slope_angle,
            stability_threshold=self.stability_threshold
        )
        
        # Setup QoS profile
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.pointcloud_sub = self.create_subscription(
            PointCloud2,
            '/rtabmap/cloud_map',
            self.pointcloud_callback,
            qos_profile
        )
        
        self.robot_pose_sub = self.create_subscription(
            PoseStamped,
            '/robot_pose',
            self.robot_pose_callback,
            qos_profile
        )
        
        # Publishers
        # TODO: Uncomment when custom messages are defined
        # self.voxel_pub = self.create_publisher(
        #     VoxelGrid3D,
        #     '/terrain/voxel_grid',
        #     10
        # )
        
        self.slope_map_pub = self.create_publisher(
            OccupancyGrid,
            '/terrain/slope_map',
            10
        )
        
        # TODO: Uncomment when custom messages are defined
        # self.terrain_info_pub = self.create_publisher(
        #     TerrainInfo,
        #     '/terrain/terrain_info',
        #     10
        # )
        
        self.visualization_pub = self.create_publisher(
            MarkerArray,
            '/terrain/visualization',
            10
        )
        
        # State variables
        self.current_robot_pose: Optional[PoseStamped] = None
        self.last_pointcloud_time: Optional[float] = None
        
        self.get_logger().info('Terrain Analyzer Node initialized')
        self.get_logger().info(f'Voxel size: {self.voxel_size}m')
        self.get_logger().info(f'Ground normal threshold: {self.ground_normal_threshold}°')
        self.get_logger().info(f'Max slope angle: {self.max_slope_angle}°')
    
    def _declare_parameters(self) -> None:
        """Declare ROS2 parameters with default values."""
        self.declare_parameter('voxel_size', 0.1)
        self.declare_parameter('ground_normal_threshold', 80.0)
        self.declare_parameter('max_slope_angle', 30.0)
        self.declare_parameter('robot_width', 0.6)
        self.declare_parameter('robot_length', 0.8)
        self.declare_parameter('stability_threshold', 20.0)
        self.declare_parameter('config_file', 'terrain_params.yaml')
        self.declare_parameter('enable_visualization', True)
        self.declare_parameter('publish_frequency', 1.0)
    
    def _load_config(self) -> None:
        """Load parameters from configuration file."""
        # Get parameter values
        self.voxel_size = self.get_parameter('voxel_size').value
        self.ground_normal_threshold = self.get_parameter('ground_normal_threshold').value
        self.max_slope_angle = self.get_parameter('max_slope_angle').value
        self.robot_width = self.get_parameter('robot_width').value
        self.robot_length = self.get_parameter('robot_length').value
        self.stability_threshold = self.get_parameter('stability_threshold').value
        self.enable_visualization = self.get_parameter('enable_visualization').value
        self.publish_frequency = self.get_parameter('publish_frequency').value
        
        # Load additional config from file
        config_file = self.get_parameter('config_file').value
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), '..', 'config', config_file
            )
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    self._apply_config(config)
                self.get_logger().info(f'Loaded config from {config_path}')
            else:
                self.get_logger().warn(f'Config file not found: {config_path}')
        except Exception as e:
            self.get_logger().error(f'Failed to load config: {e}')
    
    def _apply_config(self, config: Dict[str, Any]) -> None:
        """Apply configuration values from YAML file."""
        if 'terrain_analyzer' in config:
            terrain_config = config['terrain_analyzer']
            
            if 'voxel_size' in terrain_config:
                self.voxel_size = terrain_config['voxel_size']
            if 'ground_normal_threshold' in terrain_config:
                self.ground_normal_threshold = terrain_config['ground_normal_threshold']
            if 'max_slope_angle' in terrain_config:
                self.max_slope_angle = terrain_config['max_slope_angle']
            if 'robot_dimensions' in terrain_config:
                robot_dims = terrain_config['robot_dimensions']
                if 'width' in robot_dims:
                    self.robot_width = robot_dims['width']
                if 'length' in robot_dims:
                    self.robot_length = robot_dims['length']
            if 'stability_threshold' in terrain_config:
                self.stability_threshold = terrain_config['stability_threshold']
    
    def pointcloud_callback(self, msg: PointCloud2) -> None:
        """
        Process incoming point cloud data from RTAB-Map.
        
        Args:
            msg: PointCloud2 message containing 3D point cloud data
        """
        try:
            self.get_logger().debug(f'Received point cloud with {msg.width * msg.height} points')
            
            # TODO: Implement point cloud processing
            # 1. Convert ROS PointCloud2 to numpy array
            # 2. Process with voxel grid processor
            # 3. Calculate slopes
            # 4. Generate terrain statistics
            # 5. Publish results
            
            # Placeholder implementation
            self._process_pointcloud_placeholder(msg)
            
            self.last_pointcloud_time = self.get_clock().now().nanoseconds / 1e9
            
        except Exception as e:
            self.get_logger().error(f'Error processing point cloud: {e}')
    
    def robot_pose_callback(self, msg: PoseStamped) -> None:
        """
        Update current robot pose.
        
        Args:
            msg: PoseStamped message containing robot position and orientation
        """
        self.current_robot_pose = msg
        self.get_logger().debug(f'Updated robot pose: {msg.pose.position}')
    
    def _process_pointcloud_placeholder(self, msg: PointCloud2) -> None:
        """
        Placeholder for point cloud processing.
        
        TODO: Implement actual processing:
        1. Convert PointCloud2 to numpy array
        2. Create voxel grid
        3. Classify voxels (ground, obstacle, empty)
        4. Calculate slopes
        5. Generate terrain statistics
        6. Publish results
        """
        # Placeholder: Create dummy voxel grid
        dummy_voxel_grid = self._create_dummy_voxel_grid()
        
        # Placeholder: Create dummy slope map
        dummy_slope_map = self._create_dummy_slope_map()
        
        # Publish dummy data
        self._publish_dummy_results(dummy_voxel_grid, dummy_slope_map)
        
        self.get_logger().debug('Processed point cloud (placeholder)')
    
    def _create_dummy_voxel_grid(self) -> Dict[str, Any]:
        """Create dummy voxel grid data for testing."""
        return {
            'resolution': self.voxel_size,
            'origin': [0.0, 0.0, 0.0],
            'size': [100, 100, 20],
            'data': np.random.randint(0, 3, (100, 100, 20)).flatten(),
            'slopes': np.random.uniform(0, 30, 10000)
        }
    
    def _create_dummy_slope_map(self) -> OccupancyGrid:
        """Create dummy slope map for testing."""
        slope_map = OccupancyGrid()
        slope_map.header = Header()
        slope_map.header.stamp = self.get_clock().now().to_msg()
        slope_map.header.frame_id = 'map'
        
        slope_map.info.resolution = self.voxel_size
        slope_map.info.width = 100
        slope_map.info.height = 100
        slope_map.info.origin.position.x = -50.0
        slope_map.info.origin.position.y = -50.0
        slope_map.info.origin.position.z = 0.0
        
        # Create dummy slope data (0-100, where 100 = max slope)
        slope_data = np.random.randint(0, 101, 10000)
        slope_map.data = slope_data.tolist()
        
        return slope_map
    
    def _publish_dummy_results(self, voxel_grid: Dict[str, Any], slope_map: OccupancyGrid) -> None:
        """Publish dummy results for testing."""
        # Publish slope map
        self.slope_map_pub.publish(slope_map)
        
        # TODO: Publish voxel grid when custom message is defined
        # TODO: Publish terrain info when custom message is defined
        
        # Publish visualization markers
        if self.enable_visualization:
            markers = self._create_visualization_markers(voxel_grid)
            self.visualization_pub.publish(markers)
    
    def _create_visualization_markers(self, voxel_grid: Dict[str, Any]) -> MarkerArray:
        """Create visualization markers for Rviz."""
        markers = MarkerArray()
        
        # TODO: Create actual visualization markers
        # - Ground voxels (green)
        # - Obstacle voxels (red)
        # - Slope indicators (arrows)
        # - Robot footprint
        
        return markers
    
    def get_terrain_statistics(self) -> Dict[str, float]:
        """
        Calculate terrain statistics.
        
        Returns:
            Dictionary containing terrain statistics
        """
        # TODO: Implement actual terrain statistics calculation
        return {
            'avg_slope': 15.0,
            'max_slope': 30.0,
            'traversable_ratio': 0.8,
            'total_voxels': 200000,
            'ground_voxels': 160000,
            'obstacle_voxels': 40000
        }


def main(args=None):
    """Main function to start the terrain analyzer node."""
    rclpy.init(args=args)
    
    try:
        node = TerrainAnalyzerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'Error in terrain analyzer node: {e}')
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
