#!/usr/bin/env python3
import csv
import os

BASE = os.path.join("ros2","ros2_ws","src","path_planner_3d","path_planner_3d","benchmark_results")
TA_FILE = os.path.join(BASE, "ta_star_by_complexity.csv")
FULL_FILE = os.path.join(BASE, "complexity_performance_full.csv")
DIJK_FILE = os.path.join(BASE, "dijkstra_detailed_stats.csv")
OUT_DIR = "results"
OUT_FILE = os.path.join(OUT_DIR, "complexity_comparison.csv")

PLANNER_LABELS = {
    'RRT_STAR': 'RRT*',
    'HPA_STAR': 'HPA*',
    'DSTAR_LITE': 'D* Lite',
    'SAFETY_FIRST': 'SAFETY_FIRST',
}

COMPLEXITIES = ['SIMPLE','MODERATE','COMPLEX']

def read_full():
    data = {}
    if not os.path.exists(FULL_FILE):
        return data
    with open(FULL_FILE, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            planner = r['planner'].strip()
            comp = r['complexity'].strip()
            try:
                avg = float(r.get('avg_time',''))
            except:
                avg = None
            try:
                succ = float(r.get('success_rate',''))
            except:
                succ = None
            try:
                cnt = int(r.get('scenario_count','0'))
            except:
                cnt = 0
            data.setdefault(planner, {})[comp] = {'avg': avg, 'succ': succ, 'count': cnt}
    return data

def read_ta():
    data = {}
    if not os.path.exists(TA_FILE):
        return data
    with open(TA_FILE, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            comp = r['complexity'].strip()
            try:
                avg = float(r.get('avg_time',''))
            except:
                avg = None
            try:
                succ = float(r.get('success_rate',''))
            except:
                succ = None
            try:
                cnt = int(r.get('scenario_count','0'))
            except:
                cnt = 0
            data[comp] = {'avg': avg, 'succ': succ, 'count': cnt}
    return data

def read_dijkstra():
    # file is key,value per line
    if not os.path.exists(DIJK_FILE):
        return {}
    metrics = {}
    with open(DIJK_FILE, newline='') as f:
        reader = csv.reader(f)
        for r in reader:
            if not r: continue
            if len(r) < 2: continue
            key = r[0].strip()
            val = r[1].strip()
            metrics[key] = val

    mapping = {'Small':'SIMPLE','Medium':'MODERATE','Large':'COMPLEX'}
    out = {}
    for size, comp in mapping.items():
        total_k = f"{size}_total"
        succ_rate_k = f"{size}_success_rate"
        avg_time_k = f"{size}_avg_time_success"
        try:
            cnt = int(float(metrics.get(total_k, '0')))
        except:
            cnt = 0
        try:
            succ = float(metrics.get(succ_rate_k, 'nan'))
        except:
            succ = None
        try:
            avg = float(metrics.get(avg_time_k, 'nan'))
        except:
            avg = None
        out[comp] = {'avg': avg, 'succ': succ, 'count': cnt}
    return out

def weighted_average(items):
    # items: list of (value, count)
    num = 0.0
    den = 0
    for v,c in items:
        if v is None: continue
        num += v * (c if c is not None else 1)
        den += (c if c is not None else 1)
    return (num/den) if den>0 else None

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    full = read_full()
    ta = read_ta()
    dijk = read_dijkstra()

    planners = ['TA*', 'D* Lite', 'SAFETY_FIRST', 'HPA*', 'RRT*', 'Dijkstra']

    rows = []
    for p in planners:
        row = {'planner': p}
        comp_values = {}
        comp_succ = {}
        comp_counts = {}

        if p == 'TA*':
            source = ta
            for comp in COMPLEXITIES:
                d = source.get(comp, {})
                comp_values[comp] = d.get('avg')
                comp_succ[comp] = d.get('succ')
                comp_counts[comp] = d.get('count',0)
        elif p == 'Dijkstra':
            source = dijk
            for comp in COMPLEXITIES:
                d = source.get(comp, {})
                comp_values[comp] = d.get('avg')
                comp_succ[comp] = d.get('succ')
                comp_counts[comp] = d.get('count',0)
        else:
            # find matching planner in full (keys like RRT_STAR, HPA_STAR, DSTAR_LITE, SAFETY_FIRST)
            match_key = None
            for k in full.keys():
                if k == '': continue
                if PLANNER_LABELS.get(k) == p or (k.replace('*','_STAR')==p.replace('*','_STAR')):
                    match_key = k
                    break
            # fallback by heuristic
            if match_key is None:
                # try direct mapping
                for k in full.keys():
                    if p.replace('*','_STAR') in k or p.replace(' ','_').upper() in k:
                        match_key = k
                        break
            if match_key:
                source = full.get(match_key, {})
                for comp in COMPLEXITIES:
                    d = source.get(comp, {})
                    comp_values[comp] = d.get('avg')
                    comp_succ[comp] = d.get('succ')
                    comp_counts[comp] = d.get('count',0)
            else:
                for comp in COMPLEXITIES:
                    comp_values[comp] = None
                    comp_succ[comp] = None
                    comp_counts[comp] = 0

        # compute overall weighted averages
        avg_items = [(comp_values[c], comp_counts.get(c,0)) for c in COMPLEXITIES]
        succ_items = [(comp_succ[c], comp_counts.get(c,0)) for c in COMPLEXITIES]
        overall_avg = weighted_average(avg_items)
        overall_succ = weighted_average(succ_items)

        for c in COMPLEXITIES:
            row[c] = '' if comp_values[c] is None else f"{comp_values[c]:.6f}"
        row['overall_avg'] = '' if overall_avg is None else f"{overall_avg:.6f}"
        row['success_rate'] = '' if overall_succ is None else f"{overall_succ:.3f}"
        rows.append(row)

    # write CSV
    fieldnames = ['planner'] + COMPLEXITIES + ['overall_avg','success_rate']
    with open(OUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {OUT_FILE}")

if __name__ == '__main__':
    main()
