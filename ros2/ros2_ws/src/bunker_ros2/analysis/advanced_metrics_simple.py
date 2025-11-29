"""
高度な評価指標（簡易版）

経路の質を評価
"""
import json
import numpy as np
from pathlib import Path

def analyze_path_quality():
    """経路品質を分析"""
    print("="*70)
    print("高度な評価指標分析")
    print("="*70)
    
    results_file = Path(__file__).parent.parent / 'results' / 'efficient_terrain_results.json'
    
    if not results_file.exists():
        print("❌ Phase 2結果ファイルが見つかりません")
        return
    
    with open(results_file) as f:
        data = json.load(f)
    
    if 'results' not in data:
        print("❌ データが不完全です")
        return
    
    print("\n【計算時間分析】")
    
    for terrain, terrain_results in data['results'].items():
        print(f"\n{terrain}:")
        
        for algo, algo_results in terrain_results.items():
            times = [r['computation_time'] for r in algo_results if r.get('success', False)]
            
            if times:
                avg_time = np.mean(times)
                median_time = np.median(times)
                min_time = np.min(times)
                max_time = np.max(times)
                
                print(f"  {algo:20s}:")
                print(f"    平均: {avg_time:6.2f}s")
                print(f"    中央値: {median_time:6.2f}s")
                print(f"    範囲: {min_time:6.2f}s - {max_time:6.2f}s")
    
    print("\n【経路長分析】")
    
    for terrain, terrain_results in data['results'].items():
        print(f"\n{terrain}:")
        
        for algo, algo_results in terrain_results.items():
            lengths = [r['path_length'] for r in algo_results if r.get('success', False) and 'path_length' in r]
            
            if lengths:
                avg_length = np.mean(lengths)
                print(f"  {algo:20s}: 平均経路長 {avg_length:6.2f}m")
    
    print("\n✅ 高度な評価指標分析完了")

if __name__ == '__main__':
    analyze_path_quality()
