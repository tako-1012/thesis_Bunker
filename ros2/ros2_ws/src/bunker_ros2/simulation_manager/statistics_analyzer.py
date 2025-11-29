#!/usr/bin/env python3
"""
statistics_analyzer.py
シミュレーション結果の詳細統計解析

機能:
- 記述統計（平均、分散、最小値、最大値、四分位数）
- 地形タイプ別分析
- 難易度別分析
- 相関分析
- 外れ値検出
- 統計的検定
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict
import scipy.stats as stats

from simulation_runner import SimulationResult
from scenario_generator import ScenarioGenerator

@dataclass
class StatisticalSummary:
    """統計サマリー"""
    metric_name: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    q25: float
    median: float
    q75: float
    
class StatisticsAnalyzer:
    """統計解析クラス"""
    
    def __init__(self):
        self.results: List[SimulationResult] = []
        self.scenarios = None
        self.terrain_type_map = {}
    
    def load_data(
        self,
        results_path: str = "results/final_results.json",
        scenarios_path: str = "scenarios"
    ):
        """データ読み込み"""
        # 結果読み込み
        with open(results_path, 'r') as f:
            data = json.load(f)
        self.results = [SimulationResult(**item) for item in data]
        
        # シナリオ読み込み
        generator = ScenarioGenerator()
        self.scenarios = generator.load_scenarios(scenarios_path)
        
        # シナリオID→地形タイプのマッピング作成
        for scenario in self.scenarios:
            self.terrain_type_map[scenario.scenario_id] = {
                'terrain_type': scenario.terrain_params.terrain_type,
                'difficulty': scenario.expected_difficulty,
                'max_slope': scenario.terrain_params.max_slope,
                'obstacle_density': scenario.terrain_params.obstacle_density,
                'roughness': scenario.terrain_params.roughness
            }
        
        print(f"📂 {len(self.results)}件の結果と{len(self.scenarios)}個のシナリオを読み込みました")
    
    def calculate_descriptive_stats(self, metric: str) -> StatisticalSummary:
        """記述統計計算"""
        values = []
        
        if metric == 'computation_time':
            values = [r.computation_time for r in self.results]
        elif metric == 'path_length':
            values = [r.path_length for r in self.results if r.path_found]
        elif metric == 'num_waypoints':
            values = [r.num_waypoints for r in self.results if r.path_found]
        
        if not values:
            return None
        
        return StatisticalSummary(
            metric_name=metric,
            count=len(values),
            mean=np.mean(values),
            std=np.std(values),
            min=np.min(values),
            max=np.max(values),
            q25=np.percentile(values, 25),
            median=np.median(values),
            q75=np.percentile(values, 75)
        )
    
    def analyze_by_terrain_type(self) -> Dict[str, Dict]:
        """地形タイプ別分析"""
        terrain_stats = defaultdict(lambda: {
            'count': 0,
            'success_count': 0,
            'computation_times': [],
            'path_lengths': [],
            'waypoints': []
        })
        
        for result in self.results:
            terrain_info = self.terrain_type_map.get(result.scenario_id)
            if not terrain_info:
                continue
            
            terrain_type = terrain_info['terrain_type']
            terrain_stats[terrain_type]['count'] += 1
            
            if result.path_found:
                terrain_stats[terrain_type]['success_count'] += 1
                terrain_stats[terrain_type]['computation_times'].append(result.computation_time)
                terrain_stats[terrain_type]['path_lengths'].append(result.path_length)
                terrain_stats[terrain_type]['waypoints'].append(result.num_waypoints)
        
        # 統計計算
        analysis = {}
        for terrain_type, data in terrain_stats.items():
            analysis[terrain_type] = {
                'count': data['count'],
                'success_rate': data['success_count'] / data['count'] * 100 if data['count'] > 0 else 0,
                'avg_computation_time': np.mean(data['computation_times']) if data['computation_times'] else 0,
                'std_computation_time': np.std(data['computation_times']) if data['computation_times'] else 0,
                'avg_path_length': np.mean(data['path_lengths']) if data['path_lengths'] else 0,
                'avg_waypoints': np.mean(data['waypoints']) if data['waypoints'] else 0
            }
        
        return analysis
    
    def analyze_by_difficulty(self) -> Dict[str, Dict]:
        """難易度別分析"""
        difficulty_stats = defaultdict(lambda: {
            'count': 0,
            'success_count': 0,
            'computation_times': [],
            'path_lengths': []
        })
        
        for result in self.results:
            terrain_info = self.terrain_type_map.get(result.scenario_id)
            if not terrain_info:
                continue
            
            difficulty = terrain_info['difficulty']
            difficulty_stats[difficulty]['count'] += 1
            
            if result.path_found:
                difficulty_stats[difficulty]['success_count'] += 1
                difficulty_stats[difficulty]['computation_times'].append(result.computation_time)
                difficulty_stats[difficulty]['path_lengths'].append(result.path_length)
        
        # 統計計算
        analysis = {}
        for difficulty, data in difficulty_stats.items():
            analysis[difficulty] = {
                'count': data['count'],
                'success_rate': data['success_count'] / data['count'] * 100 if data['count'] > 0 else 0,
                'avg_computation_time': np.mean(data['computation_times']) if data['computation_times'] else 0,
                'avg_path_length': np.mean(data['path_lengths']) if data['path_lengths'] else 0
            }
        
        return analysis
    
    def calculate_correlation(self) -> Dict[str, float]:
        """相関分析"""
        # 地形パラメータと計算時間の相関
        max_slopes = []
        obstacle_densities = []
        roughnesses = []
        computation_times = []
        
        for result in self.results:
            terrain_info = self.terrain_type_map.get(result.scenario_id)
            if not terrain_info:
                continue
            
            max_slopes.append(terrain_info['max_slope'])
            obstacle_densities.append(terrain_info['obstacle_density'])
            roughnesses.append(terrain_info['roughness'])
            computation_times.append(result.computation_time)
        
        correlations = {}
        
        if len(computation_times) > 1:
            correlations['max_slope_vs_time'] = np.corrcoef(max_slopes, computation_times)[0, 1]
            correlations['obstacle_density_vs_time'] = np.corrcoef(obstacle_densities, computation_times)[0, 1]
            correlations['roughness_vs_time'] = np.corrcoef(roughnesses, computation_times)[0, 1]
        
        return correlations
    
    def detect_outliers(self, metric: str = 'computation_time') -> List[int]:
        """外れ値検出（IQR法）"""
        values = []
        scenario_ids = []
        
        for result in self.results:
            if metric == 'computation_time':
                values.append(result.computation_time)
                scenario_ids.append(result.scenario_id)
            elif metric == 'path_length' and result.path_found:
                values.append(result.path_length)
                scenario_ids.append(result.scenario_id)
        
        if not values:
            return []
        
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = []
        for sid, val in zip(scenario_ids, values):
            if val < lower_bound or val > upper_bound:
                outliers.append(sid)
        
        return outliers
    
    def perform_anova(self) -> Dict:
        """地形タイプ間のANOVA検定"""
        # 地形タイプごとに計算時間を分類
        groups = defaultdict(list)
        
        for result in self.results:
            terrain_info = self.terrain_type_map.get(result.scenario_id)
            if terrain_info:
                groups[terrain_info['terrain_type']].append(result.computation_time)
        
        # ANOVA実行
        group_data = [data for data in groups.values() if len(data) > 0]
        
        if len(group_data) >= 2:
            f_stat, p_value = stats.f_oneway(*group_data)
            
            return {
                'f_statistic': f_stat,
                'p_value': p_value,
                'significant': p_value < 0.05,
                'interpretation': 'Significant difference' if p_value < 0.05 else 'No significant difference'
            }
        
        return {}
    
    def generate_comprehensive_report(self) -> Dict:
        """包括的統計レポート生成"""
        print("\n📊 包括的統計解析実行中...")
        
        report = {
            'basic_stats': {
                'total_scenarios': len(self.results),
                'successful_scenarios': sum(1 for r in self.results if r.path_found),
                'success_rate': sum(1 for r in self.results if r.path_found) / len(self.results) * 100,
            },
            'descriptive_statistics': {
                'computation_time': self.calculate_descriptive_stats('computation_time').__dict__,
                'path_length': self.calculate_descriptive_stats('path_length').__dict__ if any(r.path_found for r in self.results) else None,
                'num_waypoints': self.calculate_descriptive_stats('num_waypoints').__dict__ if any(r.path_found for r in self.results) else None,
            },
            'terrain_type_analysis': self.analyze_by_terrain_type(),
            'difficulty_analysis': self.analyze_by_difficulty(),
            'correlations': self.calculate_correlation(),
            'outliers': {
                'computation_time': self.detect_outliers('computation_time'),
                'path_length': self.detect_outliers('path_length')
            },
            'anova': self.perform_anova()
        }
        
        print("✅ 統計解析完了！")
        return report
    
    def save_report(self, report: Dict, output_path: str = "results/statistical_analysis.json"):
        """レポート保存"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # numpy型をPython型に変換
        def convert_numpy(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
        
        def recursive_convert(obj):
            if isinstance(obj, dict):
                return {k: recursive_convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [recursive_convert(item) for item in obj]
            else:
                return convert_numpy(obj)
        
        converted_report = recursive_convert(report)
        
        with open(output_file, 'w') as f:
            json.dump(converted_report, f, indent=2)
        
        print(f"💾 統計レポート保存: {output_file}")

def main():
    """メイン実行"""
    analyzer = StatisticsAnalyzer()
    analyzer.load_data()
    
    # 包括的レポート生成
    report = analyzer.generate_comprehensive_report()
    analyzer.save_report(report)
    
    # 主要結果表示
    print("\n📊 主要統計結果:")
    print(f"  成功率: {report['basic_stats']['success_rate']:.1f}%")
    print(f"  平均計算時間: {report['descriptive_statistics']['computation_time']['mean']:.2f}秒")
    print(f"  計算時間の標準偏差: {report['descriptive_statistics']['computation_time']['std']:.2f}秒")
    
    print("\n🏔️ 地形タイプ別成功率:")
    for terrain, data in report['terrain_type_analysis'].items():
        print(f"  {terrain}: {data['success_rate']:.1f}%")
    
    print("\n🔗 相関分析:")
    for key, value in report['correlations'].items():
        print(f"  {key}: {value:.3f}")

if __name__ == "__main__":
    main()
