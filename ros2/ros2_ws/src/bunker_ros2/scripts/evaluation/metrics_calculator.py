#!/usr/bin/env python3
"""
Metrics Calculator
Calculates various metrics for 3D path planning evaluation.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import math


class MetricsCalculator:
    """
    Calculates various metrics for 3D path planning evaluation.
    
    This class provides methods for calculating:
    - Path metrics (length, smoothness, efficiency)
    - Terrain metrics (difficulty, traversability)
    - Cost metrics (total cost, component costs)
    - Performance metrics (computation time, success rate)
    """
    
    def __init__(self):
        """Initialize metrics calculator."""
        self.get_logger().info('MetricsCalculator initialized')
    
    def calculate_path_metrics(self, path_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate path-related metrics.
        
        Args:
            path_data: List of path data dictionaries
            
        Returns:
            Dictionary containing path metrics
        """
        if not path_data:
            return {}
        
        try:
            # Extract positions
            positions = [point['position'] for point in path_data]
            
            # Calculate path length
            path_length = self._calculate_path_length(positions)
            
            # Calculate path smoothness
            smoothness = self._calculate_path_smoothness(positions)
            
            # Calculate path efficiency
            efficiency = self._calculate_path_efficiency(positions)
            
            # Calculate path complexity
            complexity = self._calculate_path_complexity(positions)
            
            metrics = {
                'path_length': path_length,
                'smoothness': smoothness,
                'efficiency': efficiency,
                'complexity': complexity,
                'waypoint_count': len(path_data),
                'avg_waypoint_distance': path_length / len(path_data) if len(path_data) > 0 else 0
            }
            
            self.get_logger().debug(f'Calculated path metrics: {metrics}')
            return metrics
            
        except Exception as e:
            self.get_logger().error(f'Error calculating path metrics: {e}')
            return {}
    
    def calculate_terrain_metrics(self, terrain_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate terrain-related metrics.
        
        Args:
            terrain_data: List of terrain data dictionaries
            
        Returns:
            Dictionary containing terrain metrics
        """
        if not terrain_data:
            return {}
        
        try:
            # Extract terrain parameters
            avg_slopes = [data['avg_slope'] for data in terrain_data]
            max_slopes = [data['max_slope'] for data in terrain_data]
            traversable_ratios = [data['traversable_ratio'] for data in terrain_data]
            
            # Calculate terrain difficulty
            difficulty = self._calculate_terrain_difficulty(avg_slopes, max_slopes)
            
            # Calculate traversability
            traversability = self._calculate_traversability(traversable_ratios)
            
            # Calculate terrain complexity
            complexity = self._calculate_terrain_complexity(avg_slopes, max_slopes)
            
            metrics = {
                'avg_slope': np.mean(avg_slopes),
                'max_slope': np.max(max_slopes),
                'min_slope': np.min(avg_slopes),
                'slope_std': np.std(avg_slopes),
                'traversable_ratio': np.mean(traversable_ratios),
                'difficulty': difficulty,
                'traversability': traversability,
                'complexity': complexity
            }
            
            self.get_logger().debug(f'Calculated terrain metrics: {metrics}')
            return metrics
            
        except Exception as e:
            self.get_logger().error(f'Error calculating terrain metrics: {e}')
            return {}
    
    def calculate_cost_metrics(self, cost_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate cost-related metrics.
        
        Args:
            cost_data: List of cost data dictionaries
            
        Returns:
            Dictionary containing cost metrics
        """
        if not cost_data:
            return {}
        
        try:
            # Extract cost components
            total_costs = [data['total_cost'] for data in cost_data]
            distance_costs = [data['distance_cost'] for data in cost_data]
            slope_costs = [data['slope_cost'] for data in cost_data]
            obstacle_costs = [data['obstacle_cost'] for data in cost_data]
            stability_costs = [data['stability_cost'] for data in cost_data]
            
            # Calculate cost statistics
            cost_stats = {
                'total_cost': {
                    'mean': np.mean(total_costs),
                    'std': np.std(total_costs),
                    'min': np.min(total_costs),
                    'max': np.max(total_costs)
                },
                'distance_cost': {
                    'mean': np.mean(distance_costs),
                    'std': np.std(distance_costs)
                },
                'slope_cost': {
                    'mean': np.mean(slope_costs),
                    'std': np.std(slope_costs)
                },
                'obstacle_cost': {
                    'mean': np.mean(obstacle_costs),
                    'std': np.std(obstacle_costs)
                },
                'stability_cost': {
                    'mean': np.mean(stability_costs),
                    'std': np.std(stability_costs)
                }
            }
            
            # Calculate cost efficiency
            efficiency = self._calculate_cost_efficiency(total_costs, distance_costs)
            
            # Calculate cost distribution
            distribution = self._calculate_cost_distribution(
                distance_costs, slope_costs, obstacle_costs, stability_costs
            )
            
            metrics = {
                'cost_stats': cost_stats,
                'efficiency': efficiency,
                'distribution': distribution
            }
            
            self.get_logger().debug(f'Calculated cost metrics: {metrics}')
            return metrics
            
        except Exception as e:
            self.get_logger().error(f'Error calculating cost metrics: {e}')
            return {}
    
    def calculate_performance_metrics(self, path_data: List[Dict[str, Any]], 
                                     terrain_data: List[Dict[str, Any]], 
                                     cost_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate performance-related metrics.
        
        Args:
            path_data: Path data
            terrain_data: Terrain data
            cost_data: Cost data
            
        Returns:
            Dictionary containing performance metrics
        """
        try:
            # Calculate computation time
            computation_time = self._calculate_computation_time(path_data)
            
            # Calculate success rate
            success_rate = self._calculate_success_rate(path_data, cost_data)
            
            # Calculate energy efficiency
            energy_efficiency = self._calculate_energy_efficiency(path_data, cost_data)
            
            # Calculate navigation quality
            navigation_quality = self._calculate_navigation_quality(
                path_data, terrain_data, cost_data
            )
            
            metrics = {
                'computation_time': computation_time,
                'success_rate': success_rate,
                'energy_efficiency': energy_efficiency,
                'navigation_quality': navigation_quality
            }
            
            self.get_logger().debug(f'Calculated performance metrics: {metrics}')
            return metrics
            
        except Exception as e:
            self.get_logger().error(f'Error calculating performance metrics: {e}')
            return {}
    
    def _calculate_path_length(self, positions: List[List[float]]) -> float:
        """Calculate total path length."""
        if len(positions) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(1, len(positions)):
            prev_pos = np.array(positions[i-1])
            curr_pos = np.array(positions[i])
            distance = np.linalg.norm(curr_pos - prev_pos)
            total_length += distance
        
        return total_length
    
    def _calculate_path_smoothness(self, positions: List[List[float]]) -> float:
        """Calculate path smoothness metric."""
        if len(positions) < 3:
            return 0.0
        
        total_curvature = 0.0
        for i in range(1, len(positions) - 1):
            prev_pos = np.array(positions[i-1])
            curr_pos = np.array(positions[i])
            next_pos = np.array(positions[i+1])
            
            # Calculate curvature
            v1 = curr_pos - prev_pos
            v2 = next_pos - curr_pos
            
            v1_norm = np.linalg.norm(v1)
            v2_norm = np.linalg.norm(v2)
            
            if v1_norm > 0 and v2_norm > 0:
                cos_angle = np.dot(v1, v2) / (v1_norm * v2_norm)
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                angle = math.acos(cos_angle)
                total_curvature += angle
        
        return total_curvature / (len(positions) - 2)
    
    def _calculate_path_efficiency(self, positions: List[List[float]]) -> float:
        """Calculate path efficiency (straight-line distance / actual path length)."""
        if len(positions) < 2:
            return 0.0
        
        start_pos = np.array(positions[0])
        end_pos = np.array(positions[-1])
        straight_line_distance = np.linalg.norm(end_pos - start_pos)
        
        actual_path_length = self._calculate_path_length(positions)
        
        if actual_path_length > 0:
            return straight_line_distance / actual_path_length
        else:
            return 0.0
    
    def _calculate_path_complexity(self, positions: List[List[float]]) -> float:
        """Calculate path complexity metric."""
        if len(positions) < 3:
            return 0.0
        
        # Count direction changes
        direction_changes = 0
        for i in range(2, len(positions)):
            prev_dir = np.array(positions[i-1]) - np.array(positions[i-2])
            curr_dir = np.array(positions[i]) - np.array(positions[i-1])
            
            if np.linalg.norm(prev_dir) > 0 and np.linalg.norm(curr_dir) > 0:
                cos_angle = np.dot(prev_dir, curr_dir) / (np.linalg.norm(prev_dir) * np.linalg.norm(curr_dir))
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                angle = math.acos(cos_angle)
                
                if angle > math.pi / 4:  # 45 degrees
                    direction_changes += 1
        
        return direction_changes / len(positions)
    
    def _calculate_terrain_difficulty(self, avg_slopes: List[float], max_slopes: List[float]) -> float:
        """Calculate terrain difficulty score."""
        if not avg_slopes or not max_slopes:
            return 0.0
        
        avg_slope = np.mean(avg_slopes)
        max_slope = np.max(max_slopes)
        
        # Difficulty based on slope (0-100 scale)
        difficulty = (avg_slope * 0.7 + max_slope * 0.3) / 30.0 * 100.0
        return min(difficulty, 100.0)
    
    def _calculate_traversability(self, traversable_ratios: List[float]) -> float:
        """Calculate traversability score."""
        if not traversable_ratios:
            return 0.0
        
        return np.mean(traversable_ratios) * 100.0
    
    def _calculate_terrain_complexity(self, avg_slopes: List[float], max_slopes: List[float]) -> float:
        """Calculate terrain complexity score."""
        if not avg_slopes or not max_slopes:
            return 0.0
        
        slope_variation = np.std(avg_slopes)
        max_slope_variation = np.std(max_slopes)
        
        complexity = (slope_variation + max_slope_variation) / 2.0
        return min(complexity, 100.0)
    
    def _calculate_cost_efficiency(self, total_costs: List[float], distance_costs: List[float]) -> float:
        """Calculate cost efficiency score."""
        if not total_costs or not distance_costs:
            return 0.0
        
        avg_total_cost = np.mean(total_costs)
        avg_distance_cost = np.mean(distance_costs)
        
        if avg_distance_cost > 0:
            efficiency = avg_distance_cost / avg_total_cost
            return efficiency * 100.0
        else:
            return 0.0
    
    def _calculate_cost_distribution(self, distance_costs: List[float], slope_costs: List[float], 
                                   obstacle_costs: List[float], stability_costs: List[float]) -> Dict[str, float]:
        """Calculate cost distribution percentages."""
        if not all([distance_costs, slope_costs, obstacle_costs, stability_costs]):
            return {}
        
        total_distance = np.sum(distance_costs)
        total_slope = np.sum(slope_costs)
        total_obstacle = np.sum(obstacle_costs)
        total_stability = np.sum(stability_costs)
        
        total_cost = total_distance + total_slope + total_obstacle + total_stability
        
        if total_cost > 0:
            return {
                'distance_percentage': (total_distance / total_cost) * 100,
                'slope_percentage': (total_slope / total_cost) * 100,
                'obstacle_percentage': (total_obstacle / total_cost) * 100,
                'stability_percentage': (total_stability / total_cost) * 100
            }
        else:
            return {}
    
    def _calculate_computation_time(self, path_data: List[Dict[str, Any]]) -> float:
        """Calculate computation time."""
        # TODO: Implement computation time calculation
        # This is a placeholder implementation
        
        if not path_data:
            return 0.0
        
        # Placeholder: assume 0.1 seconds per waypoint
        return len(path_data) * 0.1
    
    def _calculate_success_rate(self, path_data: List[Dict[str, Any]], cost_data: List[Dict[str, Any]]) -> float:
        """Calculate success rate."""
        # TODO: Implement success rate calculation
        # This is a placeholder implementation
        
        if not path_data or not cost_data:
            return 0.0
        
        # Placeholder: assume 95% success rate
        return 95.0
    
    def _calculate_energy_efficiency(self, path_data: List[Dict[str, Any]], cost_data: List[Dict[str, Any]]) -> float:
        """Calculate energy efficiency."""
        # TODO: Implement energy efficiency calculation
        # This is a placeholder implementation
        
        if not path_data or not cost_data:
            return 0.0
        
        # Placeholder: assume 80% energy efficiency
        return 80.0
    
    def _calculate_navigation_quality(self, path_data: List[Dict[str, Any]], 
                                     terrain_data: List[Dict[str, Any]], 
                                     cost_data: List[Dict[str, Any]]) -> float:
        """Calculate overall navigation quality."""
        # TODO: Implement navigation quality calculation
        # This is a placeholder implementation
        
        if not all([path_data, terrain_data, cost_data]):
            return 0.0
        
        # Placeholder: assume 85% navigation quality
        return 85.0
    
    def get_logger(self):
        """Get logger instance."""
        # TODO: Implement proper logging
        import logging
        return logging.getLogger(__name__)
