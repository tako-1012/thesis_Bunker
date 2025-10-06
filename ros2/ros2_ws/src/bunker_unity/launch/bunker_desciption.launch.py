import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
import xacro

def generate_launch_description():
    bunker_unity_path = os.path.join(
        get_package_share_directory('bunker_unity'))

    xacro_file = os.path.join(bunker_unity_path,
                              'urdf',
                              'bunker.urdf.xacro')
    urdf_path = os.path.join(bunker_unity_path, 'urdf', 'bunker.urdf')

    doc = xacro.process_file(xacro_file, mappings={'use_sim' : 'true'})

    robot_desc = doc.toprettyxml(indent='  ')
    f = open(urdf_path, 'w')
    f.write(robot_desc)
    f.close()

    params = {'robot_description': robot_desc}
        
    twist_mux_params_Path=os.path.join(bunker_unity_path, 'config/twist_mux.yaml')

    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params,{'use_sim_time': True}]
    )

    twist_mux= Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            output='screen',
            parameters=[
                twist_mux_params_Path
            ],
            remappings=[
                ('cmd_vel_out', 'cmd_vel_out_unstamped')
            ]
        )

    stamped_velocity_publisher = Node(
        package='bunker_unity',
        executable='stamped_vel_pub',
       remappings=[
            ('cmd_vel_stamped', '/diff_drive_controller/cmd_vel'),
        ],
        parameters=[{'use_sim_time': True}]
    )
    
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', os.path.join(bunker_unity_path, "rviz/unity_sim.rviz")],
        parameters=[{'use_sim_time': True}]
    )

    return LaunchDescription([
        node_robot_state_publisher,
        twist_mux,
        stamped_velocity_publisher,
        rviz_node,
    ])
