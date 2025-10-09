#!/usr/bin/env python3
"""
VoxelGridProcessor
RTAB-Mapの3D点群からボクセルグリッドを生成し、地形解析を行うモジュール

機能:
- 点群のボクセル化
- 地面/障害物の分類
- 傾斜角度の計算
- 転倒リスクの評価
- ROS2メッセージとの相互変換

実装ステップ:
1. 基本的なボクセル化機能
2. 地面検出アルゴリズム
3. 傾斜計算機能
4. 転倒リスク評価
5. ROS2統合
"""

import numpy as np
import open3d as o3d
from typing import Optional, Tuple, List, Dict, Any
import time
import logging

class VoxelGridProcessor:
    """3D点群からボクセルグリッドを生成し、地形解析を行うクラス"""
    
    def __init__(self, voxel_size: float = 0.1, logger=None):
        """
        初期化
        
        Args:
            voxel_size: ボクセルサイズ [m]
            logger: ロガー（Noneの場合は標準出力）
        """
        self.voxel_size = voxel_size
        
        # 内部状態
        self._voxel_grid: Optional[o3d.geometry.VoxelGrid] = None
        self._voxel_array: Optional[np.ndarray] = None
        self._voxel_coords: Optional[np.ndarray] = None
        self._ground_mask: Optional[np.ndarray] = None
        self._slope_map: Optional[np.ndarray] = None
        
        # ログ設定
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger
            
        self.logger.info(f"VoxelGridProcessor initialized with voxel_size={voxel_size}m")
        
    def process_pointcloud(self, pcd: o3d.geometry.PointCloud) -> Dict[str, Any]:
        """
        点群を処理してボクセルグリッドに変換
        
        Args:
            pcd: Open3D PointCloud
            
        Returns:
            dict: {
                'voxel_grid': o3d.geometry.VoxelGrid,
                'num_voxels': int,
                'bounds': dict,  # min, max, size
                'processing_time': float
            }
        """
        start_time = time.time()
        
        try:
            # 点群の有効性チェック
            if len(pcd.points) == 0:
                raise ValueError("Point cloud is empty")
            
            self.logger.info(f"Processing point cloud with {len(pcd.points)} points")
            
            # ボクセルグリッドの作成
            voxel_grid = self._convert_to_voxel(pcd)
            
            # 境界情報の計算
            bounds = self._calculate_bounds(voxel_grid)
            
            processing_time = time.time() - start_time
            
            # 内部状態の更新
            self._voxel_grid = voxel_grid
            
            result = {
                'voxel_grid': voxel_grid,
                'num_voxels': len(voxel_grid.get_voxels()),
                'bounds': bounds,
                'processing_time': processing_time
            }
            
            self.logger.info(f"Processing completed: {result['num_voxels']} voxels in {processing_time:.3f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing point cloud: {e}")
            raise
    
    def _convert_to_voxel(self, pcd: o3d.geometry.PointCloud) -> o3d.geometry.VoxelGrid:
        """
        点群をボクセルグリッドに変換
        
        Args:
            pcd: Open3D PointCloud
            
        Returns:
            o3d.geometry.VoxelGrid
        """
        voxel_grid = o3d.geometry.VoxelGrid.create_from_point_cloud(pcd, self.voxel_size)
        return voxel_grid
    
    def get_voxel_centers(self, voxel_grid: o3d.geometry.VoxelGrid) -> np.ndarray:
        """
        ボクセルグリッドの中心座標を取得
        
        Args:
            voxel_grid: Open3D VoxelGrid
            
        Returns:
            np.ndarray: Nx3の中心座標配列
        """
        voxels = voxel_grid.get_voxels()
        centers = np.array([voxel_grid.get_voxel_center_coordinate(voxel.grid_index) for voxel in voxels])
        return centers
    
    def _calculate_bounds(self, voxel_grid: o3d.geometry.VoxelGrid) -> Dict[str, Any]:
        """
        ボクセルグリッドの境界情報を計算
        
        Args:
            voxel_grid: Open3D VoxelGrid
            
        Returns:
            dict: 境界情報
        """
        voxels = voxel_grid.get_voxels()
        if len(voxels) == 0:
            return {'min': [0, 0, 0], 'max': [0, 0, 0], 'size': [0, 0, 0]}
        
        centers = self.get_voxel_centers(voxel_grid)
        min_coords = np.min(centers, axis=0)
        max_coords = np.max(centers, axis=0)
        size = max_coords - min_coords
        
        return {
            'min': min_coords.tolist(),
            'max': max_coords.tolist(),
            'size': size.tolist()
        }
    
    def _calculate_normals(self, pcd: o3d.geometry.PointCloud, 
                          radius: float = 0.1, max_nn: int = 30) -> None:
        """
        点群の法線ベクトルを計算（in-place）
        
        Args:
            pcd: 点群（normals属性が追加される）
            radius: 法線推定の半径 [m]
            max_nn: 最大近傍点数
        """
        # 法線推定
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=max_nn)
        )
        
        # 法線の向きを統一（カメラ位置に向ける）
        pcd.orient_normals_towards_camera_location()
        
        self.logger.debug(f"Normals calculated for {len(pcd.points)} points")
    
    def detect_ground_voxels(self, pcd: o3d.geometry.PointCloud,
                           normal_threshold: float = 0.8) -> np.ndarray:
        """
        地面の点を検出
        
        Args:
            pcd: 点群（normalsが計算済みであること）
            normal_threshold: 法線のz成分閾値（0.8 = 約37度）
            
        Returns:
            ground_indices: 地面点のインデックス配列
        """
        # 法線が未計算なら計算
        if not pcd.has_normals():
            self._calculate_normals(pcd)
        
        # 法線のz成分をチェック
        normals = np.asarray(pcd.normals)
        z_components = normals[:, 2]  # z成分
        
        # 閾値以上の点のインデックスを取得
        ground_indices = np.where(z_components >= normal_threshold)[0]
        
        ground_ratio = len(ground_indices) / len(pcd.points) * 100
        self.logger.info(f"Ground detection: {len(ground_indices)}/{len(pcd.points)} points ({ground_ratio:.1f}%)")
        
        return ground_indices
    
    def classify_voxels(self, pcd: o3d.geometry.PointCloud,
                      voxel_grid: o3d.geometry.VoxelGrid) -> Dict[str, Any]:
        """
        ボクセルを地面/障害物/空に分類
        
        Args:
            pcd: 点群（normalsが計算済みであること）
            voxel_grid: ボクセルグリッド
            
        Returns:
            dict: {
                'ground_indices': np.ndarray,
                'obstacle_indices': np.ndarray,
                'ground_ratio': float
            }
        """
        # 地面点を検出
        ground_point_indices = self.detect_ground_voxels(pcd)
        
        # ボクセル情報を取得
        voxels = voxel_grid.get_voxels()
        voxel_indices = np.array([voxel.grid_index for voxel in voxels])
        
        # 各点がどのボクセルに含まれるか判定
        points = np.asarray(pcd.points)
        ground_voxel_indices = []
        obstacle_voxel_indices = []
        
        for i, voxel in enumerate(voxels):
            voxel_center = voxel_grid.get_voxel_center_coordinate(voxel.grid_index)
            
            # このボクセル内の点をチェック
            voxel_points_mask = np.all(np.abs(points - voxel_center) <= self.voxel_size / 2, axis=1)
            voxel_point_indices = np.where(voxel_points_mask)[0]
            
            # 地面点が含まれているかチェック
            if np.any(np.isin(voxel_point_indices, ground_point_indices)):
                ground_voxel_indices.append(i)
            else:
                obstacle_voxel_indices.append(i)
        
        ground_voxel_indices = np.array(ground_voxel_indices)
        obstacle_voxel_indices = np.array(obstacle_voxel_indices)
        
        ground_ratio = len(ground_voxel_indices) / len(voxels) if len(voxels) > 0 else 0.0
        
        self.logger.info(f"Voxel classification: {len(ground_voxel_indices)} ground, {len(obstacle_voxel_indices)} obstacle voxels")
        
        return {
            'ground_indices': ground_voxel_indices,
            'obstacle_indices': obstacle_voxel_indices,
            'ground_ratio': ground_ratio
        }
    
    def calculate_slope_angles(self, voxel_coords: np.ndarray, 
                              ground_mask: np.ndarray) -> np.ndarray:
        """
        地面ボクセルの傾斜角度を計算
        
        実装ステップ:
        1. 地面ボクセルのみを抽出
        2. 各ボクセルの法線ベクトルを取得
        3. 法線ベクトルから傾斜角度を計算
        4. 傾斜マップを生成
        
        参考: examples/05_terrain_analysis.py
        
        Args:
            voxel_coords: ボクセル座標配列
            ground_mask: 地面ボクセルのマスク
            
        Returns:
            傾斜角度の配列 [度]
        """
        # TODO: 実装
        # ステップ1: 地面ボクセルの抽出
        # ground_coords = voxel_coords[ground_mask]
        
        # ステップ2: 法線ベクトルの取得
        # - 各ボクセル周辺の点群から法線推定
        # - 法線ベクトルの正規化
        
        # ステップ3: 傾斜角度の計算
        # - 法線ベクトルと垂直方向（Z軸）の角度
        # - angle = arccos(normal[2])
        # - ラジアンから度に変換
        
        # ステップ4: 傾斜マップの生成
        # slope_map = np.zeros(len(voxel_coords))
        # slope_map[ground_mask] = slope_angles
        
        pass
    
    def evaluate_tip_over_risk(self, voxel_coords: np.ndarray,
                              slope_angles: np.ndarray,
                              ground_mask: np.ndarray) -> np.ndarray:
        """
        転倒リスクを評価
        
        実装ステップ:
        1. ロボットサイズを考慮した安定性評価
        2. 傾斜角度と転倒リスクの関係を計算
        3. リスクスコアの生成
        
        Args:
            voxel_coords: ボクセル座標配列
            slope_angles: 傾斜角度配列
            ground_mask: 地面ボクセルのマスク
            
        Returns:
            転倒リスクスコアの配列
        """
        # TODO: 実装
        # ステップ1: ロボットサイズの考慮
        # - ロボットの重心位置
        # - 支持基底の計算
        
        # ステップ2: 安定性マージンの計算
        # - 傾斜角度に基づく安定性評価
        # - 転倒リスクの計算
        
        # ステップ3: リスクスコアの生成
        # - 0.0 (安全) から 1.0 (危険) の範囲
        # - 閾値との比較
        
        pass
    
    def voxel_grid_to_3d_array(self, voxel_grid: o3d.geometry.VoxelGrid) -> Tuple[np.ndarray, np.ndarray]:
        """
        VoxelGridを3D配列に変換
        
        実装ステップ:
        1. ボクセルのインデックス範囲を計算
        2. 3D配列のサイズを決定
        3. ボクセルを3D配列にマッピング
        4. 最小インデックスを返却
        
        参考: examples/04_voxel_grid.py
        
        Args:
            voxel_grid: 入力VoxelGrid
            
        Returns:
            (3D配列, 最小インデックス)
        """
        # TODO: 実装
        # ステップ1: ボクセル情報の取得
        # voxels = voxel_grid.get_voxels()
        # voxel_indices = np.array([voxel.grid_index for voxel in voxels])
        
        # ステップ2: インデックス範囲の計算
        # min_indices = np.min(voxel_indices, axis=0)
        # max_indices = np.max(voxel_indices, axis=0)
        
        # ステップ3: 3D配列の作成
        # array_shape = max_indices - min_indices + 1
        # voxel_array = np.zeros(array_shape, dtype=bool)
        
        # ステップ4: ボクセルのマッピング
        # for voxel in voxels:
        #     relative_index = voxel.grid_index - min_indices
        #     voxel_array[tuple(relative_index)] = True
        
        pass
    
    def get_terrain_statistics(self) -> Dict[str, Any]:
        """
        地形統計情報を取得
        
        Returns:
            地形統計の辞書
        """
        # TODO: 実装
        # 統計情報の計算
        # - 総ボクセル数
        # - 地面ボクセル数
        # - 平均傾斜角度
        # - 最大傾斜角度
        # - 転倒リスクの分布
        
        pass
    
    def visualize_results(self, show_normals: bool = False, 
                         show_slopes: bool = True) -> None:
        """
        処理結果を可視化
        
        Args:
            show_normals: 法線ベクトルを表示するか
            show_slopes: 傾斜情報を表示するか
        """
        # TODO: 実装
        # 可視化の実装
        # - ボクセルグリッドの表示
        # - 地面/障害物の色分け
        # - 傾斜角度の色分け
        # - 法線ベクトルの表示（オプション）
        
        pass
    
    def save_results(self, output_dir: str) -> None:
        """
        処理結果をファイルに保存
        
        Args:
            output_dir: 出力ディレクトリ
        """
        # TODO: 実装
        # ファイル保存の実装
        # - ボクセルグリッドの保存
        # - 傾斜マップの保存
        # - 統計情報の保存
        # - 可視化画像の保存
        
        pass

# テスト用の関数
def test_voxel_grid_processor():
    """VoxelGridProcessorのテスト関数"""
    print("VoxelGridProcessorのテストを開始...")
    
    # テスト用の点群データを生成
    # 参考: examples/01_basic_pointcloud.py
    sphere = o3d.geometry.TriangleMesh.create_sphere(radius=1.0)
    sphere.compute_vertex_normals()
    test_pcd = sphere.sample_points_uniformly(number_of_points=1000)
    
    # VoxelGridProcessorのインスタンス作成
    processor = VoxelGridProcessor(voxel_size=0.1)
    
    # 処理の実行
    try:
        results = processor.process_pointcloud(test_pcd)
        print("テスト完了: 処理が正常に実行されました")
        return True
    except Exception as e:
        print(f"テスト失敗: {e}")
        return False

if __name__ == "__main__":
    # テスト実行
    test_voxel_grid_processor()