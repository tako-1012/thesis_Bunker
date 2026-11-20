"""Summarize centre-trajectory distance to debris for an existing LiDAR run."""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

from tapp.config import RESOLUTION
from tapp.mapfile import load_map_file
from tapp.obstacle_clearance import cell_boxes, path_clearance


def read_csv_parts(path):
    for part in (path, *sorted(path.parent.glob(f'{path.stem}_part*.csv'))):
        with part.open(newline='') as stream:
            yield from csv.DictReader(stream)


def summarize(run, truth_map=None):
    run = Path(run)
    if truth_map is None:
        with (run/'debris_footprints.csv').open(newline='') as stream:
            bounds = np.array([[float(row[key]) for key in ('xmin', 'ymin', 'xmax', 'ymax')]
                               for row in csv.DictReader(stream)]).reshape(-1, 4)
        lower, upper = bounds[:, :2], bounds[:, 2:]
        truth_source = 'exported world collision rectangles'
    else:
        lower, upper = cell_boxes(load_map_file(truth_map)['obstacle'], RESOLUTION, -RESOLUTION/2)
        truth_source = 'truth map occupied 0.5m cells'
    if not np.isfinite([lower, upper]).all() or np.any(upper <= lower):
        raise ValueError('invalid truth debris footprint')
    xy = np.array([[float(row['x']), float(row['y'])] for row in read_csv_parts(run/'trajectory.csv')])
    if not np.isfinite(xy).all():
        raise ValueError('trajectory contains a non-finite position')
    observed = []
    if (run/'clearance.csv').exists():
        observed = [float(row['clearance_m']) for row in read_csv_parts(run/'clearance.csv')
                    if row['clearance_m']]
    return dict(run=str(run), truth_source=truth_source, trajectory_points=len(xy),
                truth_footprints=len(lower), min_truth_clearance_m=path_clearance(xy, lower, upper),
                finite_diagnostic_samples=len(observed), min_observed_clearance_m=min(observed, default=None))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--truth-map', type=Path, help='fallback NPZ with the raw debris obstacle mask')
    args = parser.parse_args()
    result = summarize(args.run, args.truth_map)
    writer = csv.DictWriter(sys.stdout, fieldnames=list(result), lineterminator='\n')
    writer.writeheader()
    writer.writerow(result)


if __name__ == '__main__':
    main()
