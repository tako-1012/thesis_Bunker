# 指示書 058：位置の途切れ（`pose_timeout`）がどこで起きるかを分けるための記録（`--pose-trace`、選んだときだけ）

> **状態：完了（結果は `results/pose_trace/`、レビューは `REVIEW_ja.md`。研究 PC での確かめは 057 のあと）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（研究 PC での確かめは、あとで別に頼む）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/results/eval_050/REPORT_ja.md`・`REVIEW_ja.md`、`conference/results/eval_044/REPORT_ja.md`（`pose_timeout` の調べ）、
> `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py`（`tick` の `pose_timeout` の判定）、`ros2_jazzy/gz_checks/lidar_checks.py`・`lidar_planner.py`・`run_lidar_checks.sh`・`lidar_bridge.yaml`、`experiments/eval_runs.py` を読むこと。
> ブランチは `codex/058-pose-trace`（その時点の `realtime-map` の最新から）。結果は `conference/results/pose_trace/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 経路を追う側（`path_follower.py`）は、位置を**実時間で 1 秒以上**受け取れないと `pose_timeout` で止まる（`time.monotonic() - self.pose_received > 1.0`）。
- 044 では 60 回で 1 回だったが、050 では 45 回で 4 回（S 1・P 3）起き、`0167` の P の 2 回が完走できなかった原因になった。
  044 の調べでは、別の購読者が記録した軌跡は途切れておらず、Gazebo・ブリッジ・追う側のログにもエラーがなかった。**どこで途切れたか（Gazebo が出していない／受け渡しで遅れた／追う側が受け取っても処理できなかった）が分からない**。
- 0.3 倍で走らせているので、実時間の 1 秒は sim の 0.3 秒にあたる。追う側の処理が一時的に止まっただけでも起きうる。

## 作るもの（選んだときだけ働く。既定の動き・記録はバイト単位で変えない）
- `--pose-trace`（既定は付けない）。`lidar_checks.py`・`run_lidar_checks.sh` に通し、manifest に記録する。付けたときだけ、次を走行のフォルダに記録する：
  1. 追う側：位置を受け取るたびに、実時間（`time.monotonic()`）・ROS の時計・メッセージの時刻（header の stamp、なければ受け取った sim 時刻）を記録する。
     `tick` のたびに、前の `tick` からの実時間の間隔と、`tick` の処理にかかった時間を記録する。
  2. 計画する側（`lidar_planner.py`）：同じ位置の話題を受け取った実時間とメッセージの時刻（追う側と比べるため）。
  3. 走行を見張る側（`lidar_checks.py` の observer）が受け取った位置の時刻（すでに軌跡として記録しているならそれを使う）。
  4. 実時間で 1 秒ごとの CPU の使用率とロードアベレージ（Python の標準ライブラリか `/proc` から。新しいパッケージは入れない）。
- 記録は CSV で、量は 1 回 20MB 以内の見込みにする（間引くなら、途切れの前後は間引かない）。
- 後から調べる道具 `experiments/pose_trace_inspect.py`：`pose_timeout` の走行について、止まる直前の数秒で、
  (a) メッセージの時刻が進んでいたか（Gazebo が出していたか）、(b) 計画する側・見張る側は受け取っていたか、(c) 追う側の受け取りが途切れたか、(d) 追う側の `tick` の間隔が空いていたか（処理が止まっていたか）、(e) そのときの CPU、を表にする。

## 守ること・やらないこと
- 既定（付けない）の出力・manifest・記録・追う側の動きは、バイト単位で変えない（直す前の実装と同じ環境でその場で比べるテスト。別の PC で記録したハッシュとは比べない）。
- `pose_timeout` の 1 秒など、値は変えない（記録するだけ）。Gazebo は走らせない。新しいパッケージは入れない。

## テスト `conference/tests/test_pose_trace.py`（ROS2・Gazebo なしで動くこと）
1. 既定の出力・追う側の動きがバイト単位で同じ。
2. 偽の記録で、道具が (a)〜(e) を正しく分ける（Gazebo が止まった・受け渡しで遅れた・追う側の処理が止まった、の 3 通り）。
3. `--pose-trace` の manifest に記録される。
4. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 1 回あたりの記録の量の見積もり。
3. 研究 PC で確かめるときの引数の案。
4. できなかったこと、自信がないこと。
