"""Exercise plan attribution, slope stencil errors, distance bins and missing-data handling."""

from contextlib import redirect_stdout
import csv
from io import StringIO
from pathlib import Path
import tempfile

import numpy as np

from experiments import false_steep_inspect as inspect
from ros2_jazzy.gz_checks.plan_maps import encode
from tapp.traversability import inflate, slope_deg


def test_plans(root):
    shape = (14, 14)
    truth = np.zeros(shape)
    truth[10:] = .65
    truth_halo = inflate(slope_deg(truth) > 25., .5)
    assert truth_halo[8, 3] and not truth_halo[7, 3]
    folder = root/'plan_maps'
    folder.mkdir()
    for number in range(1, 5):
        steep = np.zeros(shape, bool)
        steep_halo = np.zeros_like(steep)
        obstacle, prior, lethal = (np.zeros_like(steep) for _ in range(3))
        steep[2, :number] = True
        steep_halo[3, 0] = True
        steep[5, 0] = True
        obstacle[5, 0] = True   # Shared attribution, excluded from the primary count.
        obstacle[6, 0] = True   # Obstacle-only, not even an inclusive steep false positive.
        steep_halo[5, 1] = True
        prior[5, 1] = True
        steep_halo[8, 3] = True  # Agreement with the true 0.5 m halo.
        steep_halo[1, 0] = True  # Saved layer can extend outside the planner's lethal map.
        lethal[:] = steep | steep_halo | obstacle | prior
        lethal[1, 0] = False
        (folder/f'plan_{number:06d}.npz').write_bytes(encode(dict(
            steep=steep, steep_halo=steep_halo, obstacle_halo=obstacle, prior_inflated=prior,
            lethal=lethal, sim_time=float(number), version=number)))
    (folder/'incomplete.json').write_text('{}')
    profile, rows = inspect.inspect_plans(folder, truth_halo)
    assert [row['false_steep_only'] for row in rows] == [2, 3, 4, 5]
    assert rows[-1] == dict(plan=4, sim_time=4., version=4, false_steep_only=5,
                            false_steep_inclusive=7, overlaps_obstacle=1, overlaps_prior=1)
    assert (profile['plan_first'], profile['plan_middle'], profile['plan_last'], profile['plan_max']) == (2, 3, 5, 5)
    assert profile['plan_middle_id'] == 2 and profile['plan_incomplete']
    print('1 PASS: actual lethal and steep layers, true halo and independent obstacles; first/middle/last/max')


def test_stencils():
    shape = (13, 13)
    truth = np.zeros(shape)
    estimate = truth.copy()
    tests = [((4, 5), (5, 5), .6), ((8, 5), (7, 5), -.6)]
    for cell, endpoint, value in tests:
        estimate[endpoint] += value
        assert slope_deg(estimate)[cell] > 25 and slope_deg(truth)[cell] == 0.
    seen = np.ones(shape, bool)
    pair = inspect.stencil(estimate, truth, seen, seen, [test[0] for test in tests])['x']
    np.testing.assert_array_equal(pair['high_error_m'], [.6, 0.])
    np.testing.assert_array_equal(pair['low_error_m'], [0., -.6])
    summary = inspect.pair_summary(pair['high_error_m'], pair['low_error_m'], pair['valid'])
    assert summary['high_dominates'] == summary['low_dominates'] == 1
    edge = inspect.stencil(estimate, truth, seen, seen, [(0, 0)])['x']
    assert tuple(int(axis[0]) for axis in edge['high']) == (0, 0)
    assert tuple(int(axis[0]) for axis in edge['low']) == (1, 0)
    rows = list(inspect.cell_details(estimate, truth, seen, seen, (4, 5), points=np.full(shape, 9)))
    assert rows[0]['high_points'] == rows[0]['low_points'] == rows[0]['points'] == 9
    print('2 PASS: signed high/low endpoint errors and central/edge stencil, with optional point counts')


def test_distances():
    expected = ['within_02', 'within_02', 'over_02_within_05', 'over_02_within_05', 'over_05',
                'no_detections', 'unknown']
    distances = np.array([0., .2, .20001, .5, .50001, np.inf, np.nan])
    assert inspect.distance_bins(distances).tolist() == expected
    shape = (8, 8)
    fine = np.zeros(tuple(n*5 for n in shape), bool)
    fine[4, 2] = True
    fine[12, 7] = True
    # Coarse centres use offsets (2,2) and the actual raw detections.
    sampled = inspect.archive.fine_distance(fine)
    assert inspect.distance_bins(sampled)[0, 0] == 'within_02'
    assert inspect.distance_bins(sampled)[2, 0] == 'over_02_within_05'
    assert inspect.distance_bins(sampled)[7, 7] == 'over_05'
    print('3 PASS: fine-cell centres, inclusive 0.2 and 0.5 m, empty and absent obstacle maps')


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def test_missing_and_optional(root):
    trials = root/'runs'/'test_beach'
    stub = trials/'G_r1'
    stub.mkdir(parents=True)
    (stub/'run_conditions.txt').write_text('patch=test_beach condition=G rep=1\n')
    raw = trials/'S_r1'/'physical_1'/'raw'/'test_beach'
    raw.mkdir(parents=True)
    shape = (7, 7)
    z = np.zeros(shape)
    empty = np.zeros(shape, bool)
    seen = ~empty
    np.savez(raw/'evaluation_reference.npz', truth_elev=z, truth_rock=empty, truth_lethal=empty, prior_rock=empty)
    np.savez(raw/'pointcloud_map.npz', elev=z, obstacle=empty, lethal=empty, seen=seen)
    counted = trials/'P_r1'/'physical_1'/'raw'/'test_beach'
    counted.mkdir(parents=True)
    np.savez(counted/'evaluation_reference.npz', truth_elev=z, truth_rock=empty, truth_lethal=empty, prior_rock=empty)
    np.savez(counted/'pointcloud_map.npz', elev=z, obstacle=empty, lethal=empty, seen=seen,
             point_counts=np.full(shape, 9))
    output = root/'out'
    stdout = StringIO()
    with redirect_stdout(stdout):
        inspect.main(['--runs', str(root/'runs'), '--out', str(output), '--cell', '3', '3'])
    log = stdout.getvalue()
    assert 'evaluation_reference.npz missing' in log
    assert 'no saved search maps' in log and 'does not store point_counts' in log
    reasons = read_csv(output/'skipped.csv')
    assert {row['condition'] for row in reasons} == {'G', 'S', 'P'}
    rows = read_csv(output/'features.csv')
    actual = [row for row in rows if row['condition'] == 'S' and row['classification'] == 'true_nonsteep'][0]
    assert actual['cells'] == actual['unknown'] == '49' and not actual['points_median']
    actual = [row for row in rows if row['condition'] == 'P' and row['classification'] == 'true_nonsteep'][0]
    assert float(actual['points_median']) == 9 and actual['point_count_source'] == 'point_counts'
    runs = {row['condition']: row for row in read_csv(output/'runs.csv')}
    assert runs['S']['legacy_final'] == '0' and not runs['S']['plan_first']
    assert not runs['G']['legacy_final'] and not runs['G']['plan_last']
    assert not read_csv(output/'plans.csv')
    assert len(read_csv(output/'cells.csv')) == 4
    print('4 PASS: missing records have explicit skip reasons; independent final evidence and optional counts retained')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        test_plans(root)
        test_stencils()
        test_distances()
        test_missing_and_optional(root)
    print('all task069 false-steep inspection tests passed')
