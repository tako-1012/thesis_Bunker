"""ROS-free checks for terrain-only matching, geometry and aggregation."""

import unittest

import numpy as np

from experiments import localizability_map as loc
from tapp.visibility import visible_cells


CELL = np.array([70, 70])
RADIUS = 20.


def terrain_xy():
    axis = (np.arange(141)-70)*loc.RESOLUTION
    return np.meshgrid(axis, axis, indexing='ij')


def profile(heights, cell=CELL, **kwargs):
    matcher = loc.HeightMatcher(heights, RADIUS)
    visible = loc.visible_land(matcher.filled, matcher.land, cell, RADIUS)
    costs, overlaps = matcher.profile(cell, visible, (RADIUS,), **kwargs)
    return costs[0], overlaps[0]


class LocalizabilityTests(unittest.TestCase):
    def test_extruded_shoreline_leaves_alongshore_ambiguous(self):
        _, y = terrain_xy()
        heights = 5+.12*y+.8*np.tanh(y/3.)
        costs, _ = profile(heights)
        category, states, _, _, _, weak_axis = loc.assess(costs, RADIUS)
        self.assertEqual((category, states, weak_axis),
                         ('tangent_only', ['ambiguous', 'determined', 'determined'], 'tangent'))

    def test_off_centre_cone_is_determined(self):
        x, y = terrain_xy()
        heights = 30-.55*np.hypot(x, y)
        costs, _ = profile(heights, CELL+[18, 8])
        self.assertEqual(loc.assess(costs, RADIUS)[:2],
                         ('determined', ['determined', 'determined', 'determined']))

    def test_repeated_hill_has_second_minimum(self):
        x, y = terrain_xy()
        heights = 2+np.maximum(0., 1-.65*np.minimum(np.hypot(x, y), np.hypot(x-3., y)))
        matcher = loc.HeightMatcher(heights, RADIUS)
        # Each hill matches the same excerpt. The second hill is outside the excerpt.
        excerpt = np.flatnonzero(np.linalg.norm(matcher.offsets*loc.RESOLUTION, axis=1) <= 1.)
        costs, _ = matcher.profile(CELL, excerpt, (RADIUS,))
        costs = costs[0]
        self.assertEqual(costs[loc.TRIAL_INDEX[(6, 0, 0)]], 0.)
        self.assertGreater(costs[loc.TRIAL_INDEX[(2, 0, 0)]], loc.SIGMA_M**2)
        self.assertEqual(loc.assess(costs, RADIUS)[1][0], 'ambiguous')

    def test_uniform_source_height_offset_does_not_change_result(self):
        x, y = terrain_xy()
        heights = 30-.55*np.hypot(x, y)
        cell = CELL+[18, 8]
        costs, overlaps = profile(heights, cell)
        shifted, shifted_overlaps = profile(heights, cell, source_height_offset_m=1.)
        np.testing.assert_array_equal(overlaps, shifted_overlaps)
        np.testing.assert_allclose(costs, shifted, atol=1e-12, rtol=0)
        before, after = loc.assess(costs, RADIUS), loc.assess(shifted, RADIUS)
        self.assertEqual((before[:2], before[-1]), (after[:2], after[-1]))
        for first, second in zip(before[2:5], after[2:5]):
            np.testing.assert_allclose(first, second, atol=1e-12, rtol=0)

    def test_hessian_includes_mixed_derivatives_in_physical_units(self):
        second = np.array([[2., .25, 0.], [.25, 4., -.5], [0., -.5, 5.]])
        offsets = np.asarray(loc.TRIALS)*[loc.RESOLUTION, loc.RESOLUTION, RADIUS*np.pi/180.]
        costs = .5*np.einsum('ni,ij,nj->n', offsets, second, offsets)
        _, _, hessian, eigenvalues, _, weak_axis = loc.assess(costs, RADIUS)
        np.testing.assert_allclose(hessian, second, atol=1e-12, rtol=0)
        np.testing.assert_allclose(eigenvalues, np.linalg.eigvalsh(second))
        self.assertEqual(weak_axis, 'tangent')

    def test_visibility_agrees_with_existing_ray_model_at_edges(self):
        ix, iy = np.indices((24, 22))
        heights = .4*np.sin(ix)+.3*np.cos(iy)+1
        heights[8:10, :] += 2
        heights[:4, :3] = -1.
        heights[13:16, 5:9] = np.nan
        matcher = loc.HeightMatcher(heights, max_radius=6.)
        for radius in (4., 6.):
            offsets = loc.ray_geometry(radius, heights.shape[1])[0]
            for cell in (np.array([0, 4]), np.array([8, 10]), np.array([23, 21])):
                indices = loc.visible_land(matcher.filled, matcher.land, cell, radius)
                expected = visible_cells(matcher.filled, tuple(cell), radius_m=radius,
                                         sensor_height_m=loc.SENSOR_HEIGHT_M) & matcher.land
                observed = np.zeros(heights.shape, bool)
                observed[tuple((offsets[indices]+cell).T)] = True
                np.testing.assert_array_equal(observed, expected)

    def test_alongshore_gaps_ignore_duplicate_cross_shore_positions(self):
        cells = np.array([[0, 0], [0, 10], [10, 0], [20, 0], [30, 10]])
        classes = np.array(['determined', 'determined', 'determined', 'ambiguous', 'determined'])
        gaps = loc.gap_stats(cells, classes)
        np.testing.assert_array_equal(gaps, [5., 10.])
        row = loc.summary('test', 'test', RADIUS, classes, gaps)
        self.assertEqual((row['gap_median_m'], row['gap_max_m']), (7.5, 10.))


if __name__ == '__main__':
    unittest.main(verbosity=2)
