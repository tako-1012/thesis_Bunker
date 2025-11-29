#!/usr/bin/env python3
"""
Phase 2 簡易検証システム

目的:
各アルゴリズムの基本性能を比較

注意:
Original TA-A*はタイムアウトするため短いタイムアウト設定
"""
import sys
import csv
import json
import time
from pathlib import Path
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from tastar_optimized import TerrainAwareAStarOptimized
from astar_planner import AStarPlanner3D
from config import PlannerConfig

class Phase2Validator:
    """Phase 2検証システム"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
        self.total_experiments = 0
        self.completed_experiments = 0
        
        # アルゴリズム初期化
        config = PlannerConfig.medium_scale()
        
        self.planners = {
            'TA-A* Optimized': TerrainAwareAStarOptimized(
                map_bounds=([-50, -50, 0], [50, 50, 10]),
                voxel_size=0.2
            ),
            'A*': AStarPlanner3D(config)
        }
        
        # テストシナリオ（簡易版）
        self.scenarios = self._generate_scenarios()
        
    def _generate_scenarios(self):
        """テストシナリオ生成"""
        scenarios = []
        
        # 各地形から3シナリオ
        terrains = ['flat', 'hills', 'steep', 'complex', 'extreme']
        
        np.random.seed(42)
        for terrain in terrains:
            for i in range(3):
                # ランダムなスタート・ゴール
                start = [
                    np.random.uniform(-40, 40),
                    np.random.uniform(-40, 40),
                    0.2
                ]
                goal = [
                    np.random.uniform(-40, 40),
                    np.random.uniform(-40, 40),
                    0.2
                ]
                
                scenarios.append({
                    'terrain': terrain,
                    'trial': i + 1,
                    'start': start,
                    'goal': goal
                })
        
        return scenarios
    
    def run_experiments(self):
        """全実験実行"""
        print("="*70)
        print("Phase 2 簡易検証実験")
        print("="*70)
        print(f"\n実験数: {len(self.scenarios)} シナリオ × {len(self.planners)} アルゴリズム")
        print(f"合計: {len(self.scenarios) * len(self.planners)} 実験\n")
        
        self.total_experiments = len(self.scenarios) * len(self.planners)
        
        for scenario_idx, scenario in enumerate(self.scenarios):
            for algo_name, planner in self.planners.items():
                self.completed_experiments += 1
                
                # プログレス表示
                progress = self.completed_experiments / self.total_experiments * 100
                print(f"\r[{progress:5.1f}%] {scenario['terrain']} | {algo_name} | Trial {scenario['trial']}", end=' ', flush=True)
                
                try:
                    start_t = time.time()
                    result = planner.plan_path(
                        scenario['start'],
                        scenario['goal'],
                        timeout=10 if 'Optimized' in algo_name else 30
                    )
                    elapsed = time.time() - start_t
                    
                    self.results.append({
                        'terrain': scenario['terrain'],
                        'algorithm': algo_name,
                        'trial': scenario['trial'],
                        'success': result.success,
                        'computation_time': elapsed,
                        'path_length': result.path_length if result.success else 0,
                        'nodes_explored': result.nodes_explored,
                        'error': result.error_message if not result.success else ''
                    })
                    
                except Exception as e:
                    self.results.append({
                        'terrain': scenario['terrain'],
                        'algorithm': algo_name,
                        'trial': scenario['trial'],
                        'success': False,
                        'computation_time': 0,
                        'path_length': 0,
                        'nodes_explored': 0,
                        'error': str(e)
                    })
        
        print("\n" + "="*70)
        print("実験完了")
        print("="*70)
        
        # 結果を保存
        self.save_results()
        
        # サマリー表示
        self.print_summary()
    
    def save_results(self):
        """結果を保存"""
        output_dir = Path('../results/phase2_full')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # CSV保存
        csv_file = output_dir / 'raw_data.csv'
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
            writer.writeheader()
            writer.writerows(self.results)
        
        # JSON保存
        json_file = output_dir / 'raw_data.json'
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n✅ 結果保存:")
        print(f"  - {csv_file}")
        print(f"  - {json_file}")
    
    def print_summary(self):
        """サマリー表示"""
        print("\n" + "="*70)
        print("結果サマリー")
        print("="*70)
        
        for algo_name in self.planners.keys():
            algo_results = [r for r in self.results if r['algorithm'] == algo_name]
            
            success_count = sum(1 for r in algo_results if r['success'])
            total = len(algo_results)
            success_rate = success_count / total * 100 if total > 0 else 0
            
            successful_results = [r for r in algo_results if r['success']]
            if successful_results:
                avg_time = np.mean([r['computation_time'] for r in successful_results])
            else:
                avg_time = 0
            
            print(f"\n{algo_name}:")
            print(f"  成功率: {success_rate:.1f}% ({success_count}/{total})")
            print(f"  平均処理時間: {avg_time:.3f}秒")
        
        print("\n" + "="*70)

def main():
    validator = Phase2Validator()
    validator.run_experiments()

if __name__ == '__main__':
    main()


