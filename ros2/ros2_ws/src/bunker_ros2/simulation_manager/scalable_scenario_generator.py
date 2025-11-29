#!/usr/bin/env python3
"""
スケーラブルなシナリオ生成器

マップサイズに応じた適切なシナリオを生成
"""
import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple, List

@dataclass
class MapConfig:
    """マップ設定"""
    name: str
    size: float  # 一辺の長さ [m]
    min_bound: Tuple[float, float, float]
    max_bound: Tuple[float, float, float]
    voxel_size: float
    description: str

class ScalableScenarioGenerator:
    """スケーラブルなシナリオ生成器"""
    
    # 3つのスケール定義
    SCALES = {
        'small': MapConfig(
            name='Small Scale',
            size=20.0,
            min_bound=(-10.0, -10.0, 0.0),
            max_bound=(10.0, 10.0, 3.0),
            voxel_size=0.1,
            description='基本性能検証用（20m × 20m）'
        ),
        'medium': MapConfig(
            name='Medium Scale',
            size=50.0,
            min_bound=(-25.0, -25.0, 0.0),
            max_bound=(25.0, 25.0, 5.0),
            voxel_size=0.2,  # 計算コスト削減のため粗く
            description='実用性検証用（50m × 50m）'
        ),
        'large': MapConfig(
            name='Large Scale',
            size=100.0,
            min_bound=(-50.0, -50.0, 0.0),
            max_bound=(50.0, 50.0, 8.0),
            voxel_size=0.5,  # さらに粗く
            description='スケーラビリティ検証用（100m × 100m）'
        )
    }
    
    def __init__(self, scale='small'):
        """
        初期化
        
        Args:
            scale: 'small', 'medium', 'large'
        """
        self.config = self.SCALES[scale]
        print(f"スケール: {self.config.name}")
        print(f"  サイズ: {self.config.size}m × {self.config.size}m")
        print(f"  ボクセルサイズ: {self.config.voxel_size}m")
    
    def generate_scenarios(self, num_scenarios=10):
        """
        スケールに応じたシナリオ生成
        
        Args:
            num_scenarios: 生成するシナリオ数
        """
        scenarios = []
        
        for i in range(num_scenarios):
            scenario = self._generate_single_scenario(i)
            scenarios.append(scenario)
        
        return scenarios
    
    def _generate_single_scenario(self, scenario_id):
        """1つのシナリオを生成"""
        # スタートとゴールをマップの対角に配置
        margin = self.config.size * 0.1  # 端から10%内側
        
        # スタート（左下）
        start = [
            self.config.min_bound[0] + margin,
            self.config.min_bound[1] + margin,
            0.2
        ]
        
        # ゴール（右上）
        goal = [
            self.config.max_bound[0] - margin,
            self.config.max_bound[1] - margin,
            0.2
        ]
        
        # スタート-ゴール間の距離
        distance = np.linalg.norm(np.array(goal) - np.array(start))
        
        # 地形タイプをランダムに選択
        terrain_types = [
            'Flat Terrain',
            'Gentle Slope',
            'Steep Slope',
            'Mixed Terrain',
            'Obstacle Field'
        ]
        terrain_type = np.random.choice(terrain_types)
        
        # 地形データ生成（簡易版）
        terrain_data = self._generate_terrain_data(terrain_type)
        
        scenario = {
            'scenario_id': scenario_id,
            'scale': self.config.name,
            'map_size': self.config.size,
            'distance': distance,
            'start': start,
            'goal': goal,
            'terrain_type': terrain_type,
            'terrain': terrain_data,
            'voxel_size': self.config.voxel_size
        }
        
        return scenario
    
    def _generate_terrain_data(self, terrain_type):
        """地形データ生成（簡易版）"""
        # 実際の地形データ構造を返す
        # ここでは簡易的なmock
        class MockTerrain:
            def __init__(self, terrain_type):
                self.terrain_type = terrain_type
        
        return MockTerrain(terrain_type)
    
    def save_scenarios(self, scenarios, output_dir):
        """シナリオを保存"""
        output_path = Path(output_dir) / self.config.name.lower().replace(' ', '_')
        output_path.mkdir(parents=True, exist_ok=True)
        
        for scenario in scenarios:
            filename = f"scenario_{scenario['scenario_id']:03d}.json"
            filepath = output_path / filename
            
            # JSON serializable化
            scenario_json = {
                'scenario_id': scenario['scenario_id'],
                'scale': scenario['scale'],
                'map_size': scenario['map_size'],
                'distance': scenario['distance'],
                'start': scenario['start'],
                'goal': scenario['goal'],
                'terrain_type': scenario['terrain_type'],
                'voxel_size': scenario['voxel_size']
            }
            
            with open(filepath, 'w') as f:
                json.dump(scenario_json, f, indent=2)
        
        print(f"{len(scenarios)}個のシナリオを保存: {output_path}")

def generate_all_scales():
    """全スケールのシナリオを生成"""
    output_base = '../scenarios/scalability'
    
    for scale in ['small', 'medium', 'large']:
        print(f"\n{'='*70}")
        print(f"{scale.upper()} SCALE")
        print(f"{'='*70}")
        
        generator = ScalableScenarioGenerator(scale)
        
        # シナリオ数をスケールに応じて調整
        num_scenarios = {
            'small': 20,   # 小規模：多めにテスト
            'medium': 15,  # 中規模：実用的な数
            'large': 10    # 大規模：計算コスト考慮
        }[scale]
        
        scenarios = generator.generate_scenarios(num_scenarios)
        generator.save_scenarios(scenarios, output_base)
    
    print(f"\n✅ 全スケールのシナリオ生成完了")

if __name__ == '__main__':
    generate_all_scales()




