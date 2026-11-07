# 指示書 025：研究 PC で、LiDAR の Gazebo を実時間の 1 倍で走らせられるか確かめる（検証だけ）

> **状態：未着手**。実行先は**研究 PC「hayashi」**（`conference/RESEARCH_PC_ja.md`）。最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md` を読むこと。
> **いま研究 PC で走っている実験（0.3 倍の Gazebo）は止めない**。その実験が終わるまでは、下の「段階 0」だけを行う。
> 結果は `conference/results/rtf_check/`（新しいフォルダ）、報告は同じ場所の `REPORT_ja.md`。既存の結果・既定の設定は変えない。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 指示書022（LiDAR、`--map coarse`）・023（細かい格子、`--map fine`）の Gazebo は、**クラウドの Docker（GPU なし、ソフトウェアの描画）**で走らせた。
  GPU LiDAR（ogre2）の描画が CPU では追いつかず、点群が 0.5 秒以上途切れて「センサーが止まった」と判断され走行が止まったため、
  **シミュレーションを実時間の 0.3 倍**に落とし、**途切れの基準を 1.0 秒**にした（`results/gazebo_lidar/physical_10/README_ja.md`）。
- 023 の `--map fine` では、この 2 つが**比べる条件として固定**されている：
  `ros2_jazzy/gz_checks/lidar_map.py` の `fine_protocol()` は 0.3 倍・1.0 秒以外だとエラーにし、`lidar_checks.py` も world の速さを `0.3` に固定している。
  `--map coarse` は環境変数 `THESIS_REAL_TIME_FACTOR`・`THESIS_STALE_TIMEOUT_S` で変えられる（既定は 1 倍・0.5 秒）。
- 021（誤差なしのセンサー、LiDAR なし）は 1 倍で走らせた。
- **1 倍にすると何が変わるか**（結果の比べ方に関わる）：
  - 物理（1 ステップごとの計算）は同じ。違うのは、シミュレーションの時間と実際の時間の関係だけ。
  - 計画（中央値 0.04〜0.10 秒）と地図の更新（023 で中央値 0.14 秒）は**実際の時間**で動く。0.3 倍ではシミュレーションの中では約 0.3 倍の時間しかかからず、実機より楽観的だった。
    1 倍ではその間にロボットが約 3.3 倍長く進むので、**より実機に近いが、022・023 とは条件が違う**。
  - LiDAR は 10Hz（0.1 秒ごと）。地図の更新が 0.1 秒より長いと、間の走査は捨てられる（最新の 1 つだけ残す作り）。1 倍では捨てる数（`queue_drops`）が増えるはず。
  - 途切れの判断（`stale_timeout_s`）はシミュレーションの時間（`use_sim_time:=true`）で測っている。
- **研究 PC での描画について（要確認）**：`run_lidar_checks.sh` は Docker を `--gpus` なしで起動し、`LIBGL_ALWAYS_SOFTWARE=1`（ソフトウェアの描画）が既定。
  つまり**研究 PC でも、今のままでは GPU で描画していない可能性が高い**。また Docker の中の Gazebo は 8.11（クラウドと同じイメージ）、研究 PC に直接入っているのは 8.15。

## やってはいけないこと
- 走っている実験のコンテナ・tmux・プロセスを止める、再起動する、`docker system prune` などで片付ける。
- 走っている実験が読んでいるフォルダ（`/home/kotaro/thesis_Bunker`。Docker に読み取り専用で渡している）で `git checkout`・`git pull`・ファイルの編集をする
  （走っている途中や最後の集計で読むファイルが変わってしまう）。作業は**別の作業ツリー**で行う（下の段階 0）。
- 走っている実験が終わる前に、Gazebo や Docker の別の実験を起動する（CPU・GPU の取り合いで、走っている実験の結果が変わる。
  さらに同じ `ROS_DOMAIN_ID=50` と `--network host` を使うので、2 つの Gazebo の話題が混ざる）。
- `fine_protocol()` の固定値や、既存のスクリプトの既定のふるまいを変える。022・023 の結果を書き換える。
- 1 倍の結果を 022・023 の表に混ぜる（別の条件として、別のフォルダに置く）。

## 段階 0：走っている実験が終わるまでに行うこと（Gazebo を動かさない、軽い確認だけ）
1. 別の作業ツリーを作る：
   `cd /home/kotaro/thesis_Bunker && git fetch origin && git worktree add -b claude/025-rtf-check ~/thesis_Bunker_rtf origin/realtime-map`
   （`git fetch` と `worktree add` は、走っている実験のファイルを変えない。以後の作業はすべて `~/thesis_Bunker_rtf` で行う）
2. 走っている実験の情報を**読むだけ**で記録する：どの tmux／コンテナか、出力先、開始時刻、`manifest.json` の `real_time_factor`・`stale_timeout_s`・`map_method`、
   進み具合（`raw/` のフォルダ数）、終わる見込みの時刻。
3. GPU で描画できるかの下調べ（読むだけ）：
   - `nvidia-smi`（走っている実験の gz が GPU を使っているか。プロセスの一覧に出るか）
   - `docker info | grep -i -A3 runtime`、`nvidia-ctk --version`（NVIDIA Container Toolkit が入っているか）。**入っていなければ、入れる前に利用者に聞く**（研究 PC の環境を変えるため）。
   - `gz sim --versions`（研究 PC に直接入っている Gazebo）
4. 段階 1 で使うスクリプトの準備（作業ツリーの中だけ、走らせない）：
   - `run_lidar_checks.sh` を**複製した新しいファイル** `ros2_jazzy/gz_checks/run_lidar_checks_gpu.sh` を作り、引数で GPU を選べるようにする
     （`--gpus all`、`-e NVIDIA_DRIVER_CAPABILITIES=all`、`LIBGL_ALWAYS_SOFTWARE=0`）。元のファイルは変えない。
   - `--map fine` を 1 倍で走らせるための**明示的な許可**を、新しい環境変数（例：`THESIS_FINE_PROTOCOL=rtf_check`）で足す。
     既定（変数なし）では今までどおり 0.3 倍・1.0 秒以外をエラーにすること。manifest に `protocol` として記録すること。
   - 既存のテスト（`tests.test_pointcloud_map_fine` など）が通ることを venv で確かめる（重くないテストだけ。全部のテストは段階 1 の前に）。
   - ここまでをコミットして `claude/025-rtf-check` に push する（`realtime-map` にはマージしない。PR は Mac の Claude が作る）。

## 段階 1：走っている実験が終わってから
`ROS_DOMAIN_ID` は 50 以外（例：`THESIS_ROS_DOMAIN_ID=61`）にし、ほかの Gazebo が動いていないことを確かめてから、1 つずつ順に走らせる。
すべて tmux の中で動かし、条件・コミット ID・ログ・結果を `conference/results/rtf_check/<名前>/` に残す（既存の保存先は使わない）。

| 名前 | 地図 | 描画 | 速さ | 途切れの基準 | 砂浜 | 目的 |
|---|---|---|---|---|---|---|
| A_sw_0.3 | fine | ソフトウェア | 0.3 | 1.0 秒 | 08OB86_00294 | 研究 PC でも 023 と同じ結果になるかの確認（機械の違いの影響を分ける） |
| B_gpu_0.3 | fine | GPU | 0.3 | 1.0 秒 | 同上 | 描画を GPU にしただけで結果が変わらないかの確認 |
| C_gpu_1.0 | fine | GPU | 1.0 | 1.0 秒 | 同上 | 1 倍で追いつくかの確認 |
| D_sw_1.0 | fine | ソフトウェア | 1.0 | 1.0 秒 | 同上 | （C が通ったら）GPU なしでも 1 倍でよいか |

- 砂浜は `--patch-count 1`（最初の 1 か所＝`08OB86_00294`。022・023 ともに完走した砂浜）。
- C が通ったら、`--patch-count 3`（最初の 3 か所。022・023 ともに 3 か所とも完走）で C をもう一度走らせる。**10 か所はこの指示書では走らせない**（Mac の Claude が結果を見て決める）。
- 途切れの基準は、どれも 1.0 秒のまま（変えるのは速さと描画だけ。1 回に 1 つの条件だけ変える）。
- 結果を見て設定を選び直さない（ここで試した組み合わせだけを報告する）。

## 1 倍で「使える」と言える条件（すべて満たすこと）
- 実際の速さ：`sim_to_wall_ratio` の中央値が 0.95 以上（設定 1.0 に対して）。
- 点群の届き方：シミュレーションの時間で、点群の間隔の中央値が約 0.1 秒（10Hz）、最大が 1.0 秒未満。センサーが止まった判断（`lidar_unavailable_or_stale`）が 0 回。
- 地図の更新の失敗が 0 回。捨てた走査の数（`queue_drops`）と、地図の更新の時間（中央値・95% 値・最大）を、0.3 倍の場合と並べて出す。
- A・B が 023（`results/lidar_fine/physical_10/` の `08OB86_00294`）と同じ結果（完走・回れた地点の数）であること。違えば、その時点で止めて報告する。

## 確かめ方
- 集計は `python3 experiments/lidar_fine_report.py <出力先>`（023 と同じ項目）。さらに次を自分で計算して表にする：
  `map_updates.csv` の `stamp` の差（シミュレーションの時間での点群の間隔）、`runs.csv` の `sim_to_wall_ratio`（元は各走行の `raw/<砂浜>/mission.json` の `wall_elapsed_s` と経過したシミュレーションの時間）、`nvidia-smi` の GPU 使用率（走行中に数回）。
- 段階 1 の前に、作業ツリーで `conference/tests/` のすべてのテストを venv で実行する（`AGENTS.md` の一覧）。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. 走っている実験の情報（段階 0 の 2）と、それを止めずに進めたこと。
2. GPU での描画ができたか（`nvidia-smi`・NVIDIA Container Toolkit・Gazebo の版）。できなかった場合は理由と、環境を変える必要があるか。
3. コミット ID、ブランチ、変えた・足したファイル、実行したコマンドとテストの出力。
4. A〜D（と C の 3 か所）の表：完走・回れた地点の数・`sim_to_wall_ratio`・点群の間隔（中央値・最大）・止まった判断の回数・`queue_drops`・
   地図の更新の時間（中央値・95% 値・最大）・計画の時間（中央値・最大）・GPU 使用率。
5. 上の「使える条件」を満たしたか。満たさなかった項目とその理由。
6. できなかったこと、自信がないこと（例：Docker の Gazebo 8.11 と研究 PC の 8.15 の違い）。

## 注意（論文・修論の扱い）
- 1 倍が使えても、**022・023 の結果（0.3 倍）はそのまま残す**。1 倍の結果は別の条件として扱い、0.3 倍と 1 倍を混ぜて比べない。
- 1 倍に切り替えるか（指示書024 などのこれからの実験を 1 倍で走らせるか）は、この報告を見て Mac の Claude と利用者が決める。
