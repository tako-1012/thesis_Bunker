# 指示書 078：目印の数を変えた Gazebo の世界で記録を取り、記録から出した位置のずれを測る（研究 PC）

> **状態：実行中（研究 PC、チャット：研究PC実行。073 が終わってから始める）**。実行は**研究 PC の担当**（Mac の Codex から `ssh hayashi`）。コードは変えない（走らせて集計するだけ。集計のスクリプトは足してよい）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/progress/policy.csv`（今後の方針）、
> `conference/tasks/075_landmark_world.md`・`076_offline_localization.md`・`077_recording_bridge.md` と、それぞれの `results/` の `REPORT_ja.md`・`REVIEW_ja.md`（**研究 PC での引数とコマンドの案**）、
> `conference/results/eval_073/`（同じやり方で走らせる見本。073 の `run073.sh` など）を読むこと。
> 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/078-eval`（`origin/realtime-map` から）。結果は `conference/results/eval_078/`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 修論の範囲：ドローンが撮ったばかりの地図を正とし、その上で人が選んだ地点を効率よく回る。BUNKER には GNSS がなく、位置は LiDAR（と IMU）で積み上げ、ドローンの地図に重ねて直す予定。
- 砂浜は目印が少ない。そこで（11/27 に利用者と決めた）、**目印の多い世界から始め、目印を減らして砂浜に近づける**。目印の数と位置のずれの関係を出す。
- 075 で目印を置いた世界（`--landmarks`）・「ドローンの地図」の代わりの点群（`reference_cloud.npz`）・センサーの記録（`--record-sensors`）を、076 で記録から位置を出す道具（KISS-ICP の積み上げ、small_gicp で地図に重ねる、その組み合わせ）を、077 で 2 つのつなぎを作った。
- 研究 PC に、KISS-ICP・small_gicp を**専用の新しい venv だけに**入れることを、11/27 に利用者が認めた（ROS・Docker のイメージ・今の venv には触らない）。

## 準備
1. 073 の走行が終わっていることを確かめる（073 の集計は「073 の続き」で別に行う。073 の生の記録は消さない）。
2. ディスクの空きを確かめる。1 回あたり、地図の点群が約 20MB、センサーの記録が 100MB まで、ほかの記録が約 25MB なので、24 回で 4GB 前後。足りなければ止めて報告する。
3. `conference/` で、`python3.12 -m venv .venv-localization` を作り、`.venv-localization/bin/python -m pip install -r requirements_localization.txt` で入れる（版は固定）。入れたものの一覧（`pip freeze`）を記録する。**ほかの venv や、システムの Python には入れない。**
4. 走らせる前のテスト（`.venv-localization` でも `tests.test_offline_localization`・`tests.test_recording_bridge` が飛ばされずに通ること）。

## 走らせる条件（前もって決めた）
- 共通（073 の `none` と同じ）：`--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 --sensors lidar_real+depth2 --diagnostics --terrain-source prior --obstacle-clearance distance --save-plan-maps --pose-trace`、GPU の描画、`--real-time-factor 1.0`、`THESIS_STALE_TIMEOUT_S=1.0`。位置のずれ（`--pose-error`）は入れない。
- 足す引数：`--landmarks <個数> --landmark-seed <シード> --record-sensors --record-sensors-seconds 120`。
- 目印：1ha あたり **0・10・40・160 個**。
- 砂浜：`08OB88_-1417`・`08OB86_-0205` の 2 か所。
- 目印のシード：0・1・2（目印 0 個でも、3 回走らせる）。
- 合計 4 × 2 × 3 ＝ 24 回。順番は、砂浜ごとに「シード × 目印の数」を回す。1 回に 1 か所、tmux で順に。`ROS_DOMAIN_ID` は 50 以外。
- 1 回目の走行のあとで、GPU の描画、実測の倍率（0.9 倍以上）、記録の量（センサーの記録が 100MB 以内）、`metadata.json` の状態（3 つの流れがすべて保存されたこと）、076 の道具がその記録を最後まで読めること（`--recording` で 1 回かける）を確かめてから続ける。外れたら止めて報告する。
- 目印を置いて初めの経路が引けない回は、そのまま「経路なし」として記録する（走らせ直さない）。

## 集計（走行が終わってから。「078 の続き」で頼む）
1. 各回の記録に、`.venv-localization/bin/python -m experiments.offline_localization --recording <raw/砂浜> --out <出力>` をかける（3 通りの位置の出し方）。
2. 各回・各方法：位置の誤差の平均・95% 値・最大・最後、走った距離あたりのずれ。組み合わせで直しを採った回数と止めた回数。重ね合わせの最小の固有値の分布と、いちばん弱い向き（海岸に沿う／海に向かう／高さ／回転）の数。
3. 目印の数ごと（6 回ずつ）の中央値・最小・最大。
4. **判断のしかた（前もって決めた）**：
   - 主に見るのは「組み合わせの平均誤差」と「積み上げだけの走った距離あたりのずれ」。
   - 目印の数（0・10・40・160）と、主に見る 2 つの値の関係を、Spearman の順位相関で 1 回ずつ示す（6 × 4 ＝ 24 回）。
   - 回数が少ないので、「関係がない」とは書かない。図（目印の数ごとの箱ひげ図）を必ず付ける。
5. 走行そのものの結果（完走など）と、記録の量・欠けたスキャンの数も表にする。

## 守ること
- コードは変えない。値（目印の数・シード・砂浜・120 秒・076 の基準）も変えない。結果を見て条件を足したり、走らせ直したりしない。
- 記録の量は `conference/RESEARCH_PC_ja.md` の決まりどおり。生の記録は研究 PC に置き、Git には集計の CSV・ログ・図と、生の記録の場所と sha256 の一覧（`not_committed.txt`）を入れる。push は Mac を経由する。
- 研究 PC に、上の venv 以外で何かを入れる・設定を変える必要が出たら、止めて報告する。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、push、venv に入れたものの一覧、走らせる前・あとのテストの結果。
2. 目印の数ごとの、3 通りの位置の誤差の表と図、Spearman の結果。
3. 弱い向きの数と、組み合わせで直しを止めた回数（目印 0 個で、どれだけ止めたか）。
4. 欠けた回・異常な終了の一覧、できなかったこと、自信がないこと。
