"""Test synchronized replay and optional offline localization without ROS."""

from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
from scipy.spatial.transform import Rotation

from experiments import offline_localization as loc
from experiments.offline_localization_synthetic import synthetic_recording

BACKENDS = all(find_spec(name) is not None for name in ('kiss_icp', 'small_gicp'))


class OfflineInputTests(unittest.TestCase):
    def test_packed_recording_decodes_range_interpolates_pose_and_keeps_ns(self):
        epoch = 1_700_000_000_000_000_000
        xyz = [[0., 0., 0.], [1., 2., 3.]]
        quat = Rotation.from_euler('z', [[0.], [90.]], degrees=True).as_quat()
        b = np.eye(4)
        b[:3, 3] = [-.24, 0., 1.05]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            np.savez_compressed(
                root/'recording.npz',
                lidar_stamp_ns=epoch+np.array([95, 100, 105, 110, 115], np.int64),
                truth_stamp_ns=epoch+np.array([100, 110], np.int64),
                truth_xyz_quat_xyzw=np.column_stack((xyz, quat)),
                base_from_lidar=b, azimuth_rad=np.array([0., np.pi/2]),
                elevation_rad=np.array([0., np.pi/6]),
                ranges_mm=np.repeat(np.array([[[1000, 2000], [0, 65535]]], np.uint16), 5, axis=0),
                imu_stamp_ns=epoch+np.array([103, 107], np.int64),
                imu_angular_velocity=np.zeros((2, 3)), imu_linear_acceleration=np.zeros((2, 3)),
            )
            np.savez_compressed(root/'reference_cloud.npz', xyz=np.zeros((23, 3)), kind=np.ones(23))
            recording = loc.load_recording(root/'recording.npz')
            self.assertEqual(loc.load_reference(root/'reference_cloud.npz').shape, (23, 3))
        np.testing.assert_array_equal(recording.stamps_ns, epoch+np.array([100, 105, 110]))
        np.testing.assert_allclose(recording.truth[1, :3, 3], [.5, 1., 1.5])
        np.testing.assert_allclose(recording.truth[1, :3, :3],
                                   Rotation.from_euler('z', 45., degrees=True).as_matrix(), atol=1e-15)
        np.testing.assert_allclose(list(recording.scans)[1], [[1., 0., 0.], [0., 2., 0.]], atol=1e-15)
        np.testing.assert_array_equal(recording.base_from_lidar, b)
        self.assertEqual((recording.imu_samples, recording.discarded_scans), (2, 2))

    def test_weakest_direction_is_reported_in_world_axes(self):
        h = np.diag([40., 50., 60., 1., 20., 30.])
        r = Rotation.from_euler('z', 90., degrees=True).as_matrix()
        info = loc.information(h, 2, r)
        self.assertEqual(info.weak_axis, 'cross_shore')
        np.testing.assert_allclose(info.translation, [.5, 10., 15.])
        np.testing.assert_allclose(info.rotation, [20., 25., 30.])
        np.testing.assert_allclose(info.weak_direction_world, [0., 0., 0., 0., 1., 0.], atol=1e-15)
        self.assertAlmostEqual(info.weakest, .5)
        self.assertIsNone(loc.information(h, 0, r))


@unittest.skipUnless(BACKENDS, 'kiss-icp / small_gicp が未導入のためスキップ')
class OfflineLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.landmarks, cls.reference = synthetic_recording()
        cls.result = loc.localize(cls.landmarks, cls.reference)
        cls.plane, cls.plane_reference = synthetic_recording('plane')
        cls.flat_result = loc.localize(cls.plane, cls.plane_reference)

    def test_kiss_icp_tracks_relative_motion_and_keeps_fixed_initial_offset(self):
        truth, odom = self.landmarks.truth, self.result.poses['odometry']
        np.testing.assert_allclose(odom[0, :3, 3]-truth[0, :3, 3], [.5, 0., 0.], atol=1e-12)
        r = Rotation.from_matrix(odom[0, :3, :3] @ truth[0, :3, :3].T).as_rotvec(degrees=True)
        np.testing.assert_allclose(r, [0., 0., 2.], atol=1e-12)
        errors, summary = loc.trajectory_metrics(self.landmarks, self.result)
        self.assertLess(errors['odometry'].max(), 1.)
        self.assertLess(summary[0]['relative_drift_m_per_m'], .05)
        relative = np.linalg.inv(odom[0]) @ odom
        relative_truth = np.linalg.inv(truth[0]) @ truth
        self.assertLess(np.linalg.norm((relative[:, :3, 3]-relative_truth[:, :3, 3]), axis=1).max(), .2)

    def test_scan_to_map_recovers_position_and_yaw_from_initial_offset(self):
        truth = self.landmarks.truth
        aligned = self.result.poses['map_only']
        errors = np.linalg.norm(aligned[:, :3, 3]-truth[:, :3, 3], axis=1)
        self.assertLess(errors.max(), .04)
        angle = Rotation.from_matrix(aligned[0, :3, :3] @ truth[0, :3, :3].T).magnitude()
        self.assertLess(np.degrees(angle), .5)
        self.assertTrue(self.result.alignments[0]['accepted'])

    def test_flat_plane_has_weak_translation_parallel_to_surface(self):
        weak = self.flat_result.alignments[0]['information']
        strong = self.result.alignments[0]['information']
        self.assertLess(weak.weakest, loc.MIN_INFORMATION)
        self.assertGreater(strong.weakest, 5*weak.weakest)
        self.assertIn(weak.weak_axis, ('alongshore', 'cross_shore'))
        self.assertLess(abs(weak.weak_direction_world[-1]), .01)
        self.assertLess(np.linalg.norm(weak.weak_direction_world[:3]), .1)

    def test_combined_corrects_at_odometry_multiples_in_landmark_scene(self):
        combined = [event for event in self.result.alignments if event['method'] == 'combined']
        self.assertEqual([event['scheduled_distance_m'] for event in combined], [5., 10., 15.])
        for event in combined:
            scan = event['scan']
            schedule = event['scheduled_distance_m']
            self.assertGreaterEqual(self.result.odometry_distance_m[scan], schedule)
            self.assertLess(self.result.odometry_distance_m[scan-1], schedule)
            self.assertTrue(event['accepted'])
        first = combined[0]['scan']
        tracks = self.result.poses
        np.testing.assert_array_equal(tracks['combined'][:first], tracks['odometry'][:first])
        end_error = np.linalg.norm(tracks['combined'][-1, :3, 3]-self.landmarks.truth[-1, :3, 3])
        self.assertLess(end_error, .04)

    def test_combined_rejects_low_information_even_when_registration_converges(self):
        # KISS-ICP on this featureless plane may never reach a scheduled 5 m.
        # Inject a known relative motion so the real GICP registration and gate are exercised.
        config, _, gicp = loc.load_backends()
        take = [0, 20, 40, 60]
        plane = self.plane
        data = loc.Recording(plane.stamps_ns[take], plane.truth[take],
                             [plane.scans[i] for i in take], plane.base_from_lidar)
        world_from_lidar = data.truth @ data.base_from_lidar
        relative = np.linalg.inv(world_from_lidar[0]) @ world_from_lidar

        class KnownOdometry:
            def __init__(self, _config):
                self.last_pose = np.eye(4)
                self.motion = iter(relative)

            def register_frame(self, _xyz, _stamps):
                self.last_pose = next(self.motion)

        with patch.object(loc, 'load_backends', return_value=(config, KnownOdometry, gicp)):
            result = loc.localize(data, self.plane_reference)
        attempts = [event for event in result.alignments if event['method'] == 'combined']
        self.assertEqual(len(attempts), 3)
        for event in attempts:
            self.assertTrue(event['converged'])
            self.assertFalse(event['accepted'])
            self.assertEqual(event['status'], 'weak_information')
            self.assertLess(event['information'].weakest, loc.MIN_INFORMATION)
        np.testing.assert_array_equal(result.poses['combined'], result.poses['odometry'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
