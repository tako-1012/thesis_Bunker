# 指示書 050：047（傾きを古い地図から取る）と 048（prior_veto）を、研究 PC の Gazebo で評価する

> **状態：実行中（2026-11-22 に研究 PC（チャット：研究PC実行）へ依頼。段階 A から）**。実行は**研究 PC の担当**（Mac の Codex から `ssh hayashi`）。コードは変えない（走らせて集計するだけ）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/tasks/047_terrain_from_prior.md`・`048_stale_prior_risk.md`、
> `conference/results/terrain_from_prior/REPORT_ja.md`・`REVIEW_ja.md`、`conference/results/stale_prior_risk/REPORT_ja.md`・`REVIEW_ja.md`（「研究 PC での比較案」）、
> `conference/results/eval_044/REPORT_ja.md`・`REVIEW_ja.md`・`run044.sh`（同じやり方で走らせる見本）、`conference/results/common_eval/REPORT_ja.md`（集計の道具）を読むこと。
> 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/050-eval`（`origin/realtime-map` から）。結果は `conference/results/eval_050/`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- Gazebo の評価で、残っている一番大きな失敗は「経路なし」（`goal_cell`）：走っている途中の地図で、目標のマスが**偽の急斜面の膨らませ**で塞がる。
  044 では `08OB88_-0167` が全条件で 12 回とも失敗した。046 の調べでは、`goal_cell` の 35 回のうち 28 回がこの型。
- 047 の `--terrain-source prior` は、傾き・急斜面を古い地図から取り、障害物だけをセンサーで見つける。保存した記録では、判定できた 20 回のうち 12 回が救える見込み。
- 048 の `--terrain-source prior_veto` は、`prior` に加えて、点が十分ある（そのマスの点が `samples_per_cell` の半分以上）マスでセンサーが急斜面と判断した所だけ通れないにする。保存した記録では点の数がなく、効果を確かめられなかった。最後の地図に `terrain_steep`・`veto_supported` が保存される。
- 評価用の Gazebo の世界は、地形が古い地図と同じ（箱だけ足される）。古い地図がずれていた場合は、段階 B で `--prior-variant perturbed` を使って確かめる。
- 044 の B（今の標準）の結果：完走 10/15、経路なしはすべて `goal_cell`（4 回）、箱から 0.5m 未満が 1 回。

## 段階 A（今回）：古い地図は正しい（`exact`）
- 砂浜：044 と同じ 5 か所（`08OB86_-0205`・`08OB88_-1417`・`08OB88_-0167`・`08OB88_00332`・`08OB89_-0847`）。
- 共通の設定（044 の B と同じ）：`--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 --sensors lidar_real+depth2 --diagnostics --real-time-factor 0.3`、ソフトウェアの描画（`THESIS_SOFTWARE_RENDERING=1`）、`THESIS_STALE_TIMEOUT_S=1.0`。
- 条件（各砂浜 × 各条件 3 回 ＝ 45 回。砂浜ごとに 3 条件を 3 周、1 回に 1 か所、tmux で順に。`ROS_DOMAIN_ID` は 50 以外）：
  - **S**：追加なし（`--terrain-source` を付けない。044 の B を同じコミットで走らせ直す）
  - **P**：`--terrain-source prior`
  - **V**：`--terrain-source prior_veto`
- 見込み：1 回 15〜30 分で、合計 12〜20 時間。途中で止まったら、何回目までかを報告する（走らせ直さない）。

## 段階 B（あとで別に頼む。今回は走らせない）：古い地図がずれている（`perturbed`）
- `--prior-variant perturbed --obstacle-reference local` を固定し、S・P・V を比べる（048 の「研究 PC での比較案」のとおり）。砂浜・回数は段階 A の結果を見て決める。

## 集計（`experiments/eval_runs.py` を使う。044 と同じ定義で）
1. **安全性（先に書く）**：本当の急斜面とその 0.5m の余白を通った長さ（計画の経路と実際の軌跡）、`unsafe_tilt`、転倒、箱までの最短距離（最小・中央値）と 0.5m を下回った回数、漂着物のマスの長さ。
2. 結果（完走・一部・経路なし・止まったまま・転倒）、回れた地点の数、経路なしの型（特に `goal_cell`）。
3. 地図：誤って通れないマス（急斜面によるもの）、本当の急斜面の見落とし、地図の更新の時間（中央値・95% 値）。V では最後の地図の `veto_supported` のマスの数と、それが本当の急斜面だったか。
4. `0167` の各回で、目標のマスが塞がったか、何によって塞がったか。
- 判断のしかた：条件どうしは、3 回ずつの回数がはっきり分かれたときだけ「違う」と書く。安全上の問題は効果より先に書く。

## 守ること
- コードは変えない。値（25°・0.5m・点の数の基準）も変えない。結果を見て条件を足したり走らせ直したりしない。
- 記録の量は `conference/RESEARCH_PC_ja.md` の決まりどおり（1 回で 100MB を超えそうなら相談）。研究 PC には GitHub の認証がないので、push は Mac を経由する。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、push（Mac を経由）、走らせる前・あとのテストの結果。
2. 砂浜 × 条件の表（上の 1〜3、3 回の最小・中央値・最大）と、判断のしかたに沿った結論。安全上の問題。
3. `0167` の結果と、経路なし・止まったままの原因の要約。
4. できなかったこと、自信がないこと。
