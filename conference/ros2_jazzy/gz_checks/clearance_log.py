"""Persist the debris collision rectangles from the generated Gazebo world."""

import csv

BOUNDS_FIELDS = ('xmin', 'ymin', 'xmax', 'ymax')


def save_debris_footprints(path, world):
    with path.open('x', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(BOUNDS_FIELDS)
        for model in world.findall('model'):
            if model.get('name', '').startswith('obstacle_'):
                x, y, _, roll, pitch, yaw = map(float, model.findtext('pose').split())
                width, length, _ = map(float, model.findtext('link/collision/geometry/box/size').split())
                if any((roll, pitch, yaw)):
                    raise ValueError('debris footprint requires an axis-aligned box')
                writer.writerow((x-width/2, y-length/2, x+width/2, y+length/2))
