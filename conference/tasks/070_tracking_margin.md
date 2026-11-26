# 指示書 070：追従のずれを、通れない余白に足す（`--tracking-margin none|fixed|slope`、選んだときだけ）

> **状態：実行中（クラウドの Codex、チャット：研究実装2）**。Gazebo・研究 PC は使わない（研究 PC での評価は、結果を見てから別に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/progress/policy.csv`（今後の方針の 3・5）、
> `conference/tasks/060_distance_clearance.md`・`065_steep_clearance.md`、`conference/results/distance_clearance/REPORT_ja.md`・`REVIEW_ja.md`・`replay.py`、
> `conference/results/steep_clearance/REPORT_ja.md`・`REVIEW_ja.md`・`replay.py`、`conference/results/tracking_error/REPORT_ja.md`・`PROTOCOL_ja.md`・`distribution.csv`（061、**この指示書の値の出どころ**）、
> `conference/results/overlap_goal/REVIEW_ja.md`（057 の出発のマスが塞がる抜け）、`conference/tapp/distance_clearance.py`・`steep_clearance.py`・`pointcloud_map_fine.py`、
> `conference/ros2_jazzy/gz_checks/lidar_checks.py`・`lidar_planner.py`・`lidar_map.py`・`distance_runtime.py`・`plan_maps.py`・`run_lidar_checks.sh` を読むこと。
> ブランチは `codex/070-tracking-margin`（その時点の `realtime-map` の最新から）。結果は `conference/results/tracking_margin/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 060 の `--obstacle-clearance distance` は、障害物から 0.5m（ロボットの半径）未満を通れないにし、0.5m〜1.5m に `w × ((1.5 − d) / 1.0)^2`（w = 1）のソフトなコストを足す。065 の `--steep-clearance distance` は急斜面に同じ式を使う。
  064（研究 PC、各条件 30 回）では、距離の余白で箱から 0.5m 未満の接近が 0/30 になった（今までの余白では 7/30）。ただし**ソフトなコストは経路と箱の距離を約束しない**。
- 061 で、計画の経路と実際の位置のずれ（追従のずれ）を測った（128 回、769,584 標本）。95% 値は全体で 0.274m、箱から 1.5m 以内で 0.275m。
  本当の傾き 10〜20° では 0.614m（92 回）。20° を超える区分は、転倒した回や古い固定経路の回が大半で、値として使えない。
- 方針の 5：「追従のずれを状況ごとの 95% 値で余白に入れる」。**値は 061 の表から前もって決め、064 の結果を見て選び直さない。**

## 作るもの（選んだときだけ働く。既定の `none` の出力・記録はバイト単位で変えない）
`--tracking-margin`（`--obstacle-clearance distance` または `--steep-clearance distance` と一緒のときだけ意味を持つ。どちらもないときは、始める前にエラーで止める）
- **`none`**（既定）：今までどおり。
- **`fixed`**：通れない半径を 0.5m → **0.774m**（0.5 + 061 の全体の 95% 値 0.274）にする。ソフトなコストは 1.5m までのまま、式は `w × ((1.5 − d) / (1.5 − 0.774))^2`。
- **`slope`**：通れない半径を、そのマスの**推定の傾き**で変える（地図が持っている傾きを使う。本当の傾きは使わない）。
  - 10° 未満：0.774m（0.5 + 0.274）
  - 10° 以上：1.114m（0.5 + 0.614。20° を超える区分の値は使わず、10〜20° の値で頭打ちにする）
  - ソフトなコストは `fixed` と同じ形で、そのマスの通れない半径から 1.5m まで。
- 障害物と急斜面の両方に、それぞれの `distance` が選ばれているときだけかける（片方だけならその片方）。
- **出発・目標の扱い（057 の抜けを繰り返さない）**：出発のマス・目標のマスが「0.5m 以上・新しい半径未満」の帯に入ったときは、その計画に限りその帯を通れないにせず、060 の式のソフトなコストとして扱う。
  その計画の診断に `tracking_margin_relaxed=start|goal` を書く。0.5m 未満は今までどおり通れない。
- `lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh` に通し、manifest に記録する。`--save-plan-maps` のときは、マスごとの通れない半径も保存する。

## 保存した地図での確かめ（065 の `replay.py` と同じ 14 件の終了時の地図と、失敗時の出発・目標）
- 条件：地形 `sensor|prior` × 余白 { 障害物 distance＋急斜面 distance（`none`）、同じく `fixed`、同じく `slope` } の 6 条件。
- 出すもの：経路が見つかった数、目標・出発が塞がった数、帯を緩めた数（`start`・`goal`）、本当の箱と本当の急斜面それぞれから 0.5m 未満・0.774m 未満を通る経路の長さ、経路の長さ、箱と急斜面までの最短距離。
- `none` の数字が 065 の結果と一致することを確かめる（連続値は絶対誤差 1e-10 以下）。

## 守ること・やらないこと
- 値（0.274・0.614・0.5m・1.5m・w = 1・25°・10°）は上のとおり。結果を見て変えない。
- 既定の出力・manifest・記録はバイト単位で変えない（直す前の実装と同じ環境で、その場で比べるテスト）。地形の推定は変えない。

## テスト `conference/tests/test_tracking_margin.py`（ROS2・Gazebo なしで動くこと）
1. 既定（`none`）の出力がバイト単位で同じ。
2. `fixed` で、0.5〜0.774m の帯が通れなくなり、ソフトなコストが 0.774m で最大・1.5m で 0 になる。
3. `slope` で、傾き 9° と 11° のマスの通れない半径が 0.774m と 1.114m になる。
4. 出発・目標が帯に入ったとき、経路が見つかり、診断に `start`・`goal` が出る。0.5m 未満では見つからない。
5. `distance` なしで `--tracking-margin fixed` を付けると、始める前にエラーで止まる。
6. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 保存した地図での 6 条件の表と、065 との一致。
3. 研究 PC で評価するときの引数の案。
4. できなかったこと、自信がないこと（特に、通れない帯を広げて狭い通路が塞がる場面）。
