#!/usr/bin/env python3
"""
Lazy TA-A* Wrapper for Algorithm Comparison System

既存のアルゴリズム比較システムに統合するためのラッパー
"""
import sys
from pathlib import Path

# lazy_tastarをインポート
sys.path.insert(0, str(Path(__file__).parent))
from lazy_tastar import LazyTAstar, PlanningResult

class LazyTAstarWrapper:
    """
    Lazy TA-A*を既存のアルゴリズム比較システムに統合するためのラッパー
    """
    
    def __init__(self, grid_size: tuple = (100, 100, 20), 
                 voxel_size: float = 0.1, 
                 max_slope: float = 30.0):
        """
        初期化
        
        Args:
            grid_size: グリッドサイズ (x, y, z)
            voxel_size: ボクセルサイズ
            max_slope: 最大傾斜角度
        """
        self.grid_size = grid_size
        self.voxel_size = voxel_size
        self.max_slope = max_slope
        
        # Lazy TA-A*インスタンスを作成
        # マップサイズを十分大きく設定（テストケースに対応）
        map_size = 50.0  # 固定で50mに設定（テストケースの範囲をカバー）
        self.planner = LazyTAstar(
            voxel_size=voxel_size,
            map_size=map_size,
            goal_threshold=voxel_size * 2  # ゴール閾値をボクセルサイズの2倍に
        )
        
        print(f"Lazy TA-A* Wrapper initialized:")
        print(f"  Grid size: {grid_size}")
        print(f"  Voxel size: {voxel_size}m")
        print(f"  Map size: {map_size}m")
        print(f"  Max slope: {max_slope}°")
    
    def plan_path(self, start: list, goal: list, 
                  terrain_data: dict = None, 
                  timeout: float = 300.0) -> dict:
        """
        経路計画実行
        
        Args:
            start: スタート位置 [x, y, z]
            goal: ゴール位置 [x, y, z]
            terrain_data: 地形データ（未使用、互換性のため）
            timeout: タイムアウト[秒]
            
        Returns:
            結果辞書（既存システム互換）
        """
        try:
            # Lazy TA-A*で経路計画
            result: PlanningResult = self.planner.plan_path(start, goal, timeout)
            
            # 既存システム互換の形式に変換
            return {
                'success': result.success,
                'path': result.path,
                'computation_time': result.computation_time,
                'path_length': result.path_length,
                'nodes_explored': result.nodes_explored,
                'algorithm_name': result.algorithm_name,
                'phase_used': result.phase_used,
                'error_message': result.error_message,
                'memory_usage': 0.0,  # メモリ使用量は計測しない
                'risk_score': 0.0,   # リスクスコア（簡易版）
                'terrain_adaptations': result.phase_used - 1  # Phase-1が地形適応回数
            }
            
        except Exception as e:
            return {
                'success': False,
                'path': [],
                'computation_time': 0.0,
                'path_length': 0.0,
                'nodes_explored': 0,
                'algorithm_name': 'Lazy TA-A*',
                'phase_used': 0,
                'error_message': str(e),
                'memory_usage': 0.0,
                'risk_score': 0.0,
                'terrain_adaptations': 0
            }
    
    def get_algorithm_name(self) -> str:
        """アルゴリズム名を取得"""
        return "Lazy TA-A*"
    
    def get_parameters(self) -> dict:
        """パラメータを取得"""
        return {
            'grid_size': self.grid_size,
            'voxel_size': self.voxel_size,
            'max_slope': self.max_slope
        }

# テスト用
if __name__ == '__main__':
    print("="*70)
    print("Lazy TA-A* Wrapper Test")
    print("="*70)
    
    # ラッパーを作成
    wrapper = LazyTAstarWrapper(
        grid_size=(50, 50, 20),
        voxel_size=0.1,
        max_slope=30.0
    )
    
    # テストケース
    test_cases = [
        {
            'name': 'Short Test',
            'start': [0, 0, 0.2],
            'goal': [5, 5, 0.2]
        },
        {
            'name': 'Medium Test',
            'start': [0, 0, 0.2],
            'goal': [10, 10, 0.2]
        },
        {
            'name': 'Long Test',
            'start': [-10, -10, 0.2],
            'goal': [10, 10, 0.2]
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*50}")
        print(f"Test: {test['name']}")
        print(f"Start: {test['start']}")
        print(f"Goal:  {test['goal']}")
        print(f"{'='*50}")
        
        result = wrapper.plan_path(test['start'], test['goal'])
        
        if result['success']:
            print(f"✅ SUCCESS")
            print(f"  Algorithm: {result['algorithm_name']}")
            print(f"  Phase: {result['phase_used']}")
            print(f"  Time: {result['computation_time']:.3f}s")
            print(f"  Path length: {result['path_length']:.2f}m")
            print(f"  Nodes explored: {result['nodes_explored']}")
            print(f"  Terrain adaptations: {result['terrain_adaptations']}")
        else:
            print(f"❌ FAILED")
            print(f"  Error: {result['error_message']}")
    
    print(f"\n{'='*70}")
    print("Wrapper test complete!")
    print(f"{'='*70}")
