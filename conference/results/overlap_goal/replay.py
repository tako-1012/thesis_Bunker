"""Replay the archived goal evidence and compare routes on two synthetic maps."""

import csv
import json
from pathlib import Path

import numpy as np

from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
from tapp.config import RESOLUTION
from tapp.obstacle_clearance import cell_boxes, path_clearance, point_clearance
from tapp.pointcloud_map_fine import OBSTACLE_CLEARANCES, PointCloudMapFine
from tapp.traversability import TraversabilityMap

FOLDER = Path(__file__).resolve().parent
BOX = (4.81, 4.81, .4)
START = (10, 15)
GOAL_NEAR_BOX = (9, 11)
GOAL_FAR_FROM_BOX = (11, 7)


def archived_goals(source):
    with source.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if (row['condition'] not in ('O', 'OT') or row['failure'] != 'goal_cell'
                    or row['overlap_halo'] != 'True' or row['centre_halo'] != 'False'):
                continue
            yield {**{key: row[key] for key in ('patch', 'condition', 'rep', 'cell', 'seen',
                                               'centre_halo', 'overlap_halo', 'steep', 'prior_rock')},
                   'overlap_goal_open': row['steep'] == row['prior_rock'] == 'False'}


def synthetic_case(clearance, goal):
    elev = np.zeros((24, 24))
    mapper = PointCloudMapFine(elev, obstacle_clearance=clearance, ground_estimate='non_obstacle')
    mapper.seen[:] = True
    ground = [[x*.5, y*.5, 0.] for x in range(8, 13) for y in range(8, 13)]
    xyz = np.asarray(ground + [BOX]*3)
    mapper.update(xyz-[0., 0., .8], np.zeros(6))
    assert mapper.fine_obstacle.sum() == 1
    boxes = cell_boxes(mapper.fine_obstacle, .1, -.25)
    runtime = LidarOnlineMission(dict(tmap=TraversabilityMap(elev, mapper.raw_obstacle)), mapper)
    try:
        runtime.start(dict(order=[0, 1], stops_cells=[goal]))
        start_m = np.asarray(START)*RESOLUTION
        result = runtime._plan_work(runtime.state, start_m)
        path = runtime._join(runtime.state, result, start_m) if result['success'] else []
    finally:
        runtime.close()
    return dict(mode=clearance, success=bool(path),
                goal_clearance_m=point_clearance(np.asarray(goal)*RESOLUTION, *boxes),
                path_clearance_m=path_clearance(path, *boxes),
                path_cells=json.dumps((np.asarray(path)/RESOLUTION).tolist(), separators=(',', ':')))


def save_table(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, rows[0], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(path.name)
    print(path.read_text(), end='')


def main():
    rows = list(archived_goals(FOLDER.parent/'eval_044/no_path_evidence.csv'))
    save_table(FOLDER/'archived_goals.csv', rows)
    cases = [('box_near_goal', GOAL_NEAR_BOX), ('box_near_intermediate', GOAL_FAR_FROM_BOX)]
    save_table(FOLDER/'synthetic_paths.csv',
               [dict(case=name, **synthetic_case(mode, goal))
                for name, goal in cases for mode in OBSTACLE_CLEARANCES])


if __name__ == '__main__':
    main()
