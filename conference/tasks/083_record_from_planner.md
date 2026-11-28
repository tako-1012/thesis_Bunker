# 指示書 083：センサーの記録を、計画のノードが受けた LiDAR から取る形に直す（記録を取ると点群が古くなる問題）

> **状態：完了（結果とレビューは `results/record_from_planner/`。研究 PC での確かめは 085）**。Gazebo・研究 PC は使わない（研究 PC での確かめは、取り込んでから別に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/tasks/075_landmark_world.md`・`078_landmark_localization_eval.md`・`082_localization_frame_check.md`、
> `conference/results/eval_078/diag/REPORT_ja.md`・`REVIEW_ja.md`（**この指示書の根拠**）、`conference/results/landmark_world/REPORT_ja.md`・`REVIEW_ja.md`、
> `conference/ros2_jazzy/gz_checks/sensor_recorder.py`・`lidar_planner.py`（`on_cloud`）・`lidar_checks.py`、`conference/tapp/sensor_recording.py`、`conference/experiments/recording_bridge.py` を読むこと。
> ブランチは `codex/083-record-from-planner`（その時点の `realtime-map` の最新から）。結果は `conference/results/record_from_planner/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 075 の `--record-sensors` は、別のプロセス（`sensor_recorder.py`）が `/lidar/points`・`/imu`・`/ground_truth` を受けて記録する。
- 078（研究 PC）で、`--record-sensors` を付けた**全 24 回が、計画の LiDAR が古くなって止まった**。082 で、同じ条件で記録なしは完走、記録ありは 8.8 秒で止まった。記録の側には LiDAR が届いているのに、計画の地図は 1 秒古い点群のままだった。記録の仕組みの CPU は軽い（中央値 3%）。
- 大きな LiDAR のメッセージ（1 回に約 3 万点）を、計画と記録の 2 つが同時に受けると、計画の側に届かなくなると考えられる。

## 作るもの（`--record-sensors` を選んだときだけ働く。既定の出力・記録はバイト単位で変えない）
- **LiDAR の記録を、計画のノード（`lidar_planner.py`）の `on_cloud` が受けたメッセージから取る**。`/lidar/points` を別のプロセスで受けるのをやめる。
  - 記録の書き出し（詰めて npz にする）は、計画の処理を遅らせないよう、別のスレッドか別のプロセスに渡す（受けたメッセージの中身をそのまま渡す。計画に使う点群は変えない）。渡しきれないときは、計画を止めずに記録の側で落とし、落とした数を記録する。
  - IMU と正解の位置は小さいので、今までどおり `sensor_recorder.py` で受けてよい（LiDAR だけを外す）。
- 記録の形（`sensors/chunk_*.npz`・`metadata.json`）は今までと同じにし、077 の読み込み（`recording_bridge.py`）がそのまま使えること。
- 記録の量の上限（1 回 100MB）・時間の上限（`--record-sensors-seconds`）も今までどおり。

## 守ること・やらないこと
- 既定（`--record-sensors` なし）の出力・manifest・記録は、バイト単位で変えない（直す前の実装と同じ環境で、その場で比べるテスト）。
- 計画・地図の作り方・値は変えない。Gazebo・研究 PC は使わない。

## テスト `conference/tests/test_record_from_planner.py`（ROS2・Gazebo なしで動くこと）
1. 既定の出力がバイト単位で同じ。
2. 偽の計画のノードに LiDAR のメッセージを流すと、記録の形（`chunk_*.npz`）に書かれ、077 の `recording_bridge` で読むと点（mm 単位）と時刻が元と一致する。
3. 記録の書き出しをわざと遅くしても、`on_cloud` の地図の更新は遅れない（記録の側で落とし、落とした数が `metadata.json` に出る）。
4. `--record-sensors` のとき、`sensor_recorder.py` が `/lidar/points` を受けない（起動の中身で確かめる）。
5. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 記録を計画のノードから取るやり方と、計画を遅らせないための工夫。
3. 研究 PC で確かめるときの引数の案（082 の記録あり・なしの 2 回と同じ条件で）。
4. できなかったこと、自信がないこと。
