#!/usr/bin/env python3
"""
実験状況の完全確認
- 100シナリオ実験の有無
- TA-A*を含む5アルゴリズムの結果確認
- 不足データの特定
"""
import json
import os
from pathlib import Path

def check_status():
    results_dir = Path('../results/algorithm_comparison')
    results_file = results_dir / 'comparison_results.json'
    
    print("="*70)
    print("【実験状況確認】")
    print("="*70)
    
    # 1. 結果ファイルの存在確認
    if not results_file.exists():
        print("\n❌ 結果ファイルが存在しません")
        print("   → 100シナリオ実験を実行する必要があります")
        return False
    
    # 2. 結果の内容確認
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    print(f"\n✅ 結果ファイル発見")
    print(f"   ファイルサイズ: {results_file.stat().st_size / 1024:.1f} KB")
    print(f"   アルゴリズム数: {len(data)}")
    
    # 3. 各アルゴリズムの確認
    expected_algorithms = [
        'Dijkstra',
        'A*',
        'Weighted A*',
        'RRT*',
        'TA-A* (Proposed)'
    ]
    
    print(f"\n【アルゴリズム別シナリオ数】")
    missing = []
    for algo in expected_algorithms:
        if algo in data:
            count = len(data[algo])
            print(f"  ✅ {algo:20s}: {count:3d}シナリオ")
            if count < 100:
                print(f"     ⚠️  100シナリオ未満（{100-count}個不足）")
        else:
            print(f"  ❌ {algo:20s}: データなし")
            missing.append(algo)
    
    # 4. 成功状況の確認
    print(f"\n【成功率の確認】")
    for algo in expected_algorithms:
        if algo in data and data[algo]:
            results = data[algo]
            successful = sum(1 for r in results if r.get('success', False))
            total = len(results)
            success_rate = successful / total * 100 if total > 0 else 0
            print(f"  {algo:20s}: {successful:3d}/{total:3d} = {success_rate:6.2f}%")
    
    # 5. 判定
    print(f"\n{'='*70}")
    if missing:
        print(f"❌ 不足しているアルゴリズム: {', '.join(missing)}")
        print(f"   → これらのアルゴリズムの実験を実行してください")
        return False
    
    # 全アルゴリズムのシナリオ数をチェック
    min_scenarios = min(len(data[algo]) for algo in expected_algorithms if algo in data)
    if min_scenarios < 100:
        print(f"⚠️  最小シナリオ数: {min_scenarios}")
        print(f"   → 100シナリオ実験を完了させてください")
        return False
    
    print(f"✅ 全データ完備！")
    print(f"   - 5アルゴリズム全て存在")
    print(f"   - 各100シナリオ完了")
    return True

if __name__ == '__main__':
    check_status()







