# 指示書023：細格子の障害物検出と1回だけの膨張

> **追記（Claude）**：Gazebo の「未実行」は Codex の時点の記述。その後 Claude が通常の Docker で 10 か所を走らせた。結果は `physical_10/README_ja.md`（完走 5/10、経路なし 4、地図の端での転倒 1）。

基準日：2026-11-05（利用者環境の日付、UTC）。ブランチ：`codex/023-lidar-fine-grid`。基点：`6d0ae7dc733202b41b92df3c37f62e5a246426bc`。最新realtime-mapから作成し、他の作業ブランチを積まず、マージしていない。

## 実装したもの

- `tapp/pointcloud_map_fine.py`：`PointCloudMapFine.update/snapshot/save` と `coarse_overlap`。障害物だけを0.1mで検出し、円盤膨張をその格子で1回だけ行う。地面・特徴量は既存の0.5mの式と保持履歴を維持する。
- `ros2_jazzy/gz_checks/lidar_map.py`：`make_pointcloud_map`、`fine_protocol`、`matched_task022_maps`。既定は022の元のクラスそのもの。新方式は022の実走条件と実走時の標高を再利用する。
- `lidar_planner.py`：既定coarseのROSパラメータを追加し、選択したクラスへ渡す。探索・コスト式・再計画・センサー処理は変えない。
- `lidar_checks.py` と `run_lidar_checks.sh`：`--map fine` を追加。省略/明示coarseの既定値とmanifestは維持する。fineでは同一地点・順番・初期配置、メッシュ、0.3倍速、期限1.0秒を使う。
- `experiments/lidar_fine_report.py`：`map_audit`、`box_footprints`、`evaluation_maps`、`summary_table`、`summarize`。保存済み3条件の30行と新方式10行を並べ、観測済みマスクのFP/FN、箱への隣接、更新時間、接触を集計する。
- `tests/test_pointcloud_map_fine.py`：平地、0.02m測距雑音付きの箱、中心の保持、膨張の幾何・再観測・追加シード、保存、旧方式のバイト一致、manifestとDocker引数、4条件の欠測と旧値の保持を確認する。
- `tasks/023_lidar_fine_grid.md`：今回の利用者の指示内容を同じブランチに保存した。

## 方法と事前固定した値

0.1m・高さ0.3m・3点・半径0.5mは指示書で事前指定された値として固定し、変更・選択・調整していない。
新方式ではこれらと異なる設定を拒否する。点群の登録・範囲除外・古い地面の双線形補間は022と同じで、真値ラベルを観測に流用しない。

0.5mセルを境界に合わせて5×5の0.1mセルに分ける。地面の高さは従来どおり粗セル内の直近64点の中央値。
判定もこの同じ履歴の中で細セルIDを区別する。履歴の長さや保持期間を新たに延ばしていない。
したがって、地面・傾斜・凸凹・コスト・観測済みマスクの計算は同じで、細分化するのは障害物の位置と証拠だけである。

検出した細セルを半径5細セルの円盤で膨張し、その後5×5内に膨張セルが1つでもある粗セルを通行不可にする。
粗セルへまとめたマスクは再膨張させない。追加の観測では新しい生の障害物の膨張との和を取り、膨張済みマスクを入力にしない。
既存の岩の膨張は1回のまま、急斜面は変更していない `footprint.inflate_steep` を使う。
セルの「重なり」は領域の重なりであり、距離の検証も細セル領域と粗セル領域との最小距離で行う。セル中心の距離ではない。

新しい方式のNPZは、従来のelev/seen/obstacle/cost/lethalに加え、細格子の検出・膨張マスクをpackbitsで保存する。
地図更新の公開APIは元と同じ。TA*・TA*-Sのコスト式や探索ロジックを変更していない。

## 022と同じ実走条件

021と022の10地形・world・地点・順番・スタートを共用する。メッシュの見た目とheightmapの衝突、0.3倍速と途切れ期限1.0秒をmanifestに明記した。
fineの場合は、環境変数でこれらと異なる条件を指定すると停止する。LiDARの仕様、取り付け位置、測距雑音も022の実走と同じ設定だけを受け付ける。

ライブラリ版の差で漂着物の標高のビットが変わる問題を避けるため、新しいworldには022の実走時の評価用標高配列を使う。
生の障害物・水・欠損マスクと、通行不能マスクの一致を検査し、開始点・目的地をずらさない。
旧worldファイルそのものは一時領域にしか残っていないためSDF全体のバイト比較は未実施だが、同じ入力標高・マスクと既存のエクスポーター/メッシュ生成処理を使う。
world/入力地図とbuild/installは一時領域に作り、既存の結果は更新しない。

```json
{
  "dataset": "shizuoka_beach_las",
  "split": "test",
  "side_m": 200,
  "seed": 0,
  "planner": "TA*-S+inflate",
  "sensor": "lidar",
  "patch_count": 10,
  "execution": "not_started",
  "world_max_pixels": 4097,
  "lidar_spec": {
    "vertical_samples": 16,
    "vertical_min_deg": -15.0,
    "vertical_max_deg": 15.0,
    "horizontal_samples": 1800,
    "update_hz": 10.0,
    "min_range_m": 0.1,
    "max_range_m": 30.0,
    "noise_stddev_m": 0.02,
    "range_resolution_m": 0.01
  },
  "sensor_height_m": 0.8,
  "obstacle_height_m": 0.3,
  "obstacle_reference": "stale prior DEM, bilinear; three high returns in a cell; uncalibrated assumption",
  "height_definition": "median of last 64 returns per hit cell, including obstacle tops",
  "baseline": "results/gazebo_online/physical_run",
  "scenarios": [
    {
      "patch": "08OB86_00294",
      "patch_index": 0,
      "planner": "TA*-S+inflate",
      "start": [
        52,
        195
      ],
      "points": [
        [
          309,
          113
        ],
        [
          6,
          289
        ],
        [
          273,
          232
        ],
        [
          104,
          176
        ],
        [
          46,
          121
        ]
      ],
      "order": [
        0,
        5,
        1,
        3,
        4,
        2
      ],
      "stops": [
        [
          46,
          121
        ],
        [
          309,
          113
        ],
        [
          273,
          232
        ],
        [
          104,
          176
        ],
        [
          6,
          289
        ],
        [
          52,
          195
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "05c6ce53aff1a43a4fa4f5d062744fa9702b13d14b9a3d2d263bf72d762ff89e",
        "lethal": "7ed14f758ece6fc21fe49419454b3e62c3f88c30d2d6052f5bbf897a7561ea62",
        "rock": "b0b52cb5a9e764910ac8d4e69dcc4f950d853240096a466b437693facb96ba87"
      },
      "prior_signature": {
        "elev": "06f417823b36cea218cf5ed2897911e772bdf63080178a788b43885321ab75bf",
        "lethal": "955836072744a537ab22514c7fc14a73acf7a02f3575e252da1a69a042fcb6c7",
        "rock": "8b51c5179bc998be8bb2d0b63e48a869b2c0beb9ce0c65f3adc0bbdf6e878e5b"
      },
      "initial_path": [
        [
          26.0,
          97.5
        ],
        [
          27.0,
          82.0
        ],
        [
          23.0,
          60.5
        ],
        [
          32.0,
          55.0
        ],
        [
          37.0,
          50.0
        ],
        [
          38.0,
          50.0
        ],
        [
          47.5,
          49.5
        ],
        [
          154.5,
          56.5
        ],
        [
          136.5,
          116.0
        ],
        [
          126.5,
          109.0
        ],
        [
          77.0,
          105.0
        ],
        [
          64.5,
          99.0
        ],
        [
          52.5,
          88.5
        ],
        [
          52.0,
          88.0
        ],
        [
          29.5,
          108.0
        ],
        [
          28.0,
          108.0
        ],
        [
          11.5,
          122.5
        ],
        [
          7.0,
          128.0
        ],
        [
          2.5,
          132.5
        ],
        [
          1.0,
          137.5
        ],
        [
          1.0,
          142.5
        ],
        [
          3.0,
          144.5
        ],
        [
          1.0,
          142.5
        ],
        [
          1.5,
          135.0
        ],
        [
          3.0,
          132.0
        ],
        [
          19.5,
          106.5
        ],
        [
          23.0,
          100.5
        ],
        [
          26.0,
          97.5
        ]
      ],
      "fixed_plan_times": [
        0.047015280999971765,
        0.2835738129999754,
        0.0897193050000169,
        0.1682448729999919,
        0.17760138299996697,
        0.09510763600002292
      ]
    },
    {
      "patch": "08OB86_-0205",
      "patch_index": 1,
      "planner": "TA*-S+inflate",
      "start": [
        49,
        270
      ],
      "points": [
        [
          114,
          102
        ],
        [
          114,
          214
        ],
        [
          42,
          179
        ],
        [
          135,
          255
        ],
        [
          93,
          197
        ]
      ],
      "order": [
        0,
        3,
        1,
        5,
        2,
        4
      ],
      "stops": [
        [
          42,
          179
        ],
        [
          114,
          102
        ],
        [
          93,
          197
        ],
        [
          114,
          214
        ],
        [
          135,
          255
        ],
        [
          49,
          270
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "9bc94ea920c8b6ebfadc933da84280226c00fd13aa505851f5621eb2eb4df321",
        "lethal": "e46b1e845737da313eac2b893c2b750e71c919a453356fbf749cb6e2ae706bcc",
        "rock": "221072c1cab9f2f48b7c03b74f7af552462697afe4c72881f3ce2b99bcf4b3da"
      },
      "prior_signature": {
        "elev": "7692fc79e1b4099af724d33ef3eab8949539cd4735aa57077f897cf2dfbac2a8",
        "lethal": "f1225d7397f8e3937d5664ebb7e26d2ba78b04c0d7d962bd99fca9a250c737cb",
        "rock": "6feb83e08f8cfefae386d327f9a32481b855a6548e753f343825a4f60f4b722c"
      },
      "initial_path": [
        [
          24.5,
          135.0
        ],
        [
          25.5,
          126.0
        ],
        [
          25.5,
          114.0
        ],
        [
          21.0,
          97.0
        ],
        [
          21.0,
          89.5
        ],
        [
          34.0,
          74.5
        ],
        [
          39.5,
          72.0
        ],
        [
          55.5,
          52.5
        ],
        [
          56.5,
          51.5
        ],
        [
          57.0,
          51.0
        ],
        [
          55.0,
          66.5
        ],
        [
          46.5,
          95.5
        ],
        [
          46.5,
          98.5
        ],
        [
          56.5,
          106.5
        ],
        [
          57.0,
          107.0
        ],
        [
          67.5,
          127.5
        ],
        [
          65.0,
          125.0
        ],
        [
          64.0,
          123.5
        ],
        [
          61.0,
          121.5
        ],
        [
          42.0,
          124.5
        ],
        [
          36.5,
          127.5
        ],
        [
          31.5,
          127.5
        ],
        [
          26.0,
          133.0
        ],
        [
          24.5,
          135.0
        ]
      ],
      "fixed_plan_times": [
        0.07152156099999729,
        0.0872987500000022,
        0.06529155800001263,
        0.017403748999981872,
        0.0294234400000164,
        0.1068995379999933
      ]
    },
    {
      "patch": "08OB87_-0706",
      "patch_index": 3,
      "planner": "TA*-S+inflate",
      "start": [
        50,
        200
      ],
      "points": [
        [
          9,
          255
        ],
        [
          89,
          197
        ],
        [
          263,
          259
        ],
        [
          59,
          119
        ],
        [
          347,
          145
        ]
      ],
      "order": [
        0,
        4,
        5,
        3,
        2,
        1
      ],
      "stops": [
        [
          59,
          119
        ],
        [
          347,
          145
        ],
        [
          263,
          259
        ],
        [
          89,
          197
        ],
        [
          9,
          255
        ],
        [
          50,
          200
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "22d0b939656f3a75adb1b0ae21ef57801f4b8e8af1fc0b4ad21741ade7f78119",
        "lethal": "77b9a58bec28a3f123f8cabee901a87a98be8d30b0f9c479b9efee2a5342ffb6",
        "rock": "2c94c6c1ac6bd3ca4e50f2456d1ea65506785e1325cd58dd5ef78b2919b8acc7"
      },
      "prior_signature": {
        "elev": "53c049b7e1cf1940b928740f60e7f58eba47db505cfcdf76b8bc0c18db59869a",
        "lethal": "053b5221d06b4dcd5ccbddbd8a0943db4109a85336637f3608f132dfb1c5f179",
        "rock": "bba4745e20744684f84c4896c52ff0f8f222650dcd0fc5774bdf3b03542e683a"
      },
      "initial_path": [
        [
          25.0,
          100.0
        ],
        [
          28.0,
          68.5
        ],
        [
          29.5,
          59.5
        ],
        [
          38.0,
          68.5
        ],
        [
          56.5,
          72.0
        ],
        [
          61.0,
          71.0
        ],
        [
          75.5,
          71.0
        ],
        [
          82.5,
          73.5
        ],
        [
          89.5,
          73.5
        ],
        [
          109.0,
          76.5
        ],
        [
          125.5,
          73.5
        ],
        [
          139.5,
          73.0
        ],
        [
          150.0,
          74.5
        ],
        [
          173.5,
          72.5
        ],
        [
          159.5,
          100.0
        ],
        [
          138.0,
          117.0
        ],
        [
          131.5,
          125.0
        ],
        [
          131.5,
          129.5
        ],
        [
          128.5,
          126.0
        ],
        [
          124.0,
          124.0
        ],
        [
          97.5,
          122.5
        ],
        [
          45.0,
          99.0
        ],
        [
          44.5,
          98.5
        ],
        [
          20.5,
          108.0
        ],
        [
          4.0,
          119.0
        ],
        [
          4.5,
          127.5
        ],
        [
          4.0,
          119.0
        ],
        [
          14.0,
          110.0
        ],
        [
          21.0,
          103.0
        ],
        [
          25.0,
          100.0
        ]
      ],
      "fixed_plan_times": [
        0.05674657500003377,
        0.5134107200000244,
        0.14984785699999748,
        0.2507064320000154,
        0.0794463720000067,
        0.04555728299999373
      ]
    },
    {
      "patch": "08OB88_-1417",
      "patch_index": 4,
      "planner": "TA*-S+inflate",
      "start": [
        70,
        169
      ],
      "points": [
        [
          337,
          140
        ],
        [
          313,
          165
        ],
        [
          199,
          151
        ],
        [
          264,
          194
        ],
        [
          203,
          229
        ]
      ],
      "order": [
        0,
        3,
        1,
        2,
        4,
        5
      ],
      "stops": [
        [
          199,
          151
        ],
        [
          337,
          140
        ],
        [
          313,
          165
        ],
        [
          264,
          194
        ],
        [
          203,
          229
        ],
        [
          70,
          169
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "96f92a9a3d6c0fe32e00cc977e0ce03347ecb48e21409a3801f674570c235091",
        "lethal": "f38c6a901e4a0ffbc99ef00207abecd9e42693bdd64bf70db1b6c09a870dfbf6",
        "rock": "9733aa5ad147ecf7fecbc03ca331fbb493be5728ff32f063cafba28cb33a9762"
      },
      "prior_signature": {
        "elev": "0d68ad3e7b83d8ff2a9c31b7015a9716638cf627cf1452216c3f4feeb49c6b54",
        "lethal": "2a4fa502deb5b40343bbffbd947c6221d87a39cf618615da804fdc887e59b14d",
        "rock": "0110056d01ebf0cb4213f3efce21092b32c1f2c12ccaaa6ae19a6026a3efd955"
      },
      "initial_path": [
        [
          35.0,
          84.5
        ],
        [
          56.0,
          74.0
        ],
        [
          98.0,
          74.0
        ],
        [
          99.0,
          75.0
        ],
        [
          99.5,
          75.5
        ],
        [
          100.5,
          74.5
        ],
        [
          103.5,
          72.5
        ],
        [
          123.5,
          71.5
        ],
        [
          163.0,
          71.5
        ],
        [
          168.5,
          70.0
        ],
        [
          158.5,
          76.5
        ],
        [
          157.5,
          77.5
        ],
        [
          156.5,
          82.5
        ],
        [
          138.5,
          89.0
        ],
        [
          132.0,
          96.5
        ],
        [
          132.0,
          97.0
        ],
        [
          107.5,
          108.0
        ],
        [
          101.5,
          114.5
        ],
        [
          101.0,
          113.5
        ],
        [
          50.5,
          90.0
        ],
        [
          35.0,
          84.5
        ]
      ],
      "fixed_plan_times": [
        0.08215319300001056,
        0.11942423600004304,
        0.026461893999965014,
        0.039102400999979636,
        0.04723163900001737,
        0.1231047530000069
      ]
    },
    {
      "patch": "08OB88_-0167",
      "patch_index": 5,
      "planner": "TA*-S+inflate",
      "start": [
        38,
        231
      ],
      "points": [
        [
          137,
          294
        ],
        [
          249,
          150
        ],
        [
          202,
          281
        ],
        [
          31,
          208
        ],
        [
          348,
          149
        ]
      ],
      "order": [
        0,
        4,
        2,
        5,
        3,
        1
      ],
      "stops": [
        [
          31,
          208
        ],
        [
          249,
          150
        ],
        [
          348,
          149
        ],
        [
          202,
          281
        ],
        [
          137,
          294
        ],
        [
          38,
          231
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "41d677c87293711b20b7a1a68eee7de61617c0c9159cb19f83197c77a3681e48",
        "lethal": "764a684bb1ff899bb2f01cd36131052e5dbf99ad993814321262a01fcc4e7b1a",
        "rock": "b18ca235bff3c9fa4b9d6d05f3c8a463b687bb4f99c4dc6340d329b2530c8cd4"
      },
      "prior_signature": {
        "elev": "23722bc88cf47c848bc9e12321d347247b75f09c27f10492985146ca14779aed",
        "lethal": "259f3907787df5b726fefee3cf1026dbae420f1e0fccd9eb532a06b6c5326d94",
        "rock": "71842a3c59c1ccbe171d140914a1ac4c1b3b4458171e7a718434b44b023b5d1e"
      },
      "initial_path": [
        [
          19.0,
          115.5
        ],
        [
          15.5,
          104.0
        ],
        [
          36.0,
          104.5
        ],
        [
          92.5,
          103.0
        ],
        [
          107.5,
          92.0
        ],
        [
          124.5,
          75.0
        ],
        [
          132.5,
          69.5
        ],
        [
          163.5,
          69.5
        ],
        [
          174.0,
          74.5
        ],
        [
          123.5,
          115.0
        ],
        [
          108.5,
          131.5
        ],
        [
          107.5,
          132.5
        ],
        [
          106.5,
          133.5
        ],
        [
          105.5,
          134.5
        ],
        [
          103.0,
          137.0
        ],
        [
          101.0,
          140.5
        ],
        [
          94.5,
          141.0
        ],
        [
          91.5,
          140.5
        ],
        [
          69.0,
          140.0
        ],
        [
          55.5,
          144.5
        ],
        [
          54.5,
          146.0
        ],
        [
          56.0,
          148.0
        ],
        [
          67.0,
          148.0
        ],
        [
          68.5,
          147.5
        ],
        [
          68.5,
          147.0
        ],
        [
          68.5,
          147.5
        ],
        [
          65.0,
          148.0
        ],
        [
          55.5,
          148.0
        ],
        [
          54.5,
          146.0
        ],
        [
          56.5,
          143.5
        ],
        [
          88.0,
          135.0
        ],
        [
          88.0,
          130.0
        ],
        [
          82.5,
          124.5
        ],
        [
          56.5,
          109.0
        ],
        [
          46.0,
          108.0
        ],
        [
          21.5,
          113.5
        ],
        [
          19.0,
          115.5
        ]
      ],
      "fixed_plan_times": [
        0.017507619000014074,
        0.22574734799997032,
        0.07059866000003012,
        0.21566916200004016,
        0.12087703499997815,
        0.14392919000005122
      ]
    },
    {
      "patch": "08OB88_00332",
      "patch_index": 6,
      "planner": "TA*-S+inflate",
      "start": [
        45,
        228
      ],
      "points": [
        [
          142,
          207
        ],
        [
          38,
          131
        ],
        [
          203,
          180
        ],
        [
          136,
          171
        ],
        [
          70,
          116
        ]
      ],
      "order": [
        0,
        2,
        5,
        4,
        3,
        1
      ],
      "stops": [
        [
          38,
          131
        ],
        [
          70,
          116
        ],
        [
          136,
          171
        ],
        [
          203,
          180
        ],
        [
          142,
          207
        ],
        [
          45,
          228
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "a9cf56a7b64ee1160c733fc01e1e3e61ec86953727a4679b3b37be06cb76c62e",
        "lethal": "aa52077035de8a49b5cdb396c3f2c0e2c504d5fcfabcc2a2d4ef1bb9f3be2bd1",
        "rock": "1e013680f6df39c44e88e3c8cd5b14d2539b662e3100216c0501e9cad03c0e54"
      },
      "prior_signature": {
        "elev": "1f6774027103f5d3629c0e993ff7b8aa5fbb356a1e84ee5e1dee6c9d828b4928",
        "lethal": "e908c08af69bb5ace1d25e8f3b4cc043f50f553718100511c9d57fa0b35775a1",
        "rock": "739172300967b99e78a2cd0d5afa164e1cff83c5ba4e8893a93d40fa8763ef08"
      },
      "initial_path": [
        [
          22.5,
          114.0
        ],
        [
          19.0,
          65.5
        ],
        [
          23.0,
          66.0
        ],
        [
          27.5,
          65.5
        ],
        [
          35.0,
          58.0
        ],
        [
          68.0,
          85.5
        ],
        [
          101.5,
          90.0
        ],
        [
          71.0,
          103.5
        ],
        [
          62.5,
          106.5
        ],
        [
          58.5,
          109.5
        ],
        [
          53.5,
          114.5
        ],
        [
          25.5,
          114.5
        ],
        [
          22.5,
          114.0
        ]
      ],
      "fixed_plan_times": [
        0.053327129999956924,
        0.024613177999981417,
        0.04092713800002912,
        0.0337649699999929,
        0.03452223499999718,
        0.09777324399999543
      ]
    },
    {
      "patch": "08OB88_01832",
      "patch_index": 8,
      "planner": "TA*-S+inflate",
      "start": [
        36,
        214
      ],
      "points": [
        [
          392,
          249
        ],
        [
          397,
          169
        ],
        [
          223,
          254
        ],
        [
          335,
          247
        ],
        [
          159,
          229
        ]
      ],
      "order": [
        0,
        5,
        3,
        4,
        1,
        2
      ],
      "stops": [
        [
          159,
          229
        ],
        [
          223,
          254
        ],
        [
          335,
          247
        ],
        [
          392,
          249
        ],
        [
          397,
          169
        ],
        [
          36,
          214
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "1d0114bd0d05b3df16c2a4f204bbdf23e5c9c2767cbbfa6da65c7e841f982087",
        "lethal": "0f428c5f00ed2725d62cb89cad4d476b4b83cf7f4fee2ed92ad2bf8d130a242d",
        "rock": "9f8cb7448827d13f6c0eebbdbdf450eaccb7045ffb2129f8c50817ee93537c53"
      },
      "prior_signature": {
        "elev": "23565122185b3529415815b007f6b63b5c51a859312db88a5e036b0d8bc18790",
        "lethal": "7ec00b5a8f1d0c948d0c422a712530266fbeccf532244961c26a37212156def5",
        "rock": "f7bd00cdfbd51194bef9aed8718d5f91053d207ae9abe954d44b4567bcbebca1"
      },
      "initial_path": [
        [
          18.0,
          107.0
        ],
        [
          31.5,
          105.0
        ],
        [
          68.5,
          108.5
        ],
        [
          79.5,
          114.5
        ],
        [
          82.5,
          112.0
        ],
        [
          90.0,
          113.0
        ],
        [
          91.0,
          114.0
        ],
        [
          94.5,
          117.5
        ],
        [
          98.0,
          118.5
        ],
        [
          108.0,
          123.5
        ],
        [
          111.5,
          127.0
        ],
        [
          114.0,
          119.5
        ],
        [
          119.5,
          114.0
        ],
        [
          131.5,
          113.5
        ],
        [
          150.0,
          114.5
        ],
        [
          167.5,
          123.5
        ],
        [
          181.0,
          120.5
        ],
        [
          191.0,
          121.0
        ],
        [
          196.0,
          124.5
        ],
        [
          198.5,
          84.5
        ],
        [
          19.5,
          106.5
        ],
        [
          18.0,
          107.0
        ]
      ],
      "fixed_plan_times": [
        0.11058194699995738,
        0.09380063800000471,
        0.11375646799996275,
        0.038212095000005775,
        0.03397331500002565,
        0.25385177500004374
      ]
    },
    {
      "patch": "08OB89_00152",
      "patch_index": 9,
      "planner": "TA*-S+inflate",
      "start": [
        48,
        341
      ],
      "points": [
        [
          278,
          399
        ],
        [
          198,
          398
        ],
        [
          296,
          173
        ],
        [
          183,
          372
        ],
        [
          389,
          117
        ]
      ],
      "order": [
        0,
        4,
        2,
        1,
        5,
        3
      ],
      "stops": [
        [
          183,
          372
        ],
        [
          198,
          398
        ],
        [
          278,
          399
        ],
        [
          389,
          117
        ],
        [
          296,
          173
        ],
        [
          48,
          341
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "7ac08c78f9f11957b449f1625b7a166c2d3c18975bfb6eb3db291dfb776fe4d4",
        "lethal": "569476611522d38cb2a37dd7a31581e779de501dff490e56fe887ac74c1fb588",
        "rock": "a39ec589d5c1e7cf1fb8f817d0e047411c8e6c7a0b3fd9559a3771bf7b65a8d4"
      },
      "prior_signature": {
        "elev": "aafbb2e5214391454aa2888c6350759d726267104c65135b34b8a44a498121fd",
        "lethal": "83ff4866c6d7474aae926d5498e2fb9289f6734ecb152d54b43b5dd785e80a60",
        "rock": "f31bc10da7931780eda075fe9aadcad104962beb2d0ac630ed0c3470f5f009bd"
      },
      "initial_path": [
        [
          24.0,
          170.5
        ],
        [
          24.0,
          173.0
        ],
        [
          29.5,
          178.5
        ],
        [
          55.0,
          180.0
        ],
        [
          56.5,
          180.5
        ],
        [
          61.5,
          179.0
        ],
        [
          67.5,
          179.0
        ],
        [
          85.0,
          181.5
        ],
        [
          90.5,
          186.0
        ],
        [
          91.5,
          186.0
        ],
        [
          94.0,
          192.0
        ],
        [
          95.5,
          193.5
        ],
        [
          96.5,
          194.5
        ],
        [
          97.5,
          195.5
        ],
        [
          99.0,
          199.0
        ],
        [
          100.5,
          199.5
        ],
        [
          102.5,
          199.5
        ],
        [
          103.5,
          198.5
        ],
        [
          104.5,
          198.0
        ],
        [
          114.5,
          198.5
        ],
        [
          117.5,
          198.0
        ],
        [
          128.0,
          199.0
        ],
        [
          133.0,
          198.0
        ],
        [
          137.5,
          198.0
        ],
        [
          138.5,
          199.0
        ],
        [
          139.0,
          199.5
        ],
        [
          141.0,
          198.5
        ],
        [
          144.0,
          196.0
        ],
        [
          150.5,
          189.0
        ],
        [
          158.0,
          183.0
        ],
        [
          161.5,
          180.5
        ],
        [
          165.5,
          146.0
        ],
        [
          194.5,
          82.0
        ],
        [
          194.5,
          58.5
        ],
        [
          173.5,
          77.5
        ],
        [
          166.0,
          84.5
        ],
        [
          148.0,
          86.5
        ],
        [
          85.5,
          122.5
        ],
        [
          79.0,
          127.5
        ],
        [
          69.0,
          140.5
        ],
        [
          52.5,
          154.5
        ],
        [
          43.0,
          156.0
        ],
        [
          41.5,
          157.0
        ],
        [
          34.5,
          163.5
        ],
        [
          25.0,
          169.5
        ],
        [
          24.0,
          170.5
        ]
      ],
      "fixed_plan_times": [
        0.19134659299999157,
        0.028828523999948175,
        0.089138939999998,
        0.5410790139999904,
        0.0800144800000453,
        0.4696421429999873
      ]
    },
    {
      "patch": "08OB89_-0347",
      "patch_index": 10,
      "planner": "TA*-S+inflate",
      "start": [
        55,
        326
      ],
      "points": [
        [
          294,
          224
        ],
        [
          5,
          248
        ],
        [
          164,
          169
        ],
        [
          213,
          144
        ],
        [
          195,
          352
        ]
      ],
      "order": [
        0,
        5,
        1,
        4,
        3,
        2
      ],
      "stops": [
        [
          195,
          352
        ],
        [
          294,
          224
        ],
        [
          213,
          144
        ],
        [
          164,
          169
        ],
        [
          5,
          248
        ],
        [
          55,
          326
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "9bef14761fc310c6ee9e996432c278d3eacb2aa6810a423b14778dcd754eee0b",
        "lethal": "604b8b1c47e6506d4fd34257ccfb4525cef5b2f0b5a99125613220dc6b3792fa",
        "rock": "97aee29b11e415025f724ff0c227af7945f6d890b5c739586c250a9d54bdaca2"
      },
      "prior_signature": {
        "elev": "ecac9095660a758f9efb52f296d0cfcf537eca082e8df4446339084989faf076",
        "lethal": "616ec5d0c56be61768cd4ee0757e9008fce35525f7d5fbfcf38074abdd026491",
        "rock": "bc189b89ffe4726466e714a404498fdaab2f1220dec9b7dda8ee302f10d2dfdf"
      },
      "initial_path": [
        [
          27.5,
          163.0
        ],
        [
          29.5,
          164.0
        ],
        [
          38.5,
          163.0
        ],
        [
          58.5,
          164.0
        ],
        [
          77.0,
          163.5
        ],
        [
          94.5,
          175.5
        ],
        [
          97.5,
          176.0
        ],
        [
          104.5,
          160.5
        ],
        [
          106.0,
          155.0
        ],
        [
          109.5,
          151.0
        ],
        [
          112.5,
          146.5
        ],
        [
          116.5,
          142.5
        ],
        [
          117.5,
          142.5
        ],
        [
          122.5,
          138.5
        ],
        [
          141.5,
          114.5
        ],
        [
          147.0,
          112.0
        ],
        [
          140.0,
          105.0
        ],
        [
          114.0,
          81.0
        ],
        [
          108.5,
          75.0
        ],
        [
          106.5,
          72.0
        ],
        [
          99.0,
          80.0
        ],
        [
          82.0,
          84.5
        ],
        [
          3.0,
          123.5
        ],
        [
          2.5,
          124.0
        ],
        [
          21.5,
          159.0
        ],
        [
          27.5,
          163.0
        ]
      ],
      "fixed_plan_times": [
        0.16473986300002252,
        0.1962867309999865,
        0.07519342500006587,
        0.032569372000011754,
        0.10827681099999609,
        0.0521531760000471
      ]
    },
    {
      "patch": "08OB89_-0847",
      "patch_index": 11,
      "planner": "TA*-S+inflate",
      "start": [
        70,
        146
      ],
      "points": [
        [
          269,
          98
        ],
        [
          75,
          211
        ],
        [
          227,
          332
        ],
        [
          281,
          117
        ],
        [
          350,
          279
        ]
      ],
      "order": [
        0,
        1,
        4,
        5,
        3,
        2
      ],
      "stops": [
        [
          269,
          98
        ],
        [
          281,
          117
        ],
        [
          350,
          279
        ],
        [
          227,
          332
        ],
        [
          75,
          211
        ],
        [
          70,
          146
        ]
      ],
      "planning_status": "planned",
      "blocked_truth": [],
      "blocked_prior": [],
      "truth_signature": {
        "elev": "ec56c5970e0772b0a8a651e6aeb29ae5aedde2fdd2fd616e55fa4a8986f7e153",
        "lethal": "a931a54c08d67cc4e953a21af7a9cc911ef0917fa3a2ec66854e98a137cb0055",
        "rock": "6f2c0c9e9e6ebf92b8c533e5335c2f4fe778591a81eacd26aee19a4211589755"
      },
      "prior_signature": {
        "elev": "b95f74dfd95d40020642542121ae54ae6726638b4d54001d2cbe7f2c5bb7320d",
        "lethal": "3df5176470c9487cef2af37fb0084d12330d6b37c6672889351969f1809055b0",
        "rock": "1319048c6ee1bb2f24933d31835d212ee40aad1e23ed6fec55e7bdf11b93ee2d"
      },
      "initial_path": [
        [
          35.0,
          73.0
        ],
        [
          36.0,
          72.0
        ],
        [
          43.0,
          66.5
        ],
        [
          101.0,
          69.0
        ],
        [
          134.5,
          49.0
        ],
        [
          140.5,
          58.5
        ],
        [
          175.0,
          135.5
        ],
        [
          175.0,
          139.5
        ],
        [
          135.0,
          165.0
        ],
        [
          117.5,
          167.0
        ],
        [
          113.5,
          166.0
        ],
        [
          94.0,
          154.0
        ],
        [
          76.0,
          137.0
        ],
        [
          60.0,
          126.0
        ],
        [
          54.5,
          123.5
        ],
        [
          37.5,
          105.5
        ],
        [
          35.0,
          73.0
        ]
      ],
      "fixed_plan_times": [
        0.21501869500002613,
        0.018038285999978143,
        0.13189775000000736,
        0.08813220599995475,
        0.17027997499997127,
        0.038415327999928195
      ]
    }
  ],
  "input_environment": {
    "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
    "numpy": "2.3.5"
  },
  "cases": [
    {
      "patch": "08OB86_00294",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB86_-0205",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB87_-0706",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB88_-1417",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB88_-0167",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB88_00332",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB88_01832",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB89_00152",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB89_-0347",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    },
    {
      "patch": "08OB89_-0847",
      "mode": "lidar",
      "selected": true,
      "planning_status": "planned",
      "run_folder": null,
      "error": "",
      "termination": null
    }
  ],
  "map_method": "fine",
  "obstacle_resolution_m": 0.1,
  "min_obstacle_points": 3,
  "obstacle_inflation_radius_m": 0.5,
  "obstacle_inflation": "once at 0.1m before coarse overlap; never inflate pooled detections",
  "history": "same last 64 returns per 0.5m height cell as task022; retain fine cell IDs",
  "terrain_visual": "triangle_mesh",
  "terrain_collision": "heightmap",
  "world_input": "task022 actual-run evaluation_reference.npz elevation and unchanged raw masks",
  "real_time_factor": 0.3,
  "stale_timeout_s": 1.0,
  "comparison_baseline": "results/gazebo_lidar/physical_10"
}
```

## 実行したコマンド

```bash
cd conference
python3 -m tests.test_planners
python3 -m tests.test_pointcloud_map_fine
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 10 --map fine --output results/lidar_fine
python3 experiments/lidar_fine_report.py
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/lidar_fine/physical_10 --patch-count 10 --map fine
python3 results/lidar_fine/verification/run_tests.py
python3 -m tests.test_pointcloud_map_fine
python3 results/lidar_fine/verification/plot_fixture.py
```

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-023-mpl XDG_CACHE_HOME=/tmp/thesis-023-cache` を指定した。py_compileとbash -nも成功した。

Docker起動の実際の出力（exit=125）：

```text
docker: Error response from daemon: No such image: thesis/jazzy-gz:1

Run 'docker run --help' for more information
```

## テスト出力の全文

変更前：

```text
all planner tests passed
roll-aware tests passed
```

```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ python3 -m tests.test_footprint
dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed
proximity: analytic line-circle lengths, overlapping unions and tangencies passed
requested LAS case: inflated planner reports no_path without moving endpoints
online: zero radius preserves exact task014 trajectory and planning count
rollover: strict +/-90deg threshold, first time/position and immutable fake records passed
statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)
Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed
comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)
three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)
all footprint and rollover tests passed

exit=0

$ python3 -m tests.test_geo
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
zone VIII reference differences [latitude_deg, longitude_deg]:
-4.25145429972e-09 2.46816966865e-09
-4.06389943919e-09 -3.64556740351e-09
2.36028796508e-09 -3.05306002701e-10
2.78198797332e-10 -4.38916458734e-10
projection round-trip max error [m]: 7.10133463144e-09
geographic sidecars: 13 maps; source axes, coastline anchor, half-cell offset, round trips and NPZ hashes passed
Web APIs: geographic map conversions, unavailable-map response and unchanged legacy metadata/image passed
all geographic conversion tests passed

exit=0

$ python3 -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ python3 -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0

$ python3 -m tests.test_mapfiles_sim
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed
all mapfiles/simulation tests passed

exit=0

$ python3 -m tests.test_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed
parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed
validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed
safety: synthetic/beach_gentle/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_steep/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_scarp/200/100, 5 points, terrain/euclid contact=0
safety: real/08OB87_-0206/200, 5 points, terrain/euclid contact=0
safety: real/08OB88_01332/200, 5 points, terrain/euclid contact=0
API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed
all mission tests passed

exit=0

$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ python3 -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ python3 -m tests.test_online_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
beach_gentle: no-prior/coarse exact trajectory and plan-count parity; contact=0
beach_steep: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB88_01332: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206 stale five-point tour: online contact=0; fixed debris cells= 11
08OB88_01332 stale five-point tour: online contact=0; fixed debris cells= 18
08OB89_-1597 stale five-point tour: online contact=0; fixed debris cells= 6
async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed
follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run
maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed
all online-mission tests passed

exit=0

$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ python3 -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis-023/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0

$ python3 -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: independent full disk, repeated/additive seeds, rectangle-distance radius bound, packed save passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis-023/conference/experiments/lidar_fine_report.py:163: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)

exit=0

$ python3 -m tests.test_real_beach
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
all 60 patches satisfy sea-to-land orientation
08OB86_00294: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_-0205: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0706: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-1417: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0167: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00294: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB86_-0205: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0706: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-1417: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0167: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 0
all real-beach tests passed

exit=0

$ python3 -m tests.test_real_beach_las
data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed
quantized_0.1m_fraction: new_max 0.0035301084084904803 old_min 0.27882342564826246
defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches
08OB86_00294: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_-0205: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB87_-0706: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-1417: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-0167: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_00294: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB86_-0205: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB87_-0706: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-1417: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-0167: exact offline and coarse R5 c10 safety, clean/debris contact=0
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ python3 -m tests.test_ros2_gz
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed
packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed
follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 34.2 0.02959598405434589 0.3173397734180379 0
kinematic True 34.2 0.02959598405434589 0.3173397734180379 0
attitude actual_p95_deg map_p95_deg
roll 0.0 0.0
pitch 0.0 0.0
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 7.7 0.0 0.0 0
kinematic True 7.7 0.0 0.0 0
attitude actual_p95_deg map_p95_deg
roll 0.0 11.309932474020224
pitch 0.0 5.710593137499648
report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)
API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed
worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added
all ROS-free ROS2/Gazebo tests passed

exit=0

$ python3 -m tests.test_thesis_figures

T1
 debris    metric  n    A_median   TAS_median  delta_median              p         p_holm
  False mean_cost 48 0.110342949 0.0767774554 -0.0352167333 7.10542736e-15 5.68434189e-14
  False     climb 48  1.50126915  0.890802236  -0.410943017 7.10542736e-15 5.68434189e-14
  False  p95_roll 48  5.45746622     3.567633   -1.89097743 7.10542736e-15 5.68434189e-14
  False length_xy 48         NaN          NaN   -2.00026809   0.0276182014   0.0552364028
   True mean_cost 48 0.154226921 0.0855587032 -0.0582350381 7.10542736e-15 5.68434189e-14
   True     climb 48  2.07159806   1.30575231  -0.803948405 2.13162821e-14 6.39488462e-14
   True  p95_roll 48  6.86720155   3.63401103   -2.80093993 7.10542736e-15 5.68434189e-14
   True length_xy 48         NaN          NaN  -0.764154874    0.947340222    0.947340222

T2
 radius_m   mode  runs  completed  touching   dJ_median     dJ_p90  replans_median  plan_s_median  plan_s_p95  plan_s_max
        5  fixed    48         48        46   3.8297614 10.8951737               0   0.0943159025 0.513914058  1.09228056
        5 online    48         46         0   1.9542052 10.2738521             101   0.0464642375  0.28593965  1.26618145
       10  fixed    48         48        46   3.8297614 10.8951737               0   0.0960627685 0.506711613  1.25659096
       10 online    48         46         0 0.945069248  6.6029207            94.5   0.0510014495 0.292423272  1.32438343
       15  fixed    48         48        46   3.8297614 10.8951737               0    0.094235528 0.485409814  1.26557115
       15 online    48         47         0 0.688622405 5.29694595              85    0.057362561 0.305458798  1.76405173

T3
                                world         mode  completed  path_lethal_cells  elapsed_s  roll_p95_actual_deg  pitch_p95_actual_deg  roll_p95_map_deg  pitch_p95_map_deg
              file/flat_test_100m.npz offline tour       True                  0    249.412       8.05631294e-09        6.79662109e-10                 0                  0
    file/real_08OB87_-0206_200m_0.npz offline tour       True                  0      348.2           4.76005563            6.20167607        4.58473933         6.31735413
file/real_las_08OB87_-0206_200m_0.npz offline tour       True                  0    289.516           3.83941424            2.47900287        3.84957483         2.58651471
       real_las_08OB87_-0206 / debris        fixed      False                  0      96.15           4.54713144            5.69114628        5.33797683         6.55378208
       real_las_08OB87_-0206 / debris       online       True                  0     190.95           4.31378469            4.21973305        4.30333238         3.67841423
thesis: F1-F7 PDF/PNG, T1-T3 LaTeX/Markdown and numbers.tex generated
statistics: 48 paired beaches, size means, medians and archived contact counts verified
outputs: no excluded measurement columns or values; all thesis figure tests passed

exit=0

$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ python3 -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0
```

```text
test_beach_terrain exit=0
test_collision exit=0
test_dstar exit=0
test_footprint exit=0
test_geo exit=0
test_gz_compare exit=0
test_gz_online_batch exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_deadend exit=0
test_online_mission exit=0
test_planners exit=0
test_pointcloud_map exit=0
test_pointcloud_map_fine exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

最終の新方式・選択・比較の確認：

```text
/workspace/thesis-023/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: independent full disk, repeated/additive seeds, rectangle-distance radius bound, packed save passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)
```

バイト比較では、旧方式の計測時間は時計を固定する。manifestは機械固有のPython/NumPy欄を同じ実行環境の値へ合わせ、それ以外の全バイトを元のスナップショットと比較する。実走の時刻・浮動小数の軌跡を決定的と主張するものではない。

## 集計表（スクリプト出力をそのまま）

保存済みの021の2条件と022のLiDARはその値を保持し、旧LiDARの地図だけを追加で監査した。fineは未実行。

```text
Task023: fixed / perfect R10 / task022 LiDAR / fine-grid LiDAR; identical ten-beach cohort.
First three methods are cached measurements. New fine-grid physical outcomes are 未実行 when missing.
       patch   mode    status map_seen_cells map_lethal_cells truth_lethal_cells map_fp_cells map_fn_cells map_fp_box_adjacent_cells detected_obstacle_cells detector_fp_cells detector_fn_cells detector_fp_box_adjacent_cells  map_update_s_median  map_update_s_p95  map_update_s_max debris_cells
08OB86_00294  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB86_00294 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB86_-0205  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB86_-0205 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB87_-0706  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB87_-0706 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_-1417  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_-1417 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB88_-0167  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_-0167 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_00332  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_00332 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_01832  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_01832 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_00152  fixed  rollover           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_00152 online  rollover           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_-0347  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB89_-0347 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_-0847  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            2
08OB89_-0847 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB86_00294  lidar completed          79882            19909              18975          939            5                        25                     760               601                 1                            404            0.0838974          0.156605          0.594992            0
08OB86_-0205  lidar completed          39575             7837               6888          958            9                        39                     752               601                 1                            370            0.0886842          0.117759          0.280268            0
08OB87_-0706  lidar completed          75398            10179               8480         1725           26                        31                    1448              1119                 0                            752             0.086177          0.173824          0.580021            0
08OB88_-1417  lidar   no_path          19490             1064                691          374            1                        19                     333               249                 2                            180            0.0849492          0.120034          0.408273            0
08OB88_-0167  lidar   no_path          58426             7273               5139         2149           15                        11                    1106               895                 1                            567            0.0878073            0.1176          0.732807            0
08OB88_00332  lidar completed          39025             9148               6980         2180           12                        22                    1233              1014                 1                            633            0.0991531          0.134696          0.309379            0
08OB88_01832  lidar  rollover          43762             1878                147         1737            6                         8                     157               113                 0                             78             0.081546          0.120131          0.306029            0
08OB89_00152  lidar  rollover          27105             2583                255         2335            7                         0                     293               234                 0                            157            0.0852749          0.125799          0.565805            0
08OB89_-0347  lidar   no_path          44732             1824                765         1070           11                        12                     779               600                 1                            403            0.0948189           0.12949          0.684387            0
08OB89_-0847  lidar   no_path          31921            11593              10378         1218            3                         6                     866               711                 0                            454             0.095285          0.129591          0.757749            0
08OB86_00294   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB86_-0205   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB87_-0706   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_-1417   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_-0167   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_00332   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_01832   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB89_00152   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB89_-0347   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB89_-0847   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None

Counts and per-run metric medians; all contact counts use recorded centre trajectories.
  mode execution  scheduled  executed  unexecuted  completed  stuck  rollover  no_path  timeout  runtime_error  incomplete_waypoints  debris_audited_runs  debris_touching_runs  map_seen_cells_median  map_lethal_cells_median  truth_lethal_cells_median  map_fp_cells_median  map_fn_cells_median  map_fp_box_adjacent_cells_median  clearance_fp_cells_median  clearance_fn_cells_median  detected_obstacle_cells_median  truth_obstacle_cells_median  detector_fp_cells_median  detector_fn_cells_median  detector_fp_box_adjacent_cells_median  detector_on_unusable_cells_median  map_update_s_median_median  map_update_s_p95_median  map_update_s_max_median
 fixed      記録あり         10        10           0          0      9         1        0        0              0                     0                   10                     3                    NaN                      NaN                        NaN                  NaN                  NaN                               NaN                        NaN                        NaN                             NaN                          NaN                       NaN                       NaN                                    NaN                                NaN                         NaN                      NaN                      NaN
online      記録あり         10        10           0          9      0         1        0        0              0                     0                   10                     2                    NaN                      NaN                        NaN                  NaN                  NaN                               NaN                        NaN                        NaN                             NaN                          NaN                       NaN                       NaN                                    NaN                                NaN                         NaN                      NaN                      NaN
 lidar      記録あり         10        10           0          4      0         2        4        0              0                     0                   10                     0                41668.5                     7555                     6013.5               1471.5                    8                              15.5                       1388                         30                           769.5                        157.5                       601                         1                                  403.5                              161.5                   0.0869922                 0.127645                 0.572913
  fine       未実行         10         0          10        NaN    NaN       NaN      NaN      NaN            NaN                   NaN                    0                   NaN                    NaN                      NaN                        NaN                  NaN                  NaN                               NaN                        NaN                        NaN                             NaN                          NaN                       NaN                       NaN                                    NaN                                NaN                         NaN                      NaN                      NaN
Map FP/FN use unique seen cells against original truth lethal; CSV also reports same-steep-clearance FP/FN.
Detector FP/FN compare uninflated detections to raw obstacles, excluding water/nodata; these differ from final lethal FP/FN.
Box adjacency is one four-connected cell outside the actual exported component bounding rectangles.
Missing task021 map snapshots are unrecorded, not zero. New fine-grid values are not inferred from fixtures.
Grid=0.1m, height threshold=0.3m, cluster=3, radius=0.5m were fixed in advance; no tuning or hypothesis tests.
```

## 指標の意味

`map_*` は最終lethalを元のtruth lethalと比較した、観測済みの一意な粗セルでのFP/FNである。
CSVの `clearance_*` には、真値にも同じ急斜面の膨張を入れた参照とのFP/FNを併記する。意図した安全余裕まで誤りと解釈しないためである。

`detector_*` は膨張前の検出を生の障害物と比較した指標で、水・欠損を除く。既に事前地図にある障害物も含むため、点群検出器の見落としと最終lethalの見落としは同じではない。
箱の領域はexport_gazeboと同じ連結成分の外接長方形。その外側で4方向に1粗セルだけ隣接する領域を `*_box_adjacent_cells` とする。
022の約7割という原因分析は主に膨張前の検出についてのものなので、最終lethalのFPと区別して表示する。

021の2条件には最終の点群地図スナップショットがないため、地図誤りの欄は未記録とし、0を入れない。
観測した範囲は走行ごとに異なる。件数だけで精度の優劣を断定しない。
漂着物への接触は記録された中心軌跡によるため、車体前端の接触を過少評価する。
地図更新時間は走行ごとの中央値・95%・最大と、その走行単位の集計であり、計画時間とは別である。

## 合成箱の確認図

[箱の境界と通行不可セル](box_fixture.png)。固定シード100の合成入力で、実機やGazeboの走査/遮蔽ではない。箱の外側のセル数は正常な安全余白も含み、FP件数と同義ではない。図は目視確認した。

```text
Synthetic fixture outside lethal cells: [('022 coarse', 12), ('023 fine', 8)]
```

## 既存ファイルの保持と実行環境

既存の変更は、既定動作を維持する選択引数を加えた3つのROS用ファイルに限定する。pointcloud_map.py、traversability.py、footprint.py、online_mission.py、経路計画とコスト式、および全ての既存結果・地図・world・データは変更していない。既存テストの削除・弱体化は行っていない。

```json
{
  "original_files": 2412,
  "changed": [
    "conference/ros2_jazzy/gz_checks/lidar_checks.py",
    "conference/ros2_jazzy/gz_checks/lidar_planner.py",
    "conference/ros2_jazzy/gz_checks/run_lidar_checks.sh"
  ],
  "unchanged_original_files": 2409,
  "reason": "Only opt-in selection/argument forwarding in three ROS files. Legacy core, costs, source data and all old results remain byte-identical."
}
```

```json
{
  "client_date": "2026-11-05",
  "base": "6d0ae7dc733202b41b92df3c37f62e5a246426bc",
  "branch": "codex/023-lidar-fine-grid",
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "platform": "Linux-6.18.57-x86_64-with-glibc2.41",
  "versions": {
    "numpy": "2.3.5",
    "scipy": "1.17.0",
    "pandas": "2.2.3",
    "matplotlib": "3.10.8"
  },
  "fine_resolution_m": 0.1,
  "coarse_resolution_m": 0.5,
  "obstacle_height_m": 0.3,
  "min_obstacle_points": 3,
  "radius_m": 0.5,
  "parameter_selection": "none: all four values prescribed before implementation",
  "history": "same 64 returns per coarse height cell, retaining fine IDs; same temporal window",
  "geometry": "fine-cell-centre radius disk, union of raw-seed dilations, then 5x5 any-overlap pooling",
  "synthetic_box": "0.4m high; sides on coarse cell borders; radial Gaussian sigma0.02m; seeds100..104; not Gazebo",
  "real_time_factor": 0.3,
  "stale_timeout_s": 1.0,
  "terrain_visual": "triangle_mesh",
  "fine_physical_runs": 0,
  "source_sha256": {
    "tapp/pointcloud_map_fine.py": "361014fadd3223fa19cf2c6491b862598801d039b0e41ec11a5a158aaad725b4",
    "tapp/pointcloud_map.py": "c385c4c90d4b6eb5cf2107a0ece8c79f33d06ca814b34b813dc7e10791c94c99",
    "tapp/traversability.py": "b655d1b97aef36a74a636bb1ff5089b421f9f5ef1aa8a3e489ac024d4597d9c2",
    "tapp/footprint.py": "2dcfd352570fbbcd9666439dbfeecd1d98fc911e083ff5f489d1a6c7739b1b4e",
    "tapp/online_mission.py": "cb6256d33524a7121a79c4cb12e406b3be32f741bc072ebb4eb01481935882b9",
    "tapp/config.py": "5c4cfe860b16f2d4540e970f2ca19a634f563a24deb361d0e85b7daa6e6c7895",
    "experiments/lidar_fine_report.py": "5482571ad590bcb270ad1551f0b773066ebff3b49b43867761192df31f861461",
    "tests/test_pointcloud_map_fine.py": "bca704d3c66c3fdc089ca8a49208daa47e87a6a9c893d709a0e46e7b012de306",
    "ros2_jazzy/gz_checks/lidar_checks.py": "1129631011731b2b17c41a1d0b993b1972b1c95eaf55745b7d16db9f38c491da",
    "ros2_jazzy/gz_checks/lidar_planner.py": "35f47b86293e653eac6dd464adbe0e235ca55e7e75e1035225ed571a0524a607",
    "ros2_jazzy/gz_checks/lidar_map.py": "d65031fa1b5490ff06b3f9db551bcb63dd50324872dd20e40053e60ca89d2a78",
    "ros2_jazzy/gz_checks/run_lidar_checks.sh": "46a2ff67129cade45aa9684f8c94a766e3d649a92546f32cdfcdc481344bf218",
    "ros2_jazzy/gz_checks/terrain_mesh.py": "fb6073250c52e9c50e65c83b0d4024b9280ed4f87a8fd41dc4b307ba24aa1be8",
    "results/lidar_fine/verification/plot_fixture.py": "9a75279b23a1082a8896f044b0e88959fac74d1c8b60f59f07c82bb4d2c06cbf"
  }
}
```

## できなかったこと・確認してほしいこと

**新しいfine方式のGazebo実走は未実行**。通常のDockerラッパーは標準イメージ `thesis/jazzy-gz:1` がなくexit=125で終了した。
新方式の完走・経路なし・誤検出・見落とし・更新時間・接触の実測値はない。表の空欄/NaNを0として扱わない。
合成箱の外側セルが減った結果を、10地形の完走率改善や実機の安全性へ置き換えていない。

細セル内に3点を要求するため、疎な物体や側面の検出を落とす可能性がある。逆に、同じ場所の雑音が繰り返し蓄積すれば外側の細セルが検出される場合もある。
中央値の高さによる急斜面や誤った地面高さ、古い地面基準の限界、観測されない場所のsoft prior、地図境界の転倒は今回変更していない。
細格子化のCPU・メモリ負荷と、点群の取りこぼしも実走では未評価である。

Claudeには、READMEのコマンドで新方式だけを走らせ、022と同じworld/地点/設定を確認した上で、通路の閉塞、見落とし、箱の隣のFP、更新時間、取りこぼしを確認してほしい。
10地形の検定・エネルギー集計は行わない。境界の転倒を除外したり、地点・パラメータを変えて結果を良くしたりしていない。

通常Dockerの実行コマンド、保存形式、粗セル領域の定義、指標の詳細は [README_ja.md](README_ja.md) に記載した。

## 提出状態

ブランチ `codex/023-lidar-fine-grid` をoriginへpush済み。マージは行っていない。
実装のコミットは `7bc4a16`（LiDAR障害物を細格子で判定し膨張を一度だけにする）。

PRは未作成。`gh pr create`（GraphQL）、RESTによる作成、サンドボックス外でのREST再試行のいずれも、
GitHub APIへのPOSTが `Forbidden` で拒否された。実際の出力は次に保存した。

- `verification/pr_create_log.txt`
- `verification/pr_rest_log.txt`
- `verification/pr_rest_retry_log.txt`

日本語のPR説明は [PR_DESCRIPTION_ja.md](PR_DESCRIPTION_ja.md) に保存した。
向き先は `realtime-map`、作業ブランチは `codex/023-lidar-fine-grid`。
[GitHubの比較・PR作成画面](https://github.com/tako-1012/thesis_Bunker/compare/realtime-map...codex/023-lidar-fine-grid?expand=1) から作成できる。

全23テストは成功。新方式のGazebo実走は、通常Dockerイメージ `thesis/jazzy-gz:1` がないため未実行。
後で実走するコマンドは [README_ja.md](README_ja.md) に記載した。


## 変更ファイル一覧

- `conference/experiments/lidar_fine_report.py`
- `conference/results/lidar_fine/PR_DESCRIPTION_ja.md`
- `conference/results/lidar_fine/README_ja.md`
- `conference/results/lidar_fine/REPORT_ja.md`
- `conference/results/lidar_fine/SUBMISSION_ja.md`
- `conference/results/lidar_fine/box_fixture.png`
- `conference/results/lidar_fine/changed_files.txt`
- `conference/results/lidar_fine/input_audit.json`
- `conference/results/lidar_fine/lidar_fine_log.txt`
- `conference/results/lidar_fine/manifest.json`
- `conference/results/lidar_fine/runs.csv`
- `conference/results/lidar_fine/summary.csv`
- `conference/results/lidar_fine/verification/all_tests_log.txt`
- `conference/results/lidar_fine/verification/baseline_sha256.json`
- `conference/results/lidar_fine/verification/build_report.py`
- `conference/results/lidar_fine/verification/docker_launcher_log.txt`
- `conference/results/lidar_fine/verification/legacy_manifest_before.json`
- `conference/results/lidar_fine/verification/planners_before_log.txt`
- `conference/results/lidar_fine/verification/plot_fixture.py`
- `conference/results/lidar_fine/verification/plot_fixture_log.txt`
- `conference/results/lidar_fine/verification/pr_create_log.txt`
- `conference/results/lidar_fine/verification/pr_rest_log.txt`
- `conference/results/lidar_fine/verification/pr_rest_retry_log.txt`
- `conference/results/lidar_fine/verification/prepare_console_log.txt`
- `conference/results/lidar_fine/verification/preservation_audit.json`
- `conference/results/lidar_fine/verification/protocol.json`
- `conference/results/lidar_fine/verification/report_console_log.txt`
- `conference/results/lidar_fine/verification/run_tests.py`
- `conference/results/lidar_fine/verification/test_beach_terrain_log.txt`
- `conference/results/lidar_fine/verification/test_collision_log.txt`
- `conference/results/lidar_fine/verification/test_dstar_log.txt`
- `conference/results/lidar_fine/verification/test_fine_final_log.txt`
- `conference/results/lidar_fine/verification/test_fine_initial_log.txt`
- `conference/results/lidar_fine/verification/test_footprint_log.txt`
- `conference/results/lidar_fine/verification/test_geo_log.txt`
- `conference/results/lidar_fine/verification/test_gz_compare_log.txt`
- `conference/results/lidar_fine/verification/test_gz_online_batch_log.txt`
- `conference/results/lidar_fine/verification/test_mapfiles_sim_log.txt`
- `conference/results/lidar_fine/verification/test_mission_log.txt`
- `conference/results/lidar_fine/verification/test_natural_terrain_log.txt`
- `conference/results/lidar_fine/verification/test_online_deadend_log.txt`
- `conference/results/lidar_fine/verification/test_online_log.txt`
- `conference/results/lidar_fine/verification/test_online_mission_log.txt`
- `conference/results/lidar_fine/verification/test_planners_log.txt`
- `conference/results/lidar_fine/verification/test_pointcloud_map_fine_log.txt`
- `conference/results/lidar_fine/verification/test_pointcloud_map_log.txt`
- `conference/results/lidar_fine/verification/test_real_beach_las_log.txt`
- `conference/results/lidar_fine/verification/test_real_beach_log.txt`
- `conference/results/lidar_fine/verification/test_risk_prior_log.txt`
- `conference/results/lidar_fine/verification/test_ros2_gz_log.txt`
- `conference/results/lidar_fine/verification/test_summary.txt`
- `conference/results/lidar_fine/verification/test_thesis_figures_log.txt`
- `conference/results/lidar_fine/verification/test_tour_log.txt`
- `conference/results/lidar_fine/verification/test_visibility_log.txt`
- `conference/ros2_jazzy/gz_checks/lidar_checks.py`
- `conference/ros2_jazzy/gz_checks/lidar_map.py`
- `conference/ros2_jazzy/gz_checks/lidar_planner.py`
- `conference/ros2_jazzy/gz_checks/run_lidar_checks.sh`
- `conference/tapp/pointcloud_map_fine.py`
- `conference/tasks/023_lidar_fine_grid.md`
- `conference/tests/test_pointcloud_map_fine.py`


## 追記：粗セル中心から障害物セルの端までの距離で判定

この追記が現行の実装を説明する。上記の方法・図・出力・SHA-256は `a6bf889` 時点の記録として保持した。既存の数値やファイルは再生成していない。

### 変更の理由と範囲

経路計画でロボットの中心を粗セルの中心とみなすため、粗セルの領域が膨張マスクに少しでも重なることを禁止条件にすると、余分な粗セルまで通行不可になる。
`PointCloudMapFine._add_obstacles` の膨張後の集約を、粗セル中心の距離判定へ変更した。
`detected_obstacle = coarse_overlap(self.fine_obstacle)` はそのまま。0.1m・0.3m・3点・0.5mは変更・調整していない。
022の方式、地面の高さ、コスト、急斜面の膨張、ROS用の選択引数、経路計画は変更していない。

### セルの端と境界の扱い

障害物の細セルは、中心から各軸±0.05mの**閉じた正方形**として扱う。粗セル中心と障害物の細セル中心の差を各軸Δx、Δyとすると、
最も近い端または角までの距離は `sqrt(max(abs(Δx)-0.05,0)^2 + max(abs(Δy)-0.05,0)^2)`。
これが0.5m以下なら通行不可で、円とセルがちょうど接する場合も含む。障害物セル中心までの距離ではない。

粗セルの中心は、5×5分割した細セルの中央と一致する。円と正方形の距離を表す構造要素で、生の障害物を1回だけ膨張し、
`fine_inflated[2::5, 2::5]` の値を選ぶ。粗セルの領域に対するany集約を使わない。
距離計算を0.05m単位の整数座標で表し、各軸の距離 `max(2*abs(offset)-1,0)` の二乗和を100以下と判定する。
これにより、斜めの角も含めて正方形までの距離をそのまま判定する。EDTの中心間距離から一律0.05mを引く近似は使わない。
既に膨張した結果を再膨張させず、新しい生の障害物に対する結果との和を取る。

点の細セルへの割り当ては従来のfloor式とclipを変更していない。数学的には境界の正方向のセルへ割り当てる半開区間で、
浮動小数の丸めによる境界直近の割り当ても従来のまま。一方、衝突の距離計算では割り当てられたセルの両端を含める。
地図の端では配列外へ折り返さずに切り取り、観測のない外側セルを新たに作らない。

### テストで変更した期待値

- `test_noisy_box`：膨張済み細格子のany集約を期待する式を、全障害物の正方形と全粗セル中心との距離を列挙する独立の参照計算へ変更した。高さ・コスト・seenのバイト一致、中心の検出、022より外側セルが少ないことは引き続き確認する。
- `test_one_dilation`：細セル中心からの円盤と粗セル領域間の距離を期待していた部分を、障害物正方形の端までの距離と粗セル中心の判定へ変更した。繰り返し・追加の観測で二重に膨張しないことと保存マスクの検証は保持した。
- `test_side_spill_and_centre_clearance` を追加：箱の側面の点が隣セル内の0.1mの細セルを占めても、次の粗セル中心が0.5mより遠ければ通れることを確認した。全25通りの細セルの位置、地図の四隅、斜め方向について、半径内の中心を含めたマスク全体を独立計算と完全一致で比較する。
- 既存の他のテストファイルは変更していない。022の既定/明示選択で出力バイトが一致する確認も成功した。

### 箱周辺の通行不可セル数：変更前後を実行して比較

`a6bf889` の `pointcloud_map_fine.py` をGitから読み、変更後と同じ点群をそれぞれ処理した。
`before_total/after_total` は通行不可セルの総数、`*_outside` は真の箱の中心セル(10,10)を除いた数。
`*_next_cell` は中心(6.0,5.0)mの粗セル(12,10)の通行不可判定。
数値はすべて下記スクリプトを実行して得た。実機/Gazeboの値やFPの件数ではない。

```text
Synthetic inputs only; not Gazebo measurements. Before = exact a6bf889c763484640bda6139e6291d2492d191ff mapper.
Outside excludes the true box centre cell (10,10); next cell is (12,10), centre (6.0,5.0)m.
fixture,before_total,after_total,before_outside,after_outside,before_next_cell,after_next_cell
noisy_box_100,9,9,8,8,False,False
noisy_box_101,9,9,8,8,False,False
noisy_box_102,9,9,8,8,False,False
noisy_box_103,9,9,8,8,False,False
noisy_box_104,9,9,8,8,False,False
side_spill_0.1m,7,4,6,3,True,False
Height, cost, seen and detected obstacle bytes are unchanged on every fixture.
```

元のノイズ付き箱の5ケースではセル数に変化がなかった。追加した0.1mはみ出しの回帰ケースで、次の粗セルが通れることを確認した。
比較した全入力で、高さ・コスト・seen・障害物そのものの粗格子/細格子のバイトは変更前後で一致した。

### 実行コマンドとテストの出力全文

変更前に `cd conference && python3 -m tests.test_planners` を実行し、出力は次のとおりだった。

```text
all planner tests passed
roll-aware tests passed
```

続いて以下を実行した。Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-023-mpl XDG_CACHE_HOME=/tmp/thesis-023-cache` を指定した。

```bash
cd conference
python3 -m tests.test_pointcloud_map_fine
python3 results/lidar_fine/center_update/compare_boxes.py
python3 results/lidar_fine/center_update/run_tests.py
python3 results/lidar_fine/center_update/append_report.py
```

最初の集中確認の出力全文：

```text
/workspace/thesis-023/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)
```

全テストの出力全文：

```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ python3 -m tests.test_footprint
dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed
proximity: analytic line-circle lengths, overlapping unions and tangencies passed
requested LAS case: inflated planner reports no_path without moving endpoints
online: zero radius preserves exact task014 trajectory and planning count
rollover: strict +/-90deg threshold, first time/position and immutable fake records passed
statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)
Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed
comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)
three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)
all footprint and rollover tests passed

exit=0

$ python3 -m tests.test_geo
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
zone VIII reference differences [latitude_deg, longitude_deg]:
-4.25145429972e-09 2.46816966865e-09
-4.06389943919e-09 -3.64556740351e-09
2.36028796508e-09 -3.05306002701e-10
2.78198797332e-10 -4.38916458734e-10
projection round-trip max error [m]: 7.10133463144e-09
geographic sidecars: 13 maps; source axes, coastline anchor, half-cell offset, round trips and NPZ hashes passed
Web APIs: geographic map conversions, unavailable-map response and unchanged legacy metadata/image passed
all geographic conversion tests passed

exit=0

$ python3 -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ python3 -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0

$ python3 -m tests.test_mapfiles_sim
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed
all mapfiles/simulation tests passed

exit=0

$ python3 -m tests.test_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed
parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed
validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed
safety: synthetic/beach_gentle/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_steep/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_scarp/200/100, 5 points, terrain/euclid contact=0
safety: real/08OB87_-0206/200, 5 points, terrain/euclid contact=0
safety: real/08OB88_01332/200, 5 points, terrain/euclid contact=0
API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed
all mission tests passed

exit=0

$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ python3 -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ python3 -m tests.test_online_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
beach_gentle: no-prior/coarse exact trajectory and plan-count parity; contact=0
beach_steep: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB88_01332: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206 stale five-point tour: online contact=0; fixed debris cells= 11
08OB88_01332 stale five-point tour: online contact=0; fixed debris cells= 18
08OB89_-1597 stale five-point tour: online contact=0; fixed debris cells= 6
async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed
follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run
maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed
all online-mission tests passed

exit=0

$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ python3 -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis-023/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0

$ python3 -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis-023/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)

exit=0

$ python3 -m tests.test_real_beach
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
all 60 patches satisfy sea-to-land orientation
08OB86_00294: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_-0205: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0706: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-1417: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0167: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00294: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB86_-0205: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0706: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-1417: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0167: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 0
all real-beach tests passed

exit=0

$ python3 -m tests.test_real_beach_las
data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed
quantized_0.1m_fraction: new_max 0.0035301084084904803 old_min 0.27882342564826246
defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches
08OB86_00294: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_-0205: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB87_-0706: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-1417: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-0167: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_00294: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB86_-0205: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB87_-0706: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-1417: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-0167: exact offline and coarse R5 c10 safety, clean/debris contact=0
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ python3 -m tests.test_ros2_gz
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed
packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed
follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 34.2 0.02959598405434589 0.3173397734180379 0
kinematic True 34.2 0.02959598405434589 0.3173397734180379 0
attitude actual_p95_deg map_p95_deg
roll 0.0 0.0
pitch 0.0 0.0
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 7.7 0.0 0.0 0
kinematic True 7.7 0.0 0.0 0
attitude actual_p95_deg map_p95_deg
roll 0.0 11.309932474020224
pitch 0.0 5.710593137499648
report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)
API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed
worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added
all ROS-free ROS2/Gazebo tests passed

exit=0

$ python3 -m tests.test_thesis_figures

T1
 debris    metric  n    A_median   TAS_median  delta_median              p         p_holm
  False mean_cost 48 0.110342949 0.0767774554 -0.0352167333 7.10542736e-15 5.68434189e-14
  False     climb 48  1.50126915  0.890802236  -0.410943017 7.10542736e-15 5.68434189e-14
  False  p95_roll 48  5.45746622     3.567633   -1.89097743 7.10542736e-15 5.68434189e-14
  False length_xy 48         NaN          NaN   -2.00026809   0.0276182014   0.0552364028
   True mean_cost 48 0.154226921 0.0855587032 -0.0582350381 7.10542736e-15 5.68434189e-14
   True     climb 48  2.07159806   1.30575231  -0.803948405 2.13162821e-14 6.39488462e-14
   True  p95_roll 48  6.86720155   3.63401103   -2.80093993 7.10542736e-15 5.68434189e-14
   True length_xy 48         NaN          NaN  -0.764154874    0.947340222    0.947340222

T2
 radius_m   mode  runs  completed  touching   dJ_median     dJ_p90  replans_median  plan_s_median  plan_s_p95  plan_s_max
        5  fixed    48         48        46   3.8297614 10.8951737               0   0.0943159025 0.513914058  1.09228056
        5 online    48         46         0   1.9542052 10.2738521             101   0.0464642375  0.28593965  1.26618145
       10  fixed    48         48        46   3.8297614 10.8951737               0   0.0960627685 0.506711613  1.25659096
       10 online    48         46         0 0.945069248  6.6029207            94.5   0.0510014495 0.292423272  1.32438343
       15  fixed    48         48        46   3.8297614 10.8951737               0    0.094235528 0.485409814  1.26557115
       15 online    48         47         0 0.688622405 5.29694595              85    0.057362561 0.305458798  1.76405173

T3
                                world         mode  completed  path_lethal_cells  elapsed_s  roll_p95_actual_deg  pitch_p95_actual_deg  roll_p95_map_deg  pitch_p95_map_deg
              file/flat_test_100m.npz offline tour       True                  0    249.412       8.05631294e-09        6.79662109e-10                 0                  0
    file/real_08OB87_-0206_200m_0.npz offline tour       True                  0      348.2           4.76005563            6.20167607        4.58473933         6.31735413
file/real_las_08OB87_-0206_200m_0.npz offline tour       True                  0    289.516           3.83941424            2.47900287        3.84957483         2.58651471
       real_las_08OB87_-0206 / debris        fixed      False                  0      96.15           4.54713144            5.69114628        5.33797683         6.55378208
       real_las_08OB87_-0206 / debris       online       True                  0     190.95           4.31378469            4.21973305        4.30333238         3.67841423
thesis: F1-F7 PDF/PNG, T1-T3 LaTeX/Markdown and numbers.tex generated
statistics: 48 paired beaches, size means, medians and archived contact counts verified
outputs: no excluded measurement columns or values; all thesis figure tests passed

exit=0

$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ python3 -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0
```

```text
test_beach_terrain exit=0
test_collision exit=0
test_dstar exit=0
test_footprint exit=0
test_geo exit=0
test_gz_compare exit=0
test_gz_online_batch exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_deadend exit=0
test_online_mission exit=0
test_planners exit=0
test_pointcloud_map exit=0
test_pointcloud_map_fine exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

### 既存ファイルの保持と現在のソース

```text
{
  "base": "a6bf889c763484640bda6139e6291d2492d191ff",
  "original_tracked_files": 3884,
  "permitted_existing_changes": [
    "conference/tapp/pointcloud_map_fine.py",
    "conference/tests/test_pointcloud_map_fine.py",
    "conference/results/lidar_fine/REPORT_ja.md"
  ],
  "other_original_files_unchanged": true,
  "previous_report_is_byte_identical_prefix": true,
  "old_results_unchanged": "All previous result files except the explicitly requested REPORT_ja.md append"
}
```

```text
{
  "base": "a6bf889c763484640bda6139e6291d2492d191ff",
  "branch": "codex/023-lidar-fine-grid",
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "numpy": "2.3.5",
  "scipy": "1.17.0",
  "fine_resolution_m": 0.1,
  "obstacle_height_m": 0.3,
  "min_obstacle_points": 3,
  "robot_radius_m": 0.5,
  "criterion": "coarse centre to nearest point on closed raw fine-cell square <= 0.5m",
  "contact_boundary": "inclusive; exact integer half-fine-cell coordinate comparison",
  "parameter_tuning": false,
  "new_gazebo_runs": 0,
  "source_sha256": {
    "conference/tapp/pointcloud_map_fine.py": "59d936881b8b5354dc4248ead8b9d1b105e5da1ef5fa09c6b5c900a67992abbf",
    "conference/tests/test_pointcloud_map_fine.py": "adc48a34bb405f6787d62a5538d1e8b47df62d32b64a7fcc4fb49b26508e3ab2"
  }
}
```

### 未実行・確認してほしいこと

今回もGazebo実走は実施していない。完走率・実走の誤検出・更新時間への影響は未測定で、合成箱の結果から補っていない。
保存済みのmanifest、図、比較表、旧プロトコルは修正前の記録として残した。現在の細格子の幾何とソースハッシュはこの追記と `center_update/protocol.json` を参照する。
Claudeには実走時に、同じ10地形・world・地点・速さ・途切れ期限を保ち、特に閉塞した通路と疎な障害物の見落としを確認してほしい。
同じ作業ブランチを更新し、マージは行わない。
