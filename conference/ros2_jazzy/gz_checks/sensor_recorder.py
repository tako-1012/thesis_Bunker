"""Capture unmodified ROS sensor streams in a separate process for task075."""

import argparse
from pathlib import Path

from tapp.pointcloud_map import decode_xyz
from tapp.sensor_recording import SensorArchive


def header(msg):
    stamp = msg.header.stamp
    return stamp.sec * 1_000_000_000 + stamp.nanosec, msg.header.frame_id


def xyz(vector):
    return vector.x, vector.y, vector.z


def quaternion(rotation):
    return *xyz(rotation), rotation.w


def record_lidar(archive, msg):
    stamp, frame = header(msg)
    if archive.stopped:
        return
    fields = [dict(name=f.name, offset=f.offset, datatype=f.datatype, count=f.count) for f in msg.fields]
    points = decode_xyz(msg.data, fields, point_step=msg.point_step, row_step=msg.row_step,
                        width=msg.width, height=msg.height, is_bigendian=msg.is_bigendian)
    if all(f['datatype'] == 7 for f in fields if f['name'] in ('x', 'y', 'z')):
        points = points.astype('float32')
    archive.add('lidar', stamp, frame, points.reshape(msg.height, msg.width, 3))


def record_imu(archive, msg):
    archive.add('imu', *header(msg), (*quaternion(msg.orientation), *xyz(msg.angular_velocity),
                *xyz(msg.linear_acceleration), *msg.orientation_covariance, *msg.angular_velocity_covariance,
                *msg.linear_acceleration_covariance))


def record_truth(archive, msg):
    if archive.stopped:
        return
    if not msg.poses:
        archive.skipped_empty += 1
        return
    pose = msg.poses[0]
    archive.add('ground_truth', *header(msg), (*xyz(pose.position), *quaternion(pose.orientation)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--seconds', type=float)
    args = parser.parse_args()

    import rclpy
    from geometry_msgs.msg import PoseArray
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Imu, PointCloud2

    archive = SensorArchive(args.folder, duration_s=args.seconds)
    rclpy.init(args=[])
    node = Node('thesis_sensor_recorder')
    qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT)
    for message, topic, callback in ((PointCloud2, '/lidar/points', record_lidar),
                                     (Imu, '/imu', record_imu),
                                     (PoseArray, '/ground_truth', record_truth)):
        node.create_subscription(message, topic, lambda msg, cb=callback: cb(archive, msg), qos)
    reason = 'finished'
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        reason = 'error'
        raise
    finally:
        archive.close(reason)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
