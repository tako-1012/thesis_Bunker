"""
ROS2ノード: 経路計画サービス

実機ロボットで使えるROSノード
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Path as ROSPath
from nav_msgs.msg import OccupancyGrid
import sys
from pathlib import Path as FilePath

sys.path.insert(0, str(FilePath(__file__).parent.parent / 'path_planner_3d'))

from path_planner_3d.terrain_aware_astar_fast import TerrainAwareAStarFast
from path_planner_3d.config import PlannerConfig

class PathPlannerNode(Node):
    """経路計画ROSノード"""
    
    def __init__(self):
        super().__init__('path_planner_node')
        
        # パラメータ
        self.declare_parameter('map_size', 50.0)
        self.declare_parameter('voxel_size', 0.2)
        
        map_size = self.get_parameter('map_size').value
        voxel_size = self.get_parameter('voxel_size').value
        
        # プランナー初期化
        config = PlannerConfig(
            map_bounds=([-map_size/2, -map_size/2, 0],
                       [map_size/2, map_size/2, 5]),
            voxel_size=voxel_size
        )
        
        self.planner = TerrainAwareAStarFast(config)
        
        # Subscriber
        self.goal_sub = self.create_subscription(
            PoseStamped,
            '/goal_pose',
            self.goal_callback,
            10
        )
        
        self.start_sub = self.create_subscription(
            PoseStamped,
            '/start_pose',
            self.start_callback,
            10
        )
        
        # Publisher
        self.path_pub = self.create_publisher(
            ROSPath,
            '/planned_path',
            10
        )
        
        self.start_pose = None
        self.goal_pose = None
        
        self.get_logger().info('Path Planner Node initialized')
    
    def start_callback(self, msg):
        """スタート位置受信"""
        self.start_pose = [
            msg.pose.position.x,
            msg.pose.position.y,
            msg.pose.position.z
        ]
        self.get_logger().info(f'Start: {self.start_pose}')
        self.plan_if_ready()
    
    def goal_callback(self, msg):
        """ゴール位置受信"""
        self.goal_pose = [
            msg.pose.position.x,
            msg.pose.position.y,
            msg.pose.position.z
        ]
        self.get_logger().info(f'Goal: {self.goal_pose}')
        self.plan_if_ready()
    
    def plan_if_ready(self):
        """スタート・ゴールが揃ったら経路計画"""
        if self.start_pose is None or self.goal_pose is None:
            return
        
        self.get_logger().info('Planning path...')
        
        # 経路計画実行
        result = self.planner.plan_path(
            self.start_pose,
            self.goal_pose,
            timeout=60
        )
        
        if result.success:
            self.get_logger().info(
                f'Success! Time: {result.computation_time:.2f}s, '
                f'Length: {result.path_length:.2f}m'
            )
            
            # ROS Pathに変換して配信
            ros_path = self.convert_to_ros_path(result.path)
            self.path_pub.publish(ros_path)
        else:
            self.get_logger().warn(f'Failed: {result.error_message}')
    
    def convert_to_ros_path(self, path):
        """経路をROS Pathに変換"""
        ros_path = ROSPath()
        ros_path.header.stamp = self.get_clock().now().to_msg()
        ros_path.header.frame_id = 'map'
        
        for point in path:
            pose = PoseStamped()
            pose.header = ros_path.header
            pose.pose.position.x = point[0]
            pose.pose.position.y = point[1]
            pose.pose.position.z = point[2]
            
            ros_path.poses.append(pose)
        
        return ros_path

def main(args=None):
    rclpy.init(args=args)
    node = PathPlannerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()



