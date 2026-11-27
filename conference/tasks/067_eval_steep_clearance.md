# 指示書 067：急斜面の距離の余白（065）を、研究 PC の Gazebo で評価する（GPU 描画・1.0 倍）

> **状態：負の結果（結果は `results/eval_067/`、レビューは `REVIEW_ja.md`）**。実行は**研究 PC の担当**（Mac の Codex から `ssh hayashi`）。コードは変えない（走らせて集計するだけ）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/progress/policy.csv`（今後の方針）、
> `conference/tasks/064_eval_2x2.md`・`conference/results/eval_064/REPORT_stage2_ja.md`・`REVIEW_stage2_ja.md`・`run064.sh`（同じやり方の見本）、
> `conference/results/steep_clearance/REPORT_ja.md`・`REVIEW_ja.md`（065）、`conference/results/common_eval/REPORT_ja.md` を読むこと。
> 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/067-eval`（`origin/realtime-map` から）。結果は `conference/results/eval_067/`。

## 背景
- 064（180 回、GPU・1.0 倍）で、障害物の余白を距離で作ると（060 の `distance`）、完走を減らさずに箱への接近がなくなった（前もって決めた検定で、4 比較中 3 つが有意）。
- **残った課題：`08OB88_-0167`**。傾きを古い地図から取る条件（PD）は、目標は塞がらないが、本当の急斜面のすぐそばを通り、傾き停止（25°）をくり返して完走できない。
- 065 で、急斜面にも同じ距離の余白（ハード 0.5m＋1.5m までのソフトなコスト）を付ける `--steep-clearance distance` を作った。保存した地図では、本当の急斜面から 0.5m 未満を通る経路の長さが 2.5m → 1.0m に減った。

## 走らせるもの
- 砂浜：064 と同じ 5 か所（`08OB86_-0205`・`08OB88_-1417`・`08OB88_-0167`・`08OB88_00332`・`08OB89_-0847`）。
- 共通の設定（064 と同じ）：`--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 --sensors lidar_real+depth2 --diagnostics --real-time-factor 1.0 --save-plan-maps --pose-trace --obstacle-clearance distance`、
  GPU 描画（`THESIS_RENDER=gpu`）、`THESIS_STALE_TIMEOUT_S=1.0`、`THESIS_FINE_PROTOCOL=rtf_check`。
- 条件（4 つ。どれも障害物の余白は距離）：
  - **PD**：`--terrain-source prior`（064 の PD と同じ。同じ日の比べる相手）
  - **PDS**：`--terrain-source prior --steep-clearance distance`
  - **GD**：`--ground-near-obstacle exclude`（064 の GD と同じ）
  - **GDS**：`--ground-near-obstacle exclude --steep-clearance distance`
- 回数：各砂浜 × 各条件 **6 回**（1 条件 30 回、合わせて 120 回）。砂浜ごとに 4 条件を順に回す。前もって決めた回数で、途中の結果を見て変えない。
- 1 回目の走行のあとで、`gpu_rendered=true`、実測の倍率（0.9 倍以上）、記録の量を確かめてから続ける。外れたら止めて報告する。

## 集計（`experiments/eval_runs.py`・`plan_map_inspect.py`・`pose_trace_inspect.py`）
1. **安全性（先に書く）**：傾き停止があった走行（`unsafe_tilt`）、本当の急斜面とその 0.5m の余白に実際の軌跡が入った走行と長さ、転倒、箱から 0.5m 未満・漂着物のマス。
2. 結果（完走・一部・経路なし・止まったまま・転倒・傾きのくり返しでの終了・点群が古くなった終了）、経路なしの型。
3. `0167` の 5 地点目の区間を別に示す。経路の長さ・走行時間。
- 判断のしかた（**前もって決めた検定**）：1 条件 30 回で、Fisher の両側正確検定。
  - 比べる組み合わせ：**PDS と PD**、**GDS と GD** の 2 つ。
  - 指標：「傾き停止があった走行」「本当の急斜面の余白に入った走行」「完走」の 3 つ。指標ごとに Holm で補正し、p 値と回数をそのまま示す。

## 守ること
- コードは変えない。値も変えない。結果を見て条件を足したり、走らせ直したりしない。
- 記録の量は `conference/RESEARCH_PC_ja.md` の決まりどおり。研究 PC に何かを入れる・設定を変える必要が出たら、入れずに止めて報告する。push は Mac を経由する。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、push、走らせる前・あとのテストの結果。
2. 砂浜 × 条件の表（安全性を先に）と、前もって決めた検定の結果。
3. `0167` の結果（傾き停止が減ったか、完走できたか）。064 の PD・GD とは別の日の走行として並べる。
4. できなかったこと、自信がないこと。
