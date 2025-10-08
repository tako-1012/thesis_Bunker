from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'bunker_3d_nav'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'msg'), glob('msg/*.msg')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Hayashi',
    maintainer_email='hayashi@example.com',
    description='3D Navigation package for Bunker robot in uneven terrain environments',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'terrain_analyzer_node = bunker_3d_nav.terrain_analyzer.terrain_analyzer_node:main',
            'path_planner_3d_node = bunker_3d_nav.path_planner_3d.path_planner_node:main',
        ],
    },
)
