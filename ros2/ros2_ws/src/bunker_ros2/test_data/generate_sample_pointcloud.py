#!/usr/bin/env python3
"""
テスト用点群データ生成ツール
様々な地形パターンの点群データを生成
"""

import numpy as np
import open3d as o3d
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Header
import struct
import argparse
import sys
import os
from typing import List, Tuple, Dict, Any
import json

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor


class PointCloudGenerator:
    """テスト用点群データ生成クラス"""
    
    def __init__(self, resolution: float = 0.1):
        self.resolution = resolution
        self.generator = np.random.RandomState(42)  # 再現可能な乱数
    
    def generate_flat_terrain(self, width: float = 10.0, height: float = 10.0, 
                            point_density: float = 100.0) -> np.ndarray:
        """平坦地形の点群を生成"""
        num_points = int(width * height * point_density)
        
        # 2Dグリッドを生成
        x = np.linspace(0, width, int(width / self.resolution))
        y = np.linspace(0, height, int(height / self.resolution))
        X, Y = np.meshgrid(x, y)
        
        # Z座標は0（平坦）
        Z = np.zeros_like(X)
        
        # ノイズを追加
        noise = self.generator.normal(0, 0.01, Z.shape)
        Z += noise
        
        # 1次元配列に変換
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        
        return points
    
    def generate_sloped_terrain(self, width: float = 10.0, height: float = 10.0,
                               slope_angle: float = 15.0, point_density: float = 100.0) -> np.ndarray:
        """傾斜地形の点群を生成"""
        num_points = int(width * height * point_density)
        
        # 2Dグリッドを生成
        x = np.linspace(0, width, int(width / self.resolution))
        y = np.linspace(0, height, int(height / self.resolution))
        X, Y = np.meshgrid(x, y)
        
        # 傾斜を計算
        slope_rad = np.radians(slope_angle)
        Z = X * np.tan(slope_rad)
        
        # ノイズを追加
        noise = self.generator.normal(0, 0.02, Z.shape)
        Z += noise
        
        # 1次元配列に変換
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        
        return points
    
    def generate_hilly_terrain(self, width: float = 10.0, height: float = 10.0,
                              num_hills: int = 3, max_height: float = 2.0,
                              point_density: float = 100.0) -> np.ndarray:
        """丘陵地形の点群を生成"""
        num_points = int(width * height * point_density)
        
        # 2Dグリッドを生成
        x = np.linspace(0, width, int(width / self.resolution))
        y = np.linspace(0, height, int(height / self.resolution))
        X, Y = np.meshgrid(x, y)
        
        # 複数の丘を生成
        Z = np.zeros_like(X)
        
        for _ in range(num_hills):
            # 丘の中心とサイズをランダムに決定
            center_x = self.generator.uniform(0, width)
            center_y = self.generator.uniform(0, height)
            radius = self.generator.uniform(1.0, 3.0)
            height = self.generator.uniform(0.5, max_height)
            
            # 丘の高さを計算
            distance = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
            hill_height = height * np.exp(-(distance / radius)**2)
            Z += hill_height
        
        # ノイズを追加
        noise = self.generator.normal(0, 0.02, Z.shape)
        Z += noise
        
        # 1次元配列に変換
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        
        return points
    
    def generate_obstacle_terrain(self, width: float = 10.0, height: float = 10.0,
                                 num_obstacles: int = 5, obstacle_height: float = 1.0,
                                 point_density: float = 100.0) -> np.ndarray:
        """障害物地形の点群を生成"""
        num_points = int(width * height * point_density)
        
        # 2Dグリッドを生成
        x = np.linspace(0, width, int(width / self.resolution))
        y = np.linspace(0, height, int(height / self.resolution))
        X, Y = np.meshgrid(x, y)
        
        # 平坦な地面
        Z = np.zeros_like(X)
        
        # 障害物を追加
        for _ in range(num_obstacles):
            # 障害物の位置とサイズをランダムに決定
            center_x = self.generator.uniform(0, width)
            center_y = self.generator.uniform(0, height)
            radius = self.generator.uniform(0.5, 1.5)
            height = self.generator.uniform(0.5, obstacle_height)
            
            # 障害物の高さを計算
            distance = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
            obstacle_mask = distance <= radius
            Z[obstacle_mask] = height
        
        # ノイズを追加
        noise = self.generator.normal(0, 0.01, Z.shape)
        Z += noise
        
        # 1次元配列に変換
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        
        return points
    
    def generate_mixed_terrain(self, width: float = 10.0, height: float = 10.0,
                              point_density: float = 100.0) -> np.ndarray:
        """複合地形の点群を生成"""
        num_points = int(width * height * point_density)
        
        # 2Dグリッドを生成
        x = np.linspace(0, width, int(width / self.resolution))
        y = np.linspace(0, height, int(height / self.resolution))
        X, Y = np.meshgrid(x, y)
        
        # 複合地形を生成
        Z = np.zeros_like(X)
        
        # 緩やかな傾斜
        slope_rad = np.radians(10.0)
        Z += X * np.tan(slope_rad) * 0.3
        
        # 丘を追加
        for _ in range(2):
            center_x = self.generator.uniform(0, width)
            center_y = self.generator.uniform(0, height)
            radius = self.generator.uniform(1.0, 2.0)
            height = self.generator.uniform(0.5, 1.5)
            
            distance = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
            hill_height = height * np.exp(-(distance / radius)**2)
            Z += hill_height
        
        # 障害物を追加
        for _ in range(3):
            center_x = self.generator.uniform(0, width)
            center_y = self.generator.uniform(0, height)
            radius = self.generator.uniform(0.3, 1.0)
            height = self.generator.uniform(0.5, 1.0)
            
            distance = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
            obstacle_mask = distance <= radius
            Z[obstacle_mask] = height
        
        # ノイズを追加
        noise = self.generator.normal(0, 0.02, Z.shape)
        Z += noise
        
        # 1次元配列に変換
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        
        return points
    
    def add_noise(self, points: np.ndarray, noise_level: float = 0.01) -> np.ndarray:
        """点群にノイズを追加"""
        noise = self.generator.normal(0, noise_level, points.shape)
        return points + noise
    
    def filter_points(self, points: np.ndarray, min_z: float = -1.0, 
                     max_z: float = 5.0) -> np.ndarray:
        """点群をフィルタリング"""
        mask = (points[:, 2] >= min_z) & (points[:, 2] <= max_z)
        return points[mask]
    
    def numpy_to_ros_pointcloud2(self, points: np.ndarray, frame_id: str = "map") -> PointCloud2:
        """numpy配列をROS PointCloud2メッセージに変換"""
        header = Header()
        header.frame_id = frame_id
        header.stamp.sec = 0
        header.stamp.nanosec = 0
        
        # 点群データをバイナリ形式に変換
        data = []
        for point in points:
            # x, y, z, intensity (float32)
            data.extend(struct.pack('ffff', point[0], point[1], point[2], 1.0))
        
        pointcloud = PointCloud2()
        pointcloud.header = header
        pointcloud.height = 1
        pointcloud.width = len(points)
        pointcloud.fields = [
            {'name': 'x', 'offset': 0, 'datatype': 7, 'count': 1},
            {'name': 'y', 'offset': 4, 'datatype': 7, 'count': 1},
            {'name': 'z', 'offset': 8, 'datatype': 7, 'count': 1},
            {'name': 'intensity', 'offset': 12, 'datatype': 7, 'count': 1}
        ]
        pointcloud.is_bigendian = False
        pointcloud.point_step = 16
        pointcloud.row_step = pointcloud.point_step * pointcloud.width
        pointcloud.data = bytes(data)
        pointcloud.is_dense = True
        
        return pointcloud
    
    def save_pointcloud(self, points: np.ndarray, filename: str) -> None:
        """点群をファイルに保存"""
        # Open3D形式で保存
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        o3d.io.write_point_cloud(filename, pcd)
        
        # numpy形式でも保存
        np_filename = filename.replace('.pcd', '.npy')
        np.save(np_filename, points)
        
        print(f"Saved pointcloud: {filename} ({len(points)} points)")
    
    def generate_scenario_data(self, scenario: str, **kwargs) -> np.ndarray:
        """シナリオに応じた点群データを生成"""
        if scenario == "flat":
            return self.generate_flat_terrain(**kwargs)
        elif scenario == "sloped":
            return self.generate_sloped_terrain(**kwargs)
        elif scenario == "hilly":
            return self.generate_hilly_terrain(**kwargs)
        elif scenario == "obstacles":
            return self.generate_obstacle_terrain(**kwargs)
        elif scenario == "mixed":
            return self.generate_mixed_terrain(**kwargs)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Generate sample point cloud data')
    parser.add_argument('--scenario', type=str, default='all',
                       choices=['flat', 'sloped', 'hilly', 'obstacles', 'mixed', 'all'],
                       help='Terrain scenario to generate')
    parser.add_argument('--output-dir', type=str, default='./test_data',
                       help='Output directory for generated data')
    parser.add_argument('--resolution', type=float, default=0.1,
                       help='Point cloud resolution')
    parser.add_argument('--width', type=float, default=10.0,
                       help='Terrain width')
    parser.add_argument('--height', type=float, default=10.0,
                       help='Terrain height')
    parser.add_argument('--point-density', type=float, default=100.0,
                       help='Point density per square meter')
    
    args = parser.parse_args()
    
    # 出力ディレクトリ作成
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 生成器を作成
    generator = PointCloudGenerator(resolution=args.resolution)
    
    # シナリオリスト
    scenarios = ['flat', 'sloped', 'hilly', 'obstacles', 'mixed'] if args.scenario == 'all' else [args.scenario]
    
    # 各シナリオのデータを生成
    for scenario in scenarios:
        print(f"Generating {scenario} terrain...")
        
        # シナリオ固有のパラメータ
        scenario_params = {
            'width': args.width,
            'height': args.height,
            'point_density': args.point_density
        }
        
        if scenario == 'sloped':
            scenario_params['slope_angle'] = 15.0
        elif scenario == 'hilly':
            scenario_params['num_hills'] = 3
            scenario_params['max_height'] = 2.0
        elif scenario == 'obstacles':
            scenario_params['num_obstacles'] = 5
            scenario_params['obstacle_height'] = 1.0
        
        # 点群データを生成
        points = generator.generate_scenario_data(scenario, **scenario_params)
        
        # ノイズを追加
        points = generator.add_noise(points, noise_level=0.01)
        
        # 点群をフィルタリング
        points = generator.filter_points(points, min_z=-1.0, max_z=5.0)
        
        # ファイルに保存
        filename = os.path.join(args.output_dir, f'{scenario}_terrain.pcd')
        generator.save_pointcloud(points, filename)
        
        # メタデータを保存
        metadata = {
            'scenario': scenario,
            'num_points': len(points),
            'width': args.width,
            'height': args.height,
            'resolution': args.resolution,
            'point_density': args.point_density,
            'bounds': {
                'min_x': float(np.min(points[:, 0])),
                'max_x': float(np.max(points[:, 0])),
                'min_y': float(np.min(points[:, 1])),
                'max_y': float(np.max(points[:, 1])),
                'min_z': float(np.min(points[:, 2])),
                'max_z': float(np.max(points[:, 2]))
            }
        }
        
        metadata_filename = os.path.join(args.output_dir, f'{scenario}_metadata.json')
        with open(metadata_filename, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Generated {scenario} terrain: {len(points)} points")
        print(f"Bounds: X[{metadata['bounds']['min_x']:.2f}, {metadata['bounds']['max_x']:.2f}], "
              f"Y[{metadata['bounds']['min_y']:.2f}, {metadata['bounds']['max_y']:.2f}], "
              f"Z[{metadata['bounds']['min_z']:.2f}, {metadata['bounds']['max_z']:.2f}]")
    
    print(f"\nAll scenarios generated in: {args.output_dir}")


if __name__ == '__main__':
    main()
