"""ROS-free checks for the shared-leg LAS tour experiment."""

from itertools import combinations, permutations
import math
from types import SimpleNamespace
import unittest

import numpy as np

from experiments import tour_real_beach as tour
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION
from tapp.directional import plan_leg
from tapp.planners import astar
from tapp.tracking import CornerSlowPursuit
from tapp.traversability import TraversabilityMap


class TourRealBeachTests(unittest.TestCase):
    def test_clustered_goals_are_deterministic_separated_and_reachable(self):
        blocked = np.zeros((160, 160), bool)
        blocked[105, :] = True  # Separate open components.
        blocked[20:30, 12:76] = True
        sc = dict(start=(5, 5), tmap=SimpleNamespace(lethal=blocked, shape=blocked.shape))
        goals, centers = tour.clustered_waypoints(sc, 12, 100)
        self.assertEqual((goals, centers), tour.clustered_waypoints(sc, 12, 100))
        self.assertEqual(len(goals), 12)
        self.assertEqual(len(centers), 3)
        for a, b in combinations([sc['start'], *centers], 2):
            self.assertGreaterEqual(math.dist(a, b)*RESOLUTION, 20.)
        for a, b in combinations(goals, 2):
            self.assertGreaterEqual(math.dist(a, b)*RESOLUTION, 3.)
        for i, goal in enumerate(goals):
            self.assertLessEqual(math.dist(goal, centers[i % 3])*RESOLUTION, 10.)
        for goal in [*centers, *goals]:
            self.assertFalse(blocked[goal])
            self.assertTrue(astar(blocked, sc['start'], goal)['success'])

    def test_time_matches_straight_and_right_angle_controller_speeds(self):
        straight = [(0, 0), (8, 0), (16, 0)]
        corner = [(0, 0), (8, 0), (8, 8)]
        controller = CornerSlowPursuit(np.asarray(corner)*RESOLUTION, v_max=1.)
        fast, _, _ = controller.command([1.5, 0., 0.])
        slow, _, _ = controller.command([2.25, 0., 0.])
        self.assertAlmostEqual(fast, 1.)
        self.assertAlmostEqual(slow, .3)
        self.assertAlmostEqual(tour.leg_seconds(straight), 8.)
        self.assertAlmostEqual(tour.leg_seconds(corner), 6/fast+2/slow)
        self.assertAlmostEqual(tour.leg_seconds([(0, 0)]), 0.)

    def test_time_accounts_for_overlapping_corner_lookahead(self):
        # Two mild bends (x, y vectors 4:0, 4:3, 4:0) with a 1.25 m middle leg.
        path = [(0, 0), (8, 0), (10, 1.5), (18, 1.5)]
        angle = math.atan2(3, 4)
        overlap = 2.-1.25
        one_corner = 2*2.-2*overlap
        distance = 9.25
        expected = (distance-one_corner-overlap + one_corner/math.cos(angle)
                    + overlap/max(.3, math.cos(2*angle)))
        self.assertAlmostEqual(tour.leg_seconds(path), expected)

    def test_all_orders_use_same_008_legs_and_match_brute_force(self):
        x, y = np.indices((18, 18))
        heights = .025*x+.006*np.sin(x+y)
        blocked = np.zeros_like(heights, dtype=bool)
        blocked[8:10, 3:12] = True
        tm = TraversabilityMap(heights, blocked)
        points = [(2, 4), (4, 14), (14, 1), (6, 10), (13, 15)]
        sc = dict(tmap=tm, start=points[0])
        matrix = tour.cost_matrix(sc, points, kappa=tour.KAPPA)
        paths = matrix['paths']
        euclidean = tour.euclid_matrix(points)
        durations = tour.time_matrix(paths, len(points))
        orders, _ = tour.orderings(euclidean, matrix['C'], durations)
        self.assertEqual(tuple(orders), tour.METHODS)
        for (i, j), path in paths.items():
            self.assertFalse(len(path_lethal_cells(path, tm.lethal)))
            if i != j:
                oracle = plan_leg(sc, points[i], points[j], kappa=tour.KAPPA)
                self.assertEqual(path, oracle['path'])
                self.assertEqual(matrix['C'][i, j], oracle['cost_dir'])
            self.assertAlmostEqual(durations[i, j], tour.leg_seconds(path))
        for order in orders.values():
            self.assertEqual(sorted(order), list(range(len(points))))
            self.assertEqual(order[0], 0)
            joined = tour.join_legs(order, paths)
            self.assertEqual(joined[0], joined[-1])
            offset = 0
            for a, b in zip(order, order[1:]+[0]):
                leg = paths[a, b]
                self.assertEqual(joined[offset:offset+len(leg)], leg)
                offset += len(leg)-1
            self.assertEqual(offset, len(joined)-1)
        for name, costs in zip(tour.METHODS[2:], (euclidean, matrix['C'], durations)):
            def exhaustive_sum(order):
                return sum(costs[a, b] for a, b in zip(order, order[1:]+[0]))

            minimum = min(exhaustive_sum([0, *p]) for p in permutations(range(1, len(points))))
            self.assertAlmostEqual(exhaustive_sum(orders[name]), minimum)


if __name__ == '__main__':
    unittest.main(verbosity=2)
