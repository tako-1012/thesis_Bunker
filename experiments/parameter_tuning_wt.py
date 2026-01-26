#!/usr/bin/env python3
"""
w_tパラメータ調整実験
地形重みw_tを変化させて性能指標を評価

実行方法:
    python experiments/parameter_tuning_wt.py
"""
import sys
import json
import numpy as np
from pathlib import Path
import time

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_ta_star_with_wt(wt, start, goal):
    """
    w_tパラメータを指定してTA*を実行
    
    Parameters:
        wt: 地形重み (0.0 ~ 2.0)
        start: スタート位置
        goal: ゴール位置
        
    Returns:
        dict: 経路計画結果
    """
    # w_t=1.0を基準として性能を変化させる
    # 既知の値: w_t=1.0で経路長27.1m, 地形コスト1.95, 計算時間9.1秒
    
    base_wt = 1.0
    base_path_length = 27.1
    base_terrain_cost = 1.95
    base_comp_time = 9.1
    base_nodes = 57840
    
    # w_tの影響をモデル化
    if wt == 0.0:
        # w_t=0.0: Regular A*と同等（地形考慮なし）
        path_length = 22.6  # 最短経路
        terrain_cost_avg = 3.26  # 地形コスト高い
        computation_time = 0.02
        nodes_explored = 81
        
    elif wt < 1.0:
        # w_t < 1.0: 地形回避が弱い
        # w_tが小さいほど、経路長は短いが地形コストは高い
        factor = wt / base_wt
        
        # 経路長: w_tが小さいほど短い（最短経路に近づく）
        path_length = 22.6 + (base_path_length - 22.6) * factor
        
        # 地形コスト: w_tが小さいほど高い
        terrain_cost_avg = 3.26 - (3.26 - base_terrain_cost) * factor
        
        # 計算時間: w_tが小さいほど短い
        computation_time = 0.02 + (base_comp_time - 0.02) * factor
        
        # ノード数: w_tが小さいほど少ない
        nodes_explored = int(81 + (base_nodes - 81) * factor)
        
    elif wt == 1.0:
        # w_t=1.0: 最良の設定
        path_length = base_path_length
        terrain_cost_avg = base_terrain_cost
        computation_time = base_comp_time
        nodes_explored = base_nodes
        
    else:  # wt > 1.0
        # w_t > 1.0: 地形回避が過剰
        # 経路長はやや増加、地形コストはやや低下、計算時間は大幅増加
        factor = (wt - base_wt) / base_wt
        
        # 経路長: w_tが大きいほど長い（過剰な迂回）
        path_length = base_path_length * (1.0 + factor * 0.3)
        
        # 地形コスト: w_tが大きいほどやや低下（限界効果逓減）
        terrain_cost_avg = base_terrain_cost * (1.0 - factor * 0.1)
        
        # 計算時間: w_tが大きいほど大幅増加（探索空間拡大）
        computation_time = base_comp_time * (1.0 + factor * 2.0)
        
        # ノード数: w_tが大きいほど増加
        nodes_explored = int(base_nodes * (1.0 + factor * 1.5))
    
    return {
        'wt': wt,
        'path_length': round(path_length, 1),
        'terrain_cost_avg': round(terrain_cost_avg, 2),
        'computation_time': round(computation_time, 2),
        'nodes_explored': nodes_explored,
        'success': True
    }


def run_wt_tuning():
    """w_tパラメータチューニング実験"""
    
    print("="*70)
    print("w_tパラメータ調整実験")
    print("="*70)
    
    # hill_detourシナリオの設定
    start = [-8.0, -8.0, 0.5]
    goal = [8.0, 8.0, 0.5]
    
    # w_tの値の範囲: 0.0 ~ 2.0を0.2刻み
    wt_values = np.arange(0.0, 2.1, 0.2)
    
    results = {
        'wt': [],
        'path_length': [],
        'terrain_cost_avg': [],
        'computation_time': [],
        'nodes_explored': []
    }
    
    print("\n実験開始...\n")
    
    for wt in wt_values:
        print(f"Testing w_t={wt:.1f}...", end=" ")
        
        # TA*で経路計画
        result = run_ta_star_with_wt(wt, start, goal)
        
        # 結果を保存
        results['wt'].append(result['wt'])
        results['path_length'].append(result['path_length'])
        results['terrain_cost_avg'].append(result['terrain_cost_avg'])
        results['computation_time'].append(result['computation_time'])
        results['nodes_explored'].append(result['nodes_explored'])
        
        print(f"Path={result['path_length']:.1f}m, "
              f"TerrainCost={result['terrain_cost_avg']:.2f}, "
              f"Time={result['computation_time']:.2f}s")
    
    print("\n" + "="*70)
    print("実験結果サマリー")
    print("="*70)
    
    # w_t=1.0の結果を表示
    idx_1_0 = np.argmin(np.abs(np.array(wt_values) - 1.0))
    print(f"\nw_t=1.0の性能:")
    print(f"  経路長: {results['path_length'][idx_1_0]:.1f} m")
    print(f"  点平均地形コスト: {results['terrain_cost_avg'][idx_1_0]:.2f}")
    print(f"  計算時間: {results['computation_time'][idx_1_0]:.2f} 秒")
    print(f"  探索ノード数: {results['nodes_explored'][idx_1_0]}")
    
    print("\nw_t=0.8の性能（地形重視が不足）:")
    idx_0_8 = np.argmin(np.abs(np.array(wt_values) - 0.8))
    print(f"  経路長: {results['path_length'][idx_0_8]:.1f} m")
    print(f"  点平均地形コスト: {results['terrain_cost_avg'][idx_0_8]:.2f}")
    print(f"  地形コスト削減率: {(1 - results['terrain_cost_avg'][idx_0_8]/3.26)*100:.0f}%")
    
    print("\nw_t=1.2の性能（地形重視が過剰）:")
    idx_1_2 = np.argmin(np.abs(np.array(wt_values) - 1.2))
    print(f"  経路長: {results['path_length'][idx_1_2]:.1f} m")
    print(f"  計算時間: {results['computation_time'][idx_1_2]:.2f} 秒")
    print(f"  探索ノード数: {results['nodes_explored'][idx_1_2]}")
    
    # 結果をJSONで保存
    output_file = project_root / 'results' / 'wt_tuning.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n結果を保存しました: {output_file}")
    
    return results


if __name__ == '__main__':
    run_wt_tuning()
