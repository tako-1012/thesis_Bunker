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
35 本。結果は末尾（`test_rtf_option` が Claude の環境で落ちた。下の「直したこと」）。

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
| `THESIS_FINE_PROTOCOL` なしでも 1.0 を許す | 検出 |

## 6. 報告の数字
Claude の環境（Intel Xeon 2.10GHz）で `benchmark.py` を走らせた（`review/benchmark_claude_env.csv`、同じ地図に 360 回）。

| センサー | 中央値 [ms] | 95% 値 [ms] | 最大 [ms] | 急斜面が変わった回 |
|---|---:|---:|---:|---:|
| LiDAR | 49.4 | 53.2 | 63.4 | 119 |
| カメラ 1 | 11.8 | 13.4 | 19.4 | 91 |
| カメラ 2 | 10.8 | 12.6 | 13.6 | 32 |

Codex の環境（LiDAR 38ms・カメラ 8.5ms）より遅く、3 つが 10Hz なら 1 秒あたり約 0.79 秒。1 倍の 1 秒には収まるが余裕は小さい。
Gazebo の描画・ROS・計画と同時に動く研究 PC で、1 倍が追いつくかは段階 B の結果で判断する。

## 直したこと（Claude）
- **`test_rtf_option.py` が、記録したときと違う Python・NumPy の環境で落ちた。** 準備のときに作られる 023 の集計の表・記録の文字列（数字の書き方）が、環境によって変わるため。
  - 直す前と後のコードを、同じ環境で比べると完全に一致した（`capture_default` を元の `realtime-map` と 039 の両方で実行し、すべての項目が一致）。コードの問題ではなく、テストの比べ方の問題。
  - 環境が記録と違うときは、manifest 全体と同じように、集計の表・記録のハッシュも比べないようにした。**manifest の本体（環境の情報を除く）は、どの環境でもバイト単位で比べる**ので、確かめる中身は弱めていない。
  - 研究 PC の venv（`requirements-venv.txt` の版）は記録した環境と同じ版なので、そこではすべてを比べる。
- 直したテストで、わざと壊す確認をやり直した（上の 5 の表に 1 つ追加：環境変数だけで 1.0 を許す → 検出）。

## テストの結果
- 直す前：35 本のうち `test_rtf_option` だけが失敗（`review/all_tests_summary_before_fix.txt`）。
- 直したあと：`test_rtf_option` が通ることを確かめた。ほかの 34 本は直す前の実行で合格している（直したのはこのテストのファイルだけ）。
