"""Check the clustered visit rules and reconstruct a recorded 074 case."""

import unittest

from experiments import tour_human_order as human
from experiments import tour_real_beach as beach
from tapp.tour import tour_legs


class HumanOrderTests(unittest.TestCase):
    def test_clusters_are_chosen_from_the_preceding_center_and_stay_together(self):
        centers = [(25, 0), (-55, 0), (60, 0)]
        points = [(0, 0), (28, 0), (-52, 0), (63, 0), (22, 0), (-58, 0), (57, 0)]
        orders = human.human_orders(points, centers, beach.euclid_matrix(points))
        # Center 60 is farther from the base than -55, but is closer to center 25.
        self.assertEqual(orders['human'], [0, 1, 4, 3, 6, 2, 5])
        self.assertEqual(orders['human_nearest'], [0, 4, 1, 6, 3, 2, 5])
        for order in orders.values():
            self.assertEqual(sorted(order), list(range(len(points))))
            self.assertEqual(tour_legs(order)[-1], (order[-1], 0))

    def test_nearest_within_cluster_enters_from_last_waypoint(self):
        centers = [(20, 0), (45, 0), (45, 40)]
        points = [(0, 0), (20, 4), (43, 1), (43, 39), (20, -4), (43, -1), (43, 41)]
        orders = human.human_orders(points, centers, beach.euclid_matrix(points))
        self.assertEqual(orders['human'], [0, 1, 4, 2, 5, 3, 6])
        # The first pair ties from the base. In the second cluster, index 5 is
        # closer to index 4 even though 2 and 5 tie from the previous center.
        self.assertEqual(orders['human_nearest'], [0, 1, 4, 5, 2, 3, 6])


class ArchivedTourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = ('08OB86_00294', 0)
        cls.case = human.rebuild(*cls.key)
        cls.layouts, cls.tours = human.read_074()

    def test_recomputed_matrices_reproduce_all_five_archived_methods(self):
        audit = human.check_074(self.case, self.layouts[self.key], self.tours)
        self.assertEqual(len(audit), 15)
        self.assertEqual({row['method'] for row in audit}, set(beach.METHODS))
        self.assertEqual({row['n_goals'] for row in audit}, set(beach.GOAL_COUNTS))

    def test_numerical_difference_rejects_the_replay(self):
        key = (*self.key, 5, 'nearest')
        altered = self.tours.copy()
        altered[key] = dict(self.tours[key], travel_time_s=str(float(self.tours[key]['travel_time_s'])+1))
        with self.assertRaisesRegex(ValueError, '074 travel_time_s mismatch'):
            human.check_074(self.case, self.layouts[self.key], altered)


if __name__ == '__main__':
    unittest.main(verbosity=2)
