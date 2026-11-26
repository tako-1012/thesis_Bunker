# 指示書 065：急斜面からも「距離」で余白を作る（`--steep-clearance distance`、選んだときだけ）

> **状態：完了（レビューは `results/steep_clearance/REVIEW_ja.md`。研究 PC での評価はこれから）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（研究 PC での評価は、あとで 064 の次に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/progress/policy.csv`（今後の方針）、`conference/research/literature_check_ja.md`、
> `conference/tasks/060_distance_clearance.md`・`conference/results/distance_clearance/REPORT_ja.md`・`REVIEW_ja.md`・`replay.py`（060、**同じ考え方を急斜面に使う**）、`tapp/distance_clearance.py`、
> `conference/results/eval_064/REPORT_ja.md`・`REVIEW_ja.md`、`conference/results/eval_057/REVIEW_ja.md`、`conference/results/eval_050/REVIEW_ja.md`（`0167` の傾き停止）、
> `conference/results/terrain_from_prior/replay.py`（047）、`tapp/pointcloud_map_fine.py`・`pointcloud_map_multi.py`・`tapp/traversability.py` を読むこと。
> ブランチは `codex/065-steep-clearance`（その時点の `realtime-map` の最新から）。結果は `conference/results/steep_clearance/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 修論の筋：走りながらの地図の偽の急斜面が、障害物の余白の足りなさを隠していた。060 で障害物の余白を「ハードに通れない 0.5m＋1.5m までのソフトなコスト」の距離で作ると、
  064 段階 1（GPU・1.0 倍、各 15 回）で、距離の余白の 3 条件は箱への接近・漂着物のマスとも 0/45 になった（今までの余白では接近 8/45）。完走は同じ。
- **残った課題：`08OB88_-0167`**。傾きを古い地図から取る条件（`--terrain-source prior`、P・PD）は、目標のマスは塞がらないが、
  **本当の急斜面のすぐそばを通り、追従のずれで急斜面の 0.5m の余白に入って、傾き停止（25°）をくり返して**終わった（050 の P 1 回、057 の PG 3 回、064 の P・PD 計 5〜6 回）。
- 急斜面も今は「25° 超を 0.5m 膨らませてハードに通れない」だけで、膨らませの外はコストが付かない（障害物の `centre` と同じ形）。そのため経路が膨らませの縁ぎりぎりを通る。
- 文献（層を分けた costmap、距離場、Nav2 の膨らませの層）は、通れない所の周りに距離に応じたソフトなコストを付けるのが普通。060 で障害物に効いた形を、急斜面にも使う。

## 作るもの（選んだときだけ働く。既定の動き・既存の結果はバイト単位で変えない）
- `--steep-clearance centre|distance`（既定 `centre`＝今まで）。`--map fine` 専用。
- `distance` のとき：
  1. 計画に使う急斜面のマス（`--terrain-source` の設定どおり：`sensor` ならセンサーから作った急斜面、`prior` なら古い地図の急斜面、`prior_veto` なら合わせたもの）から、各 0.5m マスの中心までの距離の地図を作る。
  2. ハードに通れない所は今までと同じ（急斜面とその 0.5m の膨らませ）。
  3. その外、急斜面から `R_soft` までのマスに、060 と同じ式のソフトなコストを足す：`c = w × ((R_soft − d) / (R_soft − R_hard))²`（`R_hard < d < R_soft`）。
     `R_hard` = 0.5m、`R_soft` = 1.5m、`w` = 1.0（060 と同じ前もって決めた値。結果を見て変えない）。障害物のソフトなコスト（060）と足し合わせてよい。
  4. 平滑化の近道で、急斜面までの最短距離が、元の格子の経路の区間より小さくならないようにする（060 の障害物と同じ考え方）。
  5. 急斜面が変わったら（センサーの地形のとき）、変わった周りだけ距離を作り直す。
- `--obstacle-clearance centre|distance`、`--terrain-source sensor|prior|prior_veto`、`--steep-near-obstacle`、`--ground-near-obstacle`、`--save-plan-maps`、`--pose-trace` と組み合わせられること。`--save-plan-maps` の記録に急斜面のソフトなコストを足す。
- `lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh` に通し、manifest に `R_hard`・`R_soft`・`w` を記録する。

## 確かめ方（Python、コミットされた記録だけ。Gazebo なし）
- 060 と同じ保存した 14 件の地図と地点で、地形 `prior`・`sensor` × 障害物 `centre`・`distance` × 急斜面 `centre`・`distance` の計画をし直して比べる：
  1. **安全（先に書く）**：計画の経路と**本当の**急斜面（評価用の地図で 25° 超）の最短距離（最小・中央値）、本当の急斜面とその 0.5m の余白を通る長さ、1.0m 未満を通る長さ。箱までの最短距離（060 の結果が悪くならないか）。
  2. 経路が見つかる数、目標のマスが塞がる数、経路の長さ・地形のコスト。
  3. `0167` の 5 地点目（050・057・064 で傾き停止が起きた区間）を別に示す。保存した地図で、P・PD の経路が急斜面からどれだけ離れるか。
- 偽の地形で、急斜面の横を通る場面と、急斜面の間が狭い場面（1.2m・1.8m・2.5m）。

## 守ること・やらないこと
- 既定（`centre`）の出力・記録は、バイト単位で変えない（直す前の実装と同じ環境でその場で比べるテスト。別の PC で記録したハッシュとは比べない）。
- 25°・0.5m・`R_soft` 1.5m・`w` 1.0 と式は変えない。結果を見て値を変えない（変えたいときは報告に書く）。
- 傾き停止（`unsafe_tilt`、25°）の仕組みは変えない。Gazebo は走らせない。既存のテストを弱めない。既存の結果は書き換えない。

## テスト `conference/tests/test_steep_clearance.py`（ROS2・Gazebo なしで動くこと）
1. 既定の出力がバイト単位で同じ。
2. `distance` のハードに通れないマスが今までと同じ。ソフトなコストが式どおり（0.5m で `w`、`R_soft` で 0）。障害物のソフトなコストと足し合わされる。
3. 偽の地形で、急斜面の横を通る経路が今までより離れる。急斜面の間が 1.2m でも経路が見つかる。
4. 平滑化の近道が、急斜面までの最短距離を縮めない。急斜面が変わったときの作り直しが、全体を作り直した結果と一致する。
5. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 確かめ方 1〜3 の表（安全を先に）と、狭い場面の結果。
3. 研究 PC で比べるときの引数と、評価の案。
4. できなかったこと、自信がないこと。
