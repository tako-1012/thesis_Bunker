import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
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

    paths = os.path.join(bunker_unity_path,"config/paths.yaml")
    with open(paths, 'r') as file:
        yaml_content = yaml.safe_load(file)
    project_path= yaml_content.get('sim_launcher', {}).get('ros__parameters', {}).get('project_path', '')
        

    robot_controllers = PathJoinSubstitution(
        [
            FindPackageShare("bunker_unity"),
            "config",
            "bunker_control.yaml",
        ]
    )

    #============================================

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
    )
    
    diff_drive_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["diff_drive_controller", "--controller-manager", "/controller_manager"],
    )
    
    control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[params, robot_controllers,{'use_sim_time': True}],
        output={
            "stdout": "screen",
            "stderr": "screen",
        },
    )

    #============================================
    
    return LaunchDescription([
        control_node,
        joint_state_broadcaster_spawner,
        diff_drive_controller_spawner,
        
        
    ])
