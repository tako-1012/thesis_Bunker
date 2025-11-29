"""
経路計画の基底クラス

全てのプランナーが継承する抽象基底クラス
"""
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional
import numpy as np
import logging
from dataclasses import dataclass

from .planning_result import PlanningResult
from .config import PlannerConfig

logger = logging.getLogger(__name__)

class BasePlanner3D(ABC):
    """3D経路計画の基底クラス"""
    
    def __init__(self, config: PlannerConfig):
        """
        初期化
        
        Args:
            config: プランナー設定
        """
        self.config = config
        self.voxel_size = config.voxel_size
        self.max_slope_deg = config.max_slope_deg
        self.max_slope_rad = np.deg2rad(config.max_slope_deg)
        
        # マップ範囲
        self.min_bound = np.array(config.map_bounds[0])
        self.max_bound = np.array(config.map_bounds[1])
        self.map_size = np.linalg.norm(self.max_bound - self.min_bound)
        
        # ゴール閾値（動的設定）
        self.goal_threshold = self._calculate_goal_threshold()
        
        logger.info(f"{self.__class__.__name__} initialized")
        logger.info(f"  Map size: {self.map_size:.1f}m")
        logger.info(f"  Voxel size: {self.voxel_size}m")
        logger.info(f"  Goal threshold: {self.goal_threshold:.2f}m")
    
    @abstractmethod
    def plan_path(self, start: List[float], goal: List[float], 
                  terrain_data=None, timeout: Optional[float] = None) -> PlanningResult:
        """
        経路計画（抽象メソッド）
        
        Args:
            start: スタート位置 [x, y, z]
            goal: ゴール位置 [x, y, z]
            terrain_data: 地形データ（オプション）
            timeout: タイムアウト [秒]
        
        Returns:
            PlanningResult: 計画結果
        """
        pass
    
    def _calculate_goal_threshold(self) -> float:
        """
        マップサイズに応じたゴール閾値を計算
        
        Returns:
            float: ゴール閾値 [m]
        """
        if self.map_size < 30:
            return 0.3
        elif self.map_size < 80:
            return 0.8
        else:
            return 1.5
    
    def _calculate_timeout(self) -> float:
        """
        マップサイズに応じたタイムアウトを計算
        
        Returns:
            float: タイムアウト [秒]
        """
        if self.map_size < 30:
            return 600   # 10分
        elif self.map_size < 80:
            return 1800  # 30分
        else:
            return 3600  # 60分
    
    def _is_valid_position(self, pos: Tuple[float, float, float]) -> bool:
        """
        位置の妥当性チェック
        
        Args:
            pos: 位置 (x, y, z)
        
        Returns:
            bool: 有効ならTrue
        """
        return (self.min_bound[0] <= pos[0] <= self.max_bound[0] and
                self.min_bound[1] <= pos[1] <= self.max_bound[1] and
                self.min_bound[2] <= pos[2] <= self.max_bound[2])
    
    def _clamp_position(self, pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        位置を有効範囲内にクランプ
        
        Args:
            pos: 位置 (x, y, z)
        
        Returns:
            Tuple[float, float, float]: クランプされた位置
        """
        return (
            np.clip(pos[0], self.min_bound[0], self.max_bound[0]),
            np.clip(pos[1], self.min_bound[1], self.max_bound[1]),
            np.clip(pos[2], self.min_bound[2], self.max_bound[2])
        )
    
    def _calculate_slope(self, pos1: Tuple[float, float, float], 
                        pos2: Tuple[float, float, float]) -> float:
        """
        2点間の勾配を計算
        
        Args:
            pos1: 位置1 (x, y, z)
            pos2: 位置2 (x, y, z)
        
        Returns:
            float: 勾配 [ラジアン]
        """
        dz = pos2[2] - pos1[2]
        dxy = np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
        return abs(np.arctan(dz / dxy)) if dxy > 1e-6 else 0.0
    
    def _is_goal(self, pos: Tuple[float, float, float], 
                 goal: Tuple[float, float, float]) -> bool:
        """
        ゴール判定
        
        Args:
            pos: 現在位置 (x, y, z)
            goal: ゴール位置 (x, y, z)
        
        Returns:
            bool: ゴールならTrue
        """
        dist = np.linalg.norm(np.array(pos) - np.array(goal))
        return dist < self.goal_threshold
    
    def _calculate_path_length(self, path: List[Tuple[float, float, float]]) -> float:
        """
        経路長を計算
        
        Args:
            path: 経路（座標のリスト）
        
        Returns:
            float: 経路長 [m]
        """
        if len(path) < 2:
            return 0.0
        
        length = 0.0
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i + 1])
            length += np.linalg.norm(p2 - p1)
        
        return length
