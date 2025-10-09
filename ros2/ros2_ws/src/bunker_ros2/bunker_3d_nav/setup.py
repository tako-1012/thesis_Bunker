from setuptools import setup
from glob import glob
import os

package_name = 'bunker_3d_nav'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'config'), glob('config/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hayashi',
    maintainer_email='hayashi@example.com',
    description='3D Navigation for Bunker Robot',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'terrain_analyzer_node = bunker_3d_nav.terrain_analyzer.terrain_analyzer_node:main',
            'tcp_server_node = bunker_3d_nav.unity_bridge.tcp_server_node:main',
        ],
    },
)
