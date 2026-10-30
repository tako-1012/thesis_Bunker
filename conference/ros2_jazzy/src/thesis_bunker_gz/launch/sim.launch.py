"""Launch one world, a generated mesh-optional model, bridge and mission nodes."""

import os
from pathlib import Path
import sys
import tempfile
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    SetEnvironmentVariable,
    RegisterEventHandler,
    EmitEvent,
)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def default_conference():
    if os.environ.get("THESIS_CONFERENCE_DIR"):
        return os.environ["THESIS_CONFERENCE_DIR"]
    for p in Path(__file__).resolve().parents:
        if (p / "tapp" / "config.py").is_file():
            return str(p)
    return str(Path.cwd().parent)


def launch_nodes(context):
    root = Path(LaunchConfiguration("conference_dir").perform(context)).resolve()
    sys.path.insert(0, str(root))
    from tapp.mapfile import load_map_file
    from tapp.config import Robot
    from thesis_bunker_gz.model import make_model

    stem = LaunchConfiguration("map").perform(context)
    if Path(stem).name != stem:
        raise ValueError("map must be a filename stem")
    map_path = root / "maps" / (stem + ".npz")
    sc = load_map_file(map_path)
    world_key = {
        "flat_test_100m": "flat_test",
        "real_08OB87_-0206_200m_0": "real_08OB87_-0206",
        "real_las_08OB87_-0206_200m_0": "real_las_08OB87_-0206",
        "real_las_08OB87_-0206_200m_0_debris": "real_las_08OB87_-0206_debris",
    }.get(stem, stem)
    world = root / "gazebo_worlds" / world_key / "world.sdf"
    if not world.is_file():
        raise ValueError(
            "worldがありません。data_prep/export_gazebo.pyで "
            + str(world.parent)
            + " に書き出してください"
        )
    folder = Path(tempfile.mkdtemp(prefix="thesis-bunker-"))
    model = make_model(
        folder / "model.sdf",
        LaunchConfiguration("lab_mesh_dir").perform(context),
        Robot().mass_kg,
    )
    import xml.etree.ElementTree as ET

    # Embedding removes the race between Gazebo services and a timed spawn command.
    tree = ET.parse(world)
    bunker = ET.parse(model).getroot().find("model")
    x, y = sc["start_xy"]
    z = float(sc["tmap"].elev[sc["start"]]) + 0.1
    ET.SubElement(bunker, "pose").text = f"{x} {y} {z} 0 0 0"
    tree.getroot().find("world").append(bunker)
    for uri in tree.findall(".//heightmap/uri"):
        uri.text = (world.parent / "heightmap.png").as_uri()
    temporary_world = folder / "world.sdf"
    tree.write(temporary_world, encoding="utf-8", xml_declaration=True)
    share = Path(get_package_share_directory("thesis_bunker_gz"))
    map_id = "file/" + map_path.name
    env = SetEnvironmentVariable(
        "PYTHONPATH", str(root) + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    gz = ExecuteProcess(cmd=["gz", "sim", "-r", str(temporary_world)], output="screen")
    common = {"use_sim_time": True, "map_id": map_id}
    online = LaunchConfiguration("online").perform(context).lower() == "true"
    follower_parameters = [common, {"online": True}] if online else [common]
    actions = [
        env,
        gz,
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            parameters=[{"config_file": str(share / "config" / "bridge.yaml")}],
            output="screen",
        ),
        Node(
            package="thesis_bunker_mission",
            executable="path_follower",
            parameters=follower_parameters,
            output="screen",
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=gz,
                on_exit=[EmitEvent(event=Shutdown(reason="Gazebo終了"))],
            )
        ),
    ]
    if online:
        prior_map = LaunchConfiguration("prior_map").perform(context)
        if (
            prior_map
            and not prior_map.startswith("coarse:")
            and not Path(prior_map).is_absolute()
        ):
            prior_map = str(root / "maps" / prior_map)
        actions.append(
            Node(
                package="thesis_bunker_mission",
                executable="online_planner",
                parameters=[
                    {
                        "use_sim_time": True,
                        "truth_map": str(map_path),
                        "prior_map": prior_map,
                        "sense_radius_m": float(
                            LaunchConfiguration("sense_radius_m").perform(context)
                        ),
                    }
                ],
                output="screen",
            )
        )
    webui = LaunchConfiguration("webui").perform(context)
    if webui:
        actions.append(
            Node(
                package="thesis_bunker_mission",
                executable="webui_bridge",
                parameters=[common, {"webui": webui}],
                output="screen",
            )
        )
    return actions


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("map", default_value="flat_test_100m"),
            DeclareLaunchArgument("lab_mesh_dir", default_value=""),
            DeclareLaunchArgument("webui", default_value=""),
            DeclareLaunchArgument("conference_dir", default_value=default_conference()),
            DeclareLaunchArgument("online", default_value="false"),
            DeclareLaunchArgument("prior_map", default_value=""),
            DeclareLaunchArgument("sense_radius_m", default_value="10.0"),
            OpaqueFunction(function=launch_nodes),
        ]
    )
