# 指示書024：最新realtime-map上での10m余白の実装・検証

作業ブランチ：`未確定（既存の同名ブランチを保持し、push先を確認待ち）`。実装・検証コミット：`fec264009f6cc741fbb22c20038b490e827a41f7`。土台：`14bcae7abef57dcc4d7767993a86ef9c3252b8b4`（作業開始時の最新realtime-map）。

Pythonの全28テストモジュールが成功した。今回Gazebo・実際のDockerは起動していない。

## 実装

旧実装 `e29320c` を最新の土台へ移植した。旧ブランチ・既存の未追跡ログは変更せず、別の作業領域を使った。過去の報告は `REPORT_2026-11-06_ja.md` に残した。
過去に記録されたDocker起動失敗は旧報告の履歴であり、今回の実行ではない。今回の準備結果と全テストは `refresh/` に保存した。

- `tapp/tour.py`：`sample_waypoints(..., edge_margin_m=0.0)`。同じ候補の順列から余白未満の候補だけを除き、距離・到達可能性の条件と既定の乱数順を維持する。
- `ros2_jazzy/gz_checks/edge_margin_checks.py`：同じ10か所の新旧地点を比較し、開始点が10m未満ならずらさず対象外。旧地点と同じ5か所の記録は再利用し、変更した5か所だけ4方式の再走行を依頼する。
- `run_edge_margin_checks.sh`：研究PCの通常Docker用。ソースは読み取り専用、build/worldは一時領域、新しい記録だけを書き込む。既存のmanifestの上書きは拒否する。
- `online_batch_checks.py` と `lidar_checks.py`：明示的に与えたシナリオと砂浜の集合だけを渡せる引数を追加。既定は変更しない。最新のground_estimate、endpoint_policy、実機センサー、THESIS_ONLY_PATCHの選択を維持し、選択集合はその選択との共通部分にした。親の集計を使う場合だけ子の集計を省略する。
- `experiments/edge_margin_report.py`：40行を再利用・再走行・未実行で区別し、既存の指標を集計する。検定・エネルギー集計は行わず、両方式が完走した同じ砂浜だけで対の差の中央値を計算する。実走がない砂浜の軌跡図は作らない。
- `tests/test_edge_margin.py`：既定と明示0のバイト一致、10か所の12点の余白・間隔・到達可能性、開始点の対象外、再利用metadataの完全一致、混合記録の集計、起動先の振り分け、ラッパーを検証する。Dockerは偽物の引数記録コマンドで、実際には起動しない。

**10mは事前に決めた値で、調整していない。** 仮想センサーのR=10mに由来する。0は互換性テストにだけ使い、他の正の余白は試していない。
距離は外側のセル中心（400セルでは0〜199.5m）を基準とし、10mちょうどを許可する。heightmapの外周より内側の保守的な基準である。
同じSeedSequenceから12点を引き、最初の5点を使う。開始点・順序の決め方・TA*-S＋膨張0.5m・コスト・worldは変えない。
LiDARの2方式は旧022の標高配列を共用し、見た目のmesh・速度0.3倍・途切れの基準1.0秒をmanifestへ記録する。ground_estimateは既定のall_returns、endpoint_policyは既定のnoneのまま比較する。

## 地点の比較と4方式の表（表示をそのまま）

地点が変わる砂浜：`08OB86_00294`, `08OB87_-0706`, `08OB88_01832`, `08OB89_00152`, `08OB89_-0347`。開始点は全10か所で条件を満たし、対象外はなかった。

```text
Task024: fixed 10m edge margin, same ten LAS test patches, four methods; no tuning.
Distance uses outermost grid centres [0,199.5]m; start is never moved.
Waypoint audit: old/new cell coordinates and edge distances [m].
       patch  points_changed  eligible     start  start_edge_m  slot  old_point  old_edge_m  new_point  new_edge_m
08OB86_00294            True      True [52, 195]          26.0     1 [309, 113]        45.0 [309, 113]        45.0
08OB86_00294            True      True [52, 195]          26.0     2   [6, 289]         3.0 [273, 232]        63.0
08OB86_00294            True      True [52, 195]          26.0     3 [273, 232]        63.0 [104, 176]        52.0
08OB86_00294            True      True [52, 195]          26.0     4 [104, 176]        52.0  [46, 121]        23.0
08OB86_00294            True      True [52, 195]          26.0     5  [46, 121]        23.0 [250, 270]        64.5
08OB86_-0205           False      True [49, 270]          24.5     1 [114, 102]        51.0 [114, 102]        51.0
08OB86_-0205           False      True [49, 270]          24.5     2 [114, 214]        57.0 [114, 214]        57.0
08OB86_-0205           False      True [49, 270]          24.5     3  [42, 179]        21.0  [42, 179]        21.0
08OB86_-0205           False      True [49, 270]          24.5     4 [135, 255]        67.5 [135, 255]        67.5
08OB86_-0205           False      True [49, 270]          24.5     5  [93, 197]        46.5  [93, 197]        46.5
08OB87_-0706            True      True [50, 200]          25.0     1   [9, 255]         4.5  [89, 197]        44.5
08OB87_-0706            True      True [50, 200]          25.0     2  [89, 197]        44.5 [263, 259]        68.0
08OB87_-0706            True      True [50, 200]          25.0     3 [263, 259]        68.0  [59, 119]        29.5
08OB87_-0706            True      True [50, 200]          25.0     4  [59, 119]        29.5 [347, 145]        26.0
08OB87_-0706            True      True [50, 200]          25.0     5 [347, 145]        26.0  [39, 236]        19.5
08OB88_-1417           False      True [70, 169]          35.0     1 [337, 140]        31.0 [337, 140]        31.0
08OB88_-1417           False      True [70, 169]          35.0     2 [313, 165]        43.0 [313, 165]        43.0
08OB88_-1417           False      True [70, 169]          35.0     3 [199, 151]        75.5 [199, 151]        75.5
08OB88_-1417           False      True [70, 169]          35.0     4 [264, 194]        67.5 [264, 194]        67.5
08OB88_-1417           False      True [70, 169]          35.0     5 [203, 229]        85.0 [203, 229]        85.0
08OB88_-0167           False      True [38, 231]          19.0     1 [137, 294]        52.5 [137, 294]        52.5
08OB88_-0167           False      True [38, 231]          19.0     2 [249, 150]        75.0 [249, 150]        75.0
08OB88_-0167           False      True [38, 231]          19.0     3 [202, 281]        59.0 [202, 281]        59.0
08OB88_-0167           False      True [38, 231]          19.0     4  [31, 208]        15.5  [31, 208]        15.5
08OB88_-0167           False      True [38, 231]          19.0     5 [348, 149]        25.5 [348, 149]        25.5
08OB88_00332           False      True [45, 228]          22.5     1 [142, 207]        71.0 [142, 207]        71.0
08OB88_00332           False      True [45, 228]          22.5     2  [38, 131]        19.0  [38, 131]        19.0
08OB88_00332           False      True [45, 228]          22.5     3 [203, 180]        90.0 [203, 180]        90.0
08OB88_00332           False      True [45, 228]          22.5     4 [136, 171]        68.0 [136, 171]        68.0
08OB88_00332           False      True [45, 228]          22.5     5  [70, 116]        35.0  [70, 116]        35.0
08OB88_01832            True      True [36, 214]          18.0     1 [392, 249]         3.5 [223, 254]        72.5
08OB88_01832            True      True [36, 214]          18.0     2 [397, 169]         1.0 [335, 247]        32.0
08OB88_01832            True      True [36, 214]          18.0     3 [223, 254]        72.5 [159, 229]        79.5
08OB88_01832            True      True [36, 214]          18.0     4 [335, 247]        32.0 [264, 180]        67.5
08OB88_01832            True      True [36, 214]          18.0     5 [159, 229]        79.5 [133, 240]        66.5
08OB89_00152            True      True [48, 341]          24.0     1 [278, 399]         0.0 [296, 173]        51.5
08OB89_00152            True      True [48, 341]          24.0     2 [198, 398]         0.5 [183, 372]        13.5
08OB89_00152            True      True [48, 341]          24.0     3 [296, 173]        51.5 [207, 192]        96.0
08OB89_00152            True      True [48, 341]          24.0     4 [183, 372]        13.5 [328, 186]        35.5
08OB89_00152            True      True [48, 341]          24.0     5 [389, 117]         5.0 [193, 222]        88.5
08OB89_-0347            True      True [55, 326]          27.5     1 [294, 224]        52.5 [294, 224]        52.5
08OB89_-0347            True      True [55, 326]          27.5     2   [5, 248]         2.5 [164, 169]        82.0
08OB89_-0347            True      True [55, 326]          27.5     3 [164, 169]        82.0 [213, 144]        72.0
08OB89_-0347            True      True [55, 326]          27.5     4 [213, 144]        72.0 [195, 352]        23.5
08OB89_-0347            True      True [55, 326]          27.5     5 [195, 352]        23.5 [264, 374]        12.5
08OB89_-0847           False      True [70, 146]          35.0     1  [269, 98]        49.0  [269, 98]        49.0
08OB89_-0847           False      True [70, 146]          35.0     2  [75, 211]        37.5  [75, 211]        37.5
08OB89_-0847           False      True [70, 146]          35.0     3 [227, 332]        33.5 [227, 332]        33.5
08OB89_-0847           False      True [70, 146]          35.0     4 [281, 117]        58.5 [281, 117]        58.5
08OB89_-0847           False      True [70, 146]          35.0     5 [350, 279]        24.5 [350, 279]        24.5

record_origin: reused = archived unchanged tour; rerun = new tour requested; execution states whether it ran.
       patch   mode record_origin execution    status  goals_reached  lethal_cells  debris_cells  plan_s_median  plan_s_p95  plan_s_max  map_update_s_median  map_update_s_p95  map_update_s_max  roll_p95_deg  roll_max_deg  pitch_p95_deg  pitch_max_deg
08OB86_00294  fixed         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB86_00294 online         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB86_00294  lidar         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB86_00294   fine         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB86_-0205  fixed        reused       再利用     stuck              1             1             1      0.0684066    0.101999      0.1069                  NaN               NaN               NaN        4.9228       9.68489         4.7532        10.4313
08OB86_-0205 online        reused       再利用 completed              5             0             0       0.069355    0.134001    0.261372                  NaN               NaN               NaN       4.82593       11.2399        6.09306        11.2888
08OB86_-0205  lidar        reused       再利用 completed              5             0             0      0.0602225    0.133896    0.195715            0.0886842          0.117759          0.280268       5.22368       11.6527        6.72799         15.493
08OB86_-0205   fine        reused       再利用 completed              5             0             0      0.0567309    0.152337    0.252926             0.147879          0.217087          0.414473       4.49613       11.2052        6.61623        15.1624
08OB87_-0706  fixed         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB87_-0706 online         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB87_-0706  lidar         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB87_-0706   fine         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB88_-1417  fixed        reused       再利用     stuck              0             0             0      0.0646924    0.122185    0.123105                  NaN               NaN               NaN       4.28389       5.30703        4.31249        4.31769
08OB88_-1417 online        reused       再利用 completed              5             1             1      0.0593737    0.157099    0.182353                  NaN               NaN               NaN       5.09445       18.8408        4.60072        18.6673
08OB88_-1417  lidar        reused       再利用   no_path              0             0             0      0.0703021    0.183786    0.779775            0.0849492          0.120034          0.408273       3.62647        5.5757        3.05475        7.22803
08OB88_-1417   fine        reused       再利用   no_path              0             0             0      0.0741922      0.1293    0.655003             0.136244          0.182907          0.767768        3.3993       4.24576        2.98031        6.81253
08OB88_-0167  fixed        reused       再利用     stuck              1             0             0       0.132403    0.223228    0.225747                  NaN               NaN               NaN       2.92837        5.2383        3.42202         5.7893
08OB88_-0167 online        reused       再利用 completed              5            27             0      0.0785826    0.384144    0.567933                  NaN               NaN               NaN         7.394       42.9836        8.88529        52.4828
08OB88_-0167  lidar        reused       再利用   no_path              4             0             0      0.0549699    0.262924    0.813405            0.0878073            0.1176          0.732807       4.81866       11.5023        7.53545        17.3064
08OB88_-0167   fine        reused       再利用   no_path              1             0             0      0.0449144    0.242908    0.584193              0.14649          0.196542          0.517358       2.71611       5.62935        3.46721        6.84554
08OB88_00332  fixed        reused       再利用     stuck              0             0             0      0.0377247   0.0866617   0.0977732                  NaN               NaN               NaN       3.51936       4.69489        10.4422        14.4091
08OB88_00332 online        reused       再利用 completed              5             0             0      0.0452776   0.0907293    0.192564                  NaN               NaN               NaN       5.48962       9.31724          6.885        14.4478
08OB88_00332  lidar        reused       再利用 completed              5             0             0        0.03756   0.0715036    0.166216            0.0991531          0.134696          0.309379       5.34296       8.91668        7.13067         16.348
08OB88_00332   fine        reused       再利用 completed              5             0             0      0.0401148    0.107446    0.134721             0.165697          0.233797          0.395351       5.47627       11.2033        6.85835        14.4911
08OB88_01832  fixed         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB88_01832 online         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB88_01832  lidar         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB88_01832   fine         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_00152  fixed         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_00152 online         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_00152  lidar         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_00152   fine         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_-0347  fixed         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_-0347 online         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_-0347  lidar         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_-0347   fine         rerun       未実行       未実行            NaN           NaN           NaN            NaN         NaN         NaN                  NaN               NaN               NaN           NaN           NaN            NaN            NaN
08OB89_-0847  fixed        reused       再利用     stuck              1             2             2       0.110015    0.203834    0.215019                  NaN               NaN               NaN       4.60119       7.53312         3.6828        8.49752
08OB89_-0847 online        reused       再利用 completed              5             1             1       0.112321     0.27778    0.386705                  NaN               NaN               NaN       3.33601       7.59398        3.68824        13.6144
08OB89_-0847  lidar        reused       再利用   no_path              1             0             0      0.0982125    0.320457    0.674176             0.095285          0.129591          0.757749       4.00998       7.27667        3.56249        6.10916
08OB89_-0847   fine        reused       再利用   no_path              1             0             0      0.0889482    0.314632    0.599566             0.145054            0.1942          0.631169       4.15796         6.919        3.31387        5.74462

Counts and per-run medians among actual recordings only; partial counts do not establish disappearance of rollovers.
  mode  scheduled  eligible  excluded  reused  rerun_requested  rerun_recorded  executed  unexecuted  completed  stuck  rollover  no_path  timeout  runtime_error  incomplete_waypoints  other_failure  goals_reached_median  lethal_cells_median  debris_cells_median  n_replans_median  elapsed_s_median  deviation_mean_m_median  deviation_max_m_median  roll_p95_deg_median  roll_max_deg_median  pitch_p95_deg_median  pitch_max_deg_median  plan_s_median_median  plan_s_p95_median  plan_s_max_median  map_update_s_median_median  map_update_s_p95_median  map_update_s_max_median
 fixed         10        10         0       5                5               0         5           5          0      5         0        0        0              0                     0              0                     1                    0                    0                 0              64.7                0.0682241                0.574867              4.28389              5.30703               4.31249               8.49752             0.0684066           0.122185           0.123105                         NaN                      NaN                      NaN
online         10        10         0       5                5               0         5           5          5      0         0        0        0              0                     0              0                     5                    1                    0               185            299.45                0.0591287                0.967311              5.09445              11.2399               6.09306               14.4478              0.069355           0.157099           0.261372                         NaN                      NaN                      NaN
 lidar         10        10         0       5                5               0         5           5          2      0         0        3        0              0                     0              0                     4                    0                    0               112            236.52                 0.046327                0.943776              4.81866              8.91668               6.72799                15.493             0.0602225           0.183786           0.674176                   0.0886842                 0.120034                 0.408273
  fine         10        10         0       5                5               0         5           5          2      0         0        3        0              0                     0              0                     1                    0                    0                79           121.051                0.0402763                0.842031              4.15796                6.919               3.46721               6.84554             0.0567309           0.152337           0.584193                     0.14649                 0.196542                 0.517358

Method minus reference: paired medians only where BOTH complete the five targets and return.
method reference              metric  paired_completed  delta_median
online     fixed       goals_reached                 0           NaN
online     fixed        lethal_cells                 0           NaN
online     fixed        debris_cells                 0           NaN
online     fixed           n_replans                 0           NaN
online     fixed           elapsed_s                 0           NaN
online     fixed    deviation_mean_m                 0           NaN
online     fixed     deviation_max_m                 0           NaN
online     fixed        roll_p95_deg                 0           NaN
online     fixed        roll_max_deg                 0           NaN
online     fixed       pitch_p95_deg                 0           NaN
online     fixed       pitch_max_deg                 0           NaN
online     fixed       plan_s_median                 0           NaN
online     fixed          plan_s_p95                 0           NaN
online     fixed          plan_s_max                 0           NaN
online     fixed map_update_s_median                 0           NaN
online     fixed    map_update_s_p95                 0           NaN
online     fixed    map_update_s_max                 0           NaN
 lidar     fixed       goals_reached                 0           NaN
 lidar     fixed        lethal_cells                 0           NaN
 lidar     fixed        debris_cells                 0           NaN
 lidar     fixed           n_replans                 0           NaN
 lidar     fixed           elapsed_s                 0           NaN
 lidar     fixed    deviation_mean_m                 0           NaN
 lidar     fixed     deviation_max_m                 0           NaN
 lidar     fixed        roll_p95_deg                 0           NaN
 lidar     fixed        roll_max_deg                 0           NaN
 lidar     fixed       pitch_p95_deg                 0           NaN
 lidar     fixed       pitch_max_deg                 0           NaN
 lidar     fixed       plan_s_median                 0           NaN
 lidar     fixed          plan_s_p95                 0           NaN
 lidar     fixed          plan_s_max                 0           NaN
 lidar     fixed map_update_s_median                 0           NaN
 lidar     fixed    map_update_s_p95                 0           NaN
 lidar     fixed    map_update_s_max                 0           NaN
  fine     fixed       goals_reached                 0           NaN
  fine     fixed        lethal_cells                 0           NaN
  fine     fixed        debris_cells                 0           NaN
  fine     fixed           n_replans                 0           NaN
  fine     fixed           elapsed_s                 0           NaN
  fine     fixed    deviation_mean_m                 0           NaN
  fine     fixed     deviation_max_m                 0           NaN
  fine     fixed        roll_p95_deg                 0           NaN
  fine     fixed        roll_max_deg                 0           NaN
  fine     fixed       pitch_p95_deg                 0           NaN
  fine     fixed       pitch_max_deg                 0           NaN
  fine     fixed       plan_s_median                 0           NaN
  fine     fixed          plan_s_p95                 0           NaN
  fine     fixed          plan_s_max                 0           NaN
  fine     fixed map_update_s_median                 0           NaN
  fine     fixed    map_update_s_p95                 0           NaN
  fine     fixed    map_update_s_max                 0           NaN
 lidar    online       goals_reached                 2             0
 lidar    online        lethal_cells                 2             0
 lidar    online        debris_cells                 2             0
 lidar    online           n_replans                 2         -54.5
 lidar    online           elapsed_s                 2       -0.2295
 lidar    online    deviation_mean_m                 2   -0.00879547
 lidar    online     deviation_max_m                 2    -0.0139585
 lidar    online        roll_p95_deg                 2      0.125549
 lidar    online        roll_max_deg                 2    0.00610705
 lidar    online       pitch_p95_deg                 2      0.440305
 lidar    online       pitch_max_deg                 2       3.05218
 lidar    online       plan_s_median                 2   -0.00842511
 lidar    online          plan_s_p95                 2   -0.00966542
 lidar    online          plan_s_max                 2    -0.0460024
 lidar    online map_update_s_median                 0           NaN
 lidar    online    map_update_s_p95                 0           NaN
 lidar    online    map_update_s_max                 0           NaN
  fine    online       goals_reached                 2             0
  fine    online        lethal_cells                 2             0
  fine    online        debris_cells                 2             0
  fine    online           n_replans                 2         -62.5
  fine    online           elapsed_s                 2         1.916
  fine    online    deviation_mean_m                 2    -0.0115147
  fine    online     deviation_max_m                 2     -0.301073
  fine    online        roll_p95_deg                 2      -0.17157
  fine    online        roll_max_deg                 2      0.925635
  fine    online       pitch_p95_deg                 2      0.248261
  fine    online       pitch_max_deg                 2       1.95847
  fine    online       plan_s_median                 2   -0.00889348
  fine    online          plan_s_p95                 2     0.0175263
  fine    online          plan_s_max                 2    -0.0331446
  fine    online map_update_s_median                 0           NaN
  fine    online    map_update_s_p95                 0           NaN
  fine    online    map_update_s_max                 0           NaN
  fine     lidar       goals_reached                 2             0
  fine     lidar        lethal_cells                 2             0
  fine     lidar        debris_cells                 2             0
  fine     lidar           n_replans                 2            -8
  fine     lidar           elapsed_s                 2        2.1455
  fine     lidar    deviation_mean_m                 2   -0.00271919
  fine     lidar     deviation_max_m                 2     -0.287114
  fine     lidar        roll_p95_deg                 2     -0.297119
  fine     lidar        roll_max_deg                 2      0.919528
  fine     lidar       pitch_p95_deg                 2     -0.192043
  fine     lidar       pitch_max_deg                 2      -1.09372
  fine     lidar       plan_s_median                 2  -0.000468373
  fine     lidar          plan_s_p95                 2     0.0271917
  fine     lidar          plan_s_max                 2     0.0128578
  fine     lidar map_update_s_median                 2     0.0628693
  fine     lidar    map_update_s_p95                 2     0.0992145
  fine     lidar    map_update_s_max                 2      0.110088
Missing physical/map timings remain None/NaN. No hypothesis tests or energy columns.
Contact is audited on centre trajectories; it does not establish clearance of the entire body.
```

上の再利用行は元の実測値をそのまま使った。再走行が必要な20行は未実行であり、転倒が消えたかは未評価である。
集計の完走数・転倒数・対の差は記録がある部分集合についての値で、10か所の新しい実走結果ではない。
新旧の全地点・開始点・端からの距離は `refresh/waypoints.csv`、記録の由来は `refresh/runs.csv` に保存した。

## 研究PCで後日走らせる手順（今回未実行）

```bash
cd conference
bash ros2_jazzy/gz_checks/run_edge_margin_checks.sh results/edge_margin/physical_run_new
python3 experiments/edge_margin_report.py results/edge_margin/physical_run_new
```

`physical_run_new` は未使用の保存先にする。変わらない砂浜は021〜023を再利用し、変わった砂浜だけ、古い地図・仮想R10・LiDAR coarse・LiDAR fineを走らせる。
元の記録は消さず、転倒・接触・完走と記録の完全性を確認する。実走した砂浜の軌跡図は集計スクリプトが保存する。

## 実行したPython確認と全文ログ

```bash
cd /workspace/thesis-024-refresh/conference
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/edge-refresh-mpl XDG_CACHE_HOME=/tmp/edge-refresh-cache python3 -m tests.test_edge_margin
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/edge-refresh-mpl XDG_CACHE_HOME=/tmp/edge-refresh-cache python3 ros2_jazzy/gz_checks/edge_margin_checks.py --prepare-only --output results/edge_margin/refresh
python3 results/edge_margin/refresh/verification/run_tests.py
```

全テストのランナーもOPENBLAS_NUM_THREADS=1と/tmpのキャッシュを指定した。以下はstdout・stderrの全文と実際の終了コードである。

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

$ python3 -m tests.test_edge_margin
sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability
sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed
cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained
synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it
report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance
real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS
dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer
Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest
all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)

exit=0

$ python3 -m tests.test_endpoint_component
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: only two corrected start_steep labels differ in replay; all other fields and four preparation variants unchanged
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
saved component contract: both start_steep cases clear ZERO cells, protect all raw masks, retry once and advance to the next stop
all task028b component tests passed (Python only; Gazebo not run)

exit=0

$ python3 -m tests.test_endpoint_policy
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).

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

$ python3 -m tests.test_ground_estimate
1 PASS: implicit/explicit all_returns match pre-change update JSON, snapshots, histories, NPZ and multi-sensor sidecar bytes
2 PASS: 0.55m box creates false steep neighbours only with all_returns; box detection/inflation and all evidence unchanged
ground_estimate x y slope_deg steep box_lethal
all_returns 9 10 28.810793742973065 True True
all_returns 11 10 28.810793742973065 True True
all_returns 10 9 28.810793742973065 True True
all_returns 10 11 28.810793742973065 True True
non_obstacle 9 10 0.0 False True
non_obstacle 11 10 0.0 False True
non_obstacle 10 9 0.0 False True
non_obstacle 10 11 0.0 False True
3 PASS: all-excluded cells retain prior height and seen status; last-64 ALL returns displace older ground, then ground observations resume
4 PASS: sub-0.3m terrain changes retained; bilinear prior and the unchanged >=0.3m obstacle boundary used
5 PASS: LiDAR+two cameras share unchanged 2+1 detection evidence, source attribution and filtering; ground-only median removes false steep cells
configuration PASS: byte-identical default manifests; opt-in factory, CLI, ROS parameter and actual node constructor propagation; invalid/coarse combinations rejected
all ground-estimate tests passed; requirement 6 is verified by running every conference/tests module separately (Python only)

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
/workspace/thesis-024-refresh/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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
/workspace/thesis-024-refresh/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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

$ python3 -m tests.test_real_sensors
PASS legacy model SDF (with/without LiDAR) and fine-map NPZ SHA256 match pre-change bytes
PASS real preset mounts, symmetry, unchanged LiDAR spec and camera FOV/ranges without intrinsics
A2 camera1: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
A2 camera2: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
PASS A2: three camera-free SDFs byte-identical; depth SDF/spec change only prescribed resolution and intrinsics
PASS arbitrary sensor/model roll-pitch-yaw and translation match independent homogeneous transform
PASS both outward cameras: ground/box registration, shared 2+1 evidence, one inflation and saved provenance
PASS synthetic camera boxes in LiDAR blind zone at 1.5/2/3m; residual 1m blind zone disclosed
PASS per-sensor range/FOV/finite filtering and byte-identical task023 fusion/inflation for registered input
PASS manifest records all real specs/mounts; explicit fine selection; Docker wrapper forwards sensor flags
PASS A2 wrapper: unset flags preserve full legacy argv bytes; individual/both/empty supplied values forwarded (fake Docker only)
PASS analytic 4.105m LiDAR near bound, discrete-beam gap, rear blind zone and camera symmetry
PASS actual ROS adapter: bounded queues, fair sources, stamped transforms, logs and freshness (transport mocked)
all real sensor tests passed (synthetic/geometry only; Gazebo not run)

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
test_edge_margin exit=0
test_endpoint_component exit=0
test_endpoint_policy exit=0
test_footprint exit=0
test_geo exit=0
test_ground_estimate exit=0
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
test_real_sensors exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

## できなかったこと・確認してほしいこと

Gazebo実走、転倒が消えたか、再走行の性能・更新時間の測定、新しい軌跡図は未実施。未測定の値は埋めていない。
接触の監査は中心軌跡についてであり、機体全体の安全性を保証するものではない。経路自体が端の余白内だけを通るという制約も追加していない。
Claudeには、研究PCでの4方式の起動・新旧記録の区別・端での転倒が残るかとその位置を確認してほしい。

最新土台での既存ファイルは、許可された3ソース以外について名前とSHA-256のダイジェストを照合し、不変を確認した。プロトコルは `refresh/verification/protocol.json` に保存した。

## 変更・追加ファイル

- `conference/experiments/edge_margin_report.py`
- `conference/results/edge_margin/PR_DESCRIPTION_ja.md`
- `conference/results/edge_margin/README_ja.md`
- `conference/results/edge_margin/REPORT_2026-11-06_ja.md`
- `conference/results/edge_margin/REPORT_ja.md`
- `conference/results/edge_margin/changed_files.txt`
- `conference/results/edge_margin/edge_margin_log.txt`
- `conference/results/edge_margin/manifest.json`
- `conference/results/edge_margin/paired_differences.csv`
- `conference/results/edge_margin/refresh/changed_files.txt`
- `conference/results/edge_margin/refresh/edge_margin_log.txt`
- `conference/results/edge_margin/refresh/implementation_commit.txt`
- `conference/results/edge_margin/refresh/manifest.json`
- `conference/results/edge_margin/refresh/paired_differences.csv`
- `conference/results/edge_margin/refresh/runs.csv`
- `conference/results/edge_margin/refresh/summary.csv`
- `conference/results/edge_margin/refresh/verification/all_tests_log.txt`
- `conference/results/edge_margin/refresh/verification/build_report.py`
- `conference/results/edge_margin/refresh/verification/protocol.json`
- `conference/results/edge_margin/refresh/verification/run_tests.py`
- `conference/results/edge_margin/refresh/verification/test_beach_terrain_log.txt`
- `conference/results/edge_margin/refresh/verification/test_collision_log.txt`
- `conference/results/edge_margin/refresh/verification/test_dstar_log.txt`
- `conference/results/edge_margin/refresh/verification/test_edge_margin_log.txt`
- `conference/results/edge_margin/refresh/verification/test_endpoint_component_log.txt`
- `conference/results/edge_margin/refresh/verification/test_endpoint_policy_log.txt`
- `conference/results/edge_margin/refresh/verification/test_footprint_log.txt`
- `conference/results/edge_margin/refresh/verification/test_geo_log.txt`
- `conference/results/edge_margin/refresh/verification/test_ground_estimate_log.txt`
- `conference/results/edge_margin/refresh/verification/test_gz_compare_log.txt`
- `conference/results/edge_margin/refresh/verification/test_gz_online_batch_log.txt`
- `conference/results/edge_margin/refresh/verification/test_mapfiles_sim_log.txt`
- `conference/results/edge_margin/refresh/verification/test_mission_log.txt`
- `conference/results/edge_margin/refresh/verification/test_natural_terrain_log.txt`
- `conference/results/edge_margin/refresh/verification/test_online_deadend_log.txt`
- `conference/results/edge_margin/refresh/verification/test_online_log.txt`
- `conference/results/edge_margin/refresh/verification/test_online_mission_log.txt`
- `conference/results/edge_margin/refresh/verification/test_planners_log.txt`
- `conference/results/edge_margin/refresh/verification/test_pointcloud_map_fine_log.txt`
- `conference/results/edge_margin/refresh/verification/test_pointcloud_map_log.txt`
- `conference/results/edge_margin/refresh/verification/test_real_beach_las_log.txt`
- `conference/results/edge_margin/refresh/verification/test_real_beach_log.txt`
- `conference/results/edge_margin/refresh/verification/test_real_sensors_log.txt`
- `conference/results/edge_margin/refresh/verification/test_risk_prior_log.txt`
- `conference/results/edge_margin/refresh/verification/test_ros2_gz_log.txt`
- `conference/results/edge_margin/refresh/verification/test_summary.txt`
- `conference/results/edge_margin/refresh/verification/test_thesis_figures_log.txt`
- `conference/results/edge_margin/refresh/verification/test_tour_log.txt`
- `conference/results/edge_margin/refresh/verification/test_visibility_log.txt`
- `conference/results/edge_margin/refresh/waypoints.csv`
- `conference/results/edge_margin/runs.csv`
- `conference/results/edge_margin/summary.csv`
- `conference/results/edge_margin/verification/all_tests_log.txt`
- `conference/results/edge_margin/verification/baseline_sha256.json`
- `conference/results/edge_margin/verification/build_report.py`
- `conference/results/edge_margin/verification/docker_launcher_log.txt`
- `conference/results/edge_margin/verification/edge_after_exclusion_log.txt`
- `conference/results/edge_margin/verification/edge_final_log.txt`
- `conference/results/edge_margin/verification/edge_initial_log.txt`
- `conference/results/edge_margin/verification/legacy_waypoints.json`
- `conference/results/edge_margin/verification/planners_before_log.txt`
- `conference/results/edge_margin/verification/prepare_console_log.txt`
- `conference/results/edge_margin/verification/preservation_audit.json`
- `conference/results/edge_margin/verification/protocol.json`
- `conference/results/edge_margin/verification/report_console_log.txt`
- `conference/results/edge_margin/verification/run_tests.py`
- `conference/results/edge_margin/verification/test_beach_terrain_log.txt`
- `conference/results/edge_margin/verification/test_collision_log.txt`
- `conference/results/edge_margin/verification/test_dstar_log.txt`
- `conference/results/edge_margin/verification/test_edge_margin_log.txt`
- `conference/results/edge_margin/verification/test_footprint_log.txt`
- `conference/results/edge_margin/verification/test_geo_log.txt`
- `conference/results/edge_margin/verification/test_gz_compare_log.txt`
- `conference/results/edge_margin/verification/test_gz_online_batch_log.txt`
- `conference/results/edge_margin/verification/test_mapfiles_sim_log.txt`
- `conference/results/edge_margin/verification/test_mission_log.txt`
- `conference/results/edge_margin/verification/test_natural_terrain_log.txt`
- `conference/results/edge_margin/verification/test_online_deadend_log.txt`
- `conference/results/edge_margin/verification/test_online_log.txt`
- `conference/results/edge_margin/verification/test_online_mission_log.txt`
- `conference/results/edge_margin/verification/test_planners_log.txt`
- `conference/results/edge_margin/verification/test_pointcloud_map_fine_log.txt`
- `conference/results/edge_margin/verification/test_pointcloud_map_log.txt`
- `conference/results/edge_margin/verification/test_real_beach_las_log.txt`
- `conference/results/edge_margin/verification/test_real_beach_log.txt`
- `conference/results/edge_margin/verification/test_risk_prior_log.txt`
- `conference/results/edge_margin/verification/test_ros2_gz_log.txt`
- `conference/results/edge_margin/verification/test_summary.txt`
- `conference/results/edge_margin/verification/test_thesis_figures_log.txt`
- `conference/results/edge_margin/verification/test_tour_log.txt`
- `conference/results/edge_margin/verification/test_visibility_log.txt`
- `conference/results/edge_margin/waypoints.csv`
- `conference/ros2_jazzy/gz_checks/edge_margin_checks.py`
- `conference/ros2_jazzy/gz_checks/lidar_checks.py`
- `conference/ros2_jazzy/gz_checks/online_batch_checks.py`
- `conference/ros2_jazzy/gz_checks/run_edge_margin_checks.sh`
- `conference/tapp/tour.py`
- `conference/tests/test_edge_margin.py`
