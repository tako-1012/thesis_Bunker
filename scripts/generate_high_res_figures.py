#!/usr/bin/env python3
"""
高解像度論文用図の生成
Generate high-resolution figures for LaTeX paper

改善点：
- DPI: 300 (論文品質)
- 図サイズ: 12 x 6インチ (十分な大きさ)
- フォントサイズ: 14pt (読みやすさ)
- 横軸ラベル: 10個に1個表示（重なり防止）

使用方法:
    python3 generate_high_res_figures.py
"""
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import math

# パス設定
ROOT = Path(__file__).resolve().parents[1]
RESULTS_FILE = ROOT / 'benchmark_results' / 'dataset3_8planners_results.json'
OUT_DIR = ROOT / 'figures' / 'high_res'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# プランナーリスト（6つ）
PLANNERS = ['D*Lite', 'RRT*', 'HPA*', 'SAFETY', 'FieldD*Hybrid', 'TA*']

# 高解像度図の設定
FIGURE_SIZE = (12, 6)  # 幅12インチ x 高さ6インチ
DPI = 300  # 論文品質
FONT_SIZE_LABEL = 16  # 軸ラベル
FONT_SIZE_TITLE = 18  # タイトル
FONT_SIZE_TICK = 14  # 目盛りラベル
FONT_SIZE_LEGEND = 14  # 凡例

# matplotlibのフォント設定
plt.rcParams.update({
    'font.size': FONT_SIZE_TICK,
    'axes.labelsize': FONT_SIZE_LABEL,
    'axes.titlesize': FONT_SIZE_TITLE,
    'legend.fontsize': FONT_SIZE_LEGEND,
    'xtick.labelsize': FONT_SIZE_TICK,
    'ytick.labelsize': FONT_SIZE_TICK,
    'figure.dpi': 100,  # 画面表示用
    'savefig.dpi': DPI,  # 保存時のDPI
})

print(f"Results file: {RESULTS_FILE}")
print(f"Output directory: {OUT_DIR}")
print(f"Figure settings: {FIGURE_SIZE[0]}x{FIGURE_SIZE[1]} inches @ {DPI} DPI")
print()

# Load results
with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
    raw = json.load(f)

# Build mapping: scenario_id -> {map_size, results: {planner: entry}}
scenarios = {}
for rec in raw:
    sid = rec.get('scenario_id') or rec.get('scenario_name')
    if sid is None:
        continue
    if sid not in scenarios:
        scenarios[sid] = {'map_size': rec.get('map_size'), 'results': {}}
    scenarios[sid]['results'][rec.get('planner')] = rec

scenario_ids = sorted(scenarios.keys())
print(f"Total scenarios: {len(scenario_ids)}")


# Helper function
def get_metric(sid, planner, key, success_key='success'):
    """指定したシナリオ・プランナー・メトリクスの値を取得"""
    rec = scenarios[sid]['results'].get(planner)
    if not rec:
        return float('nan')
    ok = rec.get(success_key, False)
    if not ok:
        return float('nan')
    
    # Support different key names
    if key in rec:
        return rec.get(key)
    
    # Fallback names
    if key == 'computation_time':
        return rec.get('computation_time')
    if key == 'path_length':
        return rec.get('path_length_meters') or rec.get('path_length') or rec.get('path_length_m')
    if key == 'nodes_explored':
        return rec.get('nodes_explored')
    
    return float('nan')


# ===== 図1: Computation Time Comparison =====
print('Creating high-res computation_time_comparison.png...')

fig, ax = plt.subplots(figsize=FIGURE_SIZE)
x = np.arange(len(scenario_ids))
width = 0.13  # バー幅

for i, planner in enumerate(PLANNERS):
    vals = [get_metric(sid, planner, 'computation_time') for sid in scenario_ids]
    vals = [float(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else np.nan for v in vals]
    ax.bar(x + width * (i - 2.5), vals, width, label=planner, alpha=0.85)

ax.set_xlabel('Scenario', fontsize=FONT_SIZE_LABEL)
ax.set_ylabel('Computation Time (s)', fontsize=FONT_SIZE_LABEL)
ax.set_title('Computation Time Comparison (6 Planners)', fontsize=FONT_SIZE_TITLE, fontweight='bold')

# 横軸ラベル: 10個に1個表示（重なり防止）
tick_interval = 10
tick_positions = x[::tick_interval]
tick_labels = [scenario_ids[i] for i in range(0, len(scenario_ids), tick_interval)]
ax.set_xticks(tick_positions)
ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=FONT_SIZE_TICK)

ax.legend(loc='upper left', fontsize=FONT_SIZE_LEGEND, framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
output_path = OUT_DIR / 'computation_time_comparison.png'
plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
print(f"✓ Saved: {output_path}")
plt.close()


# ===== 図2: Path Length Comparison =====
print('Creating high-res path_length_comparison.png...')

fig, ax = plt.subplots(figsize=FIGURE_SIZE)
x = np.arange(len(scenario_ids))

for i, planner in enumerate(PLANNERS):
    vals = [get_metric(sid, planner, 'path_length') for sid in scenario_ids]
    vals = [float(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else np.nan for v in vals]
    ax.bar(x + width * (i - 2.5), vals, width, label=planner, alpha=0.85)

ax.set_xlabel('Scenario', fontsize=FONT_SIZE_LABEL)
ax.set_ylabel('Path Length (m)', fontsize=FONT_SIZE_LABEL)
ax.set_title('Path Length Comparison (6 Planners)', fontsize=FONT_SIZE_TITLE, fontweight='bold')

# 横軸ラベル: 10個に1個表示
ax.set_xticks(tick_positions)
ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=FONT_SIZE_TICK)

ax.legend(loc='upper left', fontsize=FONT_SIZE_LEGEND, framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
output_path = OUT_DIR / 'path_length_comparison.png'
plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
print(f"✓ Saved: {output_path}")
plt.close()


# ===== 図3: オプション - ラベル回転版（方法B） =====
print('Creating alternative version with rotated labels...')

fig, ax = plt.subplots(figsize=FIGURE_SIZE)
x = np.arange(len(scenario_ids))

for i, planner in enumerate(PLANNERS):
    vals = [get_metric(sid, planner, 'computation_time') for sid in scenario_ids]
    vals = [float(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else np.nan for v in vals]
    ax.bar(x + width * (i - 2.5), vals, width, label=planner, alpha=0.85)

ax.set_xlabel('Scenario', fontsize=FONT_SIZE_LABEL)
ax.set_ylabel('Computation Time (s)', fontsize=FONT_SIZE_LABEL)
ax.set_title('Computation Time Comparison - All Labels (Rotated)', fontsize=FONT_SIZE_TITLE, fontweight='bold')

# すべてのラベルを表示（90度回転、小さめフォント）
ax.set_xticks(x)
ax.set_xticklabels(scenario_ids, rotation=90, ha='right', fontsize=10)

ax.legend(loc='upper left', fontsize=FONT_SIZE_LEGEND, framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
output_path = OUT_DIR / 'computation_time_comparison_rotated.png'
plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
print(f"✓ Saved: {output_path}")
plt.close()


# ===== 図4: オプション - シンプル横軸版（方法D） =====
print('Creating simplified version with minimal x-axis...')

fig, ax = plt.subplots(figsize=FIGURE_SIZE)
x = np.arange(len(scenario_ids))

for i, planner in enumerate(PLANNERS):
    vals = [get_metric(sid, planner, 'path_length') for sid in scenario_ids]
    vals = [float(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else np.nan for v in vals]
    ax.bar(x + width * (i - 2.5), vals, width, label=planner, alpha=0.85)

ax.set_xlabel('Scenario Index', fontsize=FONT_SIZE_LABEL)
ax.set_ylabel('Path Length (m)', fontsize=FONT_SIZE_LABEL)
ax.set_title('Path Length Comparison - Indexed', fontsize=FONT_SIZE_TITLE, fontweight='bold')

# シナリオ番号のみ表示
ax.set_xticks(x[::5])  # 5個に1個
ax.set_xticklabels([f'{i}' for i in range(0, len(scenario_ids), 5)], fontsize=FONT_SIZE_TICK)

ax.legend(loc='upper left', fontsize=FONT_SIZE_LEGEND, framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
output_path = OUT_DIR / 'path_length_comparison_indexed.png'
plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
print(f"✓ Saved: {output_path}")
plt.close()

print("\n" + "="*60)
print("全ての図を生成しました！")
print(f"出力先: {OUT_DIR}")
print("="*60)
print("\n生成された図:")
print("  1. computation_time_comparison.png (推奨: 10個に1個ラベル)")
print("  2. path_length_comparison.png (推奨: 10個に1個ラベル)")
print("  3. computation_time_comparison_rotated.png (オプション: 全ラベル90度回転)")
print("  4. path_length_comparison_indexed.png (オプション: インデックス表示)")
print("\n論文には1と2がおすすめです。")
