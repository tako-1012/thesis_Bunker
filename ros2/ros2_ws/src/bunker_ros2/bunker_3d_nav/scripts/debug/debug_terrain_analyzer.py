#!/usr/bin/env python3
"""
地形解析デバッグツール
地形解析の中間結果を出力・可視化
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String, Float32
import numpy as np
import sys
import os
import argparse
import json
from typing import Dict, Any, Optional
import time

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
    from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
except ImportError:
    # Fallback for development
    VoxelGridProcessor = None
    SlopeCalculator = None


class TerrainAnalyzerDebugger(Node):
    """地形解析のデバッグ用ノード"""
    
    def __init__(self, debug_level: int = 1, output_dir: str = './debug_output'):
        super().__init__('terrain_analyzer_debugger')
        
        # パラメータ
        self.debug_level = debug_level
        self.output_dir = output_dir
        self.frame_count = 0
        
        # 出力ディレクトリ作成
        os.makedirs(output_dir, exist_ok=True)
        
        # プロセッサー
        self.voxel_processor = VoxelGridProcessor()
        self.slope_calculator = SlopeCalculator()
        
        # Subscriber
        self.pointcloud_sub = self.create_subscription(
            PointCloud2,
            '/rtabmap/cloud_map',
            self.pointcloud_callback,
            10
        )
        
        # Publisher
        self.debug_pub = self.create_publisher(
            String,
            '/terrain/debug_info',
            10
        )
        
        self.stats_pub = self.create_publisher(
            Float32,
            '/terrain/processing_time',
            10
        )
        
        self.get_logger().info(f'TerrainAnalyzerDebugger initialized (debug_level={debug_level})')
    
    def pointcloud_callback(self, msg: PointCloud2) -> None:
        """点群データを受信してデバッグ処理"""
        start_time = time.time()
        
        try:
            self.frame_count += 1
            self.get_logger().info(f'Processing frame {self.frame_count}')
            
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
            
            # デバッグ情報出力
            self.output_debug_info(terrain_data, slope_data)
            
            # 統計情報出力
            processing_time = time.time() - start_time
            self.output_statistics(terrain_data, slope_data, processing_time)
            
            # ファイル出力
            if self.debug_level >= 2:
                self.save_debug_data(terrain_data, slope_data)
            
            # パブリッシュ
            self.publish_debug_info(terrain_data, slope_data, processing_time)
            
        except Exception as e:
            self.get_logger().error(f'Error in debug processing: {e}')
    
    def output_debug_info(self, terrain_data: Dict[str, Any], 
                         slope_data: Dict[str, Any]) -> None:
        """デバッグ情報をコンソールに出力"""
        if self.debug_level < 1:
            return
        
        print(f"\n=== Frame {self.frame_count} Debug Info ===")
        
        # 点群情報
        point_count = terrain_data['metadata']['point_count']
        print(f"Point count: {point_count}")
        
        # ボクセルグリッド情報
        voxel_grid = terrain_data['voxel_grid']
        print(f"Voxel grid shape: {voxel_grid.shape}")
        print(f"Voxel size: {self.voxel_processor.voxel_size}")
        
        # 分類結果
        classified_voxels = terrain_data['classified_voxels']
        ground_count = np.sum(classified_voxels == 1)
        obstacle_count = np.sum(classified_voxels == 2)
        unknown_count = np.sum(classified_voxels == 255)
        
        print(f"Ground voxels: {ground_count}")
        print(f"Obstacle voxels: {obstacle_count}")
        print(f"Unknown voxels: {unknown_count}")
        
        # 傾斜情報
        slopes = slope_data['slopes']
        if len(slopes) > 0:
            print(f"Slope statistics:")
            print(f"  Average: {np.mean(slopes):.2f} degrees")
            print(f"  Maximum: {np.max(slopes):.2f} degrees")
            print(f"  Minimum: {np.min(slopes):.2f} degrees")
            print(f"  Std dev: {np.std(slopes):.2f} degrees")
        
        # 統計情報
        stats = slope_data['statistics']
        print(f"Traversable ratio: {stats['traversable_ratio']:.3f}")
        
        print("=" * 40)
    
    def output_statistics(self, terrain_data: Dict[str, Any], 
                         slope_data: Dict[str, Any], processing_time: float) -> None:
        """統計情報を出力"""
        if self.debug_level < 1:
            return
        
        stats = {
            'frame': self.frame_count,
            'processing_time': processing_time,
            'point_count': terrain_data['metadata']['point_count'],
            'voxel_count': np.prod(terrain_data['voxel_grid'].shape),
            'ground_voxels': np.sum(terrain_data['classified_voxels'] == 1),
            'obstacle_voxels': np.sum(terrain_data['classified_voxels'] == 2),
            'avg_slope': slope_data['statistics']['avg_slope'],
            'max_slope': slope_data['statistics']['max_slope'],
            'traversable_ratio': slope_data['statistics']['traversable_ratio']
        }
        
        print(f"Statistics: {stats}")
    
    def save_debug_data(self, terrain_data: Dict[str, Any], 
                       slope_data: Dict[str, Any]) -> None:
        """デバッグデータをファイルに保存"""
        if self.debug_level < 2:
            return
        
        # データを保存可能な形式に変換
        debug_data = {
            'frame': self.frame_count,
            'timestamp': time.time(),
            'terrain_data': {
                'voxel_grid_shape': terrain_data['voxel_grid'].shape,
                'classified_voxels_shape': terrain_data['classified_voxels'].shape,
                'point_count': terrain_data['metadata']['point_count']
            },
            'slope_data': {
                'slopes': slope_data['slopes'].tolist(),
                'statistics': slope_data['statistics']
            }
        }
        
        # ファイル保存
        filename = f'debug_frame_{self.frame_count:04d}.json'
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(debug_data, f, indent=2)
            
            if self.debug_level >= 3:
                print(f'Saved debug data: {filepath}')
        except Exception as e:
            self.get_logger().error(f'Error saving debug data: {e}')
    
    def publish_debug_info(self, terrain_data: Dict[str, Any], 
                          slope_data: Dict[str, Any], processing_time: float) -> None:
        """デバッグ情報をパブリッシュ"""
        # デバッグ情報
        debug_info = String()
        debug_info.data = json.dumps({
            'frame': self.frame_count,
            'point_count': terrain_data['metadata']['point_count'],
            'avg_slope': slope_data['statistics']['avg_slope'],
            'max_slope': slope_data['statistics']['max_slope'],
            'traversable_ratio': slope_data['statistics']['traversable_ratio']
        })
        
        self.debug_pub.publish(debug_info)
        
        # 処理時間
        processing_time_msg = Float32()
        processing_time_msg.data = processing_time
        self.stats_pub.publish(processing_time_msg)
    
    def create_summary_report(self) -> None:
        """サマリーレポートを作成"""
        if self.debug_level < 1:
            return
        
        print(f"\n=== Terrain Analysis Summary ===")
        print(f"Total frames processed: {self.frame_count}")
        print(f"Output directory: {self.output_dir}")
        print(f"Debug level: {self.debug_level}")
        print("=" * 40)


def main(args=None):
    """メイン関数"""
    parser = argparse.ArgumentParser(description='TerrainAnalyzerDebugger')
    parser.add_argument('--debug-level', type=int, default=1,
                       help='Debug level (0=none, 1=basic, 2=detailed, 3=verbose)')
    parser.add_argument('--output-dir', type=str, default='./debug_output',
                       help='Output directory for debug data')
    
    args = parser.parse_args()
    
    rclpy.init(args=args)
    
    try:
        node = TerrainAnalyzerDebugger(
            debug_level=args.debug_level,
            output_dir=args.output_dir
        )
        
        rclpy.spin(node)
        
    except KeyboardInterrupt:
        node.create_summary_report()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
