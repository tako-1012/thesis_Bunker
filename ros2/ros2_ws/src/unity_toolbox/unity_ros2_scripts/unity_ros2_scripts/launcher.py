import os
import signal
import rclpy
from rclpy.node import Node
import subprocess

class SimLancher(Node):
    def __init__(self):
        super().__init__('sim_launcher')
        self.proc = None

        self.declare_parameter('unity_path', '')
        unity_path = self.get_parameter('unity_path').get_parameter_value().string_value

        if not os.path.isfile(unity_path):
            self.get_logger().fatal('\033[31m' + 'Unity executable not found at: ' + unity_path + '\033[0m')
            return

        self.declare_parameter('project_path', '')
        project_path = self.get_parameter('project_path').get_parameter_value().string_value

        if not os.path.isdir(project_path):
            self.get_logger().fatal('\033[31m' + 'Project not found at: ' + project_path + '\033[0m')
            return

        command = [unity_path, "-projectPath", project_path]
        
        self.get_logger().info(f"Starting Unity with command: {' '.join(command)}")

        try:
            self.proc = subprocess.Popen(command, preexec_fn=os.setsid)
        except Exception as e:
            self.get_logger().fatal(f'\033[31mFailed to start Unity: {str(e)}\033[0m')
            return
        self.get_logger().info('\033[32m' + 'Unity started succesfully' + '\033[0m')
    
    def __del__(self):
        if self.proc is not None:
            if self.proc.poll() is None:  
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)  

def main(args=None):
    rclpy.init(args=args)

    minimal_publisher = SimLancher()

    rclpy.spin(minimal_publisher)

    minimal_publisher.destroy_node()

    rclpy.shutdown()

if __name__ == '__main__':
    main()
