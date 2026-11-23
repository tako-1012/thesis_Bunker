# 指示書 057：偽の急斜面を減らす方法と、障害物の余白を広げる方法の組み合わせを、研究 PC の Gazebo で評価する

> **状態：実行中（2026-11-23 に研究 PC（チャット：研究PC実行）へ依頼。11/23 に開始、tmux `eval-057`）**。実行は**研究 PC の担当**（Mac の Codex から `ssh hayashi`）。コードは変えない（走らせて集計するだけ）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/results/eval_050/REPORT_ja.md`・`REVIEW_ja.md`（**この指示書の根拠**）・`run050.sh`（同じやり方で走らせる見本）、
> `conference/results/overlap_goal/REVIEW_ja.md`（052）、`conference/results/steep_near_obstacle/REVIEW_ja.md`（055）、`conference/results/plan_map_snapshots/REPORT_ja.md`（051）、`conference/results/common_eval/REPORT_ja.md`（集計の道具）を読むこと。
> 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/057-eval`（`origin/realtime-map` から）。結果は `conference/results/eval_057/`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 一番多い失敗は、走りながらの地図の**偽の急斜面**で目標のマスが塞がる「経路なし」（`goal_cell`）。053 で、偽の急斜面の 80% は見つけた障害物（箱）の膨らませから 0.5m 以内にあった。
- 050 で、傾きを古い地図から取る `prior`（P）は偽の急斜面をなくしたが、**`00332` で P・`prior_veto` は 6 回とも漂着物のマスを通った**（今の標準 S は 0/3）。
  箱の縁の偽の急斜面とその膨らませが、たまたま箱からの余白になっていて、それがなくなったと考えられる。
- 055 の `--steep-near-obstacle no_inflate`（障害物の膨らませの中の急斜面は膨らませない）も、同じように箱の近くの余白を減らす（通れるようになるマスの 913/921 が箱付近）。
- 052 の `--obstacle-clearance overlap_goal` は、障害物の余白をマス全体で判定して広げ（041 の `overlap`）、目標のマスだけは中心で判定する（`overlap` で目標が塞がる 12 回を避ける）。
- そこで、偽の急斜面を減らす方法を、障害物の余白を広げる方法と**組み合わせて**評価する。
  なお、`prior` では傾きはすべて古い地図から取るので、`no_inflate` は働かない（組み合わせない）。

## 走らせるもの
- 砂浜：044・050 と同じ 5 か所（`08OB86_-0205`・`08OB88_-1417`・`08OB88_-0167`・`08OB88_00332`・`08OB89_-0847`）。
- 共通の設定（050 の S と同じ）：
  - 引数：`--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 --sensors lidar_real+depth2 --diagnostics --real-time-factor 0.3 --save-plan-maps`
  - 環境：ソフトウェアの描画（`THESIS_SOFTWARE_RENDERING=1`）、`THESIS_STALE_TIMEOUT_S=1.0`、`THESIS_FINE_PROTOCOL=rtf_check`
  - 051 の `--save-plan-maps` は 3 条件すべてに付ける（箱に近づいた場面を調べるため）。1 回目の走行で、記録の量（1 回 100MB 以内の見込み）と、地図の更新の時間が 050 の S と大きく違わないかを確かめてから続ける。大きく違えば止めて報告する。
- 条件（各砂浜 × 各条件 3 回 ＝ 45 回。砂浜ごとに 3 条件を 3 周、1 回に 1 か所、tmux で順に。`ROS_DOMAIN_ID` は 50 以外）：
  - **S**：追加なし（今の標準。同じコミットで走らせ直す）
  - **PG**：`--terrain-source prior --obstacle-clearance overlap_goal`
  - **SGN**：`--obstacle-clearance overlap_goal --steep-near-obstacle no_inflate`
- 見込み：1 回 15〜30 分で、合計 12〜20 時間。途中で止まったら、何回目までかを報告する（走らせ直さない）。

## 集計（`experiments/eval_runs.py` と `experiments/plan_map_inspect.py`。050 と同じ定義で）
1. **安全性（先に書く）**：漂着物のマスを通った回数と長さ、箱までの最短距離（最小・中央値）と 0.5m を下回った回数、本当の急斜面とその 0.5m の余白を通った長さ（計画の経路と実際の軌跡）、`unsafe_tilt`、転倒。
   特に `00332` を、050 の S・P・V と並べる。
2. 箱から 0.5m 未満に近づいた回は、`plan_map_inspect.py` で、その直前の計画の地図で箱が障害物として見つかっていたか、膨らませが経路を避けさせていたかを示す。
3. 結果（完走・一部・経路なし・止まったまま・転倒）、回れた地点の数、経路なしの型。`goal_cell` は、`plan_map_inspect.py` で目標のマスが初めて塞がった計画と理由を示す。
4. 地図の更新の時間（中央値・95% 値）と、1 回あたりの `plan_maps` の記録の量。
- 判断のしかた：条件どうしは、3 回ずつの回数がはっきり分かれたときだけ「違う」と書く。安全上の問題は効果より先に書く。050 の結果とは、別の日の走行として並べる（同じ走行の比較とは書かない）。

## 守ること
- コードは変えない。値も変えない。結果を見て条件を足したり走らせ直したりしない。
- 記録の量は `conference/RESEARCH_PC_ja.md` の決まりどおり。研究 PC には GitHub の認証がないので、push は Mac を経由する。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、push（Mac を経由）、走らせる前・あとのテストの結果。
2. 砂浜 × 条件の表（上の 1〜4、3 回の最小・中央値・最大）と、判断のしかたに沿った結論。安全上の問題。
3. `00332` と `0167` の結果。箱に近づいた回・経路なしの回の `plan_map_inspect.py` の結果。
4. できなかったこと、自信がないこと。
