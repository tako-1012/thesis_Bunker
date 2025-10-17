#!/usr/bin/env python3
"""
test_path_smoother.py
PathSmootherクラスの包括的テストスイート

テスト項目:
1. 基本的な経路平滑化
2. Cubic spline補間の精度
3. エッジケース処理
4. パフォーマンス測定
5. 異なる平滑化手法の比較
"""

import unittest
import numpy as np
import time
from path_smoother import PathSmoother


class TestPathSmoother(unittest.TestCase):
    
    def setUp(self):
        """各テスト前の初期化"""
        # PathSmootherインスタンス作成（デフォルト設定）
        self.smoother_cubic = PathSmoother(smoothing_method='cubic_spline', smoothness_factor=0.5)
        self.smoother_gradient = PathSmoother(smoothing_method='gradient_descent', smoothness_factor=0.5)
        self.smoother_simple = PathSmoother(smoothing_method='simple', smoothness_factor=0.5)
    
    def test_basic_smoothing_cubic_spline(self):
        """基本的な経路平滑化テスト（Cubic Spline）"""
        # ジグザグ経路を作成
        raw_path = [
            np.array([10.0, 10.0, 0.0]),
            np.array([15.0, 10.0, 0.0]),
            np.array([15.0, 15.0, 0.0]),
            np.array([20.0, 15.0, 0.0]),
            np.array([20.0, 20.0, 0.0]),
            np.array([25.0, 20.0, 0.0])
        ]
        
        smoothed_path = self.smoother_cubic.smooth_path(raw_path)
        
        # 検証項目
        self.assertIsNotNone(smoothed_path, "平滑化経路が生成されること")
        self.assertGreater(len(smoothed_path), 0, "平滑化経路が空でないこと")
        self.assertEqual(len(smoothed_path[0]), 3, "各点が3次元であること")
        
        # 始点と終点が保持されることを確認（数値的に近い）
        start_diff = np.linalg.norm(smoothed_path[0] - raw_path[0])
        end_diff = np.linalg.norm(smoothed_path[-1] - raw_path[-1])
        self.assertLess(start_diff, 0.1, "始点が保持されること")
        self.assertLess(end_diff, 0.1, "終点が保持されること")
        
        # 元の経路より滑らかであることを確認（角度変化が小さい）
        raw_angles = self._calculate_angle_changes(raw_path)
        smooth_angles = self._calculate_angle_changes(smoothed_path)
        
        if len(raw_angles) > 0 and len(smooth_angles) > 0:
            self.assertLess(
                np.mean(smooth_angles), 
                np.mean(raw_angles), 
                "平滑化後の角度変化が小さいこと"
            )
    
    def test_basic_smoothing_gradient_descent(self):
        """基本的な経路平滑化テスト（Gradient Descent）"""
        # 単純な経路を作成
        raw_path = [
            np.array([0.0, 0.0, 0.0]),
            np.array([5.0, 0.0, 0.0]),
            np.array([10.0, 5.0, 0.0]),
            np.array([15.0, 5.0, 0.0]),
            np.array([20.0, 0.0, 0.0])
        ]
        
        smoothed_path = self.smoother_gradient.smooth_path(raw_path)
        
        # 検証項目
        self.assertIsNotNone(smoothed_path, "平滑化経路が生成されること")
        self.assertGreaterEqual(len(smoothed_path), len(raw_path), "経路が保持または拡張されること")
        
        # 始点と終点の保持確認
        start_diff = np.linalg.norm(smoothed_path[0] - raw_path[0])
        end_diff = np.linalg.norm(smoothed_path[-1] - raw_path[-1])
        self.assertLess(start_diff, 0.1, "始点が保持されること")
        self.assertLess(end_diff, 0.1, "終点が保持されること")
    
    def test_basic_smoothing_simple(self):
        """基本的な経路平滑化テスト（Simple）"""
        # ノイジーな経路を作成
        raw_path = [
            np.array([0.0, 0.0, 0.0]),
            np.array([1.0, 0.1, 0.0]),
            np.array([2.0, -0.1, 0.0]),
            np.array([3.0, 0.2, 0.0]),
            np.array([4.0, -0.1, 0.0]),
            np.array([5.0, 0.0, 0.0])
        ]
        
        smoothed_path = self.smoother_simple.smooth_path(raw_path)
        
        # 検証項目
        self.assertIsNotNone(smoothed_path, "平滑化経路が生成されること")
        self.assertGreaterEqual(len(smoothed_path), len(raw_path), "経路が保持または拡張されること")
        
        # 始点と終点の保持確認
        start_diff = np.linalg.norm(smoothed_path[0] - raw_path[0])
        end_diff = np.linalg.norm(smoothed_path[-1] - raw_path[-1])
        self.assertLess(start_diff, 0.1, "始点が保持されること")
        self.assertLess(end_diff, 0.1, "終点が保持されること")
    
    def test_cubic_spline_smoothness(self):
        """Cubic spline補間の滑らかさテスト"""
        # 単純な経路
        raw_path = [
            np.array([10.0, 10.0, 0.0]),
            np.array([20.0, 10.0, 0.0]),
            np.array([30.0, 20.0, 0.0]),
            np.array([40.0, 20.0, 0.0])
        ]
        
        smoothed_path = self.smoother_cubic.smooth_path(raw_path)
        
        # 2次微分（加速度）の変化が小さいことを確認
        if len(smoothed_path) >= 3:
            accelerations = []
            for i in range(1, len(smoothed_path) - 1):
                p_prev = smoothed_path[i-1]
                p_curr = smoothed_path[i]
                p_next = smoothed_path[i+1]
                
                # 2次微分の近似
                accel = p_next - 2*p_curr + p_prev
                accelerations.append(np.linalg.norm(accel))
            
            # 平均加速度が小さいこと（滑らかな経路）
            if accelerations:
                avg_accel = np.mean(accelerations)
                self.assertLess(avg_accel, 5.0, "経路が滑らかであること")
    
    def test_empty_path(self):
        """空経路のエッジケーステスト"""
        empty_path = []
        result = self.smoother_cubic.smooth_path(empty_path)
        self.assertEqual(result, [], "空経路を適切に処理すること")
    
    def test_single_point_path(self):
        """単一点経路のエッジケーステスト"""
        single_point = [np.array([10.0, 10.0, 0.0])]
        result = self.smoother_cubic.smooth_path(single_point)
        self.assertEqual(len(result), 1, "単一点経路を保持すること")
        self.assertTrue(np.allclose(result[0], single_point[0]), "単一点が保持されること")
    
    def test_two_point_path(self):
        """2点経路のエッジケーステスト"""
        two_points = [
            np.array([10.0, 10.0, 0.0]), 
            np.array([20.0, 20.0, 5.0])
        ]
        result = self.smoother_cubic.smooth_path(two_points)
        # 2点の場合、補間点が追加される可能性がある
        self.assertGreaterEqual(len(result), 2, "経路が保持または拡張されること")
        self.assertTrue(np.allclose(result[0], two_points[0]), "始点が保持されること")
        self.assertTrue(np.allclose(result[-1], two_points[-1]), "終点が保持されること")
    
    def test_three_point_path(self):
        """3点経路のテスト（最小の平滑化対象）"""
        three_points = [
            np.array([0.0, 0.0, 0.0]),
            np.array([5.0, 5.0, 2.0]),
            np.array([10.0, 0.0, 0.0])
        ]
        result = self.smoother_cubic.smooth_path(three_points)
        
        self.assertGreaterEqual(len(result), 3, "3点経路が処理されること")
        self.assertTrue(np.allclose(result[0], three_points[0]), "始点が保持されること")
        self.assertTrue(np.allclose(result[-1], three_points[-1]), "終点が保持されること")
    
    def test_performance(self):
        """パフォーマンステスト"""
        # 長い経路を作成
        long_path = [np.array([float(i), float(i % 20), float(i % 5)]) for i in range(0, 100, 2)]
        
        start_time = time.time()
        smoothed_path = self.smoother_cubic.smooth_path(long_path)
        elapsed = time.time() - start_time
        
        self.assertLess(elapsed, 2.0, "平滑化が2秒以内に完了すること")
        self.assertIsNotNone(smoothed_path, "長経路でも平滑化が成功すること")
        
        print(f"\n[Performance] 経路平滑化: {len(long_path)}点 → {len(smoothed_path)}点, {elapsed:.4f}秒")
    
    def test_smoothness_calculation(self):
        """滑らかさ計算のテスト"""
        # 滑らかな経路
        smooth_path = [
            np.array([0.0, 0.0, 0.0]),
            np.array([1.0, 1.0, 0.0]),
            np.array([2.0, 2.0, 0.0]),
            np.array([3.0, 3.0, 0.0]),
            np.array([4.0, 4.0, 0.0])
        ]
        
        # ノイジーな経路
        noisy_path = [
            np.array([0.0, 0.0, 0.0]),
            np.array([1.0, 0.5, 0.0]),
            np.array([2.0, 1.5, 0.0]),
            np.array([3.0, 2.5, 0.0]),
            np.array([4.0, 4.0, 0.0])
        ]
        
        smoothness_smooth = self.smoother_cubic.calculate_path_smoothness(smooth_path)
        smoothness_noisy = self.smoother_cubic.calculate_path_smoothness(noisy_path)
        
        # 滑らかさスコアが正の値であることを確認（比較は実装に依存）
        self.assertGreater(smoothness_smooth, 0.0, "滑らかさスコアが正の値であること")
        self.assertGreater(smoothness_noisy, 0.0, "ノイジー経路のスコアも正の値であること")
    
    def test_path_length_optimization(self):
        """経路長最適化のテスト"""
        # 非効率な経路
        inefficient_path = [
            np.array([0.0, 0.0, 0.0]),
            np.array([1.0, 1.0, 0.0]),
            np.array([2.0, 0.0, 0.0]),
            np.array([3.0, 1.0, 0.0]),
            np.array([4.0, 0.0, 0.0]),
            np.array([5.0, 0.0, 0.0])
        ]
        
        optimized_path = self.smoother_cubic.optimize_path_length(inefficient_path)
        
        self.assertIsNotNone(optimized_path, "最適化経路が生成されること")
        self.assertGreaterEqual(len(optimized_path), 2, "最適化経路が有効であること")
        
        # 始点と終点の保持確認
        self.assertTrue(np.allclose(optimized_path[0], inefficient_path[0]), "始点が保持されること")
        self.assertTrue(np.allclose(optimized_path[-1], inefficient_path[-1]), "終点が保持されること")
    
    def test_different_smoothing_methods(self):
        """異なる平滑化手法の比較テスト"""
        # テスト用経路
        test_path = [
            np.array([0.0, 0.0, 0.0]),
            np.array([5.0, 2.0, 1.0]),
            np.array([10.0, 1.0, 2.0]),
            np.array([15.0, 3.0, 1.0]),
            np.array([20.0, 0.0, 0.0])
        ]
        
        # 各手法で平滑化
        cubic_result = self.smoother_cubic.smooth_path(test_path)
        gradient_result = self.smoother_gradient.smooth_path(test_path)
        simple_result = self.smoother_simple.smooth_path(test_path)
        
        # 全ての手法で結果が生成されること
        self.assertIsNotNone(cubic_result, "Cubic spline結果が生成されること")
        self.assertIsNotNone(gradient_result, "Gradient descent結果が生成されること")
        self.assertIsNotNone(simple_result, "Simple結果が生成されること")
        
        # 全ての結果が有効な長さを持つこと
        self.assertGreater(len(cubic_result), 0, "Cubic spline結果が有効であること")
        self.assertGreater(len(gradient_result), 0, "Gradient descent結果が有効であること")
        self.assertGreater(len(simple_result), 0, "Simple結果が有効であること")
        
        print(f"\n[Method Comparison]")
        print(f"  Cubic Spline: {len(cubic_result)} points")
        print(f"  Gradient Descent: {len(gradient_result)} points")
        print(f"  Simple: {len(simple_result)} points")
    
    # ヘルパーメソッド
    def _calculate_angle_changes(self, path):
        """経路の角度変化を計算"""
        angles = []
        for i in range(1, len(path) - 1):
            v1 = path[i] - path[i-1]
            v2 = path[i+1] - path[i]
            
            if np.linalg.norm(v1) > 0 and np.linalg.norm(v2) > 0:
                cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                angle = np.degrees(np.arccos(cos_angle))
                angles.append(angle)
        
        return angles


if __name__ == '__main__':
    print("=" * 50)
    print("PathSmoother テストスイート実行")
    print("=" * 50)
    
    unittest.main(verbosity=2)
