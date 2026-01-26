#!/usr/bin/env python3
"""Run experiments on the generated terrain scenarios using FieldDStarHybrid
Saves results to `benchmark_results/terrain_cost_effectiveness.json` and per-scenario PNGs are created by visualization script.
"""
import os
import sys
import json
import time
import signal
import threading
from dataclasses import dataclass
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / 'terrain_test_scenarios'
OUT_DIR = ROOT / 'benchmark_results'
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR = ROOT / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Add path to path_planner_3d module
PP3D = ROOT / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d'
if str(PP3D) not in sys.path:
    sys.path.insert(0, str(PP3D))

# Import planner with robustness
try:
    from field_d_star_hybrid import FieldDStarHybrid
except Exception as e:
    print('Failed to import FieldDStarHybrid from path_planner_3d:', e)
    FieldDStarHybrid = None

try:
    from terrain_aware_astar import TerrainAwareAStar
except Exception as e:
    print('Failed to import TerrainAwareAStar:', e)
    TerrainAwareAStar = None

try:
    from planning_result import PlanningResult
except Exception:
    # fallback: define minimal PlanningResult-like class
    @dataclass
    class PlanningResult:
        success: bool = False
        path: list = None
        computation_time: float = 0.0
        path_length: float = 0.0
        nodes_explored: int = 0


def load_scenario(name):
    meta_path = SCEN_DIR / f"{name}_meta.json"
    data_path = SCEN_DIR / f"{name}_data.npz"
    if not meta_path.exists() or not data_path.exists():
        raise FileNotFoundError(name)
    meta = json.load(open(meta_path))
    npz = np.load(data_path)
    voxel_grid = npz['voxel_grid']
    elevation = npz['elevation']
    roughness = npz['roughness']
    density = npz['density']
    return {
        'name': name,
        'grid_size': tuple(meta['grid_size']),
        'voxel_size': meta['voxel_size'],
        'voxel_grid': voxel_grid,
        'terrain_data': {
            'elevation': elevation,
            'roughness': roughness,
            'density': density
        },
        'start': tuple(meta['start']),
        'goal': tuple(meta['goal'])
    }


def compute_path_length(path):
    if path is None or len(path) < 2:
        return None
    p = np.array(path)
    diffs = p[1:] - p[:-1]
    d = np.linalg.norm(diffs, axis=1)
    return float(np.sum(d))


def compute_segment_terrain_cost(point_a, point_b, terrain_data, grid_origin=(0,0), voxel_size=0.2):
    # approximate by sampling mid-point
    mid = (np.array(point_a) + np.array(point_b)) / 2.0
    # convert world coordinates to grid indices (assume center at grid middle)
    elev = terrain_data['elevation']
    gs = elev.shape
    cx = gs[0] / 2.0
    cy = gs[1] / 2.0
    ix = int(round(mid[0] / voxel_size + cx))
    iy = int(round(mid[1] / voxel_size + cy))
    ix = max(0, min(gs[0]-1, ix))
    iy = max(0, min(gs[1]-1, iy))
    # compute slope approx using elevation layer 0 and neighbors
    try:
        zc = elev[ix, iy, 0]
        # simple slope proxy: difference to neighbors
        nx = elev[min(ix+1, gs[0]-1), iy, 0]
        ny = elev[ix, min(iy+1, gs[1]-1), 0]
        slope = max(abs(nx - zc), abs(ny - zc))
    except Exception:
        slope = 0.0
    rough = float(terrain_data['roughness'][ix, iy, 0])
    dens = float(terrain_data['density'][ix, iy, 0])
    # map slope -> multiplier [1.0 .. 3.0], rough [1.0 .. 2.0], dens [1.0 .. 2.0]
    slope_mult = 1.0 + min(2.0, slope / 5.0 * 2.0)
    rough_mult = 1.0 + (rough - 0.2) / (0.8) * 1.0 if rough >= 0.2 else 1.0
    dens_mult = 1.0 + (0.9 - dens) / 0.9 * 1.0 if dens <= 0.9 else 1.0
    seg_mult = max(1.0, min(10.0, slope_mult * rough_mult * dens_mult))
    return seg_mult


def compute_total_terrain_cost(path, terrain_data, voxel_size=0.2):
    if path is None or len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path)-1):
        seg_len = float(np.linalg.norm(np.array(path[i+1]) - np.array(path[i])))
        seg_mult = compute_segment_terrain_cost(path[i], path[i+1], terrain_data, voxel_size=voxel_size)
        total += seg_len * seg_mult
    return float(total)


def plan_with_planner(planner_cls, use_terrain, scenario, timeout: float = None):
    if planner_cls is None:
        return {'error': 'planner_not_available'}
    try:
        # instantiate
        planner = planner_cls(voxel_size=scenario['voxel_size'], grid_size=scenario['grid_size'], use_terrain_cost=use_terrain)
    except Exception as e:
        try:
            planner = planner_cls(voxel_size=scenario['voxel_size'], grid_size=scenario['grid_size'])
            if hasattr(planner, 'use_terrain_cost'):
                planner.use_terrain_cost = use_terrain
        except Exception as e2:
            return {'error': f'instantiation_failed: {e} / {e2}'}

    # compute min_bound so grid center is world origin
    gx, gy = scenario['grid_size'][0], scenario['grid_size'][1]
    half_x = (gx * scenario['voxel_size']) / 2.0
    half_y = (gy * scenario['voxel_size']) / 2.0
    min_bound = (-half_x, -half_y, 0.0)
    # set voxel grid and terrain if available
    try:
        if hasattr(planner, 'set_terrain_data'):
            if use_terrain:
                planner.set_terrain_data(scenario['voxel_grid'], terrain_data=scenario['terrain_data'], min_bound=min_bound)
            else:
                planner.set_terrain_data(scenario['voxel_grid'], min_bound=min_bound)
        else:
            # attempt to set attributes directly
            planner.voxel_grid = scenario['voxel_grid']
            planner.terrain_data = scenario.get('terrain_data')
            planner.min_bound = np.array(min_bound)
    except Exception as e:
        print('Warning: set_terrain_data failed:', e)

    # plan
    start = scenario['start']
    goal = scenario['goal']
    # Debug prints
    print(f"Planning (use_terrain={use_terrain})...")
    print(f"  Start: {start}")
    print(f"  Goal: {goal}")
    print(f"  Grid size: {scenario['grid_size']}")

    # progress monitor thread
    done_event = threading.Event()
    def _monitor(t_s):
        while not done_event.is_set():
            elapsed = time.time() - t_s
            if elapsed >= 1.0:
                print(f"  ... {elapsed:.1f}s elapsed")
            time.sleep(1.0)

    # signal-based timeout
    class _TimeoutSignal(Exception):
        pass

    def _timeout_handler(signum, frame):
        raise _TimeoutSignal()

    path = None
    t0 = time.time()
    mon_thr = threading.Thread(target=_monitor, args=(t0,), daemon=True)
    mon_thr.start()

    if timeout is not None:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(int(math.ceil(timeout)))

    try:
        if hasattr(planner, 'plan_path'):
            try:
                if timeout is not None:
                    path = planner.plan_path(start, goal, timeout=timeout)
                else:
                    path = planner.plan_path(start, goal)
            except TypeError:
                path = planner.plan_path(start, goal)
        elif hasattr(planner, 'plan'):
            path = planner.plan(start, goal)
        else:
            path = planner.run(start, goal)
    except _TimeoutSignal:
        print(f"  TIMEOUT after {timeout}s")
        # provide fallback PlanningResult-like object
        try:
            path = PlanningResult(success=False, path=[], computation_time=float(timeout), path_length=0.0, nodes_explored=0)
        except Exception:
            # fallback simple dict
            path = type('PR', (), {'success': False, 'path': [], 'computation_time': float(timeout), 'path_length': 0.0, 'nodes_explored': 0})()
    except Exception as e:
        print(f"ERROR in planning (use_terrain={use_terrain}): {e}")
        try:
            path = PlanningResult(success=False, path=[], computation_time=0.0, path_length=0.0, nodes_explored=0, error_message=str(e))
        except Exception:
            path = type('PR', (), {'success': False, 'path': [], 'computation_time': 0.0, 'path_length': 0.0, 'nodes_explored': 0, 'error_message': str(e)})()
    finally:
        done_event.set()
        if timeout is not None:
            signal.alarm(0)

    t1 = time.time()
    elapsed = t1 - t0
    # planner may return a PlanningResult object or a raw path list
    path_list = None
    path_len = None
    nodes = None
    comp_time = elapsed
    try:
        if hasattr(path, 'path'):
            # PlanningResult-like
            path_list = getattr(path, 'path', None)
            path_len = getattr(path, 'path_length', None)
            nodes = getattr(path, 'nodes_explored', None)
            comp_time = getattr(path, 'computation_time', comp_time)
        else:
            path_list = path
            path_len = compute_path_length(path_list)
    except Exception:
        path_list = path
        path_len = compute_path_length(path_list)

    # determine success: prefer explicit PlanningResult.success, otherwise require non-empty path and positive length
    if hasattr(path, 'success'):
        success_flag = getattr(path, 'success')
    else:
        success_flag = (path_list is not None and isinstance(path_list, (list, tuple)) and len(path_list) >= 2 and path_len is not None and path_len > 0.0)

    terrain_cost = None
    if success_flag and path_list is not None:
        terrain_cost = compute_total_terrain_cost(path_list, scenario['terrain_data'], voxel_size=scenario['voxel_size'])

    return {
        'path': path_list,
        'success': bool(success_flag),
        'computation_time': float(comp_time),
        'path_length': float(path_len) if path_len is not None else None,
        'terrain_cost': float(terrain_cost) if terrain_cost is not None else None,
        'nodes_explored': nodes
    }


def _normalize_result(res, scenario):
    """Normalize PlanningResult or dict to a standard dict."""
    out = {
        'success': False,
        'computation_time': None,
        'path_length': None,
        'terrain_cost': None,
        'nodes_explored': None,
        'path': None
    }
    if res is None:
        return out
    # object with attributes
    if hasattr(res, 'success'):
        out['success'] = bool(getattr(res, 'success', False))
        out['computation_time'] = float(getattr(res, 'computation_time', 0.0))
        out['path_length'] = float(getattr(res, 'path_length', 0.0)) if getattr(res, 'path_length', None) is not None else None
        out['nodes_explored'] = getattr(res, 'nodes_explored', None)
        out['path'] = getattr(res, 'path', None)
    elif isinstance(res, dict):
        out['success'] = bool(res.get('success', False))
        out['computation_time'] = float(res.get('computation_time')) if res.get('computation_time') is not None else None
        out['path_length'] = float(res.get('path_length')) if res.get('path_length') is not None else None
        out['nodes_explored'] = res.get('nodes_explored')
        out['path'] = res.get('path')

    # compute terrain cost of returned path (using scenario terrain data)
    try:
        if out['path'] is not None:
            out['terrain_cost'] = compute_total_terrain_cost(out['path'], scenario.get('terrain_data'), voxel_size=scenario['voxel_size'])
        else:
            out['terrain_cost'] = None
    except Exception:
        out['terrain_cost'] = None

    return out


if __name__ == '__main__':
    scenario_names = ['hill_detour', 'roughness_avoidance', 'combined_terrain']
    comparison_results = {}
    # timeout for each planning call
    CALL_TIMEOUT = 60.0

    for scenario_name in scenario_names:
        print('\n' + '=' * 60)
        print(f"Scenario: {scenario_name}")
        print('=' * 60)
        scen = load_scenario(scenario_name)
        start = scen['start']
        goal = scen['goal']

        # 1) Regular A* (TerrainAwareAStar with no terrain data)
        print('\n[1/3] Regular A* (no terrain cost)...')
        if TerrainAwareAStar is None:
            print('  ERROR: TerrainAwareAStar not available')
            res_reg = None
        else:
            try:
                pa = TerrainAwareAStar(voxel_size=scen['voxel_size'], grid_size=scen['grid_size'])
                half_x = (scen['grid_size'][0] * scen['voxel_size']) / 2.0
                half_y = (scen['grid_size'][1] * scen['voxel_size']) / 2.0
                pa.set_terrain_data(scen['voxel_grid'], terrain_data=None, min_bound=[-half_x, -half_y, 0.0])
                r = pa.plan_path(start, goal, timeout=CALL_TIMEOUT)
                res_reg = r
            except Exception as e:
                print('  ERROR (regular A*):', e)
                res_reg = None

        # 2) Terrain-Aware A*
        print('\n[2/3] Terrain-Aware A* (with terrain cost)...')
        if TerrainAwareAStar is None:
            print('  ERROR: TerrainAwareAStar not available')
            res_ta = None
        else:
            try:
                ta = TerrainAwareAStar(voxel_size=scen['voxel_size'], grid_size=scen['grid_size'])
                half_x = (scen['grid_size'][0] * scen['voxel_size']) / 2.0
                half_y = (scen['grid_size'][1] * scen['voxel_size']) / 2.0
                ta.set_terrain_data(scen['voxel_grid'], terrain_data=scen['terrain_data'], min_bound=[-half_x, -half_y, 0.0])
                r2 = ta.plan_path(start, goal, timeout=CALL_TIMEOUT)
                res_ta = r2
            except Exception as e:
                print('  ERROR (terrain-aware A*):', e)
                res_ta = None

        # 3) Field D* Hybrid (with terrain cost)
        print('\n[3/3] Field D* Hybrid (with terrain cost)...')
        try:
            res_fd = plan_with_planner(FieldDStarHybrid, True, scen, timeout=CALL_TIMEOUT)
        except Exception as e:
            print('  ERROR (FieldD*Hybrid):', e)
            res_fd = None

        # normalize results
        n_reg = _normalize_result(res_reg, scen)
        n_ta = _normalize_result(res_ta, scen)
        n_fd = _normalize_result(res_fd, scen)

        # comparisons
        def comp(a, b):
            out = {'length_diff_m': None, 'length_diff_pct': None, 'terrain_cost_reduction_pct': None}
            try:
                la = a.get('path_length')
                lb = b.get('path_length')
                ta_cost = a.get('terrain_cost')
                tb_cost = b.get('terrain_cost')
                if la is not None and lb is not None:
                    out['length_diff_m'] = lb - la
                    out['length_diff_pct'] = ((lb - la) / la * 100.0) if la != 0 else None
                if ta_cost is not None and tb_cost is not None and ta_cost != 0:
                    out['terrain_cost_reduction_pct'] = (ta_cost - tb_cost) / ta_cost * 100.0
            except Exception:
                pass
            return out

        comparison = {
            'astar_vs_ta_astar': comp(n_reg, n_ta),
            'astar_vs_field_d': comp(n_reg, n_fd)
        }

        comparison_results[scenario_name] = {
            'regular_astar': n_reg,
            'terrain_aware_astar': n_ta,
            'field_d_hybrid': n_fd,
            'comparison': comparison
        }

        # print summary
        def _fmt(r):
            return f"{r.get('success')}, {r.get('computation_time') or 0.0:.2f}s, {r.get('path_length') or 0.0:.2f}m"

        print('\n✓ Completed', scenario_name)
        print('  Regular A*:', _fmt(n_reg))
        print('  Terrain-Aware A*:', _fmt(n_ta))
        print('  Field D* Hybrid:', _fmt(n_fd))

        # save intermediate full comparison
        with open(OUT_DIR / 'terrain_methods_comparison.json', 'w') as fh:
            json.dump(comparison_results, fh, indent=2)
        print('Saved intermediate comparison for', scenario_name)

    print('\nAll done. Results saved to', OUT_DIR / 'terrain_methods_comparison.json')
