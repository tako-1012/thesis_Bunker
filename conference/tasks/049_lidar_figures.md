# 指示書 049：Gazebo の LiDAR の走行結果から、論文用の図と表をまとめて作る

> **状態：完了（出力は `thesis/out_lidar/`、044 を含めて作り直し済み）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（コミットされた結果を読むだけ）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/thesis/README_ja.md`・`make_figures.py`（015 の修論の図の作り方）、`conference/results/common_eval/REPORT_ja.md`（共通の集計の道具）、
> 次の結果の `REPORT_ja.md`・`REVIEW_ja.md`：`eval_ground_endpoint`（030）、`eval_035`、`real_sensors_compare`（037）、`rtf_compare`（039）を読むこと。
> ブランチは `codex/049-lidar-figures`（その時点の `realtime-map` の最新から）。出力は新しいフォルダ `conference/thesis/out_lidar/`、報告は `conference/results/lidar_figures/REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 2026-12-07 締め切りの ICAROB の本文と、修論の結果の章を書くために、柱 2（走りながら地図を直して計画し直す）の Gazebo の結果を、図と表にまとめたい。
- 柱 1 の図と表は、015 の `thesis/make_figures.py` が作っている（出力 `thesis/out/` は変更禁止）。それと同じ考え方で、**数字を手で写さず、結果のファイルから作る**。
- 研究 PC の走行の結果は、030・035・037・039 が `realtime-map` にある。044（041・043 の評価）は近く入るので、**入ったら同じスクリプトに足せる形**にする。

## 作るもの：`conference/thesis/make_lidar_figures.py`
- 入力：コミットされた結果（各フォルダの `runs.csv`・`summary.csv`・共通の集計ツールの出力）。結果がないフォルダは飛ばし、何を飛ばしたかを表示する。
- 出力（`conference/thesis/out_lidar/`）：PDF・PNG の図、LaTeX・Markdown・CSV の表、本文用の数値のマクロ（`numbers_lidar.tex`）、入力のハッシュ（`sources.json`）。
- 図と表（案。データに合わせて調整してよいが、**新しい実験はしない、数値を作らない**）：
  - **T4**：条件ごとの結果（完走・一部・経路なし・止まったまま・転倒）の表。030（C0・C1・C2）、035（C1＋v1）、037（L・LC）、039（0.3 倍・1.0 倍設定）。各 3 回。
  - **F8**：上の結果を、砂浜 × 条件の色のマスで並べた図（進捗ボードの図と同じ考え方）。
  - **T5**：安全性の表（転倒、本当に通れないマス・漂着物のマスを通った長さ、箱までの最短距離がある実験はその最小、`off_path`・`unsafe_tilt` の回数）。
  - **F9**：地図の更新の時間（センサー別、中央値・95% 値）。038 の前と後、039 の 0.3 倍・1.0 倍設定。
  - **T6**：経路なしの型（`goal_cell` など）の内訳と、046・047 の保存した記録での見込み（`waypoint_feasibility/goal_cell.csv`、`terrain_from_prior/goals.csv`）。
- 3 回ずつの比較なので、**検定はしない**。回数をそのまま示す。エネルギーの数値は出さない。

## 守ること・やらないこと
- 既存の結果・`thesis/out/`・`conference/paper/` には書き込まない。
- 数値を手で写さない。すべて結果のファイルから計算し、`sources.json` に入力のハッシュを残す。
- 報告にない解釈の文（「〜が効いた」など）を図や表に入れない。

## テスト `conference/tests/test_lidar_figures.py`
1. スクリプトが全出力を作り、`numbers_lidar.tex` の値が入力の CSV から計算した値と一致する。
2. 結果のフォルダが 1 つ欠けても、ほかの図は作られ、欠けたことが表示される。
3. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 作った図と表の一覧（それぞれの入力ファイル）と、図の PNG の場所。
3. 044 の結果が入ったときに足す方法。
4. できなかったこと、自信がないこと。
