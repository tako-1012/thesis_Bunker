"""Time task038 phases in memory without instrumentation in the mapper."""

from collections import defaultdict
import inspect
from pathlib import Path
from textwrap import dedent
from time import perf_counter

import numpy as np

from tapp import pointcloud_map_fine as fine, pointcloud_map_multi as multi
from tests.test_map_speed import benchmark_cases


def instrument(module, cls, markers, samples, clock):
    source = dedent(inspect.getsource(cls.update)).splitlines()
    code = []
    for line in source:
        stage = markers.get(line.strip())
        if stage:
            indent = line[:len(line)-len(line.lstrip())]
            code.append(f'{indent}_mark({stage!r})')
        code.append(line)
    # Explicit super keeps the method usable outside its original class body.
    source = '\n'.join(code).replace('super().update', 'super(PointCloudMapMulti, self).update')

    def mark(stage):
        now = perf_counter()
        samples[stage] += now-clock[module]
        clock[module] = now

    namespace = dict(vars(module), _mark=mark)
    exec(source, namespace)
    cls.update = namespace['update']


def main():
    cpu = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
               if line.startswith('model name'))
    print('CPU:', cpu)
    print('mapper ground sensor points accepted stage median_ms p95_ms max_ms')
    samples, clock = defaultdict(float), {}
    fine_source = inspect.getsource(fine.PointCloudMapFine.update)
    instrument(fine, fine.PointCloudMapFine, {
        'with self._update_lock:': 'fine_registration',
        'if len(cells):': 'copies',
        'new = []': 'prior_lookup_and_grouping',
        'self._add_obstacles(new)': 'history_and_detection',
        'tm = TraversabilityMap(elev, self.raw_obstacle, self.robot, self.weights)': 'fine_inflation',
        'lethal = inflate_steep(tm, self.robot.footprint_radius)': 'traversability',
        'self.version += 1': 'steep_inflation_and_publish',
        "result['update_s'] = time.perf_counter()-began": 'result',
    }, samples, clock)
    update = fine.PointCloudMapFine.update
    if hasattr(fine.PointCloudMapFine, '_fuse_prior'):
        def instrument_phase(method, stage, *, subtract=()):
            original = getattr(fine.PointCloudMapFine, method)

            def measured(self, *args, **kwargs):
                previous = sum(samples[name] for name in subtract)
                start = perf_counter()
                result = original(self, *args, **kwargs)
                samples[stage] += perf_counter()-start-sum(samples[name] for name in subtract)+previous
                return result

            setattr(fine.PointCloudMapFine, method, measured)

        fine.PointCloudMapFine.update = inspect.unwrap(update)
        instrument_phase('_add_obstacles', 'fine_inflation')
        instrument_phase('_publish', 'traversability_and_publish')
        instrument_phase('_fuse_prior', 'history_and_detection',
                         subtract=('fine_inflation', 'traversability_and_publish'))
        instrument_phase('_update_prior', 'fine_binning_and_result',
                         subtract=('history_and_detection', 'fine_inflation', 'traversability_and_publish'))

        # Use the original source for Fine.update, excluding the baseline markers.
        namespace = dict(vars(fine))
        exec(dedent(fine_source), namespace)
        update = namespace['update']

    instrument(multi, multi.PointCloudMapMulti, {
        'with self._fusion_lock:': 'multi_registration',
        'prior = None': 'source_history',
        'result = super().update(world-[0., 0., .8], [0., 0., 0., 0., 0., 0.])': 'source_history',
    } if not hasattr(fine.PointCloudMapFine, '_fuse_prior') else {
        'with self._fusion_lock:': 'multi_registration',
        'prior = None': 'source_history',
    }, samples, clock)

    def timed_fine(self, *args):
        clock[fine] = start = perf_counter()
        accounted = sum(samples.values())
        result = update(self, *args)
        if hasattr(self, '_fuse_prior'):
            samples['fine_registration'] += perf_counter()-start-(sum(samples.values())-accounted)
        return result

    fine.PointCloudMapFine.update = timed_fine

    for cls, ground, sensor, cloud, pose, terrain in benchmark_cases():
        timings = defaultdict(list)
        for run in range(36):
            if run % 6 == 0:
                mapper = cls(terrain, ground_estimate=ground)
            # Variation forces changed heights and repeated detection.
            scan = cloud.copy()
            scan[:, 2] += .012*(run % 6)
            samples.clear()
            clock[multi] = start = perf_counter()
            if cls is multi.PointCloudMapMulti:
                result = mapper.update(scan, pose, sensor=sensor)
            else:
                result = mapper.update(scan, pose)
            samples['total'] = perf_counter()-start
            if cls is multi.PointCloudMapMulti:
                samples['prior_lookup_attribution_and_misc' if hasattr(mapper, '_fuse_prior')
                        else 'attribution_and_misc'] = samples['total'] - sum(
                    sec for stage, sec in samples.items() if stage != 'total')
            for stage, elapsed in samples.items():
                timings[stage].append(elapsed*1000)
        for stage, vals in timings.items():
            print(cls.__name__, ground, sensor, len(cloud), result['accepted_points'], stage,
                  *(f'{v:.3f}' for v in (*np.percentile(vals, [50, 95]), max(vals))), flush=True)


if __name__ == '__main__':
    main()
