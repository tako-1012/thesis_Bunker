import rclpy
from rclpy.node import Node
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node as LaunchNode
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():

    paths = PathJoinSubstitution(
        [
            FindPackageShare("bunker_unity"),
            "config",
            "paths.yaml",
        ]
    )

    return LaunchDescription([

        DeclareLaunchArgument(
            'params_file',
            default_value=paths,
            description='Path to the YAML file containing the paths parameters'
        ),
        
        LaunchNode(
            package='unity_ros2_scripts',  
            executable='launcher',  
            name='sim_launcher',        
            parameters=[LaunchConfiguration('params_file')]  
        )
    ])
