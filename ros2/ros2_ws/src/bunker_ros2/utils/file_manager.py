"""
ファイル管理

結果の保存・読み込み
"""
import json
from pathlib import Path
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class FileManager:
    """ファイル管理クラス"""
    
    @staticmethod
    def save_json(data: Any, filepath: str):
        """
        JSONファイルを保存
        
        Args:
            data: 保存するデータ
            filepath: ファイルパス
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved: {path}")
    
    @staticmethod
    def load_json(filepath: str) -> Dict:
        """
        JSONファイルを読み込み
        
        Args:
            filepath: ファイルパス
        
        Returns:
            Dict: 読み込んだデータ
        """
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Loaded: {path}")
        return data
    
    @staticmethod
    def ensure_dir(dirpath: str):
        """
        ディレクトリが存在することを保証
        
        Args:
            dirpath: ディレクトリパス
        """
        Path(dirpath).mkdir(parents=True, exist_ok=True)



