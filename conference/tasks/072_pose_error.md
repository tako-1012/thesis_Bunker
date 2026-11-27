# 指示書 072：Gazebo の走行で、ロボットが使う自分の位置にずれを入れる（`--pose-error`、選んだときだけ）

> **状態：完了（結果は `results/pose_error/`、レビューは `REVIEW_ja.md`。研究 PC での評価は別に頼む）**。Gazebo・研究 PC は使わない（研究 PC での評価は、実装を取り込んでから別に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/progress/policy.csv`（今後の方針。11/26 に範囲を決め直した）、
> `conference/tasks/058_pose_trace.md`・`conference/results/pose_trace/REPORT_ja.md`・`REVIEW_ja.md`、`conference/tapp/pose_trace.py`、
> `conference/ros2_jazzy/gz_checks/lidar_checks.py`・`lidar_runtime.py`・`lidar_map.py`・`run_lidar_checks.sh`、
> `conference/ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/`（位置を受け取って地図・計画・追従に渡す所）、`conference/experiments/eval_runs.py` を読むこと。
> ブランチは `codex/072-pose-error`（その時点の `realtime-map` の最新から）。結果は `conference/results/pose_error/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 修論の範囲（11/26 に決めた）：ドローンが撮ったばかりの地図を正とし、その上で人が選んだ地点を効率よく回る。
- 今の Gazebo の評価では、ロボットは**自分の位置を Gazebo の正解から受け取っている**（自己位置推定をしていない）。実機では、ここが一番最初に崩れる。
- BUNKER には GNSS がない。位置は「LiDAR と IMU で動きを積み上げる」＋「ドローンの地図に重ねて直す」で出す予定で、ずれが残る。
- 先に「**どれくらいの位置の精度があれば、地点を回り切れるか**」を測りたい。そのために、ロボットが使う位置にわざとずれを入れる仕組みを作る。

## 作るもの（選んだときだけ働く。既定の `none` の出力・記録はバイト単位で変えない）
`--pose-error none|bias|drift`、`--pose-error-seed <整数>`（既定 0）
- **ずれを入れる先**：ロボットの側が使う位置すべて（地図に点群を重ねる位置、計画の出発の位置、経路の追従、地点に着いたかの判定）。実機と同じく、**同じずれた位置を一貫して使う**。
- **ずれを入れない先**：評価（`eval_runs.py` の、本当の急斜面・箱までの距離・転倒など）は、今までどおり Gazebo の正解の位置で測る。
- **`bias`**：出発の時点から一定のずれ（地図に最初に重ねたときの位置合わせのずれを想定）。`--pose-error-bias <海岸に沿う m>,<海に向かう m>,<向き °>`。
  海岸に沿う・海に向かうの向きは、砂浜の `tangent`・`normal`（`conference/data/shizuoka_beach_las/` の各 npz）で決める。
- **`drift`**：走った距離に比例して溜まるずれ（動きの積み上げのずれを想定）。`--pose-error-drift-pct <%>`。
  走った距離 1m ごとに、海岸に沿う向き・海に向かう向きそれぞれ、平均 0・標準偏差 `pct/100 × 1m` の正規乱数を足していく（ずれの標準偏差が走った距離の平方根に比例するランダムウォーク）。
  向きのずれは今回は入れない（報告の「できなかったこと」に書く）。乱数は `--pose-error-seed` と砂浜・回の番号から決め、manifest に記録する。
- `--pose-trace` のときは、**正解の位置とずれた位置の両方**を保存する。manifest に、選んだずれの種類と値を記録する。
- `lidar_checks.py`・`run_lidar_checks.sh` に通す。

## 研究 PC で評価するときの値（前もって決めておく。今回は走らせない）
- `bias`：海岸に沿う 0.25m・0.5m・1.0m（海に向かう 0、向き 0）と、向き 2°（位置 0）。
- `drift`：0.5%・1%・2%。
- 比べる相手：ずれなし（`none`）。地形は古い地図から取る（`--terrain-source prior`）、障害物の余白は距離（`--obstacle-clearance distance`）。

## 守ること・やらないこと
- 既定の出力・manifest・記録はバイト単位で変えない（直す前の実装と同じ環境で、その場で比べるテスト。別の PC で記録したハッシュとは比べない）。
- 計画・地図の作り方・値は変えない。ずれを入れるだけ。Gazebo は走らせない。

## テスト `conference/tests/test_pose_error.py`（ROS2・Gazebo なしで動くこと）
1. 既定（`none`）の出力がバイト単位で同じ。
2. `bias` で、ロボットの側に渡る位置が、海岸に沿う向き・海に向かう向き・向きに正しくずれる（`tangent`・`normal` が斜めの砂浜でも）。
3. `drift` が、同じシードで同じ列になり、違うシードで違う列になる。1,000 本の列で、走った距離 L でのずれの標準偏差が `pct/100 × √L` に合う（許す誤差を決めて書く）。
4. 評価の側（`eval_runs.py`）が、ずれた位置ではなく正解の位置を使う。
5. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. ずれを入れた所の一覧（地図・計画・追従・到着の判定のそれぞれで、どの関数か）。入れ漏れがないことをどう確かめたか。
3. 研究 PC で評価するときの引数の案（上の値のとおり）と、1 回の見込みの時間。
4. できなかったこと、自信がないこと。
