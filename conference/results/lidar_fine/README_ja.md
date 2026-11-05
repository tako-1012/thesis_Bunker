# 指示書023：障害物だけを0.1m格子で判定する

新方式は `PointCloudMapFine`。地面の高さ・コスト・観測済みマスクと履歴は022と同じ0.5m格子で保持し、
各点に0.1mセルIDも保持して、その細セル内の高い点が3点以上の場合に障害物とする。
高さ基準は022と同じ古い地図の双線形補間、閾値は0.3m。
直近64点を保持する0.5mセル単位の履歴、検出済み障害物の保持も変えていない。

## 膨張の定義

0.1mセルは既存の0.5mセルの境界に合わせて5×5に分割する。最初の粗セルは両軸−0.25〜+0.25m。
細格子上の検出を半径0.5mの円盤（5細セル）で1回だけ膨張し、含まれる細セルがある粗セルを通行不可とする。
粗セルへ集約した障害物には、追加の膨張をしない。
更新のたびに既に膨張したマスクを膨張させず、新しく検出した生の細セルの膨張との和を取る。

「重なる粗セル」はセルの領域として定義する。距離のテストは、障害物の細セル領域と粗セル領域との最小距離で行う。
セル中心だけの距離ではない。円盤を0.1mで離散化する近似は残る。
既存の岩の膨張はそのまま、急斜面には変更していない `footprint.inflate_steep` を使う。
`TraversabilityMap`、TA*・TA*-Sのコスト式は変更しない。

0.1m・0.3m・3点・半径0.5mは指示書で事前指定された値であり、パラメータの選択・調整はしていない。
新方式ではこれらに反する値を拒否する。点がない粗セルは022と同様に未知のまま。

## 022と同じ10地形を走らせる

リポジトリ直下から通常のDocker用イメージを用意する。

```bash
docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference/ros2_jazzy/gz_checks
cd conference
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/lidar_fine/physical_10 --patch-count 10 --map fine
python3 experiments/lidar_fine_report.py results/lidar_fine/physical_10
```

新方式はメッシュの見た目・heightmapの衝突、速さ0.3倍・途切れの基準1.0秒を固定し、manifestに記録する。
環境変数で異なる速さ・期限を指定した場合は停止する。
022の実走時の `evaluation_reference.npz` の標高をworld入力へ再利用し、NumPyの版の差で漂着物の高さが変わらないようにする。
生の障害物・水・欠損のマスク、開始点・巡回順は既存のものを保持し、参照の通行不能マスクと一致しなければ停止する。
world・入力地図・build/installは一時領域に作る。既存の結果は書き換えない。

**今回の新方式のGazebo実行は未実行**。上のラッパーを試みたが、標準イメージがなくexit=125で終了した。
測っていない完走・FP/FN・更新時間を補っていない。既存022の保存済み実測と、新方式の未実行欄を比較表へ並べる。

## 既定の022方式

`--map` を省略するか `--map coarse` とすると、変更していない `PointCloudMap` 自体を使用する。
この場合、ラッパーの速さ・途切れの既定値も今までどおり1倍・0.5秒である。
022の実走と同じ設定で旧方式を走らせる場合は、従来と同じ環境変数を付ける。

```bash
THESIS_REAL_TIME_FACTOR=0.3 THESIS_STALE_TIMEOUT_S=1.0 \
  bash ros2_jazzy/gz_checks/run_lidar_checks.sh <新しい保存先> --patch-count 10 --map coarse
```

既定/明示coarseと元のクラスの全update辞書（時計を固定した試験）とNPZのバイト一致を検証する。
manifestも元のスナップショットと比較する。機械固有のPython/NumPy欄だけ実行中の値に合わせ、実験条件は変えない。
新しいROS2パラメータはcoarseを既定にし、旧manifestには新方式の項目を追加しない。

## 集計の意味

`runs.csv` は021のfixed・online、022のlidarの保存値30行と、新しいfineの10行。
旧走行値を再計算せずに保持し、旧LiDARの地図に対する追加の監査だけを実行する。
`summary.csv` と、表示した全文 `lidar_fine_log.txt` を保存する。

- `map_*`：観測済みの一意な粗セルだけを数え、最終通行不可マスクを元のtruth lethalと比較したFP/FN。
- `clearance_*`：同じ真値に急斜面の0.5m膨張を加えた参照とのFP/FN。意図した安全余裕と推定の誤りを区別するためCSVにも保存する。
- `detector_*`：膨張前の検出を生の障害物と比較したFP/FN。水・欠損は除外し、その上の検出を別に数える。
  これは点群からの検出器の監査で、既存の事前障害物まで含む最終lethalの誤りとは異なる。
- `*_box_adjacent_cells`：Gazeboが作った連結成分の外接長方形の箱の外側で、4方向に1粗セルだけ隣接する部分。
  022の「隣の1マス」という原因分析は主に膨張前の検出であり、最終lethalのFPと混同しない。
- `debris_touching_runs`：記録した中心軌跡が漂着物マスクに触れた走行。車体前端の接触は過少評価する。
- 地図更新時間は各走行の中央値・95%・最大と、その走行単位の集計。失敗・未実行値は0にしない。

021の2条件には最終の点群地図スナップショットがないため、地図のFP/FNは未記録として残す。
観測済み集合が走行によって異なるので、件数だけで精度の優劣を断定しない。
10地形の検定・エネルギー集計は行わない。境界による転倒は除外せず残す。

## ROS2なしの確認

```bash
cd conference
python3 -m tests.test_pointcloud_map_fine
python3 results/lidar_fine/verification/run_tests.py
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 10 --map fine --output /tmp/lidar-fine-new
```

箱の試験は0.02mの測距方向の雑音を加えた合成入力で、固定したvalidation用のシード100〜104を使う。
実機やGazeboの走査・遮蔽は再現しない。合成箱の結果を実走の完走率や処理時間へ置き換えない。
細分化により疎な物体の検出が減る可能性、中央値の高さから生じる急斜面、細格子のCPU・メモリ負荷は未評価の部分として残る。
Claudeには実走で通路の閉塞・見落とし・隣接セルのFP・取りこぼし・更新時間を確認してほしい。
