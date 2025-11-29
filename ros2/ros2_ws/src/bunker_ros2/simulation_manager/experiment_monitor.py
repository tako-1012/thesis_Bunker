"""
実験完了モニター

実験の完了を検知して自動で次のフェーズへ
"""
import time
import json
from pathlib import Path
from datetime import datetime
import sys

class ExperimentMonitor:
    """実験モニタークラス"""
    
    def __init__(self, log_file: str = 'phase2_experiment.log'):
        """初期化"""
        self.log_file = Path(log_file)
        self.results_file = Path('../results/efficient_terrain_results.json')
        self.check_interval = 30  # 30秒ごとにチェック
    
    def monitor_until_complete(self, max_wait_hours: int = 6):
        """
        実験完了まで監視
        
        Args:
            max_wait_hours: 最大待機時間
        """
        print("="*70)
        print("🔍 実験完了モニター開始")
        print("="*70)
        print(f"チェック間隔: {self.check_interval}秒")
        print(f"最大待機時間: {max_wait_hours}時間")
        print()
        
        start_time = time.time()
        max_wait_seconds = max_wait_hours * 3600
        
        last_progress = None
        
        while time.time() - start_time < max_wait_seconds:
            # 進捗チェック
            progress = self._check_progress()
            
            if progress != last_progress:
                self._print_progress(progress)
                last_progress = progress
            
            # 完了チェック
            if self._is_complete():
                print("\n" + "="*70)
                print("🎉 実験完了検知！")
                print("="*70)
                self._print_completion_summary()
                return True
            
            # 待機
            time.sleep(self.check_interval)
        
        print("\n⚠️ 最大待機時間に到達")
        return False
    
    def _check_progress(self) -> dict:
        """進捗をチェック"""
        if not self.results_file.exists():
            return {
                'completed': 0,
                'total': 200,
                'percentage': 0
            }
        
        try:
            with open(self.results_file) as f:
                data = json.load(f)
            
            if 'statistics' in data:
                stats = data['statistics']
                completed = stats.get('completed_experiments', 0)
                total = stats.get('total_experiments', 200)
                
                return {
                    'completed': completed,
                    'total': total,
                    'percentage': completed / total * 100 if total > 0 else 0
                }
        except:
            pass
        
        return {'completed': 0, 'total': 200, 'percentage': 0}
    
    def _is_complete(self) -> bool:
        """完了判定"""
        if not self.results_file.exists():
            return False
        
        try:
            with open(self.results_file) as f:
                data = json.load(f)
            
            if 'statistics' in data:
                stats = data['statistics']
                completed = stats.get('completed_experiments', 0)
                total = stats.get('total_experiments', 200)
                
                # 95%以上完了で完了とみなす
                return completed >= total * 0.95
        except:
            return False
    
    def _print_progress(self, progress: dict):
        """進捗を表示"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        percentage = progress['percentage']
        completed = progress['completed']
        total = progress['total']
        
        # プログレスバー
        bar_length = 50
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"[{timestamp}] [{bar}] {percentage:5.1f}% ({completed}/{total})")
        
        # 推定残り時間
        if completed > 0 and hasattr(self, '_start_time'):
            elapsed = time.time() - self._start_time
            rate = completed / elapsed
            remaining = (total - completed) / rate if rate > 0 else 0
            
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            
            print(f"         推定残り: {hours}時間{minutes}分")
    
    def _print_completion_summary(self):
        """完了サマリーを表示"""
        try:
            with open(self.results_file) as f:
                data = json.load(f)
            
            if 'statistics' in data:
                stats = data['statistics']
                print(f"\n実験統計:")
                print(f"  総実験数: {stats.get('total_experiments', 0)}")
                print(f"  完了: {stats.get('completed_experiments', 0)}")
                print(f"  成功: {stats.get('completed_experiments', 0) - stats.get('failed_experiments', 0)}")
                print(f"  失敗: {stats.get('failed_experiments', 0)}")
            
            if 'results' in data:
                print(f"\n  評価地形数: {len(data['results'])}")
                
                # 各地形の完了状況
                for terrain, results in data['results'].items():
                    print(f"    {terrain}: {len(results)}アルゴリズム")
            
            # 次のステップを表示
            print("\n次のステップ:")
            print("  cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2")
            print("  ./run_ultimate_research_final.sh")
            
        except Exception as e:
            print(f"サマリー取得エラー: {e}")
    
    def trigger_next_phase(self):
        """次のフェーズを自動トリガー"""
        print("\n" + "="*70)
        print("🚀 Phase Q1-Q15を自動実行")
        print("="*70)
        
        import subprocess
        
        script_path = Path('../run_ultimate_research_final.sh')
        
        if script_path.exists():
            print("\n実行中...")
            result = subprocess.run(
                ['bash', str(script_path)],
                capture_output=False,
                text=True
            )
            
            if result.returncode == 0:
                print("\n✅ Phase Q1-Q15完了！")
            else:
                print("\n⚠️ 一部エラーが発生しました")
        else:
            print(f"⚠️ スクリプトが見つかりません: {script_path}")

if __name__ == '__main__':
    monitor = ExperimentMonitor()
    
    # 実験完了まで監視
    completed = monitor.monitor_until_complete(max_wait_hours=6)
    
    if completed:
        # 自動で次のフェーズへ
        response = input("\nPhase Q1-Q15を自動実行しますか？ (y/n): ")
        if response.lower() == 'y':
            monitor.trigger_next_phase()
    else:
        print("\n手動で実験状況を確認してください")


