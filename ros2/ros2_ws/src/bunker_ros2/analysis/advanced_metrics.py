"""
高度な評価指標

経路の質を多角的に評価
"""
import numpy as np
from typing import List, Tuple, Dict

class AdvancedMetrics:
    """高度な評価指標クラス"""
    
    @staticmethod
    def calculate_smoothness(path: List[Tuple[float, float, float]]) -> float:
        """
        経路の滑らかさを計算
        
        曲率の変化が小さいほど滑らか
        
        Args:
            path: 経路（座標のリスト）
        
        Returns:
            float: 滑らかさスコア（0-1、大きいほど滑らか）
        """
        if len(path) < 3:
            return 1.0
        
        # 各点での曲率を計算
        curvatures = []
        
        for i in range(1, len(path) - 1):
            p1 = np.array(path[i-1])
            p2 = np.array(path[i])
            p3 = np.array(path[i+1])
            
            # 曲率 = 角度の変化
            v1 = p2 - p1
            v2 = p3 - p2
            
            if np.linalg.norm(v1) < 1e-6 or np.linalg.norm(v2) < 1e-6:
                continue
            
            # コサイン類似度
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = np.arccos(cos_angle)
            
            curvatures.append(angle)
        
        if not curvatures:
            return 1.0
        
        # 曲率の変動が小さいほど滑らか
        avg_curvature = np.mean(curvatures)
        smoothness = 1.0 / (1.0 + avg_curvature)
        
        return smoothness
    
    @staticmethod
    def calculate_energy_efficiency(path: List[Tuple[float, float, float]]) -> float:
        """
        エネルギー効率を計算
        
        高低差の変化が少ないほど効率的
        
        Args:
            path: 経路
        
        Returns:
            float: エネルギー効率スコア
        """
        if len(path) < 2:
            return 0.0
        
        total_elevation_change = 0.0
        horizontal_distance = 0.0
        
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i+1])
            
            # 高低差
            elevation_change = abs(p2[2] - p1[2])
            total_elevation_change += elevation_change
            
            # 水平距離
            horizontal_dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            horizontal_distance += horizontal_dist
        
        if horizontal_distance < 1e-6:
            return 0.0
        
        # 効率 = 水平距離 / (水平距離 + 高低差)
        efficiency = horizontal_distance / (horizontal_distance + total_elevation_change * 2)
        
        return efficiency
    
    @staticmethod
    def calculate_safety_score(path: List[Tuple[float, float, float]],
                               max_slope_deg: float = 30.0) -> float:
        """
        安全性スコアを計算
        
        勾配が緩やかなほど安全
        
        Args:
            path: 経路
            max_slope_deg: 最大許容勾配
        
        Returns:
            float: 安全性スコア（0-1）
        """
        if len(path) < 2:
            return 1.0
        
        max_slope_rad = np.deg2rad(max_slope_deg)
        slopes = []
        
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i+1])
            
            dz = p2[2] - p1[2]
            dxy = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            
            if dxy > 1e-6:
                slope = abs(np.arctan(dz / dxy))
                slopes.append(slope)
        
        if not slopes:
            return 1.0
        
        # 平均勾配が小さいほど安全
        avg_slope = np.mean(slopes)
        safety = 1.0 - (avg_slope / max_slope_rad)
        safety = max(0.0, min(1.0, safety))
        
        return safety
    
    @staticmethod
    def calculate_directness(path: List[Tuple[float, float, float]],
                            start: Tuple[float, float, float],
                            goal: Tuple[float, float, float]) -> float:
        """
        直進性を計算
        
        直線距離に近いほど良い
        
        Args:
            path: 経路
            start: スタート
            goal: ゴール
        
        Returns:
            float: 直進性スコア（0-1）
        """
        # 直線距離
        straight_distance = np.linalg.norm(np.array(goal) - np.array(start))
        
        # 実際の経路長
        path_length = 0.0
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i+1])
            path_length += np.linalg.norm(p2 - p1)
        
        if path_length < 1e-6:
            return 0.0
        
        # 直進性 = 直線距離 / 経路長
        directness = straight_distance / path_length
        
        return directness
    
    @staticmethod
    def calculate_clearance(path: List[Tuple[float, float, float]],
                           obstacle_map: np.ndarray = None) -> float:
        """
        障害物からの余裕を計算
        
        Args:
            path: 経路
            obstacle_map: 障害物マップ
        
        Returns:
            float: クリアランススコア
        """
        # 簡易版: 実装スキップ
        # 本格版では各点から最近傍障害物までの距離を計算
        return 1.0
    
    @staticmethod
    def calculate_overall_quality(path: List[Tuple[float, float, float]],
                                 start: Tuple[float, float, float],
                                 goal: Tuple[float, float, float],
                                 weights: Dict[str, float] = None) -> Dict:
        """
        経路の総合的な質を評価
        
        Args:
            path: 経路
            start: スタート
            goal: ゴール
            weights: 各指標の重み
        
        Returns:
            Dict: 各指標と総合スコア
        """
        if weights is None:
            weights = {
                'smoothness': 0.2,
                'energy_efficiency': 0.2,
                'safety': 0.3,
                'directness': 0.3
            }
        
        metrics = {
            'smoothness': AdvancedMetrics.calculate_smoothness(path),
            'energy_efficiency': AdvancedMetrics.calculate_energy_efficiency(path),
            'safety': AdvancedMetrics.calculate_safety_score(path),
            'directness': AdvancedMetrics.calculate_directness(path, start, goal)
        }
        
        # 加重平均
        overall = sum(metrics[key] * weights[key] for key in weights)
        metrics['overall_quality'] = overall
        
        return metrics

if __name__ == '__main__':
    # テスト
    test_path = [
        (0, 0, 0),
        (1, 1, 0.1),
        (2, 2, 0.2),
        (3, 3, 0.3)
    ]
    
    quality = AdvancedMetrics.calculate_overall_quality(
        test_path,
        start=(0, 0, 0),
        goal=(3, 3, 0.3)
    )
    
    print("経路品質評価:")
    for metric, value in quality.items():
        print(f"  {metric}: {value:.3f}")



