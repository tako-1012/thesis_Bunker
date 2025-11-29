"""
プランナーのテスト
"""
import unittest
import sys
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))

from astar_planner import AStarPlanner3D
from config import PlannerConfig

class TestAStarPlanner(unittest.TestCase):
    """A*プランナーのテスト"""
    
    def setUp(self):
        """セットアップ"""
        config = PlannerConfig.small_scale()
        self.planner = AStarPlanner3D(config)
    
    def test_simple_path(self):
        """簡単な経路のテスト"""
        start = [0, 0, 0.2]
        goal = [5, 5, 0.2]
        
        result = self.planner.plan_path(start, goal, timeout=60)
        
        self.assertTrue(result.success, "経路計画が失敗しました")
        self.assertGreater(result.path_length, 0, "経路長が0です")
        self.assertGreater(len(result.path), 0, "経路が空です")
    
    def test_invalid_start(self):
        """無効なスタート位置のテスト"""
        start = [100, 100, 100]  # 範囲外
        goal = [0, 0, 0.2]
        
        result = self.planner.plan_path(start, goal, timeout=10)
        
        # クランプされて実行されるはず
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()
