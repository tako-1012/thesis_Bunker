"""Record executed synthetic errors and fixed validation-prior perturbations."""
import csv
import json
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np
import scipy
from tapp.prior_variants import prior_variant
from tapp.real_beach import build_real, list_patches
from tests.test_prior_free import test_clouds

OUT = Path(__file__).resolve().parent.parent

def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

rows = test_clouds()
write_csv(OUT/'synthetic_errors.csv', rows)
statistics=[]
print('\nPerturbed priors: validation split only; fixed values, no parameter search')
print('patch patch_index max_abs_m mean_abs_m changed_land_cells')
for patch in list_patches('validation', dataset='shizuoka_beach_las'):
    sc=build_real(patch['name'], 200, 0, dataset='shizuoka_beach_las')
    _, stats=prior_variant(sc, 'perturbed')
    row=dict(patch=patch['name'], **stats)
    statistics.append(row)
    print(row['patch'], row['patch_index'], repr(row['max_abs_m']), repr(row['mean_abs_m']), row['changed_land_cells'], flush=True)
assert len(statistics)==12
write_csv(OUT/'prior_distribution.csv', statistics)
(OUT/'verification/environment.json').write_text(json.dumps(dict(
    python=sys.version, executable=sys.executable, numpy=np.__version__, scipy=scipy.__version__,
    platform=platform.platform(), base=subprocess.check_output(['git','rev-parse','origin/realtime-map'], text=True).strip(),
    virtualenv='--system-site-packages; existing installed dependencies, no new packages',
    gazebo='not executed', validation_patches=len(statistics)), indent=2)+'\n')
