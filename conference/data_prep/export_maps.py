"""Export fixed validation scenarios and a three-box flat map without modifying sources."""

import argparse
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapp.beach_scenario import build_beach
from tapp.beach_terrain import BEACH_TYPES
from tapp.real_beach import build_real, list_patches
from tapp.mapfile import save_map, scenario_to_mapfile, load_map_file

ATTRIBUTION = "静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB グリッドデータ（0.5m）。https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb 。CC BY 4.0 / ODbL。この地図は、上のデータを加工して作成したものです。"
LAS_ATTRIBUTION = "静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB 地面の点群（Ground）。https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb 。CC BY 4.0 / ODbL。このフォルダのデータは、上のデータを加工して作成したものです。"


def export_maps(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    z = np.zeros((200, 200), dtype=np.float32)
    obstacle = np.zeros(z.shape, bool)
    for a, b, c, d in ((65, 80, 75, 95), (95, 115, 120, 135), (130, 145, 60, 80)):
        obstacle[a:b, c:d] = True
    if not (folder / "flat_test_100m.npz").exists():
        save_map(
            folder / "flat_test_100m.npz",
            z,
            obstacle=obstacle,
            start_xy=[10, 10],
            name="動作確認：平地と3つの箱（100m）",
            kind="flat_test",
            source="人工の動作確認用地図",
        )
    for kind in BEACH_TYPES:
        for size in (100, 200):
            sc = build_beach(kind, size, 100)
            path = folder / f"{kind}_{size}m_100.npz"
            if not path.exists():
                scenario_to_mapfile(
                    sc,
                    path,
                    f"人工：{kind}（{size}m）",
                    kind,
                    "tapp.beach_scenario.build_beach, seed=100",
                    "",
                )
            loaded = load_map_file(path)
            assert np.array_equal(sc["tmap"].cost, loaded["tmap"].cost)
            assert np.array_equal(sc["tmap"].lethal, loaded["tmap"].lethal)
    for row in list_patches("validation"):
        name = row["name"]
        sc = build_real(name, 200, 0)
        path = folder / f"real_{name}_200m_0.npz"
        if not path.exists():
            scenario_to_mapfile(
                sc,
                path,
                f"静岡県：{name}（200m）",
                name,
                "静岡県ALB, validation, build_real seed=0",
                ATTRIBUTION,
            )
        loaded = load_map_file(path)
        assert np.array_equal(sc["tmap"].cost, loaded["tmap"].cost)
        assert np.array_equal(sc["tmap"].lethal, loaded["tmap"].lethal)
    export_las_maps(folder)
    total = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    if any(p.stat().st_size >= 5_000_000 for p in folder.glob("*.npz")):
        raise RuntimeError("地図ファイルが5 MBを超えました")
    print("filename bytes shape", flush=True)
    for path in sorted(folder.glob("*.npz")):
        sc = load_map_file(path)
        print(path.name, path.stat().st_size, sc["tmap"].shape, flush=True)
    print(
        "map_count", len(list(folder.glob("*.npz"))), "total_bytes", total, flush=True
    )


def export_las_maps(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for row in list_patches("validation", dataset="shizuoka_beach_las"):
        name = row["name"]
        sc = build_real(name, 200, 0, dataset="shizuoka_beach_las")
        path = folder / f"real_las_{name}_200m_0.npz"
        if not path.exists():
            scenario_to_mapfile(
                sc,
                path,
                f"静岡県（点群）：{name}（200m）",
                name,
                "静岡県ALB Ground, validation, build_real seed=0, dataset=shizuoka_beach_las",
                LAS_ATTRIBUTION,
            )
        loaded = load_map_file(path)
        assert np.array_equal(sc["tmap"].cost, loaded["tmap"].cost)
        assert np.array_equal(sc["tmap"].lethal, loaded["tmap"].lethal)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="固定シードの地図ファイルを書き出す")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parent.parent / "maps"
    )
    export_maps(parser.parse_args().output)
