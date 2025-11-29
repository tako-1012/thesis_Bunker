#!/usr/bin/env python3
"""
シンプルなスケーラビリティ実験
全アルゴリズムを3つのスケールで評価
"""

import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List
import sys
import logging

# パスを追加
sys.path.append('../path_planner_3d')

# アルゴリズムをインポート
from astar_planner_3d_fixed import AStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleScalabilityExperiment:
    """シンプルなスケーラビリティ実験"""
    
    def __init__(self):
        self.scales = {
            'small': {
                'name': 'Small Scale (20m×20m)',
                'voxel_size': 0.1,
                'map_bounds': ([-10, -10, 0], [10, 10, 3]),
                'scenarios': 5
            },
            'medium': {
                'name': 'Medium Scale (50m×50m)',
                'voxel_size': 0.2,
                'map_bounds': ([-25, -25, 0], [25, 25, 5]),
                'scenarios': 5
            },
            'large': {
                'name': 'Large Scale (100m×100m)',
                'voxel_size': 0.5,
                'map_bounds': ([-50, -50, 0], [50, 50, 8]),
                'scenarios': 5
            }
        }
        
        self.results = {}
    
    def create_test_scenarios(self, scale_config):
        """テストシナリオを作成"""
        scenarios = []
        map_bounds = scale_config['map_bounds']
        voxel_size = scale_config['voxel_size']
        
        # ランダムなスタート・ゴール位置を生成
        np.random.seed(42)  # 再現性のため
        
        for i in range(scale_config['scenarios']):
            # スタート位置（境界から少し内側）
            start = [
                np.random.uniform(map_bounds[0][0] + 2, map_bounds[1][0] - 2),
                np.random.uniform(map_bounds[0][1] + 2, map_bounds[1][1] - 2),
                np.random.uniform(map_bounds[0][2], map_bounds[1][2])
            ]
            
            # ゴール位置（スタートから十分離れた位置）
            goal = [
                np.random.uniform(map_bounds[0][0] + 2, map_bounds[1][0] - 2),
                np.random.uniform(map_bounds[0][1] + 2, map_bounds[1][1] - 2),
                np.random.uniform(map_bounds[0][2], map_bounds[1][2])
            ]
            
            # スタートとゴールが近すぎる場合は調整
            distance = np.linalg.norm(np.array(goal) - np.array(start))
            min_distance = np.linalg.norm(np.array(map_bounds[1]) - np.array(map_bounds[0])) * 0.3
            
            if distance < min_distance:
                # ゴールを反対側に移動
                goal[0] = map_bounds[1][0] - 2 if start[0] < 0 else map_bounds[0][0] + 2
                goal[1] = map_bounds[1][1] - 2 if start[1] < 0 else map_bounds[0][1] + 2
            
            scenarios.append({
                'scenario_id': i,
                'start': start,
                'goal': goal,
                'terrain_data': None  # シンプルなテストのため地形データなし
            })
        
        return scenarios
    
    def run_algorithm(self, algorithm_name, planner, scenarios, scale_name):
        """単一アルゴリズムの実行"""
        logger.info(f"  {algorithm_name} を実行中...")
        
        results = []
        for i, scenario in enumerate(scenarios):
            logger.info(f"    シナリオ {i+1}/{len(scenarios)}")
            
            try:
                start_time = time.time()
                
                if algorithm_name == 'TA-A* (Proposed)':
                    result = planner.plan_path(
                        start=scenario['start'],
                        goal=scenario['goal'],
                        terrain_data=scenario['terrain_data'],
                        timeout=600
                    )
                else:
                    # A*はterrain_dataパラメータを受け取らない
                    result = planner.plan_path(
                        start=scenario['start'],
                        goal=scenario['goal']
                    )
                
                computation_time = time.time() - start_time
                
                if result is not None and isinstance(result, dict):
                    # 辞書形式の結果
                    success = result.get('success', False)
                    path_length = result.get('path_length', 0)
                    nodes_explored = result.get('nodes_explored', 0)
                elif result is not None and isinstance(result, list):
                    # リスト形式の結果（A*など）
                    success = len(result) > 0
                    path_length = len(result) * 0.1  # 近似値
                    nodes_explored = len(result) * 10  # 近似値
                else:
                    success = False
                    path_length = 0
                    nodes_explored = 0
                
                results.append({
                    'scenario_id': scenario['scenario_id'],
                    'success': success,
                    'computation_time': computation_time,
                    'path_length': path_length,
                    'nodes_explored': nodes_explored,
                    'error': '' if success else 'No path found'
                })
                
                logger.info(f"      結果: {'成功' if success else '失敗'}, "
                          f"時間: {computation_time:.2f}s, "
                          f"経路長: {path_length:.2f}m")
                
            except Exception as e:
                logger.error(f"      エラー: {e}")
                results.append({
                    'scenario_id': scenario['scenario_id'],
                    'success': False,
                    'computation_time': 0,
                    'path_length': 0,
                    'nodes_explored': 0,
                    'error': str(e)
                })
        
        return results
    
    def run_scale(self, scale_name, scale_config):
        """単一スケールの実行"""
        logger.info(f"\n{'='*60}")
        logger.info(f"{scale_config['name']}")
        logger.info(f"{'='*60}")
        
        # テストシナリオを作成
        scenarios = self.create_test_scenarios(scale_config)
        logger.info(f"テストシナリオ数: {len(scenarios)}")
        
        # アルゴリズムを初期化
        algorithms = {
            'A*': AStarPlanner3D(
                voxel_size=scale_config['voxel_size'],
                map_bounds=scale_config['map_bounds']
            ),
            'TA-A* (Proposed)': TerrainAwareAStarPlanner3D(
                voxel_size=scale_config['voxel_size'],
                map_bounds=scale_config['map_bounds']
            )
        }
        
        scale_results = {}
        
        # 各アルゴリズムを実行
        for algo_name, planner in algorithms.items():
            results = self.run_algorithm(algo_name, planner, scenarios, scale_name)
            scale_results[algo_name] = results
        
        return scale_results
    
    def run_experiment(self):
        """実験全体の実行"""
        logger.info("="*60)
        logger.info("シンプルなスケーラビリティ実験開始")
        logger.info("="*60)
        
        start_time = time.time()
        
        # 各スケールで実験
        for scale_name, scale_config in self.scales.items():
            scale_results = self.run_scale(scale_name, scale_config)
            self.results[scale_name] = scale_results
        
        # 結果を保存
        self.save_results()
        
        # サマリーを表示
        self.print_summary()
        
        total_time = time.time() - start_time
        logger.info(f"\n実験完了！総時間: {total_time:.2f}秒")
    
    def save_results(self):
        """結果を保存"""
        output_path = Path('../results/simple_scalability_results.json')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"\n結果を保存: {output_path}")
    
    def print_summary(self):
        """サマリーを表示"""
        logger.info("\n" + "="*60)
        logger.info("実験結果サマリー")
        logger.info("="*60)
        
        for scale_name, scale_config in self.scales.items():
            logger.info(f"\n{scale_config['name']}:")
            logger.info("-" * 40)
            
            if scale_name not in self.results:
                logger.info("  データなし")
                continue
            
            for algo_name, results in self.results[scale_name].items():
                success_count = sum(1 for r in results if r['success'])
                total_count = len(results)
                success_rate = success_count / total_count * 100 if total_count > 0 else 0
                
                # 成功したもののみで平均を計算
                success_results = [r for r in results if r['success']]
                
                avg_time = np.mean([r['computation_time'] for r in success_results]) if success_results else 0
                avg_length = np.mean([r['path_length'] for r in success_results]) if success_results else 0
                avg_nodes = np.mean([r['nodes_explored'] for r in success_results]) if success_results else 0
                
                logger.info(f"  {algo_name:20s}: {success_count:2d}/{total_count:2d} "
                          f"({success_rate:5.1f}%) "
                          f"時間: {avg_time:6.2f}s "
                          f"経路長: {avg_length:7.2f}m "
                          f"ノード: {avg_nodes:8.0f}")

def main():
    """メイン関数"""
    experiment = SimpleScalabilityExperiment()
    experiment.run_experiment()

if __name__ == '__main__':
    main()
