"""
エラー分析（簡易版）

失敗・タイムアウトケースの分析
"""
import json
import numpy as np
from pathlib import Path

def analyze_errors():
    """エラーを分析"""
    print("="*70)
    print("エラー分析")
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
    
    print("\n【失敗率分析】")
    
    for terrain, terrain_results in data['results'].items():
        print(f"\n{terrain}:")
        
        for algo, algo_results in terrain_results.items():
            total = len(algo_results)
            failures = sum(1 for r in algo_results if not r.get('success', False))
            failure_rate = failures / total * 100 if total > 0 else 0
            
            print(f"  {algo:20s}: {failure_rate:5.1f}% ({failures}/{total})")
    
    print("\n【タイムアウト分析】")
    
    timeout_by_algo = {}
    
    for terrain, terrain_results in data['results'].items():
        for algo, algo_results in terrain_results.items():
            if algo not in timeout_by_algo:
                timeout_by_algo[algo] = 0
            
            for r in algo_results:
                if not r.get('success', False):
                    error_msg = r.get('error_message', '').lower()
                    if 'timeout' in error_msg:
                        timeout_by_algo[algo] += 1
    
    print("\nアルゴリズム別タイムアウト数:")
    for algo, count in sorted(timeout_by_algo.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {algo:20s}: {count}回")
    
    print("\n✅ エラー分析完了")

if __name__ == '__main__':
    analyze_errors()
