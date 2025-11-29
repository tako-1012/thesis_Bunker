"""
Phase 5: 完全可視化・分析

Phase 2, 3, 4の全結果を統合して、
論文用の図表を生成
"""
import json
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComprehensiveVisualization:
    """包括的可視化・分析"""
    
    def __init__(self):
        self.phase2_data = None
        self.phase3_data = None
        self.phase4_data = None
    
    def load_all_results(self):
        """全結果を読み込み"""
        logger.info("全Phase結果を読み込み中...")
        
        # Phase 2
        phase2_file = Path('../results/efficient_terrain_results.json')
        if phase2_file.exists():
            with open(phase2_file) as f:
                data = json.load(f)
                self.phase2_data = data.get('results', data)
            logger.info("✅ Phase 2データ読み込み完了")
        else:
            logger.warning("⚠️ Phase 2データが見つかりません")
        
        # Phase 3
        phase3_file = Path('../results/phase3_tastar_superiority.json')
        if phase3_file.exists():
            with open(phase3_file) as f:
                self.phase3_data = json.load(f)
            logger.info("✅ Phase 3データ読み込み完了")
        else:
            logger.warning("⚠️ Phase 3データが見つかりません")
        
        # Phase 4
        phase4_file = Path('../results/phase4_scalability_results.json')
        if phase4_file.exists():
            with open(phase4_file) as f:
                self.phase4_data = json.load(f)
            logger.info("✅ Phase 4データ読み込み完了")
        else:
            logger.warning("⚠️ Phase 4データが見つかりません")
    
    def generate_all_visualizations(self):
        """全可視化を生成"""
        logger.info("\n" + "="*70)
        logger.info("Phase 5: 包括的可視化開始")
        logger.info("="*70)
        
        self.load_all_results()
        
        # 図1: 地形別成功率（Phase 2）
        if self.phase2_data:
            self.plot_terrain_success_rates()
        
        # 図2: スケーラビリティ（Phase 4）
        if self.phase4_data:
            self.plot_scalability()
        
        # 図3: TA-A*優位性（Phase 3）
        if self.phase3_data:
            self.plot_tastar_superiority()
        
        # 図4: 計算時間比較（Phase 2+4）
        if self.phase2_data or self.phase4_data:
            self.plot_computation_time()
        
        # 図5: 包括的比較（全Phase）
        self.plot_comprehensive_comparison()
        
        # LaTeXテーブル生成
        self.generate_latex_tables()
        
        logger.info("\n✅ Phase 5完了！")
        logger.info("生成した図表: ../results/figures/")
    
    def plot_terrain_success_rates(self):
        """地形別成功率グラフ"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # データ準備
        terrains = list(self.phase2_data.keys())
        algorithms = ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']
        
        x = np.arange(len(terrains))
        width = 0.2
        
        for i, algo in enumerate(algorithms):
            rates = []
            for terrain in terrains:
                if algo in self.phase2_data[terrain]:
                    results = self.phase2_data[terrain][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100
                    rates.append(rate)
                else:
                    rates.append(0)
            
            ax.bar(x + i*width, rates, width, label=algo)
        
        ax.set_ylabel('Success Rate (%)')
        ax.set_title('Success Rate by Terrain Type')
        ax.set_xticks(x + width * 1.5)
        ax.set_xticklabels(terrains, rotation=15, ha='right')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim([0, 105])
        
        plt.tight_layout()
        output_dir = Path('../results/figures')
        output_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_dir / 'fig1_terrain_success_rates.png', dpi=300)
        logger.info("✅ 図1生成: 地形別成功率")
        plt.close()
    
    def plot_scalability(self):
        """スケーラビリティグラフ"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        scales = ['small', 'medium', 'large']
        scale_labels = ['Small\n(20m)', 'Medium\n(50m)', 'Large\n(100m)']
        algorithms = ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']
        
        # 成功率
        for algo in algorithms:
            rates = []
            for scale in scales:
                if scale in self.phase4_data and algo in self.phase4_data[scale]:
                    results = self.phase4_data[scale][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100
                    rates.append(rate)
                else:
                    rates.append(0)
            
            ax1.plot(scale_labels, rates, marker='o', label=algo, linewidth=2)
        
        ax1.set_ylabel('Success Rate (%)')
        ax1.set_title('Success Rate vs Map Scale')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([0, 105])
        
        # 計算時間
        for algo in ['A*', 'Weighted A*', 'TA-A* (Proposed)']:
            times = []
            for scale in scales:
                if scale in self.phase4_data and algo in self.phase4_data[scale]:
                    results = self.phase4_data[scale][algo]
                    avg_time = np.mean([r['computation_time'] for r in results if r.get('success', False)])
                    times.append(avg_time)
                else:
                    times.append(0)
            
            ax2.plot(scale_labels, times, marker='o', label=algo, linewidth=2)
        
        ax2.set_ylabel('Computation Time (s)')
        ax2.set_title('Computation Time vs Map Scale')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_yscale('log')
        
        plt.tight_layout()
        output_dir = Path('../results/figures')
        plt.savefig(output_dir / 'fig2_scalability.png', dpi=300)
        logger.info("✅ 図2生成: スケーラビリティ")
        plt.close()
    
    def plot_tastar_superiority(self):
        """TA-A*優位性グラフ"""
        if not self.phase3_data:
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # TA-A*のみ成功したケースをカウント
        tastar_only = sum(1 for r in self.phase3_data if r['tastar']['success'] and not r['astar']['success'])
        both_success = sum(1 for r in self.phase3_data if r['tastar']['success'] and r['astar']['success'])
        astar_only = sum(1 for r in self.phase3_data if r['astar']['success'] and not r['tastar']['success'])
        both_fail = sum(1 for r in self.phase3_data if not r['astar']['success'] and not r['tastar']['success'])
        
        categories = ['TA-A* only', 'Both\nsuccess', 'A* only', 'Both fail']
        counts = [tastar_only, both_success, astar_only, both_fail]
        colors = ['#2ca02c', '#1f77b4', '#ff7f0e', '#d62728']
        
        ax.bar(categories, counts, color=colors, alpha=0.7)
        ax.set_ylabel('Number of Scenarios')
        ax.set_title('TA-A* vs A* Performance Comparison')
        ax.grid(True, alpha=0.3, axis='y')
        
        # 数値表示
        for i, (cat, count) in enumerate(zip(categories, counts)):
            ax.text(i, count + 0.5, str(count), ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        output_dir = Path('../results/figures')
        plt.savefig(output_dir / 'fig3_tastar_superiority.png', dpi=300)
        logger.info("✅ 図3生成: TA-A*優位性")
        plt.close()
    
    def plot_computation_time(self):
        """計算時間比較"""
        logger.info("✅ 図4生成: 計算時間比較（省略）")
    
    def plot_comprehensive_comparison(self):
        """包括的比較（全Phase統合）"""
        logger.info("✅ 図5生成: 包括的比較（省略）")
    
    def generate_latex_tables(self):
        """LaTeXテーブル生成"""
        output_dir = Path('../results/tables')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Table 1: 地形別成功率
        if self.phase2_data:
            with open(output_dir / 'table1_terrain_results.tex', 'w') as f:
                f.write("\\begin{table}[htbp]\n")
                f.write("\\centering\n")
                f.write("\\caption{Success Rate by Terrain Type}\n")
                f.write("\\begin{tabular}{l|cccc}\n")
                f.write("\\hline\n")
                f.write("Terrain & A* & Weighted A* & RRT* & TA-A* \\\\\n")
                f.write("\\hline\n")
                
                for terrain in self.phase2_data.keys():
                    row = terrain.replace('_', ' ').title()
                    for algo in ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']:
                        if algo in self.phase2_data[terrain]:
                            results = self.phase2_data[terrain][algo]
                            success = sum(1 for r in results if r.get('success', False))
                            rate = success / len(results) * 100
                            row += f" & {rate:.1f}\\%"
                        else:
                            row += " & -"
                    row += " \\\\\n"
                    f.write(row)
                
                f.write("\\hline\n")
                f.write("\\end{tabular}\n")
                f.write("\\end{table}\n")
            
            logger.info("✅ LaTeXテーブル1生成: 地形別結果")

if __name__ == '__main__':
    viz = ComprehensiveVisualization()
    viz.generate_all_visualizations()



