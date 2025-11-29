from setuptools import setup, find_packages
from glob import glob
import os

package_name = 'bunker_3d_nav'

# 現状ディレクトリ構造:
# bunker_3d_nav/
#   bunker_3d_nav/ta_star_planner/ta_star_planner_node.py などが配置され重複階層
#   ta_star_planner/ (空 __init__.py のみ) などトップレベルにも存在
# 暫定対応: find_packages で二重階層両方を含めるが、推奨は「ネスト側を正規化」しトップレベルの空ディレクトリを整理すること。
# 次担当者へ: 不要なトップレベル空サブパッケージ(ta_star_planner 等)を削除し、launchから直接 console_scripts を使うよう移行する。

setup(
    name=package_name,
    version='0.0.1',
    # 自動検出: パッケージ配下のサブパッケージをすべて含める
    packages=find_packages(include=['bunker_3d_nav', 'bunker_3d_nav.*']),  # 二重階層を包括
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
            'ta_star_planner_node = bunker_3d_nav.ta_star_planner.ta_star_planner_node:main',
            'unity_visualization_node = bunker_3d_nav.unity_visualization.unity_visualization_node:main',
            'scenario_publisher = bunker_3d_nav.scenario_management.scenario_publisher:main',
        ],
    },
)















