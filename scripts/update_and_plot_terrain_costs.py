#!/usr/bin/env python3
"""
Recompute avg terrain multiplier and total terrain cost per method/scenario,
update benchmark_results/terrain_methods_comparison.json and produce comparison plots.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
IN_PATH = ROOT / 'benchmark_results' / 'terrain_methods_comparison.json'
OUT_DIR = ROOT / 'benchmark_results'
FIG_DIR = ROOT / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

def compute_segment_terrain_cost(point_a, point_b, terrain_data, voxel_size=0.2):
    # approximate by sampling mid-point (same logic as run_terrain_experiments)
    mid = (np.array(point_a) + np.array(point_b)) / 2.0
    elev = terrain_data['elevation']
    gs = elev.shape
    cx = gs[0] / 2.0
    cy = gs[1] / 2.0
    ix = int(round(mid[0] / voxel_size + cx))
    iy = int(round(mid[1] / voxel_size + cy))
    ix = max(0, min(gs[0]-1, ix))
    iy = max(0, min(gs[1]-1, iy))
    try:
        zc = elev[ix, iy, 0]
        nx = elev[min(ix+1, gs[0]-1), iy, 0]
        ny = elev[ix, min(iy+1, gs[1]-1), 0]
        slope = max(abs(nx - zc), abs(ny - zc))
    except Exception:
        slope = 0.0
    rough = float(terrain_data['roughness'][ix, iy, 0])
    dens = float(terrain_data['density'][ix, iy, 0])
    slope_mult = 1.0 + min(2.0, slope / 5.0 * 2.0)
    rough_mult = 1.0 + (rough - 0.2) / (0.8) * 1.0 if rough >= 0.2 else 1.0
    dens_mult = 1.0 + (0.9 - dens) / 0.9 * 1.0 if dens <= 0.9 else 1.0
    seg_mult = max(1.0, min(10.0, slope_mult * rough_mult * dens_mult))
    return seg_mult

def compute_total_terrain_cost_and_avg_mult(path, terrain_data, voxel_size=0.2):
    if path is None or len(path) < 2:
        return 0.0, None
    total = 0.0
    total_len = 0.0
    for i in range(len(path)-1):
        a = path[i]
        b = path[i+1]
        seg_len = float(np.linalg.norm(np.array(b) - np.array(a)))
        seg_mult = compute_segment_terrain_cost(a, b, terrain_data, voxel_size=voxel_size)
        total += seg_len * seg_mult
        total_len += seg_len
    avg_mult = (total / total_len) if total_len > 0 else None
    return total, avg_mult


def compute_point_average(path, planner_compute):
    if path is None or len(path) == 0:
        return None, []
    costs = [planner_compute(tuple(p)) for p in path]
    return float(np.mean(costs)), costs

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def main():
    with open(IN_PATH, 'r') as f:
        data = json.load(f)

    for scen_name, scen in data.items():
        scen_obj = data[scen_name]
        # attempt to get terrain_data from benchmark files if present
        # The original file doesn't include terrain_data; load scenario generator to compute if needed
        try:
            from scripts.create_terrain_scenarios import create_hill_detour_scenario, create_roughness_avoidance_scenario, create_combined_terrain_scenario
            scen_map = {
                'hill_detour': create_hill_detour_scenario(),
                'roughness_avoidance': create_roughness_avoidance_scenario(),
                'combined_terrain': create_combined_terrain_scenario()
            }
            scenario_full = scen_map.get(scen_name)
            terrain_data = scenario_full['terrain_data'] if scenario_full is not None else None
            voxel_size = scenario_full['voxel_size'] if scenario_full is not None else 0.2
        except Exception:
            terrain_data = None
            voxel_size = 0.2

        base = scen_obj.get('regular_astar', {})
        methods = ['regular_astar', 'terrain_aware_astar', 'field_d_hybrid']
        # compute avg multipliers and total costs
        for m in methods:
            res = scen_obj.get(m, {})
            path = res.get('path')
            path_length = safe_float(res.get('path_length'))
            terrain_cost = res.get('terrain_cost')
            # compute methodB (segment-weighted) as before
            avg_mult_b = None
            total_cost_b = None
            if terrain_cost is not None and path_length and path_length > 0:
                try:
                    avg_mult_b = float(terrain_cost) / float(path_length)
                    total_cost_b = float(terrain_cost)
                except Exception:
                    avg_mult_b = None
            else:
                if path is not None and terrain_data is not None and len(path) >= 2:
                    total_cost_b, avg_mult_b = compute_total_terrain_cost_and_avg_mult(path, terrain_data, voxel_size=voxel_size)
            res['avg_terrain_mult'] = avg_mult_b
            res['total_terrain_cost'] = total_cost_b

            # compute methodA (point average) using planner._compute_terrain_cost
            try:
                # create a local planner to use its point cost method
                from importlib import import_module
                mod = import_module('terrain_aware_astar')
                ptemp = mod.TerrainAwareAStar(voxel_size=voxel_size, grid_size=scenario_full['grid_size']) if scenario_full is not None else None
                if ptemp is not None:
                    ptemp.set_terrain_data(scenario_full['voxel_grid'], terrain_data=scenario_full['terrain_data'], min_bound=[-(scenario_full['grid_size'][0]*voxel_size)/2.0, -(scenario_full['grid_size'][1]*voxel_size)/2.0, 0.0])
                    avg_mult_a, costs_list = compute_point_average(path, lambda pt: ptemp._compute_terrain_cost(pt))
                else:
                    avg_mult_a, costs_list = None, []
            except Exception:
                avg_mult_a, costs_list = None, []
            total_cost_a = (avg_mult_a * path_length) if (avg_mult_a is not None and path_length) else None
            res['avg_terrain_mult_point'] = avg_mult_a
            res['total_terrain_cost_point'] = total_cost_a

        # compute reductions vs regular A*
        reg_cost = scen_obj.get('regular_astar', {}).get('total_terrain_cost')
        try:
            reg_cost = float(reg_cost) if reg_cost is not None else None
        except Exception:
            reg_cost = None

        # comparisons: both methods
        point_comp = {}
        seg_comp = {}
        try:
            ra = scen_obj.get('regular_astar', {})
            ta = scen_obj.get('terrain_aware_astar', {})
            # method A
            ra_a = ra.get('total_terrain_cost_point')
            ta_a = ta.get('total_terrain_cost_point')
            if ra_a is not None and ta_a is not None and ra_a != 0:
                mult_red_pct = (ra.get('avg_terrain_mult_point') - ta.get('avg_terrain_mult_point')) / ra.get('avg_terrain_mult_point') * 100.0 if ra.get('avg_terrain_mult_point') else None
                cost_red_pct = (ra_a - ta_a) / ra_a * 100.0
            else:
                mult_red_pct = None
                cost_red_pct = None
            point_comp = {
                'regular_avg_mult': ra.get('avg_terrain_mult_point'),
                'ta_avg_mult': ta.get('avg_terrain_mult_point'),
                'mult_reduction_pct': mult_red_pct,
                'regular_total_cost': ra_a,
                'ta_total_cost': ta_a,
                'cost_reduction_pct': cost_red_pct
            }
            # method B
            ra_b = ra.get('total_terrain_cost')
            ta_b = ta.get('total_terrain_cost')
            if ra_b is not None and ta_b is not None and ra_b != 0:
                mult_red_pct_b = (ra.get('avg_terrain_mult') - ta.get('avg_terrain_mult')) / ra.get('avg_terrain_mult') * 100.0 if ra.get('avg_terrain_mult') else None
                cost_change_pct_b = (ra_b - ta_b) / ra_b * 100.0
            else:
                mult_red_pct_b = None
                cost_change_pct_b = None
            seg_comp = {
                'regular_avg_mult': ra.get('avg_terrain_mult'),
                'ta_avg_mult': ta.get('avg_terrain_mult'),
                'mult_reduction_pct': mult_red_pct_b,
                'regular_total_cost': ra_b,
                'ta_total_cost': ta_b,
                'cost_change_pct': cost_change_pct_b
            }
        except Exception:
            point_comp = {}
            seg_comp = {}

        scen_obj['comparison'] = scen_obj.get('comparison', {})
        scen_obj['comparison']['point_average_method'] = point_comp
        scen_obj['comparison']['segment_weighted_method'] = seg_comp

    # write updated JSON
    out_path = OUT_DIR / 'terrain_methods_comparison.json'
    with open(out_path, 'w') as f:
        json.dump(data, f, indent=2)

    # plotting per scenario
    for scen_name, scen in data.items():
        methods = ['regular_astar', 'terrain_aware_astar', 'field_d_hybrid']
        labels = ['Regular A*', 'Terrain-Aware A*', 'Field D*']
        lengths = [safe_float(scen[m].get('path_length')) or 0.0 for m in methods]
        avgs = [safe_float(scen[m].get('avg_terrain_mult')) or 0.0 for m in methods]
        totals = [safe_float(scen[m].get('total_terrain_cost')) or 0.0 for m in methods]

        fig, axes = plt.subplots(2,2, figsize=(14,10))
        ax = axes[0,0]
        bars = ax.bar(labels, lengths, color=['blue','orange','green'])
        ax.set_ylabel('Path Length (m)')
        ax.set_title('Path Length Comparison')
        ax.grid(axis='y', alpha=0.3)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2., h, f'{h:.1f}m', ha='center', va='bottom')

        ax = axes[0,1]
        bars = ax.bar(labels, avgs, color=['blue','orange','green'])
        ax.set_ylabel('Average Terrain Multiplier')
        ax.set_title('Average Terrain Cost Comparison')
        ax.grid(axis='y', alpha=0.3)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2., h, f'{h:.2f}x', ha='center', va='bottom')

        ax = axes[1,0]
        bars = ax.bar(labels, totals, color=['blue','orange','green'])
        ax.set_ylabel('Total Terrain Cost (m × mult)')
        ax.set_title('Total Terrain Cost Comparison')
        ax.grid(axis='y', alpha=0.3)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2., h, f'{h:.1f}', ha='center', va='bottom')

        ax = axes[1,1]
        base = totals[0] if totals[0] != 0 else None
        improvements = [0.0, 0.0, 0.0]
        colors = ['gray','gray','gray']
        if base is not None and base != 0:
            improvements[1] = (base - totals[1]) / base * 100.0 if totals[1] is not None else 0.0
            improvements[2] = (base - totals[2]) / base * 100.0 if totals[2] is not None else 0.0
            colors = ['gray', 'green' if improvements[1] > 0 else 'red', 'green' if improvements[2] > 0 else 'red']
        bars = ax.bar(labels, improvements, color=colors)
        ax.set_ylabel('Total Cost Reduction (%)')
        ax.set_title('Improvement vs Regular A*')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.grid(axis='y', alpha=0.3)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2., h, f'{h:+.1f}%', ha='center', va='bottom' if h>=0 else 'top')

        plt.tight_layout()
        fname = FIG_DIR / f'terrain_cost_comparison_{scen_name}.png'
        plt.savefig(fname, dpi=300)
        plt.close(fig)
        print('Wrote', fname)

if __name__ == '__main__':
    main()
