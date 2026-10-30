"""Install launch, bridge configuration and the mesh-free generated model."""

from glob import glob
from setuptools import setup

setup(
    name="thesis_bunker_gz",
    version="0.1.0",
    packages=["thesis_bunker_gz"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/thesis_bunker_gz"]),
        ("share/thesis_bunker_gz", ["package.xml"]),
        ("share/thesis_bunker_gz/launch", glob("launch/*.py")),
        ("share/thesis_bunker_gz/config", glob("config/*.yaml")),
        ("share/thesis_bunker_gz/models/bunker", glob("models/bunker/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
)
