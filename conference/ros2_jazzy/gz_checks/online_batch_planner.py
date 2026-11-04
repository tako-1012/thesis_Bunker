"""Task021 ROS adapter; reuse task014 callbacks with opt-in inflated map labels."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import rclpy
from thesis_bunker_mission.online_planner import OnlinePlannerNode
from tapp.mapfile import load_map_file
from ros2_jazzy.gz_checks.online_batch_runtime import make_runtime


class BatchPlannerNode(OnlinePlannerNode):
    def __init__(self):
        super().__init__()
        self.declare_parameter('planner', 'TA*-S+inflate')
        self.declare_parameter('plan_log', '')
        # No callback can run before spin: replace the unused default runtime.
        self.runtime.close()
        self.runtime = make_runtime(load_map_file(self.get_parameter('truth_map').value),
                                    load_map_file(self.get_parameter('prior_map').value),
                                    self.get_parameter('planner').value,
                                    plan_log=self.get_parameter('plan_log').value or None)


def main(args=None):
    rclpy.init(args=args)
    node = BatchPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.runtime.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
