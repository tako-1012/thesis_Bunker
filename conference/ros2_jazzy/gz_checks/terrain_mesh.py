"""Triangle-mesh terrain visual for GPU LiDAR runs.

Gazebo's ogre2 GPU LiDAR renders visuals, and the heightmap visual's shader
fails to compile without a GPU (and on some laptop GPUs), aborting the server.
LiDAR runs therefore replace only the terrain *visual* by a mesh through the
cell centres (x = i*res, y = j*res); the heightmap collision is unchanged.
"""
import xml.etree.ElementTree as ET

import numpy as np


def write_terrain_obj(elev, path, res=0.5):
    z = np.asarray(elev, float)
    n, m = z.shape
    ii, jj = np.meshgrid(np.arange(n), np.arange(m), indexing="ij")
    with open(path, "w") as f:
        np.savetxt(f, np.c_[ii.ravel() * res, jj.ravel() * res, z.ravel()], fmt="v %.3f %.3f %.4f")
        a = (ii[:-1, :-1] * m + jj[:-1, :-1] + 1).ravel()
        b, c, d = a + m, a + m + 1, a + 1
        np.savetxt(f, np.r_[np.c_[a, b, c], np.c_[a, c, d]], fmt="f %d %d %d")
    return path


def use_mesh_visual(tree, obj_uri):
    """Drop the heightmap visual of model 'terrain' and add a static mesh visual."""
    world = tree.find("world")
    for link in world.findall('model[@name="terrain"]/link'):
        for visual in link.findall("visual"):
            link.remove(visual)
    model = ET.SubElement(world, "model", name="terrain_mesh")
    ET.SubElement(model, "static").text = "true"
    visual = ET.SubElement(ET.SubElement(model, "link", name="mesh_link"), "visual", name="mesh_visual")
    ET.SubElement(ET.SubElement(ET.SubElement(visual, "geometry"), "mesh"), "uri").text = obj_uri
    return tree
