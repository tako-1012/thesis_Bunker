#!/usr/bin/env python3
"""
Slope Calculator
Calculates terrain slopes and stability metrics from voxel grid data.
"""

import numpy as np
from typing import Tuple, List, Optional, Dict, Any
import math


class SlopeCalculator:
    """
    Calculates terrain slopes and stability metrics.
    
    This class handles:
    - Slope angle calculation from normal vectors
    - Stability assessment for robot navigation
    - Roll and pitch angle calculations
    - Traversability assessment
    """
    
    def __init__(self, max_slope_angle: float = 30.0, stability_threshold: float = 20.0):
        """
        Initialize slope calculator.
        
        Args:
            max_slope_angle: Maximum traversable slope angle in degrees
            stability_threshold: Stability threshold angle in degrees
        """
        self.max_slope_angle = np.radians(max_slope_angle)
        self.stability_threshold = np.radians(stability_threshold)
        
        self.get_logger().info(f'SlopeCalculator initialized with max_slope={max_slope_angle}°, stability_threshold={stability_threshold}°')
    
    def calculate_slopes(self, voxel_grid: np.ndarray, normals: np.ndarray) -> Dict[str, Any]:
        """
        Calculate slope angles for each voxel.
        
        Args:
            voxel_grid: 3D voxel grid array
            normals: Normal vectors array
            
        Returns:
            Dictionary containing slope information
        """
        try:
            # TODO: Implement slope calculation
            # This is a placeholder implementation
            
            slopes = self._calculate_slope_angles(normals)
            stability_map = self._calculate_stability_map(slopes)
            traversability_map = self._calculate_traversability_map(slopes)
            
            result = {
                'slopes': slopes,
                'stability_map': stability_map,
                'traversability_map': traversability_map,
                'statistics': self._calculate_slope_statistics(slopes)
            }
            
            self.get_logger().debug(f'Calculated slopes for {len(slopes)} points')
            return result
            
        except Exception as e:
            self.get_logger().error(f'Error calculating slopes: {e}')
            return self._create_empty_slope_data()
    
    def _calculate_slope_angles(self, normals: np.ndarray) -> np.ndarray:
        """
        Calculate slope angles from normal vectors.
        
        Args:
            normals: Normal vectors array of shape (N, 3)
            
        Returns:
            Slope angles in degrees
        """
        # TODO: Implement proper slope angle calculation
        # This is a placeholder implementation
        
        slopes = np.zeros(normals.shape[0])
        
        for i, normal in enumerate(normals):
            # Calculate angle between normal and vertical (0, 0, 1)
            vertical = np.array([0, 0, 1])
            
            # Normalize vectors
            normal_norm = normal / np.linalg.norm(normal)
            vertical_norm = vertical / np.linalg.norm(vertical)
            
            # Calculate angle
            dot_product = np.dot(normal_norm, vertical_norm)
            dot_product = np.clip(dot_product, -1.0, 1.0)  # Clamp to avoid numerical errors
            
            angle = np.arccos(dot_product)
            slopes[i] = np.degrees(angle)
        
        return slopes
    
    def _calculate_stability_map(self, slopes: np.ndarray) -> np.ndarray:
        """
        Calculate stability map based on slope angles.
        
        Args:
            slopes: Slope angles in degrees
            
        Returns:
            Stability map (0: stable, 1: unstable)
        """
        # TODO: Implement stability calculation
        # This is a placeholder implementation
        
        stability_map = np.zeros_like(slopes)
        
        for i, slope in enumerate(slopes):
            if slope > np.degrees(self.stability_threshold):
                stability_map[i] = 1  # Unstable
        
        return stability_map
    
    def _calculate_traversability_map(self, slopes: np.ndarray) -> np.ndarray:
        """
        Calculate traversability map based on slope angles.
        
        Args:
            slopes: Slope angles in degrees
            
        Returns:
            Traversability map (0: traversable, 1: not traversable)
        """
        # TODO: Implement traversability calculation
        # This is a placeholder implementation
        
        traversability_map = np.zeros_like(slopes)
        
        for i, slope in enumerate(slopes):
            if slope > np.degrees(self.max_slope_angle):
                traversability_map[i] = 1  # Not traversable
        
        return traversability_map
    
    def _calculate_slope_statistics(self, slopes: np.ndarray) -> Dict[str, float]:
        """
        Calculate slope statistics.
        
        Args:
            slopes: Slope angles in degrees
            
        Returns:
            Dictionary containing slope statistics
        """
        if len(slopes) == 0:
            return {
                'avg_slope': 0.0,
                'max_slope': 0.0,
                'min_slope': 0.0,
                'std_slope': 0.0,
                'traversable_ratio': 1.0
            }
        
        # Filter out invalid slopes
        valid_slopes = slopes[~np.isnan(slopes)]
        
        if len(valid_slopes) == 0:
            return {
                'avg_slope': 0.0,
                'max_slope': 0.0,
                'min_slope': 0.0,
                'std_slope': 0.0,
                'traversable_ratio': 1.0
            }
        
        # Calculate statistics
        avg_slope = np.mean(valid_slopes)
        max_slope = np.max(valid_slopes)
        min_slope = np.min(valid_slopes)
        std_slope = np.std(valid_slopes)
        
        # Calculate traversable ratio
        traversable_count = np.sum(valid_slopes <= np.degrees(self.max_slope_angle))
        traversable_ratio = traversable_count / len(valid_slopes)
        
        return {
            'avg_slope': float(avg_slope),
            'max_slope': float(max_slope),
            'min_slope': float(min_slope),
            'std_slope': float(std_slope),
            'traversable_ratio': float(traversable_ratio)
        }
    
    def calculate_robot_stability(self, robot_pose: np.ndarray, terrain_slopes: np.ndarray) -> Dict[str, float]:
        """
        Calculate robot stability at given pose.
        
        Args:
            robot_pose: Robot pose [x, y, z, roll, pitch, yaw]
            terrain_slopes: Terrain slopes at robot position
            
        Returns:
            Dictionary containing stability metrics
        """
        # TODO: Implement robot stability calculation
        # This is a placeholder implementation
        
        roll = robot_pose[3]
        pitch = robot_pose[4]
        
        # Calculate stability metrics
        roll_stability = self._calculate_roll_stability(roll)
        pitch_stability = self._calculate_pitch_stability(pitch)
        combined_stability = self._calculate_combined_stability(roll, pitch)
        
        return {
            'roll_stability': roll_stability,
            'pitch_stability': pitch_stability,
            'combined_stability': combined_stability,
            'is_stable': combined_stability > 0.5
        }
    
    def _calculate_roll_stability(self, roll: float) -> float:
        """Calculate roll stability score."""
        # TODO: Implement roll stability calculation
        roll_angle = abs(roll)
        if roll_angle < np.degrees(self.stability_threshold):
            return 1.0 - (roll_angle / np.degrees(self.stability_threshold))
        else:
            return 0.0
    
    def _calculate_pitch_stability(self, pitch: float) -> float:
        """Calculate pitch stability score."""
        # TODO: Implement pitch stability calculation
        pitch_angle = abs(pitch)
        if pitch_angle < np.degrees(self.stability_threshold):
            return 1.0 - (pitch_angle / np.degrees(self.stability_threshold))
        else:
            return 0.0
    
    def _calculate_combined_stability(self, roll: float, pitch: float) -> float:
        """Calculate combined stability score."""
        # TODO: Implement combined stability calculation
        roll_stability = self._calculate_roll_stability(roll)
        pitch_stability = self._calculate_pitch_stability(pitch)
        
        # Combined stability is the minimum of roll and pitch stability
        return min(roll_stability, pitch_stability)
    
    def _create_empty_slope_data(self) -> Dict[str, Any]:
        """Create empty slope data for error cases."""
        return {
            'slopes': np.array([]),
            'stability_map': np.array([]),
            'traversability_map': np.array([]),
            'statistics': {
                'avg_slope': 0.0,
                'max_slope': 0.0,
                'min_slope': 0.0,
                'std_slope': 0.0,
                'traversable_ratio': 1.0
            }
        }
    
    def get_logger(self):
        """Get logger instance."""
        # TODO: Implement proper logging
        import logging
        return logging.getLogger(__name__)
