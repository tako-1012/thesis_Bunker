"""Replay three saved final maps; no ROS, Gazebo or evaluation truth in planning."""
import json
from pathlib import Path
import numpy as np
from tapp.config import RESOLUTION, DEFAULT_W
from tapp.real_beach import build_real
from tapp.traversability import TraversabilityMap
from tapp.footprint import inflate_steep
from tapp.endpoint_policy import plan_endpoint, raw_mask, classify_failure, audit_path
ROOT = Path(__file__).resolve().parents[1]
CASES = (
 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706',
 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706',
 'results/lidar_fine/physical_10/raw/08OB88_-1417',
)


def saved_snapshot(folder):
    folder = Path(folder)
    mission = json.loads((folder/'mission.json').read_text())
    pose = mission['final_state']['pose']
    goal = np.rint(np.asarray(mission['final_state']['current_path'][-1])/RESOLUTION).astype(int)
    with np.load(folder/'pointcloud_map.npz', allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files}
    prior = build_real(folder.name, 200, 0, dataset='shizuoka_beach_las')
    raw = prior['terrain']['rock'] | prior['water'] | prior['nodata']
    with np.load(folder/'evaluation_reference.npz', allow_pickle=False) as z:
        prior_tm = TraversabilityMap(z['prior_elev'], raw)
        assert np.array_equal(prior_tm.rock, z['prior_rock'])
        prior_lethal = inflate_steep(prior_tm, .5)
    seen = data['seen']
    cost = 1.+DEFAULT_W*np.where(seen, data['cost'], np.where(prior_lethal, 1., prior_tm.cost))
    return dict(lethal=seen & data['lethal'], cost=cost, seen=seen,
                detected=data['obstacle'], prior_raw=raw,
                steep=TraversabilityMap(data['elev'], raw).steep,
                pose=np.asarray(pose), start=np.rint(np.asarray(pose[:2])/RESOLUTION).astype(int),
                goal=goal, sim_time=mission['final_state']['sim_time'], version=data['version'])


def replay():
    rows = []
    for case in CASES:
        folder = ROOT/case
        snapshot = saved_snapshot(folder)
        none, escape = plan_endpoint(snapshot, 'none'), plan_endpoint(snapshot, 'escape')
        assert not none['success'], case
        assert not (escape['relaxed'] & raw_mask(snapshot)).any()
        with np.load(folder/'evaluation_reference.npz') as z:
            truth = z['truth_lethal']
        audit = audit_path(np.asarray(escape['path'])*RESOLUTION, escape['relaxed'], truth)
        rows.append(dict(case=case, failure_class=classify_failure(snapshot),
                         none='path' if none['success'] else 'no_path',
                         escape='path' if escape['success'] else 'unreachable_after_retry_then_next_stop',
                         goal=list(map(int, escape['goal'])), outcome=escape['outcome'],
                         relaxed_cells=int(escape['relaxed'].sum()),
                         relaxed_truth_lethal_cells=int((escape['relaxed'] & truth).sum()),
                         raw_cells_cleared=int((escape['relaxed'] & raw_mask(snapshot)).sum()), **audit))
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    content = json.dumps(replay(), ensure_ascii=False, indent=2)+'\n'
    print(content, end='')
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'replay.json').write_text(content)
