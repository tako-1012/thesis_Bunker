#!/usr/bin/env python3
"""
data_collector.py
シミュレーション結果のデータ収集・整理

機能:
- 結果のロード・集約
- CSV/JSON形式でのエクスポート
- 基本統計の計算
"""

import json
import csv
import numpy as np
from pathlib import Path
from typing import Dict, List
from dataclasses import asdict
from simulation_runner import SimulationResult

class DataCollector:
    """データ収集・整理クラス"""
    
    def __init__(self):
        self.results: List[SimulationResult] = []
    
    def load_results(self, results_path: str = "simulation_manager/results/final_results.json"):
        """結果ファイル読み込み"""
        try:
            with open(results_path, 'r') as f:
                data = json.load(f)
            
            self.results = [SimulationResult(**item) for item in data]
            print(f"📂 {len(self.results)}件の結果を読み込みました")
        except FileNotFoundError:
            print(f"⚠️ ファイルが見つかりません: {results_path}")
            self.results = []
        except Exception as e:
            print(f"❌ エラー: {e}")
            self.results = []
    
    def export_to_csv(self, output_path: str = "simulation_manager/results/results.csv"):
        """CSV形式でエクスポート"""
        if not self.results:
            print("⚠️ データがありません")
            return
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
            writer.writeheader()
            for result in self.results:
                writer.writerow(asdict(result))
        
        print(f"💾 CSV保存完了: {output_file}")
    
    def calculate_basic_stats(self) -> Dict:
        """基本統計計算"""
        if not self.results:
            return {}
        
        successful = [r for r in self.results if r.path_found]
        
        stats = {
            'total_scenarios': len(self.results),
            'successful_scenarios': len(successful),
            'success_rate': len(successful) / len(self.results) * 100 if self.results else 0,
            'avg_computation_time': np.mean([r.computation_time for r in self.results]),
            'std_computation_time': np.std([r.computation_time for r in self.results]),
            'min_computation_time': np.min([r.computation_time for r in self.results]),
            'max_computation_time': np.max([r.computation_time for r in self.results]),
            'avg_path_length': np.mean([r.path_length for r in successful]) if successful else 0,
            'std_path_length': np.std([r.path_length for r in successful]) if successful else 0,
            'avg_waypoints': np.mean([r.num_waypoints for r in successful]) if successful else 0,
            'std_waypoints': np.std([r.num_waypoints for r in successful]) if successful else 0,
        }
        
        return stats
    
    def calculate_difficulty_stats(self) -> Dict:
        """難易度別統計計算"""
        if not self.results:
            return {}
        
        # 難易度別にグループ化
        difficulty_groups = {}
        for result in self.results:
            # シナリオ名から難易度を推定
            if 'easy' in result.scenario_name.lower():
                difficulty = 'easy'
            elif 'hard' in result.scenario_name.lower():
                difficulty = 'hard'
            else:
                difficulty = 'medium'
            
            if difficulty not in difficulty_groups:
                difficulty_groups[difficulty] = []
            difficulty_groups[difficulty].append(result)
        
        # 各難易度の統計計算
        difficulty_stats = {}
        for difficulty, results in difficulty_groups.items():
            successful = [r for r in results if r.path_found]
            
            difficulty_stats[difficulty] = {
                'total': len(results),
                'successful': len(successful),
                'success_rate': len(successful) / len(results) * 100 if results else 0,
                'avg_computation_time': np.mean([r.computation_time for r in results]),
                'avg_path_length': np.mean([r.path_length for r in successful]) if successful else 0,
                'avg_waypoints': np.mean([r.num_waypoints for r in successful]) if successful else 0,
            }
        
        return difficulty_stats
    
    def calculate_terrain_stats(self) -> Dict:
        """地形タイプ別統計計算"""
        if not self.results:
            return {}
        
        # 地形タイプ別にグループ化
        terrain_groups = {}
        for result in self.results:
            # シナリオ名から地形タイプを推定
            terrain_type = 'unknown'
            for terrain in ['flat_terrain', 'gentle_slope', 'steep_slope', 
                          'mixed_terrain', 'obstacle_field', 'narrow_passage', 'complex_3d']:
                if terrain in result.scenario_name.lower():
                    terrain_type = terrain
                    break
            
            if terrain_type not in terrain_groups:
                terrain_groups[terrain_type] = []
            terrain_groups[terrain_type].append(result)
        
        # 各地形タイプの統計計算
        terrain_stats = {}
        for terrain_type, results in terrain_groups.items():
            successful = [r for r in results if r.path_found]
            
            terrain_stats[terrain_type] = {
                'total': len(results),
                'successful': len(successful),
                'success_rate': len(successful) / len(results) * 100 if results else 0,
                'avg_computation_time': np.mean([r.computation_time for r in results]),
                'avg_path_length': np.mean([r.path_length for r in successful]) if successful else 0,
                'avg_waypoints': np.mean([r.num_waypoints for r in successful]) if successful else 0,
            }
        
        return terrain_stats
    
    def print_summary_report(self):
        """サマリーレポート表示"""
        if not self.results:
            print("⚠️ データがありません")
            return
        
        print("\n" + "="*60)
        print("📊 シミュレーション結果サマリー")
        print("="*60)
        
        # 基本統計
        basic_stats = self.calculate_basic_stats()
        print(f"\n📈 基本統計:")
        print(f"  総シナリオ数: {basic_stats['total_scenarios']}")
        print(f"  成功シナリオ数: {basic_stats['successful_scenarios']}")
        print(f"  成功率: {basic_stats['success_rate']:.1f}%")
        print(f"  平均計算時間: {basic_stats['avg_computation_time']:.4f}秒")
        print(f"  計算時間範囲: {basic_stats['min_computation_time']:.4f} - {basic_stats['max_computation_time']:.4f}秒")
        print(f"  平均経路長: {basic_stats['avg_path_length']:.2f}m")
        print(f"  平均ウェイポイント数: {basic_stats['avg_waypoints']:.1f}")
        
        # 難易度別統計
        difficulty_stats = self.calculate_difficulty_stats()
        if difficulty_stats:
            print(f"\n🎯 難易度別統計:")
            for difficulty, stats in difficulty_stats.items():
                print(f"  {difficulty.upper()}:")
                print(f"    成功率: {stats['success_rate']:.1f}% ({stats['successful']}/{stats['total']})")
                print(f"    平均計算時間: {stats['avg_computation_time']:.4f}秒")
                print(f"    平均経路長: {stats['avg_path_length']:.2f}m")
        
        # 地形別統計
        terrain_stats = self.calculate_terrain_stats()
        if terrain_stats:
            print(f"\n🏔️ 地形別統計:")
            for terrain_type, stats in terrain_stats.items():
                print(f"  {terrain_type}:")
                print(f"    成功率: {stats['success_rate']:.1f}% ({stats['successful']}/{stats['total']})")
                print(f"    平均計算時間: {stats['avg_computation_time']:.4f}秒")
                print(f"    平均経路長: {stats['avg_path_length']:.2f}m")
        
        print("\n" + "="*60)
    
    def save_detailed_report(self, output_path: str = "simulation_manager/results/detailed_report.json"):
        """詳細レポート保存"""
        if not self.results:
            print("⚠️ データがありません")
            return
        
        report = {
            'basic_stats': self.calculate_basic_stats(),
            'difficulty_stats': self.calculate_difficulty_stats(),
            'terrain_stats': self.calculate_terrain_stats(),
            'raw_results': [asdict(r) for r in self.results]
        }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"💾 詳細レポート保存完了: {output_file}")

def main():
    """メイン実行"""
    collector = DataCollector()
    collector.load_results()
    
    if collector.results:
        collector.export_to_csv()
        collector.print_summary_report()
        collector.save_detailed_report()
    else:
        print("⚠️ 結果データが見つかりません")

if __name__ == "__main__":
    main()



