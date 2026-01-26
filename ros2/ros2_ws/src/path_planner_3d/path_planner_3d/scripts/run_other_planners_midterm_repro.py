#!/usr/bin/env python3
"""Run other planners (RRT*, D* Lite, HPA*, SAFETY_FIRST) on midterm scenario_ids.json.

Produces results under benchmark_results/:
 - other_planners_midterm_repro_results.json
 - other_planners_midterm_repro_summary.json
 - midterm_vs_master_other_planners.csv
"""
import os, json, time, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, 'benchmark_results')
os.makedirs(OUT_DIR, exist_ok=True)

from dataclasses import dataclass


@dataclass
class TestScenario:
    name: str
    start: np.ndarray
    goal: np.ndarray
    bounds: tuple
    terrain_cost_map: np.ndarray
    complexity: str
    description: str
    map_size: str


def load_scenarios_from_file(path):
    with open(path) as f:
        data = json.load(f)
    scen_objs = []
    for s in data:
        start = np.array(s.get('start'))
        goal = np.array(s.get('goal'))
        bounds = s.get('bounds', ((0.0,10.0),(0.0,10.0),(0.0,2.0)))
        map_size = s.get('map_size','SMALL')
        complexity = s.get('complexity','SIMPLE')
        # provide a dummy terrain_cost_map sized according to map_size
        grid_size = 100 if map_size=='SMALL' else (500 if map_size=='MEDIUM' else 1000)
        cost_map = np.ones((grid_size, grid_size), dtype=np.float32) * 0.1
        scen = TestScenario(
            name=s.get('name'),
            start=start,
            goal=goal,
            bounds=bounds,
            terrain_cost_map=cost_map,
            complexity=complexity,
            description='',
            map_size=map_size
        )
        scen_objs.append(scen)
    return scen_objs


def summarize_results(results):
    # results: list of BenchmarkResult dataclasses or dict-like
    from collections import defaultdict
    import numpy as _np
    by_planner = defaultdict(lambda: defaultdict(list))
    by_planner_counts = defaultdict(lambda: defaultdict(int))
    for r in results:
        name = getattr(r, 'planner_name', r.get('planner_name'))
        map_size = None
        try:
            map_size = r.scenario_name.split('_')[1].capitalize()
        except Exception:
            map_size = getattr(r, 'map_size', r.get('map_size','Unknown')).capitalize()
        success = getattr(r, 'success', r.get('success', False))
        t = getattr(r, 'computation_time', r.get('computation_time', None))
        by_planner_counts[name][map_size] += 1
        if success and t is not None:
            by_planner[name][map_size].append(float(t))
    summary = {}
    for p, by in by_planner.items():
        summary[p] = {}
        for size, vals in by.items():
            summary[p][size] = {'count': len(vals), 'mean': float(_np.mean(vals)) if vals else None}
    # also include success/fail counts per planner/size
    counts = {}
    for p, byc in by_planner_counts.items():
        counts[p] = dict(byc)
    return summary, counts


def main():
    scen_file = os.path.join(OUT_DIR, 'scenario_ids.json')
    if not os.path.exists(scen_file):
        print('scenario_ids.json not found in', OUT_DIR)
        return
    print('Loading scenarios from', scen_file)
    scenarios = load_scenarios_from_file(scen_file)

    planners = ['RRT_STAR', 'DSTAR_LITE', 'HPA_STAR', 'SAFETY_FIRST']
    print('Running planners:', planners)
    import multiprocessing as mp
    results = []

    # import planner classes directly to avoid package import issues
    from path_planner_3d.terrain_guided_rrt_star import TerrainGuidedRRTStar
    from path_planner_3d.dstar_lite_planner import DStarLitePlanner
    from path_planner_3d.hpa_star_planner import HPAStarPlanner
    from path_planner_3d.safety_first_planner import SafetyFirstPlanner

    def worker(planner_key, scen, conn):
        try:
            start = np.array(scen.start)
            goal = np.array(scen.goal)
            bounds = scen.bounds
            map_size = scen.map_size
            grid_size = 100 if map_size=='SMALL' else (500 if map_size=='MEDIUM' else 1000)
            timeout = 30 if map_size=='SMALL' else (60 if map_size=='MEDIUM' else 120)
            terrain = scen.terrain_cost_map if hasattr(scen, 'terrain_cost_map') else np.ones((grid_size, grid_size), dtype=np.float32)*0.1
            if planner_key == 'RRT_STAR':
                # match settings used elsewhere: small=5000, medium=3000, large=2000
                mi = 5000 if map_size=='SMALL' else (3000 if map_size=='MEDIUM' else 2000)
                pl = TerrainGuidedRRTStar(start=start, goal=goal, bounds=bounds, terrain_cost_map=terrain, max_iterations=mi)
                t0 = time.time(); path = pl.plan(timeout=timeout); elapsed = time.time()-t0
            elif planner_key == 'DSTAR_LITE':
                pl = DStarLitePlanner(start=start, goal=goal, bounds=bounds, terrain_cost_map=terrain)
                t0 = time.time(); path = pl.plan(); elapsed = time.time()-t0
            elif planner_key == 'HPA_STAR':
                pl = HPAStarPlanner(start=start, goal=goal, bounds=bounds, terrain_cost_map=terrain, cluster_size=25 if map_size=='SMALL' else (100 if map_size=='MEDIUM' else 200))
                t0 = time.time(); path = pl.plan(); elapsed = time.time()-t0
            elif planner_key == 'SAFETY_FIRST':
                pl = SafetyFirstPlanner(start=start, goal=goal, bounds=bounds, terrain_cost_map=terrain)
                t0 = time.time(); path = pl.plan(); elapsed = time.time()-t0
            else:
                conn.send({'error':'unknown_planner'})
                return
            success = path is not None and len(path)>1
            path_len = float(np.sum([np.linalg.norm(path[i+1]-path[i]) for i in range(len(path)-1)])) if success else 0.0
            conn.send({'planner':planner_key, 'scenario_name':scen.name, 'map_size':scen.map_size, 'success':success, 'computation_time':elapsed, 'path_length':path_len})
        except Exception as e:
            conn.send({'planner':planner_key, 'scenario_name':scen.name, 'error':str(e)})

    total = len(scenarios) * len(planners)
    cur = 0
    for scen in scenarios:
        for p in planners:
            cur += 1
            parent_conn, child_conn = mp.Pipe()
            proc = mp.Process(target=worker, args=(p, scen, child_conn))
            proc.start()
            # timeout per size
            to = 30 if scen.map_size == 'SMALL' else (60 if scen.map_size == 'MEDIUM' else 120)
            proc.join(timeout=to)
            if proc.is_alive():
                proc.terminate(); proc.join()
                print(f"[{cur}/{total}] {p} {scen.name}: Timeout")
                results.append({'planner_name':p, 'scenario_name':scen.name, 'map_size':scen.map_size, 'success':False, 'computation_time':None, 'error':'timeout'})
            else:
                try:
                    payload = parent_conn.recv()
                    if 'error' in payload:
                        results.append({'planner_name':payload.get('planner',p), 'scenario_name':scen.name, 'map_size':scen.map_size, 'success':False, 'computation_time':None, 'error':payload.get('error')})
                    else:
                        results.append({'planner_name':payload.get('planner'), 'scenario_name':payload.get('scenario_name'), 'map_size':payload.get('map_size'), 'success':payload.get('success'), 'computation_time':payload.get('computation_time'), 'path_length':payload.get('path_length')})
                    print(f"[{cur}/{total}] {p} {scen.name}: Done (success={payload.get('success')}, time={payload.get('computation_time')})")
                except EOFError:
                    results.append({'planner_name':p, 'scenario_name':scen.name, 'map_size':scen.map_size, 'success':False, 'computation_time':None, 'error':'no_result'})
                    print(f"[{cur}/{total}] {p} {scen.name}: No result (EOF)")
            # flush results to disk after each run
            try:
                with open(out_path, 'w') as fh:
                    json.dump(results, fh, indent=2)
            except Exception:
                pass

    out_path = os.path.join(OUT_DIR, 'other_planners_midterm_repro_results.json')
    with open(out_path, 'w') as fh:
        json.dump(results, fh, indent=2)
    print('Wrote', out_path)

    # summarize per planner
    summary = {}
    counts = {}
    from collections import defaultdict
    vals = defaultdict(lambda: defaultdict(list))
    cnts = defaultdict(lambda: defaultdict(int))
    for r in results:
        p = r.get('planner_name')
        sz = r.get('map_size')
        cnts[p][sz] += 1
        if r.get('success') and r.get('computation_time') is not None:
            vals[p][sz].append(r.get('computation_time'))
    for p in ['RRT_STAR','DSTAR_LITE','HPA_STAR','SAFETY_FIRST']:
        summary[p] = {}
        counts[p] = {}
        for sz in ['SMALL','MEDIUM','LARGE']:
            arr = vals[p].get(sz, [])
            summary[p][sz] = {'count': len(arr), 'mean': float(np.mean(arr)) if arr else None}
            counts[p][sz] = cnts[p].get(sz, 0)
    with open(os.path.join(OUT_DIR, 'other_planners_midterm_repro_summary.json'), 'w') as fh:
        json.dump({'summary':summary,'counts':counts}, fh, indent=2)
    print('Wrote summary JSON')

    # compare to master bench stats
    master_file = os.path.join(OUT_DIR, 'full_benchmark_results.json')
    master_stats = {}
    if os.path.exists(master_file):
        with open(master_file) as f:
            full = _json.load(f)
        # compute master means per planner per size
        from collections import defaultdict
        ms = defaultdict(lambda: defaultdict(list))
        for r in full:
            pname = r.get('planner_name')
            sname = r.get('scenario_name') or r.get('scenario_id')
            size = 'Unknown'
            if sname:
                s = sname.upper()
                if 'SMALL' in s: size='Small'
                elif 'MEDIUM' in s: size='Medium'
                elif 'LARGE' in s: size='Large'
            t = r.get('computation_time')
            if pname and t is not None:
                ms[pname][size].append(float(t))
        for p, by in ms.items():
            master_stats[p] = {sz: float(np.mean(vals)) if vals else None for sz, vals in by.items()}

    # write comparison CSV
    csv_path = os.path.join(OUT_DIR, 'midterm_vs_master_other_planners.csv')
    import csv
    with open(csv_path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['プランナー','再現Small','マスターSmall','倍率','再現Med','マスターMed','倍率','再現Lrg','マスターLrg','倍率','repro_count_small','repro_count_med','repro_count_lrg'])
        targets = ['ADAPTIVE','RRT_STAR','DSTAR_LITE','HPA_STAR','SAFETY_FIRST']
        for p in targets:
            def g(d,p,size):
                return d.get(p,{}).get(size)
            r_s = summary.get(p,{}).get('Small',{}).get('mean') if summary.get(p) else None
            r_m = summary.get(p,{}).get('Medium',{}).get('mean') if summary.get(p) else None
            r_l = summary.get(p,{}).get('Large',{}).get('mean') if summary.get(p) else None
            m_s = master_stats.get(p,{}).get('Small') if master_stats.get(p) else None
            m_m = master_stats.get(p,{}).get('Medium') if master_stats.get(p) else None
            m_l = master_stats.get(p,{}).get('Large') if master_stats.get(p) else None
            def ratio(a,b):
                try:
                    return f"{b/a:.2f}x" if a and b else ''
                except Exception:
                    return ''
            cs = counts.get(p,{})
            w.writerow([p, f"{r_s:.3f}" if r_s else '', m_s if m_s else '', ratio(m_s, r_s), f"{r_m:.3f}" if r_m else '', m_m if m_m else '', ratio(m_m, r_m), f"{r_l:.3f}" if r_l else '', m_l if m_l else '', ratio(m_l, r_l), cs.get('Small',0), cs.get('Medium',0), cs.get('Large',0)])
    print('Wrote CSV', csv_path)


if __name__ == '__main__':
    main()
