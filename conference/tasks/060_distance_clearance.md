# 指示書 060：障害物の余白を「障害物までの距離」で作り、地形とは切り離す（`--obstacle-clearance distance`、選んだときだけ）

> **状態：実行中（2026-11-23 にクラウドの Codex（研究実装1）へ依頼）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（研究 PC での評価は、あとで別に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/research/literature_check_ja.md`（文献の確かめ）、
> `conference/results/eval_050/REVIEW_ja.md`・`results/false_steep_causes/REVIEW_ja.md`（053）・`results/steep_near_obstacle/REVIEW_ja.md`（055）・`results/overlap_goal/REVIEW_ja.md`（052）・`results/obstacle_clearance/REPORT_ja.md`（041）、
> `tapp/pointcloud_map_fine.py`・`pointcloud_map_multi.py`・`tapp/online_mission.py`・`tapp/collision.py`・`tapp/endpoint_policy.py`（`smooth_cost_aware`）・`tapp/obstacle_clearance.py` を読むこと。
> ブランチは `codex/060-distance-clearance`（その時点の `realtime-map` の最新から）。結果は `conference/results/distance_clearance/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- ロボットは直径約 1m（半径 0.5m）。見つけた障害物（0.1m 格子）は 0.5m 膨らませ、計画の 0.5m 格子の**中心**がその中なら通れない（`centre`）。
  これは「ロボットの中心が障害物から 0.5m 以上」＝**車体の縁と障害物の間の余白が 0m** ということ。経路の追従のずれは最大 0.6〜0.95m ある。
- 053 で、走りながらの地図の偽の急斜面の 80% が障害物の膨らませから 0.5m 以内にあった。050 で、傾きを古い地図から取る `prior` にすると、偽の急斜面はなくなったが、
  `00332` で 6 回とも漂着物のマスを通った（標準は 0/3）。**偽の急斜面とその膨らませが、たまたま箱からの余白（1.0〜1.5m）になっていた**と考えている。
- 余白を増やす 041 の `overlap`（格子のどこかが掛かれば通れない）は、目標のマスまで塞いで完走が減った（052 の `overlap_goal` は目標のマスだけ例外にする）。
- 文献（Lu ら 2014 の層を分けた costmap、Voxblox の距離場、Nav2 の膨らませの層。`literature_check_ja.md` で実在を確認）は、
  **地形の通れなさと障害物の余白を別の層にし、障害物の余白は「ハードに通れない近い所」と「距離に応じたソフトなコスト」に分ける**設計をとる。

## 作るもの（選んだときだけ働く。既定の動き・既存の結果はバイト単位で変えない）
- `--obstacle-clearance centre|overlap|overlap_goal|distance`（既定 `centre`）。`distance` は `--map fine` 専用。
- `distance` のとき、障害物の扱いを次に変える（地形の急斜面・岩・その膨らませ、まだ見ていないマスの扱いは変えない）：
  1. **距離の地図**：見つけた障害物（0.1m 格子の `fine_obstacle`）から、各 0.5m マスの中心までの距離（障害物の 0.1m のマスの縁まで）を計算する。障害物が増えたら、変わった周りだけ作り直す（038 の考え方と矛盾しないこと）。
  2. **ハードに通れない**：距離が `R_hard` 以下のマス。`R_hard` は今の `centre` と同じ 0.5m（ロボットの半径）にする（つまり通れないマスは `centre` と同じ）。
  3. **ソフトなコスト**：距離が `R_hard` から `R_soft` の間のマスに、障害物に近いほど高いコストを足す。
     - 形：`c_obs = w_obs * ((R_soft - d) / (R_soft - R_hard))^2`（`R_hard < d < R_soft`、それ以外は 0）。
     - `R_soft` は `--clearance-soft-m`（既定 1.5m。半径 0.5m＋これまでの最大の追従のずれ 0.95m を丸めた値。061 の分析のあとで見直す）。
     - `w_obs` は地形のコストの最大（`alpha + beta = 1`）と同じ 1.0（地形のいちばん走りにくい所と同じ重さで、箱の近くを避ける）。前もって決めた値で、結果を見て変えない。
     - 地形のコストに足す（最大で 2.0 になってよい）。
  4. **平滑化**：経路を平滑化（`smooth_cost_aware` など、見通しで近道する処理）するとき、近道で**障害物までの最短距離が、元の格子の経路の区間の最短距離より小さくならない**ようにする（ソフトなコストの帯を近道で突っ切らない）。
- 目標のマスは、ハードに通れない場合だけ塞がる（ソフトなコストでは塞がらない）。`overlap_goal` と組み合わせる必要はない。
- `--terrain-source sensor|prior|prior_veto`、`--steep-near-obstacle`、`--online-fixes`、`--tracking`、`--save-plan-maps`、`--pose-trace` と組み合わせられること。`--save-plan-maps` の記録に距離の地図（またはソフトなコスト）を足す。
- `lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh` に通し、manifest に `R_hard`・`R_soft`・`w_obs` を記録する。

## 確かめ方（Python、コミットされた記録だけ。Gazebo なし）
- 053 が使った 14 件の終了時の地図（見つけた障害物・評価用の地図・箱の位置）と、保存された地点で、`centre`・`overlap`・`overlap_goal`・`distance` の計画の地図を作り、同じ計画（A*/TA*-S と平滑化）をし直して比べる：
  1. **安全（先に書く）**：計画の経路と本当の箱（`debris_footprints`）の最短距離（最小・中央値）、0.5m・1.0m を下回る長さ。漂着物のマスを通る長さ。
  2. 目標のマスが塞がる数、経路が見つかる数、経路の長さ・地形のコストの増え方。
  3. 地形の作り方を `prior` にした場合（047 の `replay.py` の作り方）も同じ表を出す（050 の P で起きたことを、保存した地図で再現できるか）。
- 偽の地図で、箱の間が狭い場面（1.2m・1.8m・2.5m）を作り、`distance` で通れなくならないこと、迂回の長さを示す。

## 守ること・やらないこと
- 既定（`centre`）と `overlap`・`overlap_goal` の出力・記録は、バイト単位で変えない（直す前の実装と同じ環境でその場で比べるテスト。別の PC で記録したハッシュとは比べない）。
- `R_hard`・`R_soft`・`w_obs` と式は、前もって決めた上の値。確かめ方の結果を見て変えない（変えたいときは報告に書き、Claude と相談）。
- Gazebo は走らせない。既存のテストを弱めない。既存の結果は書き換えない。

## テスト `conference/tests/test_distance_clearance.py`（ROS2・Gazebo なしで動くこと）
1. 既定と `overlap`・`overlap_goal` の出力がバイト単位で同じ。
2. `distance` のハードに通れないマスが `centre` と同じ。ソフトなコストが式どおり（距離 0.5m で `w_obs`、`R_soft` で 0）。
3. 偽の地図で、箱の横を通る経路が `centre` より離れる。箱の間が 1.2m（ハードに塞がらない幅）でも経路が見つかる。
4. 平滑化の近道が、障害物までの最短距離を縮めない。
5. 障害物が増えたとき、変わった周りだけの作り直しが、全体を作り直した結果と一致する。
6. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 確かめ方 1〜3 の表（安全を先に）と、狭い場面の結果。
3. 研究 PC で比べるときの引数と、評価の案（地形の直し あり・なし × 余白 `centre`・`distance` の 2×2）。
4. できなかったこと、自信がないこと。
