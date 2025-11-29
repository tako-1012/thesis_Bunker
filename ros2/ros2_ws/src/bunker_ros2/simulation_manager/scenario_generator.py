#!/usr/bin/env python3
"""
scenario_generator.py
大規模シミュレーション用シナリオ自動生成システム

機能:
- 100種類の多様な地形シナリオ生成
- パラメータのランダム変動
- 難易度分類
- シナリオのシリアライズ/デシリアライズ
"""

import numpy as np
import json
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib

@dataclass
class TerrainParameters:
    """地形パラメータ"""
    terrain_type: str           # 地形タイプ
    size_x: float               # X方向サイズ (m)
    size_y: float               # Y方向サイズ (m)
    size_z: float               # Z方向サイズ (m)
    obstacle_density: float     # 障害物密度 (0.0-1.0)
    max_slope: float            # 最大勾配 (度)
    roughness: float            # 地形の粗さ (0.0-1.0)
    narrow_passage_width: float # 狭路の幅 (m)
    difficulty: str             # 難易度 (easy/medium/hard)

@dataclass
class RobotParameters:
    """ロボットパラメータ"""
    max_slope_capability: float  # 最大登坂能力 (度)
    width: float                 # ロボット幅 (m)
    height: float                # ロボット高さ (m)
    safety_margin: float         # 安全マージン (m)

@dataclass
class Scenario:
    """シミュレーションシナリオ"""
    scenario_id: int
    name: str
    description: str
    terrain_params: TerrainParameters
    robot_params: RobotParameters
    start_position: Tuple[float, float, float]
    goal_position: Tuple[float, float, float]
    expected_difficulty: str
    created_at: str
    checksum: str

class ScenarioGenerator:
    """シナリオ自動生成クラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.scenarios: List[Scenario] = []
        self.config = self._load_config(config_path)
        
        # シナリオタイプごとの生成数
        self.scenario_distribution = {
            'flat_terrain': 10,         # 平地（ベースライン）
            'gentle_slope': 15,         # 緩斜面
            'steep_slope': 15,          # 急斜面
            'mixed_terrain': 20,        # 混合地形
            'obstacle_field': 20,       # 障害物フィールド
            'narrow_passage': 10,       # 狭い通路
            'complex_3d': 10            # 複雑3D地形
        }
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """設定ファイル読み込み"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        
        # デフォルト設定
        return {
            'grid_size': [100, 100, 30],
            'voxel_size': 0.1,
            'min_bound': [-5.0, -5.0, 0.0],
            'default_robot': {
                'max_slope_capability': 30.0,
                'width': 0.8,
                'height': 0.6,
                'safety_margin': 0.2
            }
        }
    
    def generate_all_scenarios(self, total_count: int = 100) -> List[Scenario]:
        """全シナリオを生成"""
        print(f"🎲 {total_count}個のシナリオ生成開始...")
        
        scenario_id = 0
        for terrain_type, count in self.scenario_distribution.items():
            for i in range(count):
                scenario = self._generate_single_scenario(
                    scenario_id, 
                    terrain_type, 
                    i
                )
                self.scenarios.append(scenario)
                scenario_id += 1
                
                if scenario_id % 10 == 0:
                    print(f"  進捗: {scenario_id}/{total_count}シナリオ生成完了")
        
        print(f"✅ {len(self.scenarios)}個のシナリオ生成完了！")
        return self.scenarios
    
    def _generate_single_scenario(
        self, 
        scenario_id: int, 
        terrain_type: str,
        variant_id: int
    ) -> Scenario:
        """単一シナリオ生成"""
        
        # 地形パラメータ生成
        terrain_params = self._generate_terrain_params(terrain_type, variant_id)
        
        # ロボットパラメータ（基本的にデフォルト使用）
        robot_params = RobotParameters(**self.config['default_robot'])
        
        # スタート・ゴール位置生成
        start_pos, goal_pos = self._generate_start_goal(terrain_params)
        
        # 難易度評価
        difficulty = self._estimate_difficulty(terrain_params)
        
        # シナリオ作成
        scenario = Scenario(
            scenario_id=scenario_id,
            name=f"{terrain_type}_{variant_id:02d}",
            description=self._generate_description(terrain_type, terrain_params),
            terrain_params=terrain_params,
            robot_params=robot_params,
            start_position=start_pos,
            goal_position=goal_pos,
            expected_difficulty=difficulty,
            created_at=datetime.now().isoformat(),
            checksum=self._calculate_checksum(scenario_id, terrain_params)
        )
        
        return scenario
    
    def _generate_terrain_params(
        self, 
        terrain_type: str, 
        variant_id: int
    ) -> TerrainParameters:
        """地形タイプに応じたパラメータ生成"""
        
        # 再現性のためのシード設定
        np.random.seed(variant_id * 1000 + hash(terrain_type) % 1000)
        
        if terrain_type == 'flat_terrain':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=10.0,
                size_y=10.0,
                size_z=0.5,
                obstacle_density=np.random.uniform(0.0, 0.1),
                max_slope=np.random.uniform(0.0, 5.0),
                roughness=np.random.uniform(0.0, 0.2),
                narrow_passage_width=5.0,
                difficulty='easy'
            )
        
        elif terrain_type == 'gentle_slope':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=10.0,
                size_y=10.0,
                size_z=3.0,
                obstacle_density=np.random.uniform(0.05, 0.15),
                max_slope=np.random.uniform(10.0, 20.0),
                roughness=np.random.uniform(0.2, 0.4),
                narrow_passage_width=4.0,
                difficulty='easy'
            )
        
        elif terrain_type == 'steep_slope':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=10.0,
                size_y=10.0,
                size_z=5.0,
                obstacle_density=np.random.uniform(0.1, 0.2),
                max_slope=np.random.uniform(25.0, 35.0),
                roughness=np.random.uniform(0.4, 0.6),
                narrow_passage_width=3.0,
                difficulty='medium'
            )
        
        elif terrain_type == 'mixed_terrain':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=12.0,
                size_y=12.0,
                size_z=4.0,
                obstacle_density=np.random.uniform(0.15, 0.3),
                max_slope=np.random.uniform(15.0, 30.0),
                roughness=np.random.uniform(0.3, 0.6),
                narrow_passage_width=3.5,
                difficulty='medium'
            )
        
        elif terrain_type == 'obstacle_field':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=10.0,
                size_y=10.0,
                size_z=2.0,
                obstacle_density=np.random.uniform(0.3, 0.5),
                max_slope=np.random.uniform(5.0, 15.0),
                roughness=np.random.uniform(0.2, 0.4),
                narrow_passage_width=2.5,
                difficulty='medium'
            )
        
        elif terrain_type == 'narrow_passage':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=10.0,
                size_y=10.0,
                size_z=2.0,
                obstacle_density=np.random.uniform(0.4, 0.6),
                max_slope=np.random.uniform(5.0, 20.0),
                roughness=np.random.uniform(0.3, 0.5),
                narrow_passage_width=np.random.uniform(1.0, 2.0),
                difficulty='hard'
            )
        
        elif terrain_type == 'complex_3d':
            return TerrainParameters(
                terrain_type=terrain_type,
                size_x=15.0,
                size_y=15.0,
                size_z=6.0,
                obstacle_density=np.random.uniform(0.25, 0.4),
                max_slope=np.random.uniform(20.0, 35.0),
                roughness=np.random.uniform(0.5, 0.8),
                narrow_passage_width=np.random.uniform(2.0, 3.0),
                difficulty='hard'
            )
        
        else:
            raise ValueError(f"Unknown terrain type: {terrain_type}")
    
    def _generate_start_goal(
        self, 
        terrain_params: TerrainParameters
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """スタート・ゴール位置生成"""
        
        # プランナーのグリッド範囲に合わせる: (-5.0, -5.0, 0.0) to (5.0, 5.0, 3.0)
        # スタート位置（左下付近）
        start_x = np.random.uniform(-4.5, -2.0)
        start_y = np.random.uniform(-4.5, -2.0)
        start_z = 0.0
        
        # ゴール位置（右上付近）
        goal_x = np.random.uniform(2.0, 4.5)
        goal_y = np.random.uniform(2.0, 4.5)
        goal_z = np.random.uniform(0.0, 2.5)
        
        return (start_x, start_y, start_z), (goal_x, goal_y, goal_z)
    
    def _estimate_difficulty(self, terrain_params: TerrainParameters) -> str:
        """難易度推定"""
        # 既に地形タイプベースで設定されているが、パラメータで微調整
        score = 0
        
        if terrain_params.obstacle_density > 0.4:
            score += 2
        elif terrain_params.obstacle_density > 0.2:
            score += 1
        
        if terrain_params.max_slope > 30:
            score += 2
        elif terrain_params.max_slope > 20:
            score += 1
        
        if terrain_params.narrow_passage_width < 2.0:
            score += 2
        elif terrain_params.narrow_passage_width < 3.0:
            score += 1
        
        if score >= 4:
            return 'hard'
        elif score >= 2:
            return 'medium'
        else:
            return 'easy'
    
    def _generate_description(
        self, 
        terrain_type: str, 
        terrain_params: TerrainParameters
    ) -> str:
        """シナリオ説明生成"""
        descriptions = {
            'flat_terrain': "平坦な地形でのベースライン評価",
            'gentle_slope': "緩やかな斜面での移動性能評価",
            'steep_slope': "急斜面での登坂能力評価",
            'mixed_terrain': "多様な地形要素が混在する環境での適応性評価",
            'obstacle_field': "高密度障害物環境での回避能力評価",
            'narrow_passage': "狭い通路での精密制御評価",
            'complex_3d': "複雑な3D地形での総合性能評価"
        }
        
        base_desc = descriptions.get(terrain_type, "一般的な地形評価")
        param_desc = (
            f"（障害物密度: {terrain_params.obstacle_density:.2f}, "
            f"最大勾配: {terrain_params.max_slope:.1f}度, "
            f"粗さ: {terrain_params.roughness:.2f}）"
        )
        
        return f"{base_desc} {param_desc}"
    
    def _calculate_checksum(
        self, 
        scenario_id: int, 
        terrain_params: TerrainParameters
    ) -> str:
        """チェックサム計算（再現性確保）"""
        data_str = f"{scenario_id}_{asdict(terrain_params)}"
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
    
    def save_scenarios(self, output_dir: str = "scenarios"):
        """シナリオをファイルに保存"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"💾 シナリオ保存中: {output_path}")
        
        # 個別シナリオ保存
        for scenario in self.scenarios:
            scenario_file = output_path / f"scenario_{scenario.scenario_id:03d}.json"
            with open(scenario_file, 'w') as f:
                json.dump(asdict(scenario), f, indent=2)
        
        # サマリーファイル保存
        summary = {
            'total_scenarios': len(self.scenarios),
            'distribution': self.scenario_distribution,
            'difficulty_distribution': self._get_difficulty_distribution(),
            'generated_at': datetime.now().isoformat()
        }
        
        summary_file = output_path / "scenarios_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✅ {len(self.scenarios)}個のシナリオ保存完了！")
    
    def _get_difficulty_distribution(self) -> Dict[str, int]:
        """難易度分布取得"""
        distribution = {'easy': 0, 'medium': 0, 'hard': 0}
        for scenario in self.scenarios:
            distribution[scenario.expected_difficulty] += 1
        return distribution
    
    def load_scenarios(self, input_dir: str = "scenarios") -> List[Scenario]:
        """保存されたシナリオを読み込み"""
        input_path = Path(input_dir)
        
        if not input_path.exists():
            raise FileNotFoundError(f"シナリオディレクトリが見つかりません: {input_path}")
        
        print(f"📂 シナリオ読み込み中: {input_path}")
        
        self.scenarios = []
        scenario_files = sorted(input_path.glob("scenario_*.json"))
        
        for scenario_file in scenario_files:
            with open(scenario_file, 'r') as f:
                scenario_dict = json.load(f)
                
                # TerrainParametersとRobotParametersを再構築
                terrain_params = TerrainParameters(**scenario_dict['terrain_params'])
                robot_params = RobotParameters(**scenario_dict['robot_params'])
                
                # Scenarioを再構築
                scenario = Scenario(
                    scenario_id=scenario_dict['scenario_id'],
                    name=scenario_dict['name'],
                    description=scenario_dict['description'],
                    terrain_params=terrain_params,
                    robot_params=robot_params,
                    start_position=tuple(scenario_dict['start_position']),
                    goal_position=tuple(scenario_dict['goal_position']),
                    expected_difficulty=scenario_dict['expected_difficulty'],
                    created_at=scenario_dict['created_at'],
                    checksum=scenario_dict['checksum']
                )
                
                self.scenarios.append(scenario)
        
        print(f"✅ {len(self.scenarios)}個のシナリオ読み込み完了！")
        return self.scenarios

def main():
    """メイン実行"""
    generator = ScenarioGenerator()
    
    # 100シナリオ生成
    scenarios = generator.generate_all_scenarios(100)
    
    # 保存
    generator.save_scenarios("simulation_manager/scenarios")
    
    # 統計表示
    print("\n📊 シナリオ生成統計:")
    print(f"  総シナリオ数: {len(scenarios)}")
    print(f"  難易度分布: {generator._get_difficulty_distribution()}")
    print(f"  地形タイプ分布: {generator.scenario_distribution}")

if __name__ == "__main__":
    main()
