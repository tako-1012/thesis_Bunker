"""Generate a new cylinder-wheel approximation; optional lab mesh is visual-only."""

import math
from pathlib import Path
import xml.etree.ElementTree as ET


def make_model(output, lab_mesh_dir="", mass_kg=150.0):
    sdf = ET.Element("sdf", version="1.9")
    model = ET.SubElement(sdf, "model", name="bunker")

    def node(parent, tag, text=None, **attrs):
        e = ET.SubElement(parent, tag, attrs)
        if text is not None:
            e.text = str(text)
        return e

    node(model, "self_collide", "false")
    body = node(model, "link", name="base_link")
    node(body, "pose", "0 0 0.35 0 0 0")
    inertia = node(body, "inertial")
    node(inertia, "mass", mass_kg)
    tensor = node(inertia, "inertia")
    length, width, height = 1.023, 0.778, 0.410
    for tag, value in dict(
        ixx=mass_kg * (width**2 + height**2) / 12,
        iyy=mass_kg * (length**2 + height**2) / 12,
        izz=mass_kg * (length**2 + width**2) / 12,
        ixy=0,
        ixz=0,
        iyz=0,
    ).items():
        node(tensor, tag, value)
    for tag in ("collision", "visual"):
        item = node(body, tag, name="body_" + tag)
        geo = node(item, "geometry")
        if tag == "visual" and lab_mesh_dir:
            mesh_path = Path(lab_mesh_dir).expanduser().resolve() / "BUNKER.STL"
            if not mesh_path.is_file():
                raise ValueError(f"mesh not found: {mesh_path}")
            mesh = node(geo, "mesh")
            node(mesh, "uri", mesh_path.as_uri())
            node(mesh, "scale", "0.001 0.001 0.001")
        else:
            node(node(geo, "box"), "size", f"{length} {width} {height}")
        if tag == "visual":
            mat = node(item, "material")
            node(mat, "ambient", "0.15 0.28 0.2 1")
            node(mat, "diffuse", "0.2 0.4 0.25 1")
    sensor = node(body, "sensor", name="imu", type="imu")
    node(sensor, "always_on", "true")
    node(sensor, "update_rate", "50")
    node(sensor, "topic", "/imu")
    node(sensor, "imu")
    drive = node(
        model,
        "plugin",
        filename="gz-sim-diff-drive-system",
        name="gz::sim::systems::DiffDrive",
    )
    radius, thickness, wheel_mass = 0.12, 0.08, 1.0
    for side, y in (("left", 0.3495), ("right", -0.3495)):
        for index, x in enumerate((-0.36, -0.12, 0.12, 0.36)):
            name = f"{side}_{index}"
            wheel = node(model, "link", name=name)
            node(wheel, "pose", f"{x} {y} {radius} 0 0 0")
            inertial = node(wheel, "inertial")
            node(inertial, "mass", wheel_mass)
            tensor = node(inertial, "inertia")
            for tag, value in dict(
                ixx=wheel_mass * (3 * radius**2 + thickness**2) / 12,
                iyy=wheel_mass * radius**2 / 2,
                izz=wheel_mass * (3 * radius**2 + thickness**2) / 12,
                ixy=0,
                ixz=0,
                iyz=0,
            ).items():
                node(tensor, tag, value)
            for tag in ("collision", "visual"):
                item = node(wheel, tag, name=name + "_" + tag)
                node(item, "pose", f"0 0 0 {math.pi/2} 0 0")
                cylinder = node(node(item, "geometry"), "cylinder")
                node(cylinder, "radius", radius)
                node(cylinder, "length", thickness)
                if tag == "collision":
                    ode = node(node(node(item, "surface"), "friction"), "ode")
                    node(ode, "mu", "1.0")
                    node(ode, "mu2", "0.1")
                    node(ode, "fdir1", "1 0 0")
            joint = node(model, "joint", name=name + "_joint", type="revolute")
            node(joint, "parent", "base_link")
            node(joint, "child", name)
            axis = node(joint, "axis")
            node(axis, "xyz", "0 1 0")
            node(node(axis, "dynamics"), "damping", "0.05")
            node(drive, side + "_joint", name + "_joint")
    node(drive, "wheel_separation", "0.699")
    node(drive, "wheel_radius", radius)
    node(drive, "topic", "/cmd_vel")
    node(drive, "odom_topic", "/wheel_odom")
    node(drive, "odom_publish_frequency", "20")
    poses = node(
        model,
        "plugin",
        filename="gz-sim-pose-publisher-system",
        name="gz::sim::systems::PosePublisher",
    )
    for tag, value in dict(
        publish_model_pose="true",
        publish_link_pose="false",
        publish_nested_model_pose="false",
        publish_visual_pose="false",
        publish_collision_pose="false",
        publish_sensor_pose="false",
        use_pose_vector_msg="true",
        update_frequency="20",
    ).items():
        node(poses, tag, value)
    ET.indent(sdf)
    Path(output).write_bytes(ET.tostring(sdf, encoding="utf-8", xml_declaration=True))
    return Path(output)
