# 指示書 055：見つけた障害物の膨らませの中にできた急斜面には、急斜面の膨らませを足さない（`--steep-near-obstacle no_inflate`、選んだときだけ）

> **状態：実行中（2026-11-23 にクラウドの Codex（研究実装1）へ依頼）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（Gazebo での評価は、050・054 の結果を見てから別に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/results/false_steep_causes/REPORT_ja.md`・`REVIEW_ja.md`・`PROTOCOL_ja.md`・`replay.py`（053、**この指示書の根拠**）、
> `conference/results/terrain_from_prior/replay.py`（047）、`conference/results/waypoint_feasibility/REPORT_ja.md`（046）、`conference/results/overlap_goal/REVIEW_ja.md`（052）、
> `tapp/pointcloud_map_fine.py`・`pointcloud_map_multi.py`・`traversability.py` を読むこと。
> ブランチは `codex/055-steep-near-obstacle`（その時点の `realtime-map` の最新から）。結果は `conference/results/steep_near_obstacle/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- Gazebo の評価で一番多い失敗は「経路なし」（`goal_cell`）。多くは、走りながらの地図が**本当は急斜面でない所を急斜面（25° 超）と判断**し、その **0.5m の膨らませ**で目標のマスが塞がるもの（046：35 回中 28 回）。
- 053 で、コミットされた 14 件の記録を調べると、終了時の偽の急斜面 2,040 マスのうち **1,633 マス（80%）が、見つけた障害物の膨らませから 0.5m 以内**だった（正しく急斜面でないマスでは 5%、正しい急斜面では 0.43%）。
  箱の縁で地面と箱の上の高さが混ざり、傾きが大きく出ていると考えられる（029 の合成のテストでも、箱の隣のマスが 28.8° になった）。
- そのようなマスは、すでに障害物の膨らませで通れないことが多い。そこへ急斜面としての 0.5m の膨らませが**さらに外へ**足されるため、通れない範囲が広がり、目標が塞がりやすくなる。

## 作るもの（選んだときだけ働く。既定の動き・既存の結果はバイト単位で変えない）
- `--steep-near-obstacle keep|no_inflate`（既定 `keep`＝今まで）。`--map fine` 専用。
- `no_inflate` のとき：
  - 急斜面のマスのうち、**その時点の障害物の膨らませ（計画に使う粗いマスの膨らませ。`--obstacle-clearance` の設定どおり）の中にあるもの**は、通れないのまま残すが、**急斜面としての 0.5m の膨らませの元にしない**。
  - 障害物の膨らませの外にある急斜面は、今までどおり膨らませる。古い地図の岩、古い地図の急斜面（`--terrain-source prior`・`prior_veto` のとき）の扱いは変えない。
  - 障害物の膨らませが変わったら（新しい障害物を見つけたら）、急斜面の膨らませも作り直す。038 の「変わった周りだけ」の計算と矛盾しないこと。
- `PointCloudMapFine`・`PointCloudMapMulti` の両方、`--terrain-source sensor|prior|prior_veto`、`--obstacle-clearance centre|overlap|overlap_goal`、`--online-fixes`・`--save-plan-maps` と組み合わせられること。
- `lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh` に通し、manifest に記録する。

## 確かめ方（Python、コミットされた記録だけ。Gazebo なし）
- 053 と同じ 14 件の終了時の地図（保存された推定の高さ・見つけた障害物・評価用の地図）で、`keep` と `no_inflate` の計画の地図を作り直し、次を数える：
  1. 誤って通れないマス（評価用の地図では通れる）のうち、急斜面とその膨らませによるものが、どれだけ減るか。
  2. 本当の急斜面（25° 超）とその 0.5m の余白のうち、通れると誤るマスが増えるか（**見落としの危険。先に書く**）。
  3. 046・047 の `goal_cell` の記録（`waypoint_feasibility/goal_cell.csv`、`terrain_from_prior/goals.csv`）のうち、記録がある回で、目標のマスが通れるようになり、そこへの経路があるか。
- 053 の型（箱付近・点が少ない・境目・高低差）ごとに、減った数を示す。`0167` の 5 地点目（箱と関係ない型）は、変わらないはずなので、変わらないことを確かめる。

## 守ること・やらないこと
- 既定（`keep`）の出力・記録は、バイト単位で変えない（直す前の実装と同じ環境でその場で比べるテスト。別の PC で記録したハッシュとは比べない）。
- 25°・0.5m・障害物の判定の値は変えない。結果を見て値や定義を変えない。Gazebo は走らせない。

## テスト `conference/tests/test_steep_near_obstacle.py`（ROS2・Gazebo なしで動くこと）
1. 既定の出力がバイト単位で同じ。
2. 偽の地図で、障害物の膨らませの中の急斜面は通れないのままだが、その外へ急斜面の膨らませが広がらない。障害物の膨らませの外の急斜面は、今までどおり膨らむ。
3. 障害物を新しく見つけたとき、その周りの急斜面の膨らませが作り直される（全体を作り直した結果と一致する）。
4. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 確かめ方 1〜3 の表（見落としの危険を先に）、型ごとの内訳、`0167` の結果。
3. 研究 PC で比べるときの引数と、評価の案。
4. できなかったこと、自信がないこと。
