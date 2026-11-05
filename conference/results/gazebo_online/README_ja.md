# 指示書021：10地形での固定経路とオンライン再計画の比較

この保存先のGazebo走行は**未実行**。`manifest.json` と図の経路は実際の事前計画であり、
走行記録ではない。実測欄の空欄・None・NaNを0として読まないこと。
全テストの出力と今回の集計は `REPORT_ja.md` にある。

## 通常のDockerで走らせる

リポジトリ直下から、既存の019用Dockerfileを使う。

```bash
docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference
cd conference
bash ros2_jazzy/gz_checks/run_online_batch_checks.sh results/gazebo_online/physical_run
python3 experiments/gz_online_batch_report.py results/gazebo_online/physical_run
```

既存イメージを使う場合は `THESIS_ROS_IMAGE` を指定する。ラッパーはローカルのイメージだけを使う。
出力先にmanifestがあれば停止するので、再試行するときは新しい出力先を指定する。
今回は通常のDocker起動を試み、イメージがなくexit=125になった。
`verification/docker_launcher_log.txt` に実際のエラーを保存した。

ソースは読み取り専用でマウントする。colconのビルド・install・ROSログ、地図NPZとworldは
コンテナー内の一時領域にだけ作る。worldは `max_pixels=4097`。
各地形は同一のworld・初期位置・yaw=0、Gazebo seed=0で両条件を別々に起動し、5秒静置してから出発する。
事前地図は漂着物なし、worldは漂着物あり。半径10mの完全な走行可能ラベル観測を使い、LiDAR・遮蔽・観測誤差は含まない。

## ROS2なしの確認

```bash
cd conference
python3 -m tests.test_gz_online_batch
python3 results/gazebo_online/verification/run_tests.py
python3 ros2_jazzy/gz_checks/online_batch_checks.py --prepare-only --output /tmp/gazebo-online-new-preflight
```

前半の2コマンドはテストの値をGazeboの実測として保存しない。
最後のコマンドも実走せず、実際の事前計画と未実行の20行を作る。既存の出力先は上書きしない。
計画方法は `--planner 'TA*-S+inflate'`（既定、0.5m）または `--planner 'TA*-S'` で指定できる。

## 記録と集計の定義

- `raw/<地形>_<fixedまたはonline>/trajectory.csv`：ミッション送信から終了判定までに受信した
  Gazeboのground truthと直近の速度指令。待機・初回計画中も残す。
- `plans.csv`：固定経路では出発前の6区間の探索と平滑化、オンラインではワーカーが実行した全探索。
  失敗した計画や、遅延によって経路を適用できなかった探索も保存する。
- `replans.csv`：ROSへ送られた経路置換通知。再計画回数は通知数ではなく、`plans.csv` の
  `start_leg` 以外の探索数から数える。区間の開始は再計画に含めない。
- `path_revisions.csv`：followerのstateで確認した適用経路と時刻。ずれは各時刻の経路に対して計算し、
  初回経路がまだないサンプルを除外する。受信・適用の遅延は計画時間に含まない。
- 元のfollowerのログも `follower/` に残す。CSVはヘッダー付きの連番partに分割し、
  数値の文字列表現と全行の順序を保つ。分割ファイルの欠落はエラーとする。各ファイルは5MB未満。
- 到達地点数は、事前に決めた順の5地点について半径0.3m以内に入った接頭部分の数。
  記録点間の線分も調べる。完走はfollowerのcompletedに加えて5地点への到達と出発点への帰還を要求する。
  followerだけがcompletedで途中地点を通っていなければ `incomplete_waypoints` として残す。
- `rollover` は020と同じ厳密な `|roll| > 90°`。原状態は `recorded_status` に保持する。
  転倒を立ち往生・時間切れより優先し、最初の転倒時刻と位置、roll/pitchの95%と最大を出す。
- 接触は記録された中心軌跡の線分と元のtruth lethal、および `truth.rock & ~prior.rock` の
  一意なセル数。後者は014と同じ膨張済み漂着物マスクである。物理接触センサーの測定ではない。
- ペアの差は両方が完走した同じ地形だけで `online - fixed` を計算する。必ず対の数を併記する。
  未完走も走行別表と件数に残す。10地形に検定は行わず、エネルギーは集計しない。

計画時間は地形生成・膨張・巡回順序決定・ROS受け渡しを含まない。
1m/sで1秒は1mに相当するが、計画時間だけで実時間性能や安全性を保証しない。
実走がない今回は、漂着物で停止したか、転倒したか、完走不能の原因、実走中の計画時間を判断できない。
