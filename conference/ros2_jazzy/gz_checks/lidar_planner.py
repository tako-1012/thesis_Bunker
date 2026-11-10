"""Stamped PointCloud2 -> stale-prior map -> task021 async ROS mission adapter."""

from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ros2_jazzy/src/thesis_bunker_mission'))
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseArray
from nav_msgs.msg import Path as ROSPath
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String, Empty
from thesis_bunker_mission.online_planner import OnlinePlannerNode
from tapp.mapfile import load_map_file
from tapp.pointcloud_map import PointCloudMap, PoseBuffer, decode_xyz
from tapp.pointcloud_map_fine import GROUND_ESTIMATES
from ros2_jazzy.gz_checks.endpoint_runtime import make_lidar_runtime
from ros2_jazzy.gz_checks.online_batch_runtime import CsvChunks
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map

UPDATE_FIELDS = ['stamp', 'status', 'error', 'version', 'input_points', 'accepted_points',
                 'observed_cells', 'update_s', 'decode_s', 'queue_drops', 'cloud_sha256']


class LidarPlannerNode(OnlinePlannerNode):
    def __init__(self, *, ground_estimate='all_returns'):
        # Deliberately do not load truth_map or construct a perfect-sensor runtime.
        Node.__init__(self, 'lidar_planner')
        for name, default in [('prior_map', ''), ('map_id', 'file/truth.npz'), ('run_folder', ''),
                              ('sensor_height_m', .8), ('max_range_m', 30.), ('obstacle_height_m', .3), ('range_resolution_m', .01),
                              ('stale_timeout_s', .5), ('map_method', 'coarse'), ('sensors', 'legacy'), ('endpoint_policy', 'none'), ('diagnostics', False),
                              ('ground_estimate', ground_estimate)]:
            self.declare_parameter(name, default)
        # Cloud age that stops the mission; 0.5s by default, raised only for slow CPU rendering.
        self.stale_timeout_s = float(self.get_parameter('stale_timeout_s').value)
        prior = load_map_file(self.get_parameter('prior_map').value)
        self.folder = Path(self.get_parameter('run_folder').value)
        if not self.get_parameter('run_folder').value:
            raise ValueError('run_folder is required')
        self.folder.mkdir(parents=True, exist_ok=True)
        self.map_id = self.get_parameter('map_id').value
        raw_obstacle = prior['obstacle'] | prior['water'] | prior['nodata']
        from tapp.sensor_geometry import sensor_configuration
        self.sensor_mode = self.get_parameter('sensors').value
        sensor_configuration(self.sensor_mode)
        self.multi = self.sensor_mode != 'legacy'
        self.mapper = make_pointcloud_map(prior['tmap'].elev, raw_obstacle,
                                    map_method=self.get_parameter('map_method').value, sensors=self.sensor_mode,
                                    ground_estimate=self.get_parameter('ground_estimate').value,
                                    robot=prior['tmap'].robot, weights=prior['tmap'].weights,
                                    sensor_height_m=self.get_parameter('sensor_height_m').value,
                                    max_range_m=self.get_parameter('max_range_m').value,
                                    range_resolution_m=self.get_parameter('range_resolution_m').value,
                                    obstacle_height_m=self.get_parameter('obstacle_height_m').value)
        self.runtime = make_lidar_runtime(prior, self.mapper, plan_log=self.folder / 'plans.csv',
            endpoint_policy=self.get_parameter('endpoint_policy').value,
            diagnostics=self.get_parameter('diagnostics').value)
        self.poses = PoseBuffer()
        self.map_pool = ThreadPoolExecutor(max_workers=1)
        self.pending = self.future = None
        self.last_cloud_stamp = self.mission_started = None
        self.dropped = self.received_clouds = 0
        self.observed_cells = 0
        self.last_error = ''
        self.terminal_sensor_error = ''
        self.mapping_finished = self.watchdog_sent = False
        self.update_fields = UPDATE_FIELDS + (['sensor', 'new_obstacle_cells'] if self.multi else [])
        self.log = CsvChunks(self.folder / 'map_updates.csv', self.update_fields)
        if self.multi:
            self.pending_by_sensor = {}
            self.source_state = {name: dict(received=0, processed=0, queue_drops=0, last_stamp=None, error='')
                                 for name in self.mapper.mounts}
        self.pose = self.received = None
        self.command = self.create_publisher(String, '/mission/online_command', 10)
        self.path = self.create_publisher(ROSPath, '/mission/path', 10)
        self.sensor_state = self.create_publisher(String, '/lidar/state', 10)
        self.create_subscription(PoseArray, '/ground_truth', self.on_pose, qos_profile_sensor_data)
        self.create_subscription(PointCloud2, '/lidar/points', self.on_cloud, qos_profile_sensor_data)
        if self.multi:
            for name in self.mapper.mounts:
                if name != 'lidar':
                    self.create_subscription(PointCloud2, '/'+name+'/points',
                                             lambda message, source=name: self.on_cloud(message, source), qos_profile_sensor_data)
        self.create_subscription(String, '/mission/command', self.on_mission, 10)
        self.create_subscription(String, '/mission/state', self.on_state, 10)
        self.create_subscription(Empty, '/mission/stop', self.on_stop, 10)
        self.create_timer(.02, self.map_tick)
        self.create_timer(.05, self.tick)

    @staticmethod
    def stamp(message):
        return message.header.stamp.sec + message.header.stamp.nanosec/1e9

    def on_pose(self, message):
        super().on_pose(message)
        stamp = self.stamp(message)
        now = self.get_clock().now().nanoseconds/1e9
        try:
            if stamp == 0 and now > .1:
                raise ValueError('ground-truth timestamp is absent')
            self.poses.add(stamp, self.pose)
        except ValueError as exc:
            self.last_error = str(exc)

    def on_cloud(self, message, sensor='lidar'):
        if self.mapping_finished:
            return
        self.received_clouds += 1
        if self.multi:
            stats = self.source_state[sensor]
            stats['received'] += 1
            if sensor in self.pending_by_sensor:
                self.dropped += 1
                stats['queue_drops'] += 1
            self.pending_by_sensor[sensor] = message
            return
        if self.pending is not None:
            self.dropped += 1
        self.pending = message  # Bounded backlog: keep only the latest unprocessed scan.

    def on_mission(self, message):
        version = self.runtime.version
        super().on_mission(message)
        if self.runtime.version != version:
            self.mission_started = self.get_clock().now().nanoseconds/1e9

    def on_state(self, message):
        super().on_state(message)
        if self.runtime.state is not None and self.runtime.finished:
            self.mapping_finished = True

    def on_stop(self, _):
        self.mapping_finished = True
        self.runtime.stop()

    def _update(self, message, pose, sensor='lidar'):
        began = time.perf_counter()
        frame = message.header.frame_id
        if frame != sensor and not frame.endswith('/'+sensor):
            raise ValueError('unexpected sensor frame: ' + frame)
        if self.stamp(message) == 0 and self.get_clock().now().nanoseconds/1e9 > .1:
            raise ValueError('LiDAR timestamp is absent')
        fields = [dict(name=f.name, offset=f.offset, datatype=f.datatype, count=f.count) for f in message.fields]
        points = decode_xyz(message.data, fields, point_step=message.point_step, row_step=message.row_step,
                            width=message.width, height=message.height, is_bigendian=message.is_bigendian)
        decoded = time.perf_counter()
        result = (self.mapper.update(points, pose, sensor=sensor, stamp=self.stamp(message)) if self.multi
                  else self.mapper.update(points, pose))
        result.update(decode_s=decoded-began, update_s=time.perf_counter()-began,
                      cloud_sha256=hashlib.sha256(message.data).hexdigest())
        first_cloud = self.folder / ('first_cloud.npz' if sensor == 'lidar' else 'first_cloud_'+sensor+'.npz')
        if not first_cloud.exists():
            np.savez_compressed(first_cloud, points=points, pose=pose, stamp=self.stamp(message))
        return result

    def _collect(self):
        if self.future is None or not self.future.done():
            return
        row = dict.fromkeys(self.update_fields)
        if self.multi:
            row['sensor'] = self.future_sensor
        row.update(stamp=self.future_stamp, status='ok', error='', queue_drops=self.dropped)
        try:
            result = self.future.result()
            row.update(result)
            if self.multi:
                stats = self.source_state[self.future_sensor]
                stats['processed'] += 1
                stats['error'] = ''
                if result['accepted_points']:
                    stats['last_stamp'] = self.future_stamp
            self.observed_cells = result['observed_cells']
            if result['accepted_points']:
                self.last_cloud_stamp = self.future_stamp
            self.last_error = ''
        except Exception as exc:
            row.update(status='error', error=type(exc).__name__ + ': ' + str(exc))
            self.last_error = row['error']
            if self.multi:
                self.source_state[self.future_sensor]['error'] = row['error']
        self.log.write(row)
        self.future = None

    def map_tick(self):
        if self.multi:
            return self.multi_map_tick()
        self._collect()
        now = self.get_clock().now().nanoseconds/1e9
        if self.future is None and self.pending is not None and not self.mapping_finished:
            message = self.pending
            stamp = self.stamp(message)
            pose = self.poses.at(stamp)
            if pose is not None:
                self.pending = None
                self.future_stamp = stamp
                self.future = self.map_pool.submit(self._update, message, pose)
            elif now-stamp > self.stale_timeout_s:
                self.pending = None
                self.dropped += 1
                self.last_error = 'no bracketing stamped pose for LiDAR cloud'
        state = dict(ready=self.last_cloud_stamp is not None and now-self.last_cloud_stamp <= self.stale_timeout_s,
                     observed_cells=self.observed_cells, received_clouds=self.received_clouds,
                     queue_drops=self.dropped, last_cloud_stamp=self.last_cloud_stamp,
                     error=self.terminal_sensor_error or self.last_error)
        message = String()
        message.data = json.dumps(state)
        self.sensor_state.publish(message)

    def multi_map_tick(self):
        self._collect()
        now = self.get_clock().now().nanoseconds/1e9
        if self.future is None and not self.mapping_finished:
            # One bounded pending cloud per source; choose the oldest stamp so
            # a faster camera cannot starve the LiDAR or the other camera.
            for sensor, message in sorted(self.pending_by_sensor.items(), key=lambda item: self.stamp(item[1])):
                stamp = self.stamp(message)
                pose = self.poses.at(stamp)
                if pose is not None:
                    del self.pending_by_sensor[sensor]
                    self.future_stamp, self.future_sensor = stamp, sensor
                    self.future = self.map_pool.submit(self._update, message, pose, sensor)
                    break
                if now-stamp > self.stale_timeout_s:
                    del self.pending_by_sensor[sensor]
                    self.dropped += 1
                    self.source_state[sensor]['queue_drops'] += 1
                    self.source_state[sensor]['error'] = 'no bracketing stamped pose'
        stamps = [s['last_stamp'] for s in self.source_state.values()]
        # Each enabled source must have accepted, fresh observations. A camera
        # cannot hide an absent/stale LiDAR, and missing cameras fail explicitly.
        self.last_cloud_stamp = min(stamps) if all(t is not None for t in stamps) else None
        state = dict(ready=self.last_cloud_stamp is not None and now-self.last_cloud_stamp <= self.stale_timeout_s,
                     observed_cells=self.observed_cells, received_clouds=self.received_clouds,
                     queue_drops=self.dropped, last_cloud_stamp=self.last_cloud_stamp,
                     sensors=self.source_state, error=self.terminal_sensor_error or self.last_error)
        message = String()
        message.data = json.dumps(state)
        self.sensor_state.publish(message)

    def tick(self):
        now = self.get_clock().now().nanoseconds/1e9
        if self.runtime.state is not None and not self.runtime.finished:
            if self.last_cloud_stamp is None or now-self.last_cloud_stamp > self.stale_timeout_s:
                if self.mission_started is not None and now-self.mission_started > .5 and not self.watchdog_sent:
                    self.terminal_sensor_error = 'lidar_unavailable_or_stale'
                    message = String()
                    message.data = json.dumps(dict(self.runtime.state['mission'], online_generated=True,
                                                   online_error='lidar_unavailable_or_stale'))
                    self.command.publish(message)
                    self.watchdog_sent = True
                    self.runtime.stop()
                return
        if hasattr(self.runtime, 'pose') and self.pose is not None:
            self.runtime.pose = np.asarray(self.pose, float).copy()
        super().tick()

    def close(self):
        self.mapping_finished = True
        self.map_pool.shutdown(wait=True)
        self._collect()
        self.runtime.close()
        self.mapper.save(self.folder / 'pointcloud_map.npz')
        (self.folder / 'sensor_status.json').write_text(json.dumps(dict(
            received_clouds=self.received_clouds, queue_drops=self.dropped,
            last_cloud_stamp=self.last_cloud_stamp, error=self.terminal_sensor_error or self.last_error,
            sensor_height_m=(self.mapper.mounts['lidar'].xyz[2] if self.multi else self.mapper.sensor_height_m),
            obstacle_height_m=self.mapper.obstacle_height_m,
            scan_storage='first cloud plus SHA-256 per processed scan; complete cloud stream not stored'), indent=2)+'\n')
        if self.multi:
            (self.folder/'sensor_status_multi.json').write_text(json.dumps(self.source_state, indent=2)+'\n')
        self.log.close()


def main(args=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--ground-estimate', choices=GROUND_ESTIMATES, default=None)
    options, remaining = parser.parse_known_args(sys.argv[1:] if args is None else args)
    # Without the new flag, pass the exact original args object to ROS.
    rclpy.init(args=remaining if options.ground_estimate is not None else args)
    node = (LidarPlannerNode(ground_estimate=options.ground_estimate)
            if options.ground_estimate is not None else LidarPlannerNode())
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
