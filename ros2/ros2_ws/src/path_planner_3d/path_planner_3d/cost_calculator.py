"""
経路計画用のコスト計算クラス
地形データ（傾斜、障害物、転倒リスク）を考慮
"""
import numpy as np
from typing import Tuple

class CostCalculator:
    """統合コスト計算"""
    
    def __init__(
        self,
        weight_distance: float = 1.0,
        weight_slope: float = 3.0,
        weight_obstacle: float = 5.0,
        weight_risk: float = 4.0,
        weight_smoothness: float = 1.0
    ):
        """
        コスト計算の重み設定
        
        Args:
            weight_distance: 距離コストの重み（基準: 1.0）
            weight_slope: 傾斜コストの重み（重要度: 高）
            weight_obstacle: 障害物コストの重み（重要度: 最高）
            weight_risk: 転倒リスクコストの重み（重要度: 高）
            weight_smoothness: 平滑化コストの重み（重要度: 中）
        """
        self.weight_distance = weight_distance
        self.weight_slope = weight_slope
        self.weight_obstacle = weight_obstacle
        self.weight_risk = weight_risk
        self.weight_smoothness = weight_smoothness
    
    def calculate_total_cost(
        self,
        base_distance: float,
        slope_deg: float = 0.0,
        is_obstacle: bool = False,
        risk_score: float = 0.0,
        turn_angle: float = 0.0
    ) -> float:
        """
        統合コスト計算
        
        total_cost = distance + slope + obstacle + risk + smoothness
        
        Args:
            base_distance: 基本移動距離（メートル）
            slope_deg: 傾斜角度（度、-90~90）
            is_obstacle: 障害物フラグ
            risk_score: 転倒リスクスコア（0-1）
            turn_angle: 旋回角度（ラジアン）
        
        Returns:
            総コスト（低いほど良い）
        """
        # 各コスト成分を計算
        distance_cost = base_distance * self.weight_distance
        slope_cost = self._calculate_slope_cost(slope_deg) * self.weight_slope
        obstacle_cost = self._calculate_obstacle_cost(is_obstacle) * self.weight_obstacle
        risk_cost = self._calculate_risk_cost(risk_score) * self.weight_risk
        smoothness_cost = self._calculate_smoothness_cost(turn_angle) * self.weight_smoothness
        
        # 統合コスト
        total_cost = (distance_cost + slope_cost + obstacle_cost + 
                     risk_cost + smoothness_cost)
        
        return total_cost
    
    def _calculate_slope_cost(self, slope_deg: float) -> float:
        """
        傾斜コスト計算
        
        傾斜の大きさに応じて非線形に増加:
        - 0-15度: コストなし（平地と同等）
        - 15-25度: 線形増加（0→1）
        - 25-35度: 急増（1→5）
        - 35度以上: 実質走行不可（1000）
        
        Args:
            slope_deg: 傾斜角度（度）
        
        Returns:
            傾斜コスト
        """
        slope_deg = abs(slope_deg)  # 絶対値を使用（登り・下り両方）
        
        if slope_deg < 15.0:
            # 緩やか: コストなし
            return 0.0
        elif slope_deg < 25.0:
            # 中程度: 線形増加
            return (slope_deg - 15.0) / 10.0
        elif slope_deg < 35.0:
            # 急: 急激に増加
            return 1.0 + (slope_deg - 25.0) / 2.5
        else:
            # 非常に急: 走行不可
            return 1000.0
    
    def _calculate_obstacle_cost(self, is_obstacle: bool) -> float:
        """
        障害物コスト計算
        
        Args:
            is_obstacle: 障害物フラグ
        
        Returns:
            障害物コスト（障害物なし: 0、あり: 1000）
        """
        return 1000.0 if is_obstacle else 0.0
    
    def _calculate_risk_cost(self, risk_score: float) -> float:
        """
        転倒リスクコスト計算
        
        リスクスコア（0-1）を0-10のコストに変換
        
        Args:
            risk_score: リスクスコア（0: 安全、1: 非常に危険）
        
        Returns:
            リスクコスト
        """
        return risk_score * 10.0
    
    def _calculate_smoothness_cost(self, turn_angle: float) -> float:
        """
        平滑化コスト計算（急旋回ペナルティ）
        
        急な方向転換を避けるためのペナルティ
        
        Args:
            turn_angle: 旋回角度（ラジアン）
        
        Returns:
            平滑化コスト
        """
        return abs(turn_angle)
    
    def get_traversability(self, slope_deg: float, risk_score: float) -> bool:
        """
        走行可能性判定
        
        Args:
            slope_deg: 傾斜角度（度）
            risk_score: リスクスコア（0-1）
        
        Returns:
            走行可能ならTrue、不可ならFalse
        """
        # 傾斜35度以上は走行不可
        if abs(slope_deg) >= 35.0:
            return False
        
        # リスクスコア0.8以上は走行不可
        if risk_score >= 0.8:
            return False
        
        return True
    
    def set_weights(
        self,
        distance: float = None,
        slope: float = None,
        obstacle: float = None,
        risk: float = None,
        smoothness: float = None
    ) -> None:
        """
        重みパラメータの動的設定
        
        Args:
            distance: 距離コストの重み
            slope: 傾斜コストの重み
            obstacle: 障害物コストの重み
            risk: リスクコストの重み
            smoothness: 平滑化コストの重み
        """
        if distance is not None:
            self.weight_distance = distance
        if slope is not None:
            self.weight_slope = slope
        if obstacle is not None:
            self.weight_obstacle = obstacle
        if risk is not None:
            self.weight_risk = risk
        if smoothness is not None:
            self.weight_smoothness = smoothness
