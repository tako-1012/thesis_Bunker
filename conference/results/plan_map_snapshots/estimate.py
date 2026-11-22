"""Size the lossless format with committed diagnostic grids and 044 counts."""

import csv
import json
import statistics
import tempfile
from pathlib import Path

import numpy as np

from experiments.eval_runs import read_csv
from ros2_jazzy.gz_checks.plan_maps import PlanMapStore
from tapp.config import Robot
from tapp.endpoint_policy import load_snapshot
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.traversability import inflate

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT/'results'


def samples():
    diagnostics = sorted(RESULTS.glob('eval_ground_endpoint/runs/*/*/physical_1/raw/*/diag/*.npz'))
    folders = sorted({file.parent for file in diagnostics})
    initial, delta, handoff = [], [], []
    with tempfile.TemporaryDirectory() as temporary:
        for index, directory in enumerate(folders):
            maps = sorted((load_snapshot(f) for f in directory.glob('*.npz')), key=lambda d: float(d['sim_time']))
            _, revisions = read_csv(directory.parent/'path_revisions.csv')
            timed = [(float(row['t']), np.asarray(json.loads(row['path']))) for row in revisions]
            store = PlanMapStore(Path(temporary)/str(index))
            for i, snapshot in enumerate(maps):
                # Reconstruct the archive's centre-mode halo. Include a full
                # veto mask sized like the observed area in the estimate.
                radius = Robot().footprint_radius
                mapper = PointCloudMapFine(snapshot['elev'], snapshot['prior_raw'])
                mapper._add_obstacles(np.flatnonzero(snapshot['fine_obstacle']).tolist())
                snapshot.update(obstacle_halo=mapper._inflated_coarse,
                                prior_inflated=inflate(snapshot['prior_raw'], radius),
                                steep_halo=inflate(snapshot['steep'], radius),
                                veto_supported=snapshot['seen'],
                                retained_lethal=np.zeros_like(snapshot['seen']))
                path_m = next((path for stamp, path in reversed(timed) if stamp <= snapshot['sim_time']),
                              np.asarray([snapshot['pose'][:2]]))
                result = dict(path=path_m/float(snapshot['resolution_m']), success=True, reason='distance')
                before = store.bytes
                plan_id = store.search(snapshot, result, '')
                (initial if i == 0 else delta).append(store.bytes-before)
                before = store.bytes
                store.application(plan_id, dict(path=path_m, revision=i+1), float(snapshot['sim_time']))
                handoff.append(store.bytes-before)
    return initial, delta, handoff


def main():
    with (RESULTS/'eval_044/common_eval/runs.csv').open() as stream:
        counts = [int(r['n_plans']) for r in csv.DictReader(stream)]
    initial, delta, handoff = samples()
    print('044 runs, minimum/median/maximum searches:', len(counts), min(counts), statistics.median(counts), max(counts))
    for name, sizes in [('full first map', initial), ('XOR delta', delta), ('handoff', handoff)]:
        print(f'{name}: n={len(sizes)} min/median/max bytes={min(sizes)}/{statistics.median(sizes)}/{max(sizes)}')
    for count in (min(counts), int(statistics.median(counts)), max(counts)):
        typical = statistics.median(initial)+(count-1)*statistics.median(delta)+count*statistics.median(handoff)
        sampled_max = max(initial)+(count-1)*max(delta)+count*max(handoff)
        print(f'{count} searches: median-sampled estimate {typical/1e6:.3f} MB; max-sampled estimate {sampled_max/1e6:.3f} MB')


if __name__ == '__main__':
    main()
