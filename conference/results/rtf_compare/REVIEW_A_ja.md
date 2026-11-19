# 039 段階 A のレビュー（Claude、2026-11-19、取り込む前）

対象：`codex/039-rtf-option`（`9d74bf3`・`71c4c71`）。元は `realtime-map` の `0e0dfee`。手順は `CLAUDE.md` の 1〜6。

## 結論
- **取り込んでよい。** 既定（0.3 倍）の出力は直す前とバイト単位で同じ。`--real-time-factor 1.0` で manifest の倍率が 1.0、点群の古さの基準 1.0 秒は変わらない。
- 走行中と同じ条件（同じ地図に 360 回）の地図の更新は、LiDAR の 95% 値 38ms・最大 63ms（Codex の環境）。3 つのセンサーが 10Hz なら 1 秒あたり約 0.55 秒で、1 倍の 1 秒に収まる見込み。
  ただし Gazebo の描画・ROS の通信・計画と同時に動かしたときは未確認で、段階 B で確かめる。

## 1. 差分
`lidar_checks.py`・`lidar_map.py`・`run_lidar_checks.sh` に `--real-time-factor 0.3|1.0`、テスト `test_rtf_option.py`、比べるための記録 `tests/reference/rtf039_default.json`、計測 `results/rtf_compare/`。
既存のテスト・既存の結果は変えていない。`ros2_jazzy/` の変更は指示書 039 が許可したもの。

## 2. 全テスト
35 本（既存 34＋新規 1）。結果は末尾。

## 3. 既定の出力
034 の `capture_defaults.py`（7 項目）を、元の `realtime-map` と 039 で走らせ、すべて一致。fine の 10 か所の manifest は、`--real-time-factor 0.3` を明示しても既定とバイト単位で同じ。
`--real-time-factor 1.0` では `real_time_factor=1.0`・`stale_timeout_s=1.0`。

## 4. コードを読んで
- CLI の値が環境変数より優先される。`--map fine` 以外で指定すると拒む。1.0 のときは 023 の集計（0.3 倍が前提）を行わず、記録だけ残す。
- `/code-review`（low）の所見：1.0 の終わり方の分岐が CLI の値だけを見ていて、環境変数（`THESIS_FINE_PROTOCOL=rtf_check`＋`THESIS_REAL_TIME_FACTOR=1`）で 1.0 にした場合は 023 の集計に進み、そこで失敗する。
  段階 B では CLI の `--real-time-factor` を使うので影響はない。直すなら `manifest['real_time_factor']` を見る（急ぎではない）。

## 5. わざと壊す
| 壊したところ | 結果 |
|---|---|
| CLI の 1.0 を無視する | `test_rtf_option` が検出 |
| fine 以外でも受け付ける | 検出 |

## 6. 報告の数字
末尾に追記。
