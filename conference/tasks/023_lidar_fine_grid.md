# 指示書023：LiDARの障害物判定を細かい格子にし、膨張を1回だけにする

> **状態：完了**（Codex が実装。Gazebo は Claude が通常の Docker で 10 か所を実行）。結果は `conference/results/lidar_fine/physical_10/README_ja.md`：
> 完走 5/10（022 は 4/10）、経路なし 4（022 と同じ 4 か所）、地図の端での転倒 1。誤って通れないとしたマスは中央値で約 6 割減った。漂着物に触れた走行は 0。

tako-1012/thesis_Bunker で、指示書 022（LiDAR）の地図の作り方を改良してください（指示書 023）。

## 最初に読むもの
1. AGENTS.md
2. conference/tasks/BATCH_RULES_ja.md
3. conference/tasks/022_gazebo_lidar.md と conference/results/gazebo_lidar/physical_10/README_ja.md
   （022 の結果と「経路なし」の原因。今回はこれを直す）
4. conference/tapp/pointcloud_map.py、conference/tapp/footprint.py、conference/ros2_jazzy/gz_checks/lidar_*.py

## ブランチ
- realtime-map の最新を取得してから、codex/023-lidar-fine-grid を作る。マージしない。push までで止める。
- この指示の内容を conference/tasks/023_lidar_fine_grid.md として保存し、同じブランチでコミットする。

## 背景
022 では、LiDAR で計画し直すと完走は 10 か所中 4 か所だった（半径 10m の仮想センサーでは 9 か所）。
残りの多くは「経路なし」。原因は、誤って障害物にされたマスの約 7 割が、漂着物の箱のすぐ隣の 1 マスだったこと。
箱の側面が 0.5m のマスの境目にあり、側面に当たった点が測距ノイズ（0.02m）で隣のマスに入る。
さらに、そのマスをロボットの大きさ（0.5m＝1 マス）だけ膨らませるので、通れない所が 2 重に太る。

## 今回やること（この 2 つだけ）
1. 障害物を見つける格子を細かくする
   - 新しいファイル conference/tapp/pointcloud_map_fine.py に、PointCloudMap と同じ使い方
     （コンストラクタ、update(sensor_points, pose)、snapshot()、save()）のクラスを作る。
   - 障害物の判定だけを 0.1m の細かい格子で行う。判定の規則は 022 と同じ
     （古い地図の高さより 0.3m 以上高い点が、1 つの細かい格子に 3 点以上）。
   - 地面の高さ・傾斜・凸凹・コストは、022 と同じく 0.5m のマスで計算する（TraversabilityMap の式は変えない）。
2. 膨らませを 1 回だけにする
   - 細かい格子で見つけた障害物を、ロボットの半径（0.5m）で 1 回だけ膨らませ、それと重なる 0.5m のマスを通れないとする。
   - 「細かい格子の障害物を先に 0.5m のマスに丸めてから、さらに膨らませる」という 2 重の膨らませをしない。
   - 急斜面の膨らませ（指示書 020、footprint.py）は今のまま。

## 変えないこと
- 0.1m・0.3m・3 点・0.5m は、どれも事前に決めた値とする。テスト用の砂浜の結果を見て変えない。今回はパラメータの調整をしない。
- 既存のファイル（pointcloud_map.py、traversability.py、footprint.py、online_mission.py、経路計画）と、既存の結果は変えない。
  022 の方法は既定のまま残し、新しい方法は新しいファイルと、既定値で今までと同じ動きになる新しい引数（例：lidar_checks.py の --map fine）で選べるようにする。
- 経路計画（TA*・TA*-S）のコストの式は変えない。
- 結果は実行して得た値だけを書く。Gazebo・Docker が使えなければ、スクリプトとテストまで作り、Gazebo の実行は「未実行」と書く。

## テスト：conference/tests/test_pointcloud_map_fine.py（ROS2・Gazebo なしで動くこと）
1. 平らな地面の点群から、障害物のない地図ができる。
2. 側面が 0.5m のマスの境目にある箱の点群（測距ノイズ 0.02m）で、箱の外側の 0.5m のマスが通れないとされる数が、
   022 の方法（PointCloudMap）より少ない。
3. 箱そのもの（中心のマス）は、022 の方法と同じく通れないとされる（見落とさない）。
4. 膨らませが 1 回だけであること（障害物の端から、ロボットの半径より遠いマスは通れないとされない）。
5. 既存の 022 の方法を選んだ場合、出力が今までとバイト単位で同じ。
- 作業を終える前に、conference/tests/ のすべてのテストを実行する。

## Gazebo で走らせる手順（Claude が Docker で実行する）
- 022 と同じ 10 か所・同じ world・同じ地点・同じスタートで、新しい方法だけを走らせられるようにする
  （例：bash run_lidar_checks.sh results/lidar_fine/physical_10 --patch-count 10 --map fine）。
- 022 で使った走らせ方の設定（地形の見た目のメッシュ、シミュレーションの速さ 0.3 倍、点群の途切れの基準 1.0 秒）は、
  022 と同じにする。manifest に記録する。
- 集計（experiments/gz_lidar_report.py を使うか、新しい集計スクリプト）で、
  021 の古い地図のまま・021 の仮想センサー・022 の LiDAR・今回の LiDAR の 4 つを並べる。
  項目：完走・立ち往生・転倒・経路なし、通れないマスの数（本当の地図と比べた誤検出と見落とし）、
  そのうち箱のすぐ隣の 1 マスの数、地図の更新の時間（中央値・95% 値・最大）、漂着物に触れた走行の数。

## 報告（conference/results/lidar_fine/REPORT_ja.md と PR の説明。日本語）
1. 実装したもの（ファイル、関数）
2. 実行したコマンドと、テストの出力の全文
3. 集計表（Gazebo を走らせていなければ、その欄は「未実行」）
4. 0.1m・0.3m・3 点が事前に決めた値で、調整していないこと
5. できなかったこと、自信がないこと、Claude に確かめてほしいこと
