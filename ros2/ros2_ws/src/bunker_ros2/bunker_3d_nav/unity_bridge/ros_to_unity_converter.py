#!/usr/bin/env python3
"""
ROS2メッセージをUnity互換JSON形式に変換
"""

import json
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# ROS2メッセージ
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
    from geometry_msgs.msg import Point, Vector3
    from std_msgs.msg import Header
except ImportError:
    # Fallback for development
    TerrainInfo = None
    VoxelGrid3D = None
    Point = None
    Vector3 = None
    Header = None


class RosToUnityConverter:
    """
    ROS2メッセージをUnity互換JSON形式に変換するクラス
    
    機能:
    - TerrainInfo → Unity JSON
    - VoxelGrid3D → Unity JSON
    - データ圧縮・最適化
    - エラーハンドリング
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Unity用設定
        self.max_voxels_for_unity = 100  # Unity送信用の最大ボクセル数
        self.compression_enabled = True  # データ圧縮有効
        self.precision_digits = 2  # 小数点以下桁数
        
        self.logger.info('RosToUnityConverter initialized')
    
    @staticmethod
    def terrain_info_to_json(msg: TerrainInfo) -> str:
        """
        TerrainInfo → Unity JSON
        
        Args:
            msg: TerrainInfoメッセージ
            
        Returns:
            JSON文字列
        """
        try:
            # タイムスタンプ計算
            timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            
            # Unity用データ構造
            data = {
                "message_type": "terrain_info",
                "timestamp": timestamp,
                "frame_id": msg.header.frame_id,
                "statistics": {
                    "avg_slope": round(msg.avg_slope, 2),
                    "max_slope": round(msg.max_slope, 2),
                    "min_slope": round(msg.min_slope, 2),
                    "traversable_ratio": round(msg.traversable_ratio, 3)
                },
                "voxels": {
                    "total": int(msg.total_voxels),
                    "ground": int(msg.ground_voxels),
                    "obstacle": int(msg.obstacle_voxels)
                },
                "risk": {
                    "avg_score": round(msg.avg_risk, 3),
                    "max_score": round(msg.max_risk, 3)
                },
                "cost": {
                    "avg_cost": round(msg.avg_cost, 2),
                    "impassable_ratio": round(msg.impassable_ratio, 3)
                },
                "performance": {
                    "processing_time": round(msg.processing_time, 3),
                    "point_count": int(msg.point_count)
                }
            }
            
            return json.dumps(data, separators=(',', ':'))
            
        except Exception as e:
            logging.error(f'TerrainInfo conversion error: {e}')
            return json.dumps({"error": "conversion_failed", "message": str(e)})
    
    @staticmethod
    def voxel_grid_to_json(msg: VoxelGrid3D, max_samples: int = 100) -> str:
        """
        VoxelGrid3D → Unity JSON（サンプリング版）
        
        Args:
            msg: VoxelGrid3Dメッセージ
            max_samples: 最大サンプル数
            
        Returns:
            JSON文字列
        """
        try:
            # タイムスタンプ計算
            timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            
            # ボクセルデータのサンプリング
            voxel_samples = RosToUnityConverter._sample_voxels(msg, max_samples)
            
            # Unity用データ構造
            data = {
                "message_type": "voxel_grid",
                "timestamp": timestamp,
                "frame_id": msg.header.frame_id,
                "grid_info": {
                    "voxel_size": round(msg.voxel_size, 3),
                    "num_voxels": int(msg.num_voxels),
                    "bounds": {
                        "min": {
                            "x": round(msg.min_bound.x, 2),
                            "y": round(msg.min_bound.y, 2),
                            "z": round(msg.min_bound.z, 2)
                        },
                        "max": {
                            "x": round(msg.max_bound.x, 2),
                            "y": round(msg.max_bound.y, 2),
                            "z": round(msg.max_bound.z, 2)
                        },
                        "size": {
                            "x": round(msg.size_bound.x, 2),
                            "y": round(msg.size_bound.y, 2),
                            "z": round(msg.size_bound.z, 2)
                        }
                    }
                },
                "voxel_samples": voxel_samples,
                "sampling_info": {
                    "total_voxels": int(msg.num_voxels),
                    "sampled_voxels": len(voxel_samples),
                    "sampling_ratio": round(len(voxel_samples) / max(msg.num_voxels, 1), 3)
                }
            }
            
            return json.dumps(data, separators=(',', ':'))
            
        except Exception as e:
            logging.error(f'VoxelGrid3D conversion error: {e}')
            return json.dumps({"error": "conversion_failed", "message": str(e)})
    
    @staticmethod
    def _sample_voxels(msg: VoxelGrid3D, max_samples: int) -> List[Dict[str, Any]]:
        """
        ボクセルデータをサンプリング
        
        Args:
            msg: VoxelGrid3Dメッセージ
            max_samples: 最大サンプル数
            
        Returns:
            サンプリングされたボクセルデータのリスト
        """
        try:
            voxel_samples = []
            
            # データ長の確認
            if len(msg.voxel_indices_x) == 0:
                return voxel_samples
            
            # サンプリング間隔計算
            total_voxels = len(msg.voxel_indices_x)
            if total_voxels <= max_samples:
                step = 1
            else:
                step = total_voxels // max_samples
            
            # サンプリング実行
            for i in range(0, total_voxels, step):
                if len(voxel_samples) >= max_samples:
                    break
                
                # インデックス範囲チェック
                if (i < len(msg.voxel_indices_x) and 
                    i < len(msg.voxel_indices_y) and 
                    i < len(msg.voxel_indices_z) and
                    i < len(msg.voxel_types) and
                    i < len(msg.voxel_slopes) and
                    i < len(msg.voxel_risks) and
                    i < len(msg.voxel_costs)):
                    
                    voxel_data = {
                        "index": i,
                        "position": {
                            "x": int(msg.voxel_indices_x[i]),
                            "y": int(msg.voxel_indices_y[i]),
                            "z": int(msg.voxel_indices_z[i])
                        },
                        "type": int(msg.voxel_types[i]),
                        "slope": round(msg.voxel_slopes[i], 2),
                        "risk": round(msg.voxel_risks[i], 3),
                        "cost": round(msg.voxel_costs[i], 2)
                    }
                    
                    voxel_samples.append(voxel_data)
            
            return voxel_samples
            
        except Exception as e:
            logging.error(f'Voxel sampling error: {e}')
            return []
    
    @staticmethod
    def create_unity_terrain_data(terrain_info: TerrainInfo, voxel_grid: VoxelGrid3D) -> str:
        """
        Unity用の統合地形データを作成
        
        Args:
            terrain_info: TerrainInfoメッセージ
            voxel_grid: VoxelGrid3Dメッセージ
            
        Returns:
            統合されたJSON文字列
        """
        try:
            # タイムスタンプ計算
            timestamp = terrain_info.header.stamp.sec + terrain_info.header.stamp.nanosec * 1e-9
            
            # 統合データ構造
            data = {
                "message_type": "unified_terrain",
                "timestamp": timestamp,
                "frame_id": terrain_info.header.frame_id,
                "terrain_info": {
                    "statistics": {
                        "avg_slope": round(terrain_info.avg_slope, 2),
                        "max_slope": round(terrain_info.max_slope, 2),
                        "traversable_ratio": round(terrain_info.traversable_ratio, 3)
                    },
                    "voxels": {
                        "total": int(terrain_info.total_voxels),
                        "ground": int(terrain_info.ground_voxels),
                        "obstacle": int(terrain_info.obstacle_voxels)
                    },
                    "risk": {
                        "avg_score": round(terrain_info.avg_risk, 3),
                        "max_score": round(terrain_info.max_risk, 3)
                    }
                },
                "voxel_grid": {
                    "voxel_size": round(voxel_grid.voxel_size, 3),
                    "num_voxels": int(voxel_grid.num_voxels),
                    "bounds": {
                        "min": {
                            "x": round(voxel_grid.min_bound.x, 2),
                            "y": round(voxel_grid.min_bound.y, 2),
                            "z": round(voxel_grid.min_bound.z, 2)
                        },
                        "max": {
                            "x": round(voxel_grid.max_bound.x, 2),
                            "y": round(voxel_grid.max_bound.y, 2),
                            "z": round(voxel_grid.max_bound.z, 2)
                        }
                    }
                },
                "unity_metadata": {
                    "version": "1.0",
                    "data_format": "terrain_analysis",
                    "compression": "none",
                    "coordinate_system": "ros_map"
                }
            }
            
            return json.dumps(data, separators=(',', ':'))
            
        except Exception as e:
            logging.error(f'Unified terrain data creation error: {e}')
            return json.dumps({"error": "unified_data_creation_failed", "message": str(e)})
    
    @staticmethod
    def create_status_message(status: str, message: str = "") -> str:
        """
        Unity用のステータスメッセージを作成
        
        Args:
            status: ステータス（"connected", "disconnected", "error", "ready"）
            message: 追加メッセージ
            
        Returns:
            JSON文字列
        """
        data = {
            "message_type": "status",
            "timestamp": datetime.now().timestamp(),
            "status": status,
            "message": message,
            "unity_metadata": {
                "version": "1.0",
                "data_format": "status"
            }
        }
        
        return json.dumps(data, separators=(',', ':'))
    
    def get_conversion_stats(self) -> Dict[str, Any]:
        """
        変換統計情報を取得
        
        Returns:
            統計情報の辞書
        """
        return {
            "max_voxels_for_unity": self.max_voxels_for_unity,
            "compression_enabled": self.compression_enabled,
            "precision_digits": self.precision_digits,
            "supported_message_types": ["terrain_info", "voxel_grid", "unified_terrain", "status"]
        }
