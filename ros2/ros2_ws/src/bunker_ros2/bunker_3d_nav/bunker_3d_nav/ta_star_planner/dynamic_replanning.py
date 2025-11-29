"""
動的再計画

移動障害物や環境変化に対応
"""
import time
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import logging

from .terrain_aware_astar_fast import TerrainAwareAStarFast
from .config import PlannerConfig
from .planning_result import PlanningResult

logger = logging.getLogger(__name__)

@dataclass
class DynamicObstacle:
    """動的障害物"""
    position: Tuple[float, float, float]
    velocity: Tuple[float, float, float]
    radius: float
    timestamp: float

class DynamicReplanner:
    """動的再計画クラス"""
    
    def __init__(self, config: PlannerConfig):
        """初期化"""
        self.planner = TerrainAwareAStarFast(config)
        self.current_path = []
        self.current_position = None
        self.goal = None
        
        # 再計画パラメータ
        self.replan_threshold = 2.0  # 障害物がこの距離内なら再計画
        self.max_replan_frequency = 1.0  # 最低1秒間隔
        self.last_replan_time = 0
        
        self.dynamic_obstacles = []
        
        logger.info("Dynamic Replanner initialized")
    
    def update_obstacles(self, obstacles: List[DynamicObstacle]):
        """
        動的障害物を更新
        
        Args:
            obstacles: 動的障害物リスト
        """
        self.dynamic_obstacles = obstacles
    
    def predict_obstacle_position(self, obstacle: DynamicObstacle, 
                                 time_horizon: float) -> Tuple[float, float, float]:
        """
        障害物の未来位置を予測
        
        Args:
            obstacle: 動的障害物
            time_horizon: 予測時間[秒]
        
        Returns:
            予測位置
        """
        current_pos = np.array(obstacle.position)
        velocity = np.array(obstacle.velocity)
        
        predicted_pos = current_pos + velocity * time_horizon
        
        return tuple(predicted_pos)
    
    def check_path_collision(self, path: List[Tuple], 
                            current_time: float) -> bool:
        """
        経路と動的障害物の衝突をチェック
        
        Args:
            path: 経路
            current_time: 現在時刻
        
        Returns:
            衝突の可能性があればTrue
        """
        if not self.dynamic_obstacles:
            return False
        
        # 経路上の各点で衝突チェック
        robot_speed = 1.0  # m/s（仮定）
        
        for i, waypoint in enumerate(path):
            time_to_waypoint = i * 0.2  # 0.2秒/waypoint（仮定）
            future_time = current_time + time_to_waypoint
            
            for obstacle in self.dynamic_obstacles:
                # 障害物の未来位置を予測
                predicted_pos = self.predict_obstacle_position(
                    obstacle, 
                    future_time - obstacle.timestamp
                )
                
                # 距離チェック
                distance = np.linalg.norm(
                    np.array(waypoint) - np.array(predicted_pos)
                )
                
                safety_margin = obstacle.radius + 1.0  # +1mの安全マージン
                
                if distance < safety_margin:
                    logger.warning(f"Collision predicted at waypoint {i}")
                    return True
        
        return False
    
    def dynamic_planning(self, start: List[float], goal: List[float],
                        max_duration: float = 30.0,
                        update_interval: float = 0.5) -> Dict:
        """
        動的経路計画
        
        環境変化に応じて経路を再計画
        
        Args:
            start: スタート位置
            goal: ゴール位置
            max_duration: 最大実行時間[秒]
            update_interval: 更新間隔[秒]
        
        Returns:
            Dict: 結果
        """
        logger.info("Dynamic planning started")
        
        start_time = time.time()
        self.current_position = start
        self.goal = goal
        
        # 初期経路計画
        result = self.planner.plan_path(start, goal, timeout=10)
        
        if not result.success:
            logger.error("Initial planning failed")
            return {
                'success': False,
                'reason': 'Initial planning failed',
                'replans': 0
            }
        
        self.current_path = result.path
        total_replans = 0
        
        # シミュレーション
        path_index = 0
        
        while time.time() - start_time < max_duration:
            current_time = time.time()
            
            # ゴール到達チェック
            if path_index >= len(self.current_path):
                logger.info("Goal reached!")
                return {
                    'success': True,
                    'replans': total_replans,
                    'total_time': time.time() - start_time,
                    'final_path': self.current_path
                }
            
            # 現在位置更新
            self.current_position = self.current_path[path_index]
            
            # 衝突チェック
            remaining_path = self.current_path[path_index:]
            collision_detected = self.check_path_collision(
                remaining_path, 
                current_time
            )
            
            # 再計画が必要か判定
            need_replan = (
                collision_detected and
                (current_time - self.last_replan_time) > self.max_replan_frequency
            )
            
            if need_replan:
                logger.info(f"Replanning from {self.current_position}")
                
                # 再計画実行
                replan_result = self.planner.plan_path(
                    self.current_position,
                    goal,
                    timeout=5
                )
                
                if replan_result.success:
                    self.current_path = replan_result.path
                    path_index = 0
                    total_replans += 1
                    self.last_replan_time = current_time
                    logger.info(f"Replan #{total_replans} successful")
                else:
                    logger.warning("Replan failed, continuing with original path")
            
            # 次のウェイポイントへ移動
            path_index += 1
            time.sleep(update_interval)
        
        # タイムアウト
        logger.warning("Max duration reached")
        return {
            'success': False,
            'reason': 'Timeout',
            'replans': total_replans,
            'total_time': time.time() - start_time
        }
    
    def adaptive_replanning(self, start: List[float], goal: List[float]) -> Dict:
        """
        適応的再計画
        
        環境の変化度合いに応じて再計画頻度を調整
        
        Returns:
            Dict: 結果
        """
        # 環境の変化を評価
        environment_volatility = self._assess_environment_volatility()
        
        # 変化が大きいほど頻繁に再計画
        if environment_volatility > 0.7:
            self.max_replan_frequency = 0.5  # 0.5秒ごと
            logger.info("High volatility: frequent replanning")
        elif environment_volatility > 0.3:
            self.max_replan_frequency = 1.0  # 1秒ごと
            logger.info("Medium volatility: moderate replanning")
        else:
            self.max_replan_frequency = 2.0  # 2秒ごと
            logger.info("Low volatility: infrequent replanning")
        
        return self.dynamic_planning(start, goal)
    
    def _assess_environment_volatility(self) -> float:
        """
        環境の変化度合いを評価
        
        Returns:
            変化度合い（0-1）
        """
        if not self.dynamic_obstacles:
            return 0.0
        
        # 障害物の平均速度を評価
        avg_speed = np.mean([
            np.linalg.norm(obs.velocity) 
            for obs in self.dynamic_obstacles
        ])
        
        # 正規化（0-2 m/s → 0-1）
        volatility = min(avg_speed / 2.0, 1.0)
        
        return volatility

# 動的環境シミュレータ
class DynamicEnvironmentSimulator:
    """動的環境シミュレータ"""
    
    def __init__(self, num_obstacles: int = 5):
        """初期化"""
        self.num_obstacles = num_obstacles
        self.obstacles = []
        self._initialize_obstacles()
    
    def _initialize_obstacles(self):
        """障害物を初期化"""
        np.random.seed(42)
        
        for i in range(self.num_obstacles):
            obstacle = DynamicObstacle(
                position=(
                    np.random.uniform(-20, 20),
                    np.random.uniform(-20, 20),
                    0.5
                ),
                velocity=(
                    np.random.uniform(-1, 1),
                    np.random.uniform(-1, 1),
                    0
                ),
                radius=1.0,
                timestamp=time.time()
            )
            self.obstacles.append(obstacle)
    
    def update(self, dt: float):
        """障害物を更新"""
        for obstacle in self.obstacles:
            # 位置を更新
            new_pos = (
                obstacle.position[0] + obstacle.velocity[0] * dt,
                obstacle.position[1] + obstacle.velocity[1] * dt,
                obstacle.position[2]
            )
            
            # 境界チェック
            if abs(new_pos[0]) > 25 or abs(new_pos[1]) > 25:
                # 反転
                obstacle.velocity = (
                    -obstacle.velocity[0],
                    -obstacle.velocity[1],
                    0
                )
            else:
                obstacle.position = new_pos
            
            obstacle.timestamp = time.time()
    
    def get_obstacles(self) -> List[DynamicObstacle]:
        """障害物を取得"""
        return self.obstacles

if __name__ == '__main__':
    # テスト
    config = PlannerConfig.medium_scale()
    replanner = DynamicReplanner(config)
    
    # 動的環境シミュレータ
    simulator = DynamicEnvironmentSimulator(num_obstacles=3)
    
    # 障害物を設定
    replanner.update_obstacles(simulator.get_obstacles())
    
    # 動的計画実行
    result = replanner.dynamic_planning(
        start=[0, 0, 0.2],
        goal=[20, 20, 0.2],
        max_duration=10,
        update_interval=0.5
    )
    
    print(f"成功: {result['success']}")
    print(f"再計画回数: {result['replans']}")
    print(f"総時間: {result.get('total_time', 0):.2f}s")


