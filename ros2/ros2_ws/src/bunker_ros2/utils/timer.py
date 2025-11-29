"""
タイマー

実行時間の計測
"""
import time
from typing import Optional

class Timer:
    """タイマークラス"""
    
    def __init__(self, name: str = "Timer"):
        """
        初期化
        
        Args:
            name: タイマー名
        """
        self.name = name
        self.start_time: Optional[float] = None
        self.elapsed: float = 0.0
    
    def start(self):
        """計測開始"""
        self.start_time = time.time()
    
    def stop(self) -> float:
        """
        計測終了
        
        Returns:
            float: 経過時間 [秒]
        """
        if self.start_time is None:
            raise RuntimeError("Timer was not started")
        
        self.elapsed = time.time() - self.start_time
        self.start_time = None
        return self.elapsed
    
    def __enter__(self):
        """コンテキストマネージャー: 開始"""
        self.start()
        return self
    
    def __exit__(self, *args):
        """コンテキストマネージャー: 終了"""
        self.stop()
        print(f"{self.name}: {self.elapsed:.2f}s")



