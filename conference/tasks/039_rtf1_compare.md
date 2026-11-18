# 指示書 039：実時間 1 倍と 0.3 倍を、研究 PC の Gazebo で比べる（038 のあと）

> **状態：未着手**。段階 A は **クラウドの Codex**（実装、Gazebo は使わない）、段階 B は **研究 PC の担当**（Mac の Codex から `ssh hayashi`）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/results/rtf_check/hayashi_rtf1_check/README_ja.md`・`hayashi_rtf_repeat/README_ja.md`、
> `conference/results/map_speed/REPORT_ja.md`・`REVIEW_ja.md`（038）、`conference/results/review_fixes/REPORT_ja.md`（040、`--online-fixes v2`）を読むこと。

## 背景（別の環境の会話は共有されないので、ここに書く）
- Gazebo の走行は、ずっと実時間の 0.3 倍で行っている。2026-11-07 の確認（`rtf_check`）で、研究 PC の Gazebo は 1 倍で動くが、私たちの地図の更新が追いつかず（点群を 15〜27 回捨てた）、事前に決めた基準を満たさなかった。
- 038 で地図の更新を速くした（出力はバイト単位で同じ）。クラウドの合成の点群で、LiDAR 1 回の 95% 値が 205ms → 23ms、カメラ 1 台が 43ms → 7ms。
  ただし、「作りたての地図に 1 回」の測定で、走行中の速さは分からない（038 のレビューの所見 1・2）。
- 今は `--map fine` のとき、`lidar_map.fine_protocol()` が 0.3 倍以外を拒む。2026-11-07 の確認は、コードを変えずに上書き（`rtf_check/hayashi_rtf1_check/overlay.diff`）で 1 倍にした。

## 段階 A（クラウドの Codex）：1 倍を選べるようにする
- ブランチは `codex/039-rtf-option`（その時点の `realtime-map` の最新から）。結果は `conference/results/rtf_compare/`（段階 A の報告は `REPORT_A_ja.md`）。
- `lidar_checks.py`・`run_lidar_checks.sh` に `--real-time-factor 0.3|1.0`（既定 0.3＝今まで）を足す。1.0 のときだけ `fine_protocol` の確かめを通し、manifest に記録する。
  点群が古いと判断する基準（シミュレーションの時間で 1.0 秒）、物理の刻み、センサーの周期など、ほかの設定は変えない。
- 既定（0.3）の manifest と出力は、バイト単位で変えない。`rtf_check` の上書き（`overlay.diff`）と同じ結果になることを、manifest で確かめる。
- 地図の更新の時間を、走行中と同じように**作った地図に何回も**点群を入れて測る計測のスクリプトを足す（038 の `benchmark.py` を元に、保存した走行の点群の列か、動きながらの合成の点群で 100 回以上。急斜面が変わる場面を含める）。
  センサー別の中央値・95% 値・最大を出す。テストの合否には使わない。
- テスト `conference/tests/test_rtf_option.py`：既定のバイト一致、1.0 の manifest、`run_lidar_checks.sh` が引数を渡すこと。既存のテストがすべて通る。

## 段階 B（研究 PC）：1 倍と 0.3 倍を比べる（段階 A を取り込んだあと、037 が終わってから）
- 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/039-rtf-compare`（`origin/realtime-map` から）。結果は `conference/results/rtf_compare/`。
- 砂浜：037 と同じ 5 か所（`08OB86_-0205`・`08OB88_-1417`・`08OB88_-0167`・`08OB88_00332`・`08OB89_-0847`）。
- 共通の設定：`--map fine --ground-estimate non_obstacle --online-fixes v2 --sensors lidar_real+depth2 --diagnostics`。
- 比べる 2 つ：`--real-time-factor 0.3` と `--real-time-factor 1.0`。各砂浜 × 各条件 3 回（30 回）。砂浜ごとに 0.3 → 1.0 を 3 周。1 回に 1 か所、tmux で 1 回ずつ順に。
- 判定の基準（前もって決めたもの。`rtf_check` と同じ）：
  - 有効な回：実測倍率が目標の ±1% 以内、地図の更新の誤りが 0。
  - 1 倍が「追いついている」：捨てた点群（`queue_drops`）が 0.3 倍より増えない、更新が周期（実時間）を超える割合が 1% 以下、`/cmd_vel` が 19Hz 以上、点群の古さの最大が 1.0 秒（シミュレーションの時間）未満。
  - 走行の結果（完走・一部・経路なし・止まったまま・転倒）、安全性（本当に通れないマス・漂着物のマスを通った長さ）、`unsafe_tilt`・`off_path`・`unsafe_tilt` の繰り返しでの終了（`v2`）の回数。
- 判断のしかた：1 倍の 15 回すべてが「追いついている」を満たし、走行の結果と安全性が 0.3 倍と 3 回ずつの回数ではっきり違わないときだけ、以後の比較を 1 倍に切り替える提案をする。
- 記録の量は `conference/RESEARCH_PC_ja.md` の決まりどおり（1 回で 100MB を超えそうなら相談）。

## Mac の Claude に持ち帰る報告
- 段階 A：コミット ID、変えた・足したファイル、テストの出力全文、走行中と同じ条件での地図の更新の時間の表。
- 段階 B：コミット ID と push、走らせる前のテスト、1 倍と 0.3 倍の表（判定の基準の項目と走行の結果）、判断のしかたに沿った結論、できなかったこと。
