"""Read-only evidence for the saved-start success/raw-steep constraint conflict."""

import hashlib
import json
from pathlib import Path
import sys
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from experiments.endpoint_replay import CASES, saved_snapshot
from tapp.config import Robot
from tapp.traversability import slope_deg


def main():
    rows = []
    for case in CASES[:2]:
        folder = ROOT/case
        files = [folder/'pointcloud_map.npz', folder/'evaluation_reference.npz', folder/'mission.json']
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        snapshot = saved_snapshot(folder)
        start = tuple(snapshot['start'])
        with np.load(folder/'pointcloud_map.npz', allow_pickle=False) as data:
            estimated_slope = float(slope_deg(data['elev'])[start])
        with np.load(folder/'evaluation_reference.npz', allow_pickle=False) as data:
            truth_slope = float(slope_deg(data['truth_elev'])[start])
            truth_lethal = bool(data['truth_lethal'][start])
        rows.append(dict(case=case, start=list(map(int, start)), pose=snapshot['pose'].tolist(),
                         start_flags={name: bool(snapshot[name][start]) for name in ('lethal', 'seen', 'detected', 'prior_raw', 'steep')},
                         estimated_slope_deg=estimated_slope, max_slope_deg=Robot().max_slope_deg,
                         truth_slope_deg=truth_slope, truth_lethal=truth_lethal, source_sha256=before))
        assert all(hashlib.sha256(p.read_bytes()).hexdigest() == before[str(p.relative_to(ROOT))] for p in files)
    content = json.dumps(rows, ensure_ascii=False, indent=2)+'\n'
    (OUT/'saved_start_diagnosis.json').write_text(content)
    print(content, end='')


if __name__ == '__main__':
    main()
