"""
エラー分析

失敗・タイムアウト・異常ケースの詳細分析
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt

class ErrorAnalyzer:
    """エラー分析クラス"""
    
    def __init__(self, results_file: str):
        """初期化"""
        with open(results_file) as f:
            self.data = json.load(f)
    
    def analyze_all_errors(self) -> Dict:
        """全エラーを分析"""
        print("="*70)
        print("エラー分析")
        print("="*70)
        
        analysis = {
            'timeout_analysis': self._analyze_timeouts(),
            'failure_analysis': self._analyze_failures(),
            'anomaly_detection': self._detect_anomalies(),
            'correlation_analysis': self._analyze_correlations()
        }
        
        return analysis
    
    def _analyze_timeouts(self) -> Dict:
        """タイムアウトケースを分析"""
        print("\n【タイムアウト分析】")
        
        timeouts_by_algo = {}
        timeouts_by_terrain = {}
        timeout_distances = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            for algo, algo_results in terrain_results.items():
                for result in algo_results:
                    error_msg = result.get('error_message', '').lower()
                    
                    if 'timeout' in error_msg:
                        # アルゴリズム別
                        if algo not in timeouts_by_algo:
                            timeouts_by_algo[algo] = 0
                        timeouts_by_algo[algo] += 1
                        
                        # 地形別
                        if terrain not in timeouts_by_terrain:
                            timeouts_by_terrain[terrain] = 0
                        timeouts_by_terrain[terrain] += 1
                        
                        # 距離
                        if 'distance' in result:
                            timeout_distances.append(result['distance'])
        
        print("\nアルゴリズム別タイムアウト数:")
        for algo, count in sorted(timeouts_by_algo.items(), key=lambda x: x[1], reverse=True):
            print(f"  {algo:20s}: {count}回")
        
        print("\n地形別タイムアウト数:")
        for terrain, count in sorted(timeouts_by_terrain.items(), key=lambda x: x[1], reverse=True):
            print(f"  {terrain:30s}: {count}回")
        
        if timeout_distances:
            print(f"\nタイムアウト時の距離統計:")
            print(f"  平均: {np.mean(timeout_distances):.1f}m")
            print(f"  中央値: {np.median(timeout_distances):.1f}m")
            print(f"  最小: {np.min(timeout_distances):.1f}m")
            print(f"  最大: {np.max(timeout_distances):.1f}m")
        
        return {
            'by_algorithm': timeouts_by_algo,
            'by_terrain': timeouts_by_terrain,
            'distances': timeout_distances
        }
    
    def _analyze_failures(self) -> Dict:
        """失敗ケース（経路なし）を分析"""
        print("\n【失敗分析（経路なし）】")
        
        failures = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            for algo, algo_results in terrain_results.items():
                for result in algo_results:
                    if not result.get('success', False):
                        error_msg = result.get('error_message', '').lower()
                        if 'no path' in error_msg or 'not found' in error_msg:
                            failures.append({
                                'algorithm': algo,
                                'terrain': terrain,
                                'distance': result.get('distance', 0),
                                'error': error_msg
                            })
        
        print(f"\n経路なし失敗数: {len(failures)}")
        
        # 共通パターン分析
        if failures:
            # 最も失敗が多いアルゴリズム
            algo_counts = {}
            for f in failures:
                algo = f['algorithm']
                algo_counts[algo] = algo_counts.get(algo, 0) + 1
            
            print("\nアルゴリズム別:")
            for algo, count in sorted(algo_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {algo}: {count}回")
        
        return {
            'total': len(failures),
            'cases': failures[:10]  # 最初の10件
        }
    
    def _detect_anomalies(self) -> Dict:
        """異常ケースを検出"""
        print("\n【異常検出】")
        
        anomalies = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            for algo, algo_results in terrain_results.items():
                for result in algo_results:
                    if result.get('success', False):
                        time = result.get('computation_time', 0)
                        length = result.get('path_length', 0)
                        distance = result.get('distance', 0)
                        
                        # 異常1: 経路長が直線距離の5倍以上
                        if distance > 0 and length > distance * 5:
                            anomalies.append({
                                'type': 'excessive_detour',
                                'algorithm': algo,
                                'terrain': terrain,
                                'ratio': length / distance,
                                'details': f'経路長が直線距離の{length/distance:.1f}倍'
                            })
                        
                        # 異常2: 極端に遅い計算時間
                        if time > 100:  # 100秒以上
                            anomalies.append({
                                'type': 'slow_computation',
                                'algorithm': algo,
                                'terrain': terrain,
                                'time': time,
                                'details': f'{time:.0f}秒かかった'
                            })
        
        print(f"\n検出された異常: {len(anomalies)}件")
        
        if anomalies:
            print("\n主な異常:")
            for i, anomaly in enumerate(anomalies[:5]):
                print(f"  {i+1}. {anomaly['type']}: {anomaly['details']}")
                print(f"     {anomaly['algorithm']} on {anomaly['terrain']}")
        
        return {
            'total': len(anomalies),
            'cases': anomalies
        }
    
    def _analyze_correlations(self) -> Dict:
        """失敗と各要因の相関を分析"""
        print("\n【相関分析】")
        
        # 距離と失敗率の相関
        distance_bins = {}
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            for algo, algo_results in terrain_results.items():
                for result in algo_results:
                    distance = result.get('distance', 0)
                    success = result.get('success', False)
                    
                    # 10m単位でビン分け
                    bin_key = int(distance / 10) * 10
                    
                    if bin_key not in distance_bins:
                        distance_bins[bin_key] = {'total': 0, 'failures': 0}
                    
                    distance_bins[bin_key]['total'] += 1
                    if not success:
                        distance_bins[bin_key]['failures'] += 1
        
        print("\n距離と失敗率の関係:")
        for dist, data in sorted(distance_bins.items()):
            if data['total'] > 0:
                failure_rate = data['failures'] / data['total'] * 100
                print(f"  {dist:3d}-{dist+10:3d}m: {failure_rate:5.1f}% ({data['failures']}/{data['total']})")
        
        return {
            'distance_correlation': distance_bins
        }
    
    def generate_error_report(self, output_file: str = '../results/error_analysis_report.txt'):
        """エラー分析レポートを生成"""
        analysis = self.analyze_all_errors()
        
        with open(output_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("エラー分析レポート\n")
            f.write("="*70 + "\n\n")
            
            # タイムアウト
            f.write("【タイムアウト分析】\n")
            if 'timeout_analysis' in analysis:
                timeouts = analysis['timeout_analysis']
                if 'by_algorithm' in timeouts:
                    f.write("アルゴリズム別:\n")
                    for algo, count in timeouts['by_algorithm'].items():
                        f.write(f"  {algo}: {count}回\n")
            
            # 失敗
            f.write("\n【失敗分析】\n")
            if 'failure_analysis' in analysis:
                failures = analysis['failure_analysis']
                f.write(f"総失敗数: {failures.get('total', 0)}\n")
            
            # 異常
            f.write("\n【異常検出】\n")
            if 'anomaly_detection' in analysis:
                anomalies = analysis['anomaly_detection']
                f.write(f"検出された異常: {anomalies.get('total', 0)}件\n")
        
        print(f"\n✅ エラー分析レポート生成: {output_file}")

if __name__ == '__main__':
    analyzer = ErrorAnalyzer('../results/efficient_terrain_results.json')
    analyzer.generate_error_report()



