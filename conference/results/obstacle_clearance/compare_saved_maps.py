"""Count lost free cells and newly disconnected endpoints in archived fine maps."""

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import label

from tapp.pointcloud_map_fine import PointCloudMapFine, RATIO


def compare(run):
    with np.load(run/'pointcloud_map.npz', allow_pickle=False) as data:
        lethal = data['lethal']
        shape = tuple(data['fine_shape'])
        count = int(np.prod(shape))
        keys = np.flatnonzero(np.unpackbits(data['fine_obstacle_bits'], count=count))
        old_inflated = np.unpackbits(data['fine_inflated_bits'], count=count).reshape(shape).astype(bool)
        seen = data['seen']
    mapper = PointCloudMapFine(np.zeros(lethal.shape), obstacle_clearance='overlap')
    mapper._add_obstacles(keys.tolist())
    centre = old_inflated[RATIO//2::RATIO, RATIO//2::RATIO]
    if np.any(centre & ~lethal) or np.any(centre & ~mapper._inflated_coarse):
        raise ValueError(f'not an archived centre fine map: {run}')
    overlap = lethal | mapper._inflated_coarse
    added = overlap & ~lethal
    mission = json.loads((run/'mission.json').read_text())
    start = tuple(mission['start_cells'])
    goals = [tuple(goal) for goal in mission['stops_cells']]

    def reachable(mask):
        regions, _ = label(~mask)
        component = regions[start]
        return {i for i, goal in enumerate(goals) if component and regions[goal] == component}

    before_goals, after_goals = reachable(lethal), reachable(overlap)
    return dict(run=str(run), cells=lethal.size, detected_fine_cells=len(keys),
                centre_free=int((~lethal).sum()), overlap_free=int((~overlap).sum()),
                lost_free=int(added.sum()), lost_free_seen=int((added & seen).sum()),
                reachable_centre_goals=len(before_goals), reachable_overlap_goals=len(after_goals))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    args = parser.parse_args()
    rows = [compare(run) for run in args.runs]
    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)


if __name__ == '__main__':
    main()
