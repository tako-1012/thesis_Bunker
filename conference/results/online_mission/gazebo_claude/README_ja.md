# Gazebo での「計画し直す」確認の結果（Claude が Docker で実行）

Codex の環境では Docker のイメージを取れず、Gazebo での確認ができませんでした（`../gazebo/launcher_failure.json`）。
Claude が `run_online_checks.sh` を実行しました。イメージは、`osrf/ros:jazzy-desktop-full` に pandas を足したもの
（`conference/ros2_jazzy/gz_checks/Dockerfile`。`docker build -t thesis/jazzy-gz:1 .` のあと、
`THESIS_ROS_IMAGE=thesis/jazzy-gz:1 bash run_online_checks.sh <出力フォルダ>`）。Gazebo 8.11.0。結果の全文は `results.json`。

- 本当の地形（Gazebo の world）：点群の砂浜 `08OB87_-0206` の漂着物あり。事前の地図：同じ場所の漂着物なし（`stale`）。
- 見える半径 10m（本当の地形の地図から読む簡単化。LiDAR・陰・誤差はない）。5 点の巡回。

| | 計画し直さない（`fixed`） | 計画し直す（`online`） |
|---|---|---|
| 結果 | **立ち往生**（96 秒、4 点目の手前） | **完走**（194 秒） |
| 止まった位置と漂着物の距離 | 0.34m（漂着物の箱に引っかかった） | — |
| 通れない場所に触れたマス | 0（触れる手前で止まった） | 0 |
| 計画し直した回数 | 0 | 129（経路の差し替え 134） |
| 1 回の計画の時間（中央値／95%／最大） | 0.034／0.077／0.087 秒 | 0.055／0.11／0.15 秒 |

`compare.png`：左が計画し直さない場合（×が止まった位置）、右が計画し直す場合。水色が漂着物（ロボットの半径だけ膨らませたもの）。
古い地図のまま走ると、Gazebo の物理でも漂着物で止まってしまい、走りながら計画し直すと避けて回れることが確かめられました。
1 回の計画は最大 0.15 秒で、1m/s で走りながら十分に間に合います（この 1 走行の値）。
