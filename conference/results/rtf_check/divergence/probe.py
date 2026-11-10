#!/usr/bin/env python3
"""Passive once-per-wall-second probe: sim clock, LiDAR state, /cmd_vel cadence. Publishes nothing."""
import csv, json, sys, time
import rclpy
from rclpy.clock import Clock as RclClock, ClockType
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String

class Probe(Node):
    def __init__(self, path):
        super().__init__('rtf_probe')
        self.f = open(path, 'w', newline='')
        self.w = csv.writer(self.f)
        self.w.writerow(['wall_s', 'sim_t', 'cloud_age_sim_s', 'ready', 'received_clouds', 'queue_drops', 'sensor_error',
                         'cmd_count', 'cmd_gap_max_wall_s', 'cmd_gap_max_sim_s', 'status'])
        self.t = self.per = self.status = None
        self.count, self.gap_w, self.gap_s = 0, 0., 0.
        self.last_w = self.last_s = None
        self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data)
        self.create_subscription(Twist, '/cmd_vel', self.cmd, 10)
        self.create_subscription(String, '/lidar/state', self.sensor, 10)
        self.create_subscription(String, '/mission/state', self.mission, 10)
        self.timer = self.create_timer(1., self.row, clock=RclClock(clock_type=ClockType.STEADY_TIME))
    def clock(self, m): self.t = m.clock.sec+m.clock.nanosec/1e9
    def sensor(self, m): self.per = json.loads(m.data)
    def mission(self, m): self.status = json.loads(m.data).get('status')
    def cmd(self, _):
        now = time.monotonic()
        if self.last_w is not None:
            self.gap_w = max(self.gap_w, now-self.last_w)
            if self.t is not None and self.last_s is not None:
                self.gap_s = max(self.gap_s, self.t-self.last_s)
        self.last_w, self.last_s = now, self.t
        self.count += 1
    def row(self):
        p = self.per or {}
        stamp = p.get('last_cloud_stamp')
        age = '' if stamp is None or self.t is None else f'{self.t-stamp:.3f}'
        self.w.writerow([f'{time.monotonic():.3f}', self.t, age, p.get('ready'), p.get('received_clouds'), p.get('queue_drops'),
                         p.get('error'), self.count, f'{self.gap_w:.4f}', f'{self.gap_s:.4f}', self.status])
        self.f.flush()
        self.count, self.gap_w, self.gap_s = 0, 0., 0.

rclpy.init()
rclpy.spin(Probe(sys.argv[1]))
