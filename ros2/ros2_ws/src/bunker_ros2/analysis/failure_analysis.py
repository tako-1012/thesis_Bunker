"""
失敗ケース詳細分析

失敗した経路計画の原因を詳細に分析
"""
import numpy as np
import json
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class FailureCaseAnalyzer:
    """失敗ケース分析クラス"""
    
    def __init__(self, results_file: str):
        """
        初期化
        
        Args:
            results_file: 実験結果ファイル
        """
        with open(results_file) as f:
            self.data = json.load(f)
    
    def analyze_failure_patterns(self) -> Dict:
        """
        失敗パターンの分析
        
        Returns:
            Dict: 失敗分析結果
        """
        print("\n" + "="*70)
        print("失敗ケース詳細分析")
        print("="*70)
        
        # 全アルゴリズムの失敗ケースを集める
        failure_data = {}
        
        if 'results' not in self.data:
            return {}
        
        # 最初の地形から全アルゴリズムを取得
        first_terrain = list(self.data['results'].keys())[0]
        algorithms = list(self.data['results'][first_terrain].keys())
        
        for algo in algorithms:
            failure_data[algo] = []
        
        # 全地形から失敗ケースを集める
        for terrain, terrain_results in self.data['results'].items():
            for algo in algorithms:
                if algo in terrain_results:
                    for result in terrain_results[algo]:
                        if not result.get('success', False):
                            failure_data[algo].append({
                                'terrain': terrain,
                                'scenario_id': result.get('scenario_id', -1),
                                'error_message': result.get('error_message', ''),
                                'computation_time': result.get('computation_time', 0),
                                'distance': result.get('distance', 0),
                                'max_slope': result.get('max_slope', 0)
                            })
        
        # 各アルゴリズムの失敗率計算
        print(f"\n各アルゴリズムの失敗率:")
        for algo in algorithms:
            failures = failure_data[algo]
            total_cases = 0
            
            # 全地形での総ケース数を計算
            for terrain, terrain_results in self.data['results'].items():
                if algo in terrain_results:
                    total_cases += len(terrain_results[algo])
            
            failure_rate = (len(failures) / total_cases * 100) if total_cases > 0 else 0
            
            print(f"\n{algo}:")
            print(f"  失敗ケース数: {len(failures)}")
            print(f"  総ケース数: {total_cases}")
            print(f"  失敗率: {failure_rate:.1f}%")
        
        # 失敗原因の分析
        print(f"\n失敗原因分析:")
        error_patterns = {}
        
        for algo in algorithms:
            failures = failure_data[algo]
            if not failures:
                continue
            
            error_counts = {}
            for failure in failures:
                error_msg = failure['error_message']
                if error_msg in error_counts:
                    error_counts[error_msg] += 1
                else:
                    error_counts[error_msg] = 1
            
            error_patterns[algo] = error_counts
            
            print(f"\n{algo} の失敗原因:")
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(failures)) * 100
                print(f"  {error}: {count}回 ({percentage:.1f}%)")
        
        # 地形別失敗率分析
        print(f"\n地形別失敗率分析:")
        terrain_failure_rates = {}
        
        for terrain in ['flat_agricultural_field', 'gentle_hills', 'steep_terrain', 
                       'complex_obstacles', 'extreme_hazards']:
            if terrain not in self.data['results']:
                continue
            
            terrain_results = self.data['results'][terrain]
            terrain_failure_rates[terrain] = {}
            
            print(f"\n{terrain}:")
            for algo in algorithms:
                if algo in terrain_results:
                    results = terrain_results[algo]
                    failures = [r for r in results if not r.get('success', False)]
                    failure_rate = (len(failures) / len(results)) * 100
                    
                    terrain_failure_rates[terrain][algo] = failure_rate
                    print(f"  {algo}: {len(failures)}/{len(results)} ({failure_rate:.1f}%)")
        
        # 距離・勾配と失敗率の関係
        print(f"\n距離・勾配と失敗率の関係:")
        
        for algo in algorithms:
            failures = failure_data[algo]
            if not failures:
                continue
            
            distances = [f['distance'] for f in failures if f['distance'] > 0]
            slopes = [f['max_slope'] for f in failures if f['max_slope'] > 0]
            
            if distances:
                print(f"\n{algo} 失敗ケースの距離分布:")
                print(f"  平均距離: {np.mean(distances):.1f}m")
                print(f"  最大距離: {np.max(distances):.1f}m")
                print(f"  最小距離: {np.min(distances):.1f}m")
            
            if slopes:
                print(f"\n{algo} 失敗ケースの勾配分布:")
                print(f"  平均勾配: {np.mean(slopes):.1f}°")
                print(f"  最大勾配: {np.max(slopes):.1f}°")
                print(f"  最小勾配: {np.min(slopes):.1f}°")
        
        return {
            'failure_data': failure_data,
            'error_patterns': error_patterns,
            'terrain_failure_rates': terrain_failure_rates
        }
    
    def analyze_timeout_cases(self) -> Dict:
        """
        タイムアウトケースの分析
        
        Returns:
            Dict: タイムアウト分析結果
        """
        print(f"\n" + "="*70)
        print("タイムアウトケース分析")
        print("="*70)
        
        timeout_cases = {}
        
        if 'results' not in self.data:
            return {}
        
        # 最初の地形から全アルゴリズムを取得
        first_terrain = list(self.data['results'].keys())[0]
        algorithms = list(self.data['results'][first_terrain].keys())
        
        for algo in algorithms:
            timeout_cases[algo] = []
        
        # タイムアウトケースを集める
        for terrain, terrain_results in self.data['results'].items():
            for algo in algorithms:
                if algo in terrain_results:
                    for result in terrain_results[algo]:
                        if (not result.get('success', False) and 
                            'timeout' in result.get('error_message', '').lower()):
                            timeout_cases[algo].append({
                                'terrain': terrain,
                                'scenario_id': result.get('scenario_id', -1),
                                'computation_time': result.get('computation_time', 0),
                                'distance': result.get('distance', 0),
                                'max_slope': result.get('max_slope', 0)
                            })
        
        # タイムアウト率計算
        print(f"\n各アルゴリズムのタイムアウト率:")
        for algo in algorithms:
            timeouts = timeout_cases[algo]
            total_cases = 0
            
            # 全地形での総ケース数を計算
            for terrain, terrain_results in self.data['results'].items():
                if algo in terrain_results:
                    total_cases += len(terrain_results[algo])
            
            timeout_rate = (len(timeouts) / total_cases * 100) if total_cases > 0 else 0
            
            print(f"\n{algo}:")
            print(f"  タイムアウト数: {len(timeouts)}")
            print(f"  総ケース数: {total_cases}")
            print(f"  タイムアウト率: {timeout_rate:.1f}%")
        
        # タイムアウトケースの特徴分析
        print(f"\nタイムアウトケースの特徴:")
        for algo in algorithms:
            timeouts = timeout_cases[algo]
            if not timeouts:
                continue
            
            distances = [t['distance'] for t in timeouts if t['distance'] > 0]
            slopes = [t['max_slope'] for t in timeouts if t['max_slope'] > 0]
            times = [t['computation_time'] for t in timeouts]
            
            print(f"\n{algo} タイムアウトケース:")
            if distances:
                print(f"  平均距離: {np.mean(distances):.1f}m")
                print(f"  距離範囲: {np.min(distances):.1f} - {np.max(distances):.1f}m")
            
            if slopes:
                print(f"  平均勾配: {np.mean(slopes):.1f}°")
                print(f"  勾配範囲: {np.min(slopes):.1f} - {np.max(slopes):.1f}°")
            
            if times:
                print(f"  平均計算時間: {np.mean(times):.1f}s")
                print(f"  時間範囲: {np.min(times):.1f} - {np.max(times):.1f}s")
        
        return {
            'timeout_cases': timeout_cases
        }
    
    def generate_failure_report(self):
        """失敗分析の完全レポートを生成"""
        print("\n" + "="*70)
        print("失敗ケース詳細分析 完全レポート")
        print("="*70)
        
        # 1. 失敗パターン分析
        failure_results = self.analyze_failure_patterns()
        
        # 2. タイムアウトケース分析
        timeout_results = self.analyze_timeout_cases()
        
        # 3. 改善提案
        print(f"\n" + "="*70)
        print("改善提案")
        print("="*70)
        
        if failure_results and timeout_results:
            print(f"\n1. アルゴリズム別改善点:")
            
            # 最初の地形から全アルゴリズムを取得
            first_terrain = list(self.data['results'].keys())[0]
            algorithms = list(self.data['results'][first_terrain].keys())
            
            for algo in algorithms:
                failures = failure_results['failure_data'].get(algo, [])
                timeouts = timeout_results['timeout_cases'].get(algo, [])
                
                print(f"\n{algo}:")
                if failures:
                    print(f"  - 失敗率: {len(failures)}ケース")
                    if timeouts:
                        print(f"  - タイムアウト率: {len(timeouts)}ケース")
                        print(f"  - 改善: タイムアウト時間の延長、探索効率の向上")
                    else:
                        print(f"  - 改善: 探索戦略の見直し、障害物回避の強化")
                else:
                    print(f"  - 良好: 失敗ケースなし")
            
            print(f"\n2. 地形別改善点:")
            terrain_failure_rates = failure_results.get('terrain_failure_rates', {})
            
            for terrain, rates in terrain_failure_rates.items():
                max_failure_algo = max(rates.keys(), key=lambda k: rates[k])
                max_rate = rates[max_failure_algo]
                
                print(f"\n{terrain}:")
                print(f"  - 最高失敗率: {max_failure_algo} ({max_rate:.1f}%)")
                if max_rate > 50:
                    print(f"  - 改善: この地形でのアルゴリズム改良が必要")
                elif max_rate > 20:
                    print(f"  - 改善: パラメータ調整で改善可能")
                else:
                    print(f"  - 良好: 失敗率は許容範囲")
            
            print(f"\n3. 全体的な改善提案:")
            print(f"  - タイムアウト時間の動的調整")
            print(f"  - 探索範囲の最適化")
            print(f"  - 障害物回避アルゴリズムの強化")
            print(f"  - 複雑な地形での事前処理")
        
        print("\n" + "="*70)
        print("✅ 失敗分析完了")
        print("="*70)

if __name__ == '__main__':
    analyzer = FailureCaseAnalyzer('../results/efficient_terrain_results.json')
    analyzer.generate_failure_report()



