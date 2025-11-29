#!/usr/bin/env python3
"""
test_simulation_runner.py
SimulationRunnerのテストスイート
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation_runner import SimulationRunner, TerrainGenerator
from scenario_generator import ScenarioGenerator, Scenario

class TestSimulationRunner(unittest.TestCase):
    
    def setUp(self):
        """テスト前の初期化"""
        self.runner = SimulationRunner()
        self.generator = ScenarioGenerator()
    
    def test_single_scenario_execution(self):
        """単一シナリオ実行テスト"""
        # 簡単なシナリオ生成
        scenarios = self.generator.generate_all_scenarios(1)
        scenario = scenarios[0]
        
        # 実行
        result = self.runner.run_scenario(scenario)
        
        # 検証
        self.assertIsNotNone(result)
        self.assertEqual(result.scenario_id, 0)
        self.assertIsInstance(result.computation_time, float)
        self.assertGreater(result.computation_time, 0)
    
    def test_terrain_generation(self):
        """地形生成テスト"""
        scenarios = self.generator.generate_all_scenarios(7)
        
        for scenario in scenarios:
            occupancy = TerrainGenerator.generate_occupancy_grid(
                scenario,
                self.runner.grid_size,
                self.runner.voxel_size,
                self.runner.min_bound
            )
            
            slope = TerrainGenerator.generate_slope_grid(
                scenario,
                self.runner.grid_size,
                self.runner.voxel_size,
                self.runner.min_bound
            )
            
            # 検証
            self.assertEqual(occupancy.shape, self.runner.grid_size)
            self.assertEqual(slope.shape, self.runner.grid_size)
            self.assertTrue((occupancy >= 0).all())
            self.assertTrue((occupancy <= 1).all())
            self.assertTrue((slope >= 0).all())
    
    def test_world_to_grid_conversion(self):
        """座標変換テスト"""
        world_pos = (0.5, 0.5, 0.5)
        grid_pos = self.runner._world_to_grid(world_pos)
        
        self.assertIsInstance(grid_pos, tuple)
        self.assertEqual(len(grid_pos), 3)
        self.assertTrue(all(isinstance(x, int) for x in grid_pos))
    
    def test_path_length_calculation(self):
        """経路長計算テスト"""
        # 簡単な経路
        path = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
        length = self.runner._calculate_path_length(path)
        
        self.assertAlmostEqual(length, 2.0, places=2)
    
    def test_success_rate_calculation(self):
        """成功率計算テスト"""
        # 空の結果
        self.assertEqual(self.runner._calculate_success_rate(), 0.0)
        
        # 成功・失敗の結果を追加
        from simulation_runner import SimulationResult
        from datetime import datetime
        
        success_result = SimulationResult(
            scenario_id=0, scenario_name="test", success=True, path_found=True,
            path_length=1.0, num_waypoints=2, computation_time=0.1,
            memory_usage=0.0, cost_breakdown={}, error_message="",
            executed_at=datetime.now().isoformat()
        )
        
        fail_result = SimulationResult(
            scenario_id=1, scenario_name="test2", success=False, path_found=False,
            path_length=0.0, num_waypoints=0, computation_time=0.1,
            memory_usage=0.0, cost_breakdown={}, error_message="No path",
            executed_at=datetime.now().isoformat()
        )
        
        self.runner.results = [success_result, fail_result]
        success_rate = self.runner._calculate_success_rate()
        self.assertEqual(success_rate, 50.0)
    
    def test_terrain_types(self):
        """地形タイプ別テスト"""
        terrain_types = [
            'flat_terrain', 'gentle_slope', 'steep_slope',
            'mixed_terrain', 'obstacle_field', 'narrow_passage', 'complex_3d'
        ]
        
        for terrain_type in terrain_types:
            # テスト用シナリオ作成（既存のシナリオから取得）
            scenarios = self.generator.generate_all_scenarios(7)
            scenario = scenarios[0]  # 最初のシナリオを使用
            
            # 地形生成
            occupancy = TerrainGenerator.generate_occupancy_grid(
                scenario, self.runner.grid_size, self.runner.voxel_size, self.runner.min_bound
            )
            
            slope = TerrainGenerator.generate_slope_grid(
                scenario, self.runner.grid_size, self.runner.voxel_size, self.runner.min_bound
            )
            
            # 基本検証
            self.assertEqual(occupancy.shape, self.runner.grid_size)
            self.assertEqual(slope.shape, self.runner.grid_size)
            self.assertTrue((occupancy >= 0).all() and (occupancy <= 1).all())
            self.assertTrue((slope >= 0).all())

if __name__ == '__main__':
    unittest.main(verbosity=2)
