#!/usr/bin/env python3
"""
TerrainInfoメッセージの使用例とテストコード
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Header
from geometry_msgs.msg import Point, Vector3
from bunker_ros2.msg import TerrainInfo, VoxelGrid3D
import numpy as np
import time


class TerrainInfoExample(Node):
    """TerrainInfoメッセージの使用例"""
    
    def __init__(self):
        super().__init__('terrain_info_example')
        
        # Publisher
        self.terrain_info_pub = self.create_publisher(
            TerrainInfo,
            '/terrain/terrain_info',
            10
        )
        
        self.voxel_grid_pub = self.create_publisher(
            VoxelGrid3D,
            '/terrain/voxel_grid',
            10
        )
        
        # Timer
        self.timer = self.create_timer(1.0, self.publish_terrain_info)
        
        self.get_logger().info('TerrainInfo Example Node started')
    
    def create_sample_terrain_info(self) -> TerrainInfo:
        """サンプルのTerrainInfoメッセージを作成"""
        msg = TerrainInfo()
        
        # Header
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        # 統計情報（サンプルデータ）
        msg.avg_slope = 15.5
        msg.max_slope = 35.2
        msg.min_slope = 0.1
        msg.traversable_ratio = 0.75
        
        # ボクセル情報
        msg.total_voxels = 1000
        msg.ground_voxels = 750
        msg.obstacle_voxels = 250
        
        # リスク情報
        msg.avg_risk = 0.3
        msg.max_risk = 0.8
        
        # コスト情報
        msg.avg_cost = 2.5
        msg.impassable_ratio = 0.1
        
        # 処理情報
        msg.processing_time = 0.05
        msg.point_count = 5000
        
        return msg
    
    def create_sample_voxel_grid(self) -> VoxelGrid3D:
        """サンプルのVoxelGrid3Dメッセージを作成"""
        msg = VoxelGrid3D()
        
        # Header
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        # ボクセルグリッド情報
        msg.voxel_size = 0.1
        msg.num_voxels = 100
        
        # 境界情報
        msg.min_bound = Point(x=-5.0, y=-5.0, z=-1.0)
        msg.max_bound = Point(x=5.0, y=5.0, z=1.0)
        msg.size = Vector3(x=10.0, y=10.0, z=2.0)
        
        # ボクセルデータ（サンプル）
        msg.voxel_indices = [0, 0, 0, 1, 0, 0, 2, 0, 0]  # x, y, z
        msg.voxel_types = [1, 1, 2]  # 地面, 地面, 障害物
        msg.voxel_slopes = [5.0, 15.0, 0.0]  # 度
        msg.voxel_risks = [0.1, 0.4, 0.0]  # 0-1
        msg.voxel_costs = [1.2, 2.5, 999.0]  # コスト
        
        return msg
    
    def publish_terrain_info(self):
        """TerrainInfoメッセージをパブリッシュ"""
        try:
            # TerrainInfoメッセージ作成・送信
            terrain_msg = self.create_sample_terrain_info()
            self.terrain_info_pub.publish(terrain_msg)
            
            # VoxelGrid3Dメッセージ作成・送信
            voxel_msg = self.create_sample_voxel_grid()
            self.voxel_grid_pub.publish(voxel_msg)
            
            self.get_logger().info(
                f'Published: avg_slope={terrain_msg.avg_slope:.1f}°, '
                f'traversable={terrain_msg.traversable_ratio:.1%}, '
                f'voxels={terrain_msg.total_voxels}'
            )
            
        except Exception as e:
            self.get_logger().error(f'Error publishing terrain info: {e}')


def test_terrain_info_message():
    """TerrainInfoメッセージのテスト"""
    print("=" * 60)
    print("TerrainInfoメッセージテスト")
    print("=" * 60)
    
    # メッセージ作成テスト
    try:
        msg = TerrainInfo()
        msg.header = Header()
        msg.header.stamp.sec = int(time.time())
        msg.header.frame_id = 'map'
        
        # データ設定
        msg.avg_slope = 20.5
        msg.max_slope = 45.0
        msg.min_slope = 0.0
        msg.traversable_ratio = 0.8
        msg.total_voxels = 1500
        msg.ground_voxels = 1200
        msg.obstacle_voxels = 300
        msg.avg_risk = 0.25
        msg.max_risk = 0.9
        msg.avg_cost = 3.2
        msg.impassable_ratio = 0.05
        msg.processing_time = 0.08
        msg.point_count = 8000
        
        print("✅ TerrainInfoメッセージ作成成功")
        print(f"   平均傾斜: {msg.avg_slope}°")
        print(f"   走行可能率: {msg.traversable_ratio:.1%}")
        print(f"   総ボクセル数: {msg.total_voxels}")
        print(f"   処理時間: {msg.processing_time}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ TerrainInfoメッセージテスト失敗: {e}")
        return False


def test_voxel_grid_message():
    """VoxelGrid3Dメッセージのテスト"""
    print("\n" + "=" * 60)
    print("VoxelGrid3Dメッセージテスト")
    print("=" * 60)
    
    try:
        msg = VoxelGrid3D()
        msg.header = Header()
        msg.header.stamp.sec = int(time.time())
        msg.header.frame_id = 'map'
        
        # ボクセルグリッド情報
        msg.voxel_size = 0.15
        msg.num_voxels = 200
        
        # 境界情報
        msg.min_bound = Point(x=-3.0, y=-3.0, z=-0.5)
        msg.max_bound = Point(x=3.0, y=3.0, z=0.5)
        msg.size = Vector3(x=6.0, y=6.0, z=1.0)
        
        # ボクセルデータ（サンプル）
        voxel_data = []
        voxel_types = []
        voxel_slopes = []
        voxel_risks = []
        voxel_costs = []
        
        for i in range(10):
            voxel_data.extend([i, 0, 0])  # x, y, z
            voxel_types.append(1 if i < 7 else 2)  # 地面 or 障害物
            voxel_slopes.append(float(i * 5))  # 0, 5, 10, ...度
            voxel_risks.append(min(1.0, i * 0.1))  # 0.0, 0.1, 0.2, ...
            voxel_costs.append(1.0 + i * 0.5)  # 1.0, 1.5, 2.0, ...
        
        msg.voxel_indices = voxel_data
        msg.voxel_types = voxel_types
        msg.voxel_slopes = voxel_slopes
        msg.voxel_risks = voxel_risks
        msg.voxel_costs = voxel_costs
        
        print("✅ VoxelGrid3Dメッセージ作成成功")
        print(f"   ボクセルサイズ: {msg.voxel_size}m")
        print(f"   ボクセル数: {msg.num_voxels}")
        print(f"   境界: [{msg.min_bound.x}, {msg.min_bound.y}, {msg.min_bound.z}] - "
              f"[{msg.max_bound.x}, {msg.max_bound.y}, {msg.max_bound.z}]")
        print(f"   データ点数: {len(msg.voxel_indices) // 3}")
        
        return True
        
    except Exception as e:
        print(f"❌ VoxelGrid3Dメッセージテスト失敗: {e}")
        return False


def main():
    """メインテスト"""
    print("\n" + "=" * 60)
    print("カスタムメッセージテスト")
    print("=" * 60 + "\n")
    
    success_count = 0
    total_tests = 2
    
    # TerrainInfoテスト
    if test_terrain_info_message():
        success_count += 1
    
    # VoxelGrid3Dテスト
    if test_voxel_grid_message():
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"テスト結果: {success_count}/{total_tests} 成功")
    if success_count == total_tests:
        print("✅ 全テスト完了")
        print("\n🎯 カスタムメッセージの準備完了！")
        print("   - TerrainInfo: 地形統計情報")
        print("   - VoxelGrid3D: 3Dボクセルデータ")
        print("   - Week 2でのROS2統合準備完了")
    else:
        print("❌ 一部テストが失敗しました")
    print("=" * 60)
    
    return 0 if success_count == total_tests else 1


if __name__ == "__main__":
    # ROS2ノードのテスト
    try:
        rclpy.init()
        node = TerrainInfoExample()
        
        print("ROS2ノードテスト開始...")
        print("Ctrl+Cで終了")
        
        rclpy.spin(node)
        
    except KeyboardInterrupt:
        print("\nROS2ノードテスト終了")
    except Exception as e:
        print(f"ROS2ノードテストエラー: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()
    
    # メッセージテスト
    exit(main())
