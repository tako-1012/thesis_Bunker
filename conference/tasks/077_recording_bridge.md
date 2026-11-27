# 指示書 077：075 のセンサーの記録を、076 の位置を出す道具で読めるようにする

> **状態：完了（結果は `results/recording_bridge/`、レビューは `REVIEW_ja.md`）**。Gazebo・研究 PC は使わない。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/tasks/075_landmark_world.md`・`076_offline_localization.md`、
> `conference/results/landmark_world/REPORT_ja.md`・`REVIEW_ja.md`（**つながっていない所の表**）、`conference/results/offline_localization/REPORT_ja.md`・`REVIEW_ja.md`、
> `conference/tapp/sensor_recording.py`、`conference/ros2_jazzy/gz_checks/sensor_recorder.py`・`lidar_checks.py`（LiDAR の取り付け位置が世界にどう書かれるか）、`conference/tapp/sensor_geometry.py`、`conference/experiments/offline_localization.py` を読むこと。
> ブランチは `codex/077-recording-bridge`（その時点の `realtime-map` の最新から）。結果は `conference/results/recording_bridge/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 075 で、Gazebo の走行のセンサー（LiDAR・IMU・正解の位置）を `sensors/chunk_*.npz` に分けて記録するようにした。076 で、記録からあとで自分の位置を出す道具を作った。
- 2 つは並行して作ったので、**記録の形が合っていない**（075 の REVIEW の表）：ファイルの分け方、LiDAR の向きの持ち方（`rays` と `azimuth_rad`・`elevation_rad`）、列の名前、LiDAR の取り付け位置（`base_from_lidar`）がない。

## 作るもの
- 076 の道具が、**075 の走行の記録のフォルダ（`raw/`）をそのまま読める**ようにする。やり方は Codex が選んでよい（076 の読み込みに 075 の形を足す、または変換の道具を作る）。どちらでも、次を満たすこと。
  - LiDAR の点は、075 の `iter_lidar`（`unpack_lidar`）で元に戻したものを使う（例外の点・届かなかった点の扱いも含めて）。
  - 正解の位置は `truth_values`、IMU は `imu_values` から取る。
  - **LiDAR の取り付け位置（車体から LiDAR への変換）**は、その走行の manifest か `world.sdf` に書かれた値から取る。決め打ちの数字は使わない。見つからないときは、はっきりしたエラーで止める。
  - 地図の点群は、同じ走行の `reference_cloud.npz` を使う。
- 076 の既存の入力の形（1 つの npz）は、そのまま読めること。

## 守ること・やらないこと
- 既存の出力（075・076 の既定の出力を含む）はバイト単位で変えない。076 の基準（固有値 1.0・5m）や値は変えない。Gazebo・研究 PC は使わない。

## テスト `conference/tests/test_recording_bridge.py`（ROS2・Gazebo なしで動くこと。kiss-icp・small_gicp がない環境では、それが要るテストだけ飛ばして、そう表示する）
1. 075 の記録の書き手（`SensorArchive`）で書いた合成の記録を、076 の道具で読むと、LiDAR の点（mm 単位）・正解の位置・IMU・時刻が元と一致する。
2. 取り付け位置が、合成の manifest（または `world.sdf`）の値と一致する。見つからないときはエラーになる。
3. 075 の形の合成の記録と `reference_cloud.npz` で、076 の 3 通りの位置の出し方が最後まで動き、目印のある合成の世界で、重ね合わせの誤差が 076 の報告と同じ程度になる。
4. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 選んだやり方と理由。取り付け位置をどこから取ったか。
3. 研究 PC で、075 の記録に 076 の道具をかけるコマンドの案。
4. できなかったこと、自信がないこと。
