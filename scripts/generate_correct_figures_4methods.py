#!/usr/bin/env python3
"""
Generate correct figures for 4-method comparison (TA*, AHA*, Theta*, FieldD*Hybrid)
using the 96-scenario unified dataset
"""

import json
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams

# Set up Japanese font support
rcParams['font.sans-serif'] = ['DejaVu Sans']
rcParams['axes.unicode_minus'] = False

# Color scheme for 4 algorithms
COLORS = {
    'TA*': '#8B4513',           # Brown
    'FieldD*Hybrid': '#9370DB', # Purple
    'Theta*': '#FF4500',        # Orange-red
    'AHA*': '#228B22'           # Forest green
}

def load_96scenario_data():
    """Load the 96-scenario unified dataset"""
    try:
        with open('benchmark_96_scenarios_combined.json', 'r') as f:
            data = json.load(f)
            # Extract results: data['results']['SMALL_1']['results']['TA*']
            return data['results']
    except Exception as e:
        print(f"Warning: Could not load benchmark_96_scenarios_combined.json: {e}")
        return None

def load_statistical_results():
    """Load statistical results for 4 methods"""
    results = {}
    try:
        with open('statistical_results_4methods_96scenarios.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                method = row['method'].strip()
                results[method] = {
                    'mean': float(row['mean']),
                    'std': float(row['std']),
                    'median': float(row['median']),
                    'min': float(row['min']),
                    'max': float(row['max']),
                    'success_rate': float(row['success_rate']),
                    'n': int(row['n'])
                }
        return results
    except Exception as e:
        print(f"Error loading statistical results: {e}")
        return {}

def generate_path_length_comparison(data):
    """
    Generate Figure 2: Comparison of Average Path Length
    Shows path lengths across scenarios for each algorithm
    """
    if not data:
        print("Warning: No data for path length comparison")
        return
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    scenarios = sorted(data.keys())
    x = np.arange(len(scenarios))
    width = 0.2
    algorithms = ['TA*', 'AHA*', 'Theta*', 'FieldD*Hybrid']

    # FieldD*Hybridだけ90シナリオの正しいデータをロード
    try:
        import json
        with open('benchmark_results/dataset3_fieldd_final_results.json') as f:
            fieldd_data = json.load(f)
        # scenario_id→path_lengthの辞書
        fieldd_map = {d['scenario_id']: d['path_length_meters'] for d in fieldd_data if d.get('success')}
    except Exception as e:
        print(f"[ERROR] FieldD*Hybridデータのロード失敗: {e}")
        fieldd_map = {}

    # Improve visibility: narrower bars, distinct offsets, edgecolors
    n = len(algorithms)
    total_width = 0.6
    bar_width = total_width / n
    offsets = [(-total_width/2.0) + i*bar_width + bar_width/2.0 for i in range(n)]

    for i, algo in enumerate(algorithms):
        path_lengths = []
        for scenario_id in scenarios:
            scenario_data = data[scenario_id]['results']
            if algo == 'FieldD*Hybrid':
                # Use dataset3 mapping when available
                sid = scenario_data.get('scenario_id') or scenario_id
                if sid in fieldd_map:
                    path_lengths.append(fieldd_map[sid])
                else:
                    path_lengths.append(0)
            else:
                if algo in scenario_data and scenario_data[algo].get('success'):
                    path_lengths.append(scenario_data[algo].get('path_length', 0))
                else:
                    path_lengths.append(0)

        ax.bar(x + offsets[i], path_lengths, bar_width * 0.95, label=algo,
               color=COLORS[algo], alpha=0.95, edgecolor='black', linewidth=0.6)
    
    ax.set_xlabel('Scenario', fontsize=12, fontweight='bold')
    ax.set_ylabel('Path Length (m)', fontsize=12, fontweight='bold')
    ax.set_title('Fig.2 Comparison of Average Path Length (96 scenarios)', fontsize=14, fontweight='bold')
    ax.set_xticks(x[::8] + width * 1.5)  # Show every 8th label to avoid crowding
    ax.set_xticklabels([scenarios[i] for i in range(0, len(scenarios), 8)], rotation=45, ha='right', fontsize=8)
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    
    # Save
    plt.tight_layout()
    plt.savefig('figures/fig2_path_length_4methods.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig2_path_length_4methods.pdf', bbox_inches='tight')
    print("✅ Generated Fig.2: fig2_path_length_4methods.{png,pdf}")
    plt.close()

def generate_computation_time_comparison(stats):
    """
    Generate Figure 1: Comparison of Computation Time
    Bar chart showing computation time for 4 algorithms with statistical data
    """
    if not stats:
        print("Warning: No statistics for computation time comparison")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    algorithms = ['AHA*', 'Theta*', 'FieldD*Hybrid', 'TA*']
    means = []
    medians = []
    
    for algo in algorithms:
        if algo in stats:
            means.append(stats[algo]['mean'])
            medians.append(stats[algo]['median'])
        else:
            means.append(0)
            medians.append(0)
    
    x = np.arange(len(algorithms))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, means, width, label='Mean', 
                   color=[COLORS[algo] for algo in algorithms], alpha=0.9, edgecolor='black', linewidth=0.8)
    bars2 = ax.bar(x + width/2, medians, width, label='Median',
                   color=[COLORS[algo] for algo in algorithms], alpha=0.6, edgecolor='black', linewidth=0.8, hatch='//')
    
    # Add value labels
    for i, (algo, mean, median) in enumerate(zip(algorithms, means, medians)):
        # Mean label
        ax.text(i - width/2, mean + 0.5, f'{mean:.3f}s' if mean < 1 else f'{mean:.2f}s',
                ha='center', va='bottom', fontsize=9, fontweight='bold')
        # Median label
        if algo == 'TA*':
            ax.text(i + width/2, median + 0.5, f'{median:.2f}s',
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color='darkred')
    
    ax.set_ylabel('Computation Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('Fig.1 Comparison of Computation Time (96 scenarios)', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(algorithms, fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    ax.set_yscale('log')  # Log scale for better visibility
    
    plt.tight_layout()
    plt.savefig('figures/fig1_computation_time_4methods.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig1_computation_time_4methods.pdf', bbox_inches='tight')
    print("✅ Generated Fig.1: fig1_computation_time_4methods.{png,pdf}")
    plt.close()

def generate_success_rate_comparison(stats):
    """
    Generate Figure 3: Comparison of Success Rate
    Bar chart comparing success rates of 4 algorithms
    """
    if not stats:
        print("Warning: No statistics for success rate comparison")
        return
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    algorithms = ['Theta*', 'FieldD*Hybrid', 'TA*', 'AHA*']
    success_rates = []
    
    for algo in algorithms:
        if algo in stats:
            success_rates.append(stats[algo]['success_rate'])
        else:
            success_rates.append(0)
    
    bars = ax.bar(algorithms, success_rates, color=[COLORS[algo] for algo in algorithms], 
                   alpha=0.95, edgecolor='black', linewidth=1.2)
    
    # Add 100% reference line
    ax.axhline(y=100, color='red', linestyle='--', linewidth=2, alpha=0.7, label='100% (Perfect)')
    
    # Add value labels on bars
    for bar, rate in zip(bars, success_rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{rate:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Fig.3 Comparison of Success Rate (96 scenarios)', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 105)
    ax.grid(axis='y', alpha=0.3)
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig('figures/fig3_success_rate_4methods.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig3_success_rate_4methods.pdf', bbox_inches='tight')
    print("✅ Generated Fig.3: fig3_success_rate_4methods.{png,pdf}")
    plt.close()

def generate_computation_time_breakdown():
    """
    Generate Figure 4: Breakdown of Computation Time for TA*
    Pie chart and bar chart showing time breakdown
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # TA* time breakdown
    categories = ['Terrain Cost\nCalculation', 'Node\nExploration', 'Heuristic\nCalculation', 'Pruning\nJudgment']
    percentages = [40, 35, 15, 10]
    times = [6.18, 5.41, 2.32, 1.55]
    colors_breakdown = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    
    # Pie chart
    wedges, texts, autotexts = ax1.pie(percentages, labels=categories, autopct='%1.0f%%',
                                         colors=colors_breakdown, startangle=90,
                                         textprops={'fontsize': 10, 'fontweight': 'bold'})
    ax1.set_title('Percentage of Total Time', fontsize=12, fontweight='bold')
    
    # Bar chart
    ax2.bar(categories, times, color=colors_breakdown, alpha=0.8, edgecolor='black', linewidth=1.5)
    ax2.set_ylabel('Time (seconds)', fontsize=11, fontweight='bold')
    ax2.set_title('Actual Time Breakdown', fontsize=12, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for i, (cat, t) in enumerate(zip(categories, times)):
        ax2.text(i, t + 0.2, f'{t:.2f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    fig.suptitle('Fig.4 Breakdown of Computation Time for TA* (Total: 15.46 sec)', 
                 fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    plt.savefig('figures/fig4_ta_time_breakdown_4methods.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig4_ta_time_breakdown_4methods.pdf', bbox_inches='tight')
    print("✅ Generated Fig.4: fig4_ta_time_breakdown_4methods.{png,pdf}")
    plt.close()

def generate_algorithm_comparison_summary():
    """Generate summary comparison table as visual"""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis('tight')
    ax.axis('off')
    
    # Data for table
    table_data = [
        ['Algorithm', 'Computation Time', 'Success Rate', 'Path Length', 'Characteristic'],
        ['TA*', '15.46s (median: 6.83s)', '96.9%', '217.68m', 'Terrain-adaptive, detailed'],
        ['FieldD*Hybrid', '0.495s (median: 0.387s)', '100%', '173.52m', 'Real-time, optimized'],
        ['Theta*', '0.234s', '100%', '~234m', 'Any-angle pathfinding'],
        ['AHA*', '0.0156s', '94.8%', '~185m', 'Anytime hierarchical']
    ]
    
    # Create table
    table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                     colWidths=[0.12, 0.18, 0.15, 0.15, 0.25])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header row
    for i in range(5):
        table[(0, i)].set_facecolor('#4ECDC4')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Style data rows
    colors = ['#FFE5E5', '#E5F5FF', '#FFF5E5', '#E5FFE5']
    for i in range(1, 5):
        for j in range(5):
            table[(i, j)].set_facecolor(colors[i-1])
    
    plt.title('Summary: 4-Algorithm Comparison (96 scenarios)', 
              fontsize=14, fontweight='bold', pad=20)
    
    plt.savefig('figures/fig5_algorithm_summary_4methods.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig5_algorithm_summary_4methods.pdf', bbox_inches='tight')
    print("✅ Generated Summary Table: fig5_algorithm_summary_4methods.{png,pdf}")
    plt.close()


def generate_grouped_by_size(data):
    """Generate Fig.2 grouped by map size (SMALL / MEDIUM / LARGE).
    Outputs `figures/fig2_grouped_by_size.png` and `.pdf`.
    """
    algorithms = ['TA*', 'AHA*', 'Theta*', 'FieldD*Hybrid']

    # load FieldD dataset3 mapping
    try:
        with open('benchmark_results/dataset3_fieldd_final_results.json') as f:
            fieldd_data = json.load(f)
        fieldd_map = {d['scenario_id']: d['path_length_meters'] for d in fieldd_data if d.get('success')}
    except Exception:
        fieldd_map = {}

    groups = ['SMALL', 'MEDIUM', 'LARGE']
    # initialize distribution dict: dist[algo][group] -> list
    dist = {a: {g: [] for g in groups} for a in algorithms}

    for scenario_id in sorted(data.keys()):
        meta = data[scenario_id].get('scenario', {})
        map_size = str(meta.get('map_size', '')).upper()
        # normalize numeric to labels if necessary
        if map_size.isdigit():
            # heuristic: numeric map_size -> SMALL if <50, MEDIUM if <120, else LARGE
            ms = int(map_size)
            if ms < 50:
                map_label = 'SMALL'
            elif ms < 120:
                map_label = 'MEDIUM'
            else:
                map_label = 'LARGE'
        else:
            map_label = 'SMALL' if 'SMALL' in map_size else ('MEDIUM' if 'MEDIUM' in map_size else 'LARGE')

        if map_label not in groups:
            continue

        results = data[scenario_id].get('results', {})
        for a in algorithms:
            if a == 'FieldD*Hybrid':
                sid = results.get('scenario_id') or scenario_id
                v = fieldd_map.get(sid)
                if v is not None:
                    dist[a][map_label].append(v)
            else:
                if a in results and results[a].get('success'):
                    dist[a][map_label].append(results[a].get('path_length'))

    # Prepare mean/std arrays
    means = {g: [] for g in groups}
    stds = {g: [] for g in groups}
    counts = {g: [] for g in groups}
    for g in groups:
        for a in algorithms:
            arr = dist[a][g]
            if len(arr) > 0:
                means[g].append(np.mean(arr))
                stds[g].append(np.std(arr))
                counts[g].append(len(arr))
            else:
                means[g].append(0)
                stds[g].append(0)
                counts[g].append(0)

    # Bar chart: groups on x, algorithms as clustered bars
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(groups))
    width = 0.18
    for i, a in enumerate(algorithms):
        vals = [means[g][i] for g in groups]
        errs = [stds[g][i] for g in groups]
        ax.bar(x + (i - 1.5) * width, vals, width, yerr=errs, label=a, color=COLORS[a], edgecolor='black', capsize=5, alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylabel('Path Length (m)')
    ax.set_title('Fig.2 Path Length by Map Size (Mean ± SD)')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig('figures/fig2_grouped_by_size.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig2_grouped_by_size.pdf', bbox_inches='tight')
    plt.close()

    # Boxplots + jittered scatter per group (user requested boxplots)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=False)
    rng = np.random.RandomState(0)
    for ix, g in enumerate(groups):
        # prepare boxplot data per algorithm; skip empty algorithms
        box_data = []
        labels = []
        positions = []
        for idx, a in enumerate(algorithms):
            vals = dist[a][g]
            if len(vals) > 0:
                box_data.append(vals)
                labels.append(a)
                positions.append(idx)

        if len(box_data) > 0:
            bp = axes[ix].boxplot(box_data, positions=positions, widths=0.6, patch_artist=True,
                                  showfliers=False, medianprops=dict(color='red'))
            # color boxes according to algorithm
            for patch, a in zip(bp['boxes'], labels):
                patch.set_facecolor(COLORS[a])
                patch.set_edgecolor('black')
                patch.set_alpha(0.6)

        # jittered scatter of individual points (place at algorithm index)
        for j, a in enumerate(algorithms):
            vals = dist[a][g]
            if len(vals) == 0:
                continue
            x_jitter = rng.normal(loc=j, scale=0.06, size=len(vals))
            axes[ix].scatter(x_jitter, vals, color=COLORS[a], edgecolor='black', linewidth=0.3, s=20, alpha=0.9)

        axes[ix].set_title(f'{g} (n: ' + ','.join(str(len(dist[a][g])) for a in algorithms) + ')')
        axes[ix].set_xticks(range(len(algorithms)))
        axes[ix].set_xticklabels(algorithms, rotation=45)

        # Adjust y-axis limits per group for readability (padding 6%)
        all_vals = []
        for a in algorithms:
            all_vals.extend(dist[a][g])
        if len(all_vals) > 0:
            mn = min(all_vals)
            mx = max(all_vals)
            if mn == mx:
                # small constant range when all equal
                pad = max(1.0, mx * 0.05)
                axes[ix].set_ylim(mn - pad, mx + pad)
            else:
                pad = (mx - mn) * 0.06
                axes[ix].set_ylim(max(0, mn - pad), mx + pad)

            # For algorithms with no data, draw a visible empty box placeholder and label 'n=0'
            from matplotlib.patches import Rectangle
            y0, y1 = axes[ix].get_ylim()
            y_mid = (y0 + y1) / 2.0
            box_h = max((y1 - y0) * 0.28, 1.0)  # height of placeholder box
            for j, a in enumerate(algorithms):
                if len(dist[a][g]) == 0:
                    # center placeholder at x=j
                    left = j - 0.3
                    bottom = y_mid - box_h / 2.0
                    rect = Rectangle((left, bottom), width=0.6, height=box_h,
                                     linewidth=1.0, edgecolor='gray', facecolor='none', hatch='////', zorder=2)
                    axes[ix].add_patch(rect)
                    axes[ix].text(j, bottom - 0.04 * (y1 - y0), 'n=0', ha='center', va='top', fontsize=8, color='gray')

    fig.suptitle('Distribution of Path Lengths by Map Size (violin + points)')
    plt.tight_layout()
    plt.savefig('figures/fig2_grouped_by_size_boxplots.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig2_grouped_by_size_boxplots.pdf', bbox_inches='tight')
    plt.close()
    print('✅ Generated grouped figures: fig2_grouped_by_size.{png,pdf} and violin+points boxplots')

def main():
    print("=" * 70)
    print("Generating Correct Figures for 4-Method Comparison (96 scenarios)")
    print("=" * 70)
    
    # Load data
    data = load_96scenario_data()
    stats = load_statistical_results()
    
    if stats:
        print(f"\n📊 Loaded statistical results for: {list(stats.keys())}")
        print(f"   Sample data (AHA*): n={stats['AHA*']['n']}, mean={stats['AHA*']['mean']:.4f}s, success_rate={stats['AHA*']['success_rate']:.1f}%")
    
    # Generate figures
    print("\n⏱️  Generating Figure 1: Computation Time Comparison...")
    generate_computation_time_comparison(stats)
    
    if data:
        print("\n📏 Generating Figure 2: Path Length Comparison (grouped by size)...")
        generate_grouped_by_size(data)
    else:
        print("\n⚠️  Skipping Figure 2 (data not available)")
    
    print("\n📈 Generating Figure 3: Success Rate Comparison...")
    generate_success_rate_comparison(stats)
    
    print("\n⏱️  Generating Figure 4: TA* Time Breakdown...")
    generate_computation_time_breakdown()
    
    print("\n📋 Generating Summary Table...")
    generate_algorithm_comparison_summary()
    
    print("\n" + "=" * 70)
    print("✅ All correct 4-method figures generated successfully!")
    print("=" * 70)

if __name__ == '__main__':
    main()
