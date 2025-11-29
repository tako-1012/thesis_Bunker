"""
パラメータ感度分析

TA-A*のパラメータが性能に与える影響を分析
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt

class ParameterSensitivityAnalyzer:
    """パラメータ感度分析クラス"""
    
    def __init__(self):
        """初期化"""
        self.results_file = Path('../results/efficient_terrain_results.json')
    
    def analyze_sensitivity(self) -> Dict:
        """
        パラメータ感度を分析
        
        Returns:
            Dict: 分析結果
        """
        print("="*70)
        print("🔍 パラメータ感度分析")
        print("="*70)
        
        if not self.results_file.exists():
            print("❌ 結果ファイルが見つかりません")
            return {}
        
        with open(self.results_file) as f:
            data = json.load(f)
        
        # TA-A*の結果を抽出
        tastar_results = self._extract_tastar_results(data)
        
        if not tastar_results:
            print("⚠️ TA-A*の結果が見つかりません")
            return {}
        
        analysis = {
            'total_scenarios': len(tastar_results),
            'success_rate': self._calculate_success_rate(tastar_results),
            'performance_by_terrain': self._analyze_by_terrain(tastar_results),
            'performance_by_distance': self._analyze_by_distance(tastar_results),
            'computation_time_stats': self._analyze_computation_time(tastar_results),
            'path_length_stats': self._analyze_path_length(tastar_results),
            'risk_score_stats': self._analyze_risk_scores(tastar_results),
            'recommendations': self._generate_parameter_recommendations(tastar_results)
        }
        
        self._print_analysis(analysis)
        
        # 結果を保存
        output_file = Path('../results/parameter_sensitivity_analysis.json')
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n✅ パラメータ感度分析完了: {output_file}")
        
        return analysis
    
    def _extract_tastar_results(self, data: Dict) -> List[Dict]:
        """TA-A*の結果を抽出"""
        tastar_results = []
        
        if 'results' not in data:
            return tastar_results
        
        for terrain, terrain_results in data['results'].items():
            for algo, algo_results in terrain_results.items():
                if 'TA-A*' in algo or 'tastar' in algo.lower():
                    tastar_results.extend(algo_results)
        
        return tastar_results
    
    def _calculate_success_rate(self, results: List[Dict]) -> float:
        """成功率を計算"""
        if not results:
            return 0.0
        
        successes = sum(1 for r in results if r.get('success', False))
        return successes / len(results) * 100
    
    def _analyze_by_terrain(self, results: List[Dict]) -> Dict:
        """地形別性能分析"""
        terrain_stats = {}
        
        for result in results:
            terrain = result.get('terrain_type', 'unknown')
            if terrain not in terrain_stats:
                terrain_stats[terrain] = {
                    'total': 0,
                    'successes': 0,
                    'times': [],
                    'lengths': []
                }
            
            stats = terrain_stats[terrain]
            stats['total'] += 1
            
            if result.get('success', False):
                stats['successes'] += 1
                stats['times'].append(result.get('computation_time', 0))
                stats['lengths'].append(result.get('path_length', 0))
        
        # 統計を計算
        for terrain, stats in terrain_stats.items():
            stats['success_rate'] = stats['successes'] / stats['total'] * 100
            stats['avg_time'] = np.mean(stats['times']) if stats['times'] else 0
            stats['avg_length'] = np.mean(stats['lengths']) if stats['lengths'] else 0
        
        return terrain_stats
    
    def _analyze_by_distance(self, results: List[Dict]) -> Dict:
        """距離別性能分析"""
        distance_ranges = {
            'short (0-20m)': [],
            'medium (20-40m)': [],
            'long (40m+)': []
        }
        
        for result in results:
            distance = result.get('distance', 0)
            if distance < 20:
                distance_ranges['short (0-20m)'].append(result)
            elif distance < 40:
                distance_ranges['medium (20-40m)'].append(result)
            else:
                distance_ranges['long (40m+)'].append(result)
        
        # 各範囲の統計を計算
        range_stats = {}
        for range_name, range_results in distance_ranges.items():
            if range_results:
                successes = sum(1 for r in range_results if r.get('success', False))
                range_stats[range_name] = {
                    'total': len(range_results),
                    'success_rate': successes / len(range_results) * 100,
                    'avg_time': np.mean([r.get('computation_time', 0) for r in range_results if r.get('success', False)])
                }
        
        return range_stats
    
    def _analyze_computation_time(self, results: List[Dict]) -> Dict:
        """計算時間分析"""
        times = [r.get('computation_time', 0) for r in results if r.get('success', False)]
        
        if not times:
            return {}
        
        return {
            'min': min(times),
            'max': max(times),
            'mean': np.mean(times),
            'median': np.median(times),
            'std': np.std(times)
        }
    
    def _analyze_path_length(self, results: List[Dict]) -> Dict:
        """経路長分析"""
        lengths = [r.get('path_length', 0) for r in results if r.get('success', False)]
        
        if not lengths:
            return {}
        
        return {
            'min': min(lengths),
            'max': max(lengths),
            'mean': np.mean(lengths),
            'median': np.median(lengths),
            'std': np.std(lengths)
        }
    
    def _analyze_risk_scores(self, results: List[Dict]) -> Dict:
        """リスクスコア分析"""
        risk_scores = [r.get('risk_score', 0) for r in results if r.get('success', False) and 'risk_score' in r]
        
        if not risk_scores:
            return {}
        
        return {
            'min': min(risk_scores),
            'max': max(risk_scores),
            'mean': np.mean(risk_scores),
            'median': np.median(risk_scores),
            'std': np.std(risk_scores)
        }
    
    def _generate_parameter_recommendations(self, results: List[Dict]) -> List[str]:
        """パラメータ改善提案を生成"""
        recommendations = []
        
        # 成功率が低い場合
        success_rate = self._calculate_success_rate(results)
        if success_rate < 80:
            recommendations.append(f"成功率が{success_rate:.1f}%と低い: タイムアウト時間を延長")
        
        # 計算時間が長い場合
        time_stats = self._analyze_computation_time(results)
        if time_stats and time_stats['mean'] > 10:
            recommendations.append("平均計算時間が長い: アルゴリズムの最適化が必要")
        
        # 特定の地形で性能が悪い場合
        terrain_stats = self._analyze_by_terrain(results)
        worst_terrain = min(terrain_stats.items(), key=lambda x: x[1]['success_rate']) if terrain_stats else None
        if worst_terrain and worst_terrain[1]['success_rate'] < 70:
            recommendations.append(f"{worst_terrain[0]}での成功率が低い: 地形適応パラメータを調整")
        
        return recommendations
    
    def _print_analysis(self, analysis: Dict):
        """分析結果を表示"""
        print(f"\n総シナリオ数: {analysis['total_scenarios']}")
        print(f"成功率: {analysis['success_rate']:.1f}%")
        
        print(f"\n地形別性能:")
        for terrain, stats in analysis['performance_by_terrain'].items():
            print(f"  {terrain}: {stats['success_rate']:.1f}% "
                  f"(平均時間: {stats['avg_time']:.2f}s)")
        
        print(f"\n距離別性能:")
        for distance_range, stats in analysis['performance_by_distance'].items():
            print(f"  {distance_range}: {stats['success_rate']:.1f}%")
        
        if analysis['computation_time_stats']:
            time_stats = analysis['computation_time_stats']
            print(f"\n計算時間統計:")
            print(f"  平均: {time_stats['mean']:.2f}s")
            print(f"  中央値: {time_stats['median']:.2f}s")
            print(f"  最大: {time_stats['max']:.2f}s")
        
        print(f"\n改善提案:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"  {i}. {rec}")

if __name__ == '__main__':
    analyzer = ParameterSensitivityAnalyzer()
    analyzer.analyze_sensitivity()


