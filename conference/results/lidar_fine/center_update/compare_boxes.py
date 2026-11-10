"""Run the exact a6bf889 mapper and corrected mapper on fixed synthetic boxes."""

import csv
import io
from pathlib import Path
import subprocess
import sys
import types
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from tapp.pointcloud_map_fine import PointCloudMapFine
from tests.test_pointcloud_map_fine import box_cloud

BASE = 'a6bf889c763484640bda6139e6291d2492d191ff'


def main():
    source = subprocess.check_output(
        ['git', 'show', BASE+':conference/tapp/pointcloud_map_fine.py'], cwd=ROOT, text=True)
    previous = types.ModuleType('tapp._task023_before_centre_clearance')
    previous.__package__ = 'tapp'
    exec(compile(source, BASE+':pointcloud_map_fine.py', 'exec'), previous.__dict__)
    cases = [('noisy_box_'+str(seed), *box_cloud(seed)) for seed in range(100, 105)]
    world = np.array([[5.35, 5., .4]]*3+[[5.5, 5., 0.]]*16)
    cases.append(('side_spill_0.1m', world-[2, 2, .8], [2, 2, 0, 0, 0, 0]))
    rows = []
    for name, cloud, pose in cases:
        before = previous.PointCloudMapFine(np.zeros((40, 40)))
        after = PointCloudMapFine(np.zeros((40, 40)))
        before.update(cloud, pose)
        after.update(cloud, pose)
        for field in ['elev', 'seen', 'detected_obstacle', 'fine_obstacle']:
            assert getattr(before, field).tobytes() == getattr(after, field).tobytes(), (name, field)
        assert before.tm.cost.tobytes() == after.tm.cost.tobytes()
        outside = np.ones(before.prior.shape, bool)
        outside[10, 10] = False  # Fixed true box footprint [4.75,5.25]^2.
        rows.append(dict(fixture=name, before_total=int(before.lethal.sum()), after_total=int(after.lethal.sum()),
                         before_outside=int((before.lethal & outside).sum()),
                         after_outside=int((after.lethal & outside).sum()),
                         before_next_cell=bool(before.lethal[12, 10]),
                         after_next_cell=bool(after.lethal[12, 10])))
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    table = stream.getvalue()
    (OUT/'box_comparison.csv').write_text(table)
    log = ('Synthetic inputs only; not Gazebo measurements. Before = exact '+BASE+' mapper.\n'
           'Outside excludes the true box centre cell (10,10); next cell is (12,10), centre (6.0,5.0)m.\n'
           +table+'Height, cost, seen and detected obstacle bytes are unchanged on every fixture.\n')
    (OUT/'box_comparison_log.txt').write_text(log)
    print(log, end='')


if __name__ == '__main__':
    main()
