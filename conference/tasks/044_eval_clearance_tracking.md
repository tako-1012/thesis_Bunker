# 指示書 044：041（障害物の膨らませをマス全体で判定）と 043（曲がり角で減速）を、研究 PC の Gazebo で評価する

> **状態：完了（結果は `results/eval_044/`、レビューは `REVIEW_ja.md`。overlap は標準にしない）**。実行は**研究 PC の担当**（Mac の Codex から `ssh hayashi`）。コードは変えない（走らせて集計するだけ）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/tasks/041_obstacle_clearance.md`・`043_path_tracking.md`、
> `conference/results/obstacle_clearance/REVIEW_ja.md`・`path_tracking/REVIEW_ja.md`・`rtf_compare/REPORT_B_ja.md`・`REVIEW_B_ja.md`、`conference/results/common_eval/REPORT_ja.md`（集計の道具）を読むこと。
> 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/044-eval`（`origin/realtime-map` から）。結果は `conference/results/eval_044/`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 035・037 で、ロボットの中心が本当の漂着物のマスに入った。地図は正しかったが、計画の地図で障害物の膨らませを「マスの中心」だけで判定しているため、経路が障害物のすぐそばを通った。
  さらに、膨らませで通れないになったマスでも、点が当たっていない（見ていない）マスは計画で通れるとみなされていた。041 の `--obstacle-clearance overlap` は両方を直す。
- 経路を追う側のずれが大きい（最大 0.6〜0.95m、`off_path` が 30 回で 45〜52 回）。043 の `--tracking corner_slow`（曲がり角の手前で減速、向きのずれが 45° を超えたらその場で回る）は、簡単な模型では効果が言えず、Gazebo で確かめる必要がある。
- 039 段階 B で、今の標準の設定（下の共通の設定、0.3 倍）の 15 回の結果がある：完走 10・経路なし 3・止まったまま 2、`off_path` 23、箱までの最短距離の最小 0.501m。

## 走らせるもの
- 砂浜：037・039 と同じ 5 か所（`08OB86_-0205`・`08OB88_-1417`・`08OB88_-0167`・`08OB88_00332`・`08OB89_-0847`）。
- 共通の設定：`--map fine --ground-estimate non_obstacle --online-fixes v2 --sensors lidar_real+depth2 --diagnostics`、0.3 倍、ソフトウェアの描画。
- 条件（各砂浜 × 各条件 3 回 ＝ 60 回。砂浜ごとに 4 条件を 3 周、1 回に 1 か所、tmux で順に。`ROS_DOMAIN_ID` は 50 以外）：
  - **B**：追加なし（今の標準。039 段階 B と同じ設定を、同じコミットで走らせ直す）
  - **O**：`--obstacle-clearance overlap`
  - **T**：`--tracking corner_slow`
  - **OT**：`--obstacle-clearance overlap --tracking corner_slow`
- 見込み：1 回 15〜30 分で、合計 15〜25 時間。途中で止まったら、何回目までかを報告する（走らせ直さない）。

## 集計（`experiments/eval_runs.py` を使う。同じ定義で）
1. 結果（完走・一部・経路なし・止まったまま・転倒・傾きのくり返しでの終了）、回れた地点の数、経路なしの型。
2. **安全性（先に書く）**：箱までの最短距離（最小・中央値）、0.5m を下回った時間と回数、本当に通れないマス・漂着物のマスの長さ、地図で見つけた障害物までの最短距離（`clearance.csv`）。
3. 経路からのずれ（最大・95% 値）、ずれが最大の場所の曲率、`off_path` の回数とそのあと、走行時間。
4. 「止まったまま」があれば、その場面（どこで、何に止められたか）を記録から調べる。
- 判断のしかた：条件どうしは、3 回ずつの回数がはっきり分かれたときだけ「違う」と書く。安全上の問題は効果より先に書く。

## 記録の量
`conference/RESEARCH_PC_ja.md` の決まりどおり（1 回で 100MB を超えそうなら相談）。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、push（Mac を経由）、走らせる前・あとのテストの結果。
2. 砂浜 × 条件の表（上の 1〜3、3 回の最小・中央値・最大）と、判断のしかたに沿った結論。安全上の問題。
3. 止まったまま・経路なしの原因の要約。
4. できなかったこと、自信がないこと。
