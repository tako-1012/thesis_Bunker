"""
3D空間のノードクラス
A*アルゴリズムで使用
"""
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class Node3D:
    """3D空間のノード"""
    
    # 位置（ワールド座標またはボクセルインデックス）
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    position: Optional[Tuple[int, int, int]] = None  # 既存コードとの互換性
    
    # コスト
    g: float = float('inf')  # スタートからのコスト
    g_cost: float = float('inf')  # 既存コードとの互換性
    h: float = 0.0          # ゴールまでの推定コスト
    h_cost: float = 0.0     # 既存コードとの互換性
    f: float = 0.0          # 総コスト（TA-A*では拡張される）
    f_cost: float = float('inf')  # Weighted A*用に明示的に属性化
    
    # 親ノード
    parent: Optional['Node3D'] = None
    
    def __post_init__(self):
        """初期化後の処理"""
        # 既存コードとの互換性
        if self.position is not None:
            self.x, self.y, self.z = self.position
        
        # コストの同期
        if self.g != float('inf'):
            self.g_cost = self.g
        if self.h != 0.0:
            self.h_cost = self.h
    
    # 既存のf_costプロパティは削除し、属性として利用
    
    def __eq__(self, other: object) -> bool:
        """位置が同じなら同一ノード"""
        if not isinstance(other, Node3D):
            return False
        
        # 既存コードとの互換性
        if self.position is not None and other.position is not None:
            return self.position == other.position
        
        return abs(self.x - other.x) < 1e-6 and \
               abs(self.y - other.y) < 1e-6 and \
               abs(self.z - other.z) < 1e-6
    
    def __hash__(self) -> int:
        """ハッシュ値（dictのキーとして使用）"""
        if self.position is not None:
            return hash(self.position)
        return hash((round(self.x, 3), round(self.y, 3), round(self.z, 3)))
    
    def __lt__(self, other: 'Node3D') -> bool:
        """優先度キューでの比較（f_costで比較）"""
        return self.f_cost < other.f_cost
    
    def __repr__(self) -> str:
        """文字列表現"""
        if self.position is not None:
            return (f"Node3D(pos={self.position}, "
                    f"g={self.g_cost:.2f}, h={self.h_cost:.2f}, "
                    f"f={self.f_cost:.2f})")
        else:
            return (f"Node3D(pos=({self.x:.2f}, {self.y:.2f}, {self.z:.2f}), "
                    f"g={self.g:.2f}, h={self.h:.2f}, f={self.f:.2f})")