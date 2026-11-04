# 指示書 021：漂着物のある砂浜 10 か所で、古い地図のまま走る場合と、走りながら計画し直す場合を Gazebo で比べる

> **状態：未着手**。最初に `AGENTS.md` と `conference/tasks/BATCH_RULES_ja.md` を読むこと。
> **指示書020 が `realtime-map` にマージされてから始めること**（020 の急斜面の膨らませと、転倒の判定を使う）。
> ブランチは `codex/021-gazebo-online`（その時点の `realtime-map` の最新から）。結果は `conference/results/gazebo_online/`、報告は同じ場所の `REPORT_ja.md`。

## 背景
指示書014で、走りながら計画し直す仕組み（`online_mission`）を ROS2・Gazebo に入れ、点群の砂浜 1 か所（`08OB87_-0206`）で確かめた
（古い地図のまま走ると漂着物で立ち往生、計画し直すと完走。`results/online_mission/gazebo_claude/`）。
国際学会の論文に使うため、**複数の砂浜で**同じ比較を行う。1 か所の結果は偶然かもしれないので、10 か所に広げる。

## シナリオ
- 点群の砂浜（`shizuoka_beach_las`）の **`test` の最初の 10 か所**、200m、シード 0。
- 本当の地形（Gazebo の world）：`build_real(..., debris=True, dataset="shizuoka_beach_las")`。事前の地図：同じ場所の `debris=False`（`stale`）。
- 地点：5 点の巡回。選び方は指示書014の実験と同じ（`np.random.SeedSequence([0, 3000, 200, パッチの番号])`、漂着物ありの地図で通れる地点）。
  巡回の順は、出発前に事前の地図で決める（014 と同じ）。
- 計画は、**指示書020 の急斜面の膨らませ（0.5m）を入れた TA\*-S** を使う。膨らませなしの結果も比べたい場合は、あとから足せるように、
  計画の方法を引数で選べるようにしておく（今回の必須は膨らませありだけ）。
- world と地図ファイルは、走らせるときに一時フォルダに作る（リポジトリには置かない。大きいため）。`export_gazebo` の `max_pixels` は 019 と同じ 4097。

## 比べる 2 つ（同じ world・同じ地点・同じスタート）
1. **古い地図のまま走る**（`online:=false`）：事前の地図で計画した巡回の経路を、そのまま追う。
2. **走りながら計画し直す**（`online:=true`、半径 10m）：指示書014の `online_planner`。

## 作るもの
- `conference/ros2_jazzy/gz_checks/online_batch_checks.py` と `run_online_batch_checks.sh`（`online_checks.py`・`compare_checks.py` と同じ作り、Docker で動く）。
- 集計 `conference/experiments/gz_online_batch_report.py`。走行ごとに：
  - 結果：**完走／立ち往生／転倒**（020 の判定：どこかで |roll| > 90°）／打ち切り（時間切れ）。最後に到達した地点の数（5 点中いくつ回れたか）。
  - **通れない場所に触れたマスの数**（全体と、漂着物のマスだけの両方）。
  - **1 回の計画の時間**（中央値・95% 値・最大）と、計画し直した回数。
  - 所要時間、経路からのずれ、横傾き・縦傾きの 95% 値と**最大値**。
- 出力：`conference/results/gazebo_online/` に、走行ごとの `runs.csv`、2 つの方法を並べた `summary.csv`、表示した集計表 `gazebo_online_log.txt`、
  各砂浜の軌跡の図（漂着物の位置を重ねる）。元の記録（`trajectory.csv`・`replans.csv`・`plans.csv`）も残す（1 ファイル 5MB 未満）。
- 10 か所しかないので**検定はしない**。件数（例：完走 a/10、転倒 b/10）と、対にした差の中央値だけを出す。**エネルギーは集計しない。**

## Gazebo を走らせられない場合
`BATCH_RULES_ja.md` のとおり、スクリプトとテスト（ROS2 なし）まで作り、「未実行」と書く。Claude が通常の Docker で走らせる。
019 のように特殊な方法で走らせた場合は、その手順と、通常の Docker でも同じ手順で走らせられることを報告に書く。

## テスト：`conference/tests/test_gz_online_batch.py`（ROS2・Gazebo なしで動くこと）
1. 10 か所のシナリオ（world の元になる地図・地点・巡回の順）が、`build_real` と指示書014の地点の選び方を直接呼んだ結果と一致する。
2. 集計：偽の記録（完走・立ち往生・転倒の 3 種類）から、結果の分類と回れた地点の数が正しく出る。
3. 出力にエネルギーの列がない。

## 結果の報告で必ず書くこと
- 10 か所の表（そのまま）。古い地図のまま走る場合に、漂着物で止まったか・転倒したか。計画し直す場合に、完走できなかった砂浜とその理由。
- 1 回の計画の時間（1m/s で走りながら間に合うか）。
- センサーは「半径 10m が誤差なく見える」という簡単化であること（LiDAR は指示書022）。
