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
from geometry_msgs.msg import PoseStamped, Point, Vector3
from nav_msgs.msg import OccupancyGrid
from visualization_msgs.msg import MarkerArray, Marker
from std_msgs.msg import Header
from typing import Optional, Dict, Any
import numpy as np
import yaml
import os
import time
import open3d as o3d
from sensor_msgs_py import point_cloud2

# Custom messages
from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D

try:
    from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
    from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
    from bunker_3d_nav.terrain_analyzer.terrain_visualizer import TerrainVisualizer
except ImportError:
    # Fallback for development
    VoxelGridProcessor = None
    SlopeCalculator = None
    TerrainVisualizer = None


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
        self._initialize_processors()
        
        # Setup QoS profile
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.pointcloud_sub = self.create_subscription(
            PointCloud2,
            '/bunker/pointcloud',
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
        self.terrain_info_pub = self.create_publisher(
            TerrainInfo,
            '/bunker/terrain_info',
            10
        )
        
        self.voxel_grid_pub = self.create_publisher(
            VoxelGrid3D,
            '/bunker/voxel_grid',
            10
        )
        
        self.slope_map_pub = self.create_publisher(
            OccupancyGrid,
            '/terrain/slope_map',
            10
        )
        
        self.visualization_pub = self.create_publisher(
            MarkerArray,
            '/terrain/visualization',
            10
        )
        
        # State variables
        self.current_robot_pose: Optional[PoseStamped] = None
        self.last_pointcloud_time: Optional[float] = None
        self.processing_stats: Dict[str, Any] = {
            'total_processed': 0,
            'total_time': 0.0,
            'avg_processing_time': 0.0,
            'last_processing_time': 0.0
        }
        
        self.get_logger().info('Terrain Analyzer Node initialized')
        self.get_logger().info(f'Voxel size: {self.voxel_size}m')
        self.get_logger().info(f'Robot dimensions: {self.robot_width}m × {self.robot_length}m')
        self.get_logger().info(f'Max safe slope: {self.max_safe_slope}°')
    
    def _declare_parameters(self) -> None:
        """Declare ROS2 parameters with default values."""
        self.declare_parameter('voxel_size', 0.1)
        self.declare_parameter('robot_width', 0.6)
        self.declare_parameter('robot_length', 0.8)
        self.declare_parameter('max_safe_slope', 25.0)
        self.declare_parameter('config_file', 'terrain_params.yaml')
        self.declare_parameter('enable_visualization', True)
        self.declare_parameter('publish_frequency', 1.0)
    
    def _load_config(self) -> None:
        """Load parameters from configuration file."""
        # Get parameter values
        self.voxel_size = self.get_parameter('voxel_size').value
        self.robot_width = self.get_parameter('robot_width').value
        self.robot_length = self.get_parameter('robot_length').value
        self.max_safe_slope = self.get_parameter('max_safe_slope').value
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
            if 'robot_dimensions' in terrain_config:
                robot_dims = terrain_config['robot_dimensions']
                if 'width' in robot_dims:
                    self.robot_width = robot_dims['width']
                if 'length' in robot_dims:
                    self.robot_length = robot_dims['length']
            if 'max_safe_slope' in terrain_config:
                self.max_safe_slope = terrain_config['max_safe_slope']
    
    def _initialize_processors(self) -> None:
        """Initialize terrain analysis processors."""
        if VoxelGridProcessor is not None:
            self.voxel_processor = VoxelGridProcessor(
                voxel_size=self.voxel_size,
                logger=self.get_logger()
            )
        else:
            self.voxel_processor = None
            self.get_logger().error('VoxelGridProcessor not available')
        
        if SlopeCalculator is not None:
            self.slope_calculator = SlopeCalculator(
                robot_width=self.robot_width,
                robot_length=self.robot_length,
                max_safe_slope=self.max_safe_slope,
                logger=self.get_logger()
            )
        else:
            self.slope_calculator = None
            self.get_logger().error('SlopeCalculator not available')
        
        if TerrainVisualizer is not None:
            self.terrain_visualizer = TerrainVisualizer(self)
        else:
            self.terrain_visualizer = None
            self.get_logger().error('TerrainVisualizer not available')
    
    def pointcloud_callback(self, msg: PointCloud2) -> None:
        """
        Process incoming point cloud data from RTAB-Map.
        
        Args:
            msg: PointCloud2 message containing 3D point cloud data
        """
        start_time = time.time()
        
        try:
            self.get_logger().debug(f'Received point cloud with {msg.width * msg.height} points')
            
            if self.voxel_processor is None or self.slope_calculator is None:
                self.get_logger().error('Processors not available')
                return
            
            # 1. PointCloud2 → Open3D変換
            pcd = self._convert_pointcloud2_to_open3d(msg)
            
            if len(pcd.points) == 0:
                self.get_logger().warn('Empty point cloud received')
                return
            
            # 2. VoxelGridProcessor.process_pointcloud()
            voxel_result = self.voxel_processor.process_pointcloud(pcd)
            
            # 3. SlopeCalculator.analyze_terrain()
            classification = self.voxel_processor.classify_voxels(pcd, voxel_result['voxel_grid'])
            terrain_analysis = self.slope_calculator.analyze_terrain(pcd, classification['ground_indices'])
            
            # 4. TerrainInfo メッセージ作成・パブリッシュ
            self._publish_terrain_info(terrain_analysis, classification, voxel_result)
            
            # 5. VoxelGrid3D メッセージ作成・パブリッシュ
            self._publish_voxel_grid(voxel_result, classification, terrain_analysis)
            
            # 6. 高度な可視化
            if self.enable_visualization and self.terrain_visualizer is not None:
                self.terrain_visualizer.visualize_terrain(voxel_result, classification, terrain_analysis)
            
            # 処理時間の記録
            processing_time = time.time() - start_time
            self._update_processing_stats(processing_time)
            
            self.last_pointcloud_time = self.get_clock().now().nanoseconds / 1e9
            
            self.get_logger().debug(f'Processed point cloud in {processing_time:.3f}s')
            
        except Exception as e:
            self.get_logger().error(f'Error processing point cloud: {e}')
            import traceback
            self.get_logger().error(f'Traceback: {traceback.format_exc()}')
    
    def robot_pose_callback(self, msg: PoseStamped) -> None:
        """
        Update current robot pose.
        
        Args:
            msg: PoseStamped message containing robot position and orientation
        """
        self.current_robot_pose = msg
        self.get_logger().debug(f'Updated robot pose: {msg.pose.position}')
    
    def _convert_pointcloud2_to_open3d(self, msg: PointCloud2) -> o3d.geometry.PointCloud:
        """
        Convert ROS PointCloud2 message to Open3D PointCloud.
        
        Args:
            msg: PointCloud2 message
            
        Returns:
            Open3D PointCloud object
        """
        try:
            # Extract points using sensor_msgs_py
            points = point_cloud2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True)
            points_array = np.array(list(points))
            
            if len(points_array) == 0:
                return o3d.geometry.PointCloud()
            
            # Create Open3D point cloud
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(points_array)
            
            return pcd
            
        except Exception as e:
            self.get_logger().error(f'Error converting PointCloud2 to Open3D: {e}')
            return o3d.geometry.PointCloud()
    
    def _publish_terrain_info(self, terrain_analysis: Dict, classification: Dict, voxel_result: Dict) -> None:
        """
        Publish TerrainInfo message.
        
        Args:
            terrain_analysis: Terrain analysis results
            classification: Voxel classification results
            voxel_result: Voxel processing results
        """
        try:
            msg = TerrainInfo()
            
            # Header
            msg.header = Header()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'map'
            
            # 統計情報
            stats = terrain_analysis['statistics']
            msg.avg_slope = stats['avg_slope']
            msg.max_slope = stats['max_slope']
            msg.min_slope = stats['min_slope']
            msg.traversable_ratio = classification['ground_ratio']
            
            # ボクセル情報
            msg.total_voxels = voxel_result['num_voxels']
            msg.ground_voxels = len(classification['ground_indices'])
            msg.obstacle_voxels = len(classification['obstacle_indices'])
            
            # リスク情報
            msg.avg_risk = stats['avg_risk']
            msg.max_risk = stats['max_risk']
            
            # コスト情報
            msg.avg_cost = stats['avg_cost']
            msg.impassable_ratio = stats['unsafe_ratio']
            
            # 処理情報
            msg.processing_time = self.processing_stats['last_processing_time']
            msg.point_count = stats['total_points']
            
            self.terrain_info_pub.publish(msg)
            
            self.get_logger().debug(
                f'Published TerrainInfo: avg_slope={msg.avg_slope:.1f}°, '
                f'traversable={msg.traversable_ratio:.1%}, '
                f'voxels={msg.total_voxels}'
            )
            
        except Exception as e:
            self.get_logger().error(f'Error publishing TerrainInfo: {e}')
    
    def _publish_voxel_grid(self, voxel_result: Dict, classification: Dict, terrain_analysis: Dict) -> None:
        """
        Publish VoxelGrid3D message.
        
        Args:
            voxel_result: Voxel processing results
            classification: Voxel classification results
            terrain_analysis: Terrain analysis results
        """
        try:
            msg = VoxelGrid3D()
            
            # Header
            msg.header = Header()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'map'
            
            # ボクセルグリッド情報
            msg.voxel_size = self.voxel_size
            msg.num_voxels = voxel_result['num_voxels']
            
            # 境界情報
            bounds = voxel_result['bounds']
            msg.min_bound = Point(x=bounds['min'][0], y=bounds['min'][1], z=bounds['min'][2])
            msg.max_bound = Point(x=bounds['max'][0], y=bounds['max'][1], z=bounds['max'][2])
            msg.size = Vector3(x=bounds['size'][0], y=bounds['size'][1], z=bounds['size'][2])
            
            # ボクセルデータ（サンプル - 全データは大きすぎるため）
            voxel_grid = voxel_result['voxel_grid']
            voxels = voxel_grid.get_voxels()
            
            # サンプリング（最大1000ボクセル）
            max_voxels = min(1000, len(voxels))
            sample_indices = np.random.choice(len(voxels), max_voxels, replace=False)
            
            voxel_indices = []
            voxel_types = []
            voxel_slopes = []
            voxel_risks = []
            voxel_costs = []
            
            slope_angles = terrain_analysis['slope_angles']
            risk_scores = terrain_analysis['risk_scores']
            traversability_costs = terrain_analysis['traversability_costs']
            
            for i, idx in enumerate(sample_indices):
                voxel = voxels[idx]
                voxel_indices.extend([voxel.grid_index[0], voxel.grid_index[1], voxel.grid_index[2]])
                
                # ボクセルタイプ（簡易版）
                if idx < len(classification['ground_indices']):
                    voxel_types.append(1)  # 地面
                    if i < len(slope_angles):
                        voxel_slopes.append(slope_angles[i])
                        voxel_risks.append(risk_scores[i])
                        voxel_costs.append(traversability_costs[i])
                    else:
                        voxel_slopes.append(0.0)
                        voxel_risks.append(0.0)
                        voxel_costs.append(1.0)
                else:
                    voxel_types.append(2)  # 障害物
                    voxel_slopes.append(0.0)
                    voxel_risks.append(0.0)
                    voxel_costs.append(999.0)
            
            msg.voxel_indices = voxel_indices
            msg.voxel_types = voxel_types
            msg.voxel_slopes = voxel_slopes
            msg.voxel_risks = voxel_risks
            msg.voxel_costs = voxel_costs
            
            self.voxel_grid_pub.publish(msg)
            
            self.get_logger().debug(f'Published VoxelGrid3D: {msg.num_voxels} voxels, {len(voxel_indices)//3} samples')
            
        except Exception as e:
            self.get_logger().error(f'Error publishing VoxelGrid3D: {e}')
    
    def _publish_visualization(self, voxel_result: Dict, classification: Dict, terrain_analysis: Dict) -> None:
        """
        Publish visualization markers for Rviz.
        
        Args:
            voxel_result: Voxel processing results
            classification: Voxel classification results
            terrain_analysis: Terrain analysis results
        """
        try:
            markers = MarkerArray()
            
            # ボクセルマーカー（傾斜別色分け）
            voxel_grid = voxel_result['voxel_grid']
            centers = self.voxel_processor.get_voxel_centers(voxel_grid)
            
            slope_angles = terrain_analysis['slope_angles']
            ground_indices = classification['ground_indices']
            
            # 地面ボクセルのマーカー
            for i, voxel_idx in enumerate(ground_indices[:100]):  # 最大100個
                if i < len(slope_angles) and voxel_idx < len(centers):
                    marker = Marker()
                    marker.header.frame_id = 'map'
                    marker.header.stamp = self.get_clock().now().to_msg()
                    marker.id = voxel_idx
                    marker.type = Marker.CUBE
                    marker.action = Marker.ADD
                    
                    # Position
                    marker.pose.position.x = float(centers[voxel_idx][0])
                    marker.pose.position.y = float(centers[voxel_idx][1])
                    marker.pose.position.z = float(centers[voxel_idx][2])
                    
                    # Size
                    marker.scale.x = self.voxel_size
                    marker.scale.y = self.voxel_size
                    marker.scale.z = self.voxel_size
                    
                    # Color based on slope
                    slope = slope_angles[i]
                    if slope < 10:
                        # Green: flat
                        marker.color.r = 0.0
                        marker.color.g = 1.0
                        marker.color.b = 0.0
                    elif slope < 20:
                        # Yellow: gentle
                        marker.color.r = 1.0
                        marker.color.g = 1.0
                        marker.color.b = 0.0
                    elif slope < 30:
                        # Orange: moderate
                        marker.color.r = 1.0
                        marker.color.g = 0.5
                        marker.color.b = 0.0
                    else:
                        # Red: steep
                        marker.color.r = 1.0
                        marker.color.g = 0.0
                        marker.color.b = 0.0
                    
                    marker.color.a = 0.7
                    markers.markers.append(marker)
            
            self.visualization_pub.publish(markers)
            
            self.get_logger().debug(f'Published {len(markers.markers)} visualization markers')
            
        except Exception as e:
            self.get_logger().error(f'Error publishing visualization: {e}')
    
    def _update_processing_stats(self, processing_time: float) -> None:
        """
        Update processing statistics.
        
        Args:
            processing_time: Time taken for processing
        """
        self.processing_stats['total_processed'] += 1
        self.processing_stats['total_time'] += processing_time
        self.processing_stats['last_processing_time'] = processing_time
        self.processing_stats['avg_processing_time'] = (
            self.processing_stats['total_time'] / self.processing_stats['total_processed']
        )
        
        # Log statistics every 10 processed point clouds
        if self.processing_stats['total_processed'] % 10 == 0:
            self.get_logger().info(
                f'Processing stats: {self.processing_stats["total_processed"]} processed, '
                f'avg_time={self.processing_stats["avg_processing_time"]:.3f}s'
            )


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