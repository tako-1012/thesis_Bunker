#!/usr/bin/env python3
"""
TA* Unity Demo Launch File
TA*経路計画とUnity可視化を統合した起動ファイル
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch.actions import ExecuteProcess
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    """Launch TA* + Unity visualization system"""
    
    # パッケージパス
    pkg_share = FindPackageShare('bunker_3d_nav')
    
    # Launch引数
    voxel_size_arg = DeclareLaunchArgument(
        'voxel_size',
        default_value='0.2',
        description='Voxel size in meters'
    )
    
    grid_size_x_arg = DeclareLaunchArgument(
        'grid_size_x',
        default_value='200',
        description='Grid size X dimension'
    )
    
    grid_size_y_arg = DeclareLaunchArgument(
        'grid_size_y',
        default_value='200',
        description='Grid size Y dimension'
    )
    
    grid_size_z_arg = DeclareLaunchArgument(
        'grid_size_z',
        default_value='50',
        description='Grid size Z dimension'
    )
    
    planning_interval_arg = DeclareLaunchArgument(
        'planning_interval',
        default_value='2.0',
        description='Path planning interval in seconds'
    )
    
    enable_visualization_arg = DeclareLaunchArgument(
        'enable_visualization',
        default_value='true',
        description='Enable RViz visualization markers'
    )
    
    terrain_analysis_radius_arg = DeclareLaunchArgument(
        'terrain_analysis_radius',
        default_value='5',
        description='Terrain analysis radius for TA*'
    )
    
    # 1. Terrain Analyzer Node (オプション: 実地形データがある場合)
    # terrain_analyzer_node = Node(
    #     package='bunker_3d_nav',
    #     executable='terrain_analyzer_node',
    #     name='terrain_analyzer',
    #     output='screen',
    #     parameters=[{
    #         'voxel_size': LaunchConfiguration('voxel_size'),
    #         'publish_frequency': 1.0,
    #         'enable_visualization': LaunchConfiguration('enable_visualization'),
    #     }]
    # )
    
    # 2. TA* Planner Node
    ta_star_planner_node = ExecuteProcess(
        cmd=['python3', '/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/bunker_3d_nav/ta_star_planner/ta_star_planner_node.py'],
        output='screen'
    )

    # TA* Planner parameters are handled via ROS params within the script
    
    # 3. Unity Visualization Bridge Node
    unity_visualization_node = ExecuteProcess(
        cmd=['python3', '/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/bunker_3d_nav/unity_visualization/unity_visualization_node.py'],
        output='screen'
    )
    
    # 4. Scenario Publisher (デモ用: start/goalを送信)
    scenario_publisher_node = ExecuteProcess(
        cmd=['python3', '/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/bunker_3d_nav/scenario_management/scenario_publisher.py'],
        output='screen'
    )
    
    # 5. RViz (オプション)
    rviz_config_file = PathJoinSubstitution([
        pkg_share,
        'config',
        'ta_star_demo.rviz'
    ])
    
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config_file],
        condition=None  # 必要に応じてIfConditionで制御
    )
    
    # 起動順序制御: Unity bridge → TA* planner (2秒後) → scenario publisher (5秒後)
    ta_star_delayed = TimerAction(
        period=2.0,
        actions=[ta_star_planner_node]
    )
    
    scenario_delayed = TimerAction(
        period=5.0,
        actions=[scenario_publisher_node]
    )
    
    return LaunchDescription([
        # 引数
        voxel_size_arg,
        grid_size_x_arg,
        grid_size_y_arg,
        grid_size_z_arg,
        planning_interval_arg,
        enable_visualization_arg,
        terrain_analysis_radius_arg,
        
        # ノード起動
        # terrain_analyzer_node,  # コメントアウト: 実地形データなしの場合
        unity_visualization_node,
        ta_star_delayed,
        scenario_delayed,
        # rviz_node,  # 必要に応じてコメント解除
    ])
