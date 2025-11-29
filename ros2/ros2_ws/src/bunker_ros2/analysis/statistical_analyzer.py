"""
統計分析

実験結果の統計的分析
"""
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class StatisticalAnalyzer:
    """統計分析クラス"""
    
    def __init__(self):
        """初期化"""
        logger.info("StatisticalAnalyzer initialized")
    
    def calculate_success_rate(self, results: List[Dict]) -> float:
        """
        成功率を計算
        
        Args:
            results: 実験結果のリスト
        
        Returns:
            float: 成功率（0-100%）
        """
        if not results:
            return 0.0
        
        success = sum(1 for r in results if r.get('success', False))
        return success / len(results) * 100
    
    def calculate_statistics(self, values: List[float]) -> Dict:
        """
        基本統計量を計算
        
        Args:
            values: 数値のリスト
        
        Returns:
            Dict: 統計量（mean, std, min, max, median）
        """
        if not values:
            return {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'median': 0.0
            }
        
        return {
            'mean': np.mean(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'median': np.median(values)
        }
    
    def t_test(self, group1: List[float], group2: List[float]) -> Tuple[float, float]:
        """
        t検定
        
        Args:
            group1: グループ1の値
            group2: グループ2の値
        
        Returns:
            Tuple[float, float]: (t統計量, p値)
        """
        if len(group1) < 2 or len(group2) < 2:
            return 0.0, 1.0
        
        t_stat, p_value = stats.ttest_ind(group1, group2)
        return t_stat, p_value
    
    def analyze_algorithm_performance(self, results: Dict) -> Dict:
        """
        アルゴリズム性能を分析
        
        Args:
            results: アルゴリズムごとの結果
        
        Returns:
            Dict: 分析結果
        """
        analysis = {}
        
        for algo, algo_results in results.items():
            # 成功したもののみ
            success_results = [r for r in algo_results if r.get('success', False)]
            
            if not success_results:
                analysis[algo] = {
                    'success_rate': 0.0,
                    'computation_time': {'mean': 0.0},
                    'path_length': {'mean': 0.0}
                }
                continue
            
            times = [r['computation_time'] for r in success_results]
            lengths = [r['path_length'] for r in success_results if r.get('path_length', 0) > 0]
            
            analysis[algo] = {
                'success_rate': self.calculate_success_rate(algo_results),
                'computation_time': self.calculate_statistics(times),
                'path_length': self.calculate_statistics(lengths),
                'total_scenarios': len(algo_results),
                'successful_scenarios': len(success_results)
            }
        
        return analysis
    
    def compare_algorithms(self, algo1_results: List[Dict], 
                          algo2_results: List[Dict]) -> Dict:
        """
        2つのアルゴリズムを統計的に比較
        
        Args:
            algo1_results: アルゴリズム1の結果
            algo2_results: アルゴリズム2の結果
        
        Returns:
            Dict: 比較結果
        """
        # 成功したもののみ
        algo1_success = [r for r in algo1_results if r.get('success', False)]
        algo2_success = [r for r in algo2_results if r.get('success', False)]
        
        if not algo1_success or not algo2_success:
            return {
                'significant': False,
                'reason': 'Insufficient data'
            }
        
        # 計算時間の比較
        times1 = [r['computation_time'] for r in algo1_success]
        times2 = [r['computation_time'] for r in algo2_success]
        
        t_stat, p_value = self.t_test(times1, times2)
        
        return {
            'success_rate_diff': self.calculate_success_rate(algo1_results) - 
                                self.calculate_success_rate(algo2_results),
            'mean_time_diff': np.mean(times1) - np.mean(times2),
            't_statistic': t_stat,
            'p_value': p_value,
            'significant': p_value < 0.05
        }



