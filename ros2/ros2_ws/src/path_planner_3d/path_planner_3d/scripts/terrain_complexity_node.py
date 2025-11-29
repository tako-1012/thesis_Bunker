#!/usr/bin/env python3
"""
ROS2ノード: TerrainComplexityNode
RTAB-Mapの点群を受信し、地形複雑度を評価・配信する
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String, Float32
from geometry_msgs.msg import PoseStamped
import sensor_msgs_py.point_cloud2 as pc2
import numpy as np
import open3d as o3d
from path_planner_3d.terrain_complexity_evaluator import TerrainComplexityEvaluator
from typing import Optional

class TerrainComplexityNode(Node):
    """
    RTAB-Map点群から地形複雑度を評価し配信するROS2ノード
    """
    def __init__(self) -> None:
        """
        ノード初期化・サブスクライバ/パブリッシャ/タイマー/パラメータ設定
        """
        super().__init__('terrain_complexity_node')
        self.declare_parameter('evaluation_radius', 5.0)
        self.declare_parameter('complexity_threshold_low', 0.15)
        self.declare_parameter('complexity_threshold_high', 0.55)
        radius = self.get_parameter('evaluation_radius').get_parameter_value().double_value
        th_low = self.get_parameter('complexity_threshold_low').get_parameter_value().double_value
        th_high = self.get_parameter('complexity_threshold_high').get_parameter_value().double_value
        self.evaluator = TerrainComplexityEvaluator(evaluation_radius=radius, complexity_thresholds=(th_low, th_high))
        self.latest_cloud: Optional[PointCloud2] = None
        self.start_pose: Optional[PoseStamped] = None
        self.cloud_sub = self.create_subscription(
            PointCloud2, '/rtabmap/cloud_map', self.cloud_callback, 10)
        self.pose_sub = self.create_subscription(
            PoseStamped, '/start_pose', self.start_pose_callback, 10)
        self.complexity_pub = self.create_publisher(String, '/terrain_complexity', 10)
        self.score_pub = self.create_publisher(Float32, '/terrain_complexity_score', 10)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.get_logger().info('TerrainComplexityNode initialized.')

    def cloud_callback(self, msg: PointCloud2) -> None:
        """
        RTAB-Map点群受信時のコールバック
        """
        self.latest_cloud = msg
        # 点数取得
        try:
            n_points = msg.width * msg.height
            self.get_logger().info(f"Received point cloud with {n_points} points")
        except Exception:
            self.get_logger().info("Received point cloud.")

    def start_pose_callback(self, msg: PoseStamped) -> None:
        """
        始点位置受信時のコールバック
        """
        self.start_pose = msg

    def timer_callback(self) -> None:
        """
        1Hz周期で地形複雑度を評価し配信
        """
        if self.latest_cloud is None:
            return
        try:
            pcd = self.pointcloud2_to_o3d(self.latest_cloud)
            if len(pcd.points) == 0:
                self.get_logger().warn('Point cloud is empty. Skipping evaluation.')
                return
            complexity = self.evaluator.evaluate_complexity(pcd)
            # スコアも計算
            slope_var = self.evaluator.calc_slope_variance(pcd)
            obs_density = self.evaluator.calc_obstacle_density(pcd)
            score = self.evaluator.compute_complexity_score(slope_var, obs_density)
            self.complexity_pub.publish(String(data=complexity))
            self.score_pub.publish(Float32(data=float(score)))
            self.get_logger().info(f"Terrain complexity: {complexity} (score: {score:.3f})")
        except Exception as e:
            self.get_logger().error(f"Error in timer_callback: {e}")

    def pointcloud2_to_o3d(self, cloud: PointCloud2) -> o3d.geometry.PointCloud:
        """
        PointCloud2メッセージをopen3d点群に変換
        """
        try:
            points = []
            for pt in pc2.read_points(cloud, field_names=("x", "y", "z"), skip_nans=True):
                points.append([pt[0], pt[1], pt[2]])
            pcd = o3d.geometry.PointCloud()
            if points:
                pcd.points = o3d.utility.Vector3dVector(np.array(points, dtype=np.float32))
            return pcd
        except Exception as e:
            self.get_logger().error(f"Failed to convert PointCloud2 to Open3D: {e}")
            return o3d.geometry.PointCloud()

def main(args=None):
    """
    ROS2ノード起動用エントリポイント
    """
    rclpy.init(args=args)
    node = TerrainComplexityNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
