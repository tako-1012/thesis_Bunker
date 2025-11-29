#!/usr/bin/env python3
"""
TA-A* Optimized クイック検証

目的:
Phase 2の一部地形で最適化版TA-A*が動作するか検証

実行時間: 約5-10分
"""
import sys
import json
import time
from pathlib import Path
import numpy as np

# パスの追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from tastar_optimized import TerrainAwareAStarOptimized

def quick_validation():
    """クイック検証"""
    print("="*70)
    print("TA-A* Optimized - クイック検証")
    print("="*70)
    
    # プランナー初期化
    planner = TerrainAwareAStarOptimized(
        map_bounds=([-50, -50, 0], [50, 50, 10]),
        voxel_size=0.2
    )
    
    # テストシナリオ
    test_cases = [
        # Flat terrain
        ([0, 0, 0.2], [5, 5, 0.2], "Flat-Short"),
        ([0, 0, 0.2], [10, 10, 0.2], "Flat-Medium"),
        ([-10, -10, 0.2], [10, 10, 0.2], "Flat-Long"),
        
        # Hills terrain
        ([0, 0, 0.3], [5, 5, 0.3], "Hill-Short"),
        ([0, 0, 0.3], [10, 10, 0.3], "Hill-Medium"),
        
        # Complex terrain
        ([-10, -10, 0.5], [10, 10, 0.5], "Complex-Long"),
    ]
    
    results = []
    
    for start, goal, name in test_cases:
        print(f"\n{name}:", end=" ")
        
        try:
            start_time = time.time()
            result = planner.plan_path(start, goal, timeout=60)
            elapsed = time.time() - start_time
            
            if result.success:
                status = "✅"
                print(f"{status} {elapsed:.3f}s ({result.path_length:.1f}m, {result.nodes_explored} nodes)")
            else:
                status = "❌"
                print(f"{status} {result.error_message[:50]}")
            
            results.append({
                'name': name,
                'success': result.success,
                'time': elapsed,
                'path_length': result.path_length if result.success else 0,
                'nodes': result.nodes_explored
            })
            
        except Exception as e:
            print(f"❌ Error: {str(e)[:50]}")
            results.append({
                'name': name,
                'success': False,
                'time': 0,
                'path_length': 0,
                'nodes': 0,
                'error': str(e)
            })
    
    # サマリー
    print("\n" + "="*70)
    print("検証結果サマリー")
    print("="*70)
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    success_rate = success_count / total_count * 100
    
    successful_results = [r for r in results if r['success']]
    if successful_results:
        avg_time = np.mean([r['time'] for r in successful_results])
        print(f"\n成功率: {success_rate:.1f}% ({success_count}/{total_count})")
        print(f"平均処理時間: {avg_time:.3f}s")
    
    # 結果を保存
    output_dir = Path('../results/phase2_validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'quick_validation_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'results': results,
            'success_rate': success_rate
        }, f, indent=2)
    
    print(f"\n✅ 結果保存: {output_file}")
    
    # 次のステップ
    print("\n" + "="*70)
    print("次のステップ")
    print("="*70)
    print("1. クイック検証の結果を確認")
    print("2. 問題なければ詳細検証に進む")
    print("3. 論文データの生成")
    print("="*70)

if __name__ == '__main__':
    quick_validation()


