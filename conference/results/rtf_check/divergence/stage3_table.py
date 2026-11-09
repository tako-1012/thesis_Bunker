"""Stage 3 table from saved records only: one row per run, plus min/median/max per condition.
Shape gap is to the official cloud run over the common elapsed window, as in experiments.run_divergence.
False lethal = cells blocked in the final map (seen & lethal) but not lethal in truth. Run from conference/."""
import csv, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, str(Path(__file__).parent))
from diagnose_no_path import diagnose
PATCH = '08OB87_-0706'
here = Path(__file__).parent
ref_raw = Path('results/lidar_fine/physical_10/raw')/PATCH
def track(raw):
    m = json.loads((raw/'mission.json').read_text())
    r = list(csv.DictReader((raw/'trajectory.csv').open()))
    t = np.array([[float(x[k]) for k in ('t', 'x', 'y', 'roll', 'pitch')] for x in r])
    return m, t[t[:, 0] >= m['started_t']]
_, ref = track(ref_raw)
ref[:, 0] -= ref[0, 0]
rows = []
for run in sorted(here.glob('R[0-9]_[0-9][0-9]')):
    raw = run/'physical_1/raw'/PATCH
    row = dict(run=run.name, condition=run.name[:2])
    try:
        status = json.loads((run/'status.json').read_text())
        row.update(sim_ok=status['simulation']['ok'], meas_ok=status['measurement']['ok'], report=status['existing_report']['result'])
    except (OSError, ValueError, KeyError):
        pass
    try:
        m, t = track(raw)
        t[:, 0] -= t[0, 0]
        rp = list(csv.DictReader(next(raw.glob('follower/*/replans.csv')).open()))
        end = min(t[-1, 0], ref[-1, 0])
        a, b = t[t[:, 0] <= end][:, 1:3], ref[ref[:, 0] <= end][:, 1:3]
        d = np.r_[cKDTree(b).query(a)[0], cKDTree(a).query(b)[0]]
        mp, e = np.load(raw/'pointcloud_map.npz'), np.load(raw/'evaluation_reference.npz')
        s = (m.get('final_state') or {})
        row.update(status=m['status'], sim_s=round(m['finished_t']-m['started_t'], 2), wall_s=round(m['wall_elapsed_s'], 1),
                   measured_rtf=round((m['finished_t']-m['started_t'])/m['wall_elapsed_s'], 4), goals_reached=(6 if m['status'] == 'completed' else int(rp[-1]['leg_index'])),
                   n_replans=s.get('n_replans'), shape_gap_cloud_max_m=round(float(d.max()), 2), shape_gap_cloud_p95_m=round(float(np.percentile(d, 95)), 2),
                   false_lethal=int((mp['seen'] & mp['lethal'] & ~e['truth_lethal']).sum()),
                   roll_max_deg=round(float(np.degrees(np.abs(t[:, 3]).max())), 1), pitch_max_deg=round(float(np.degrees(np.abs(t[:, 4]).max())), 1))
        if m['status'] != 'completed':
            dx, _ = diagnose(raw)
            row.update({'fail_'+k: dx[k] for k in ('class', 't', 'robot_xy', 'leg', 'goal_lethal', 'robot_cell_lethal', 'replay_start_released_success', 'blocked_of_9_around_robot')})
    except Exception as exc:
        row['read_error'] = type(exc).__name__+': '+str(exc)
    rows.append(row)
keys = list(dict.fromkeys(k for r in rows for k in r))
with (here/'stage3_runs.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
with (here/'stage3_summary.csv').open('w', newline='') as f:
    w = csv.writer(f); w.writerow(['condition', 'n', 'completed', 'no_path', 'rollover', 'other', 'metric', 'min', 'median', 'max'])
    for c in ('R1', 'R2'):
        g = [r for r in rows if r['condition'] == c and 'status' in r]
        n = {k: sum(r['status'] == k for r in g) for k in ('completed', 'no_path', 'rollover')}
        head = [c, len(g), n['completed'], n['no_path'], n['rollover'], len(g)-sum(n.values())]
        for k in ('sim_s', 'shape_gap_cloud_max_m', 'false_lethal', 'measured_rtf'):
            v = [r[k] for r in g]
            w.writerow(head+[k]+([min(v), float(np.median(v)), max(v)] if v else ['', '', '']))
print((here/'stage3_runs.csv').read_text()); print((here/'stage3_summary.csv').read_text())
