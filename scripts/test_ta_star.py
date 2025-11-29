#!/usr/bin/env python3
"""
TA* Quick Test Script
TA*システムの簡易動作確認用スクリプト
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
import time

class TAStarQuickTest(Node):
    def __init__(self):
        super().__init__('ta_star_quick_test')
        
        # Publishers
        self.current_pose_pub = self.create_publisher(PoseStamped, '/current_pose', 10)
        self.goal_pose_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        
        # Subscriber
        self.path_sub = self.create_subscription(
            Path,
            '/path_3d',
            self.path_callback,
            10
        )
        
        self.path_received = False
        self.get_logger().info('✅ TA* Quick Test Node initialized')
    
    def path_callback(self, msg):
        """経路を受信"""
        self.path_received = True
        self.get_logger().info(f'✅ Path received with {len(msg.poses)} waypoints')
        
        if len(msg.poses) > 0:
            first = msg.poses[0].pose.position
            last = msg.poses[-1].pose.position
            self.get_logger().info(f'   Start: ({first.x:.2f}, {first.y:.2f}, {first.z:.2f})')
            self.get_logger().info(f'   Goal:  ({last.x:.2f}, {last.y:.2f}, {last.z:.2f})')
    
    def publish_test_poses(self):
        """テスト用のpose送信"""
        # 現在位置
        current = PoseStamped()
        current.header.frame_id = 'map'
        current.header.stamp = self.get_clock().now().to_msg()
        current.pose.position.x = 0.0
        current.pose.position.y = 0.0
        current.pose.position.z = 0.5
        current.pose.orientation.w = 1.0
        
        self.current_pose_pub.publish(current)
        self.get_logger().info('📍 Current pose published: (0.0, 0.0, 0.5)')
        
        time.sleep(0.5)
        
        # 目標位置
        goal = PoseStamped()
        goal.header.frame_id = 'map'
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = 5.0
        goal.pose.position.y = 5.0
        goal.pose.position.z = 0.5
        goal.pose.orientation.w = 1.0
        
        self.goal_pose_pub.publish(goal)
        self.get_logger().info('🎯 Goal pose published: (5.0, 5.0, 0.5)')


def main():
    rclpy.init()
    node = TAStarQuickTest()
    
    # 初期化待ち
    time.sleep(2.0)
    
    # テスト実行
    node.get_logger().info('🚀 Starting TA* quick test...')
    node.publish_test_poses()
    
    # 経路受信待ち（最大10秒）
    timeout = 10.0
    start_time = time.time()
    
    while not node.path_received and (time.time() - start_time) < timeout:
        rclpy.spin_once(node, timeout_sec=0.1)
    
    if node.path_received:
        node.get_logger().info('✅ Test PASSED: Path planning successful!')
    else:
        node.get_logger().error('❌ Test FAILED: No path received within timeout')
    
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
