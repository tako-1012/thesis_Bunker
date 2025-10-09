#!/usr/bin/env python3
"""
ボクセルグリッド可視化ツール
Rvizでボクセルグリッドと傾斜角度をカラーマップで表示
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point
from std_msgs.msg import ColorRGBA, Header
import numpy as np
import sys
import os
import argparse
from typing import Optional, Dict, Any

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
    from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
except ImportError:
    # Fallback for development
    VoxelGridProcessor = None
    SlopeCalculator = None


class VoxelGridVisualizer(Node):
    """ボクセルグリッドをRvizで可視化するノード"""
    
    def __init__(self, voxel_size: float = 0.1, max_slope: float = 30.0):
        super().__init__('voxel_grid_visualizer')
        
        # パラメータ
        self.voxel_size = voxel_size
        self.max_slope = max_slope
        
        # プロセッサー
        self.voxel_processor = VoxelGridProcessor(voxel_size=voxel_size)
        self.slope_calculator = SlopeCalculator(max_slope_angle=max_slope)
        
        # Subscriber
        self.pointcloud_sub = self.create_subscription(
            PointCloud2,
            '/rtabmap/cloud_map',
            self.pointcloud_callback,
            10
        )
        
        # Publisher
        self.marker_pub = self.create_publisher(
            MarkerArray,
            '/terrain/visualization',
            10
        )
        
        self.get_logger().info('VoxelGridVisualizer initialized')
    
    def pointcloud_callback(self, msg: PointCloud2) -> None:
        """点群データを受信して可視化"""
        try:
            # 点群処理
            terrain_data = self.voxel_processor.process_pointcloud(msg)
            
            if terrain_data['metadata']['point_count'] == 0:
                self.get_logger().warn('Empty point cloud received')
                return
            
            # 傾斜計算
            slope_data = self.slope_calculator.calculate_slopes(
                terrain_data['voxel_grid'],
                terrain_data['normals']
            )
            
            # 可視化マーカー生成
            markers = self.create_visualization_markers(terrain_data, slope_data)
            
            # パブリッシュ
            self.marker_pub.publish(markers)
            
            self.get_logger().info(f'Published {len(markers.markers)} markers')
            
        except Exception as e:
            self.get_logger().error(f'Error processing point cloud: {e}')
    
    def create_visualization_markers(self, terrain_data: Dict[str, Any], 
                                    slope_data: Dict[str, Any]) -> MarkerArray:
        """可視化マーカーを作成"""
        markers = MarkerArray()
        
        # ボクセルグリッドマーカー
        voxel_markers = self.create_voxel_markers(terrain_data)
        markers.markers.extend(voxel_markers)
        
        # 傾斜マーカー
        slope_markers = self.create_slope_markers(slope_data)
        markers.markers.extend(slope_markers)
        
        return markers
    
    def create_voxel_markers(self, terrain_data: Dict[str, Any]) -> list[Marker]:
        """ボクセルグリッドマーカーを作成"""
        markers = []
        voxel_grid = terrain_data['voxel_grid']
        classified_voxels = terrain_data['classified_voxels']
        
        # 地面ボクセル
        ground_marker = self.create_marker_base('ground_voxels')
        ground_marker.type = Marker.CUBE_LIST
        ground_marker.scale.x = self.voxel_size
        ground_marker.scale.y = self.voxel_size
        ground_marker.scale.z = self.voxel_size
        ground_marker.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.7)
        
        # 障害物ボクセル
        obstacle_marker = self.create_marker_base('obstacle_voxels')
        obstacle_marker.type = Marker.CUBE_LIST
        obstacle_marker.scale.x = self.voxel_size
        obstacle_marker.scale.y = self.voxel_size
        obstacle_marker.scale.z = self.voxel_size
        obstacle_marker.color = ColorRGBA(r=1.0, g=0.0, b=0.0, a=0.8)
        
        # ボクセルを分類して追加
        for i in range(voxel_grid.shape[0]):
            for j in range(voxel_grid.shape[1]):
                for k in range(voxel_grid.shape[2]):
                    if classified_voxels[i, j, k] == 1:  # 地面
                        point = Point()
                        point.x = i * self.voxel_size
                        point.y = j * self.voxel_size
                        point.z = k * self.voxel_size
                        ground_marker.points.append(point)
                    elif classified_voxels[i, j, k] == 2:  # 障害物
                        point = Point()
                        point.x = i * self.voxel_size
                        point.y = j * self.voxel_size
                        point.z = k * self.voxel_size
                        obstacle_marker.points.append(point)
        
        markers.extend([ground_marker, obstacle_marker])
        return markers
    
    def create_slope_markers(self, slope_data: Dict[str, Any]) -> list[Marker]:
        """傾斜マーカーを作成"""
        markers = []
        slopes = slope_data['slopes']
        
        # 傾斜角度をカラーマップで表示
        slope_marker = self.create_marker_base('slope_visualization')
        slope_marker.type = Marker.CUBE_LIST
        slope_marker.scale.x = self.voxel_size * 0.8
        slope_marker.scale.y = self.voxel_size * 0.8
        slope_marker.scale.z = self.voxel_size * 0.1
        
        # 傾斜角度に応じて色を設定
        for i, slope in enumerate(slopes):
            if slope > 0:
                point = Point()
                point.x = i * self.voxel_size
                point.y = 0.0
                point.z = 0.0
                slope_marker.points.append(point)
                
                # 傾斜角度に応じた色（0度=緑、30度=赤）
                color = self.slope_to_color(slope)
                slope_marker.colors.append(color)
        
        markers.append(slope_marker)
        return markers
    
    def slope_to_color(self, slope: float) -> ColorRGBA:
        """傾斜角度を色に変換"""
        # 0度（緑）から30度（赤）へのグラデーション
        normalized_slope = min(slope / self.max_slope, 1.0)
        
        if normalized_slope < 0.5:
            # 緑から黄色
            r = normalized_slope * 2.0
            g = 1.0
            b = 0.0
        else:
            # 黄色から赤
            r = 1.0
            g = 2.0 - normalized_slope * 2.0
            b = 0.0
        
        return ColorRGBA(r=r, g=g, b=b, a=0.6)
    
    def create_marker_base(self, name: str) -> Marker:
        """マーカーのベースを作成"""
        marker = Marker()
        marker.header = Header()
        marker.header.frame_id = 'map'
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = name
        marker.id = 0
        marker.action = Marker.ADD
        return marker


def main(args=None):
    """メイン関数"""
    parser = argparse.ArgumentParser(description='VoxelGridVisualizer')
    parser.add_argument('--voxel-size', type=float, default=0.1,
                       help='Voxel size in meters')
    parser.add_argument('--max-slope', type=float, default=30.0,
                       help='Maximum slope angle in degrees')
    
    args = parser.parse_args()
    
    rclpy.init(args=args)
    
    try:
        node = VoxelGridVisualizer(
            voxel_size=args.voxel_size,
            max_slope=args.max_slope
        )
        
        rclpy.spin(node)
        
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
