#!/usr/bin/env python3
"""
Path Planner 3D Node
Plans 3D paths considering terrain slopes and obstacles for Bunker robot navigation.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from geometry_msgs.msg import PoseStamped, Pose
from nav_msgs.msg import Path
from visualization_msgs.msg import MarkerArray
from std_msgs.msg import Float32, Header
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import yaml
import os

# Custom messages (will be defined later)
# from bunker_3d_nav.msg import VoxelGrid3D, TerrainInfo, PathCost

try:
    from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
    from bunker_3d_nav.path_planner_3d.cost_function import CostFunction
    from bunker_3d_nav.path_planner_3d.path_smoother import PathSmoother
except ImportError:
    # Fallback for development
    AStar3D = None
    CostFunction = None
    PathSmoother = None


class PathPlanner3DNode(Node):
    """
    ROS2 node for 3D path planning in uneven terrain.
    
    This node subscribes to terrain information and goal poses, then publishes
    optimal 3D paths considering slopes, obstacles, and robot stability.
    """
    
    def __init__(self) -> None:
        super().__init__('path_planner_3d')
        
        # Declare parameters
        self._declare_parameters()
        
        # Load configuration
        self._load_config()
        
        # Initialize path planning components
        self.astar_planner = AStar3D(
            voxel_size=self.voxel_size,
            max_iterations=self.max_iterations
        )
        
        self.cost_function = CostFunction(
            weights=self.cost_weights,
            safety_params=self.safety_params
        )
        
        self.path_smoother = PathSmoother(
            smoothing_method=self.smoothing_method,
            smoothness_factor=self.smoothness_factor
        )
        
        # Setup QoS profile
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        # TODO: Uncomment when custom messages are defined
        # self.terrain_sub = self.create_subscription(
        #     VoxelGrid3D,
        #     '/terrain/voxel_grid',
        #     self.terrain_callback,
        #     qos_profile
        # )
        
        self.goal_sub = self.create_subscription(
            PoseStamped,
            '/goal_pose',
            self.goal_callback,
            qos_profile
        )
        
        self.current_pose_sub = self.create_subscription(
            PoseStamped,
            '/current_pose',
            self.current_pose_callback,
            qos_profile
        )
        
        # Publishers
        self.path_pub = self.create_publisher(
            Path,
            '/path_3d',
            10
        )
        
        self.path_visualization_pub = self.create_publisher(
            MarkerArray,
            '/path_visualization',
            10
        )
        
        # TODO: Uncomment when custom messages are defined
        # self.path_cost_pub = self.create_publisher(
        #     PathCost,
        #     '/path_cost',
        #     10
        # )
        
        # State variables
        self.current_terrain: Optional[Dict[str, Any]] = None
        self.current_pose: Optional[PoseStamped] = None
        self.current_goal: Optional[PoseStamped] = None
        self.last_planned_path: Optional[Path] = None
        
        # Planning state
        self.is_planning = False
        self.planning_timeout = 10.0  # seconds
        
        self.get_logger().info('Path Planner 3D Node initialized')
        self.get_logger().info(f'Voxel size: {self.voxel_size}m')
        self.get_logger().info(f'Max iterations: {self.max_iterations}')
        self.get_logger().info(f'Cost weights: {self.cost_weights}')
    
    def _declare_parameters(self) -> None:
        """Declare ROS2 parameters with default values."""
        self.declare_parameter('voxel_size', 0.1)
        self.declare_parameter('max_iterations', 10000)
        self.declare_parameter('planning_timeout', 10.0)
        self.declare_parameter('config_file', 'planner_params.yaml')
        self.declare_parameter('enable_path_smoothing', True)
        self.declare_parameter('enable_visualization', True)
        
        # Cost function weights
        self.declare_parameter('weight_distance', 1.0)
        self.declare_parameter('weight_slope', 3.0)
        self.declare_parameter('weight_obstacle', 5.0)
        self.declare_parameter('weight_stability', 4.0)
        
        # Safety parameters
        self.declare_parameter('min_obstacle_distance', 0.5)
        self.declare_parameter('max_roll_angle', 20.0)
        self.declare_parameter('max_pitch_angle', 25.0)
        
        # Path smoothing
        self.declare_parameter('smoothing_method', 'cubic_spline')
        self.declare_parameter('smoothness_factor', 0.5)
    
    def _load_config(self) -> None:
        """Load parameters from configuration file."""
        # Get parameter values
        self.voxel_size = self.get_parameter('voxel_size').value
        self.max_iterations = self.get_parameter('max_iterations').value
        self.planning_timeout = self.get_parameter('planning_timeout').value
        self.enable_path_smoothing = self.get_parameter('enable_path_smoothing').value
        self.enable_visualization = self.get_parameter('enable_visualization').value
        
        # Cost function weights
        self.cost_weights = {
            'distance': self.get_parameter('weight_distance').value,
            'slope': self.get_parameter('weight_slope').value,
            'obstacle': self.get_parameter('weight_obstacle').value,
            'stability': self.get_parameter('weight_stability').value
        }
        
        # Safety parameters
        self.safety_params = {
            'min_obstacle_distance': self.get_parameter('min_obstacle_distance').value,
            'max_roll_angle': self.get_parameter('max_roll_angle').value,
            'max_pitch_angle': self.get_parameter('max_pitch_angle').value
        }
        
        # Path smoothing
        self.smoothing_method = self.get_parameter('smoothing_method').value
        self.smoothness_factor = self.get_parameter('smoothness_factor').value
        
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
        if 'path_planner_3d' in config:
            planner_config = config['path_planner_3d']
            
            if 'voxel_size' in planner_config:
                self.voxel_size = planner_config['voxel_size']
            if 'max_iterations' in planner_config:
                self.max_iterations = planner_config['max_iterations']
            if 'planning_timeout' in planner_config:
                self.planning_timeout = planner_config['planning_timeout']
            
            if 'weights' in planner_config:
                weights = planner_config['weights']
                if 'distance' in weights:
                    self.cost_weights['distance'] = weights['distance']
                if 'slope' in weights:
                    self.cost_weights['slope'] = weights['slope']
                if 'obstacle' in weights:
                    self.cost_weights['obstacle'] = weights['obstacle']
                if 'stability' in weights:
                    self.cost_weights['stability'] = weights['stability']
            
            if 'safety' in planner_config:
                safety = planner_config['safety']
                if 'min_obstacle_distance' in safety:
                    self.safety_params['min_obstacle_distance'] = safety['min_obstacle_distance']
                if 'max_roll_angle' in safety:
                    self.safety_params['max_roll_angle'] = safety['max_roll_angle']
                if 'max_pitch_angle' in safety:
                    self.safety_params['max_pitch_angle'] = safety['max_pitch_angle']
            
            if 'path_smoothing' in planner_config:
                smoothing = planner_config['path_smoothing']
                if 'method' in smoothing:
                    self.smoothing_method = smoothing['method']
                if 'smoothness' in smoothing:
                    self.smoothness_factor = smoothing['smoothness']
    
    def terrain_callback(self, msg) -> None:
        """
        Process incoming terrain information.
        
        Args:
            msg: VoxelGrid3D message containing terrain data
        """
        try:
            # TODO: Implement terrain data processing
            # This is a placeholder implementation
            
            self.current_terrain = {
                'voxel_grid': None,  # Will be populated from msg
                'slopes': None,      # Will be populated from msg
                'metadata': {
                    'resolution': self.voxel_size,
                    'timestamp': msg.header.stamp
                }
            }
            
            self.get_logger().debug('Updated terrain information')
            
            # Trigger path planning if goal is available
            if self.current_goal is not None and self.current_pose is not None:
                self._plan_path()
                
        except Exception as e:
            self.get_logger().error(f'Error processing terrain data: {e}')
    
    def goal_callback(self, msg: PoseStamped) -> None:
        """
        Process incoming goal pose.
        
        Args:
            msg: PoseStamped message containing goal position and orientation
        """
        try:
            self.current_goal = msg
            self.get_logger().info(f'New goal received: {msg.pose.position}')
            
            # Trigger path planning if terrain is available
            if self.current_terrain is not None and self.current_pose is not None:
                self._plan_path()
                
        except Exception as e:
            self.get_logger().error(f'Error processing goal: {e}')
    
    def current_pose_callback(self, msg: PoseStamped) -> None:
        """
        Update current robot pose.
        
        Args:
            msg: PoseStamped message containing current robot position and orientation
        """
        self.current_pose = msg
        self.get_logger().debug(f'Updated current pose: {msg.pose.position}')
    
    def _plan_path(self) -> None:
        """Plan 3D path from current pose to goal."""
        if self.is_planning:
            self.get_logger().warn('Path planning already in progress')
            return
        
        try:
            self.is_planning = True
            self.get_logger().info('Starting 3D path planning...')
            
            # TODO: Implement actual path planning
            # This is a placeholder implementation
            
            # Convert poses to numpy arrays
            start_pos = self._pose_to_numpy(self.current_pose.pose)
            goal_pos = self._pose_to_numpy(self.current_goal.pose)
            
            # Plan path using A* 3D
            path_points = self._plan_path_placeholder(start_pos, goal_pos)
            
            # Smooth path if enabled
            if self.enable_path_smoothing and len(path_points) > 2:
                path_points = self.path_smoother.smooth_path(path_points)
            
            # Create ROS Path message
            path_msg = self._create_path_message(path_points)
            
            # Publish path
            self.path_pub.publish(path_msg)
            self.last_planned_path = path_msg
            
            # Publish visualization
            if self.enable_visualization:
                visualization_msg = self._create_visualization_message(path_points)
                self.path_visualization_pub.publish(visualization_msg)
            
            # TODO: Calculate and publish path cost
            # path_cost_msg = self._calculate_path_cost(path_points)
            # self.path_cost_pub.publish(path_cost_msg)
            
            self.get_logger().info(f'Path planning completed with {len(path_points)} waypoints')
            
        except Exception as e:
            self.get_logger().error(f'Error in path planning: {e}')
        finally:
            self.is_planning = False
    
    def _pose_to_numpy(self, pose: Pose) -> np.ndarray:
        """Convert ROS Pose to numpy array [x, y, z, roll, pitch, yaw]."""
        # TODO: Implement proper pose conversion
        # This is a placeholder implementation
        
        position = pose.position
        orientation = pose.orientation
        
        # Convert quaternion to euler angles
        # TODO: Implement proper quaternion to euler conversion
        
        return np.array([
            position.x,
            position.y,
            position.z,
            0.0,  # roll (placeholder)
            0.0,  # pitch (placeholder)
            0.0   # yaw (placeholder)
        ])
    
    def _plan_path_placeholder(self, start: np.ndarray, goal: np.ndarray) -> List[np.ndarray]:
        """
        Placeholder for path planning.
        
        TODO: Implement actual A* 3D path planning
        """
        # Create simple straight-line path for testing
        path_points = []
        
        # Add start point
        path_points.append(start)
        
        # Add intermediate points
        num_points = 10
        for i in range(1, num_points):
            t = i / num_points
            point = start + t * (goal - start)
            path_points.append(point)
        
        # Add goal point
        path_points.append(goal)
        
        return path_points
    
    def _create_path_message(self, path_points: List[np.ndarray]) -> Path:
        """Create ROS Path message from path points."""
        path_msg = Path()
        path_msg.header = Header()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = 'map'
        
        for point in path_points:
            pose_stamped = PoseStamped()
            pose_stamped.header = path_msg.header
            pose_stamped.pose.position.x = point[0]
            pose_stamped.pose.position.y = point[1]
            pose_stamped.pose.position.z = point[2]
            
            # TODO: Set proper orientation
            pose_stamped.pose.orientation.w = 1.0
            
            path_msg.poses.append(pose_stamped)
        
        return path_msg
    
    def _create_visualization_message(self, path_points: List[np.ndarray]) -> MarkerArray:
        """Create visualization markers for path."""
        markers = MarkerArray()
        
        # TODO: Create actual visualization markers
        # - Path line
        # - Waypoint markers
        # - Cost indicators
        
        return markers
    
    def _calculate_path_cost(self, path_points: List[np.ndarray]) -> Dict[str, float]:
        """Calculate path cost metrics."""
        # TODO: Implement path cost calculation
        # This is a placeholder implementation
        
        if len(path_points) < 2:
            return {
                'total_cost': 0.0,
                'distance_cost': 0.0,
                'slope_cost': 0.0,
                'obstacle_cost': 0.0,
                'stability_cost': 0.0,
                'path_length': 0.0,
                'max_slope': 0.0,
                'avg_slope': 0.0
            }
        
        # Calculate path length
        path_length = 0.0
        for i in range(1, len(path_points)):
            distance = np.linalg.norm(path_points[i] - path_points[i-1])
            path_length += distance
        
        # Placeholder cost calculations
        total_cost = path_length * 1.0  # Simple distance cost
        
        return {
            'total_cost': total_cost,
            'distance_cost': path_length,
            'slope_cost': 0.0,  # TODO: Calculate actual slope cost
            'obstacle_cost': 0.0,  # TODO: Calculate actual obstacle cost
            'stability_cost': 0.0,  # TODO: Calculate actual stability cost
            'path_length': path_length,
            'max_slope': 0.0,  # TODO: Calculate actual max slope
            'avg_slope': 0.0   # TODO: Calculate actual avg slope
        }


def main(args=None):
    """Main function to start the path planner 3D node."""
    rclpy.init(args=args)
    
    try:
        node = PathPlanner3DNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'Error in path planner 3D node: {e}')
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
