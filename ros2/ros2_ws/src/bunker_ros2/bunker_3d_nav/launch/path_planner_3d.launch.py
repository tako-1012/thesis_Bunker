#!/usr/bin/env python3
"""
Launch file for 3D path planner node.
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for 3D path planner."""
    
    # Get package directory
    package_dir = get_package_share_directory('bunker_3d_nav')
    
    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value='planner_params.yaml',
        description='Configuration file for path planner'
    )
    
    enable_visualization_arg = DeclareLaunchArgument(
        'enable_visualization',
        default_value='true',
        description='Enable visualization markers'
    )
    
    enable_path_smoothing_arg = DeclareLaunchArgument(
        'enable_path_smoothing',
        default_value='true',
        description='Enable path smoothing'
    )
    
    enable_debug_arg = DeclareLaunchArgument(
        'enable_debug',
        default_value='false',
        description='Enable debug logging'
    )
    
    # Get launch configurations
    config_file = LaunchConfiguration('config_file')
    enable_visualization = LaunchConfiguration('enable_visualization')
    enable_path_smoothing = LaunchConfiguration('enable_path_smoothing')
    enable_debug = LaunchConfiguration('enable_debug')
    
    # Path planner 3D node
    path_planner_3d_node = Node(
        package='bunker_3d_nav',
        executable='path_planner_3d_node',
        name='path_planner_3d',
        output='screen',
        parameters=[
            os.path.join(package_dir, 'config', config_file),
            {
                'enable_visualization': enable_visualization,
                'enable_path_smoothing': enable_path_smoothing,
                'enable_debug_logging': enable_debug
            }
        ],
        remappings=[
            ('/terrain/voxel_grid', '/terrain/voxel_grid'),
            ('/goal_pose', '/goal_pose'),
            ('/current_pose', '/current_pose'),
            ('/path_3d', '/path_3d'),
            ('/path_visualization', '/path_visualization'),
            ('/path_cost', '/path_cost')
        ]
    )
    
    return LaunchDescription([
        config_file_arg,
        enable_visualization_arg,
        enable_path_smoothing_arg,
        enable_debug_arg,
        path_planner_3d_node
    ])
