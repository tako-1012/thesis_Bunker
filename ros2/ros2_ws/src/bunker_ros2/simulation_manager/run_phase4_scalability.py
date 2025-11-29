"""
Phase 4: スケーラビリティ検証

3つのマップスケール（20m, 50m, 100m）で全アルゴリズムを評価
実用性を実証
"""
import json
import time
import numpy as np
from pathlib import Path
import logging
import sys

sys.path.append('../path_planner_3d')
from astar_planner_3d_fixed import AStarPlanner3D
from weighted_astar_planner_3d import WeightedAStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D
from rrt_star_planner_3d import RRTStarPlanner3D

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScalabilityExperiment:
    """スケーラビリティ検証実験"""
    
    def __init__(self):
        # 3つのスケール定義
        self.scales = {
            'small': {
                'name': 'Small (20m×20m)',
                'map_bounds': ([-10, -10, 0], [10, 10, 3]),
                'voxel_size': 0.1,
                'num_scenarios': 15,
                'timeout': 600
            },
            'medium': {
                'name': 'Medium (50m×50m)',
                'map_bounds': ([-25, -25, 0], [25, 25, 5]),
                'voxel_size': 0.2,
                'num_scenarios': 15,
                'timeout': 1800
            },
            'large': {
                'name': 'Large (100m×100m)',
                'map_bounds': ([-50, -50, 0], [50, 50, 8]),
                'voxel_size': 0.5,
                'num_scenarios': 10,
                'timeout': 3600
            }
        }
        
        self.results = {}
    
    def run_all_experiments(self):
        """全スケールで実験"""
        logger.info("="*70)
        logger.info("Phase 4: スケーラビリティ検証実験")
        logger.info("="*70)
        
        for scale_name, scale_config in self.scales.items():
            logger.info(f"\n{'#'*70}")
            logger.info(f"# スケール: {scale_config['name']}")
            logger.info(f"{'#'*70}")
            
            # シナリオ生成
            scenarios = self._generate_scenarios(scale_config)
            
            # 実験実行
            results = self._run_scale_experiments(scale_name, scale_config, scenarios)
            
            self.results[scale_name] = results
            
            # 中間保存
            self._save_results()
            
            # サマリー
            self._print_scale_summary(scale_name, results)
        
        # 最終サマリー
        self._print_final_summary()
    
    def _generate_scenarios(self, scale_config):
        """シナリオ生成"""
        scenarios = []
        
        min_bound = np.array(scale_config['map_bounds'][0])
        max_bound = np.array(scale_config['map_bounds'][1])
        
        map_size = np.linalg.norm(max_bound - min_bound)
        margin = map_size * 0.1
        
        for i in range(scale_config['num_scenarios']):
            # ランダムなスタート・ゴール
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
            min_distance = map_size * 0.3
            
            if distance >= min_distance:
                scenarios.append({
                    'scenario_id': i,
                    'start': start,
                    'goal': goal,
                    'distance': distance
                })
        
        logger.info(f"生成したシナリオ数: {len(scenarios)}")
        return scenarios
    
    def _run_scale_experiments(self, scale_name, scale_config, scenarios):
        """1つのスケールで実験"""
        # アルゴリズム初期化
        algorithms = {
            'A*': AStarPlanner3D(
                voxel_size=scale_config['voxel_size'],
                map_bounds=scale_config['map_bounds']
            ),
            'Weighted A*': WeightedAStarPlanner3D(
                voxel_size=scale_config['voxel_size'],
                map_bounds=scale_config['map_bounds']
            ),
            'RRT*': RRTStarPlanner3D(
                voxel_size=scale_config['voxel_size'],
                map_bounds=scale_config['map_bounds']
            ),
            'TA-A* (Proposed)': TerrainAwareAStarPlanner3D(
                voxel_size=scale_config['voxel_size'],
                map_bounds=scale_config['map_bounds']
            )
        }
        
        results = {algo: [] for algo in algorithms}
        
        for scenario in scenarios:
            logger.info(f"\nScenario {scenario['scenario_id']} (distance: {scenario['distance']:.1f}m)")
            
            for algo_name, planner in algorithms.items():
                logger.info(f"  {algo_name:20s}...")
                
                try:
                    result = planner.plan_path(
                        start=scenario['start'],
                        goal=scenario['goal'],
                        terrain_data=None,
                        timeout=scale_config['timeout']
                    )
                    
                    results[algo_name].append({
                        'scenario_id': scenario['scenario_id'],
                        'success': result.success,
                        'computation_time': result.computation_time,
                        'path_length': result.path_length if result.success else 0,
                        'nodes_explored': result.nodes_explored,
                        'distance': scenario['distance']
                    })
                    
                    status = "✅" if result.success else "❌"
                    logger.info(f"    {status} ({result.computation_time:.2f}s)")
                
                except Exception as e:
                    logger.error(f"    ❌ Error: {e}")
                    results[algo_name].append({
                        'scenario_id': scenario['scenario_id'],
                        'success': False,
                        'error': str(e)
                    })
        
        return results
    
    def _save_results(self):
        """結果を保存"""
        output_path = Path('../results/phase4_scalability_results.json')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"結果を保存: {output_path}")
    
    def _print_scale_summary(self, scale_name, results):
        """スケールごとのサマリー"""
        logger.info(f"\n{'='*70}")
        logger.info(f"{self.scales[scale_name]['name']} サマリー")
        logger.info(f"{'='*70}")
        
        for algo, algo_results in results.items():
            success = sum(1 for r in algo_results if r.get('success', False))
            total = len(algo_results)
            rate = success / total * 100 if total > 0 else 0
            
            times = [r['computation_time'] for r in algo_results if r.get('success', False)]
            avg_time = np.mean(times) if times else 0
            
            logger.info(f"{algo:20s}: {success}/{total} = {rate:.1f}%  Avg time: {avg_time:.2f}s")
    
    def _print_final_summary(self):
        """最終サマリー"""
        logger.info(f"\n{'='*70}")
        logger.info("Phase 4 最終サマリー")
        logger.info(f"{'='*70}")
        
        print(f"\n{'Scale':15s} | {'A*':10s} | {'W-A*':10s} | {'RRT*':10s} | {'TA-A*':10s}")
        print("-"*75)
        
        for scale_name, scale_results in self.results.items():
            line = f"{self.scales[scale_name]['name']:15s}"
            
            for algo in ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']:
                if algo in scale_results:
                    results = scale_results[algo]
                    success = sum(1 for r in results if r.get('success', False))
                    total = len(results)
                    rate = success / total * 100 if total > 0 else 0
                    line += f" | {rate:8.1f}%"
                else:
                    line += " |     -    "
            
            print(line)
        
        logger.info("\n✅ Phase 4完了")

if __name__ == '__main__':
    experiment = ScalabilityExperiment()
    experiment.run_all_experiments()



