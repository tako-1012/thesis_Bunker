#!/usr/bin/env python3
"""
TA* vs FieldD*Hybrid 性能比較分析

データ:
- TA* (96シナリオ)
- FieldD*Hybrid (90シナリオ、dataset3)

比較メトリクス:
- 計算時間
- 成功率
- パス長
- 統計的有意性（Welch t検定）
- 効果量（Cohen's d）
"""

import json
import numpy as np
from scipy import stats
from pathlib import Path

def compare_ta_vs_fieldd():
    print("=" * 70)
    print("🔬 TA* vs FieldD*Hybrid 性能比較")
    print("=" * 70)
    
    # TA*データを読み込む（96シナリオ）
    with open('/home/hayashi/thesis_work/benchmark_96_scenarios_combined.json', 'r') as f:
        ta_data = json.load(f)
    
    # FieldD*Hybridデータを読み込む（90シナリオ）
    with open('/home/hayashi/thesis_work/benchmark_results/dataset3_fieldd_final_results.json', 'r') as f:
        fieldd_list = json.load(f)
    
    # TA*の計算時間を抽出
    ta_times = []
    ta_success = 0
    ta_total = 0
    
    for scenario_data in ta_data['results'].values():
        if 'results' in scenario_data and 'TA*' in scenario_data['results']:
            ta_result = scenario_data['results']['TA*']
            ta_times.append(ta_result.get('computation_time', 0))
            ta_total += 1
            if ta_result.get('success', False):
                ta_success += 1
    
    ta_times = np.array(ta_times)
    
    # FieldD*の計算時間を抽出
    fieldd_times = []
    fieldd_success = 0
    fieldd_total = 0
    
    for result in fieldd_list:
        fieldd_times.append(result['computation_time'])
        fieldd_total += 1
        if result.get('success', False):
            fieldd_success += 1
    
    fieldd_times = np.array(fieldd_times)
    
    print(f"\n📊 データセット情報")
    print(f"TA*:              {len(ta_times)} シナリオ")
    print(f"FieldD*Hybrid:    {len(fieldd_times)} シナリオ")
    print()
    
    # 記述統計量
    print("=" * 70)
    print("📈 記述統計量")
    print("=" * 70)
    print(f"\n{'手法':<20} | {'平均(秒)':<12} | {'SD':<12} | {'中央値':<12} | {'成功率'}")
    print("-" * 70)
    
    print(f"{'TA*':<20} | {np.mean(ta_times):>10.4f}s | {np.std(ta_times, ddof=1):>10.4f}s | {np.median(ta_times):>10.4f}s | {ta_success}/{ta_total} ({100*ta_success/ta_total:.1f}%)")
    print(f"{'FieldD*Hybrid':<20} | {np.mean(fieldd_times):>10.4f}s | {np.std(fieldd_times, ddof=1):>10.4f}s | {np.median(fieldd_times):>10.4f}s | {fieldd_success}/{fieldd_total} ({100*fieldd_success/fieldd_total:.1f}%)")
    
    # 四分位数
    print(f"\n{'手法':<20} | {'Q1':<12} | {'Q3':<12} | {'IQR':<12}")
    print("-" * 70)
    q1_ta = np.percentile(ta_times, 25)
    q3_ta = np.percentile(ta_times, 75)
    print(f"{'TA*':<20} | {q1_ta:>10.4f}s | {q3_ta:>10.4f}s | {q3_ta-q1_ta:>10.4f}s")
    
    q1_fd = np.percentile(fieldd_times, 25)
    q3_fd = np.percentile(fieldd_times, 75)
    print(f"{'FieldD*Hybrid':<20} | {q1_fd:>10.4f}s | {q3_fd:>10.4f}s | {q3_fd-q1_fd:>10.4f}s")
    
    # Welch t検定
    print("\n" + "=" * 70)
    print("🔍 統計検定 (Welch t検定)")
    print("=" * 70)
    
    t_stat, p_value = stats.ttest_ind(ta_times, fieldd_times, equal_var=False)
    
    # Cohen's d
    n1, n2 = len(ta_times), len(fieldd_times)
    mean1, mean2 = np.mean(ta_times), np.mean(fieldd_times)
    std1, std2 = np.std(ta_times, ddof=1), np.std(fieldd_times, ddof=1)
    
    pooled_std = np.sqrt(((n1-1)*std1**2 + (n2-1)*std2**2) / (n1+n2-2))
    cohens_d = (mean1 - mean2) / pooled_std if pooled_std != 0 else 0
    
    # 信頼区間
    dof_ta = n1 - 1
    dof_fd = n2 - 1
    t_crit_ta = stats.t.ppf(0.975, dof_ta)
    t_crit_fd = stats.t.ppf(0.975, dof_fd)
    
    ci_ta_lower = mean1 - t_crit_ta * std1 / np.sqrt(n1)
    ci_ta_upper = mean1 + t_crit_ta * std1 / np.sqrt(n1)
    
    ci_fd_lower = mean2 - t_crit_fd * std2 / np.sqrt(n2)
    ci_fd_upper = mean2 + t_crit_fd * std2 / np.sqrt(n2)
    
    print(f"\n✅ 検定結果")
    print(f"  t統計量: {t_stat:.4f}")
    print(f"  p値: {p_value:.6f}")
    print(f"  Cohen's d: {cohens_d:.4f}")
    
    # 結果解釈
    if p_value < 0.001:
        sig_level = "***非常に有意 (p < 0.001)"
    elif p_value < 0.01:
        sig_level = "**非常に有意 (p < 0.01)"
    elif p_value < 0.05:
        sig_level = "*有意 (p < 0.05)"
    else:
        sig_level = "有意でない (p ≥ 0.05)"
    
    print(f"\n📌 統計的結論: {sig_level}")
    
    if abs(cohens_d) < 0.2:
        effect = "無視できる効果"
    elif abs(cohens_d) < 0.5:
        effect = "小さい効果"
    elif abs(cohens_d) < 0.8:
        effect = "中程度の効果"
    else:
        effect = "大きい効果"
    
    print(f"📌 効果量: {effect} (|d| = {abs(cohens_d):.4f})")
    
    # 95%信頼区間
    print(f"\n95%信頼区間:")
    print(f"  TA*:           [{ci_ta_lower:.4f}, {ci_ta_upper:.4f}] 秒")
    print(f"  FieldD*Hybrid: [{ci_fd_lower:.4f}, {ci_fd_upper:.4f}] 秒")
    
    # 平均差
    mean_diff = mean1 - mean2
    print(f"\n平均時間差: {mean_diff:.4f}秒 ({abs(mean_diff/mean2)*100:.1f}% {'遅い' if mean_diff > 0 else '高速'})")
    
    print("\n" + "=" * 70)
    print("🎯 総合評価")
    print("=" * 70)
    
    print(f"""
【計算時間】
  • TA*: {mean1:.4f}秒 ± {std1:.4f}
  • FieldD*Hybrid: {mean2:.4f}秒 ± {std2:.4f}
  → FieldD*Hybridが {abs(mean_diff):.4f}秒 {'遅い' if mean_diff > 0 else '高速'} 

【成功率】
  • TA*: {100*ta_success/ta_total:.1f}% ({ta_success}/{ta_total})
  • FieldD*Hybrid: {100*fieldd_success/fieldd_total:.1f}% ({fieldd_success}/{fieldd_total})
  
【安定性（標準偏差）】
  • TA*: {std1:.4f}秒 (変動係数: {100*std1/mean1:.1f}%)
  • FieldD*Hybrid: {std2:.4f}秒 (変動係数: {100*std2/mean2:.1f}%)
  → {"TA*の方が安定" if std1 < std2 else "FieldD*Hybridの方が安定"}

【統計的有意性】
  • p値 = {p_value:.6f} ({sig_level})
  • Cohen's d = {cohens_d:.4f} ({effect})
  
""")
    
    # 優劣判定
    print("=" * 70)
    print("🏆 優劣判定")
    print("=" * 70)
    
    winner_speed = "FieldD*Hybrid" if mean2 < mean1 else "TA*"
    winner_stability = "TA*" if std1 < std2 else "FieldD*Hybrid"
    winner_success = "TA*" if ta_success/ta_total > fieldd_success/fieldd_total else "FieldD*Hybrid"
    
    print(f"\n✅ 計算速度が優れている: {winner_speed} ({abs(mean_diff):.4f}秒高速)")
    print(f"✅ 安定性が優れている: {winner_stability}")
    print(f"✅ 成功率が高い: {winner_success}")
    
    print("\n📋 用途別推奨:")
    if mean2 < mean1 and fieldd_success/fieldd_total >= 0.95:
        print("  🥇 FieldD*Hybrid: 高速性重視のアプリケーション")
        print("  🥈 TA*: 確実性重視のアプリケーション")
    elif ta_success/ta_total > fieldd_success/fieldd_total and std1 < std2:
        print("  🥇 TA*: 信頼性と安定性が重要な場面")
        print("  🥈 FieldD*Hybrid: リアルタイム応答が必要な場面")
    else:
        print("  💡 シーン別に使い分け推奨")


if __name__ == '__main__':
    compare_ta_vs_fieldd()
