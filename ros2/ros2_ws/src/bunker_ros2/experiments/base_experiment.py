"""
実験管理の基底クラス

全ての実験が継承する抽象基底クラス
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ExperimentResult:
    """実験結果の基本構造"""
    experiment_id: str
    algorithm_name: str
    success: bool
    computation_time: float
    path_length: float
    nodes_explored: int
    error_message: str = ""
    
    # 追加メトリクス
    additional_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_metrics is None:
            self.additional_metrics = {}

class BaseExperiment(ABC):
    """実験の基底クラス"""
    
    def __init__(self, name: str, output_dir: str = "../results"):
        """
        初期化
        
        Args:
            name: 実験名
            output_dir: 出力ディレクトリ
        """
        self.name = name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 統計情報
        self.stats = {
            'experiment_name': name,
            'start_time': None,
            'end_time': None,
            'total_experiments': 0,
            'completed_experiments': 0,
            'failed_experiments': 0,
            'success_rate': 0.0
        }
        
        # 結果格納
        self.results = []
        
        logger.info(f"Experiment '{name}' initialized")
    
    @abstractmethod
    def run_experiment(self) -> None:
        """
        実験実行（抽象メソッド）
        
        各実験で実装する必要がある
        """
        pass
    
    def start_experiment(self) -> None:
        """実験開始"""
        self.stats['start_time'] = time.time()
        logger.info(f"Starting experiment: {self.name}")
        logger.info("="*70)
    
    def end_experiment(self) -> None:
        """実験終了"""
        self.stats['end_time'] = time.time()
        self.stats['success_rate'] = (
            self.stats['completed_experiments'] - self.stats['failed_experiments']
        ) / self.stats['completed_experiments'] * 100 if self.stats['completed_experiments'] > 0 else 0
        
        logger.info("="*70)
        logger.info(f"Experiment '{self.name}' completed")
        logger.info(f"Total experiments: {self.stats['total_experiments']}")
        logger.info(f"Completed: {self.stats['completed_experiments']}")
        logger.info(f"Failed: {self.stats['failed_experiments']}")
        logger.info(f"Success rate: {self.stats['success_rate']:.1f}%")
        logger.info(f"Total time: {(self.stats['end_time'] - self.stats['start_time'])/60:.1f} minutes")
        logger.info("="*70)
    
    def add_result(self, result: ExperimentResult) -> None:
        """
        結果を追加
        
        Args:
            result: 実験結果
        """
        self.results.append(result)
        self.stats['completed_experiments'] += 1
        
        if not result.success:
            self.stats['failed_experiments'] += 1
        
        logger.info(f"Result added: {result.algorithm_name} - "
                   f"{'✅' if result.success else '❌'} "
                   f"({result.computation_time:.2f}s)")
    
    def save_results(self, filename: Optional[str] = None) -> Path:
        """
        結果を保存
        
        Args:
            filename: ファイル名（Noneなら自動生成）
        
        Returns:
            Path: 保存されたファイルのパス
        """
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{self.name.lower().replace(' ', '_')}_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        # 結果データを準備
        output_data = {
            'experiment_info': self.stats,
            'results': [asdict(result) for result in self.results],
            'metadata': {
                'experiment_name': self.name,
                'total_results': len(self.results),
                'generated_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Results saved: {output_path}")
        return output_path
    
    def load_results(self, filename: str) -> Dict:
        """
        結果を読み込み
        
        Args:
            filename: ファイル名
        
        Returns:
            Dict: 読み込まれたデータ
        """
        file_path = self.output_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Results file not found: {file_path}")
        
        with open(file_path) as f:
            data = json.load(f)
        
        logger.info(f"Results loaded: {file_path}")
        return data
    
    def print_summary(self) -> None:
        """結果サマリーを表示"""
        if not self.results:
            logger.warning("No results to summarize")
            return
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Experiment Summary: {self.name}")
        logger.info(f"{'='*70}")
        
        # アルゴリズム別統計
        algo_stats = {}
        for result in self.results:
            algo = result.algorithm_name
            if algo not in algo_stats:
                algo_stats[algo] = {
                    'total': 0,
                    'success': 0,
                    'total_time': 0,
                    'total_length': 0,
                    'total_nodes': 0
                }
            
            stats = algo_stats[algo]
            stats['total'] += 1
            if result.success:
                stats['success'] += 1
                stats['total_time'] += result.computation_time
                stats['total_length'] += result.path_length
                stats['total_nodes'] += result.nodes_explored
        
        # サマリー表示
        for algo, stats in algo_stats.items():
            success_rate = stats['success'] / stats['total'] * 100
            avg_time = stats['total_time'] / stats['success'] if stats['success'] > 0 else 0
            avg_length = stats['total_length'] / stats['success'] if stats['success'] > 0 else 0
            avg_nodes = stats['total_nodes'] / stats['success'] if stats['success'] > 0 else 0
            
            logger.info(f"{algo:20s}: {stats['success']:2d}/{stats['total']:2d} "
                       f"({success_rate:5.1f}%)  "
                       f"Avg time: {avg_time:6.2f}s  "
                       f"Avg length: {avg_length:6.2f}m  "
                       f"Avg nodes: {avg_nodes:8.0f}")
        
        logger.info(f"{'='*70}")



