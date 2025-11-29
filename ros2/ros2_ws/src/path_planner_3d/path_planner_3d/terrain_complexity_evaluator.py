"""
Module: terrain_complexity_evaluator.py
Purpose: 点群データから地形の複雑度を評価
Author: Kotaro's Research
Dependencies: numpy, open3d

Usage Example:
    import open3d as o3d
    from terrain_complexity_evaluator import TerrainComplexityEvaluator
    pcd = o3d.geometry.PointCloud()
    # ...点群を生成/読み込み...
    evaluator = TerrainComplexityEvaluator(evaluation_radius=5.0)
    result = evaluator.evaluate_complexity(pcd)
    print(result)  # "SIMPLE", "MODERATE", "COMPLEX"
"""
import numpy as np
import open3d as o3d
from typing import Tuple, Optional

class TerrainComplexityEvaluator:
    """
    地形点群から複雑度（SIMPLE, MODERATE, COMPLEX）を判定するクラス
    """
    def __init__(self, evaluation_radius: float = 5.0, complexity_thresholds: Tuple[float, float] = (0.3, 0.7)):
        self.evaluation_radius = evaluation_radius
        self.complexity_thresholds = complexity_thresholds

    def evaluate_complexity(self, point_cloud: o3d.geometry.PointCloud) -> str:
        """
        地形点群の複雑度を評価
        Returns: "SIMPLE", "MODERATE", "COMPLEX"
        """
        if point_cloud.is_empty():
            return "SIMPLE"  # 空なら安全側でSIMPLE
        slope_var = self.calc_slope_variance(point_cloud)
        obstacle_dens = self.calc_obstacle_density(point_cloud)
        score = self.compute_complexity_score(slope_var, obstacle_dens)
        th_simple, th_moderate = self.complexity_thresholds
        if score < th_simple:
            return "SIMPLE"
        elif score < th_moderate:
            return "MODERATE"
        else:
            return "COMPLEX"

    def calc_slope_variance(self, point_cloud: o3d.geometry.PointCloud) -> float:
        """
        法線ベクトルから傾斜角の分散を計算（0.0~1.0に正規化）
        """
        if point_cloud.is_empty():
            return 0.0
        pcd = point_cloud.voxel_down_sample(voxel_size=0.1)
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=30))
        normals = np.asarray(pcd.normals)
        # 法線z成分から傾斜角（degree）
        slope_deg = np.degrees(np.arccos(np.clip(normals[:, 2], -1.0, 1.0)))
        var = np.var(slope_deg)
        # 0~90度の範囲で正規化
        return np.clip(var / (90.0 ** 2), 0.0, 1.0)

    def calc_obstacle_density(self, point_cloud: o3d.geometry.PointCloud) -> float:
        """
        傾斜30度以上 or 段差0.3m以上を障害物とみなして密度計算（0.0~1.0）
        """
        if point_cloud.is_empty():
            return 0.0
        pcd = point_cloud.voxel_down_sample(voxel_size=0.1)
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=30))
        points = np.asarray(pcd.points)
        normals = np.asarray(pcd.normals)
        slope_deg = np.degrees(np.arccos(np.clip(normals[:, 2], -1.0, 1.0)))
        # 傾斜30度以上
        steep_mask = slope_deg >= 30.0
        # 段差0.3m以上（近傍点とのz差）
        z = points[:, 2]
        dz = np.abs(z[:, None] - z[None, :])
        # 近傍点（半径0.3m以内）
        dist = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
        neighbor_mask = (dist < 0.3) & (dist > 0)
        large_step = (dz > 0.3) & neighbor_mask
        step_mask = np.any(large_step, axis=1)
        # 障害物判定
        obstacle_mask = steep_mask | step_mask
        density = np.sum(obstacle_mask) / len(points)
        return float(np.clip(density, 0.0, 1.0))

    def compute_complexity_score(self, slope_var: float, obstacle_dens: float) -> float:
        """
        総合スコア = slope_var * 0.6 + obstacle_dens * 0.4
        """
        return slope_var * 0.6 + obstacle_dens * 0.4

    def visualize_complexity(self, point_cloud: o3d.geometry.PointCloud, complexity: Optional[str] = None) -> None:
        """
        デバッグ用: 傾斜角に応じて色分けして可視化
        赤: 急傾斜, 緑: 緩斜面, 青: 平坦
        """
        if point_cloud.is_empty():
            print("[visualize_complexity] Empty point cloud.")
            return
        pcd = point_cloud.voxel_down_sample(voxel_size=0.1)
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=30))
        normals = np.asarray(pcd.normals)
        slope_deg = np.degrees(np.arccos(np.clip(normals[:, 2], -1.0, 1.0)))
        # 色付け: 赤(>30), 緑(10~30), 青(<10)
        colors = np.zeros((len(slope_deg), 3))
        colors[slope_deg < 10] = [0, 0, 1]      # 青
        colors[(slope_deg >= 10) & (slope_deg < 30)] = [0, 1, 0]  # 緑
        colors[slope_deg >= 30] = [1, 0, 0]     # 赤
        pcd.colors = o3d.utility.Vector3dVector(colors)
        title = f"Terrain Complexity: {complexity}" if complexity else "Terrain Complexity"
        o3d.visualization.draw_geometries([pcd], window_name=title)
