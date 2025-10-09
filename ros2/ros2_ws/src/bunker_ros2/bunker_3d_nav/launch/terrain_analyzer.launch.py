#!/usr/bin/env python3
"""
Launch file for terrain analyzer node.
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for terrain analyzer."""
    
    # Get package directory
    package_dir = get_package_share_directory('bunker_3d_nav')
    
    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value='terrain_params.yaml',
        description='Configuration file for terrain analyzer'
    )
    
    enable_visualization_arg = DeclareLaunchArgument(
        'enable_visualization',
        default_value='true',
        description='Enable visualization markers'
    )
    
    enable_debug_arg = DeclareLaunchArgument(
        'enable_debug',
        default_value='false',
        description='Enable debug logging'
    )
    
    # Get launch configurations
    config_file = LaunchConfiguration('config_file')
    enable_visualization = LaunchConfiguration('enable_visualization')
    enable_debug = LaunchConfiguration('enable_debug')
    
    # Terrain analyzer node
    terrain_analyzer_node = Node(
        package='bunker_3d_nav',
        executable='terrain_analyzer_node',
        name='terrain_analyzer',
        output='screen',
        parameters=[
            os.path.join(package_dir, 'config', config_file),
            {
                'enable_visualization': enable_visualization,
                'enable_debug_logging': enable_debug
            }
        ],
        remappings=[
            ('/bunker/pointcloud', '/rtabmap/cloud_map'),
            ('/robot_pose', '/robot_pose'),
            ('/bunker/voxel_grid', '/terrain/voxel_grid'),
            ('/bunker/terrain_info', '/terrain/terrain_info'),
            ('/terrain/slope_map', '/terrain/slope_map'),
            ('/terrain/visualization', '/terrain/visualization')
        ]
    )
    
    return LaunchDescription([
        config_file_arg,
        enable_visualization_arg,
        enable_debug_arg,
        terrain_analyzer_node
    ])
