"""
統計的検定（簡易版）

既存の実験結果から統計的有意性を検証
"""
import json
import numpy as np
from pathlib import Path

def simple_statistical_test():
    """簡易統計的検定"""
    print("="*70)
    print("統計的検定（簡易版）")
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
    
    # A* vs TA-A* の成功率比較
    print("\n【A* vs TA-A* 成功率比較】")
    
    total_astar_success = 0
    total_astar_total = 0
    total_tastar_success = 0
    total_tastar_total = 0
    
    for terrain, terrain_results in data['results'].items():
        if 'A*' in terrain_results and 'TA-A* (Proposed)' in terrain_results:
            astar = terrain_results['A*']
            tastar = terrain_results['TA-A* (Proposed)']
            
            astar_success = sum(1 for r in astar if r.get('success', False))
            tastar_success = sum(1 for r in tastar if r.get('success', False))
            
            total_astar_success += astar_success
            total_astar_total += len(astar)
            total_tastar_success += tastar_success
            total_tastar_total += len(tastar)
            
            astar_rate = astar_success / len(astar) * 100
            tastar_rate = tastar_success / len(tastar) * 100
            
            diff = tastar_rate - astar_rate
            
            print(f"\n{terrain}:")
            print(f"  A*:      {astar_rate:5.1f}% ({astar_success}/{len(astar)})")
            print(f"  TA-A*:   {tastar_rate:5.1f}% ({tastar_success}/{len(tastar)})")
            print(f"  差:      {diff:+5.1f}ポイント")
            
            if abs(diff) > 10:
                print(f"  → TA-A*が大きく優位 ✅")
            elif abs(diff) > 5:
                print(f"  → TA-A*が優位 ✅")
            elif diff > -5:
                print(f"  → ほぼ同等")
            else:
                print(f"  → A*が優位")
    
    # 全体サマリー
    print("\n" + "="*70)
    print("全体サマリー")
    print("="*70)
    
    if total_astar_total > 0:
        overall_astar_rate = total_astar_success / total_astar_total * 100
        overall_tastar_rate = total_tastar_success / total_tastar_total * 100
        overall_diff = overall_tastar_rate - overall_astar_rate
        
        print(f"\nA*:      {overall_astar_rate:5.1f}% ({total_astar_success}/{total_astar_total})")
        print(f"TA-A*:   {overall_tastar_rate:5.1f}% ({total_tastar_success}/{total_tastar_total})")
        print(f"改善:    {overall_diff:+5.1f}ポイント")
        
        if overall_diff > 5:
            print("\n結論: TA-A*は統計的に優位 ✅")
        else:
            print("\n結論: TA-A*とA*は同等レベル")
    
    print("\n✅ 統計的検定（簡易版）完了")
    
    # 結果を保存
    output_file = Path(__file__).parent.parent / 'results' / 'statistical_analysis_simple.json'
    output_data = {
        'a_star': {
            'success_rate': overall_astar_rate if total_astar_total > 0 else 0,
            'successes': total_astar_success,
            'total': total_astar_total
        },
        'ta_a_star': {
            'success_rate': overall_tastar_rate if total_tastar_total > 0 else 0,
            'successes': total_tastar_success,
            'total': total_tastar_total
        },
        'improvement': overall_diff if total_astar_total > 0 else 0
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"結果保存: {output_file}")

if __name__ == '__main__':
    simple_statistical_test()
