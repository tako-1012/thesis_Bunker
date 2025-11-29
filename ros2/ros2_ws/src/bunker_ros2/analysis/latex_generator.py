"""
LaTeX生成

論文用のテーブルを生成
"""
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class LaTeXGenerator:
    """LaTeX生成クラス"""
    
    def __init__(self, output_dir: str = '../results/tables'):
        """
        初期化
        
        Args:
            output_dir: 出力ディレクトリ
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LaTeXGenerator initialized: output_dir={output_dir}")
    
    def generate_terrain_results_table(self, data: Dict, 
                                       filename: str = 'table1_terrain_results.tex'):
        """
        地形別結果テーブル
        
        Args:
            data: Phase 2結果
            filename: 出力ファイル名
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            f.write("\\begin{table}[htbp]\n")
            f.write("\\centering\n")
            f.write("\\caption{Success Rate by Terrain Type (\\%)}\n")
            f.write("\\label{tab:terrain_results}\n")
            f.write("\\begin{tabular}{l|cccc}\n")
            f.write("\\hline\n")
            f.write("\\textbf{Terrain} & \\textbf{A*} & \\textbf{W-A*} & \\textbf{RRT*} & \\textbf{TA-A*} \\\\\n")
            f.write("\\hline\n")
            
            for terrain in data.keys():
                # 地形名を綺麗に
                terrain_name = terrain.replace('_', ' ').title()
                row = f"{terrain_name:<25s}"
                
                for algo in ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']:
                    if algo in data[terrain]:
                        results = data[terrain][algo]
                        success = sum(1 for r in results if r.get('success', False))
                        rate = success / len(results) * 100 if results else 0
                        row += f" & {rate:5.1f}"
                    else:
                        row += " & ---"
                
                row += " \\\\\n"
                f.write(row)
            
            f.write("\\hline\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")
        
        logger.info(f"✅ テーブル1生成: {output_path}")
    
    def generate_scalability_table(self, data: Dict,
                                   filename: str = 'table2_scalability.tex'):
        """
        スケーラビリティテーブル
        
        Args:
            data: Phase 4結果
            filename: 出力ファイル名
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            f.write("\\begin{table}[htbp]\n")
            f.write("\\centering\n")
            f.write("\\caption{Success Rate by Map Scale (\\%)}\n")
            f.write("\\label{tab:scalability}\n")
            f.write("\\begin{tabular}{l|cccc}\n")
            f.write("\\hline\n")
            f.write("\\textbf{Scale} & \\textbf{A*} & \\textbf{W-A*} & \\textbf{RRT*} & \\textbf{TA-A*} \\\\\n")
            f.write("\\hline\n")
            
            scale_names = {
                'small': 'Small (20m × 20m)',
                'medium': 'Medium (50m × 50m)',
                'large': 'Large (100m × 100m)'
            }
            
            for scale in ['small', 'medium', 'large']:
                if scale not in data:
                    continue
                
                row = f"{scale_names[scale]:<20s}"
                
                for algo in ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']:
                    if algo in data[scale]:
                        results = data[scale][algo]
                        success = sum(1 for r in results if r.get('success', False))
                        rate = success / len(results) * 100 if results else 0
                        row += f" & {rate:5.1f}"
                    else:
                        row += " & ---"
                
                row += " \\\\\n"
                f.write(row)
            
            f.write("\\hline\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")
        
        logger.info(f"✅ テーブル2生成: {output_path}")
    
    def generate_computation_time_table(self, data: Dict,
                                       filename: str = 'table3_computation_time.tex'):
        """
        計算時間テーブル
        
        Args:
            data: Phase 2結果
            filename: 出力ファイル名
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            f.write("\\begin{table}[htbp]\n")
            f.write("\\centering\n")
            f.write("\\caption{Average Computation Time by Terrain (seconds)}\n")
            f.write("\\label{tab:computation_time}\n")
            f.write("\\begin{tabular}{l|cccc}\n")
            f.write("\\hline\n")
            f.write("\\textbf{Terrain} & \\textbf{A*} & \\textbf{W-A*} & \\textbf{RRT*} & \\textbf{TA-A*} \\\\\n")
            f.write("\\hline\n")
            
            for terrain in data.keys():
                terrain_name = terrain.replace('_', ' ').title()
                row = f"{terrain_name:<25s}"
                
                for algo in ['A*', 'Weighted A*', 'RRT*', 'TA-A* (Proposed)']:
                    if algo in data[terrain]:
                        results = data[terrain][algo]
                        success_results = [r for r in results if r.get('success', False)]
                        if success_results:
                            times = [r['computation_time'] for r in success_results]
                            avg_time = sum(times) / len(times)
                            row += f" & {avg_time:6.2f}"
                        else:
                            row += " & ---"
                    else:
                        row += " & ---"
                
                row += " \\\\\n"
                f.write(row)
            
            f.write("\\hline\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")
        
        logger.info(f"✅ テーブル3生成: {output_path}")
    
    def generate_all_tables(self, phase2_data: Dict, phase4_data: Dict):
        """
        全テーブルを一括生成
        
        Args:
            phase2_data: Phase 2結果
            phase4_data: Phase 4結果
        """
        logger.info("全LaTeXテーブルを生成中...")
        
        if phase2_data:
            self.generate_terrain_results_table(phase2_data)
            self.generate_computation_time_table(phase2_data)
        
        if phase4_data:
            self.generate_scalability_table(phase4_data)
        
        logger.info(f"✅ 全テーブル生成完了: {self.output_dir}")



