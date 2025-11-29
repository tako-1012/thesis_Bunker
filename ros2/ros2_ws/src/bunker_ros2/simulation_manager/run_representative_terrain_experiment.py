"""
代表的地形での全アルゴリズム完全比較実験

5地形 × 検証済みシナリオ × 5アルゴリズム
"""
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List
import logging
import sys

# プランナーのインポート
sys.path.append('../path_planner_3d')
from astar_planner_3d_fixed import AStarPlanner3D
from weighted_astar_planner_3d import WeightedAStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D
from dijkstra_planner_3d import DijkstraPlanner3D
from rrt_star_planner_3d import RRTStarPlanner3D

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RepresentativeTerrainExperiment:
    """代表的地形での完全比較実験"""
    
    def __init__(self):
        # 5つの地形タイプ
        self.terrain_types = [
            'flat_agricultural_field',
            'gentle_hills',
            'steep_terrain',
            'complex_obstacles',
            'extreme_hazards'
        ]
        
        self.terrain_names = {
            'flat_agricultural_field': 'Flat Agricultural Field',
            'gentle_hills': 'Gentle Hills',
            'steep_terrain': 'Steep Terrain',
            'complex_obstacles': 'Complex Obstacles',
            'extreme_hazards': 'Extreme Hazards'
        }
        
        # 結果格納
        self.results = {}
        
        # 統計
        self.stats = {
            'total_experiments': 0,
            'completed_experiments': 0,
            'failed_experiments': 0,
            'start_time': None,
            'end_time': None
        }
    
    def run_all_experiments(self):
        """全実験を実行"""
        self.stats['start_time'] = time.time()
        
        logger.info("="*70)
        logger.info("Phase 2: 代表的地形での全アルゴリズム比較実験開始")
        logger.info("="*70)
        logger.info(f"地形数: {len(self.terrain_types)}")
        logger.info(f"アルゴリズム数: 5")
        logger.info("="*70)
        
        for i, terrain_type in enumerate(self.terrain_types, 1):
            logger.info(f"\n{'#'*70}")
            logger.info(f"# 地形 {i}/{len(self.terrain_types)}: {self.terrain_names[terrain_type]}")
            logger.info(f"{'#'*70}")
            
            try:
                results = self._run_terrain_experiments(terrain_type)
                self.results[terrain_type] = results
                
                # 中間結果を保存
                self._save_results()
                
                # サマリー表示
                self._print_terrain_summary(terrain_type, results)
                
            except Exception as e:
                logger.error(f"地形 {terrain_type} でエラー: {e}")
                import traceback
                traceback.print_exc()
        
        self.stats['end_time'] = time.time()
        
        # 最終サマリー
        self._print_final_summary()
    
    def _run_terrain_experiments(self, terrain_type: str) -> Dict:
        """1つの地形タイプで全実験"""
        # 検証済みシナリオディレクトリ
        scenario_dir = Path(f'../scenarios/validated/{terrain_type}')
        
        if not scenario_dir.exists():
            logger.error(f"検証済みシナリオが見つかりません: {scenario_dir}")
            logger.error("先に scenario_reachability_validator.py を実行してください")
            return {}
        
        scenario_files = sorted(scenario_dir.glob('scenario_*.json'))
        
        if not scenario_files:
            logger.warning(f"シナリオファイルがありません: {scenario_dir}")
            return {}
        
        logger.info(f"検証済みシナリオ数: {len(scenario_files)}")
        
        # アルゴリズム初期化（50m×50mマップ）
        map_bounds = ([-25, -25, 0], [25, 25, 5])
        voxel_size = 0.2
        
        algorithms = {
            'Dijkstra': DijkstraPlanner3D(
                voxel_size=voxel_size,
                map_bounds=map_bounds
            ),
            'A*': AStarPlanner3D(
                voxel_size=voxel_size,
                map_bounds=map_bounds
            ),
            'Weighted A*': WeightedAStarPlanner3D(
                voxel_size=voxel_size,
                map_bounds=map_bounds
            ),
            'RRT*': RRTStarPlanner3D(
                voxel_size=voxel_size,
                map_bounds=map_bounds
            ),
            'TA-A* (Proposed)': TerrainAwareAStarPlanner3D(
                voxel_size=voxel_size,
                map_bounds=map_bounds
            )
        }
        
        logger.info(f"アルゴリズム数: {len(algorithms)}")
        
        # 総実験数を計算
        total_experiments = len(scenario_files) * len(algorithms)
        self.stats['total_experiments'] += total_experiments
        completed = 0
        
        logger.info(f"この地形での実験数: {total_experiments}")
        
        # 結果格納
        results = {algo: [] for algo in algorithms}
        
        # 各シナリオで実験
        for scenario_file in scenario_files:
            with open(scenario_file) as f:
                scenario = json.load(f)
            
            scenario_id = scenario['scenario_id']
            logger.info(f"\nScenario {scenario_id:03d}/{len(scenario_files)} "
                       f"(distance: {scenario.get('distance', 0):.1f}m)")
            
            for algo_name, planner in algorithms.items():
                logger.info(f"  {algo_name:20s}...")
                
                try:
                    # 経路計画実行
                    result = planner.plan_path(
                        start=scenario['start'],
                        goal=scenario['goal'],
                        terrain_data=None,
                        timeout=1800  # 30分
                    )
                    
                    # 結果を記録
                    result_data = {
                        'scenario_id': scenario_id,
                        'terrain_type': terrain_type,
                        'terrain_name': self.terrain_names[terrain_type],
                        'success': result.success,
                        'computation_time': result.computation_time,
                        'path_length': result.path_length if result.success else 0,
                        'nodes_explored': result.nodes_explored,
                        'distance': scenario.get('distance', 0),
                        'max_slope': scenario.get('max_slope', 0),
                        'error_message': result.error_message
                    }
                    
                    # TA-A*の場合は追加情報
                    if algo_name == 'TA-A* (Proposed)' and result.success:
                        result_data['risk_score'] = result.risk_score
                        result_data['terrain_adaptations'] = result.terrain_adaptations
                    
                    results[algo_name].append(result_data)
                    
                    # 統計更新
                    completed += 1
                    self.stats['completed_experiments'] += 1
                    
                    if result.success:
                        status = "✅"
                    else:
                        status = "❌"
                        self.stats['failed_experiments'] += 1
                    
                    logger.info(f"{status} ({result.computation_time:.2f}s)")
                    
                except Exception as e:
                    logger.error(f"❌ Error: {str(e)}")
                    
                    results[algo_name].append({
                        'scenario_id': scenario_id,
                        'terrain_type': terrain_type,
                        'terrain_name': self.terrain_names[terrain_type],
                        'success': False,
                        'error_message': str(e)
                    })
                    
                    completed += 1
                    self.stats['completed_experiments'] += 1
                    self.stats['failed_experiments'] += 1
            
            # 進捗表示
            progress = completed / total_experiments * 100
            logger.info(f"  進捗: {completed}/{total_experiments} ({progress:.1f}%)")
        
        return results
    
    def _save_results(self):
        """結果を保存"""
        output_path = Path('../results/representative_terrain_results.json')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 結果と統計を一緒に保存
        output_data = {
            'results': self.results,
            'statistics': self.stats,
            'metadata': {
                'terrain_types': self.terrain_types,
                'terrain_names': self.terrain_names,
                'algorithms': [
                    'Dijkstra',
                    'A*',
                    'Weighted A*',
                    'RRT*',
                    'TA-A* (Proposed)'
                ]
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"結果を保存: {output_path}")
    
    def _print_terrain_summary(self, terrain_type: str, results: Dict):
        """地形ごとのサマリー"""
        logger.info(f"\n{'='*70}")
        logger.info(f"{self.terrain_names[terrain_type]} サマリー")
        logger.info(f"{'='*70}")
        
        for algo, algo_results in results.items():
            if not algo_results:
                continue
            
            success = sum(1 for r in algo_results if r.get('success', False))
            total = len(algo_results)
            rate = success / total * 100 if total > 0 else 0
            
            times = [r['computation_time'] for r in algo_results if r.get('success', False)]
            avg_time = np.mean(times) if times else 0
            
            lengths = [r['path_length'] for r in algo_results if r.get('success', False) and r['path_length'] > 0]
            avg_length = np.mean(lengths) if lengths else 0
            
            nodes = [r['nodes_explored'] for r in algo_results if r.get('success', False)]
            avg_nodes = np.mean(nodes) if nodes else 0
            
            logger.info(f"{algo:20s}: {success:2d}/{total:2d} = {rate:5.1f}%  "
                       f"Time: {avg_time:7.2f}s  "
                       f"Length: {avg_length:7.2f}m  "
                       f"Nodes: {avg_nodes:8.0f}")
    
    def _print_final_summary(self):
        """最終サマリー"""
        elapsed = self.stats['end_time'] - self.stats['start_time']
        
        logger.info(f"\n{'='*70}")
        logger.info("Phase 2 完了！最終サマリー")
        logger.info(f"{'='*70}")
        logger.info(f"総実験数: {self.stats['total_experiments']}")
        logger.info(f"完了: {self.stats['completed_experiments']}")
        logger.info(f"失敗: {self.stats['failed_experiments']}")
        logger.info(f"所要時間: {elapsed/3600:.2f}時間")
        logger.info(f"{'='*70}")
        
        # テーブル形式で表示
        print(f"\n地形タイプ別成功率:")
        print(f"{'Terrain':25s} | {'Dijkstra':10s} | {'A*':10s} | {'W-A*':10s} | {'RRT*':10s} | {'TA-A*':10s}")
        print("-"*95)
        
        for terrain_type in self.terrain_types:
            if terrain_type not in self.results:
                continue
            
            line = f"{self.terrain_names[terrain_type]:25s}"
            
            for algo in ['Dijkstra', 'A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']:
                if algo in self.results[terrain_type]:
                    results = self.results[terrain_type][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    total = len(results)
                    rate = success / total * 100 if total > 0 else 0
                    line += f" | {rate:8.1f}%"
                else:
                    line += " |     -    "
            
            print(line)
        
        logger.info(f"\n✅ Phase 2完了！")
        logger.info(f"結果: ../results/representative_terrain_results.json")

if __name__ == '__main__':
    experiment = RepresentativeTerrainExperiment()
    experiment.run_all_experiments()