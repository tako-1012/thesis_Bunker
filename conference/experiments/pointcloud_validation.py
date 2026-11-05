"""Validation-only dense artificial DEM returns; NOT Gazebo or VLP-16 performance.

All mapper assumptions are fixed before this audit. No parameter is selected.
This tests registration/height bookkeeping on twelve real validation DEMs, but
omits beam sparsity, occlusion, dynamics, and true sensor noise/reflectance.
"""

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.real_beach import list_patches, build_real
from tapp.pointcloud_map import PointCloudMap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results/gazebo_lidar/validation')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in list_patches('validation', dataset='shizuoka_beach_las'):
        prior = build_real(row['name'], 200, 0, dataset='shizuoka_beach_las')
        truth = build_real(row['name'], 200, 0, debris=True, dataset='shizuoka_beach_las')
        tm = truth['tmap']
        cell = tuple(truth['start'])
        pose = np.array([cell[0]*RESOLUTION, cell[1]*RESOLUTION, tm.elev[cell], 0, 0, 0])
        grid = np.indices(tm.shape).reshape(2, -1).T*RESOLUTION
        world = np.column_stack((grid, tm.elev.ravel()))
        local = world-pose[:3]-[0, 0, .8]
        radius = np.linalg.norm(local, axis=1)
        select = (radius >= .1) & (radius < 29.995)
        local = np.repeat(local[select], 3, axis=0)
        rng = np.random.default_rng(np.random.SeedSequence([100, 22, truth['patch_index']]))
        direction = local/np.linalg.norm(local, axis=1)[:, None]
        local += direction*rng.normal(0, .02, (len(local), 1))
        raw = prior['terrain']['rock'] | prior['terrain']['water'] | prior['terrain']['nodata']
        mapper = PointCloudMap(prior['tmap'].elev, raw)
        result = mapper.update(local, pose)
        error = np.abs(mapper.elev[mapper.seen]-tm.elev[mapper.seen])
        rows.append(dict(source='validation_dense_artificial_returns', patch=row['name'],
                         observed_cells=int(mapper.seen.sum()), error_median_m=float(np.median(error)),
                         error_p95_m=float(np.percentile(error, 95)), update_s=result['update_s'],
                         input_points=result['input_points']))
        print('audited', row['name'], flush=True)
    data = pd.DataFrame(rows)
    data.to_csv(args.output/'height_audit.csv', index=False)
    stream = io.StringIO()
    with redirect_stdout(stream):
        print('VALIDATION ONLY: dense artificial DEM returns, not Gazebo/VLP-16 measurements; no tuning.')
        print(data.to_string(index=False, float_format=lambda v: f'{v:.6g}'))
    log = stream.getvalue()
    (args.output/'validation_log.txt').write_text(log)
    (args.output/'protocol.json').write_text(json.dumps(dict(
        split='validation', dataset='shizuoka_beach_las', seed='SeedSequence([100,22,patch_index])',
        scope='dense cell-centre synthetic returns, independent Gaussian 0.02m radial noise; no occlusion/beam model',
        parameter_selection='none; assumptions fixed before audit'), indent=2)+'\n')
    print(log, end='')


if __name__ == '__main__':
    main()
