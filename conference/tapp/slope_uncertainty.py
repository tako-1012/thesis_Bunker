"""Propagate height standard errors through the existing slope stencil."""

import numpy as np

from .config import RESOLUTION

SLOPE_UNCERTAINTY_MODES = ('none', 'soft')
SINGLE_HEIGHT_ERROR_M = .15
LOWER_95_Z = 1.645


def validate_slope_uncertainty(mode, terrain_source, *, map_method='fine'):
    if mode not in SLOPE_UNCERTAINTY_MODES:
        raise ValueError('unknown slope uncertainty mode')
    if mode == 'soft' and (map_method != 'fine' or terrain_source != 'sensor'):
        raise ValueError('--slope-uncertainty soft requires --map fine and --terrain-source sensor')


def ground_standard_errors(z, groups, counts):
    """Sample standard deviation / sqrt(n) for contiguous groups of returns."""
    occupied = counts > 0
    first = np.zeros(len(counts))
    first[occupied] = z[(np.cumsum(counts)-counts)[occupied]]
    z = z - first[groups]
    total = np.bincount(groups, weights=z, minlength=len(counts))
    mean = total / np.maximum(counts, 1)
    residual = z - mean[groups]
    squares = np.bincount(groups, weights=residual**2, minlength=len(counts))
    supported = counts > 1
    error = np.full(len(counts), SINGLE_HEIGHT_ERROR_M)
    error[supported] = np.sqrt(squares[supported] / counts[supported] / (counts[supported]-1))
    return error


def _gradient_variance(variance):
    """Variance of np.gradient along its first axis, including one-sided edges."""
    result = np.empty_like(variance)
    result[1:-1] = (variance[2:] + variance[:-2]) / (2*RESOLUTION)**2
    result[0] = (variance[1] + variance[0]) / RESOLUTION**2
    result[-1] = (variance[-1] + variance[-2]) / RESOLUTION**2
    return result


def slope_standard_error(gx, gy, sigma_h):
    """First-order standard error of hypot(gx, gy), the slope tangent."""
    tangent = np.hypot(gx, gy)
    # Flat cells are below threshold without a confidence decision.
    wx = np.divide(gx, tangent, out=np.zeros_like(gx), where=tangent > 0.)
    wy = np.divide(gy, tangent, out=np.zeros_like(gy), where=tangent > 0.)
    variance = sigma_h**2
    result = wx**2 * _gradient_variance(variance) + wy**2 * _gradient_variance(variance.T).T
    # At each corner the two one-sided differences share the corner height.
    corners = np.ix_([0, -1], [0, -1])
    signs = np.array([[1, -1], [-1, 1]])
    result[corners] += 2 * wx[corners] * wy[corners] * signs * variance[corners] / RESOLUTION**2
    return np.sqrt(np.maximum(result, 0.))


def uncertain_steep(gx, gy, steep, sigma_h, limit_deg):
    lower = np.hypot(gx, gy) - LOWER_95_Z * slope_standard_error(gx, gy, sigma_h)
    return steep & (lower <= np.tan(np.deg2rad(limit_deg)))
