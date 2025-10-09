#!/usr/bin/env python3
"""
Launch file for full 3D navigation system.
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for full 3D navigation system."""
    
    # Get package directory
    package_dir = get_package_share_directory('bunker_3d_nav')
    
    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value='planner_params.yaml',
        description='Configuration file for the system'
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
    
    enable_rviz_arg = DeclareLaunchArgument(
        'enable_rviz',
        default_value='true',
        description='Enable RViz visualization'
    )
    
    # Get launch configurations
    config_file = LaunchConfiguration('config_file')
    enable_visualization = LaunchConfiguration('enable_visualization')
    enable_path_smoothing = LaunchConfiguration('enable_path_smoothing')
    enable_debug = LaunchConfiguration('enable_debug')
    enable_rviz = LaunchConfiguration('enable_rviz')
    
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
            ('/rtabmap/cloud_map', '/rtabmap/cloud_map'),
            ('/robot_pose', '/robot_pose'),
            ('/terrain/voxel_grid', '/terrain/voxel_grid'),
            ('/terrain/slope_map', '/terrain/slope_map'),
            ('/terrain/terrain_info', '/terrain/terrain_info'),
            ('/terrain/visualization', '/terrain/visualization')
        ]
    )
    
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
    
    # RViz node (optional)
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(package_dir, 'config', 'rviz_config.rviz')],
        condition=IfCondition(enable_rviz)
    )
    
    return LaunchDescription([
        config_file_arg,
        enable_visualization_arg,
        enable_path_smoothing_arg,
        enable_debug_arg,
        enable_rviz_arg,
        terrain_analyzer_node,
        path_planner_3d_node,
        rviz_node
    ])
