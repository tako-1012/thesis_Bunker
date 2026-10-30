"""Install the thin ROS node entry points."""

from setuptools import setup

setup(
    name="thesis_bunker_mission",
    version="0.1.0",
    packages=["thesis_bunker_mission"],
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/thesis_bunker_mission"],
        ),
        ("share/thesis_bunker_mission", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "path_follower = thesis_bunker_mission.path_follower:main",
            "webui_bridge = thesis_bunker_mission.webui_bridge:main",
            "online_planner = thesis_bunker_mission.online_planner:main",
        ]
    },
)
