"""Export a cell-centred NPZ as a 16-bit SDF heightmap with conservative box obstacles."""

import argparse
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
import numpy as np
from scipy.ndimage import label, find_objects, map_coordinates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapp.mapfile import load_map_file


def png16(pixels):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    height, width = pixels.shape
    raw = b"".join(b"\0" + row.astype(">u2").tobytes() for row in pixels)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def export_gazebo(map_path, output):
    sc = load_map_file(map_path)
    z = sc["tmap"].elev
    if z.shape[0] != z.shape[1]:
        raise ValueError("Gazeboの地形は正方形の地図にしてください")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    n = z.shape[0]
    res = sc["resolution"]
    side = n * res
    minimum = float(z.min())
    span = max(float(z.max() - minimum), 1.0e-3)
    pixels = 2 ** int(np.ceil(np.log2(n - 1))) + 1
    # Use the smallest legal raster meeting the required reconstruction error.
    # Nearest-data fills can introduce sharper edges than a 513-pixel grid retains.
    while True:
        axis = np.linspace(-0.5, n - 0.5, pixels)
        xx, yy = np.meshgrid(axis, axis, indexing="ij")
        heights = map_coordinates(z, [xx, yy], order=1, mode="nearest")
        encoded = np.rint((heights - minimum) / span * 65535).astype(np.uint16)
        decoded = encoded.astype(float) / 65535 * span + minimum
        source_axis = (np.arange(n) + 0.5) / n * (pixels - 1)
        sx, sy = np.meshgrid(source_axis, source_axis, indexing="ij")
        restored = map_coordinates(decoded, [sx, sy], order=1, mode="nearest")
        error = float(np.max(np.abs(restored - z)))
        if error <= 0.1:
            break
        if pixels >= 2049:
            raise ValueError(f"高さ地図の補間誤差が0.1mを超えています: {error}")
        pixels = 2 * (pixels - 1) + 1
    (output / "heightmap.png").write_bytes(png16(encoded.T[::-1]))
    sdf = ET.Element("sdf", version="1.9")
    world = ET.SubElement(sdf, "world", name="beach")

    def node(parent, tag, text=None, **attrs):
        item = ET.SubElement(parent, tag, attrs)
        if text is not None:
            item.text = str(text)
        return item

    for filename, plugin_name in [
        ("gz-sim-physics-system", "gz::sim::systems::Physics"),
        ("gz-sim-user-commands-system", "gz::sim::systems::UserCommands"),
        ("gz-sim-scene-broadcaster-system", "gz::sim::systems::SceneBroadcaster"),
    ]:
        node(world, "plugin", filename=filename, name=plugin_name)
    physics = node(world, "physics", name="physics", type="ignored")
    node(physics, "max_step_size", "0.001")
    node(physics, "real_time_factor", "1")
    scene = node(world, "scene")
    node(scene, "ambient", "0.5 0.5 0.5 1")
    node(scene, "background", "0.75 0.85 0.95 1")
    sun = node(world, "light", type="directional", name="sun")
    node(sun, "cast_shadows", "true")
    node(sun, "direction", "-0.5 -0.5 -1")
    node(sun, "diffuse", "0.9 0.9 0.9 1")
    node(sun, "specular", "0.2 0.2 0.2 1")
    model = node(world, "model", name="terrain")
    node(model, "static", "true")
    link = node(model, "link", name="terrain_link")
    for tag in ("collision", "visual"):
        item = node(link, tag, name="terrain_" + tag)
        heightmap = node(node(item, "geometry"), "heightmap")
        node(heightmap, "uri", "heightmap.png")
        node(heightmap, "size", f"{side:.17g} {side:.17g} {span:.17g}")
        node(
            heightmap, "pos", f"{side/2-res/2:.17g} {side/2-res/2:.17g} {minimum:.17g}"
        )
        node(heightmap, "sampling", "1")
        if tag == "collision":
            ode = node(node(node(item, "surface"), "friction"), "ode")
            node(ode, "mu", "1.0")
            node(ode, "mu2", "1.0")
        else:
            mat = node(item, "material")
            node(mat, "ambient", "0.65 0.55 0.35 1")
            node(mat, "diffuse", "0.75 0.65 0.45 1")
    if sc["water"].any():
        water = node(world, "model", name="water")
        node(water, "static", "true")
        node(water, "pose", f"{side/2-res/2} {side/2-res/2} 0 0 0 0")
        visual = node(
            node(water, "link", name="water_link"), "visual", name="water_visual"
        )
        plane = node(node(visual, "geometry"), "plane")
        node(plane, "normal", "0 0 1")
        node(plane, "size", f"{side} {side}")
        material = node(visual, "material")
        node(material, "ambient", "0.1 0.35 0.8 0.5")
        node(material, "diffuse", "0.1 0.35 0.8 0.5")
        node(visual, "transparency", "0.5")
    labels, count = label(sc["obstacle"])
    for index, region in enumerate(find_objects(labels), 1):
        if region is None:
            continue
        lo = np.array([s.start for s in region])
        hi = np.array([s.stop for s in region])
        cells = z[region][labels[region] == index]
        bottom = float(cells.min()) - 0.1
        top = float(cells.max()) + 0.5
        centre = (lo + hi - 1) * res / 2
        size = (hi - lo) * res
        obstacle = node(world, "model", name=f"obstacle_{index}")
        node(obstacle, "static", "true")
        node(obstacle, "pose", f"{centre[0]} {centre[1]} {(bottom+top)/2} 0 0 0")
        link = node(obstacle, "link", name="box_link")
        for tag in ("collision", "visual"):
            item = node(link, tag, name="box_" + tag)
            box = node(node(item, "geometry"), "box")
            node(box, "size", f"{size[0]} {size[1]} {top-bottom}")
    ET.indent(sdf)
    ET.ElementTree(sdf).write(
        output / "world.sdf", encoding="utf-8", xml_declaration=True
    )
    (output / "README_ja.md").write_text(
        f"""# Gazebo Harmonic用の地形

元地図：`{Path(map_path).name}`。{sc['attribution']}

Ubuntu 24.04でGazebo Harmonicをインストール後、このフォルダで実行します。

```bash
export GZ_SIM_RESOURCE_PATH="$PWD:${{GZ_SIM_RESOURCE_PATH:-}}"
gz sim world.sdf
```

高さ画像は{pixels}×{pixels}画素、16 bitグレースケールです。
元格子中心に戻す最大誤差が0.1m以下となる最小の2^n+1画像を選びます。
地図の各マス中心は(x,y)=(i×{res},j×{res})m、x右向き・y上向き、PNGの上端は+y側です。
地形の範囲は両軸とも−{res/2}〜{side-res/2}m、原点は最初のマス中心です。
マス境界まで半マス延長して双線形補間し、端は最近傍値で延長しました。
NaNは地図ローダーで最近傍の実測値を使って埋めます。高さは最小値{minimum:.17g}mをpos.zに、幅{span:.17g}mをsize.zに分けています。
16bit量子化の上限は{span/65535/2:.17g}m、元格子中心へ戻した最大誤差は{error:.17g}mでした。
障害物は膨張前マスクの4近傍連結成分ごとの軸平行な外接箱{count}個です。
各箱はその領域の最小標高より0.1m下から最大標高より0.5m上までとする形状の仮定です。穴や非矩形部分も箱で覆います。
摩擦係数は仮定値1.0（測定値ではありません）。水面はz=0の見た目だけの平面で、衝突を作りません。
通行不可の傾斜・水・データなし・安全余白はPython側の計画マスクであり、Gazeboの箱と同じものではありません。
この環境ではGazeboを実行していません。XML・PNG・標高の復元だけを検証しました。
"""
    )
    result = dict(
        map=Path(map_path).name,
        pixels=pixels,
        side_m=side,
        z_min=minimum,
        z_span=span,
        max_error_m=error,
        quantization_bound_m=span / 65535 / 2,
        obstacle_boxes=int(count),
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="地図ファイルをGazebo Harmonicの高さ地図へ変換"
    )
    parser.add_argument("map", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = export_gazebo(args.map, args.output)
    print("map pixels side_m max_error_m quantization_bound_m obstacle_boxes")
    print(
        *(
            result[k]
            for k in (
                "map",
                "pixels",
                "side_m",
                "max_error_m",
                "quantization_bound_m",
                "obstacle_boxes",
            )
        )
    )
