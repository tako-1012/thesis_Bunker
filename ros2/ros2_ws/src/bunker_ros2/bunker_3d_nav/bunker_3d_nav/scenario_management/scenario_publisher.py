#!/usr/bin/env python3
"""
scenario_publisher.py
シナリオデータをROS2にパブリッシュするノード
"""

import rclpy
from rclpy.node import Node
import json
import sys
from pathlib import Path as FilePath

# ROS2メッセージのインポート
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from std_msgs.msg import Int32, String

class ScenarioPublisher(Node):
    def __init__(self):
        super().__init__('scenario_publisher')
        
        # パブリッシャー
        self.scenario_id_pub = self.create_publisher(Int32, '/scenario_id', 10)
        self.scenario_info_pub = self.create_publisher(String, '/scenario_info', 10)
        self.path_pub = self.create_publisher(Path, '/path_3d', 10)
        
        # シナリオデータ読み込み - pathlib.Path() コンストラクタ引数修正
        _file_path = FilePath(__file__)
        _repo_root = _file_path.parent.parent.parent.parent.parent.parent.parent
        self.scenarios_path = _repo_root / 'scenarios'
        if not self.scenarios_path.exists():
            # Fallback: ワークスペースベース
            self.scenarios_path = FilePath('/home/hayashi/thesis_work/scenarios')
        self.scenarios = self.load_scenarios()
        
        self.get_logger().info(f'Scenario Publisher started with {len(self.scenarios)} scenarios from {self.scenarios_path}')
    
    def load_scenarios(self):
        """シナリオファイルを読み込み"""
        scenarios = []
        
        if not self.scenarios_path.exists():
            self.get_logger().error(f'Scenarios path not found: {self.scenarios_path}')
            return scenarios
        
        for scenario_file in self.scenarios_path.glob('scenario_*.json'):
            try:
                with open(scenario_file, 'r') as f:
                    scenario_data = json.load(f)
                    scenarios.append(scenario_data)
            except Exception as e:
                self.get_logger().error(f'Error loading {scenario_file}: {e}')
        
        return scenarios
    
    def publish_scenario(self, scenario_id):
        """指定されたシナリオをパブリッシュ"""
        if scenario_id >= len(self.scenarios):
            self.get_logger().error(f'Scenario {scenario_id} not found')
            return
        
        scenario = self.scenarios[scenario_id]
        
        # シナリオIDをパブリッシュ
        scenario_id_msg = Int32()
        scenario_id_msg.data = scenario_id
        self.scenario_id_pub.publish(scenario_id_msg)
        
        # シナリオ情報をパブリッシュ
        scenario_info_msg = String()
        scenario_info_msg.data = json.dumps(scenario)
        self.scenario_info_pub.publish(scenario_info_msg)
        
        # ダミー経路を生成・パブリッシュ
        path_msg = self.generate_dummy_path(scenario)
        self.path_pub.publish(path_msg)
        
        self.get_logger().info(f'Published scenario {scenario_id}')
    
    def generate_dummy_path(self, scenario):
        """ダミー経路を生成"""
        path_msg = Path()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = 'map'
        
        # スタート・ゴール位置を取得
        start_pos = scenario.get('start_position', [0.0, 0.0, 0.0])
        goal_pos = scenario.get('goal_position', [5.0, 5.0, 1.0])
        
        # 経路ポイントを生成
        num_points = 20
        for i in range(num_points + 1):
            t = i / num_points
            
            pose = PoseStamped()
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.header.frame_id = 'map'
            
            # 線形補間
            pose.pose.position.x = start_pos[0] + (goal_pos[0] - start_pos[0]) * t
            pose.pose.position.y = start_pos[1] + (goal_pos[1] - start_pos[1]) * t
            pose.pose.position.z = start_pos[2] + (goal_pos[2] - start_pos[2]) * t
            
            # 簡単な向き設定
            pose.pose.orientation.w = 1.0
            
            path_msg.poses.append(pose)
        
        return path_msg
    
    def publish_all_scenarios(self):
        """全シナリオを順次パブリッシュ"""
        for i in range(len(self.scenarios)):
            self.publish_scenario(i)
            rclpy.spin_once(self, timeout_sec=1.0)

def main():
    rclpy.init()
    node = ScenarioPublisher()
    
    try:
        # コマンドライン引数でシナリオIDを指定
        if len(sys.argv) > 1:
            scenario_id = int(sys.argv[1])
            node.publish_scenario(scenario_id)
        else:
            # デフォルトでシナリオ0をパブリッシュ
            node.publish_scenario(0)
        
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()


