"""
Module: test_terrain_complexity.py
Purpose: TerrainComplexityEvaluatorの単体テスト・可視化
Author: Kotaro's Research
Dependencies: numpy, open3d

Usage Example:
    python3 test_terrain_complexity.py
"""
import open3d as o3d
import numpy as np
from terrain_complexity_evaluator import TerrainComplexityEvaluator

def create_test_terrain(terrain_type: str) -> o3d.geometry.PointCloud:
    """
    テスト用の地形点群を生成
    terrain_type: "flat", "moderate_slope", "rough"
    """
    n = 1000
    if terrain_type == "flat":
        x = np.random.uniform(-2, 2, n)
        y = np.random.uniform(-2, 2, n)
        z = np.zeros(n)
    elif terrain_type == "moderate_slope":
        x = np.random.uniform(-2, 2, n)
        y = np.random.uniform(-2, 2, n)
        z = 0.2 * x + np.random.normal(0, 0.01, n)
    elif terrain_type == "rough":
        x = np.random.uniform(-2, 2, n)
        y = np.random.uniform(-2, 2, n)
        z = 0.5 * np.sin(2 * x) + 0.5 * np.cos(2 * y) + np.random.normal(0, 0.1, n)
    else:
        raise ValueError(f"Unknown terrain_type: {terrain_type}")
    pts = np.stack([x, y, z], axis=1)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    return pcd

def main():
    evaluator = TerrainComplexityEvaluator(evaluation_radius=5.0, complexity_thresholds=(0.15, 0.55))
    for terrain_type in ["flat", "moderate_slope", "rough"]:
        print(f"\n=== Testing terrain: {terrain_type} ===")
        pcd = create_test_terrain(terrain_type)
        # 内部数値を取得
        slope_var = evaluator.calc_slope_variance(pcd)
        obs_density = evaluator.calc_obstacle_density(pcd)
        score = slope_var * 0.6 + obs_density * 0.4
        complexity = evaluator.evaluate_complexity(pcd)
        print(f"  Slope Variance: {slope_var:.4f}")
        print(f"  Obstacle Density: {obs_density:.4f}")
        print(f"  Score: {score:.4f}")
        print(f"  Complexity: {complexity}")
        evaluator.visualize_complexity(pcd, complexity)

    # 空点群テスト
    print("\n=== Testing empty point cloud ===")
    empty_pcd = o3d.geometry.PointCloud()
    result = evaluator.evaluate_complexity(empty_pcd)
    print(f"判定: {result}")

if __name__ == "__main__":
    main()
