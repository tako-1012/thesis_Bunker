# 研究 PC で実時間倍率 1.0 を達成できるかの短時間確認

`results/hayashi_first_gazebo_check/` の 3 か所（実時間の 0.3 倍）に続く確認。研究の新しい比較ではなく、性能の確認。

## 変えるもの・変えないもの
- 変える：`physics/real_time_factor` の目標だけ（0.3 → 1.0）。
- 変えない：物理の刻み 0.001 秒、LiDAR 10Hz、地図（fine、0.1m）、途切れの基準 1.0 秒（シミュレーション時間）、制御（20Hz、先読み 1m）、ソフトウェア描画、イメージ。
- シナリオ：`08OB86_-0205`、`--map fine`。3 か所のうち走行が最も短い（クラウドでシミュレーション時間 約 240 秒）。

## コードを直接変えずに走らせる方法
`--map fine` は `lidar_map.py` の `fine_protocol()` が 0.3 倍以外を拒否し、`lidar_checks.py` が world の値を `'0.3'` に固定している。
`conference/ros2_jazzy/` は変更禁止なので、この 2 ファイルの変更済みコピーを `overlay/` に置き、Docker で読み取り専用で重ねて実行する。変更内容は `overlay.diff` がすべて。
リポジトリの追跡中のファイルは変えていない。`THESIS_ONLY_PATCH` で走らせる砂浜を 1 か所にしている。

## 実行の順番
`run_both.sh` が `rtf_1/`（目標 1.0）、`rtf_0.3/`（対照）の順に実行し、最後に `analyze_rtf.py` が `comparison.csv`・`comparison.json` を作る。
対照を追加したのは、測定を同じ道具・同じ基準で比べるため（3 か所の試験には probe がない）。

## 時間の基準（コードで確認）
| 量 | 基準 | 根拠 |
|---|---|---|
| LiDAR 10Hz | シミュレーション時間 | Gazebo のセンサーの `update_rate`。点群の時刻もシミュレーション時間 |
| 地図更新の間隔・頻度（`map_updates.csv` の `stamp`） | シミュレーション時間 | 点群の header の時刻。行数は「処理した点群」で、受信数ではない |
| `update_s`（地図更新の時間） | 実時間 | `time.perf_counter()` |
| `plan_time_s` | 実時間 | 計画の計測 |
| 途切れ判定 1.0 秒 | シミュレーション時間 | `get_clock()`（`use_sim_time`）と点群の時刻の差 |
| 制御 20Hz、`map_tick` 50Hz、`tick` 20Hz | シミュレーション時間 | `create_timer` と `use_sim_time` |
| `probe.csv` の `wall_s` | 実時間 | `time.monotonic()` |

- 実時間での予算は倍率で変わる：点群 1 回分は 0.3 倍で 0.333 秒、1.0 倍で 0.100 秒。途切れ基準 1.0 秒は、0.3 倍で実時間 3.33 秒、1.0 倍で実時間 1.0 秒。
- `comparison.csv` の項目名には基準を入れている（`_sim_`／`_wall_`）。`update_share_of_scan_period_median` は、`update_s` をその倍率の実時間の周期で割った値。

## 記録するもの
- `rtf_*/physical_1/`：既存の形式の記録（`mission.json`、`map_updates.csv`、`replans.csv` など）
- `rtf_*/physical_1/probe.csv`：壁時計 1 秒ごとの受動的な測定。何も publish しない
- `rtf_*/physical_1/gz_stats.txt`、`world_audit.txt`：Gazebo の /stats、実際の world の倍率・刻み・更新周期
- `rtf_*/resources.csv`：CPU（平均・最も忙しいコア）・メモリ・GPU・プロセス別の使用率
- `resources_rtf03.csv`：3 か所の試験の途中からの参考記録

## 終了状態の分離（`rtf_*/status.json`）
- `simulation`：Docker の終了コード、時間切れ、`manifest.json` の `execution`、走行の終わり方と誤り
- `measurement`：probe・資源・/stats・world の記録が残っているか
- `existing_report`：`lidar_checks.py` の終了コードと、既存集計の結果（`passed`／`expected_failure`／`unexpected_failure`／`failed_outside_report`／`not_run`）
- `lidar_fine_report` は 0.3 倍以外と 10 か所以外を拒否する条件を持つ。これは `expected_failure` として記録する。
  生データと `manifest.json` は集計の前に保存される。コンテナ内の処理は `set -e` を使わず、終了コードを保存して続けるので、集計の失敗で chown・サンプラーの停止・状態の記録・比較の集計は止まらない。

## 判定の条件（走らせる前に決めたもの）
- 達成：走行中の実測倍率（シミュレーション時間 ÷ 実時間）が 0.95 以上で、壁時計 30 秒の移動区間の 5% 値も 0.95 以上。
- 追いついている：受信頻度と地図更新頻度（どちらもシミュレーション時間あたり）が対照より下がらず、`queue_drops` が増えず、点群の古さ（シミュレーション時間）が 1.0 秒に届かない。
- 異常なし：`lidar_unavailable_or_stale`・実行時の誤りがない。`handoff_*` と `/cmd_vel` の間隔は実時間とシミュレーション時間の両方で対照と比べる。
- 1 か所 1 回ずつなので、走行結果の一致を保証するものではない。結果が変わった場合はそのまま報告する。

## 結果（2026-11-07、1 か所 1 回ずつ）
`comparison.csv`（`analyze_rtf.py`）と `comparison_extra.json`（引き継ぎ・走行中の資源・軌跡）が元の数値。`replans.csv` の引き継ぎの列は `raw/*/follower/*/replans.csv` にあるため、`comparison_extra.json` に集計した。

| 項目（基準） | 目標 1.0 | 対照 0.3 |
|---|---|---|
| 走行の終わり方 | completed | completed |
| 実測倍率（シミュレーション時間 ÷ 実時間） | 0.9997 | 0.3000 |
| 壁時計 30 秒の移動区間の 5% 値／最小 | 0.9995／0.9994 | 0.3000／0.2999 |
| 点群の受信頻度（シミュレーション時間あたり） | 9.08Hz | 8.55Hz |
| 地図更新の頻度（シミュレーション時間あたり） | 9.08Hz | 8.55Hz |
| 地図更新の時間（実時間、中央値／95%／最大） | 0.071／0.087／0.128 秒 | 0.056／0.072／0.082 秒 |
| 更新時間 ÷ 実時間の周期（中央値） | 71% | 17% |
| 実時間の周期を超えた更新 | 0.6% | 0% |
| 点群の古さ（シミュレーション時間、中央値／最大） | 0.217／0.525 秒 | 0.059／0.458 秒 |
| /cmd_vel の頻度（シミュレーション時間あたり） | 19.93Hz | 19.95Hz |
| /cmd_vel の最大間隔（シミュレーション時間） | 0.052 秒 | 0.050 秒 |
| 経路の引き継ぎ（シミュレーション時間、中央値／最大） | 0.05／0.10 秒 | 0.05／0.05 秒 |
| `queue_drops`／地図の誤り／センサーの誤り | 0／0／なし | 0／0／なし |
| CPU 全体（走行中、中央値／最大） | 12.6／21.9% | 5.3／5.9% |
| 最も忙しいコア（走行中、中央値／最大） | 19.1／37.4% | 11.5／18.7% |
| メモリ（最大） | 3.79GiB | 3.86GiB |
| GPU の使用率／メモリ | 0%／15MiB | 0%／15MiB |

- 終了状態：`simulation` と `measurement` は両方 ok。`existing_report` は 1.0 が `expected_failure`、0.3 が `passed`。
- 判定：倍率 1.0 は達成。ただし更新時間の余裕は小さく、軌跡は最大 14.5m 離れた（中央値 0.64m）。probe は壁時計 1 秒ごとなので、点群の古さの最大は過小かもしれない。
- まだ測っていないもの：姿勢の取得から `/cmd_vel` までの端から端までの遅延、長時間の安定性、点群の受信が 10Hz を下回る原因。
- 図：`tracks_rtf1_vs_rtf03.png`。

## 軌跡のばらつき（`trajectory_gaps.csv`）
同じ砂浜の 4 本（目標 1.0、対照 0.3、3 か所の試験の 0.3、クラウドの 0.3）を組ごとに比べた。0.3 倍どうしでも経路が分かれるかどうかを確かめるため。
