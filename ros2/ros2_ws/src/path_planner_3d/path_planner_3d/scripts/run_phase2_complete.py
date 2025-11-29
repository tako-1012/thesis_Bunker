#!/usr/bin/env python3
"""
Phase 2 Complete Validation

200実験を自動実行し、論文用データを生成
"""
import sys
import csv
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# tqdmのインポート（なければプログレス表示なし）
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("tqdm not installed. Progress bar disabled.")
    print("Install: pip3 install tqdm")

# パス追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# プランナーインポート
from tastar_optimized import TerrainAwareAStarOptimized
from config import PlannerConfig

class Phase2Complete:
    """Phase 2完全検証"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
        
        # アルゴリズム初期化
        self.planners = {
            'TA-A* Optimized': TerrainAwareAStarOptimized(
                map_bounds=([-50, -50, 0], [50, 50, 10]),
                voxel_size=0.2
            ),
            'A*': None  # A*は使わない（importエラー回避のため）
        }
        
        # 地形定義
        self.terrains = [
            'flat_agricultural_field',
            'gentle_hills',
            'steep_terrain',
            'complex_obstacles',
            'extreme_hazards'
        ]
        
        # シナリオ生成
        self.scenarios = self._generate_scenarios()
        
    def _generate_scenarios(self):
        """シナリオ生成"""
        scenarios = []
        np.random.seed(42)
        
        for terrain in self.terrains:
            for trial in range(1, 11):  # 各地形10回
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
                
                # 最低距離チェック
                dist = np.linalg.norm(np.array(goal) - np.array(start))
                if dist < 5.0:  # 距離が短すぎる場合は再生成
                    goal = [
                        start[0] + np.random.uniform(5, 15),
                        start[1] + np.random.uniform(5, 15),
                        0.2
                    ]
                
                scenarios.append({
                    'terrain': terrain,
                    'trial': trial,
                    'start': start,
                    'goal': goal
                })
        
        return scenarios
    
    def run_experiments(self, test_mode=False):
        """実験実行"""
        print("="*70)
        print("Phase 2 Complete Validation")
        print("="*70)
        
        total = len(self.scenarios) * len(self.planners) if not test_mode else 2
        print(f"\n総実験数: {total}")
        if test_mode:
            print("⚠️ TEST MODE: 2実験のみ実行")
        print()
        
        count = 0
        iterator = self.scenarios if not test_mode else self.scenarios[:2]
        
        # tqdm使用
        if HAS_TQDM:
            pbar = tqdm(total=total, desc="Progress")
        
        for scenario in iterator:
            for algo_name, planner in self.planners.items():
                if planner is None:
                    continue  # A*をスキップ
                
                count += 1
                
                if HAS_TQDM:
                    pbar.set_description(f"{scenario['terrain']} + {algo_name}")
                
                try:
                    start_t = time.time()
                    result = planner.plan_path(
                        scenario['start'],
                        scenario['goal'],
                        timeout=60
                    )
                    elapsed = time.time() - start_t
                    
                    self.results.append({
                        'terrain': scenario['terrain'],
                        'algorithm': algo_name,
                        'trial': scenario['trial'],
                        'success': result.success,
                        'computation_time': elapsed,
                        'path_length': result.path_length if result.success else 0,
                        'nodes_explored': result.nodes_explored
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
                
                # 中間保存（10実験ごと）
                if count % 10 == 0:
                    self._save_intermediate()
                
                if HAS_TQDM:
                    pbar.update(1)
        
        if HAS_TQDM:
            pbar.close()
        
        print("\n" + "="*70)
        print("実験完了")
        print("="*70)
        
        # 結果保存
        self._save_results()
        
        # 統計分析
        self._analyze_results()
        
        # レポート生成
        self._generate_report()
    
    def _save_intermediate(self):
        """中間保存"""
        output_dir = Path('../results/phase2_complete')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # CSV保存
        csv_file = output_dir / 'raw_data.csv'
        with open(csv_file, 'w', newline='') as f:
            if self.results:
                writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
                writer.writeheader()
                writer.writerows(self.results)
    
    def _save_results(self):
        """結果保存"""
        self._save_intermediate()
        
        # CSV保存
        csv_file = Path('../results/phase2_complete/raw_data.csv')
        
        # JSON保存
        json_file = Path('../results/phase2_complete/raw_data.json')
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n✅ 結果保存:")
        print(f"  - {csv_file}")
        print(f"  - {json_file}")
    
    def _analyze_results(self):
        """統計分析"""
        print("\n" + "="*70)
        print("統計分析")
        print("="*70)
        
        df = pd.DataFrame(self.results)
        
        for algo_name in self.planners.keys():
            if algo_name not in df['algorithm'].values:
                continue
            
            algo_results = df[df['algorithm'] == algo_name]
            
            success_count = algo_results['success'].sum()
            total = len(algo_results)
            success_rate = success_count / total * 100
            
            successful_results = algo_results[algo_results['success']]
            if len(successful_results) > 0:
                avg_time = successful_results['computation_time'].mean()
                std_time = successful_results['computation_time'].std()
                avg_nodes = successful_results['nodes_explored'].mean()
            else:
                avg_time = std_time = avg_nodes = 0
            
            print(f"\n{algo_name}:")
            print(f"  成功率: {success_rate:.1f}% ({success_count}/{total})")
            print(f"  平均処理時間: {avg_time:.3f}秒 (std: {std_time:.3f})")
            print(f"  平均探索ノード: {avg_nodes:.0f}")
    
    def _generate_report(self):
        """レポート生成"""
        report = f"""
# Phase 2 Complete Validation Report

**生成日**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

### Experiments
- Total: {len(self.results)}
- Success: {sum(1 for r in self.results if r['success'])}
- Failed: {sum(1 for r in self.results if not r['success'])}

### Results
"""
        
        df = pd.DataFrame(self.results)
        
        for algo_name in df['algorithm'].unique():
            algo_results = df[df['algorithm'] == algo_name]
            success_count = algo_results['success'].sum()
            total = len(algo_results)
            success_rate = success_count / total * 100
            
            successful_results = algo_results[algo_results['success']]
            if len(successful_results) > 0:
                avg_time = successful_results['computation_time'].mean()
                report += f"\n### {algo_name}\n"
                report += f"- Success rate: {success_rate:.1f}%\n"
                report += f"- Avg time: {avg_time:.3f}s\n\n"
        
        # 保存
        report_file = Path('../reports/phase2_complete_report.md')
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"✅ レポート生成: {report_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='Test mode (2 experiments only)')
    args = parser.parse_args()
    
    validator = Phase2Complete()
    validator.run_experiments(test_mode=args.test)

if __name__ == '__main__':
    main()

