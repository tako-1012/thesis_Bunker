"""
実験クラスのテスト
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'experiments'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))

from terrain_experiment import TerrainExperiment

class TestTerrainExperiment(unittest.TestCase):
    """地形実験のテスト"""
    
    def setUp(self):
        """セットアップ"""
        self.experiment = TerrainExperiment(
            terrain_type="test_terrain",
            num_scenarios=2,  # 小規模テスト
            output_dir="../results"
        )
    
    def test_experiment_initialization(self):
        """実験初期化のテスト"""
        self.assertEqual(self.experiment.terrain_type, "test_terrain")
        self.assertEqual(self.experiment.num_scenarios, 2)
        self.assertIn('A*', self.experiment.algorithms)
    
    def test_scenario_generation(self):
        """シナリオ生成のテスト"""
        scenarios = self.experiment._generate_scenarios()
        self.assertGreaterEqual(len(scenarios), 1, "シナリオが生成されていません")
        
        for scenario in scenarios:
            self.assertIn('start', scenario)
            self.assertIn('goal', scenario)
            self.assertIn('scenario_id', scenario)

if __name__ == '__main__':
    unittest.main()
