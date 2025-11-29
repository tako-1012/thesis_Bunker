"""
3D経路計画用のコスト計算クラス
地形データ（傾斜、障害物、転倒リスク）を考慮
"""
import numpy as np
from typing import Tuple, Dict, Any

class CostCalculator3D:
    """統合コスト計算（3D版）"""
    
    def __init__(
        self,
        voxel_size: float = 0.1,
        max_slope: float = 30.0,
        weight_distance: float = 1.0,
        weight_slope: float = 3.0,
        weight_obstacle: float = 5.0,
        weight_risk: float = 4.0,
        weight_smoothness: float = 1.0
    ):
        """
        コスト計算の重み設定
        
        Args:
            voxel_size: ボクセルサイズ [m]
            max_slope: 最大許容勾配 [度]
            weight_distance: 距離コストの重み（基準: 1.0）
            weight_slope: 傾斜コストの重み（重要度: 高）
            weight_obstacle: 障害物コストの重み（重要度: 最高）
            weight_risk: 転倒リスクコストの重み（重要度: 高）
            weight_smoothness: 平滑化コストの重み（重要度: 中）
        """
        self.voxel_size = voxel_size
        self.max_slope_deg = max_slope
        self.max_slope_rad = np.deg2rad(max_slope)
        
        self.weight_distance = weight_distance
        self.weight_slope = weight_slope
        self.weight_obstacle = weight_obstacle
        self.weight_risk = weight_risk
        self.weight_smoothness = weight_smoothness
    
    def calculate_move_cost(
        self,
        from_pos: Tuple[float, float, float],
        to_pos: Tuple[float, float, float],
        terrain_data: Any = None
    ) -> float:
        """
        移動コスト計算（地形データを考慮）
        
        Args:
            from_pos: 移動元位置
            to_pos: 移動先位置
            terrain_data: 地形データ
        
        Returns:
            移動コスト
        """
        # 基本距離計算
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dz = to_pos[2] - from_pos[2]
        base_distance = np.sqrt(dx*dx + dy*dy + dz*dz)
        
        # 地形データがない場合は基本距離のみ
        if terrain_data is None:
            return base_distance * self.weight_distance
        
        # 地形情報取得
        slope_deg = self._get_slope_at_position(to_pos, terrain_data)
        is_obstacle = self._is_obstacle_at_position(to_pos, terrain_data)
        risk_score = self._get_risk_at_position(to_pos, terrain_data)
        
        # 統合コスト計算
        total_cost = self.calculate_total_cost(
            base_distance=base_distance,
            slope_deg=slope_deg,
            is_obstacle=is_obstacle,
            risk_score=risk_score
        )
        
        return total_cost
    
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
    
    def _get_slope_at_position(self, pos: Tuple[float, float, float], terrain_data: Any) -> float:
        """指定位置の勾配を取得（簡易実装）"""
        # 簡易実装：周辺の高低差から勾配を推定
        dx = 0.1  # サンプリング距離
        
        # X方向の勾配
        z1 = self._get_height_at_position((pos[0] - dx, pos[1]), terrain_data)
        z2 = self._get_height_at_position((pos[0] + dx, pos[1]), terrain_data)
        slope_x = abs(z2 - z1) / (2 * dx)
        
        # Y方向の勾配
        z3 = self._get_height_at_position((pos[0], pos[1] - dx), terrain_data)
        z4 = self._get_height_at_position((pos[0], pos[1] + dx), terrain_data)
        slope_y = abs(z4 - z3) / (2 * dx)
        
        # 最大勾配
        slope = np.arctan(max(slope_x, slope_y))
        return np.degrees(slope)
    
    def _get_height_at_position(self, pos: Tuple[float, float], terrain_data: Any) -> float:
        """指定位置の高さを取得（簡易実装）"""
        # 簡易実装：ランダムな高さを返す（実際の実装では地形データから取得）
        return np.random.uniform(0.0, 1.0)
    
    def _is_obstacle_at_position(self, pos: Tuple[float, float, float], terrain_data: Any) -> bool:
        """指定位置に障害物があるかチェック（簡易実装）"""
        # 簡易実装：ランダムに障害物を配置
        return np.random.random() < 0.1  # 10%の確率で障害物
    
    def _get_risk_at_position(self, pos: Tuple[float, float, float], terrain_data: Any) -> float:
        """指定位置のリスクスコアを取得（簡易実装）"""
        # 簡易実装：ランダムなリスクスコア
        return np.random.uniform(0.0, 0.5)
