"""
共通の経路計画結果クラス

全アルゴリズムで統一的に使用
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class PlanningResult:
    """
    経路計画の結果（統一フォーマット）
    
    全アルゴリズムが同じフォーマットで結果を返す
    """
    # 必須フィールド（全アルゴリズム共通）
    success: bool
    path: List[Tuple[float, float, float]]
    computation_time: float
    path_length: float
    nodes_explored: int
    
    # オプショナルフィールド
    error_message: str = ""
    
    # TA-A*専用フィールド
    risk_score: float = 0.0
    terrain_adaptations: int = 0
    
    # デバッグ用
    algorithm_name: str = ""
    scenario_id: int = -1
    
    def __post_init__(self):
        """データ検証"""
        if self.success and not self.path:
            raise ValueError("Success is True but path is empty")
        
        if self.success and self.path_length <= 0:
            raise ValueError("Success is True but path_length is zero or negative")
    
    def to_dict(self):
        """辞書に変換"""
        return {
            'success': self.success,
            'path': self.path,
            'computation_time': self.computation_time,
            'path_length': self.path_length,
            'nodes_explored': self.nodes_explored,
            'error_message': self.error_message,
            'risk_score': self.risk_score,
            'terrain_adaptations': self.terrain_adaptations,
            'algorithm_name': self.algorithm_name,
            'scenario_id': self.scenario_id
        }




