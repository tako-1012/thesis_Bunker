#!/usr/bin/env python3
"""
Monitor the 8-planner benchmark run every 30 minutes.

Checks:
- whether the benchmark PID is alive
- latest log lines
- completed task count in results file
- search for errors in the log

On completion (process stopped or expected tasks reached), runs a simple postprocessing summary and exits.
"""
import time
import os
import json
from datetime import datetime

PID = 125710
LOG_PATH = 'benchmark_results/run_8planners.log'
RESULTS_PATH = 'benchmark_results/dataset3_8planners_results.json'
SCENARIOS_PATH = 'dataset3_scenarios.json'
MONITOR_LOG = 'benchmark_results/monitor_benchmark.log'
CHECK_INTERVAL = 30 * 60  # 30 minutes


def log(msg):
    ts = datetime.utcnow().isoformat() + 'Z'
    line = f'[{ts}] {msg}'
    print(line)
    try:
        with open(MONITOR_LOG, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def is_pid_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tail_log(path, n=20):
    if not os.path.exists(path):
        return ''
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = 8192
            data = b''
            while end > 0 and data.count(b'\n') <= n:
                to_read = min(size, end)
                f.seek(end - to_read)
                chunk = f.read(to_read)
                data = chunk + data
                end -= to_read
            return '\n'.join(line.decode(errors='replace') for line in data.splitlines()[-n:])
    except Exception as e:
        return f'-- tail error: {e}'


def count_results(path):
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return len(data)
            # sometimes file contains partial JSON per-line
            return 0
    except Exception:
        return 0


def find_errors_in_log(path):
    if not os.path.exists(path):
        return []
    errs = []
    try:
        with open(path, 'r', errors='replace') as f:
            for line in f:
                if 'Traceback' in line or 'ERROR' in line or 'Exception' in line:
                    errs.append(line.strip())
        return errs[-20:]
    except Exception:
        return ['-- error scanning log']


def postprocess_results(results_path, scenarios_path):
    log('Postprocessing results...')
    if not os.path.exists(results_path):
        log('Results file not found: ' + results_path)
        return
    try:
        with open(results_path, 'r') as f:
            results = json.load(f)
    except Exception as e:
        log('Failed to load results JSON: ' + str(e))
        return

    # basic per-planner stats
    from collections import defaultdict
    stats = defaultdict(list)
    by_scenario = defaultdict(list)
    for r in results:
        planner = r.get('planner')
        stats[planner].append(r)
        sid = r.get('scenario_id')
        by_scenario[sid].append(r)

    summary = {}
    for planner, entries in stats.items():
        total = len(entries)
        succ = sum(1 for e in entries if e.get('success'))
        avg_time = sum(e.get('computation_time', 0.0) for e in entries) / total if total else None
        avg_time_succ = (sum(e.get('computation_time', 0.0) for e in entries if e.get('success')) / succ) if succ else None
        summary[planner] = {'total': total, 'success': succ, 'success_rate': succ/total if total else 0.0, 'avg_time_s': avg_time, 'avg_time_success_s': avg_time_succ}

    # fastest-by-scenario
    fastest = {}
    for sid, entries in by_scenario.items():
        succs = [e for e in entries if e.get('success')]
        if not succs:
            fastest[sid] = None
            continue
        best = min(succs, key=lambda x: x.get('computation_time', float('inf')))
        fastest[sid] = {'planner': best.get('planner'), 'time_s': best.get('computation_time'), 'path_length_m': best.get('path_length_meters')}

    outdir = 'benchmark_results'
    try:
        with open(os.path.join(outdir, 'dataset3_8planners_summary_auto.json'), 'w') as f:
            json.dump({'summary': summary, 'fastest_by_scenario': fastest}, f, indent=2)
        log('Wrote summary to dataset3_8planners_summary_auto.json')
    except Exception as e:
        log('Failed to write summary: ' + str(e))

    # Field D* Hybrid analysis vs D*Lite
    fd_diffs = []
    for sid, entries in by_scenario.items():
        d_entry = next((e for e in entries if e.get('planner') == 'D*Lite'), None)
        f_entry = next((e for e in entries if e.get('planner') == 'FieldD*Hybrid'), None)
        if d_entry and f_entry and d_entry.get('success') and f_entry.get('success'):
            dlen = d_entry.get('path_length_meters', 0.0)
            flen = f_entry.get('path_length_meters', 0.0)
            if dlen > 0:
                pct = (dlen - flen) / dlen * 100.0
            else:
                pct = 0.0
            fd_diffs.append(pct)

    if fd_diffs:
        import statistics
        stats_fd = {'count': len(fd_diffs), 'mean_pct_shorter': statistics.mean(fd_diffs), 'median_pct_shorter': statistics.median(fd_diffs)}
        try:
            with open(os.path.join(outdir, 'fieldd_hybrid_vs_dstar_summary.json'), 'w') as f:
                json.dump(stats_fd, f, indent=2)
            log('Wrote FieldD*Hybrid vs D*Lite summary')
        except Exception as e:
            log('Failed to write FieldD*Hybrid summary: ' + str(e))

    log('Postprocessing complete')


def main():
    log('Monitor started (interval {}s)'.format(CHECK_INTERVAL))
    # compute expected tasks
    expected = None
    try:
        with open(SCENARIOS_PATH, 'r') as f:
            scenarios = json.load(f)
            expected = len(scenarios) * 8
    except Exception:
        expected = None

    while True:
        try:
            running = is_pid_running(PID)
            completed = count_results(RESULTS_PATH)
            tail = tail_log(LOG_PATH, n=20)
            errors = find_errors_in_log(LOG_PATH)

            log(f'PID {PID} running={running} | completed tasks={completed} | expected={expected}')
            if tail:
                log('--- log tail ---\n' + tail)
            if errors:
                log('--- recent errors (max20) ---\n' + '\n'.join(errors[-20:]))

            # completion condition
            if (not running) or (expected is not None and completed >= expected):
                log('Completion detected (process stopped or expected tasks reached). Running postprocessing.')
                postprocess_results(RESULTS_PATH, SCENARIOS_PATH)
                log('Monitor exiting')
                break

        except Exception as e:
            log('Monitor loop error: ' + str(e))

        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
