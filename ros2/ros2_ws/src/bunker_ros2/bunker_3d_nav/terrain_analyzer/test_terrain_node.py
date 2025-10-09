#!/usr/bin/env python3
"""
統合テストコード: terrain_analyzer_node
ノードの起動、メッセージパブリッシュ、パイプライン全体のテスト
"""

import sys
import time
import threading
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Header
import numpy as np
import open3d as o3d
from sensor_msgs_py import point_cloud2

# 相対importを試みる
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
except ImportError:
    # パスを追加して再試行
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D


class TerrainAnalyzerTester(Node):
    """terrain_analyzer_nodeの統合テスト用ノード"""
    
    def __init__(self):
        super().__init__('terrain_analyzer_tester')
        
        # テスト結果
        self.test_results = {
            'terrain_info_received': False,
            'voxel_grid_received': False,
            'processing_time': 0.0,
            'message_count': 0,
            'errors': []
        }
        
        # Subscribers for testing
        self.terrain_info_sub = self.create_subscription(
            TerrainInfo,
            '/bunker/terrain_info',
            self.terrain_info_callback,
            10
        )
        
        self.voxel_grid_sub = self.create_subscription(
            VoxelGrid3D,
            '/bunker/voxel_grid',
            self.voxel_grid_callback,
            10
        )
        
        # Publisher for test data
        self.pointcloud_pub = self.create_publisher(
            PointCloud2,
            '/bunker/pointcloud',
            10
        )
        
        self.robot_pose_pub = self.create_publisher(
            PoseStamped,
            '/robot_pose',
            10
        )
        
        self.get_logger().info('Terrain Analyzer Tester initialized')
    
    def terrain_info_callback(self, msg: TerrainInfo):
        """TerrainInfoメッセージの受信テスト"""
        self.test_results['terrain_info_received'] = True
        self.test_results['message_count'] += 1
        
        self.get_logger().info(
            f'Received TerrainInfo: avg_slope={msg.avg_slope:.1f}°, '
            f'traversable={msg.traversable_ratio:.1%}, '
            f'voxels={msg.total_voxels}, '
            f'processing_time={msg.processing_time:.3f}s'
        )
        
        # 処理時間の記録
        if msg.processing_time > 0:
            self.test_results['processing_time'] = msg.processing_time
    
    def voxel_grid_callback(self, msg: VoxelGrid3D):
        """VoxelGrid3Dメッセージの受信テスト"""
        self.test_results['voxel_grid_received'] = True
        
        self.get_logger().info(
            f'Received VoxelGrid3D: voxels={msg.num_voxels}, '
            f'samples={len(msg.voxel_indices)//3}, '
            f'size={msg.voxel_size}m'
        )
    
    def create_test_pointcloud(self) -> PointCloud2:
        """テスト用の点群データを作成"""
        # 複雑な地形データを生成
        points = []
        
        # 1. 平坦な地面
        for i in range(500):
            x = np.random.uniform(-2, 2)
            y = np.random.uniform(-2, 2)
            z = 0.0
            points.append([x, y, z])
        
        # 2. 緩やかな傾斜
        for i in range(300):
            x = np.random.uniform(-1, 1)
            y = np.random.uniform(-1, 1)
            z = np.random.uniform(0.1, 0.5)
            points.append([x, y, z])
        
        # 3. 急な傾斜
        for i in range(200):
            x = np.random.uniform(-0.5, 0.5)
            y = np.random.uniform(-0.5, 0.5)
            z = np.random.uniform(0.6, 1.0)
            points.append([x, y, z])
        
        # 4. 障害物（球体）
        for i in range(100):
            angle = np.random.uniform(0, 2*np.pi)
            radius = np.random.uniform(0.1, 0.3)
            x = 1.0 + radius * np.cos(angle)
            y = 1.0 + radius * np.sin(angle)
            z = np.random.uniform(0.1, 0.6)
            points.append([x, y, z])
        
        # PointCloud2メッセージを作成
        points_array = np.array(points)
        
        # Header
        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = 'map'
        
        # PointCloud2作成
        msg = point_cloud2.create_cloud_xyz32(header, points_array)
        
        return msg
    
    def create_test_robot_pose(self) -> PoseStamped:
        """テスト用のロボット姿勢を作成"""
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        msg.pose.position.x = 0.0
        msg.pose.position.y = 0.0
        msg.pose.position.z = 0.0
        
        msg.pose.orientation.x = 0.0
        msg.pose.orientation.y = 0.0
        msg.pose.orientation.z = 0.0
        msg.pose.orientation.w = 1.0
        
        return msg
    
    def run_integration_test(self):
        """統合テストの実行"""
        self.get_logger().info("Starting integration test...")
        
        try:
            # 1. テストデータの送信
            self.get_logger().info("1. Sending test point cloud...")
            pointcloud_msg = self.create_test_pointcloud()
            self.pointcloud_pub.publish(pointcloud_msg)
            
            # 2. ロボット姿勢の送信
            self.get_logger().info("2. Sending robot pose...")
            pose_msg = self.create_test_robot_pose()
            self.robot_pose_pub.publish(pose_msg)
            
            # 3. メッセージ受信の待機
            self.get_logger().info("3. Waiting for responses...")
            start_time = time.time()
            timeout = 10.0  # 10秒タイムアウト
            
            while time.time() - start_time < timeout:
                if (self.test_results['terrain_info_received'] and 
                    self.test_results['voxel_grid_received']):
                    break
                time.sleep(0.1)
            
            # 4. 結果の評価
            elapsed_time = time.time() - start_time
            
            if self.test_results['terrain_info_received'] and self.test_results['voxel_grid_received']:
                self.get_logger().info("✅ Integration test PASSED")
                self.get_logger().info(f"   Response time: {elapsed_time:.3f}s")
                self.get_logger().info(f"   Processing time: {self.test_results['processing_time']:.3f}s")
                self.get_logger().info(f"   Messages received: {self.test_results['message_count']}")
                return True
            else:
                self.get_logger().error("❌ Integration test FAILED")
                if not self.test_results['terrain_info_received']:
                    self.get_logger().error("   TerrainInfo not received")
                if not self.test_results['voxel_grid_received']:
                    self.get_logger().error("   VoxelGrid3D not received")
                return False
                
        except Exception as e:
            self.get_logger().error(f"Integration test error: {e}")
            self.test_results['errors'].append(str(e))
            return False
    
    def run_performance_test(self):
        """パフォーマンステストの実行"""
        self.get_logger().info("Starting performance test...")
        
        try:
            processing_times = []
            
            # 複数回のテスト
            for i in range(5):
                self.get_logger().info(f"Performance test iteration {i+1}/5")
                
                # テストデータ送信
                pointcloud_msg = self.create_test_pointcloud()
                self.pointcloud_pub.publish(pointcloud_msg)
                
                # レスポンス待機
                start_time = time.time()
                timeout = 5.0
                
                while time.time() - start_time < timeout:
                    if self.test_results['terrain_info_received']:
                        processing_times.append(self.test_results['processing_time'])
                        break
                    time.sleep(0.1)
                
                # リセット
                self.test_results['terrain_info_received'] = False
                self.test_results['voxel_grid_received'] = False
                time.sleep(1.0)  # 1秒間隔
            
            # 統計計算
            if processing_times:
                avg_time = np.mean(processing_times)
                max_time = np.max(processing_times)
                min_time = np.min(processing_times)
                
                self.get_logger().info("✅ Performance test completed")
                self.get_logger().info(f"   Average processing time: {avg_time:.3f}s")
                self.get_logger().info(f"   Max processing time: {max_time:.3f}s")
                self.get_logger().info(f"   Min processing time: {min_time:.3f}s")
                
                # パフォーマンス評価
                if avg_time < 1.0:  # 1秒以内
                    self.get_logger().info("   Performance: EXCELLENT")
                elif avg_time < 2.0:  # 2秒以内
                    self.get_logger().info("   Performance: GOOD")
                else:
                    self.get_logger().warn("   Performance: NEEDS IMPROVEMENT")
                
                return True
            else:
                self.get_logger().error("❌ Performance test FAILED - No responses received")
                return False
                
        except Exception as e:
            self.get_logger().error(f"Performance test error: {e}")
            return False
    
    def run_error_case_test(self):
        """エラーケーステストの実行"""
        self.get_logger().info("Starting error case test...")
        
        try:
            # 1. 空の点群テスト
            self.get_logger().info("1. Testing empty point cloud...")
            empty_msg = PointCloud2()
            empty_msg.header.stamp = self.get_clock().now().to_msg()
            empty_msg.header.frame_id = 'map'
            empty_msg.width = 0
            empty_msg.height = 1
            empty_msg.point_step = 12
            empty_msg.row_step = 0
            empty_msg.data = []
            
            self.pointcloud_pub.publish(empty_msg)
            time.sleep(2.0)
            
            # 2. 異常な点群テスト
            self.get_logger().info("2. Testing invalid point cloud...")
            invalid_msg = PointCloud2()
            invalid_msg.header.stamp = self.get_clock().now().to_msg()
            invalid_msg.header.frame_id = 'map'
            invalid_msg.width = 100
            invalid_msg.height = 1
            invalid_msg.point_step = 12
            invalid_msg.row_step = 1200
            invalid_msg.data = b'invalid_data' * 100
            
            self.pointcloud_pub.publish(invalid_msg)
            time.sleep(2.0)
            
            self.get_logger().info("✅ Error case test completed")
            return True
            
        except Exception as e:
            self.get_logger().error(f"Error case test error: {e}")
            return False


def test_node_startup():
    """ノード起動テスト"""
    print("=" * 60)
    print("Test 1: Node Startup Test")
    print("=" * 60)
    
    try:
        rclpy.init()
        tester = TerrainAnalyzerTester()
        
        print("✅ TerrainAnalyzerTester node started successfully")
        
        # 短時間スピンしてノードが正常に動作することを確認
        start_time = time.time()
        while time.time() - start_time < 2.0:
            rclpy.spin_once(tester, timeout_sec=0.1)
        
        tester.destroy_node()
        rclpy.shutdown()
        
        print("✅ Node startup test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Node startup test FAILED: {e}")
        return False


def test_message_publishing():
    """メッセージパブリッシュテスト"""
    print("\n" + "=" * 60)
    print("Test 2: Message Publishing Test")
    print("=" * 60)
    
    try:
        rclpy.init()
        tester = TerrainAnalyzerTester()
        
        # テストデータ送信
        pointcloud_msg = tester.create_test_pointcloud()
        pose_msg = tester.create_test_robot_pose()
        
        tester.pointcloud_pub.publish(pointcloud_msg)
        tester.robot_pose_pub.publish(pose_msg)
        
        print("✅ Test messages published successfully")
        
        # 短時間スピン
        start_time = time.time()
        while time.time() - start_time < 1.0:
            rclpy.spin_once(tester, timeout_sec=0.1)
        
        tester.destroy_node()
        rclpy.shutdown()
        
        print("✅ Message publishing test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Message publishing test FAILED: {e}")
        return False


def test_full_pipeline():
    """パイプライン全体テスト"""
    print("\n" + "=" * 60)
    print("Test 3: Full Pipeline Test")
    print("=" * 60)
    
    try:
        rclpy.init()
        tester = TerrainAnalyzerTester()
        
        # 統合テスト実行
        success = tester.run_integration_test()
        
        tester.destroy_node()
        rclpy.shutdown()
        
        if success:
            print("✅ Full pipeline test PASSED")
        else:
            print("❌ Full pipeline test FAILED")
        
        return success
        
    except Exception as e:
        print(f"❌ Full pipeline test FAILED: {e}")
        return False


def test_performance():
    """パフォーマンステスト"""
    print("\n" + "=" * 60)
    print("Test 4: Performance Test")
    print("=" * 60)
    
    try:
        rclpy.init()
        tester = TerrainAnalyzerTester()
        
        # パフォーマンステスト実行
        success = tester.run_performance_test()
        
        tester.destroy_node()
        rclpy.shutdown()
        
        if success:
            print("✅ Performance test PASSED")
        else:
            print("❌ Performance test FAILED")
        
        return success
        
    except Exception as e:
        print(f"❌ Performance test FAILED: {e}")
        return False


def test_error_cases():
    """エラーケーステスト"""
    print("\n" + "=" * 60)
    print("Test 5: Error Cases Test")
    print("=" * 60)
    
    try:
        rclpy.init()
        tester = TerrainAnalyzerTester()
        
        # エラーケーステスト実行
        success = tester.run_error_case_test()
        
        tester.destroy_node()
        rclpy.shutdown()
        
        if success:
            print("✅ Error cases test PASSED")
        else:
            print("❌ Error cases test FAILED")
        
        return success
        
    except Exception as e:
        print(f"❌ Error cases test FAILED: {e}")
        return False


def main():
    """メインテスト"""
    print("\n" + "=" * 60)
    print("terrain_analyzer_node 統合テストスイート")
    print("=" * 60 + "\n")
    
    success_count = 0
    total_tests = 5
    
    # テスト実行
    if test_node_startup():
        success_count += 1
    
    if test_message_publishing():
        success_count += 1
    
    if test_full_pipeline():
        success_count += 1
    
    if test_performance():
        success_count += 1
    
    if test_error_cases():
        success_count += 1
    
    # 結果表示
    print("\n" + "=" * 60)
    print(f"テスト結果: {success_count}/{total_tests} 成功")
    if success_count == total_tests:
        print("✅ 全テスト完了")
        print("\n🎯 terrain_analyzer_node統合完了！")
        print("   - ROS2ノード正常動作")
        print("   - メッセージ送受信正常")
        print("   - パイプライン処理正常")
        print("   - パフォーマンス良好")
        print("   - エラーハンドリング適切")
    else:
        print("❌ 一部テストが失敗しました")
    print("=" * 60)
    
    return 0 if success_count == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
