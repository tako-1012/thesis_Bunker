# 指示書 035：034 の不具合の直しを評価し、032（点群だけの障害物の判定など）を短く試す（研究 PC）

> **状態：未着手**。実行は**研究 PC の担当**（Mac の Claude Code から `ssh hayashi` で操作）。コードは変えない（走らせて集計するだけ。集計のスクリプトは足してよい）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`（記録の量の決まり）、`conference/tasks/030_eval_ground_endpoint.md`・`032_prior_free_obstacles.md`・`034_online_safety_fixes.md`、
> `conference/results/eval_ground_endpoint/REPORT_ja.md`、`conference/results/diagnosis_033/REPORT_ja.md`、`conference/results/online_safety/REPORT_ja.md` を読むこと。
> 作業は研究 PC の作業ツリー `~/thesis_Bunker_rtf` で、`origin/realtime-map` から作った作業用のブランチ `claude/035-eval` で行う。結果は `conference/results/eval_035/`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 030：029（`--ground-estimate non_obstacle`、以下「C1」）は効いて安全だった（今後の標準）。028b（`--endpoint-policy escape_component`）は転倒したので使わない。
- 033：走りながら計画し直す仕組みに不具合があった。
  - ロボット自身のマスが通れないと止まったままになる。
  - 前から見えていたマスが通れなくなっても計画し直さない。
  - 経路を追う側に、傾き・ずれで止まる仕組みがない。
- 034：その 3 つを `--online-fixes v1` で直した。保存した止まった状態では、`v1` で経路が受け渡されることを Python で確かめた。**Gazebo では未確認**。
- 032：古い地図に頼らない障害物の判定（`--obstacle-reference local`）、漂着物を本当の高さにする world（`--debris-box-height true`）、古い地図が古い・ない場合（`--prior-variant perturbed|none`）を足した。**Gazebo では未確認**。
  `local` は点ごとに平面をあてはめるので**計算が重い可能性**があり、0.3 倍で地図の更新が追いつくかが分からない。
- 走らせるたびに結果がばらつくので、比べるときは繰り返しの回数で比べる。実時間は 0.3 倍、ソフトウェアの描画（026 の結論）。

## 段階 1：034 の直しの評価（本番）
- 030 と同じ 5 か所（`08OB87_-0706`・`08OB88_-1417`・`08OB88_-0167`・`08OB89_-0347`・`08OB89_-0847`）、030 と同じ地点、既定の LiDAR（`--sensors` なし）、`--map fine`。
- 条件は **C1＋v1** だけ：`--ground-estimate non_obstacle --online-fixes v1 --diagnostics`。各砂浜 3 回（15 回）。
  比べる相手は 030 の C1（同じ 5 か所 × 3 回、記録済み）。走らせ直さない。
- 1 回に 1 か所（`THESIS_FINE_PROTOCOL=rtf_check`、`THESIS_ONLY_PATCH=<砂浜>`）。tmux で 1 回ずつ順に。`ROS_DOMAIN_ID` は 50 以外。
- 見るもの（030 と同じ項目に加えて）：
  - 結果（完走／一部／経路なし／止まったまま／転倒）。止まったままが消えたか。
  - `08OB88_-0167` で転倒が起きないか。経路なしで止まるか、別の経路で着くか。
  - 本当の地図で通れないマス・漂着物に触れた長さ（安全性）。
  - `lethal_changed` で計画し直した回数、`join_rejected` で終わった回数。
  - `unsafe_tilt`・`off_path` で止まった回数と、そのあとどうなったか（計画し直して進めたか、止まったままになったか）。
  - **経路を渡した時点で、その経路に地図の通れないマス（ロボットのマスを除く）が含まれていたか**（033 で確かめきれなかった点）。

## 段階 2：032 の短い試し（動くかと、計算が追いつくかの確認。比較ではない）
- 砂浜は `08OB86_-0205`（地点がすべて地図の端から 20m 以上）。センサーは実機と同じ `--sensors lidar_real+depth2`。全部に `--ground-estimate non_obstacle --online-fixes v1 --diagnostics`。各 1 回：
  - S1：`--obstacle-reference prior`（今まで）
  - S2：`--obstacle-reference local`
  - S3：`--obstacle-reference local --debris-box-height true`
  - S4：`--obstacle-reference local --prior-variant perturbed`
  - S5：`--obstacle-reference local --prior-variant none`
- 見るもの：
  - 地図の更新の時間（中央値・95% 値・最大、センサー別）と捨てた走査。0.3 倍の 1 周期（実時間 0.33 秒）に追いつくか。
  - 誤って通れないとしたマス・見落としたマス（023 と同じ定義）。
  - 走行の結果。
  - 障害物を初めて地図に入れたときのロボットからの距離（センサー別）。
- **S2 で地図の更新が追いつかない（捨てた走査が多い、95% 値が 0.33 秒を超える）場合は、S3〜S5 は走らせずに止めて報告する**（計算を速くする直しが先に要るため）。

## 記録の量
`conference/RESEARCH_PC_ja.md` の決まりどおり、集計・要約・図と最小限の記録だけをコミットする。1 回で 100MB を超えそうなら相談する。

## 判断のしかた
- 段階 1 は 030 の C1 と、3 回ずつの回数で比べる。はっきり分かれたときだけ「効いた」と書く。安全上の問題（転倒、本当に通れないマスを通った）は効果より先に報告する。
- 段階 2 は 1 回ずつなので、比較の結論は出さない（動いたか、計算が追いつくかだけ）。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、ブランチ、push したか（Mac を経由）。走らせる前のテストの結果。
2. 段階 1 の表（030 の C1 と並べる）と、判断のしかたに沿った結論。安全上の問題。
3. 段階 2 の表（S1〜S5）と、計算が追いつくか。
4. 失敗した走行それぞれの、失敗の瞬間の地図から見た原因の要約。できなかったこと、自信がないこと。
