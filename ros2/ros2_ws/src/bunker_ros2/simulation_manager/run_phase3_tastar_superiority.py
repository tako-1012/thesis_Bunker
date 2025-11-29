"""
Phase 3: TA-A*優位性実証実験

目的：A* vs TA-A*の詳細比較
      転倒リスク評価機能の実証
"""
import json
import time
import numpy as np
from pathlib import Path
import logging
import sys

sys.path.append('../path_planner_3d')
from astar_planner_3d_fixed import AStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TAAStarSuperiorityExperiment:
    """TA-A*優位性実証実験"""
    
    def __init__(self):
        self.results = []
    
    def run_experiment(self):
        """実験実行"""
        logger.info("="*70)
        logger.info("Phase 3: TA-A*優位性実証実験")
        logger.info("="*70)
        
        # Phase 2の結果から困難なシナリオを抽出
        difficult_scenarios = self._extract_difficult_scenarios()
        
        logger.info(f"困難なシナリオ数: {len(difficult_scenarios)}")
        
        # A*とTA-A*で比較
        for scenario in difficult_scenarios:
            self._compare_algorithms(scenario)
        
        # 結果を保存
        self._save_results()
        
        # サマリー表示
        self._print_summary()
    
    def _extract_difficult_scenarios(self):
        """困難なシナリオを抽出"""
        # Phase 2の結果を読み込み
        with open('../results/representative_terrain_results.json') as f:
            phase2_data = json.load(f)
        
        difficult = []
        
        # Steep Terrain, Complex, Extremeから抽出
        target_terrains = ['steep_terrain', 'complex_obstacles', 'extreme_hazards']
        
        for terrain in target_terrains:
            if terrain not in phase2_data['results']:
                continue
            
            # A*が失敗したシナリオ
            astar_results = phase2_data['results'][terrain].get('A*', [])
            
            for result in astar_results:
                if not result.get('success', False):
                    # シナリオファイルを読み込み
                    scenario_file = Path(f'../scenarios/validated/{terrain}/scenario_{result["scenario_id"]:03d}.json')
                    if scenario_file.exists():
                        with open(scenario_file) as f:
                            scenario = json.load(f)
                        scenario['terrain_type'] = terrain
                        difficult.append(scenario)
        
        logger.info(f"A*が失敗した困難シナリオ: {len(difficult)}個")
        
        # さらに、A*は成功したが時間がかかったシナリオも追加
        for terrain in target_terrains:
            if terrain not in phase2_data['results']:
                continue
            
            astar_results = phase2_data['results'][terrain].get('A*', [])
            
            for result in astar_results:
                if result.get('success', False) and result.get('computation_time', 0) > 100:
                    scenario_file = Path(f'../scenarios/validated/{terrain}/scenario_{result["scenario_id"]:03d}.json')
                    if scenario_file.exists():
                        with open(scenario_file) as f:
                            scenario = json.load(f)
                        scenario['terrain_type'] = terrain
                        difficult.append(scenario)
        
        logger.info(f"困難シナリオ合計: {len(difficult)}個")
        
        return difficult[:30]  # 最大30シナリオ
    
    def _compare_algorithms(self, scenario):
        """A*とTA-A*を比較"""
        logger.info(f"\nシナリオ {scenario.get('scenario_id', '?')}: {scenario.get('terrain_type', '?')}")
        
        # 初期化
        map_bounds = ([-25, -25, 0], [25, 25, 5])
        
        astar = AStarPlanner3D(voxel_size=0.2, map_bounds=map_bounds)
        tastar = TerrainAwareAStarPlanner3D(voxel_size=0.2, map_bounds=map_bounds)
        
        # A*実行
        logger.info("  A*実行中...")
        astar_result = astar.plan_path(
            start=scenario['start'],
            goal=scenario['goal'],
            terrain_data=None,
            timeout=1800
        )
        
        # TA-A*実行
        logger.info("  TA-A*実行中...")
        tastar_result = tastar.plan_path(
            start=scenario['start'],
            goal=scenario['goal'],
            terrain_data=None,
            timeout=1800
        )
        
        # 比較結果を記録
        comparison = {
            'scenario_id': scenario.get('scenario_id'),
            'terrain_type': scenario.get('terrain_type'),
            'distance': scenario.get('distance', 0),
            'astar': {
                'success': astar_result.success,
                'time': astar_result.computation_time,
                'length': astar_result.path_length if astar_result.success else 0,
                'nodes': astar_result.nodes_explored
            },
            'tastar': {
                'success': tastar_result.success,
                'time': tastar_result.computation_time,
                'length': tastar_result.path_length if tastar_result.success else 0,
                'nodes': tastar_result.nodes_explored,
                'risk': tastar_result.risk_score if tastar_result.success else 0
            }
        }
        
        # 優位性を計算
        if astar_result.success and tastar_result.success:
            comparison['length_diff_pct'] = (tastar_result.path_length - astar_result.path_length) / astar_result.path_length * 100
            comparison['time_ratio'] = tastar_result.computation_time / astar_result.computation_time
        elif tastar_result.success and not astar_result.success:
            comparison['tastar_advantage'] = 'TA-A* succeeded where A* failed'
        
        self.results.append(comparison)
        
        logger.info(f"  A*: {'✅' if astar_result.success else '❌'} {astar_result.computation_time:.2f}s")
        logger.info(f"  TA-A*: {'✅' if tastar_result.success else '❌'} {tastar_result.computation_time:.2f}s")
    
    def _save_results(self):
        """結果を保存"""
        output_path = Path('../results/phase3_tastar_superiority.json')
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"結果を保存: {output_path}")
    
    def _print_summary(self):
        """サマリー表示"""
        logger.info("\n" + "="*70)
        logger.info("Phase 3 サマリー")
        logger.info("="*70)
        
        total = len(self.results)
        tastar_success = sum(1 for r in self.results if r['tastar']['success'])
        astar_success = sum(1 for r in self.results if r['astar']['success'])
        
        logger.info(f"総シナリオ数: {total}")
        logger.info(f"A*成功: {astar_success}/{total} ({astar_success/total*100:.1f}%)")
        logger.info(f"TA-A*成功: {tastar_success}/{total} ({tastar_success/total*100:.1f}%)")
        
        # TA-A*だけが成功したケース
        tastar_only = sum(1 for r in self.results if r['tastar']['success'] and not r['astar']['success'])
        if tastar_only > 0:
            logger.info(f"TA-A*のみ成功: {tastar_only}個")
        
        logger.info("\n✅ Phase 3完了")

if __name__ == '__main__':
    experiment = TAAStarSuperiorityExperiment()
    experiment.run_experiment()



