"""Task030: did the followed path cross cells that the online map marked lethal (periodic snapshots)?"""
import sys, glob, csv, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tapp.collision import segment_cells

def bits(z, n):
    s = tuple(z[n+'_shape'])
    return np.unpackbits(z[n+'_bits'], count=int(np.prod(s))).reshape(s).astype(bool)

for R in sys.argv[1:]:
    ref = np.load(R+'/evaluation_reference.npz')
    revs = list(csv.DictReader(open(R+'/path_revisions.csv')))
    print(R)
    for f in sorted(glob.glob(R+'/diag/periodic_*.npz')):
        z = np.load(f); t = float(z['sim_time']); L = bits(z, 'lethal')
        rv = [r for r in revs if float(r['t']) <= t][-1]
        p = np.array(json.loads(rv['path']))/0.5
        cells = np.unique(np.concatenate([segment_cells(a, b, L.shape) for a, b in zip(p[:-1], p[1:])]), axis=0)
        print(f"  snap t={t:.1f} path_t={rv['t']} path_cells={len(cells)} map_lethal_on_path={int(L[tuple(cells.T)].sum())} "
              f"truth_lethal_on_path={int(ref['truth_lethal'][tuple(cells.T)].sum())}")
