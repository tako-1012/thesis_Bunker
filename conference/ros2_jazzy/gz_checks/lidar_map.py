"""Opt-in mapper selection; the default is the exact task022 class."""

import os
from tapp.pointcloud_map import PointCloudMap
from tapp.distance_clearance import R_SOFT, validate_clearance
from tapp.pointcloud_map_fine import GROUND_ESTIMATES, FINE_CLEARANCE_MODES, STEEP_NEAR_OBSTACLE, TERRAIN_SOURCES


def make_pointcloud_map(*args, map_method='coarse', sensors='legacy', ground_estimate='all_returns', obstacle_reference='prior',
                        obstacle_clearance='centre', terrain_source='sensor', steep_near_obstacle='keep',
                        clearance_soft_m=R_SOFT, **kwargs):
    validate_clearance(obstacle_clearance, clearance_soft_m)
    if steep_near_obstacle not in STEEP_NEAR_OBSTACLE:
        raise ValueError('unknown steep-near-obstacle policy')
    if steep_near_obstacle != 'keep':
        if map_method != 'fine':
            raise ValueError('--steep-near-obstacle no_inflate requires --map fine')
        kwargs['steep_near_obstacle'] = steep_near_obstacle
    if terrain_source not in TERRAIN_SOURCES:
        raise ValueError('unknown terrain source')
    if terrain_source != 'sensor':
        if map_method != 'fine':
            raise ValueError(f'{terrain_source} terrain source requires --map fine')
        kwargs['terrain_source'] = terrain_source
    from tapp.prior_variants import OBSTACLE_REFERENCES
    if obstacle_clearance not in FINE_CLEARANCE_MODES:
        raise ValueError('unknown obstacle clearance')
    if obstacle_clearance != 'centre':
        if map_method != 'fine':
            raise ValueError(f'{obstacle_clearance} obstacle clearance requires --map fine')
        kwargs['obstacle_clearance'] = obstacle_clearance
    if obstacle_clearance == 'distance':
        kwargs['clearance_soft_m'] = clearance_soft_m
    if obstacle_reference not in OBSTACLE_REFERENCES:
        raise ValueError('unknown obstacle reference')
    if obstacle_reference != 'prior':
        if map_method != 'fine':
            raise ValueError('local obstacle reference requires --map fine')
        kwargs['obstacle_reference'] = obstacle_reference
    if ground_estimate not in GROUND_ESTIMATES:
        raise ValueError('unknown ground estimate')
    if ground_estimate != 'all_returns' and map_method != 'fine':
        raise ValueError('non_obstacle ground estimate requires --map fine')
    if sensors != 'legacy':
        if map_method != 'fine':
            raise ValueError('real sensors require --map fine')
        from tapp.pointcloud_map_multi import PointCloudMapMulti
        return PointCloudMapMulti(*args, sensors=sensors, ground_estimate=ground_estimate, **kwargs)
    if map_method == 'coarse':
        return PointCloudMap(*args, **kwargs)
    if map_method == 'fine':
        from tapp.pointcloud_map_fine import PointCloudMapFine
        return PointCloudMapFine(*args, ground_estimate=ground_estimate, **kwargs)
    raise ValueError('map method must be coarse or fine')


def fine_protocol(*, real_time_factor=None):
    """Fixed task023 settings, matching task022's actual ten-beach run."""
    factor = (float(os.environ.get('THESIS_REAL_TIME_FACTOR', '.3'))
              if real_time_factor is None else real_time_factor)
    stale = float(os.environ.get('THESIS_STALE_TIMEOUT_S', '1.0'))
    # Keep the archived environment-based protocol as well as the CLI opt-in.
    protocol = os.environ.get('THESIS_FINE_PROTOCOL')
    if protocol not in (None, 'rtf_check'):
        raise ValueError('unknown fine protocol')
    allowed = (.3, 1.) if protocol or real_time_factor == 1. else (.3,)
    if factor not in allowed or stale != 1.:
        raise ValueError('fine comparison fixes real_time_factor=0.3 and stale_timeout_s=1.0')
    return dict(map_method='fine', obstacle_resolution_m=.1, obstacle_height_m=.3,
                min_obstacle_points=3, obstacle_inflation_radius_m=.5,
                obstacle_inflation='once at 0.1m before coarse overlap; never inflate pooled detections',
                history='same last 64 returns per 0.5m height cell as task022; retain fine cell IDs',
                terrain_visual='triangle_mesh', terrain_collision='heightmap',
                world_input='task022 actual-run evaluation_reference.npz elevation and unchanged raw masks',
                real_time_factor=factor, stale_timeout_s=stale,
                comparison_baseline='results/gazebo_lidar/physical_10')


def matched_task022_maps(patch, truth, prior):
    """Reuse task022's actual elevation bits, including its debris surface.

    Only the new fine run uses this path; its physical inputs should not drift
    when NumPy versions differ from the original run.
    """
    import json
    from pathlib import Path
    import numpy as np
    from tapp.traversability import TraversabilityMap
    root = Path(__file__).resolve().parents[2]
    baseline = root/'results/gazebo_lidar/physical_10'
    manifest = json.loads((baseline/'manifest.json').read_text())
    case = next(c for c in manifest['cases'] if c['patch'] == patch)
    reference = baseline/case['run_folder']/'evaluation_reference.npz'
    result = []
    with np.load(reference, allow_pickle=False) as arrays:
        for name, sc in [('truth', truth), ('prior', prior)]:
            z = arrays[name+'_elev'].copy()
            terrain = sc['terrain']
            if z.shape != sc['tmap'].shape or not np.isfinite(z).all():
                raise ValueError('invalid task022 height reference')
            raw = terrain['rock'] | terrain['water'] | terrain['nodata']
            tm = TraversabilityMap(z, raw, sc['tmap'].robot, sc['tmap'].weights)
            if not np.array_equal(tm.rock, arrays[name+'_rock']) or not np.array_equal(tm.lethal, arrays[name+'_lethal']):
                raise ValueError('task022 reference masks changed')
            result.append(dict(sc, tmap=tm, raw_elev=z, terrain=dict(terrain, elev=z)))
    return *result, str(reference.relative_to(root))


def sensor_bridge_config(base, sensors='legacy'):
    """Keep legacy YAML bytes, adding only explicit camera point-cloud bridges."""
    from tapp.sensor_geometry import sensor_configuration
    configuration = sensor_configuration(sensors)
    if configuration is None or sensors == 'lidar_real':
        return base
    for name in ('camera1', 'camera2'):
        base += (f'\n- ros_topic_name: /{name}/points\n  gz_topic_name: /{name}/points\n'
                 '  ros_type_name: sensor_msgs/msg/PointCloud2\n'
                 '  gz_type_name: gz.msgs.PointCloudPacked\n  direction: GZ_TO_ROS\n')
    return base
