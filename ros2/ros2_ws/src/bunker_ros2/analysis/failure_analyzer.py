"""
失敗分析器

実験失敗の詳細分析と改善提案
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt

class FailureAnalyzer:
    """失敗分析クラス"""
    
    def __init__(self):
        """初期化"""
        self.results_file = Path('../results/efficient_terrain_results.json')
    
    def analyze_failures(self) -> Dict:
        """
        失敗を分析
        
        Returns:
            Dict: 分析結果
        """
        print("="*70)
        print("🔍 失敗分析")
        print("="*70)
        
        if not self.results_file.exists():
            print("❌ 結果ファイルが見つかりません")
            return {}
        
        with open(self.results_file) as f:
            data = json.load(f)
        
        failures = self._extract_failures(data)
        
        if not failures:
            print("✅ 失敗なし")
            return {'failures': [], 'analysis': 'No failures detected'}
        
        analysis = {
            'total_failures': len(failures),
            'failure_by_algorithm': self._analyze_by_algorithm(failures),
            'failure_by_terrain': self._analyze_by_terrain(failures),
            'failure_by_distance': self._analyze_by_distance(failures),
            'common_error_patterns': self._analyze_error_patterns(failures),
            'recommendations': self._generate_recommendations(failures)
        }
        
        self._print_analysis(analysis)
        
        # 結果を保存
        output_file = Path('../results/failure_analysis.json')
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n✅ 失敗分析完了: {output_file}")
        
        return analysis
    
    def _extract_failures(self, data: Dict) -> List[Dict]:
        """失敗ケースを抽出"""
        failures = []
        
        if 'results' not in data:
            return failures
        
        for terrain, terrain_results in data['results'].items():
            for algo, algo_results in terrain_results.items():
                for result in algo_results:
                    if not result.get('success', False):
                        failures.append({
                            'terrain': terrain,
                            'algorithm': algo,
                            'scenario_id': result.get('scenario_id', 0),
                            'error_message': result.get('error_message', 'Unknown'),
                            'distance': result.get('distance', 0),
                            'computation_time': result.get('computation_time', 0)
                        })
        
        return failures
    
    def _analyze_by_algorithm(self, failures: List[Dict]) -> Dict:
        """アルゴリズム別失敗分析"""
        algo_failures = {}
        
        for failure in failures:
            algo = failure['algorithm']
            if algo not in algo_failures:
                algo_failures[algo] = 0
            algo_failures[algo] += 1
        
        return algo_failures
    
    def _analyze_by_terrain(self, failures: List[Dict]) -> Dict:
        """地形別失敗分析"""
        terrain_failures = {}
        
        for failure in failures:
            terrain = failure['terrain']
            if terrain not in terrain_failures:
                terrain_failures[terrain] = 0
            terrain_failures[terrain] += 1
        
        return terrain_failures
    
    def _analyze_by_distance(self, failures: List[Dict]) -> Dict:
        """距離別失敗分析"""
        distances = [f['distance'] for f in failures]
        
        if not distances:
            return {}
        
        return {
            'min_distance': min(distances),
            'max_distance': max(distances),
            'avg_distance': np.mean(distances),
            'median_distance': np.median(distances)
        }
    
    def _analyze_error_patterns(self, failures: List[Dict]) -> Dict:
        """エラーパターン分析"""
        error_counts = {}
        
        for failure in failures:
            error = failure['error_message']
            if error not in error_counts:
                error_counts[error] = 0
            error_counts[error] += 1
        
        return error_counts
    
    def _generate_recommendations(self, failures: List[Dict]) -> List[str]:
        """改善提案を生成"""
        recommendations = []
        
        # タイムアウトが多い場合
        timeout_count = sum(1 for f in failures if 'timeout' in f['error_message'].lower())
        if timeout_count > len(failures) * 0.5:
            recommendations.append("タイムアウトが多い: タイムアウト時間を延長またはアルゴリズムを最適化")
        
        # 距離が長い場合の失敗
        long_distance_failures = [f for f in failures if f['distance'] > 30]
        if len(long_distance_failures) > len(failures) * 0.3:
            recommendations.append("長距離での失敗が多い: スケーラビリティを改善")
        
        # 特定の地形での失敗
        terrain_failures = self._analyze_by_terrain(failures)
        worst_terrain = max(terrain_failures.items(), key=lambda x: x[1]) if terrain_failures else None
        if worst_terrain:
            recommendations.append(f"{worst_terrain[0]}での失敗が多い: 地形適応を改善")
        
        return recommendations
    
    def _print_analysis(self, analysis: Dict):
        """分析結果を表示"""
        print(f"\n失敗総数: {analysis['total_failures']}")
        
        print(f"\nアルゴリズム別失敗:")
        for algo, count in analysis['failure_by_algorithm'].items():
            print(f"  {algo}: {count}回")
        
        print(f"\n地形別失敗:")
        for terrain, count in analysis['failure_by_terrain'].items():
            print(f"  {terrain}: {count}回")
        
        if analysis['failure_by_distance']:
            dist = analysis['failure_by_distance']
            print(f"\n距離統計:")
            print(f"  平均: {dist['avg_distance']:.1f}m")
            print(f"  中央値: {dist['median_distance']:.1f}m")
        
        print(f"\nエラーパターン:")
        for error, count in analysis['common_error_patterns'].items():
            print(f"  {error}: {count}回")
        
        print(f"\n改善提案:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"  {i}. {rec}")

if __name__ == '__main__':
    analyzer = FailureAnalyzer()
    analyzer.analyze_failures()


