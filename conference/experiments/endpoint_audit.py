"""Offline, time-aligned actual travel in applied endpoint-clearance masks.

Example: python3 -m experiments.endpoint_audit RAW_RUN --truth RAW_RUN/evaluation_reference.npz
The evaluation map is loaded here only, never by the online planner.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from tapp.endpoint_policy import audit_path
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts


def audit_run(folder, truth=None):
    folder = Path(folder)
    rows = read_csv_parts(folder/'endpoint_trajectory.csv')
    trajectory = np.array([[float(r[k]) for k in ('sim_time', 'x', 'y')] for r in rows])
    masks = []
    for path in sorted((folder/'endpoint_masks').glob('*.npz')):
        with np.load(path, allow_pickle=False) as z:
            if not bool(z['applied']):
                continue
            shape = tuple(z['relaxed_shape'])
            mask = np.unpackbits(z['relaxed_bits'], count=int(np.prod(shape))).reshape(shape).astype(bool)
            masks.append((float(z['sim_time']), mask, path.name))
    masks.sort(key=lambda row: (row[0], row[2]))
    total = dict(relaxed_length_m=0., truth_lethal_length_m=0., truth_available=truth is not None,
                 trajectory_segments=max(0, len(trajectory)-1), applied_plans=len(masks))
    if not masks:
        return total
    index = -1
    for a, b in zip(trajectory[:-1], trajectory[1:]):
        if b[0] <= a[0]:
            continue
        while index+1 < len(masks) and masks[index+1][0] <= a[0]:
            index += 1
        times = [a[0]]+[m[0] for m in masks[index+1:] if a[0] < m[0] < b[0]]+[b[0]]
        for lo, hi in zip(times[:-1], times[1:]):
            while index+1 < len(masks) and masks[index+1][0] <= lo:
                index += 1
            if index < 0:
                continue
            xy = np.array([a[1:]+(b[1:]-a[1:])*(t-a[0])/(b[0]-a[0]) for t in (lo, hi)])
            result = audit_path(xy, masks[index][1], truth)
            for key in ('relaxed_length_m', 'truth_lethal_length_m'):
                total[key] += result[key]
    return total


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--truth', type=Path)
    args = parser.parse_args()
    truth = None
    if args.truth:
        with np.load(args.truth, allow_pickle=False) as z:
            truth = z['truth_lethal'].copy()
    report = json.dumps(audit_run(args.run, truth), indent=2)+'\n'
    (args.run/'endpoint_audit.json').write_text(report)
    print(report, end='')
