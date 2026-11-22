# 指示書 052：障害物の膨らませはマス全体で判定し、目標のマスだけは中心で判定する（`--obstacle-clearance overlap_goal`、選んだときだけ）

> **状態：実行中（2026-11-22 にクラウドの Codex（研究実装1）へ依頼）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（Gazebo での評価は、あとで研究 PC で別に行う）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/tasks/041_obstacle_clearance.md`、`conference/results/obstacle_clearance/REPORT_ja.md`・`REVIEW_ja.md`、
> `conference/results/eval_044/REPORT_ja.md`・`REVIEW_ja.md`・`no_path_evidence.csv`（この指示書の根拠）、`tapp/pointcloud_map_fine.py`・`pointcloud_map_multi.py`・`tapp/online_mission.py` を読むこと。
> ブランチは `codex/052-overlap-goal`（その時点の `realtime-map` の最新から）。結果は `conference/results/overlap_goal/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 障害物（箱）を見つけると、計画の地図で 0.5m 膨らませて通れないにする。今の標準 `centre` は、マスの**中心**が膨らませの中かで判定する。そのため経路が箱のすぐそばを通ることがある（044 で、計画の経路が箱から 0.354m を通った回、ロボットが 0.432m まで近づいた回がある）。
- 041 の `overlap` は、マスの**どこか**が膨らませにかかれば通れないにする。044 の 60 回では、箱に近づいた回は O・OT で 0 回（B・T で 2 回。3 回ずつなので差とは言えない）だったが、
  **完走が 10/15 → 6/15 に減った**。O・OT の「経路なし」のうち 12 回は、**目標のマスが `overlap` の膨らませで塞がった**もの（`1417` の目標 (199, 151)、`0847` の目標 (281, 117)。同じ地図で `centre` なら塞がらない。急斜面・岩ではない）。
- そこで、経路の途中は `overlap` で箱から離し、**今向かっている目標のマスだけ**は `centre` で判定する。目標のマスの中心は `centre` の基準（箱の点から 0.5m）を守る。

## 作るもの（選んだときだけ働く。既定の動き・既存の結果はバイト単位で変えない）
- `--obstacle-clearance centre|overlap|overlap_goal`（既定 `centre`）。`overlap_goal` は `--map fine` 専用（`overlap` と同じ制限）。
- `overlap_goal` のとき：
  - 計画に使う地図は `overlap` と同じ。
  - ただし、**その時点の目標のマス**だけは、障害物の膨らませを `centre` で判定し直した値を使う。急斜面・岩・その膨らませ、まだ見ていないマスの扱いは変えない。
  - 目標が次の地点に移ったら、前の目標のマスは `overlap` に戻す。スタートのマスの扱いは今までどおり。
- `PointCloudMapFine`・`PointCloudMapMulti` の両方、`--terrain-source sensor|prior|prior_veto`、`--online-fixes`・`--tracking`・`--save-plan-maps` と組み合わせられること。
- `lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh` に通し、manifest に記録する。

## 確かめ方（Python、Gazebo なし）
- 044 の `no_path_evidence.csv` の 12 回について、記録されている値（`centre_halo`・`overlap_halo`・急斜面・岩）から、`overlap_goal` なら目標のマスが通れたかを表にする（経路全体があったかは、地図がコミットされていないので分からない、と書く）。
- 偽の地図で、目標のマスのそばに箱がある場面と、経路の途中のマスのそばに箱がある場面を作り、`centre`・`overlap`・`overlap_goal` の経路と箱までの距離を比べる。

## 守ること・やらないこと
- 既定（`centre`）と `overlap` の出力・記録は、バイト単位で変えない（直す前の実装と同じ環境でその場で比べるテスト。別の PC で記録したハッシュとは比べない）。
- 0.5m・0.1m の格子・0.3m・3 点などの値は変えない。結果を見て値を合わせない。Gazebo は走らせない。

## テスト `conference/tests/test_overlap_goal.py`（ROS2・Gazebo なしで動くこと）
1. 既定と `overlap` の出力がバイト単位で同じ。
2. 偽の地図で、目標のマスが `overlap` では塞がり、`overlap_goal` では通れる（`centre` で塞がる目標は、`overlap_goal` でも塞がる）。
3. 経路の途中のマスは、`overlap_goal` でも `overlap` と同じく通れないのまま。目標が次に移ると、前の目標のマスは `overlap` に戻る。
4. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 12 回の表と、偽の地図での比較。
3. 研究 PC で比べるときの引数と、評価の案（044 と同じ条件で B と `overlap_goal`）。
4. できなかったこと、自信がないこと。
