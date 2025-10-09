#!/usr/bin/env python3
"""
SlopeCalculator: 傾斜角度と転倒リスクの計算

VoxelGridProcessorの出力を受け取り、各ボクセルの傾斜角度と
ロボットの転倒リスクを計算する。
"""
import numpy as np
import open3d as o3d
from typing import Dict, Tuple, Optional
import logging


class SlopeCalculator:
    """傾斜角度と転倒リスクを計算するクラス"""
    
    def __init__(self, 
                 robot_width: float = 0.6,
                 robot_length: float = 0.8,
                 max_safe_slope: float = 25.0,
                 logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            robot_width: ロボットの幅 [m]
            robot_length: ロボットの長さ [m]
            max_safe_slope: 安全な最大傾斜角度 [度]
            logger: ロガー
        """
        self.robot_width = robot_width
        self.robot_length = robot_length
        self.max_safe_slope = max_safe_slope
        
        # ロガーの設定
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger
            
        self.logger.info(f"SlopeCalculator initialized: robot({robot_width}x{robot_length}m), max_slope={max_safe_slope}°")
    
    def calculate_slope_angles(self, 
                               pcd: o3d.geometry.PointCloud,
                               ground_indices: np.ndarray) -> np.ndarray:
        """
        地面点の傾斜角度を計算
        
        Args:
            pcd: 点群（normalsが計算済み）
            ground_indices: 地面点のインデックス
            
        Returns:
            slope_angles: 各地面点の傾斜角度 [度]
        """
        try:
            # 法線が未計算ならエラー
            if not pcd.has_normals():
                raise ValueError("Point cloud must have normals calculated")
            
            # 地面点の法線ベクトルを取得
            normals = np.asarray(pcd.normals)
            ground_normals = normals[ground_indices]
            
            # 法線のz成分からアークコサインで角度計算
            # angle = 90 - arccos(normal_z) * 180/pi
            z_components = np.abs(ground_normals[:, 2])  # 絶対値を取る
            z_components = np.clip(z_components, 0.0, 1.0)  # 0-1の範囲にクリップ
            
            slope_angles = 90.0 - np.arccos(z_components) * 180.0 / np.pi
            
            # 0-90度の範囲にクリップ
            slope_angles = np.clip(slope_angles, 0.0, 90.0)
            
            # 統計情報をログ出力
            avg_slope = np.mean(slope_angles)
            max_slope = np.max(slope_angles)
            min_slope = np.min(slope_angles)
            
            self.logger.info(f"Slope calculation: avg={avg_slope:.1f}°, max={max_slope:.1f}°, min={min_slope:.1f}°")
            
            return slope_angles
            
        except Exception as e:
            self.logger.error(f"Error calculating slope angles: {e}")
            raise
    
    def classify_slopes(self, slope_angles: np.ndarray) -> Dict[str, np.ndarray]:
        """
        傾斜を分類
        
        Args:
            slope_angles: 傾斜角度配列 [度]
            
        Returns:
            dict: {
                'flat': 0-10度のインデックス,
                'gentle': 10-20度のインデックス,
                'moderate': 20-30度のインデックス,
                'steep': 30度以上のインデックス
            }
        """
        try:
            # 各範囲のインデックスを取得
            flat_indices = np.where(slope_angles < 10.0)[0]
            gentle_indices = np.where((slope_angles >= 10.0) & (slope_angles < 20.0))[0]
            moderate_indices = np.where((slope_angles >= 20.0) & (slope_angles < 30.0))[0]
            steep_indices = np.where(slope_angles >= 30.0)[0]
            
            # 各カテゴリの割合をログ出力
            total = len(slope_angles)
            flat_ratio = len(flat_indices) / total * 100
            gentle_ratio = len(gentle_indices) / total * 100
            moderate_ratio = len(moderate_indices) / total * 100
            steep_ratio = len(steep_indices) / total * 100
            
            self.logger.info(f"Slope classification: flat={flat_ratio:.1f}%, gentle={gentle_ratio:.1f}%, "
                           f"moderate={moderate_ratio:.1f}%, steep={steep_ratio:.1f}%")
            
            return {
                'flat': flat_indices,
                'gentle': gentle_indices,
                'moderate': moderate_indices,
                'steep': steep_indices
            }
            
        except Exception as e:
            self.logger.error(f"Error classifying slopes: {e}")
            raise
    
    def calculate_stability_risk(self,
                                 pcd: o3d.geometry.PointCloud,
                                 ground_indices: np.ndarray,
                                 slope_angles: np.ndarray) -> np.ndarray:
        """
        転倒リスクを計算
        
        Args:
            pcd: 点群
            ground_indices: 地面点のインデックス
            slope_angles: 傾斜角度 [度]
            
        Returns:
            risk_scores: 転倒リスクスコア [0-1]
                        0: 安全, 1: 非常に危険
        """
        try:
            # 基本リスク: slope_angle / max_safe_slope
            basic_risk = slope_angles / self.max_safe_slope
            
            # 追加リスク要因の計算
            points = np.asarray(pcd.points)
            ground_points = points[ground_indices]
            
            # 横転リスク: ロボット幅に対する傾斜の影響
            # より幅広いロボットは横転しにくい
            lateral_risk_factor = 1.0 - (self.robot_width / 1.0)  # 1m基準で正規化
            lateral_risk = basic_risk * lateral_risk_factor
            
            # 前後転リスク: ロボット長さに対する傾斜の影響
            # より長いロボットは前後転しにくい
            longitudinal_risk_factor = 1.0 - (self.robot_length / 1.0)  # 1m基準で正規化
            longitudinal_risk = basic_risk * longitudinal_risk_factor
            
            # 総合リスク = 基本リスク * (1 + 追加要因)
            total_risk = basic_risk * (1.0 + lateral_risk + longitudinal_risk)
            
            # 0-1の範囲にクリップ
            risk_scores = np.clip(total_risk, 0.0, 1.0)
            
            # リスク統計をログ出力
            avg_risk = np.mean(risk_scores)
            max_risk = np.max(risk_scores)
            high_risk_count = np.sum(risk_scores > 0.7)
            
            self.logger.info(f"Stability risk: avg={avg_risk:.3f}, max={max_risk:.3f}, "
                           f"high_risk_points={high_risk_count}")
            
            return risk_scores
            
        except Exception as e:
            self.logger.error(f"Error calculating stability risk: {e}")
            raise
    
    def get_traversability_cost(self, 
                                slope_angles: np.ndarray,
                                risk_scores: np.ndarray) -> np.ndarray:
        """
        走行コストを計算
        
        Args:
            slope_angles: 傾斜角度 [度]
            risk_scores: 転倒リスク [0-1]
            
        Returns:
            costs: 走行コスト [1.0-inf]
                   1.0: 平坦で安全
                   inf: 走行不可
        """
        try:
            # 基本コスト = 1.0 + (slope_angle / 10.0)
            basic_cost = 1.0 + (slope_angles / 10.0)
            
            # リスクペナルティ = exp(risk_score * 5)
            risk_penalty = np.exp(risk_scores * 5.0)
            
            # 総コスト = 基本コスト * リスクペナルティ
            total_cost = basic_cost * risk_penalty
            
            # slope > max_safe_slope の場合 = inf
            unsafe_mask = slope_angles > self.max_safe_slope
            total_cost[unsafe_mask] = np.inf
            
            # コスト統計をログ出力
            safe_costs = total_cost[~unsafe_mask]
            if len(safe_costs) > 0:
                avg_cost = np.mean(safe_costs)
                max_cost = np.max(safe_costs)
                unsafe_count = np.sum(unsafe_mask)
                
                self.logger.info(f"Traversability cost: avg={avg_cost:.2f}, max={max_cost:.2f}, "
                               f"unsafe_points={unsafe_count}")
            
            return total_cost
            
        except Exception as e:
            self.logger.error(f"Error calculating traversability cost: {e}")
            raise
    
    def analyze_terrain(self,
                       pcd: o3d.geometry.PointCloud,
                       ground_indices: np.ndarray) -> Dict:
        """
        地形の総合分析
        
        Args:
            pcd: 点群（normalsが計算済み）
            ground_indices: 地面点のインデックス
            
        Returns:
            dict: {
                'slope_angles': np.ndarray,
                'slope_classification': dict,
                'risk_scores': np.ndarray,
                'traversability_costs': np.ndarray,
                'statistics': dict
            }
        """
        try:
            self.logger.info(f"Starting terrain analysis for {len(ground_indices)} ground points")
            
            # 1. 傾斜角度計算
            slope_angles = self.calculate_slope_angles(pcd, ground_indices)
            
            # 2. 傾斜分類
            slope_classification = self.classify_slopes(slope_angles)
            
            # 3. 転倒リスク計算
            risk_scores = self.calculate_stability_risk(pcd, ground_indices, slope_angles)
            
            # 4. 走行コスト計算
            traversability_costs = self.get_traversability_cost(slope_angles, risk_scores)
            
            # 5. 統計情報をまとめる
            statistics = {
                'avg_slope': float(np.mean(slope_angles)),
                'max_slope': float(np.max(slope_angles)),
                'min_slope': float(np.min(slope_angles)),
                'avg_risk': float(np.mean(risk_scores)),
                'max_risk': float(np.max(risk_scores)),
                'avg_cost': float(np.mean(traversability_costs[traversability_costs != np.inf])),
                'unsafe_ratio': float(np.sum(traversability_costs == np.inf) / len(traversability_costs)),
                'total_points': len(ground_indices)
            }
            
            self.logger.info(f"Terrain analysis completed: avg_slope={statistics['avg_slope']:.1f}°, "
                           f"unsafe_ratio={statistics['unsafe_ratio']*100:.1f}%")
            
            # 6. 全結果を辞書で返す
            return {
                'slope_angles': slope_angles,
                'slope_classification': slope_classification,
                'risk_scores': risk_scores,
                'traversability_costs': traversability_costs,
                'statistics': statistics
            }
            
        except Exception as e:
            self.logger.error(f"Error in terrain analysis: {e}")
            raise


# テスト用の関数
def test_slope_calculator():
    """SlopeCalculatorのテスト関数"""
    print("SlopeCalculatorのテストを開始...")
    
    # テスト用の点群データを生成
    # 地面（平面）
    ground = o3d.geometry.TriangleMesh.create_box(width=5.0, height=0.1, depth=5.0)
    ground.translate([-2.5, -0.05, -2.5])
    ground_pcd = ground.sample_points_uniformly(number_of_points=500)
    
    # 法線計算
    ground_pcd.estimate_normals()
    ground_pcd.orient_normals_towards_camera_location()
    
    # SlopeCalculatorのインスタンス作成
    calculator = SlopeCalculator(robot_width=0.6, robot_length=0.8, max_safe_slope=25.0)
    
    # 全地面点を対象とする
    ground_indices = np.arange(len(ground_pcd.points))
    
    # 処理の実行
    try:
        results = calculator.analyze_terrain(ground_pcd, ground_indices)
        print("テスト完了: 処理が正常に実行されました")
        print(f"統計情報: {results['statistics']}")
        return True
    except Exception as e:
        print(f"テスト失敗: {e}")
        return False


if __name__ == "__main__":
    # テスト実行
    test_slope_calculator()