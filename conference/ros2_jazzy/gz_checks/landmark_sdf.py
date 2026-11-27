"""Attach static known landmarks without changing the exported debris models."""

import xml.etree.ElementTree as ET


def add_landmark_models(world, landmarks):
    for item in landmarks:
        model = ET.SubElement(world, 'model', name=item.name)
        ET.SubElement(model, 'static').text = 'true'
        ET.SubElement(model, 'pose').text = (
            f'{item.x_m} {item.y_m} {item.bottom_z_m + item.height_m/2} 0 0 {item.yaw_rad}')
        link = ET.SubElement(model, 'link', name='landmark_link')
        for tag in ('collision', 'visual'):
            node = ET.SubElement(link, tag, name=tag)
            geometry = ET.SubElement(ET.SubElement(node, 'geometry'), item.shape)
            if item.shape == 'box':
                ET.SubElement(geometry, 'size').text = f'{item.width_m} {item.depth_m} {item.height_m}'
            else:
                ET.SubElement(geometry, 'radius').text = str(item.radius_m)
                ET.SubElement(geometry, 'length').text = str(item.height_m)
