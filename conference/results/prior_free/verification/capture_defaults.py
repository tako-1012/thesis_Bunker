"""Capture pre-task032 byte fixtures; also usable for post-change verification."""
import hashlib
import json
from pathlib import Path
import tempfile
import numpy as np
from tests.test_ground_estimate import legacy_output_bytes
from tapp.mapfile import save_map
from data_prep.export_gazebo import export_gazebo
from ros2_jazzy.gz_checks.lidar_checks import prepare_cases


def capture():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mapping = legacy_output_bytes(root)
        z = np.indices((16, 16))[0]*.01
        obstacle = np.zeros(z.shape, bool)
        obstacle[8:10, 8:10] = True
        z[obstacle] += .4
        save_map(root/'input.npz', z, obstacle=obstacle, start_xy=[1., 1.])
        export_gazebo(root/'input.npz', root/'world')
        world = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'world').iterdir()}
        manifests = {}
        for mode, options in [('coarse', {}), ('fine', dict(map_method='fine')),
                              ('lidar_real', dict(map_method='fine', sensors='lidar_real')),
                              ('lidar_real+depth2', dict(map_method='fine', sensors='lidar_real+depth2'))]:
            prepare_cases(root/mode, **options)
            # Drop only the machine-specific Python/NumPy versions; every other byte of the manifest is still compared.
            manifest = json.loads((root/mode/'manifest.json').read_text())
            manifest.pop('input_environment', None)
            manifests[mode] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        return dict(mapping=mapping, world=world, manifests=manifests)

if __name__ == '__main__':
    print(json.dumps(capture(), indent=2, sort_keys=True))
