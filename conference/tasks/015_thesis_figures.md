# 指示書 015：修論の結果の章に使う図と表を、既存の結果ファイルから一括で作る

> **状態：未着手**。最初に `AGENTS.md` と `conference/tasks/BATCH_RULES_ja.md` を読むこと。ブランチは `codex/015-thesis-figures`。

## 背景
修論の結果の章の図と表を、これまでの結果ファイルから**新しい実験なしで**作る。
数値を手で写すと誤りが入るので、図・表・本文に入れる数値を、すべてスクリプトで作る。

## 作るもの
新しいスクリプト `conference/thesis/make_figures.py`（`python3 thesis/make_figures.py` で全部作る）。出力は `conference/thesis/out/`。

| 番号 | 中身 | 元の結果 |
|---|---|---|
| F1 | 本物の砂浜（点群）の例：陰影図の上に A\* と TA\*-S の経路（漂着物なし・ありの 2 か所ずつ） | `build_real(..., dataset="shizuoka_beach_las")` と `run_planner_exact` を**その場で計画して描く**（計画だけなので数秒。既存の結果と同じシナリオ・同じ設定） |
| F2 | 本物の砂浜：TA\*-S と A\* の差（地形コスト・登った高さ・横傾きの 95% 値）の箱ひげ図。**砂浜ごとに 100m と 200m を平均した 48 個**で描く | `results/real_beach_las/offline.csv`（A\* と `TA*-S exact`） |
| F3 | 走りながらの再計画：条件ごとの理想との差 dJ（中央値と 90% 値）。前のデータと点群のデータを並べる | `results/real_beach_las/compare_C_online.csv` |
| F4 | 古い地図（stale）：計画し直す／し直さない、の通れない場所に触れた走行の数（半径 5・10・15m） | `results/online_mission/` の CSV |
| F5 | 1 回の計画にかかる時間の分布（中央値・95%・最大、1m/s で走る距離に換算した目盛りも） | `results/online_mission/` の計画時間の CSV |
| F6 | Gazebo：計画し直す／し直さないの軌跡の比較図と、傾きの時間変化 | `results/online_mission/gazebo_claude/`、`ros2_jazzy/gz_checks/results/claude_docker_run_las/` |
| F7 | 重み：経路長と傾斜の関係（重みごと）。**エネルギーは描かない** | `results/weight_opt.csv` など（ICAROB の原稿の図 `paper/figures/weights.*` と同じデータ） |
| T1 | 本物の砂浜の TA\*-S と A\* の比較表（中央値・差の中央値・Wilcoxon の p・Holm 補正後の p）。**砂浜ごとの 48 個**で検定 | `offline.csv` |
| T2 | 古い地図の表（半径ごとに：完走、接触、dJ の中央値と 90% 値、計画し直した回数、計画時間） | `results/online_mission/` |
| T3 | Gazebo の確認の表（world ごと：完走、接触、所要時間、傾きの 95% 値と地図からの値） | 上の Gazebo の結果 |

- 図は PDF と PNG。表は LaTeX と Markdown の両方。本文に使う数値は `numbers.tex`（`\newcommand`）にまとめて出す。
- **エネルギー（kJ も % も）は図・表・数値に入れない**（利用者の方針）。
- 統計：対応のある Wilcoxon（両側）＋ Holm。検定の単位は**砂浜（48 か所）**。100m と 200m は同じ砂浜なので独立に数えない。
- 経路長は「差」として出すだけにし、「TA\*-S の方が短い」といった主張の文は作らない。
- `conference/thesis/README_ja.md`：図と表ごとに、元のファイル・列・計算方法を書く。

## テスト：`conference/tests/test_thesis_figures.py`
1. `make_figures.py` が最後まで動き、上の図・表・`numbers.tex` がすべてできる。
2. T1 の中央値が `offline.csv` から直接計算した値と一致する。F4・T2 の接触の数が `results/online_mission/online_mission_log.txt` の表の値と一致する。
3. 出力のどこにも `energy` の列・数値がない。

## 報告：`conference/thesis/REPORT_ja.md`
