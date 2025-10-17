"""
3D空間のノードクラス
A*アルゴリズムで使用
"""
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class Node3D:
    """3D空間のノード"""
    
    # 位置（ボクセルグリッドのインデックス）
    position: Tuple[int, int, int]
    
    # コスト
    g_cost: float = float('inf')  # スタートからのコスト
    h_cost: float = 0.0           # ゴールまでの推定コスト
    
    # 親ノード
    parent: Optional['Node3D'] = None
    
    @property
    def f_cost(self) -> float:
        """総コスト = g + h"""
        return self.g_cost + self.h_cost
    
    def __eq__(self, other: object) -> bool:
        """位置が同じなら同一ノード"""
        if not isinstance(other, Node3D):
            return False
        return self.position == other.position
    
    def __hash__(self) -> int:
        """ハッシュ値（dictのキーとして使用）"""
        return hash(self.position)
    
    def __lt__(self, other: 'Node3D') -> bool:
        """優先度キューでの比較（f_costで比較）"""
        return self.f_cost < other.f_cost
    
    def __repr__(self) -> str:
        """文字列表現"""
        return (f"Node3D(pos={self.position}, "
                f"g={self.g_cost:.2f}, h={self.h_cost:.2f}, "
                f"f={self.f_cost:.2f})")
