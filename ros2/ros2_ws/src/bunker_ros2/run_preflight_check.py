"""
実行前チェック

Phase Q1-Q15実行前の準備確認
"""
from pathlib import Path
import sys
import json

class PreflightChecker:
    """実行前チェッククラス"""
    
    def __init__(self):
        """初期化"""
        self.checks = []
        self.warnings = []
        self.errors = []
    
    def run_all_checks(self):
        """全チェックを実行"""
        print("="*70)
        print("🔍 Phase Q1-Q15実行前チェック")
        print("="*70)
        
        self._check_phase2_completion()
        self._check_required_files()
        self._check_python_packages()
        self._check_disk_space()
        self._check_directory_structure()
        
        self._print_summary()
        
        return len(self.errors) == 0
    
    def _check_phase2_completion(self):
        """Phase 2完了チェック"""
        print("\n【Phase 2完了チェック】")
        
        results_file = Path('results/efficient_terrain_results.json')
        
        if not results_file.exists():
            self.errors.append("Phase 2結果ファイルが存在しません")
            print("  ❌ Phase 2未完了")
            return
        
        try:
            with open(results_file) as f:
                data = json.load(f)
            
            if 'statistics' in data:
                stats = data['statistics']
                completed = stats.get('completed_experiments', 0)
                total = stats.get('total_experiments', 200)
                
                if completed >= total * 0.95:
                    print(f"  ✅ Phase 2完了 ({completed}/{total})")
                else:
                    self.warnings.append(f"Phase 2が未完了 ({completed}/{total})")
                    print(f"  ⚠️ Phase 2が未完了 ({completed}/{total})")
        except Exception as e:
            self.errors.append(f"Phase 2結果ファイル読み込みエラー: {e}")
            print(f"  ❌ エラー: {e}")
    
    def _check_required_files(self):
        """必要ファイルチェック"""
        print("\n【必要ファイルチェック】")
        
        required_files = [
            'analysis/statistical_tests.py',
            'analysis/advanced_metrics.py',
            'analysis/failure_analyzer.py',
            'analysis/theoretical_proof.py',
            'analysis/error_analysis.py',
            'analysis/novelty_analysis.py',
            'experiments/parameter_sensitivity.py',
            'experiments/ablation_study.py',
            'path_planner_3d/terrain_aware_astar_fast.py',
            'path_planner_3d/ml_path_predictor.py',
            'path_planner_3d/dynamic_replanning.py',
            'benchmarks/create_benchmark_dataset.py',
            'benchmarks/realtime_benchmark.py',
            'run_ultimate_research_final.sh'
        ]
        
        missing = []
        for file in required_files:
            if not Path(file).exists():
                missing.append(file)
        
        if missing:
            self.errors.append(f"{len(missing)}個のファイルが見つかりません")
            print(f"  ❌ 不足ファイル: {len(missing)}個")
            for f in missing[:5]:
                print(f"     - {f}")
        else:
            print(f"  ✅ 全ファイル存在 ({len(required_files)}個)")
    
    def _check_python_packages(self):
        """Pythonパッケージチェック"""
        print("\n【Pythonパッケージチェック】")
        
        required_packages = [
            'numpy',
            'scipy',
            'matplotlib',
            'sklearn'
        ]
        
        missing = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            self.warnings.append(f"不足パッケージ: {', '.join(missing)}")
            print(f"  ⚠️ 不足パッケージ: {', '.join(missing)}")
            print(f"     インストール: pip install {' '.join(missing)}")
        else:
            print(f"  ✅ 全パッケージインストール済み")
    
    def _check_disk_space(self):
        """ディスク容量チェック"""
        print("\n【ディスク容量チェック】")
        
        import shutil
        
        try:
            usage = shutil.disk_usage('.')
            free_gb = usage.free / (1024**3)
            
            if free_gb < 1:
                self.errors.append(f"ディスク容量不足: {free_gb:.1f}GB")
                print(f"  ❌ 容量不足: {free_gb:.1f}GB")
            elif free_gb < 5:
                self.warnings.append(f"ディスク容量少: {free_gb:.1f}GB")
                print(f"  ⚠️ 容量少: {free_gb:.1f}GB")
            else:
                print(f"  ✅ 十分な容量: {free_gb:.1f}GB")
        except Exception as e:
            self.warnings.append(f"容量チェック失敗: {e}")
    
    def _check_directory_structure(self):
        """ディレクトリ構造チェック"""
        print("\n【ディレクトリ構造チェック】")
        
        required_dirs = [
            'path_planner_3d',
            'experiments',
            'analysis',
            'benchmarks',
            '../results',
            '../docs'
        ]
        
        missing = []
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                self.checks.append(f"ディレクトリ作成: {dir_path}")
        
        print(f"  ✅ ディレクトリ構造OK")
    
    def _print_summary(self):
        """サマリー表示"""
        print("\n" + "="*70)
        print("チェック結果サマリー")
        print("="*70)
        
        if self.errors:
            print(f"\n❌ エラー: {len(self.errors)}個")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️ 警告: {len(self.warnings)}個")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ 全チェック合格！")
            print("\nPhase Q1-Q15実行準備完了")
            print("実行コマンド:")
            print("  cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2")
            print("  ./run_ultimate_research_final.sh")
        elif not self.errors:
            print("\n⚠️ 警告はありますが実行可能です")
        else:
            print("\n❌ エラーを修正してください")
        
        print("="*70)

if __name__ == '__main__':
    checker = PreflightChecker()
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)
