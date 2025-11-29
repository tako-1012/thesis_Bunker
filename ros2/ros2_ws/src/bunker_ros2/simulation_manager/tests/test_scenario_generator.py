#!/usr/bin/env python3
"""
test_scenario_generator.py
ScenarioGeneratorのテストスイート
"""

import unittest
import sys
import shutil
from pathlib import Path

# パス追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from scenario_generator import ScenarioGenerator, Scenario

class TestScenarioGenerator(unittest.TestCase):
    
    def setUp(self):
        """テスト前の初期化"""
        self.generator = ScenarioGenerator()
        self.test_output_dir = "test_scenarios_temp"
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        if Path(self.test_output_dir).exists():
            shutil.rmtree(self.test_output_dir)
    
    def test_scenario_generation_count(self):
        """正しい数のシナリオが生成されること"""
        scenarios = self.generator.generate_all_scenarios(100)
        self.assertEqual(len(scenarios), 100, "100シナリオ生成")
    
    def test_scenario_distribution(self):
        """シナリオタイプの分布が正しいこと"""
        scenarios = self.generator.generate_all_scenarios(100)
        
        type_counts = {}
        for scenario in scenarios:
            terrain_type = scenario.terrain_params.terrain_type
            type_counts[terrain_type] = type_counts.get(terrain_type, 0) + 1
        
        expected = self.generator.scenario_distribution
        self.assertEqual(type_counts, expected, "分布が期待通り")
    
    def test_scenario_uniqueness(self):
        """各シナリオがユニークであること"""
        scenarios = self.generator.generate_all_scenarios(100)
        
        checksums = [s.checksum for s in scenarios]
        self.assertEqual(len(checksums), len(set(checksums)), "チェックサムがユニーク")
    
    def test_save_and_load(self):
        """保存・読み込みが正しく動作すること"""
        # 生成
        original_scenarios = self.generator.generate_all_scenarios(10)
        
        # 保存
        self.generator.save_scenarios(self.test_output_dir)
        
        # 新しいインスタンスで読み込み
        new_generator = ScenarioGenerator()
        loaded_scenarios = new_generator.load_scenarios(self.test_output_dir)
        
        # 検証
        self.assertEqual(len(loaded_scenarios), len(original_scenarios))
        
        for orig, loaded in zip(original_scenarios, loaded_scenarios):
            self.assertEqual(orig.scenario_id, loaded.scenario_id)
            self.assertEqual(orig.checksum, loaded.checksum)
    
    def test_difficulty_classification(self):
        """難易度分類が適切であること"""
        scenarios = self.generator.generate_all_scenarios(100)
        
        difficulty_counts = {'easy': 0, 'medium': 0, 'hard': 0}
        for scenario in scenarios:
            difficulty_counts[scenario.expected_difficulty] += 1
        
        # 各難易度が存在すること
        self.assertGreater(difficulty_counts['easy'], 0)
        self.assertGreater(difficulty_counts['medium'], 0)
        self.assertGreater(difficulty_counts['hard'], 0)
        
        print(f"\n難易度分布: {difficulty_counts}")
    
    def test_start_goal_positions(self):
        """スタート・ゴール位置が有効範囲内であること"""
        scenarios = self.generator.generate_all_scenarios(20)
        
        for scenario in scenarios:
            terrain = scenario.terrain_params
            start = scenario.start_position
            goal = scenario.goal_position
            
            # 範囲チェック
            self.assertGreaterEqual(start[0], 0)
            self.assertLess(start[0], terrain.size_x)
            self.assertGreaterEqual(goal[0], 0)
            self.assertLess(goal[0], terrain.size_x)
    
    def test_terrain_parameter_ranges(self):
        """地形パラメータが適切な範囲内であること"""
        scenarios = self.generator.generate_all_scenarios(50)
        
        for scenario in scenarios:
            terrain = scenario.terrain_params
            
            # 基本範囲チェック
            self.assertGreaterEqual(terrain.obstacle_density, 0.0)
            self.assertLessEqual(terrain.obstacle_density, 1.0)
            self.assertGreaterEqual(terrain.max_slope, 0.0)
            self.assertLessEqual(terrain.max_slope, 90.0)
            self.assertGreaterEqual(terrain.roughness, 0.0)
            self.assertLessEqual(terrain.roughness, 1.0)
            self.assertGreater(terrain.narrow_passage_width, 0.0)
    
    def test_scenario_consistency(self):
        """シナリオの一貫性が保たれること"""
        scenarios = self.generator.generate_all_scenarios(20)
        
        for scenario in scenarios:
            # 地形タイプと名前の一貫性
            terrain_type = scenario.terrain_params.terrain_type
            self.assertTrue(scenario.name.startswith(terrain_type))
            
            # チェックサムの再計算
            expected_checksum = self.generator._calculate_checksum(
                scenario.scenario_id, 
                scenario.terrain_params
            )
            self.assertEqual(scenario.checksum, expected_checksum)
    
    def test_reproducibility(self):
        """同じシードで同じシナリオが生成されること"""
        # 2回同じシナリオを生成
        generator1 = ScenarioGenerator()
        scenarios1 = generator1.generate_all_scenarios(10)
        
        generator2 = ScenarioGenerator()
        scenarios2 = generator2.generate_all_scenarios(10)
        
        # チェックサムが同じであること
        for s1, s2 in zip(scenarios1, scenarios2):
            self.assertEqual(s1.checksum, s2.checksum, "再現性が保たれること")

if __name__ == '__main__':
    print("=" * 60)
    print("ScenarioGenerator テストスイート実行")
    print("=" * 60)
    
    unittest.main(verbosity=2)
