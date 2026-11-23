"""Summarize receipt, timing, and CPU evidence immediately before a pose timeout."""

import argparse
import csv
import math
from pathlib import Path
import sys

from experiments.eval_runs import discover, read_json
from tapp.pose_trace import CPU_FIELDS, NS, POSE_FIELDS, TICK_FIELDS

SUBSCRIBERS = ('follower', 'planner', 'observer')
FIELDS = ('run', 'diagnosis', 'trace_issues', 'stop_mono_ns', 'window_s', 'follower_pose_gap_s',
          *(f'{who}_{metric}' for who in SUBSCRIBERS for metric in (
              'receipts_in_window', 'usable_in_gap', 'empty_in_gap', 'header_advanced_in_gap')),
          'tick_samples_in_window', 'max_tick_interval_s', 'max_tick_duration_s',
          'tick_gap_overlaps_pose_gap', 'cpu_samples_in_window', 'cpu_pct_last', 'cpu_pct_max',
          'cpu_last_before_stop_s', 'load1_last', 'load5_last', 'load15_last')


def read_trace(folder, name, fields, *, strings=(), floats=()):
    converters = dict.fromkeys(fields, int)
    converters.update(dict.fromkeys(strings, str))
    converters.update(dict.fromkeys(floats, float))
    rows = []
    for file in (folder/f'{name}_previous.csv', folder/f'{name}.csv'):
        if not file.is_file():
            continue
        with file.open(newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(fields):
                raise ValueError(f'{file.name}: unexpected header')
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f'{file.name}:{reader.line_num}: incomplete row')
                parsed = {key: converters[key](value) if value else None for key, value in row.items()}
                if any(value is not None and not math.isfinite(value) for key, value in parsed.items()
                       if key not in strings):
                    raise ValueError(f'{file.name}:{reader.line_num}: nonfinite timestamp or value')
                if parsed['mono_ns'] is None or (rows and parsed['mono_ns'] < rows[-1]['mono_ns']):
                    raise ValueError(f'{file.name}:{reader.line_num}: missing or decreasing monotonic time')
                rows.append(parsed)
    return rows


def header_advanced(recent, gap_start):
    stamps = [row for row in recent if row['stamp_source'] == 'header' and row['stamp_ns'] is not None]
    if not stamps:
        return None
    before = [row['stamp_ns'] for row in stamps if row['mono_ns'] <= gap_start]
    during = [row['stamp_ns'] for row in stamps if row['mono_ns'] > gap_start]
    ordered = before[-1:] + during
    if not before and len(ordered) < 2:
        return None
    return any(b > a for a, b in zip(ordered, ordered[1:]))


def receipt_evidence(rows, start, gap_start, stop):
    # A pose at the gap boundary has itself already been received.
    recent = [row for row in rows if start <= row['mono_ns'] <= stop]
    gap = [row for row in recent if row['mono_ns'] > gap_start]
    return dict(receipts_in_window=len(recent), usable_in_gap=sum(bool(row['has_pose']) for row in gap),
                empty_in_gap=sum(not row['has_pose'] for row in gap), header_advanced_in_gap=header_advanced(recent, gap_start))


def tick_evidence(ticks, start, gap_start, stop):
    recent = [row for row in ticks if start <= row['mono_ns'] <= stop]
    intervals = [row['interval_ns'] for row in recent if row['interval_ns'] is not None]
    # Exclude the timeout tick itself. Its duration includes terminal logging.
    prior = [row for row in ticks if row['mono_ns'] < stop and row['duration_ns'] is not None
             and row['mono_ns']+row['duration_ns'] >= start]
    durations = [row['duration_ns'] for row in prior]
    overlap = any(row['mono_ns'] > gap_start and (row['interval_ns'] or 0) >= NS for row in recent)
    overlap |= any(row['mono_ns']+row['duration_ns'] > gap_start and row['duration_ns'] >= NS for row in prior)
    return dict(tick_samples_in_window=len(recent),
                max_tick_interval_s=max(intervals)/NS if intervals else None,
                max_tick_duration_s=max(durations)/NS if durations else None,
                tick_gap_overlaps_pose_gap=overlap if intervals or durations else None)


def cpu_evidence(rows, start, stop):
    recent = [row for row in rows if start <= row['mono_ns'] <= stop]
    if not recent:
        return dict(cpu_samples_in_window=0)
    last = recent[-1]
    percentages = [row['cpu_pct'] for row in recent if row['cpu_pct'] is not None]
    return dict(cpu_samples_in_window=len(recent), cpu_pct_last=last['cpu_pct'],
                cpu_pct_max=max(percentages) if percentages else None, cpu_last_before_stop_s=(stop-last['mono_ns'])/NS,
                **{key+'_last': last[key] for key in ('load1', 'load5', 'load15')})


def diagnosis(receipts, follower_age, ticks):
    peers = [receipt for who, receipt in receipts.items() if who != 'follower']
    follower = receipts.get('follower')
    if follower_age is None or follower is None or follower['usable_in_gap'] or ticks is None:
        return 'insufficient_data'
    if any(peer['usable_in_gap'] for peer in peers):
        return 'follower_processing_gap' if ticks else 'follower_receive_gap'
    if len(peers) == 2 and all(peer['receipts_in_window'] and not peer['empty_in_gap'] for peer in peers):
        return 'shared_upstream_gap'
    return 'insufficient_data'


def inspect(raw, window_s=5.):
    folder = raw/'pose_trace'
    issues = []

    def load(name, fields, **kwargs):
        try:
            rows = read_trace(folder, name, fields, **kwargs)
        except (OSError, ValueError) as error:
            issues.append(str(error))
            return []
        if not rows:
            issues.append(f'{name}: no samples')
        return rows

    ticks = load('follower_tick', TICK_FIELDS) if folder.is_dir() else []
    terminal = next((row for row in ticks if row['pose_timeout'] == 1), None)
    if terminal is None:
        try:
            mission = read_json(raw/'mission.json')
            status = mission.get('status')
            if status != 'pose_timeout' and raw.parent.name == 'raw':
                manifest = read_json(raw.parent.parent/'manifest.json')
                status = next((row.get('termination') for row in manifest.get('cases', []) if row.get('patch') == raw.name),
                              status)
        except (OSError, ValueError):
            return None
        if status != 'pose_timeout':
            return None
        return dict(run=str(raw), diagnosis='missing_timeout_marker',
                    trace_issues=' | '.join([*issues, 'no follower wall-clock timeout marker']))

    stop = terminal['mono_ns']
    start = stop-round(window_s*NS)
    last_pose = terminal['last_pose_received_ns']
    last_pose = last_pose if last_pose is not None and last_pose <= stop else None
    follower_age = (stop-last_pose)/NS if last_pose is not None else None
    gap_start = max(start, last_pose) if last_pose is not None else start
    receipts = {}
    for who in SUBSCRIBERS:
        rows = load(who+'_pose', POSE_FIELDS, strings=('stamp_source',))
        if rows:
            receipts[who] = receipt_evidence(rows, start, gap_start, stop)
    timing = tick_evidence(ticks, start, gap_start, stop)
    cpu = load('cpu', CPU_FIELDS, floats=CPU_FIELDS[1:])
    return dict(run=str(raw), diagnosis=diagnosis(receipts, follower_age, timing['tick_gap_overlaps_pose_gap']),
                trace_issues=' | '.join(issues), stop_mono_ns=stop, window_s=window_s, follower_pose_gap_s=follower_age,
                **{f'{who}_{key}': value for who, metrics in receipts.items() for key, value in metrics.items()},
                **timing, **cpu_evidence(cpu, start, stop))


def write_table(stream, rows):
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path, help='raw run folders or containing roots')
    parser.add_argument('--window-s', type=float, default=5., help='wall seconds before timeout to report')
    parser.add_argument('--out', type=Path, help='new CSV file (default: stdout)')
    args = parser.parse_args(argv)
    if not math.isfinite(args.window_s) or args.window_s <= 0.:
        parser.error('--window-s must be finite and positive')
    inputs = [path.resolve() for path in args.inputs]
    if any(not path.is_dir() for path in inputs):
        parser.error('inputs must be existing directories')
    runs = dict.fromkeys(run for path in inputs for run in discover(path))
    rows = [result for run in runs if (result := inspect(run, args.window_s)) is not None]
    if args.out is None:
        write_table(sys.stdout, rows)
    else:
        try:
            with args.out.open('x', encoding='utf-8', newline='') as stream:
                write_table(stream, rows)
        except OSError as error:
            parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
