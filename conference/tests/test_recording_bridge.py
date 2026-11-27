"""Read genuine task075 SensorArchive chunks through the task076 entry point."""

from contextlib import redirect_stdout
import csv
from importlib.util import find_spec
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from scipy.spatial.transform import Rotation

from experiments import offline_localization as loc
from experiments.offline_localization_synthetic import synthetic_recording
from experiments.recording_bridge import open_archive
from tapp.sensor_geometry import sensor_configuration
from tapp.sensor_recording import IMU_COLUMNS, SensorArchive, iter_lidar

BACKENDS = all(find_spec(name) is not None for name in ('kiss_icp', 'small_gicp'))


def batch_run(output):
    run = output/'raw'/'08OB86_00294'
    run.mkdir(parents=True)
    configuration = sensor_configuration('lidar_real')
    manifest = dict(sensor_configuration=configuration, cases=[dict(run_folder='raw/08OB86_00294')])
    (output/'manifest.json').write_text(json.dumps(manifest))
    return run, manifest


def write_landmark_recording(output):
    run, manifest = batch_run(output)
    recording, reference = synthetic_recording()
    mount = manifest['sensor_configuration']['mounts']['lidar']
    model_from_lidar = np.eye(4)
    model_from_lidar[:3, 3] = mount['xyz']
    model_from_lidar[:3, :3] = Rotation.from_euler('xyz', mount['rpy']).as_matrix()
    # Keep the 076 LiDAR trajectory; task075 saves the BUNKER model's pose.
    truth = recording.truth @ recording.base_from_lidar @ np.linalg.inv(model_from_lidar)
    archive = SensorArchive(run/'sensors')
    width = max(map(len, recording.scans))
    for k, (stamp, pose, scan) in enumerate(zip(recording.stamps_ns, loc.pose_values(truth), recording.scans)):
        packed = np.full((1, width, 3), np.nan, dtype=np.float32)
        packed[0, :len(scan)] = scan
        archive.add('ground_truth', int(stamp), 'world', pose)
        archive.add('imu', int(stamp), 'imu', np.arange(len(IMU_COLUMNS))+k*.01)
        archive.add('lidar', int(stamp), 'bunker/base_link/lidar', packed)
    archive.close()
    np.savez_compressed(run/'reference_cloud.npz', xyz=reference.astype(np.float32),
                        kind=np.zeros(len(reference), np.uint8), format_version=1)
    return run


class RecordingBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.run, self.manifest = batch_run(self.output)
        np.savez_compressed(self.run/'reference_cloud.npz', xyz=np.zeros((20, 3)))
        self.epoch = 1_700_000_000_000_000_000
        self.truth_rows = np.array([[0., 0., 1., 0., 0., 0., 1.],
                                    [2., 4., 1., 0., 0., 1., 0.]])
        self.imu_rows = np.arange(2*len(IMU_COLUMNS)).reshape(2, -1)*.25-.5
        first = np.array([[[1.23456, 0., 0.], [0., 3.45678, 0.], [np.nan, np.inf, -np.inf],
                           [np.nan, 2.1, 3.3], [72.12345, 0., 0.]]], dtype=np.float32)
        second = first.copy()
        second[0, 0, :] = [1.3, .047, 0.]  # Not on the first scan's ray.
        archive = SensorArchive(self.run/'sensors')
        for dt, points in ((90, first), (100, first), (105, second), (110, second)):
            archive.add('lidar', self.epoch+dt, 'lidar', points)
        archive.flush()
        for dt, values in zip((100, 110), self.truth_rows):
            archive.add('ground_truth', self.epoch+dt, 'world', values)
        for dt, values in zip((94, 115), self.imu_rows):
            archive.add('imu', self.epoch+dt, 'imu', values)
        archive.add('lidar', self.epoch+125, 'lidar', first)
        archive.close('duration_limit')
        self.scans = [first, second, second]

    def test_native_rows_and_decoded_lidar_match_writer(self):
        native = open_archive(self.run)
        np.testing.assert_array_equal(native.truth_stamp_ns-self.epoch, [100, 110])
        np.testing.assert_array_equal(native.truth_values, self.truth_rows)
        self.assertEqual(native.status, 'duration_limit')
        # Supplying a raw/ parent is unambiguous here.
        record = loc.load_recording(self.run.parent)
        np.testing.assert_array_equal(record.stamps_ns-self.epoch, [100, 105, 110])
        self.assertEqual(record.discarded_scans, 2)
        np.testing.assert_allclose(loc.pose_values(record.truth)[[0, 2]], self.truth_rows, atol=1e-15)
        np.testing.assert_allclose(record.truth[1, :3, 3], [1, 2, 1])
        np.testing.assert_allclose(record.truth[1, :3, :3],
                                   Rotation.from_euler('z', 90, degrees=True).as_matrix(), atol=1e-15)
        np.testing.assert_array_equal(record.imu_stamp_ns-self.epoch, [94, 115])
        np.testing.assert_array_equal(record.imu_values, self.imu_rows)
        self.assertEqual(record.imu_samples, 2)
        expected = [scan.xyz.reshape(-1, 3) for scan in iter_lidar(self.run/'sensors')][1:4]
        for actual, original, decoded in zip(record.scans, self.scans, expected, strict=True):
            np.testing.assert_array_equal(actual, decoded)
            np.testing.assert_allclose(actual, original.reshape(-1, 3), atol=.001, rtol=0)

    def test_truth_alias_described_in_review(self):
        path = self.run/'sensors'/'chunk_00001.npz'
        with np.load(path, allow_pickle=False) as data:
            columns = {key.replace('ground_truth_', 'truth_'): data[key] for key in data.files}
        np.savez_compressed(path, **columns)
        native = open_archive(self.run)
        np.testing.assert_array_equal(native.truth_values, self.truth_rows)

    def test_manifest_uses_model_origin_and_full_orientation(self):
        mount = self.manifest['sensor_configuration']['mounts']['lidar']
        mount.update(xyz=[.71, -.18, 1.62], base_link_xyz=[.71, -.18, 1.27], rpy=[.12, -.19, .38])
        (self.output/'manifest.json').write_text(json.dumps(self.manifest))
        actual, reference, description = loc.load_run_directory(self.run)
        np.testing.assert_array_equal(actual.base_from_lidar[:3, 3], mount['xyz'])
        np.testing.assert_allclose(actual.base_from_lidar[:3, :3],
                                   Rotation.from_euler('xyz', mount['rpy']).as_matrix(), atol=1e-15)
        self.assertEqual(reference, self.run/'reference_cloud.npz')
        self.assertIn('manifest.json#sensor_configuration.mounts.lidar.xyz/rpy', description['extrinsic_source'])

    def test_sdf_composes_lidar_and_parent_link_poses(self):
        (self.output/'manifest.json').unlink()
        sdf = self.run/'world.sdf'
        sdf.write_text("""<sdf version="1.9"><world name="beach"><model name="bunker">
          <pose>18 29 37 0 0 1</pose>
          <link name="base_link"><pose relative_to="__model__">1 2 .4 0 0 1.5707963267948966</pose>
            <sensor type="gpu_lidar" name="lidar"><pose relative_to="base_link">.3 .2 .7 .2 0 0</pose></sensor>
          </link></model></world></sdf>""")
        actual, _, description = loc.load_run_directory(self.run)
        np.testing.assert_allclose(actual.base_from_lidar[:3, 3], [.8, 2.3, 1.1], atol=1e-15)
        expected = Rotation.from_euler('z', np.pi/2) * Rotation.from_euler('x', .2)
        np.testing.assert_allclose(actual.base_from_lidar[:3, :3], expected.as_matrix(), atol=1e-15)
        self.assertEqual(description['extrinsic_source'], str(sdf))

    def test_missing_mount_and_foreign_reference_fail(self):
        with self.assertRaisesRegex(ValueError, '同じ走行フォルダの reference_cloud'):
            loc.load_run_directory(self.run, self.output/'outside.npz')
        # The legacy manifest only records the height. It does not give a complete pose.
        (self.output/'manifest.json').write_text(json.dumps({'sensor_height_m': 1.9}))
        with self.assertRaisesRegex(ValueError, 'LiDARの取り付け位置がありません'):
            loc.load_recording(self.run)

    def test_manifest_for_another_case_cannot_supply_mount(self):
        self.manifest['cases'][0]['run_folder'] = 'raw/somewhere_else'
        (self.output/'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'LiDARの取り付け位置がありません'):
            loc.load_recording(self.run)


@unittest.skipUnless(BACKENDS, 'kiss-icp / small_gicp が未導入のためスキップ')
class RecordingBridgeLocalizationTests(unittest.TestCase):
    def test_localization_cli_runs_all_three_methods_on_native_chunks(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            run = write_landmark_recording(output)
            result = output/'replay'
            with redirect_stdout(io.StringIO()) as stdout:
                loc.main(['--recording', str(run), '--out', str(result)])
            with (result/'summary.csv').open(newline='') as stream:
                summary = {row['method']: row for row in csv.DictReader(stream)}
            self.assertEqual(tuple(summary), loc.METHODS)
            self.assertTrue(all(row['frames'] == '65' for row in summary.values()))
            # 076's scale is millimetres on this independently sampled synthetic map.
            self.assertLess(float(summary['map_only']['mean_error_m']), .01)
            self.assertIn('combined: 3/3 accepted', stdout.getvalue())
            metadata = json.loads((result/'metadata.json').read_text())
            self.assertEqual(metadata['source']['recording_format'], 'sensor_archive_v1')
            self.assertEqual(metadata['source']['reference'], str(run/'reference_cloud.npz'))
            self.assertEqual((metadata['minimum_information'], metadata['correction_interval_m']), (1., 5.))
            self.assertEqual(metadata['imu_samples'], 65)
            self.assertTrue((result/'diagnostics.png').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
