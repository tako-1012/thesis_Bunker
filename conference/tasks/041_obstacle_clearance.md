# 指示書 041：計画の地図で、障害物の膨らませを「マスの中心」ではなく「マスの中のどこか」で判定する（障害物との余裕を保つ）

> **状態：実行中（2026-11-19 にクラウドの Codex（研究実装1）へ依頼）**。実装は **クラウドの Codex**（Gazebo・研究 PC は使わない）。Gazebo での評価は、あとで研究 PC で別に行う。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/results/real_sensors_compare/REPORT_ja.md`・`REVIEW_ja.md`（037）、`conference/results/eval_035/REVIEW_ja.md`、
> `conference/results/online_safety/REVIEW_ja.md`（034 の所見 1）、`conference/results/review_fixes/REVIEW_ja.md`・`conference/results/rtf_compare/REVIEW_A_ja.md`（残っている小さな所見）を読むこと。
> ブランチは `codex/041-obstacle-clearance`（その時点の `realtime-map` の最新から）。結果は `conference/results/obstacle_clearance/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 035 の S1 と 037 の `08OB89_-0847` L 2 回目で、ロボットの中心が本当の漂着物の 0.5m のマスに入った（0.38m・0.08m）。
  どちらも、**地図ではそのマスが通れないになっていた**のに、計画した経路がそのマスから 5cm・9mm のところを通っていた。そこに経路を追う側のずれ（0.15m・0.84m）が加わった。
- 原因の作り（Claude がコードで確かめた）：`tapp/pointcloud_map_fine.py` は、見つけた障害物を 0.1m の細かい格子でロボットの半径 0.5m だけ膨らませる（`fine_inflated`）。
  しかし、計画に使う 0.5m のマスを通れないにするのは、**マスの中心の細かい格子が膨らませた範囲に入るときだけ**（`_inflated_coarse` は `fine_inflated` を各マスの中心で拾ったもの）。
  通れるマスの中を通る経路は、マスの中心から最大約 0.35m 離れうるので、**見つけた障害物まで 0.5m より近づきうる（最悪で約 0.15m）**。ロボットの半径は 0.5m なので、車体が障害物に触れうる。
- 経路を追う側のずれの許容（`off_path` 0.75m）と膨らませ（0.5m）の食い違い（034 の所見 1）も同じ問題の一部だが、まずは**計画の側で余裕を保つ**ことを直す。追う側の許容は、この直しの評価を見てから決める。

## 作るもの（**選んだときだけ**働く。既定のふるまい・既存の結果はバイト単位で変えない）
### A. `--obstacle-clearance centre|overlap`（既定 `centre`＝今まで）
- `overlap` のとき、計画に使う 0.5m のマスを「**マスの中の細かい格子（5×5）の 1 つでも膨らませた範囲に入れば通れない**」とする（`coarse_overlap(fine_inflated)` の考え方。障害物そのものの `detected_obstacle` と同じ判定のしかた）。
  - これで、通れるマスの中のどこを通っても、見つけた障害物（0.1m の格子）から 0.5m 以上離れる。新しい値は入れない（膨らませの幅はロボットの半径 0.5m のまま）。
  - 古い地図からの障害物（`prior` の岩）と急斜面の膨らませは、今までどおり（この指示書では変えない）。
- 038 の「変わった周りだけを計算し直す」仕組みの中で、`overlap` も同じように変わった周りだけ計算し直す。`prior`・`local` の両方で使えるようにする。
- `lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh` に引数を通し、manifest に記録する。

### B. 余裕を測る記録（評価のため。`--diagnostics` のときに足す）
- 走行中、ロボットの中心から**その時点の地図で見つけた障害物（0.1m の格子）**までの最短の距離を、記録の周期ごとに残す（`clearance.csv` など）。
- 評価用に、ロボットの中心から**本当の漂着物（評価用の地図）**までの最短の距離も、走行のあとに出せるようにする（集計のスクリプト）。
  今の「0.5m のマスに入った長さ」より、車体が触れたかに近い指標にする。0.5m のマスしかなく箱の形が分からない場合は、その限界を報告に書く。

### C. 残っている小さな所見（`v1`・`v2` の出力は変えない）
1. `thesis_bunker_mission/online_safety.py` の `v2` の `tick`：`command['plan_history']` を `command.get(...)` にする（040 のレビューの所見 1）。
2. `tapp/online_safety.py` の `RemainingPathFollower._path_distance`：切り出した経路で `path_distance` を呼ぶ形にする（所見 3。結果は同じであることをテストで示す）。
3. `path_follower.py`：`safety_enabled` をクラスに既定値 `False` として置く（所見 5）。
4. `lidar_checks.py`：1.0 倍の終わり方の分岐を、CLI の値ではなく `manifest['real_time_factor']` で決める（039 段階 A のレビューの所見）。

## 守ること・やらないこと
- 既定（`centre`）と、`--online-fixes none|v1|v2` の出力・記録は、バイト単位で変えない。テストで示す。
- 膨らませの幅（0.5m）、`off_path` の 0.75m、そのほかの閾値は変えない。結果を見て値を合わせない。
- 経路を追う側（Pure Pursuit）の動きは変えない（追う側の許容は、この評価のあとで決める）。Gazebo は走らせない。

## テスト `conference/tests/test_obstacle_clearance.py`（ROS2・Gazebo なしで動くこと）
1. 既定（`centre`）の出力がバイト単位で同じ（`prior`・`local`、`PointCloudMapFine`・`PointCloudMapMulti`）。
2. マスの中心から外れた位置に置いた小さな障害物で、`centre` では隣のマスが通れるまま、`overlap` では通れないになる。
   `overlap` で計画した経路の上のどの点も、見つけた障害物（0.1m の格子）から 0.5m 以上離れていることを確かめる（`centre` では 0.5m より近づく例を示す）。
3. 038 の「変わった周りだけ」の計算で、`overlap` の結果が、地図全体を計算し直した結果と、すべての更新のあとで一致する。
4. B の記録が出ること。C の 4 つが直っていること（2 は結果が同じこと）。
5. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. テスト 2 の結果（`centre` と `overlap` で、経路と障害物の最短距離の違い）。
3. 通れるマスがどれくらい減るか（保存した走行の地図などで、`centre` と `overlap` の通れないマスの数の違い）。狭い所が通れなくなって、経路なしが増える心配があるかの見込み。
4. 研究 PC で評価するときの引数と、評価の案。
5. できなかったこと、自信がないこと。
