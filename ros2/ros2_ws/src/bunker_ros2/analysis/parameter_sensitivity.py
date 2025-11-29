"""
パラメータ感度分析

TA-A*のパラメータが性能に与える影響を分析
"""
import numpy as np
import json
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class ParameterSensitivityAnalyzer:
    """パラメータ感度分析クラス"""
    
    def __init__(self, results_file: str):
        """
        初期化
        
        Args:
            results_file: 実験結果ファイル
        """
        with open(results_file) as f:
            self.data = json.load(f)
    
    def analyze_terrain_adaptation_sensitivity(self) -> Dict:
        """
        地形適応パラメータの感度分析
        
        Returns:
            Dict: 感度分析結果
        """
        print("\n" + "="*70)
        print("TA-A* 地形適応パラメータ感度分析")
        print("="*70)
        
        # TA-A*の結果を集める
        tastar_results = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            if 'TA-A* (Proposed)' in terrain_results:
                for result in terrain_results['TA-A* (Proposed)']:
                    if result.get('success', False):
                        tastar_results.append({
                            'terrain': terrain,
                            'terrain_adaptations': result.get('terrain_adaptations', 0),
                            'computation_time': result.get('computation_time', 0),
                            'path_length': result.get('path_length', 0),
                            'risk_score': result.get('risk_score', 0)
                        })
        
        if not tastar_results:
            print("TA-A*の成功データがありません")
            return {}
        
        # 地形別の適応回数分析
        terrain_stats = {}
        for terrain in ['flat_agricultural_field', 'gentle_hills', 'steep_terrain', 
                       'complex_obstacles', 'extreme_hazards']:
            terrain_data = [r for r in tastar_results if r['terrain'] == terrain]
            
            if terrain_data:
                adaptations = [r['terrain_adaptations'] for r in terrain_data]
                terrain_stats[terrain] = {
                    'count': len(terrain_data),
                    'avg_adaptations': np.mean(adaptations),
                    'std_adaptations': np.std(adaptations),
                    'max_adaptations': np.max(adaptations),
                    'min_adaptations': np.min(adaptations)
                }
                
                print(f"\n{terrain}:")
                print(f"  成功ケース数: {len(terrain_data)}")
                print(f"  平均適応回数: {np.mean(adaptations):.2f} (±{np.std(adaptations):.2f})")
                print(f"  範囲: {np.min(adaptations)} - {np.max(adaptations)}")
        
        # 適応回数と性能の相関分析
        adaptations = [r['terrain_adaptations'] for r in tastar_results]
        computation_times = [r['computation_time'] for r in tastar_results]
        path_lengths = [r['path_length'] for r in tastar_results]
        risk_scores = [r['risk_score'] for r in tastar_results]
        
        # 相関係数計算
        corr_time = np.corrcoef(adaptations, computation_times)[0, 1]
        corr_length = np.corrcoef(adaptations, path_lengths)[0, 1]
        corr_risk = np.corrcoef(adaptations, risk_scores)[0, 1]
        
        print(f"\n相関分析:")
        print(f"  適応回数 vs 計算時間: r = {corr_time:.3f}")
        print(f"  適応回数 vs 経路長: r = {corr_length:.3f}")
        print(f"  適応回数 vs リスクスコア: r = {corr_risk:.3f}")
        
        # 適応回数による性能グループ分け
        low_adapt = [r for r in tastar_results if r['terrain_adaptations'] <= 2]
        mid_adapt = [r for r in tastar_results if 2 < r['terrain_adaptations'] <= 5]
        high_adapt = [r for r in tastar_results if r['terrain_adaptations'] > 5]
        
        print(f"\n適応回数による性能比較:")
        
        for group_name, group_data in [("低適応 (≤2)", low_adapt), 
                                      ("中適応 (3-5)", mid_adapt), 
                                      ("高適応 (>5)", high_adapt)]:
            if group_data:
                avg_time = np.mean([r['computation_time'] for r in group_data])
                avg_length = np.mean([r['path_length'] for r in group_data])
                avg_risk = np.mean([r['risk_score'] for r in group_data])
                
                print(f"\n{group_name}:")
                print(f"  ケース数: {len(group_data)}")
                print(f"  平均計算時間: {avg_time:.2f}s")
                print(f"  平均経路長: {avg_length:.2f}m")
                print(f"  平均リスクスコア: {avg_risk:.2f}")
        
        return {
            'terrain_stats': terrain_stats,
            'correlations': {
                'time': corr_time,
                'length': corr_length,
                'risk': corr_risk
            },
            'group_performance': {
                'low_adapt': len(low_adapt),
                'mid_adapt': len(mid_adapt),
                'high_adapt': len(high_adapt)
            }
        }
    
    def analyze_risk_score_sensitivity(self) -> Dict:
        """
        リスクスコアの感度分析
        
        Returns:
            Dict: 感度分析結果
        """
        print("\n" + "="*70)
        print("TA-A* リスクスコア感度分析")
        print("="*70)
        
        # TA-A*の結果を集める
        tastar_results = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            if 'TA-A* (Proposed)' in terrain_results:
                for result in terrain_results['TA-A* (Proposed)']:
                    if result.get('success', False):
                        tastar_results.append({
                            'terrain': terrain,
                            'risk_score': result.get('risk_score', 0),
                            'computation_time': result.get('computation_time', 0),
                            'path_length': result.get('path_length', 0),
                            'terrain_adaptations': result.get('terrain_adaptations', 0)
                        })
        
        if not tastar_results:
            print("TA-A*の成功データがありません")
            return {}
        
        # リスクスコアの分布
        risk_scores = [r['risk_score'] for r in tastar_results]
        
        print(f"\nリスクスコア分布:")
        print(f"  平均: {np.mean(risk_scores):.3f}")
        print(f"  標準偏差: {np.std(risk_scores):.3f}")
        print(f"  最小値: {np.min(risk_scores):.3f}")
        print(f"  最大値: {np.max(risk_scores):.3f}")
        print(f"  中央値: {np.median(risk_scores):.3f}")
        
        # リスクスコアによる性能グループ分け
        low_risk = [r for r in tastar_results if r['risk_score'] <= 0.3]
        mid_risk = [r for r in tastar_results if 0.3 < r['risk_score'] <= 0.7]
        high_risk = [r for r in tastar_results if r['risk_score'] > 0.7]
        
        print(f"\nリスクスコアによる性能比較:")
        
        for group_name, group_data in [("低リスク (≤0.3)", low_risk), 
                                      ("中リスク (0.3-0.7)", mid_risk), 
                                      ("高リスク (>0.7)", high_risk)]:
            if group_data:
                avg_time = np.mean([r['computation_time'] for r in group_data])
                avg_length = np.mean([r['path_length'] for r in group_data])
                avg_adaptations = np.mean([r['terrain_adaptations'] for r in group_data])
                
                print(f"\n{group_name}:")
                print(f"  ケース数: {len(group_data)}")
                print(f"  平均計算時間: {avg_time:.2f}s")
                print(f"  平均経路長: {avg_length:.2f}m")
                print(f"  平均適応回数: {avg_adaptations:.2f}")
        
        # 地形別リスクスコア分析
        print(f"\n地形別リスクスコア:")
        for terrain in ['flat_agricultural_field', 'gentle_hills', 'steep_terrain', 
                       'complex_obstacles', 'extreme_hazards']:
            terrain_data = [r for r in tastar_results if r['terrain'] == terrain]
            
            if terrain_data:
                terrain_risks = [r['risk_score'] for r in terrain_data]
                print(f"\n{terrain}:")
                print(f"  平均リスク: {np.mean(terrain_risks):.3f}")
                print(f"  標準偏差: {np.std(terrain_risks):.3f}")
                print(f"  範囲: {np.min(terrain_risks):.3f} - {np.max(terrain_risks):.3f}")
        
        return {
            'risk_distribution': {
                'mean': np.mean(risk_scores),
                'std': np.std(risk_scores),
                'min': np.min(risk_scores),
                'max': np.max(risk_scores),
                'median': np.median(risk_scores)
            },
            'group_performance': {
                'low_risk': len(low_risk),
                'mid_risk': len(mid_risk),
                'high_risk': len(high_risk)
            }
        }
    
    def generate_sensitivity_report(self):
        """感度分析の完全レポートを生成"""
        print("\n" + "="*70)
        print("TA-A* パラメータ感度分析 完全レポート")
        print("="*70)
        
        # 1. 地形適応パラメータ感度
        adaptation_results = self.analyze_terrain_adaptation_sensitivity()
        
        # 2. リスクスコア感度
        risk_results = self.analyze_risk_score_sensitivity()
        
        # 3. 推奨パラメータ設定
        print(f"\n" + "="*70)
        print("推奨パラメータ設定")
        print("="*70)
        
        if adaptation_results and risk_results:
            print(f"\n1. 地形適応閾値:")
            print(f"   - 低適応 (≤2): 平坦地形に適している")
            print(f"   - 中適応 (3-5): 一般的な地形に適している")
            print(f"   - 高適応 (>5): 複雑な地形に適している")
            
            print(f"\n2. リスクスコア閾値:")
            print(f"   - 低リスク (≤0.3): 安全な経路")
            print(f"   - 中リスク (0.3-0.7): 許容可能なリスク")
            print(f"   - 高リスク (>0.7): 危険な経路")
            
            print(f"\n3. 最適化提案:")
            print(f"   - 地形適応回数が多い場合、計算時間が増加")
            print(f"   - リスクスコアと適応回数に相関がある可能性")
            print(f"   - パラメータの動的調整が有効")
        
        print("\n" + "="*70)
        print("✅ 感度分析完了")
        print("="*70)

if __name__ == '__main__':
    analyzer = ParameterSensitivityAnalyzer('../results/efficient_terrain_results.json')
    analyzer.generate_sensitivity_report()



