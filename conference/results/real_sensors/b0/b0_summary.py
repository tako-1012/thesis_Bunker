"""Stage B0 checks 1, 3, 4 from one saved run (read-only): per-sensor cloud arrival (sim-time intervals, drops),
map-update time, mission outcome, and the robot distance when each fine obstacle cell was first put in the map,
by triggering sensor. `on_truth_lethal` = the fine cell's 0.5 m cell is lethal in the truth (rock or steep).
Usage: python3 b0_summary.py RUN_DIR [RUN_DIR ...] > b0_summary.txt"""
import csv, gzip, json, sys
from pathlib import Path
import numpy as np
def q(v):
    v = np.asarray(v, float)
    return [round(float(x), 4) for x in (np.median(v), np.percentile(v, 95), v.max())] if len(v) else None
for run in map(Path, sys.argv[1:]):
    raw = next((run/'physical_1/raw').iterdir())
    m = json.loads((raw/'mission.json').read_text())
    u = list(csv.DictReader((raw/'map_updates.csv').open()))
    print('=====', run.name, raw.name)
    print('outcome', m['status'], 'sim_s', round(m['finished_t']-m['started_t'], 2), 'replans', (m.get('final_state') or {}).get('n_replans'))
    st = json.loads((run/'status.json').read_text())['simulation']['cases'][0]
    print('measured_rtf', round((st['finished_t']-st['started_t'])/st['wall_elapsed_s'], 4), 'wall_s', round(st['wall_elapsed_s'], 1))
    print('perception', json.dumps(m['perception']['sensors']))
    allu = [float(r['update_s']) for r in u if r['status'] == 'ok']
    print('update_s all (median, p95, max)', q(allu), 'n', len(allu), 'errors', sum(r['status'] != 'ok' for r in u))
    for s in sorted({r.get('sensor', 'lidar') for r in u}):
        rs = [r for r in u if r.get('sensor', 'lidar') == s and r['status'] == 'ok']
        t = np.array(sorted(float(r['stamp']) for r in rs)); g = np.diff(t)
        print(f' {s}: updates {len(rs)}, rate_sim_hz {round(len(t)/(t[-1]-t[0]), 3)}, gap_sim (median, p95, max) {q(g)}, '
              f'update_s (median, p95, max) {q([float(r["update_s"]) for r in rs])}, accepted_points median {int(np.median([int(r["accepted_points"]) for r in rs]))}')
    sj = raw/'pointcloud_map.npz.sensors.json'
    if not sj.exists() and sj.with_suffix('.json.gz').exists():
        sj = sj.with_suffix('.json.gz')  # compressed after the run (5 MB rule)
    if sj.exists():
        d = json.loads(gzip.open(sj, 'rt').read() if sj.suffix == '.gz' else sj.read_text()); ref = np.load(raw/'evaluation_reference.npz')
        for s in d['counters']:
            fd = [f for f in d['first_detections'] if f['triggering_sensor'] == s]
            dist = [f['robot_distance_xy_m'] for f in fd]
            lethal = [bool(ref['truth_lethal'][tuple(int(round(c*.1/.5)) for c in f['fine_cell'])]) for f in fd]
            dl = [x for x, l in zip(dist, lethal) if l]
            print(f' first detections by {s}: cells {len(fd)}, robot distance m (min, median, max) '
                  f'{[round(float(x), 2) for x in (min(dist), np.median(dist), max(dist))] if dist else None}, '
                  f'on_truth_lethal {sum(lethal)}, distance on truth lethal (min, median, max) '
                  f'{[round(float(x), 2) for x in (min(dl), np.median(dl), max(dl))] if dl else None}')
