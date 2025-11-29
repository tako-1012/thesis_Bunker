#!/usr/bin/env python3
"""
失敗シナリオの詳細分析
各アルゴリズムがどのシナリオで失敗したか、
その理由を特定
"""
import json
from pathlib import Path

def analyze_failures():
    results_file = Path('../results/algorithm_comparison/comparison_results.json')
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    print("="*70)
    print("【失敗シナリオの詳細分析】")
    print("="*70)
    
    # 各アルゴリズムの失敗シナリオを集計
    all_failures = {}
    
    for algo, results in data.items():
        if algo == 'TA-A* (Proposed)':  # TA-A*は未実装なのでスキップ
            continue
            
        failures = [r for r in results if not r['success']]
        all_failures[algo] = failures
        
        print(f"\n{algo}:")
        print(f"  成功: {len(results) - len(failures)}/{len(results)}")
        print(f"  失敗: {len(failures)}/{len(results)}")
        
        if failures:
            print(f"  失敗シナリオID: {[f['scenario_id'] for f in failures]}")
            
            # 失敗の詳細
            for f in failures:
                print(f"\n  --- Scenario {f['scenario_id']:03d} ---")
                print(f"    地形: {f.get('terrain_type', 'Unknown')}")
                print(f"    エラー: {f.get('error_message', 'No error message')}")
                print(f"    計算時間: {f.get('computation_time', 0):.2f}秒")
                
                # タイムアウトチェック
                if f.get('computation_time', 0) > 500:
                    print(f"    ⚠️ タイムアウトの可能性")
                elif f.get('computation_time', 0) < 0.1:
                    print(f"    ⚠️ 即座に失敗（座標エラーの可能性）")
    
    # 共通して失敗しているシナリオを特定
    print("\n" + "="*70)
    print("【共通失敗シナリオ】")
    print("="*70)
    
    # 全アルゴリズムで失敗しているシナリオ
    if all_failures:
        first_algo_failures = set(f['scenario_id'] for f in all_failures[list(all_failures.keys())[0]])
        common_failures = first_algo_failures.copy()
        
        for algo, failures in all_failures.items():
            failure_ids = set(f['scenario_id'] for f in failures)
            common_failures &= failure_ids
        
        if common_failures:
            print(f"全アルゴリズムで失敗: {sorted(common_failures)}")
            print("→ これらのシナリオに問題がある可能性")
        else:
            print("全アルゴリズムで共通して失敗しているシナリオはなし")
            print("→ アルゴリズムごとに異なるシナリオで失敗")
    
    # エラータイプの分析
    print("\n" + "="*70)
    print("【エラータイプ分析】")
    print("="*70)
    
    error_types = {}
    for algo, failures in all_failures.items():
        error_types[algo] = {}
        for f in failures:
            error_msg = f.get('error_message', 'Unknown')
            error_types[algo][error_msg] = error_types[algo].get(error_msg, 0) + 1
    
    for algo, errors in error_types.items():
        if errors:
            print(f"\n{algo}:")
            for error_msg, count in errors.items():
                print(f"  - {error_msg}: {count}回")

if __name__ == '__main__':
    analyze_failures()







