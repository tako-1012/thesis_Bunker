#!/usr/bin/env python3
"""
unity_visualization_node.py
UnityへROS2データを送信するブリッジノード
"""

import rclpy
from rclpy.node import Node
import json
import socket
import sys
from pathlib import Path

# ROS2メッセージのインポート
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped

class UnityVisualizationNode(Node):
    def __init__(self):
        super().__init__('unity_visualization_node')
        
        # Unity接続（TCP Socket）
        self.unity_socket = None
        self.connect_to_unity()
        
        # ROS2サブスクライバー
        self.path_subscription = self.create_subscription(
            Path,
            '/path_3d',
            self.path_callback,
            10
        )
        
        self.pointcloud_subscription = self.create_subscription(
            PointCloud2,
            '/rtabmap/cloud_map',
            self.pointcloud_callback,
            10
        )
        
        self.get_logger().info('Unity Visualization Node started')
    
    def connect_to_unity(self):
        """Unity側のサーバーに接続"""
        try:
            self.unity_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.unity_socket.connect(('localhost', 11000))
            self.get_logger().info('✅ Unity接続成功')
        except Exception as e:
            self.get_logger().error(f'❌ Unity接続失敗: {e}')
            self.unity_socket = None
    
    def path_callback(self, msg):
        """経路データを受信してUnityに送信"""
        if self.unity_socket is None:
            return
        
        # ROS2 Path → Unity Vector3配列に変換
        path_points = []
        for pose_stamped in msg.poses:
            point = {
                'x': pose_stamped.pose.position.x,
                'y': pose_stamped.pose.position.y,
                'z': pose_stamped.pose.position.z
            }
            path_points.append(point)
        
        # Unityに送信
        data = {
            'type': 'path',
            'path': path_points,
            'timestamp': self.get_clock().now().nanoseconds
        }
        
        self.send_to_unity(data)
    
    def pointcloud_callback(self, msg):
        """点群データを受信してUnityに送信"""
        if self.unity_socket is None:
            return
        
        # 点群データを簡略化して送信
        # 実際の実装では、点群をサンプリングして送信
        data = {
            'type': 'pointcloud',
            'count': len(msg.data) // 12,  # 簡略化
            'timestamp': self.get_clock().now().nanoseconds
        }
        
        self.send_to_unity(data)
    
    def send_to_unity(self, data):
        """Unityにデータを送信"""
        try:
            json_data = json.dumps(data) + '\n'
            self.unity_socket.sendall(json_data.encode())
        except Exception as e:
            self.get_logger().error(f'Unity送信エラー: {e}')
            self.connect_to_unity()  # 再接続試行
    
    def send_scenario_to_unity(self, scenario_id):
        """シナリオデータをUnityに送信"""
        if self.unity_socket is None:
            return
        
        data = {
            'type': 'scenario',
            'scenario_id': scenario_id,
            'timestamp': self.get_clock().now().nanoseconds
        }
        
        self.send_to_unity(data)

def main():
    rclpy.init()
    node = UnityVisualizationNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()


