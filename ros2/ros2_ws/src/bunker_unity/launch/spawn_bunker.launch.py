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


    paths = os.path.join(bunker_unity_path,"config/paths.yaml")
    with open(paths, 'r') as file:
        yaml_content = yaml.safe_load(file)
    project_path= yaml_content.get('sim_launcher', {}).get('ros__parameters', {}).get('project_path', '')
        

    unity_spawn_robot = Node(
        package="unity_ros2_scripts",
        executable="spawn_robot",
        parameters=[{'urdf_path': urdf_path,
                    'package_name' : "bunker_unity",
                    'unity_project_path' : project_path,
                    'x' : 0.0,
                    'y' : 0.0,
                    'z' : 0.0,
                    'R' : 0.0,
                    'P' : 0.0,
                    'Y' : 1.57,
                    }],
    )

    
    
    return LaunchDescription([     
        unity_spawn_robot
    ])
