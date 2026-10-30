# Web画面とGazeboで共用する地図

リポジトリ直下から `cd conference && python3 data_prep/export_maps.py` で再生成できます。
人工地形は検証シード100、実測地形は `build_real(name, 200, 0)` を使用します。元データは変更しません。

| ファイル | 内容 |
|---|---|
| `flat_test_100m.npz` | 平らな100m四方、基地(10,10)m。中央付近に軸平行な箱3つの障害物マスク |
| `beach_gentle_{100,200}m_100.npz` | 緩やかな人工砂浜。水と漂着物を含む |
| `beach_steep_{100,200}m_100.npz` | 急な人工砂浜。水と漂着物を含む |
| `beach_scarp_{100,200}m_100.npz` | 浜崖のある人工砂浜。水と漂着物を含む |
| `rolling_{100,200}m_100.npz` | 起伏地 |
| `hills_{100,200}m_100.npz` | 丘陵 |
| `real_<パッチ名>_200m_0.npz` | 静岡県のvalidation 12パッチ、200m四方。漂着物は追加しない |

実測パッチは `08OB87_-0206`、`08OB88_01332`、`08OB89_-1597`、`08OC90_00270`、
`08OC91_00811`、`08OC93_-1519`、`08OC95_-0321`、`08OC96_-0676`、`08OC97_-0077`、
`08OC98_-1101`、`08OC98_01898`、`08OC99_00983` です。
機械可読なファイル一覧・容量は `results/mapfiles_sim/export_maps_log.txt` を参照してください。

## 形式と座標

`np.savez_compressed`、`format_version=1`。`allow_pickle=False` で読み込めます。

- `elev`：float32の標高[m]（NaN可）、配列の軸は(x,y)。
- `obstacle`・`water`・`nodata`：同じ形状のbool配列。**障害物は安全余白を膨張する前**のマスクです。
- `resolution`：0.5m。保護された既存プランナーの解像度が固定のため、他の値は受け付けません。
- `start_xy`：最初の基地の座標[m]。
- `name`・`kind`・`source`・`attribution`：文字列。
- `elev_residual`：必要な場合だけ保存するfloat64の精度補助配列。
  元のfloat64標高と `elev.astype(float64)` の差です。読み込み時に加算して元の標高を復元します。
  float32の標高だけでは、元の勾配・粗さ・コストのビット単位の一致を保てないため追加しています。
  派生コストや膨張済み障害物は保存せず、元と同じ `TraversabilityMap` で計算します。

マス中心は `(x,y)=(i×0.5,j×0.5)`m、原点は最初のマス中心。xは海岸線方向、yは海から陸の方向です。
実測データの元の座標範囲（x=−100〜100m、y=−50〜150m）から原点を移したローカル平面です。
GPSではありません。起伏地と丘陵はローカルなx・y軸です。

`tapp.mapfile.load_map_file` でNaNを最近傍の標高で埋め、
`TraversabilityMap(elev_filled, obstacle | water | nodata, robot, weights)` を作ります。
`scenario_to_mapfile` の往復では、元と同じロボット／重みを指定すると `cost`・`lethal`・`start` が完全一致します。
標準の出力は既定のロボット／重みです。

Webサーバーを起動するとこのフォルダの `*.npz` が `file/<ファイル名>` として一覧に加わります。
独自地図は上の形式で保存して置き、サーバーを再起動してください。
指示書010の `synthetic/...`・`real/...` も残っています。

## 実測地形の出典

- 出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB グリッドデータ（0.5m）
  https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb
- ライセンス：CC BY 4.0 / ODbL。**このフォルダのデータは、上のデータを加工して作成したものです**
  （論文や発表で使うときは、この出典を書くこと）。
- 元データの座標：日本測地系2024・平面直角座標系第8系、高さは東京湾平均海面（T.P.）。

切り出しの詳細と限界は `conference/data/shizuoka_beach/README_ja.md` を参照してください。

## 点群から再作成したLAS版（タスク013）

`real_las_<パッチ名>_200m_0.npz` の12枚を追加しています。
パッチ名・位置・向き・validationの選択は従来の実測12枚と同じで、
`build_real(name, 200, 0, dataset="shizuoka_beach_las")` から作成します。
元データは `conference/data/shizuoka_beach_las/` に同梱済みで、ダウンロードは不要です。
従来のグリッド版の地図も残してあり、既存ファイルは上書きしません。

```bash
cd conference
python3 data_prep/export_maps.py
```

このコマンドは既存23枚を保持・検証し、LAS版12枚を追加して合計35枚を検証します。
元の「全体15MB」の制限は12枚追加と両立しないため、追加後は各ファイル5MB未満を検査します。
元の `tests.test_mapfiles_sim` の枚数・容量・API件数の固定検査は、この指示書では変更許可がないため保持しています。
実行出力と対応表は `results/real_beach_las/export_maps_log.txt`、検証結果・制約は同フォルダの `REPORT_ja.md` に記録します。

LAS版の元データの作り方と注意点は `conference/data/shizuoka_beach_las/README_ja.md` を参照してください。
出典・ライセンスは各ファイルの `attribution` にも保存しています。

- 出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB 地面の点群（Ground）
  https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb
- ライセンス：CC BY 4.0 / ODbL。**このフォルダのデータは、上のデータを加工して作成したものです。**
- 元データの座標：日本測地系2024・平面直角座標系第8系、高さは東京湾平均海面（T.P.）。
