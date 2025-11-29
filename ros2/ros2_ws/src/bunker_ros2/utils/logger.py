"""
ロガー設定

統一されたログ管理
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(name: str = 'thesis', 
                level: int = logging.INFO,
                log_file: str = None) -> logging.Logger:
    """
    ロガーを設定
    
    Args:
        name: ロガー名
        level: ログレベル
        log_file: ログファイルパス（Noneならコンソールのみ）
    
    Returns:
        logging.Logger: 設定されたロガー
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 既存のハンドラをクリア
    logger.handlers.clear()
    
    # フォーマット
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラ（オプション）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger



