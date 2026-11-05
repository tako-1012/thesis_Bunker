# 指示書022：VLP-16相当の点群による試験的な再計画

> **追記（Claude）**：下の「未実行」は Codex の時点の記述。その後 Claude が通常の Docker で 10 か所を走らせた。結果と原因の調査は `physical_10/README_ja.md`（LiDAR で完走 4/10、経路なし 4/10、地図の端での転倒 2/10）。

点群処理・ROS2/Gazebo連携スクリプト・集計を実装した。**今回のLiDAR実走は3か所・10か所とも未実行**。
Docker起動は `thesis/jazzy-gz:1` がなくexit=125で終了した。既存の021の20走行は、保存済みの実測値をそのまま使う。
`runs.csv` は古い地図・完全なR10観測・LiDARの30行。LiDARの空欄を0と解釈しないこと。

## 通常のDockerでの手順

リポジトリ直下から、既存のDockerfileでイメージを準備する。

```bash
docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference/ros2_jazzy/gz_checks
cd conference
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/gazebo_lidar/physical_3 --patch-count 3
python3 experiments/gz_lidar_report.py results/gazebo_lidar/physical_3
```

3か所で、`/lidar/points` のframe_idが `lidar`（または末尾が `/lidar`）であること、
点群とground_truthのtimestampが届くこと、地面が地図上の適切な位置・高さに重なることを確認する。
ros_gz_bridgeの `gz.msgs.PointCloudPacked` → `sensor_msgs/PointCloud2` とogre2のGPU LiDARは、この環境では未検証。
画面を使わず `--headless-rendering` で起動する。ラッパーのソフトウェア描画は `THESIS_SOFTWARE_RENDERING`、
イメージは `THESIS_ROS_IMAGE` で指定できる。ローカルに準備したイメージだけを使用する。

確認後、**新しい保存先**で10か所に広げる。

```bash
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/gazebo_lidar/physical_10 --patch-count 10
python3 experiments/gz_lidar_report.py results/gazebo_lidar/physical_10
```

既存manifestの上書きは拒否する。地形NPZ・world・colconのbuild/installは一時領域に作る。
ソースは読み取り専用。真値地図はworldと事後評価のためだけに使い、LiDARノードには渡さない。
021の保存済みmanifestの地点・巡回順・初期経路を共有し、境界にある地点もずらさない。

## 仕様・仮定

- 利用者が指定したVLP-16相当：16本、垂直−15°〜+15°を2°刻み、水平360°、10Hz。
- 水平方向1800サンプル、最小距離0.1m、距離の刻み0.01m、平均0・標準偏差0.02mのGaussian測距雑音は**未校正のシミュレーション仮定**。
  同時刻の走査線群として扱い、実機の発光順、走査中の運動歪み、反射率・水面の反射・欠測特性は再現しない。
- 最大距離は指示書の30m。実機仕様の100mを再現する試験ではなく、0.5m地図での近傍再計画を対象とし、描画・処理量を抑えるために維持した上限。
  実験成績から最適化した値ではない。R10の対照と範囲が異なるため、遮蔽だけの効果の比較にはならない。
- 取り付け高さ0.8mは実測値が不明なための仮定。平地でのモデル原点（接地時は地面付近）から車体z軸方向に0.8m。
  base_linkの原点はモデルから0.35mなので、センサーの局所zは `height-0.35`。
  傾いた車体では、地面から鉛直方向に常に0.8mという意味ではない。
- 漂着物は、古い地図の高さを双線形補間した基準から0.3m以上高い点が、1セルに3点以上集まった場合に検出する。
  この閾値は017の仮定の流木高さ0.3mを参考に事前固定した**未校正の仮定**であり、実測の地面分離ではない。
  地形の変化や位置誤差でも誤検出しうる。閾値をtestの結果で変更していない。
- `--sensor-height-m`、`--obstacle-height-m`、`--noise-stddev-m`、`--max-range-m` を指定できる。
  パラメータを選ぶためのデータはvalidationの12か所に限る。今回のvalidation監査でも選択・調整はしていない。

## 点群からの地図

`tapp/pointcloud_map.py` はROSに依存しない。各点を点群時刻のground_truth姿勢でworld座標へ変換する。
姿勢は前後のtimestampから位置とSO(3)を補間し、最新姿勢への無条件な代用はしない。
セル中心に最も近い0.5mのセルへ集約し、直近64点の中央値を高さとする。
障害物上面しか見えない場合、この高さは地面ではなく上面である。
無限値・範囲外・最大距離で飽和した返り値を除く。通過した光線のセルや陰は観測済みにしない。

観測済みセルと事前地図を合わせた高さで、既存の `TraversabilityMap` と同じ式を再計算する。
岩と急斜面の0.5m膨張は既存関数を使い、生の障害物を二重に膨張させない。
周辺の特徴量は再計算しても、点のないセルは未知のまま。点群のない危険箇所は古い地図のsoft priorに依存する。
検出した障害物は保持し、動いて消えた障害物の除去や空き領域の推定は行わない。

計画ワーカーと遅延経路の引き継ぎの**両方**で、`virtual_sense` を点群の観測に置き換えた。
点群の処理は別ワーカーで行い、待ち行列は最新の1走査までに制限する。
点群が0.5シミュレーション秒以上古い場合は停止要求を出し、完全センサーには戻さない。
この期限やtimestamp補間の最大間隔0.1秒も、実機で検証した値ではない。

## 保存と評価

`trajectory.csv`、`plans.csv`、`replans.csv`、適用経路の `path_revisions.csv`、元のfollower記録を残す。
`map_updates.csv` はデコード・座標変換・融合・特徴量計算の時間と入力のSHA-256、失敗・取りこぼしを記録する。
最終の `pointcloud_map.npz` と最初の `first_cloud.npz`、`sensor_status.json` も保存する。
点群の全量は保存しないため、全走査をそのまま再生することはできない。
CSVは5MB未満のヘッダー付きpartへ分割する。

高さ誤差は、最後の地図の観測済みセルを1回ずつ数え、推定した中央値の表面高さと真値DEMの絶対差を集計する。
上面がDEMに入っていない物体などでは、その高さの違いも含む。未観測セルや、真値の評価用配列がない場合の誤差を0にしない。
地図更新時間の分布は成功した更新を対象とし、失敗件数・queue dropも併記する。
計画時間は021と同じ探索・平滑化のみで、地図更新やROS遅延を含まない。

021の実走はNumPy1.26.4、この環境は2.3.5で、漂着物を加えた標高のSHAだけが一致しなかった。
LASのバイト列、岩・lethalマスク、事前地図の標高は一致している。旧標高配列が残っていないため差の最大値は不明。
元の021の数値を書き換えず、この違いを `baseline_input_audit.json` に残す。
新しい実走では、実際に使った高さ・マスクを `evaluation_reference.npz` に保存して、別環境でも同じ配列で評価する。
これは解析用配列であり、`load_map_file` で読む地図やworldのコピーではない。

021の `08OB89_00152` の境界による転倒は除外せず注記して残す。接触数は中心軌跡とマスクとの照合なので車体接触を過少評価する。
Gazeboの進む速さが壁時計より遅い場合、計画・地図更新が間に合うように見えるため、実走の `sim_to_wall_ratio` と合わせて読む。
10か所に検定は行わず、エネルギーは集計しない。

## ROS2なしの確認

```bash
cd conference
python3 -m tests.test_pointcloud_map
python3 results/gazebo_lidar/verification/run_tests.py
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 3 --output /tmp/lidar-new-preflight
python3 experiments/pointcloud_validation.py --output /tmp/lidar-validation-new
```

validationの表は**実際のVLP-16・Gazeboの値ではない**。
validation12地形のDEMセル中心から作った密な人工点群に、固定シードで仮定の測距雑音を足した処理監査である。
走査線・遮蔽・動力学を省いており、値をLiDARの実測欄に埋めないこと。
