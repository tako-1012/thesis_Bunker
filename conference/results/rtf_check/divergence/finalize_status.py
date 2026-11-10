#!/usr/bin/env python3
"""Record simulation, measurement and existing-report outcomes separately; never raises."""
import csv, json, sys
from pathlib import Path
run = Path(sys.argv[1]); out = run/'physical_1'; console = run/'console.log'
def text(path):
    try:
        return path.read_text(errors='replace')
    except OSError:
        return None
def rows(path):
    try:
        return len(list(csv.reader(path.open())))-1
    except (OSError, csv.Error):
        return 0
status = dict(run=run.name)
try:
    docker_exit = int(text(run/'docker_exit.txt'))
except (TypeError, ValueError):
    docker_exit = None
checks_text = text(out/'lidar_checks_exit.txt')
checks_exit = int(checks_text) if checks_text and checks_text.strip().isdigit() else None
sim = dict(docker_exit=docker_exit, timed_out=docker_exit in (124, 137), manifest='missing', cases=[])
try:
    m = json.loads((out/'manifest.json').read_text())
    sim.update(manifest='ok', execution=m.get('execution'), real_time_factor=m.get('real_time_factor'),
               stale_timeout_s=m.get('stale_timeout_s'), map_method=m.get('map_method'),
               gazebo=(m.get('environment') or {}).get('gazebo'))
    for c in m['cases']:
        if c.get('selected'):
            item = dict(patch=c['patch'], termination=c.get('termination'), error=c.get('error'))
            try:
                run_m = json.loads((out/c['run_folder']/'mission.json').read_text())
                item.update(status=run_m.get('status'), started_t=run_m.get('started_t'),
                            finished_t=run_m.get('finished_t'), wall_elapsed_s=run_m.get('wall_elapsed_s'),
                            online_error=(run_m.get('final_state') or {}).get('error'))
            except (OSError, TypeError, ValueError) as exc:
                item['mission_json'] = type(exc).__name__
            sim['cases'].append(item)
except (OSError, ValueError, KeyError) as exc:
    sim['manifest'] = type(exc).__name__
sim['ok'] = (sim.get('execution') == 'finished' and not sim['timed_out']
             and bool(sim['cases']) and all(not c['error'] for c in sim['cases']))
status['simulation'] = sim
measure = dict(probe_rows=rows(out/'probe.csv'), resource_rows=rows(run/'resources.csv'),
               gz_stats_samples=(text(out/'gz_stats.txt') or '').count('real_time_factor'),
               world_audit=(text(out/'world_audit.txt') or '').strip().splitlines(),
               probe_stderr_tail=(text(out/'probe_stdout.txt') or '').strip().splitlines()[-3:])
measure['ok'] = measure['probe_rows'] > 0 and measure['resource_rows'] > 0 and measure['gz_stats_samples'] > 0 and bool(measure['world_audit'])
status['measurement'] = measure
log = text(console) or ''
tail = [l for l in log.strip().splitlines() if l.strip()]
trace_at = log.rfind('Traceback (most recent call last)')
trace = log[trace_at:] if trace_at >= 0 else ''
in_report = 'lidar_fine_report' in trace or 'summarize(' in trace
last = trace.strip().splitlines()[-1] if trace else ''
EXPECTED = {'ValueError: fine run conditions differ from task022',
            'ValueError: retain all ten scenarios, including unexecuted cases'}
if checks_exit is None:
    kind = 'not_run'
elif checks_exit == 0:
    kind = 'passed'
elif in_report and last in EXPECTED:
    kind = 'expected_failure'
elif in_report:
    kind = 'unexpected_failure'
else:
    kind = 'failed_outside_report'
status['existing_report'] = dict(lidar_checks_exit=checks_exit, result=kind, last_error=last,
                                 note='execution is saved before summarize runs, so a report failure does not touch raw records')
(run/'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2)+'\n')
print(run.name, 'simulation_ok', sim['ok'], 'measurement_ok', measure['ok'], 'report', kind)
