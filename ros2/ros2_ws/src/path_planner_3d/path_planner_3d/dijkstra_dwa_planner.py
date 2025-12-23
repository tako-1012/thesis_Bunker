"""
Dijkstra + Simple DWA の統合ラッパー（プロトタイプ）

このファイルは DijkstraPlanner3D（既存実装）と
`SimpleDWAPlanner` を組み合わせて、Small/Medium/Large 環境で
振る舞いを分岐させる簡易ラッパーを提供します。
"""
import time
import logging
from typing import Tuple, List, Optional, Any

logger = logging.getLogger(__name__)


class DijkstraDWAPlanner:
    """統合プランナー

    - small: Dijkstra のみ
    - medium/large: Dijkstra で global_path を生成し DWA で局所最適化
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.map_size_threshold = self.config.get('map_size_threshold', 300)

        # SimpleDWA は同一パッケージ内に存在する前提だが、安全のため遅延ロード
        self.dwa = None
        self.dijkstra = None

    def _lazy_load_dijkstra(self):
        # 既存の dijkstra_planner_3d をインポート（通常のパッケージ import を試行）
        try:
            from path_planner_3d.dijkstra_planner_3d import DijkstraPlanner3D
            return DijkstraPlanner3D
        except Exception:
            # フォールバック: ソースファイルから直接ロード
            import importlib.machinery, importlib.util
            dp_path = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/dijkstra_planner_3d.py'
            loader = importlib.machinery.SourceFileLoader('dijkstra_planner_3d', dp_path)
            spec = importlib.util.spec_from_loader(loader.name, loader)
            mod = importlib.util.module_from_spec(spec)
            loader.exec_module(mod)
            return mod.DijkstraPlanner3D

    def _lazy_load_dwa(self):
        try:
            from path_planner_3d.simple_dwa_planner import SimpleDWAPlanner
            return SimpleDWAPlanner
        except Exception:
            import importlib.machinery, importlib.util
            path = 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/simple_dwa_planner.py'
            loader = importlib.machinery.SourceFileLoader('simple_dwa_planner', path)
            spec = importlib.util.spec_from_loader(loader.name, loader)
            mod = importlib.util.module_from_spec(spec)
            loader.exec_module(mod)
            return mod.SimpleDWAPlanner

    def _get_map_size(self, terrain_map: Any) -> str:
        try:
            size = float(getattr(terrain_map, 'size', None) or getattr(terrain_map, 'map_size', None))
        except Exception:
            # fallback: try to infer from obstacle_map shape
            try:
                obs = getattr(terrain_map, 'obstacle_map', None)
                if obs is None and isinstance(terrain_map, (list, tuple)):
                    obs = terrain_map[0]
                size = float(obs.shape[0])
            except Exception:
                size = 0.0

        if size <= 200:
            return 'small'
        elif size <= 500:
            return 'medium'
        else:
            return 'large'

    def plan_path(self, start: Tuple[float, float, float],
                  goal: Tuple[float, float, float],
                  terrain_map, timeout: Optional[float] = 60.0):
        """統合経路計画

        戻り値: (final_path, computation_time)
        """
        t0 = time.time()

        # lazy load planners
        if self.dijkstra is None:
            DijkstraPlanner3D = self._lazy_load_dijkstra()
            # config mapping: pass basic args if present
            dcfg = self.config.get('dijkstra', {})
            try:
                self.dijkstra = DijkstraPlanner3D(**dcfg)
            except Exception:
                # try without kwargs
                self.dijkstra = DijkstraPlanner3D()

        if self.dwa is None:
            SimpleDWAPlanner = self._lazy_load_dwa()
            self.dwa = SimpleDWAPlanner(self.config.get('dwa', {}))

        # Step 1: Dijkstra でグローバル経路生成
        try:
            dres = self.dijkstra.plan_path(start, goal, terrain_map, timeout=timeout)
        except TypeError:
            # 一部実装では引数名が異なる可能性があるため柔軟に呼ぶ
            try:
                dres = self.dijkstra.plan_path(start, goal, terrain_map)
            except Exception as e:
                logger.error(f'Dijkstra execution failed: {e}')
                return None, time.time() - t0

        # dres が PlanningResult の場合 path 属性を読む
        global_path = None
        try:
            global_path = getattr(dres, 'path', None) or dres
        except Exception:
            global_path = None

        if not global_path:
            logger.warning('Dijkstra returned no path')
            return None, time.time() - t0

        # Step 2: マップサイズ判定
        map_size = self._get_map_size(terrain_map)

        if map_size == 'small':
            final_path = global_path
        else:
            # DWA による局所最適化
            try:
                final_path, dwa_time = self.dwa.plan_path(start, goal, terrain_map, global_path=global_path, timeout=timeout)
            except TypeError:
                # some signature mismatch
                final_path, dwa_time = self.dwa.plan_path(start, goal, terrain_map, global_path=global_path)

        comp_time = time.time() - t0
        return final_path, comp_time
