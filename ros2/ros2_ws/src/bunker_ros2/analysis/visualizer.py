"""
実験結果の可視化

全ての図表を生成するクラス
"""
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class Visualizer:
    """実験結果可視化クラス"""
    
    # スタイル設定
    FIGURE_SIZE = (12, 6)
    DPI = 300
    COLORS = {
        'Dijkstra': '#1f77b4',
        'A*': '#ff7f0e',
        'Weighted A*': '#2ca02c',
        'RRT*': '#d62728',
        'TA-A* (Proposed)': '#9467bd'
    }
    
    def __init__(self, output_dir: str = '../results/figures'):
        """
        初期化
        
        Args:
            output_dir: 出力ディレクトリ
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Matplotlibスタイル設定
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except OSError:
            plt.style.use('seaborn-darkgrid')
        
        plt.rcParams['font.size'] = 11
        plt.rcParams['axes.labelsize'] = 12
        plt.rcParams['axes.titlesize'] = 14
        plt.rcParams['legend.fontsize'] = 10
        plt.rcParams['figure.dpi'] = 100
        
        logger.info(f"Visualizer initialized: output_dir={output_dir}")
    
    def plot_terrain_success_rates(self, data: Dict, filename: str = 'fig1_terrain_success_rates.png'):
        """
        地形別成功率グラフ
        
        Args:
            data: Phase 2実験結果
            filename: 出力ファイル名
        """
        fig, ax = plt.subplots(figsize=self.FIGURE_SIZE)
        
        terrains = list(data.keys())
        algorithms = ['Dijkstra', 'A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']
        
        # 地形名を綺麗に
        terrain_labels = [t.replace('_', ' ').title() for t in terrains]
        
        x = np.arange(len(terrains))
        width = 0.15
        
        for i, algo in enumerate(algorithms):
            rates = []
            for terrain in terrains:
                if algo in data[terrain]:
                    results = data[terrain][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100 if results else 0
                    rates.append(rate)
                else:
                    rates.append(0)
            
            ax.bar(x + i*width, rates, width, 
                   label=algo, color=self.COLORS.get(algo, '#999999'))
        
        ax.set_ylabel('Success Rate (%)', fontweight='bold')
        ax.set_title('Success Rate by Terrain Type', fontweight='bold', pad=20)
        ax.set_xticks(x + width * 2)
        ax.set_xticklabels(terrain_labels, rotation=15, ha='right')
        ax.legend(loc='lower left', framealpha=0.9)
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim([0, 105])
        
        # 値を表示
        for i, algo in enumerate(algorithms):
            rates = []
            for terrain in terrains:
                if algo in data[terrain]:
                    results = data[terrain][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100 if results else 0
                    rates.append(rate)
                else:
                    rates.append(0)
            
            for j, rate in enumerate(rates):
                if rate > 0:
                    ax.text(j + i*width, rate + 2, f'{rate:.0f}%',
                           ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.DPI, bbox_inches='tight')
        logger.info(f"✅ 図1生成: {output_path}")
        plt.close()
    
    def plot_scalability(self, data: Dict, filename: str = 'fig2_scalability.png'):
        """
        スケーラビリティグラフ
        
        Args:
            data: Phase 4実験結果
            filename: 出力ファイル名
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        scales = ['small', 'medium', 'large']
        scale_labels = ['Small\n(20m)', 'Medium\n(50m)', 'Large\n(100m)']
        algorithms = ['Dijkstra', 'A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']
        
        # 成功率
        for algo in algorithms:
            rates = []
            for scale in scales:
                if scale in data and algo in data[scale]:
                    results = data[scale][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100 if results else 0
                    rates.append(rate)
                else:
                    rates.append(0)
            
            ax1.plot(scale_labels, rates, marker='o', label=algo,
                    linewidth=2.5, markersize=8,
                    color=self.COLORS.get(algo, '#999999'))
        
        ax1.set_ylabel('Success Rate (%)', fontweight='bold')
        ax1.set_title('Success Rate vs Map Scale', fontweight='bold', pad=20)
        ax1.legend(loc='lower left', framealpha=0.9)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([0, 105])
        
        # 計算時間
        for algo in ['A*', 'Weighted A*', 'TA-A* (Proposed)']:
            times = []
            for scale in scales:
                if scale in data and algo in data[scale]:
                    results = data[scale][algo]
                    success_results = [r for r in results if r.get('success', False)]
                    avg_time = np.mean([r['computation_time'] for r in success_results]) if success_results else 0
                    times.append(avg_time)
                else:
                    times.append(0)
            
            ax2.plot(scale_labels, times, marker='o', label=algo,
                    linewidth=2.5, markersize=8,
                    color=self.COLORS.get(algo, '#999999'))
        
        ax2.set_ylabel('Computation Time (s)', fontweight='bold')
        ax2.set_title('Computation Time vs Map Scale', fontweight='bold', pad=20)
        ax2.legend(loc='upper left', framealpha=0.9)
        ax2.grid(True, alpha=0.3)
        ax2.set_yscale('log')
        
        plt.tight_layout()
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.DPI, bbox_inches='tight')
        logger.info(f"✅ 図2生成: {output_path}")
        plt.close()
    
    def plot_tastar_superiority(self, data: List[Dict], filename: str = 'fig3_tastar_superiority.png'):
        """
        TA-A*優位性グラフ
        
        Args:
            data: Phase 3実験結果
            filename: 出力ファイル名
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 成功パターン分類
        tastar_only = sum(1 for r in data if r.get('tastar', {}).get('success', False) 
                         and not r.get('astar', {}).get('success', False))
        both_success = sum(1 for r in data if r.get('tastar', {}).get('success', False) 
                          and r.get('astar', {}).get('success', False))
        astar_only = sum(1 for r in data if r.get('astar', {}).get('success', False) 
                        and not r.get('tastar', {}).get('success', False))
        both_fail = sum(1 for r in data if not r.get('astar', {}).get('success', False) 
                       and not r.get('tastar', {}).get('success', False))
        
        categories = ['TA-A*\nonly', 'Both\nsuccess', 'A*\nonly', 'Both\nfail']
        counts = [tastar_only, both_success, astar_only, both_fail]
        colors = ['#2ca02c', '#1f77b4', '#ff7f0e', '#d62728']
        
        bars = ax1.bar(categories, counts, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
        ax1.set_ylabel('Number of Scenarios', fontweight='bold')
        ax1.set_title('TA-A* vs A* Performance Comparison', fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.3, axis='y')
        
        # 数値表示
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{count}', ha='center', va='bottom', fontweight='bold', fontsize=12)
        
        # 計算時間比較（両方成功したケースのみ）
        both_success_data = [r for r in data 
                            if r.get('tastar', {}).get('success', False) 
                            and r.get('astar', {}).get('success', False)]
        
        if both_success_data:
            astar_times = [r['astar']['time'] for r in both_success_data]
            tastar_times = [r['tastar']['time'] for r in both_success_data]
            
            x_pos = np.arange(len(both_success_data))
            width = 0.35
            
            ax2.bar(x_pos - width/2, astar_times, width, label='A*', 
                   color=self.COLORS['A*'], alpha=0.7)
            ax2.bar(x_pos + width/2, tastar_times, width, label='TA-A*',
                   color=self.COLORS['TA-A* (Proposed)'], alpha=0.7)
            
            ax2.set_ylabel('Computation Time (s)', fontweight='bold')
            ax2.set_xlabel('Scenario ID', fontweight='bold')
            ax2.set_title('Computation Time Comparison (Both Success)', fontweight='bold', pad=20)
            ax2.legend(framealpha=0.9)
            ax2.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.DPI, bbox_inches='tight')
        logger.info(f"✅ 図3生成: {output_path}")
        plt.close()
    
    def plot_comprehensive_comparison(self, phase2_data: Dict, phase4_data: Dict,
                                     filename: str = 'fig4_comprehensive.png'):
        """
        包括的比較（全Phase統合）
        
        Args:
            phase2_data: Phase 2結果
            phase4_data: Phase 4結果
            filename: 出力ファイル名
        """
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
        
        algorithms = ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']
        
        # 1. 地形別成功率（簡易版）
        ax1 = fig.add_subplot(gs[0, 0])
        terrains = list(phase2_data.keys())
        terrain_labels = [t.replace('_', ' ').title()[:15] for t in terrains]
        
        for algo in algorithms:
            rates = []
            for terrain in terrains:
                if algo in phase2_data[terrain]:
                    results = phase2_data[terrain][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100 if results else 0
                    rates.append(rate)
                else:
                    rates.append(0)
            
            ax1.plot(terrain_labels, rates, marker='o', label=algo,
                    linewidth=2, markersize=6, color=self.COLORS.get(algo, '#999999'))
        
        ax1.set_ylabel('Success Rate (%)', fontweight='bold')
        ax1.set_title('A) Terrain Performance', fontweight='bold')
        ax1.legend(loc='lower left', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticklabels(terrain_labels, rotation=30, ha='right', fontsize=9)
        
        # 2. スケーラビリティ（簡易版）
        ax2 = fig.add_subplot(gs[0, 1])
        scales = ['small', 'medium', 'large']
        scale_labels = ['20m', '50m', '100m']
        
        for algo in algorithms:
            rates = []
            for scale in scales:
                if scale in phase4_data and algo in phase4_data[scale]:
                    results = phase4_data[scale][algo]
                    success = sum(1 for r in results if r.get('success', False))
                    rate = success / len(results) * 100 if results else 0
                    rates.append(rate)
                else:
                    rates.append(0)
            
            ax2.plot(scale_labels, rates, marker='o', label=algo,
                    linewidth=2, markersize=6, color=self.COLORS.get(algo, '#999999'))
        
        ax2.set_ylabel('Success Rate (%)', fontweight='bold')
        ax2.set_xlabel('Map Size', fontweight='bold')
        ax2.set_title('B) Scalability', fontweight='bold')
        ax2.legend(loc='lower left', fontsize=9)
        ax2.grid(True, alpha=0.3)
        
        # 3. 計算時間比較
        ax3 = fig.add_subplot(gs[1, 0])
        
        all_times = {}
        for algo in algorithms:
            times = []
            # Phase 2から
            for terrain, terrain_data in phase2_data.items():
                if algo in terrain_data:
                    for r in terrain_data[algo]:
                        if r.get('success', False):
                            times.append(r['computation_time'])
            all_times[algo] = times
        
        # ボックスプロット
        box_data = [all_times[algo] for algo in algorithms if all_times[algo]]
        box_labels = [algo for algo in algorithms if all_times[algo]]
        
        bp = ax3.boxplot(box_data, labels=box_labels, patch_artist=True)
        for patch, algo in zip(bp['boxes'], box_labels):
            patch.set_facecolor(self.COLORS.get(algo, '#999999'))
            patch.set_alpha(0.7)
        
        ax3.set_ylabel('Computation Time (s)', fontweight='bold')
        ax3.set_title('C) Computation Time Distribution', fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.set_yscale('log')
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=15, ha='right', fontsize=9)
        
        # 4. 総合評価スコア
        ax4 = fig.add_subplot(gs[1, 1])
        
        # 総合スコア = 成功率 × (1 / log(計算時間))
        scores = {}
        for algo in algorithms:
            success_count = 0
            total_count = 0
            total_time = 0
            
            for terrain, terrain_data in phase2_data.items():
                if algo in terrain_data:
                    for r in terrain_data[algo]:
                        total_count += 1
                        if r.get('success', False):
                            success_count += 1
                            total_time += r['computation_time']
            
            if total_count > 0 and total_time > 0:
                success_rate = success_count / total_count
                avg_time = total_time / success_count if success_count > 0 else 1
                score = success_rate / np.log10(max(avg_time, 1))
                scores[algo] = score
        
        algos = list(scores.keys())
        score_values = list(scores.values())
        colors = [self.COLORS.get(a, '#999999') for a in algos]
        
        bars = ax4.barh(algos, score_values, color=colors, alpha=0.7, edgecolor='black')
        ax4.set_xlabel('Efficiency Score', fontweight='bold')
        ax4.set_title('D) Overall Efficiency', fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='x')
        
        # スコア表示
        for bar, score in zip(bars, score_values):
            width = bar.get_width()
            ax4.text(width + 0.01, bar.get_y() + bar.get_height()/2,
                    f'{score:.3f}', ha='left', va='center', fontweight='bold')
        
        plt.tight_layout()
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.DPI, bbox_inches='tight')
        logger.info(f"✅ 図4生成: {output_path}")
        plt.close()
    
    def generate_all_figures(self, phase2_data: Dict, phase3_data: List[Dict],
                            phase4_data: Dict):
        """
        全ての図を一括生成
        
        Args:
            phase2_data: Phase 2結果
            phase3_data: Phase 3結果
            phase4_data: Phase 4結果
        """
        logger.info("全図表を生成中...")
        
        if phase2_data:
            self.plot_terrain_success_rates(phase2_data)
        
        if phase4_data:
            self.plot_scalability(phase4_data)
        
        if phase3_data:
            self.plot_tastar_superiority(phase3_data)
        
        if phase2_data and phase4_data:
            self.plot_comprehensive_comparison(phase2_data, phase4_data)
        
        logger.info(f"✅ 全図表生成完了: {self.output_dir}")



