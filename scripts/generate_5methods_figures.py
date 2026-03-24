#!/usr/bin/env python3
"""
Generate high-resolution comparison figures for 5 methods

Methods:
  1. Regular A* (baseline)
  2. D*Lite (baseline)
  3. RRT* (baseline)
  4. FieldD*Hybrid (proposed)
  5. TA* (proposed)

Figures:
  - Computation Time Comparison (5 Methods)
  - Path Length Comparison (5 Methods)

Settings:
  - DPI: 300
  - Size: 12×6 inches
  - Fonts: title=18pt, labels=16pt, ticks=14pt
  - X-axis: every 10th scenario labeled
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

# Configuration
DPI = 300
FIGURE_SIZE = (12, 6)
FONT_TITLE = 18
FONT_LABEL = 16
FONT_TICK = 14

# 5 methods to include
METHODS = ['A*', 'D*Lite', 'RRT*', 'FieldD*Hybrid', 'TA*']

# Color scheme
COLORS = {
    'A*': '#1f77b4',           # Blue (baseline)
    'D*Lite': '#ff7f0e',       # Orange (baseline)
    'RRT*': '#2ca02c',         # Green (baseline)
    'FieldD*Hybrid': '#d62728', # Red (proposed)
    'TA*': '#9467bd'            # Purple (proposed)
}

# Line styles (proposed methods get thicker lines)
LINEWIDTHS = {
    'A*': 1.5,
    'D*Lite': 1.5,
    'RRT*': 1.5,
    'FieldD*Hybrid': 2.5,
    'TA*': 2.5
}

# Marker styles
MARKERS = {
    'A*': 'o',
    'D*Lite': 's',
    'RRT*': '^',
    'FieldD*Hybrid': 'D',
    'TA*': '*'
}


def load_results(json_path):
    """Load benchmark results from JSON"""
    with open(json_path, 'r') as f:
        results = json.load(f)
    return results


def organize_by_scenario(results, methods):
    """Organize results by scenario for selected methods"""
    data = defaultdict(lambda: defaultdict(dict))
    
    for entry in results:
        planner = entry.get('planner')
        if planner not in methods:
            continue
        
        scenario_id = entry.get('scenario_id', 'unknown')
        success = entry.get('success', False)
        
        data[scenario_id][planner] = {
            'success': success,
            'time': entry.get('computation_time', None),
            'path': entry.get('path_length_meters', None),
            'nodes': entry.get('nodes_explored', 0)
        }
    
    return data


def prepare_plot_data(data, methods):
    """Prepare data for plotting"""
    # Sort scenarios by ID
    sorted_scenarios = sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 999)
    
    plot_data = {method: {'times': [], 'paths': [], 'scenario_ids': []} 
                 for method in methods}
    
    for sid in sorted_scenarios:
        for method in methods:
            if method in data[sid]:
                entry = data[sid][method]
                if entry['success']:
                    plot_data[method]['times'].append(entry['time'])
                    plot_data[method]['paths'].append(entry['path'])
                else:
                    plot_data[method]['times'].append(None)
                    plot_data[method]['paths'].append(None)
            else:
                plot_data[method]['times'].append(None)
                plot_data[method]['paths'].append(None)
            
            plot_data[method]['scenario_ids'].append(sid)
    
    return plot_data, sorted_scenarios


def create_computation_time_figure(plot_data, methods, output_path):
    """Generate computation time comparison figure"""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE, dpi=DPI)
    
    for method in methods:
        times = plot_data[method]['times']
        x_indices = np.arange(len(times))
        
        # Plot only successful runs
        valid_x = [i for i, t in enumerate(times) if t is not None]
        valid_times = [t for t in times if t is not None]
        
        ax.plot(valid_x, valid_times, 
                label=method,
                color=COLORS[method],
                linewidth=LINEWIDTHS[method],
                marker=MARKERS[method],
                markersize=4,
                markevery=5,
                alpha=0.8)
    
    # Formatting
    ax.set_xlabel('Scenario Index', fontsize=FONT_LABEL, fontweight='bold')
    ax.set_ylabel('Computation Time (s)', fontsize=FONT_LABEL, fontweight='bold')
    ax.set_title('Computation Time Comparison (5 Methods)', 
                 fontsize=FONT_TITLE, fontweight='bold', pad=20)
    
    # X-axis: show every 10th label
    total_scenarios = len(plot_data[methods[0]]['scenario_ids'])
    tick_positions = list(range(0, total_scenarios, 10))
    tick_labels = [str(i) for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=FONT_TICK)
    ax.tick_params(axis='y', labelsize=FONT_TICK)
    
    # Legend
    ax.legend(fontsize=FONT_TICK, loc='upper left', framealpha=0.9)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
    plt.close()
    
    print(f'✓ Saved: {output_path}')


def create_path_length_figure(plot_data, methods, output_path):
    """Generate path length comparison figure"""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE, dpi=DPI)
    
    for method in methods:
        paths = plot_data[method]['paths']
        x_indices = np.arange(len(paths))
        
        # Plot only successful runs
        valid_x = [i for i, p in enumerate(paths) if p is not None]
        valid_paths = [p for p in paths if p is not None]
        
        ax.plot(valid_x, valid_paths,
                label=method,
                color=COLORS[method],
                linewidth=LINEWIDTHS[method],
                marker=MARKERS[method],
                markersize=4,
                markevery=5,
                alpha=0.8)
    
    # Formatting
    ax.set_xlabel('Scenario Index', fontsize=FONT_LABEL, fontweight='bold')
    ax.set_ylabel('Path Length (m)', fontsize=FONT_LABEL, fontweight='bold')
    ax.set_title('Path Length Comparison (5 Methods)',
                 fontsize=FONT_TITLE, fontweight='bold', pad=20)
    
    # X-axis: show every 10th label
    total_scenarios = len(plot_data[methods[0]]['scenario_ids'])
    tick_positions = list(range(0, total_scenarios, 10))
    tick_labels = [str(i) for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=FONT_TICK)
    ax.tick_params(axis='y', labelsize=FONT_TICK)
    
    # Legend
    ax.legend(fontsize=FONT_TICK, loc='upper left', framealpha=0.9)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight')
    plt.close()
    
    print(f'✓ Saved: {output_path}')


def print_statistics(plot_data, methods):
    """Print summary statistics for each method"""
    print()
    print('='*80)
    print('STATISTICS SUMMARY (5 Methods)')
    print('='*80)
    print()
    
    for method in methods:
        times = [t for t in plot_data[method]['times'] if t is not None]
        paths = [p for p in plot_data[method]['paths'] if p is not None]
        
        if times and paths:
            print(f'{method:20s}')
            print(f'  Success Rate:    {len(times):3d}/{len(plot_data[method]["times"]):3d} ({len(times)/len(plot_data[method]["times"])*100:5.1f}%)')
            print(f'  Avg Time:        {np.mean(times):8.4f} s')
            print(f'  Median Time:     {np.median(times):8.4f} s')
            print(f'  Avg Path:        {np.mean(paths):8.2f} m')
            print(f'  Median Path:     {np.median(paths):8.2f} m')
            print(f'  Min Path:        {np.min(paths):8.2f} m')
            print(f'  Max Path:        {np.max(paths):8.2f} m')
            print()


def main():
    # Paths
    results_path = 'benchmark_results/dataset3_5methods_combined_results.json'
    output_dir = Path('figures/5methods')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if results file exists
    if not Path(results_path).exists():
        print(f'Error: {results_path} not found!')
        print('Please combine results first:')
        print('  python3 combine_results_for_5methods.py')
        return
    
    print()
    print('='*80)
    print('GENERATING 5-METHOD COMPARISON FIGURES')
    print('='*80)
    print(f'Input:   {results_path}')
    print(f'Output:  {output_dir}/')
    print(f'Methods: {", ".join(METHODS)}')
    print()
    
    # Load and organize data
    print('Loading results...')
    results = load_results(results_path)
    data = organize_by_scenario(results, METHODS)
    plot_data, sorted_scenarios = prepare_plot_data(data, METHODS)
    
    print(f'Loaded {len(sorted_scenarios)} scenarios')
    print()
    
    # Generate figures
    print('Generating figures...')
    create_computation_time_figure(
        plot_data, METHODS,
        output_dir / 'computation_time_5methods.png'
    )
    create_path_length_figure(
        plot_data, METHODS,
        output_dir / 'path_length_5methods.png'
    )
    
    # Print statistics
    print_statistics(plot_data, METHODS)
    
    print('='*80)
    print('COMPLETE!')
    print('='*80)
    print()
    print(f'Figures saved to: {output_dir}/')
    print(f'  - computation_time_5methods.png')
    print(f'  - path_length_5methods.png')
    print()


if __name__ == '__main__':
    main()
