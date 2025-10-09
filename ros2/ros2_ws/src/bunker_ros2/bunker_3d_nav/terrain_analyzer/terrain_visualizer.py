#!/usr/bin/env python3
"""
TerrainVisualizer: Rviz可視化専用クラス
MarkerArray, OccupancyGrid, PointCloud2を使った高度な可視化
"""

import numpy as np
import open3d as o3d
from typing import Dict, Any, Optional
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import OccupancyGrid
from visualization_msgs.msg import MarkerArray, Marker
from geometry_msgs.msg import Point, Vector3, Pose
from std_msgs.msg import Header, ColorRGBA
from sensor_msgs_py import point_cloud2


class TerrainVisualizer:
    """
    Rviz可視化専用クラス
    
    機能:
    - ボクセルマーカー（傾斜別色分け）
    - 2D占有グリッドマップ
    - 色付き点群
    - 統計情報表示
    """
    
    def __init__(self, node):
        """
        初期化
        
        Args:
            node: ROS2ノードインスタンス
        """
        self.node = node
        
        # パブリッシャー
        self.marker_pub = node.create_publisher(
            MarkerArray, 
            '/terrain/markers', 
            10
        )
        
        self.grid_pub = node.create_publisher(
            OccupancyGrid, 
            '/terrain/occupancy', 
            10
        )
        
        self.colored_cloud_pub = node.create_publisher(
            PointCloud2, 
            '/terrain/colored_cloud', 
            10
        )
        
        # 可視化設定
        self.voxel_size = 0.1
        self.max_markers = 1000  # パフォーマンス制限
        self.grid_resolution = 0.2  # 2Dグリッド解像度
        
        # 色設定（傾斜別）
        self.colors = {
            'flat': (0.0, 1.0, 0.0, 0.8),      # 緑: 0-15度
            'gentle': (1.0, 1.0, 0.0, 0.8),    # 黄: 15-25度
            'moderate': (1.0, 0.5, 0.0, 0.8),  # オレンジ: 25-35度
            'steep': (1.0, 0.0, 0.0, 0.8),     # 赤: 35度以上
            'obstacle': (0.5, 0.5, 0.5, 0.8),  # グレー: 障害物
            'unknown': (0.0, 0.0, 1.0, 0.3)    # 青: 未知
        }
        
        self.node.get_logger().info('TerrainVisualizer initialized')
    
    def visualize_terrain(self, voxel_result: Dict, classification: Dict, terrain_analysis: Dict) -> None:
        """
        全ての可視化を実行
        
        Args:
            voxel_result: ボクセル処理結果
            classification: ボクセル分類結果
            terrain_analysis: 地形解析結果
        """
        try:
            # 1. ボクセルマーカー
            self.publish_voxel_markers(voxel_result, classification, terrain_analysis)
            
            # 2. 2D占有グリッド
            self.publish_occupancy_grid(voxel_result, classification)
            
            # 3. 色付き点群
            self.publish_colored_pointcloud(voxel_result, classification, terrain_analysis)
            
            self.node.get_logger().debug('Terrain visualization completed')
            
        except Exception as e:
            self.node.get_logger().error(f'Visualization error: {e}')
    
    def publish_voxel_markers(self, voxel_result: Dict, classification: Dict, terrain_analysis: Dict) -> None:
        """
        ボクセルをMarkerArrayで可視化（傾斜別色分け）
        
        Args:
            voxel_result: ボクセル処理結果
            classification: ボクセル分類結果
            terrain_analysis: 地形解析結果
        """
        try:
            markers = MarkerArray()
            
            # ボクセルグリッドから中心座標を取得
            voxel_grid = voxel_result['voxel_grid']
            centers = self._get_voxel_centers(voxel_grid)
            
            # 傾斜角度を取得
            slope_angles = terrain_analysis.get('slope_angles', np.array([]))
            ground_indices = classification.get('ground_indices', np.array([]))
            obstacle_indices = classification.get('obstacle_indices', np.array([]))
            
            # 地面ボクセルのマーカー
            for i, voxel_idx in enumerate(ground_indices[:self.max_markers]):
                if i < len(slope_angles) and voxel_idx < len(centers):
                    marker = self._create_voxel_marker(
                        centers[voxel_idx], 
                        slope_angles[i], 
                        voxel_idx
                    )
                    markers.markers.append(marker)
            
            # 障害物ボクセルのマーカー
            for i, voxel_idx in enumerate(obstacle_indices[:self.max_markers//2]):
                if voxel_idx < len(centers):
                    marker = self._create_obstacle_marker(
                        centers[voxel_idx], 
                        voxel_idx + len(ground_indices)
                    )
                    markers.markers.append(marker)
            
            # 統計情報マーカー
            stats_marker = self._create_stats_marker(terrain_analysis)
            markers.markers.append(stats_marker)
            
            self.marker_pub.publish(markers)
            
            self.node.get_logger().debug(f'Published {len(markers.markers)} markers')
            
        except Exception as e:
            self.node.get_logger().error(f'Voxel markers error: {e}')
    
    def publish_occupancy_grid(self, voxel_result: Dict, classification: Dict) -> None:
        """
        2D占有グリッドマップ（ナビゲーション用）
        
        Args:
            voxel_result: ボクセル処理結果
            classification: ボクセル分類結果
        """
        try:
            # グリッドマップ作成
            grid_map = self._create_occupancy_grid(voxel_result, classification)
            
            self.grid_pub.publish(grid_map)
            
            self.node.get_logger().debug('Published occupancy grid')
            
        except Exception as e:
            self.node.get_logger().error(f'Occupancy grid error: {e}')
    
    def publish_colored_pointcloud(self, voxel_result: Dict, classification: Dict, terrain_analysis: Dict) -> None:
        """
        色付き点群（高解像度可視化）
        
        Args:
            voxel_result: ボクセル処理結果
            classification: ボクセル分類結果
            terrain_analysis: 地形解析結果
        """
        try:
            # 色付き点群作成
            colored_cloud = self._create_colored_pointcloud(voxel_result, classification, terrain_analysis)
            
            self.colored_cloud_pub.publish(colored_cloud)
            
            self.node.get_logger().debug('Published colored point cloud')
            
        except Exception as e:
            self.node.get_logger().error(f'Colored point cloud error: {e}')
    
    def _get_voxel_centers(self, voxel_grid) -> np.ndarray:
        """ボクセル中心座標を取得"""
        try:
            voxels = voxel_grid.get_voxels()
            centers = []
            
            for voxel in voxels:
                # グリッドインデックスから世界座標に変換
                world_coord = voxel_grid.get_voxel_center_coordinate(voxel.grid_index)
                centers.append([world_coord[0], world_coord[1], world_coord[2]])
            
            return np.array(centers)
            
        except Exception as e:
            self.node.get_logger().error(f'Voxel centers error: {e}')
            return np.array([])
    
    def _create_voxel_marker(self, center: np.ndarray, slope_angle: float, marker_id: int) -> Marker:
        """地面ボクセルマーカーを作成"""
        marker = Marker()
        
        # Header
        marker.header.frame_id = 'map'
        marker.header.stamp = self.node.get_clock().now().to_msg()
        
        # Marker properties
        marker.id = marker_id
        marker.type = Marker.CUBE
        marker.action = Marker.ADD
        
        # Position
        marker.pose.position.x = float(center[0])
        marker.pose.position.y = float(center[1])
        marker.pose.position.z = float(center[2])
        
        # Size
        marker.scale.x = self.voxel_size
        marker.scale.y = self.voxel_size
        marker.scale.z = self.voxel_size
        
        # Color based on slope
        if slope_angle < 15:
            marker.color.r, marker.color.g, marker.color.b, marker.color.a = self.colors['flat']
        elif slope_angle < 25:
            marker.color.r, marker.color.g, marker.color.b, marker.color.a = self.colors['gentle']
        elif slope_angle < 35:
            marker.color.r, marker.color.g, marker.color.b, marker.color.a = self.colors['moderate']
        else:
            marker.color.r, marker.color.g, marker.color.b, marker.color.a = self.colors['steep']
        
        return marker
    
    def _create_obstacle_marker(self, center: np.ndarray, marker_id: int) -> Marker:
        """障害物ボクセルマーカーを作成"""
        marker = Marker()
        
        # Header
        marker.header.frame_id = 'map'
        marker.header.stamp = self.node.get_clock().now().to_msg()
        
        # Marker properties
        marker.id = marker_id
        marker.type = Marker.CUBE
        marker.action = Marker.ADD
        
        # Position
        marker.pose.position.x = float(center[0])
        marker.pose.position.y = float(center[1])
        marker.pose.position.z = float(center[2])
        
        # Size
        marker.scale.x = self.voxel_size
        marker.scale.y = self.voxel_size
        marker.scale.z = self.voxel_size * 2  # 障害物は高く表示
        
        # Color
        marker.color.r, marker.color.g, marker.color.b, marker.color.a = self.colors['obstacle']
        
        return marker
    
    def _create_stats_marker(self, terrain_analysis: Dict) -> Marker:
        """統計情報マーカーを作成"""
        marker = Marker()
        
        # Header
        marker.header.frame_id = 'map'
        marker.header.stamp = self.node.get_clock().now().to_msg()
        
        # Marker properties
        marker.id = 9999  # 特別なID
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD
        
        # Position (右上に表示)
        marker.pose.position.x = 2.0
        marker.pose.position.y = 2.0
        marker.pose.position.z = 1.0
        
        # Size
        marker.scale.z = 0.2
        
        # Color
        marker.color.r = 1.0
        marker.color.g = 1.0
        marker.color.b = 1.0
        marker.color.a = 1.0
        
        # Text content
        stats = terrain_analysis.get('statistics', {})
        text = f"Terrain Stats:\n"
        text += f"Avg Slope: {stats.get('avg_slope', 0):.1f}°\n"
        text += f"Max Slope: {stats.get('max_slope', 0):.1f}°\n"
        text += f"Traversable: {stats.get('traversable_ratio', 0):.1%}\n"
        text += f"Risk Score: {stats.get('avg_risk', 0):.2f}"
        
        marker.text = text
        
        return marker
    
    def _create_occupancy_grid(self, voxel_result: Dict, classification: Dict) -> OccupancyGrid:
        """2D占有グリッドマップを作成"""
        grid = OccupancyGrid()
        
        # Header
        grid.header.frame_id = 'map'
        grid.header.stamp = self.node.get_clock().now().to_msg()
        
        # Grid properties
        grid.info.resolution = self.grid_resolution
        grid.info.width = 200
        grid.info.height = 200
        
        # Origin (中心を原点に)
        grid.info.origin.position.x = -20.0
        grid.info.origin.position.y = -20.0
        grid.info.origin.position.z = 0.0
        
        # Grid data (0: 未知, 50: 走行可能, 100: 障害物)
        grid_data = np.full(200 * 200, 0, dtype=np.int8)
        
        # ボクセルデータを2Dグリッドに投影
        voxel_grid = voxel_result['voxel_grid']
        centers = self._get_voxel_centers(voxel_grid)
        
        ground_indices = classification.get('ground_indices', np.array([]))
        obstacle_indices = classification.get('obstacle_indices', np.array([]))
        
        # 地面ボクセルを走行可能として設定
        for voxel_idx in ground_indices:
            if voxel_idx < len(centers):
                x, y = centers[voxel_idx][0], centers[voxel_idx][1]
                grid_x = int((x + 20.0) / self.grid_resolution)
                grid_y = int((y + 20.0) / self.grid_resolution)
                
                if 0 <= grid_x < 200 and 0 <= grid_y < 200:
                    grid_data[grid_y * 200 + grid_x] = 50
        
        # 障害物ボクセルを障害物として設定
        for voxel_idx in obstacle_indices:
            if voxel_idx < len(centers):
                x, y = centers[voxel_idx][0], centers[voxel_idx][1]
                grid_x = int((x + 20.0) / self.grid_resolution)
                grid_y = int((y + 20.0) / self.grid_resolution)
                
                if 0 <= grid_x < 200 and 0 <= grid_y < 200:
                    grid_data[grid_y * 200 + grid_x] = 100
        
        grid.data = grid_data.tolist()
        
        return grid
    
    def _create_colored_pointcloud(self, voxel_result: Dict, classification: Dict, terrain_analysis: Dict) -> PointCloud2:
        """色付き点群を作成"""
        try:
            # ボクセル中心から点群を作成
            voxel_grid = voxel_result['voxel_grid']
            centers = self._get_voxel_centers(voxel_grid)
            
            if len(centers) == 0:
                return PointCloud2()
            
            # 色情報を準備
            colors = []
            slope_angles = terrain_analysis.get('slope_angles', np.array([]))
            ground_indices = classification.get('ground_indices', np.array([]))
            obstacle_indices = classification.get('obstacle_indices', np.array([]))
            
            # 各点の色を決定
            for i, center in enumerate(centers):
                if i in ground_indices:
                    # 地面点の色（傾斜に応じて）
                    slope_idx = np.where(ground_indices == i)[0]
                    if len(slope_idx) > 0 and slope_idx[0] < len(slope_angles):
                        slope = slope_angles[slope_idx[0]]
                        if slope < 15:
                            colors.append([0, 255, 0])  # 緑
                        elif slope < 25:
                            colors.append([255, 255, 0])  # 黄
                        elif slope < 35:
                            colors.append([255, 128, 0])  # オレンジ
                        else:
                            colors.append([255, 0, 0])  # 赤
                    else:
                        colors.append([0, 255, 0])  # デフォルト緑
                elif i in obstacle_indices:
                    colors.append([128, 128, 128])  # グレー
                else:
                    colors.append([0, 0, 255])  # 青（未知）
            
            # PointCloud2メッセージを作成
            header = Header()
            header.frame_id = 'map'
            header.stamp = self.node.get_clock().now().to_msg()
            
            # 点群データ（XYZ + RGB）
            points = []
            for i, center in enumerate(centers):
                if i < len(colors):
                    points.append([
                        center[0], center[1], center[2],
                        colors[i][0], colors[i][1], colors[i][2]
                    ])
            
            # PointCloud2作成
            cloud = point_cloud2.create_cloud_xyz32(header, centers)
            
            return cloud
            
        except Exception as e:
            self.node.get_logger().error(f'Colored point cloud creation error: {e}')
            return PointCloud2()
    
    def get_visualization_stats(self) -> Dict[str, Any]:
        """可視化統計情報を取得"""
        return {
            'max_markers': self.max_markers,
            'voxel_size': self.voxel_size,
            'grid_resolution': self.grid_resolution,
            'color_schemes': list(self.colors.keys())
        }
