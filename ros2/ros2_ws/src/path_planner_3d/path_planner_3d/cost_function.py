#!/usr/bin/env python3
"""
Cost Function Implementation
Calculates various costs for 3D path planning including slope, obstacle, and stability costs.
"""

import numpy as np
from typing import Dict, Any, Tuple, List
import math


class CostFunction:
    """
    Cost function for 3D path planning.
    
    This class calculates various costs including:
    - Distance cost
    - Slope cost
    - Obstacle proximity cost
    - Stability cost
    """
    
    def __init__(self, weights: Dict[str, float], safety_params: Dict[str, float]):
        """
        Initialize cost function.
        
        Args:
            weights: Dictionary containing weight values for different cost components
            safety_params: Dictionary containing safety parameters
        """
        self.weights = weights
        self.safety_params = safety_params
        
        self.get_logger().info(f'CostFunction initialized with weights: {weights}')
        self.get_logger().info(f'Safety parameters: {safety_params}')
    
    def calculate_total_cost(self, from_pos: Tuple[float, float, float], 
                           to_pos: Tuple[float, float, float],
                           terrain_data: Dict[str, Any]) -> float:
        """
        Calculate total cost for moving from one position to another.
        
        Args:
            from_pos: From position (x, y, z) in meters
            to_pos: To position (x, y, z) in meters
            terrain_data: Dictionary containing terrain information
            
        Returns:
            Total cost value
        """
        try:
            # Calculate individual cost components
            distance_cost = self.calculate_distance_cost(from_pos, to_pos)
            slope_cost = self.calculate_slope_cost(to_pos, terrain_data)
            obstacle_cost = self.calculate_obstacle_cost(to_pos, terrain_data)
            stability_cost = self.calculate_stability_cost(from_pos, to_pos, terrain_data)
            
            # Calculate weighted total cost
            total_cost = (
                self.weights['distance'] * distance_cost +
                self.weights['slope'] * slope_cost +
                self.weights['obstacle'] * obstacle_cost +
                self.weights['stability'] * stability_cost
            )
            
            return total_cost
            
        except Exception as e:
            self.get_logger().error(f'Error calculating total cost: {e}')
            return float('inf')
    
    def calculate_distance_cost(self, from_pos: Tuple[float, float, float], 
                               to_pos: Tuple[float, float, float]) -> float:
        """
        Calculate distance cost between two positions.
        
        Args:
            from_pos: From position (x, y, z)
            to_pos: To position (x, y, z)
            
        Returns:
            Distance cost
        """
        # TODO: Implement distance cost calculation
        # This is a placeholder implementation
        
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dz = to_pos[2] - from_pos[2]
        
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)
        return distance
    
    def calculate_slope_cost(self, position: Tuple[float, float, float], 
                           terrain_data: Dict[str, Any]) -> float:
        """
        Calculate slope cost at a given position.
        
        Args:
            position: Position (x, y, z)
            terrain_data: Terrain data containing slope information
            
        Returns:
            Slope cost
        """
        # TODO: Implement slope cost calculation
        # This is a placeholder implementation
        
        # Get slope at position
        slope_angle = self._get_slope_at_position(position, terrain_data)
        
        if slope_angle is None:
            return 0.0
        
        # Non-linear slope cost function
        if slope_angle < 10:
            return 1.0
        elif slope_angle < 20:
            return 2.0
        elif slope_angle < 30:
            return 5.0
        else:
            return float('inf')  # Impassable
    
    def calculate_obstacle_cost(self, position: Tuple[float, float, float], 
                              terrain_data: Dict[str, Any]) -> float:
        """
        Calculate obstacle proximity cost at a given position.
        
        Args:
            position: Position (x, y, z)
            terrain_data: Terrain data containing obstacle information
            
        Returns:
            Obstacle cost
        """
        # TODO: Implement obstacle cost calculation
        # This is a placeholder implementation
        
        # Get distance to nearest obstacle
        obstacle_distance = self._get_distance_to_obstacle(position, terrain_data)
        
        if obstacle_distance is None:
            return 0.0
        
        min_distance = self.safety_params['min_obstacle_distance']
        
        if obstacle_distance < min_distance:
            return float('inf')  # Too close to obstacle
        else:
            return 1.0 / obstacle_distance  # Inverse distance cost
    
    def calculate_stability_cost(self, from_pos: Tuple[float, float, float], 
                               to_pos: Tuple[float, float, float],
                               terrain_data: Dict[str, Any]) -> float:
        """
        Calculate stability cost for robot movement.
        
        Args:
            from_pos: From position (x, y, z)
            to_pos: To position (x, y, z)
            terrain_data: Terrain data containing stability information
            
        Returns:
            Stability cost
        """
        # TODO: Implement stability cost calculation
        # This is a placeholder implementation
        
        # Calculate roll and pitch angles
        roll, pitch = self._calculate_robot_angles(from_pos, to_pos, terrain_data)
        
        max_roll = self.safety_params['max_roll_angle']
        max_pitch = self.safety_params['max_pitch_angle']
        
        # Calculate stability risk
        roll_risk = max(0, abs(roll) - max_roll)
        pitch_risk = max(0, abs(pitch) - max_pitch)
        
        if roll_risk > 0 or pitch_risk > 0:
            return 10.0 * (roll_risk + pitch_risk)
        else:
            return abs(roll) + abs(pitch)
    
    def _get_slope_at_position(self, position: Tuple[float, float, float], 
                              terrain_data: Dict[str, Any]) -> Optional[float]:
        """
        Get slope angle at a given position.
        
        Args:
            position: Position (x, y, z)
            terrain_data: Terrain data containing slope information
            
        Returns:
            Slope angle in degrees, or None if not available
        """
        # TODO: Implement slope lookup
        # This is a placeholder implementation
        
        # For now, return a random slope for testing
        return np.random.uniform(0, 30)
    
    def _get_distance_to_obstacle(self, position: Tuple[float, float, float], 
                                terrain_data: Dict[str, Any]) -> Optional[float]:
        """
        Get distance to nearest obstacle at a given position.
        
        Args:
            position: Position (x, y, z)
            terrain_data: Terrain data containing obstacle information
            
        Returns:
            Distance to nearest obstacle in meters, or None if not available
        """
        # TODO: Implement obstacle distance calculation
        # This is a placeholder implementation
        
        # For now, return a random distance for testing
        return np.random.uniform(0.5, 5.0)
    
    def _calculate_robot_angles(self, from_pos: Tuple[float, float, float], 
                              to_pos: Tuple[float, float, float],
                              terrain_data: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calculate roll and pitch angles for robot movement.
        
        Args:
            from_pos: From position (x, y, z)
            to_pos: To position (x, y, z)
            terrain_data: Terrain data containing terrain information
            
        Returns:
            Tuple of (roll, pitch) angles in degrees
        """
        # TODO: Implement robot angle calculation
        # This is a placeholder implementation
        
        # Calculate movement vector
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dz = to_pos[2] - from_pos[2]
        
        # Calculate roll and pitch
        roll = math.atan2(dy, dz) * 180 / math.pi
        pitch = math.atan2(-dx, math.sqrt(dy*dy + dz*dz)) * 180 / math.pi
        
        return roll, pitch
    
    def get_cost_breakdown(self, from_pos: Tuple[float, float, float], 
                          to_pos: Tuple[float, float, float],
                          terrain_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Get detailed cost breakdown for analysis.
        
        Args:
            from_pos: From position (x, y, z)
            to_pos: To position (x, y, z)
            terrain_data: Terrain data
            
        Returns:
            Dictionary containing individual cost components
        """
        distance_cost = self.calculate_distance_cost(from_pos, to_pos)
        slope_cost = self.calculate_slope_cost(to_pos, terrain_data)
        obstacle_cost = self.calculate_obstacle_cost(to_pos, terrain_data)
        stability_cost = self.calculate_stability_cost(from_pos, to_pos, terrain_data)
        
        total_cost = (
            self.weights['distance'] * distance_cost +
            self.weights['slope'] * slope_cost +
            self.weights['obstacle'] * obstacle_cost +
            self.weights['stability'] * stability_cost
        )
        
        return {
            'total_cost': total_cost,
            'distance_cost': distance_cost,
            'slope_cost': slope_cost,
            'obstacle_cost': obstacle_cost,
            'stability_cost': stability_cost,
            'weights': self.weights
        }
    
    def get_logger(self):
        """Get logger instance."""
        # TODO: Implement proper logging
        import logging
        return logging.getLogger(__name__)
