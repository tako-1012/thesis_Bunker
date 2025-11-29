"""
地形実験クラス

Phase 2の代表的地形実験をリファクタリング版で実装
"""
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional

# パス追加
sys.path.append('../path_planner_3d')

from base_experiment import BaseExperiment, ExperimentResult
from config import PlannerConfig
from astar_planner import AStarPlanner3D

logger = logging.getLogger(__name__)

class TerrainExperiment(BaseExperiment):
    """地形実験クラス"""
    
    def __init__(self, terrain_type: str, num_scenarios: int = 10, 
                 output_dir: str = "../results"):
        """
        初期化
        
        Args:
            terrain_type: 地形タイプ
            num_scenarios: シナリオ数
            output_dir: 出力ディレクトリ
        """
        super().__init__(f"Terrain_{terrain_type}", output_dir)
        
        self.terrain_type = terrain_type
        self.num_scenarios = num_scenarios
        
        # プランナー設定
        self.config = PlannerConfig.medium_scale()
        
        # アルゴリズム初期化
        self.algorithms = {
            'A*': AStarPlanner3D(self.config),
            # 他のアルゴリズムも後で追加
        }
        
        logger.info(f"Terrain experiment initialized: {terrain_type}")
        logger.info(f"Scenarios: {num_scenarios}")
        logger.info(f"Algorithms: {list(self.algorithms.keys())}")
    
    def run_experiment(self) -> None:
        """地形実験を実行"""
        self.start_experiment()
        
        try:
            # シナリオ生成
            scenarios = self._generate_scenarios()
            self.stats['total_experiments'] = len(scenarios) * len(self.algorithms)
            
            logger.info(f"Generated {len(scenarios)} scenarios")
            
            # 各シナリオで実験
            for i, scenario in enumerate(scenarios):
                logger.info(f"\nScenario {i+1}/{len(scenarios)}: "
                           f"{scenario['start']} -> {scenario['goal']}")
                
                for algo_name, planner in self.algorithms.items():
                    logger.info(f"  {algo_name:20s}...")
                    
                    try:
                        # 経路計画実行
                        result = planner.plan_path(
                            start=scenario['start'],
                            goal=scenario['goal'],
                            terrain_data=None,
                            timeout=300  # 5分
                        )
                        
                        # 結果を記録
                        exp_result = ExperimentResult(
                            experiment_id=f"{self.terrain_type}_{i:03d}",
                            algorithm_name=algo_name,
                            success=result.success,
                            computation_time=result.computation_time,
                            path_length=result.path_length if result.success else 0,
                            nodes_explored=result.nodes_explored,
                            error_message=result.error_message,
                            additional_metrics={
                                'terrain_type': self.terrain_type,
                                'scenario_id': i,
                                'start': scenario['start'],
                                'goal': scenario['goal'],
                                'distance': scenario.get('distance', 0)
                            }
                        )
                        
                        self.add_result(exp_result)
                        
                        status = "✅" if result.success else "❌"
                        logger.info(f"{status} ({result.computation_time:.2f}s)")
                        
                    except Exception as e:
                        logger.error(f"❌ Error: {str(e)}")
                        
                        # エラー結果も記録
                        exp_result = ExperimentResult(
                            experiment_id=f"{self.terrain_type}_{i:03d}",
                            algorithm_name=algo_name,
                            success=False,
                            computation_time=0,
                            path_length=0,
                            nodes_explored=0,
                            error_message=str(e),
                            additional_metrics={
                                'terrain_type': self.terrain_type,
                                'scenario_id': i,
                                'start': scenario['start'],
                                'goal': scenario['goal']
                            }
                        )
                        
                        self.add_result(exp_result)
            
            # 結果保存
            self.save_results()
            self.print_summary()
            
        except Exception as e:
            logger.error(f"Experiment failed: {e}", exc_info=True)
        
        finally:
            self.end_experiment()
    
    def _generate_scenarios(self) -> List[Dict]:
        """
        シナリオを生成
        
        Returns:
            List[Dict]: シナリオのリスト
        """
        import numpy as np
        
        scenarios = []
        min_bound = np.array(self.config.map_bounds[0])
        max_bound = np.array(self.config.map_bounds[1])
        
        # マージンを設定
        margin = 2.0
        
        for i in range(self.num_scenarios):
            # ランダムなスタート・ゴール生成
            start = [
                np.random.uniform(min_bound[0] + margin, max_bound[0] - margin),
                np.random.uniform(min_bound[1] + margin, max_bound[1] - margin),
                0.2
            ]
            
            goal = [
                np.random.uniform(min_bound[0] + margin, max_bound[0] - margin),
                np.random.uniform(min_bound[1] + margin, max_bound[1] - margin),
                0.2
            ]
            
            # 最低距離をチェック
            distance = np.linalg.norm(np.array(goal) - np.array(start))
            min_distance = 5.0  # 最低5m
            
            if distance >= min_distance:
                scenarios.append({
                    'scenario_id': i,
                    'start': start,
                    'goal': goal,
                    'distance': distance,
                    'terrain_type': self.terrain_type
                })
        
        return scenarios
