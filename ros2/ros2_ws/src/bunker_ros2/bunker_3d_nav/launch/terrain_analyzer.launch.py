from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # パッケージのパス取得
    pkg_dir = get_package_share_directory('bunker_3d_nav')
    config_file = os.path.join(pkg_dir, 'config', 'terrain_params.yaml')
    
    # Launch引数定義
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation clock'
    )
    
    voxel_size_arg = DeclareLaunchArgument(
        'voxel_size',
        default_value='0.2',
        description='Voxel size for terrain analysis'
    )
    
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='Enable debug mode'
    )
    
    # ノード定義
    terrain_analyzer_node = Node(
        package='bunker_3d_nav',
        executable='terrain_analyzer_node',
        name='terrain_analyzer',
        output='screen',
        parameters=[
            config_file,
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'voxel_size': LaunchConfiguration('voxel_size'),
                'debug_mode': LaunchConfiguration('debug')
            }
        ],
        remappings=[
            ('/velodyne_points', '/points'),
            ('/terrain/voxel_grid', '/terrain/voxels')
        ]
    )
    
    # Rviz2ノード（オプション）
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(pkg_dir, 'rviz', 'terrain_analyzer.rviz')],
        condition=launch.conditions.IfCondition(LaunchConfiguration('use_rviz'))
    )
    
    return LaunchDescription([
        use_sim_time_arg,
        voxel_size_arg,
        debug_arg,
        terrain_analyzer_node,
        # rviz_node  # 必要に応じてコメント解除
    ])
