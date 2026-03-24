#!/usr/bin/env python3
import os
import numpy as np
import json
from importlib import util

base = os.path.join(os.path.dirname(__file__), '..')
orig_npz = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
amplified_npz = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_amplified_data.npz')
meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')

print('Loading original:', orig_npz)
data = np.load(orig_npz)
# amplify elevation
elev = data['elevation'].copy()
factor = 6.0
print('Amplifying elevation by factor', factor)
elev_ampl = elev * factor
# save amplified npz
np.savez(amplified_npz, voxel_grid=data['voxel_grid'], elevation=elev_ampl, roughness=data['roughness'], density=data['density'])
print('Saved amplified NPZ:', amplified_npz)

# now run planners on amplified scenario using code from make_fig4_path_visualization_final
from subprocess import run
run(['python3','scripts/make_fig4_path_visualization_final.py'], check=True)
print('Re-run final visualization (will pick up amplified npz automatically if exist)')
