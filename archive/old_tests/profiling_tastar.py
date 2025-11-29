#!/usr/bin/env python3
"""
TA-A* 詳細性能分析

目的:
TA-A*の処理時間が長い原因を特定し、最適化の方向性を明確にする。

実行方法:
python3 profiling_tastar.py
"""

import cProfile
import pstats
import io
import time
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

# パスの追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from path_planner_3d.terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D
from path_planner_3d.astar_planner import AStarPlanner3D

class ProfilingAnalyzer:
    """TA-A*のプロファイリング分析"""
    
    def __init__(self):
        self.results = {}
        self.profile_data = {}
        
    def run_comprehensive_profiling(self):
        """包括的なプロファイリング"""
        print("="*70)
        print("TA-A* 詳細性能分析")
        print("="*70)
        
        # 設定
        from config import PlannerConfig
        config = PlannerConfig(
            map_bounds=([-50, -50, 0], [50, 50, 10]),
            voxel_size=0.1
        )
        
        # アルゴリズム初期化
        # TA-A*は古いAPIを使用
        tastar = TerrainAwareAStarPlanner3D(
            map_bounds=([-50, -50, 0], [50, 50, 10]),
            voxel_size=0.1
        )
        
        # A*は新しいAPIを使用
        astar = AStarPlanner3D(config)
        
        # テストシナリオ
        scenarios = [
            ([0, 0, 0.2], [10, 10, 0.2], "Short"),
            ([0, 0, 0.2], [20, 20, 0.2], "Medium"),
            ([-20, -20, 0.2], [20, 20, 0.2], "Long")
        ]
        
        for start, goal, name in scenarios:
            print(f"\n{'#'*70}")
            print(f"# {name} Distance Scenario")
            print(f"{'#'*70}")
            
            # TA-A* プロファイリング
            print(f"\n[TA-A*]")
            self.profile_algorithm(tastar, start, goal, "TA-A*", name)
            
            # A* プロファイリング（比較用）
            print(f"\n[A* (Baseline)]")
            self.profile_algorithm(astar, start, goal, "A*", name)
        
        # 詳細分析
        self.analyze_profiling_results()
        self.generate_optimization_report()
    
    def profile_algorithm(self, planner, start, goal, algo_name, scenario_name):
        """アルゴリズムのプロファイリング"""
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            result = planner.plan_path(start, goal, timeout=60)
            computation_time = result.computation_time if result.success else 60.0
            
            profiler.disable()
            
            # プロファイル結果を解析
            s = io.StringIO()
            stats = pstats.Stats(profiler, stream=s)
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.print_stats(30)  # トップ30
            
            profile_output = s.getvalue()
            
            # 結果を保存
            key = f"{algo_name}_{scenario_name}"
            self.results[key] = {
                'success': result.success,
                'computation_time': computation_time,
                'nodes_explored': result.nodes_explored if result.success else 0,
                'path_length': result.path_length if result.success else 0,
                'profile_output': profile_output
            }
            
            # ボトルネック分析
            bottlenecks = self.extract_bottlenecks(stats)
            self.results[key]['bottlenecks'] = bottlenecks
            
            # 結果を表示
            status = "✅" if result.success else "❌"
            print(f"  {status} Time: {computation_time:.2f}s")
            print(f"  Nodes: {result.nodes_explored if result.success else 'N/A'}")
            print(f"  Path length: {result.path_length if result.success else 'N/A'}")
            
            # トップ5ボトルネック
            print(f"\n  Top 5 Bottlenecks:")
            for i, (func, (call_count, total_time, per_call_time)) in enumerate(bottlenecks[:5], 1):
                print(f"    {i}. {func}: {total_time:.3f}s ({call_count} calls)")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            profiler.disable()
    
    def extract_bottlenecks(self, stats) -> List[Tuple[str, Tuple[int, float, float]]]:
        """ボトルネックを抽出"""
        bottlenecks = []
        
        for func, (call_count, total_time, cumulative_time, _, _) in stats.stats.items():
            per_call_time = total_time / call_count if call_count > 0 else 0
            
            func_name = f"{func[2]} in {func[0]}"
            
            bottlenecks.append((func_name, (call_count, total_time, per_call_time)))
        
        # 累積時間でソート
        bottlenecks.sort(key=lambda x: x[1][1], reverse=True)
        
        return bottlenecks
    
    def analyze_profiling_results(self):
        """プロファイリング結果の分析"""
        print("\n" + "="*70)
        print("詳細分析")
        print("="*70)
        
        # TA-A*とA*の比較
        print("\n【TA-A* vs A* 比較】")
        
        for scenario in ['Short', 'Medium', 'Long']:
            tastar_key = f"TA-A*_{scenario}"
            astar_key = f"A*_{scenario}"
            
            if tastar_key in self.results and astar_key in self.results:
                tastar_time = self.results[tastar_key]['computation_time']
                astar_time = self.results[astar_key]['computation_time']
                
                if tastar_time > 0 and astar_time > 0:
                    slowdown = tastar_time / astar_time
                    print(f"\n{scenario}:")
                    print(f"  TA-A*: {tastar_time:.2f}s")
                    print(f"  A*: {astar_time:.2f}s")
                    print(f"  → TA-A*は{slowdown:.1f}倍遅い")
    
    def generate_optimization_report(self):
        """最適化レポートの生成"""
        print("\n" + "="*70)
        print("最適化提案")
        print("="*70)
        
        # 全ボトルネックを集約
        all_bottlenecks = defaultdict(lambda: {'calls': 0, 'total_time': 0.0})
        
        for key, data in self.results.items():
            if 'bottlenecks' in data:
                for func, (call_count, total_time, _) in data['bottlenecks']:
                    all_bottlenecks[func]['calls'] += call_count
                    all_bottlenecks[func]['total_time'] += total_time
        
        # ソート
        sorted_bottlenecks = sorted(
            all_bottlenecks.items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        )
        
        # トップ10を表示
        print("\n【Top 10 Bottlenecks Across All Tests】")
        for i, (func, data) in enumerate(sorted_bottlenecks[:10], 1):
            avg_per_call = data['total_time'] / data['calls'] if data['calls'] > 0 else 0
            print(f"\n{i}. {func}")
            print(f"   Total time: {data['total_time']:.3f}s")
            print(f"   Call count: {data['calls']:,}")
            print(f"   Avg per call: {avg_per_call*1000:.2f}ms")
        
        # 最適化提案
        print("\n" + "="*70)
        print("推奨される最適化")
        print("="*70)
        
        optimization_suggestions = [
            {
                'title': '地形評価のキャッシング',
                'description': '同じ位置の地形評価を複数回行わない',
                'expected_speedup': '2-3x',
                'difficulty': '低',
                'priority': '高'
            },
            {
                'title': 'ヒューリスティックの簡略化',
                'description': '複雑な地形適応ヒューリスティックを簡略版に',
                'expected_speedup': '1.5-2x',
                'difficulty': '中',
                'priority': '高'
            },
            {
                'title': '探索範囲の制限',
                'description': '26近傍から14近傍に減らす',
                'expected_speedup': '1.3-1.5x',
                'difficulty': '低',
                'priority': '中'
            },
            {
                'title': '早期終了判定',
                'description': '十分な候補が見つかったら探索を終了',
                'expected_speedup': '1.2-1.4x',
                'difficulty': '中',
                'priority': '中'
            },
            {
                'title': 'コスト関数の簡略化',
                'description': '詳細な地形分析を簡易版に',
                'expected_speedup': '1.5-2x',
                'difficulty': '中',
                'priority': '中'
            }
        ]
        
        for i, suggestion in enumerate(optimization_suggestions, 1):
            print(f"\n{i}. {suggestion['title']}")
            print(f"   説明: {suggestion['description']}")
            print(f"   期待効果: {suggestion['expected_speedup']}")
            print(f"   難易度: {suggestion['difficulty']}")
            print(f"   優先度: {suggestion['priority']}")
        
        # レポートを保存
        self.save_optimization_report(sorted_bottlenecks, optimization_suggestions)
    
    def save_optimization_report(self, bottlenecks, suggestions):
        """最適化レポートを保存"""
        report_path = Path('../results/optimization_report.md')
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# TA-A* 最適化レポート\n\n")
            f.write(f"生成日: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 1. Top 10 Bottlenecks\n\n")
            for i, (func, data) in enumerate(bottlenecks[:10], 1):
                f.write(f"### {i}. {func}\n\n")
                f.write(f"- Total time: {data['total_time']:.3f}s\n")
                f.write(f"- Call count: {data['calls']:,}\n")
                f.write(f"- Avg per call: {data['total_time']/data['calls']*1000:.2f}ms\n\n")
            
            f.write("## 2. 最適化提案\n\n")
            for i, suggestion in enumerate(suggestions, 1):
                f.write(f"### {i}. {suggestion['title']}\n\n")
                f.write(f"**説明**: {suggestion['description']}\n\n")
                f.write(f"**期待効果**: {suggestion['expected_speedup']}\n\n")
                f.write(f"**難易度**: {suggestion['difficulty']}\n\n")
                f.write(f"**優先度**: {suggestion['priority']}\n\n")
        
        print(f"\n✅ レポート保存: {report_path}")

def main():
    analyzer = ProfilingAnalyzer()
    analyzer.run_comprehensive_profiling()

if __name__ == '__main__':
    main()

