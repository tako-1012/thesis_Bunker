# 081 段階 A　2024-04-24 の ODM 点群

研究室の OpenDroneMap 点群 **43,539,562 点**を、5 cm の立方体で集約した。
10 cm の標高地図も同じ元点群から作成した。元の 6 ファイルは研究 PC の
`~/thesis_data/drone_odm/2024-04-24/` に保管している。

## 座標と範囲

水平座標系は WGS 84 / UTM zone 52N（EPSG:32652）。`coords.txt` の
基準は `WGS84 UTM 52N`、次の行の ODM 平面オフセットは
`655213 3725181`。`proj.txt` は `+proj=utm +zone=52 +datum=WGS84 +units=m +no_defs +type=crs`。
LAZ は地理参照済みなので、局所原点には実際に格納された点の各軸の最小値を使った。
LAZ の埋め込み座標系も EPSG:32652。ヘッダーの境界値は
丸め前の値で、出力の境界値は実際の 1 mm 刻みの点から確認した。

| 軸 | 元の座標 (m) | 局所座標 (m) |
| --- | ---: | ---: |
| X（東） | 655194.349 ～ 655232.826 | 0 ～ 38.477 |
| Y（北） | 3725159.720 ～ 3725202.245 | 0 ～ 42.525 |
| Z（上） | 77.771 ～ 78.161 | 0 ～ 0.390 |

局所値に各 NPZ の `origin_utm_xyz_m`（float64）を加えると元の座標系に戻る。
原点は XYZ の成分ごとの最小で、元の 1 点に一致するとは限らない。
Z は LAZ の高さを使い、鉛直基準の変換は行っていない。

## 出力

| ファイル | バイト | 内容 |
| --- | ---: | --- |
| `point_cloud_5cm_000.npz` | 3,226,384 | 160,000 ボクセル |
| `point_cloud_5cm_001.npz` | 3,340,481 | 160,000 ボクセル |
| `point_cloud_5cm_002.npz` | 3,335,127 | 160,000 ボクセル |
| `point_cloud_5cm_003.npz` | 3,254,645 | 160,000 ボクセル |
| `point_cloud_5cm_004.npz` | 163,145 | 9,172 ボクセル |
| `elevation_10cm.npz` | 645,692 | X 385 × Y 426 マス |

- 5 cm 点群は **649,172 点**。`xyz` は局所 m の float32、
  `point_count` は元点数の uint32。RGB 付き入力では `rgb` に元 LAS の
  チャンネル単位で各格子の平均色を float32 で格納する。分割時はファイル名順に
  配列を連結できる。
- 10 cm 地図の配列は `[y, x]`。各セルの `z_min`、`z_max`、`z_median` は
  局所 m の float32、`point_count` は元点数の uint32。各マスの全元点で
  計算し、偶数点の中央値は中央 2 点の平均。点なしは高さ NaN・点数 0。
  点のないマスは **18,190/164,010（11.0908%）**。
  分母は点群の外接長方形全体で、撮影範囲外の端のマスも含む。
- セルは局所 0 m から増える軸に沿い、下端を含む。出力の高さには地面以外の点も含む。

## 元ファイルの SHA-256

| ファイル | バイト | SHA-256 |
| --- | ---: | --- |
| odm_georeferenced_model.laz | 136,294,985 | `fb00d07f8fe9a7ca8502108dda0dd7dc1c53a7d6b7b2c23aaaef48844b234187` |
| coords.txt | 16,745 | `6687ddcfc2b3ff89c693f39ef700b2e6ff67ba4d900b3706561516e487127cbf` |
| proj.txt | 59 | `fbceeda239eb013d77467fdc90203c449aa740648bc95628a7f52b4656611e44` |
| odm_georeferenced_model.info.json | 2,229 | `f2ce7088ee676332f8718a6874d22005a3cf50b6fd847e52530372b0beb3807c` |
| odm_orthophoto.tif | 2,180,641 | `98ecc25179d4335b2aff75321a313ed31f4734ffca25f6c8b0ce06c43e017076` |
| report.pdf | 7,473,246 | `c9def1b89255242b450f254fc7f18e3a5bf4bf3ecf22bc88d601547bef67a471` |

## 作り方

`conference/` から実行する。Python 3.12 の専用 venv に
`requirements_localization.txt` と `requirements_drone_map.txt` を入れる。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1
nice -n 19 ionice -c 3 .venv-localization/bin/python -m experiments.drone_map_downsample \
  --source "$HOME/thesis_data/drone_odm/2024-04-24" \
  --out data/drone_odm/2024-04-24
```

LAZ は単一スレッドの lazrs でチャンク読み込みする。整数の LAS 座標で
格子番号を求め、各ボクセルで元点の座標と色の和・点数を集計する。
標高は、10 cm セルと元の Z の組を整列して最大・最小・中央値を求める。
座標系、点数、範囲、依存の版は [summary.json](summary.json) に保存している。
