# 043 のレビュー（Claude、2026-11-21、取り込む前）

対象：`codex/043-path-tracking`（`e1c364e`・`78b840e`）。元は `realtime-map` の `fa86d83`。手順は `CLAUDE.md` の 1〜6。

## 結論
- **取り込んでよい。** 既定（`default`）と `--online-fixes none`・`v1` の出力は、直す前とバイト単位で同じ（自分で比べた）。`corner_slow` は選んだときだけ働く。
- **ただし、模型での比較からは `corner_slow` が効くかは言えない。** 模型では、どの条件でもずれが最大 0.2m 程度で、Gazebo（035・037 で最大 0.6〜0.95m）よりずっと小さい。
  模型は Gazebo の大きなずれ（履帯の滑りなど）を再現できていないので、効果は研究 PC の Gazebo で確かめるしかない。

## 1. 差分
`tapp/tracking.py`・`tracking_sim.py`（新規）、`path_follower.py`・`online_runtime.py`・`lidar_checks.py`・`run_lidar_checks.sh`（`--tracking` を通す）、テスト、結果。
変更禁止の `pure_pursuit.py`・`follower.py`・`robot_sim.py` は変えていない。検証用の砂浜（12 か所）だけを使い、テスト用は使っていない。

## 2. 全テスト
042 と合わせた状態で 38 本。結果は末尾。

## 3. 既定の出力
040 の `capture_compatibility`（034 の 7 項目と、`none`・`v1` の追従・実行・記録）を、直す前（`fa86d83`）と 042＋043 を合わせた状態で走らせ、すべて一致。

## 4. コードを読んで（`/code-review` low も含む）
- `corner_slow`：Pure Pursuit の進み具合をそのまま使い、目標への向きのずれが 45° を超えたらその場で回り、そうでなければ速度を `v_max × max(0.3, cos(角度))` にする。
- 所見【低】：「2.0m 先までの向きの変化」を、**経路の頂点ごとの向きの変化の絶対値の合計**で測っている（指示書は「向きの変化」とだけ書いていた）。
  S 字でも減速できる一方、マスの経路の細かいジグザグでも合計が大きくなり、ほぼ直線でも遅くなりうる。報告にも書かれている。Gazebo で比べるときに、直線で遅くなっていないかを見る。

## 5. わざと壊す
| 壊したところ | 結果 |
|---|---|
| 最低速度 0.3 → 0.4 | `test_path_tracking` が検出 |
| その場で回る閾値 45° → 60° | 検出 |
| 模型の遅れ 0.3 秒 → 0.5 秒 | 検出 |

## 6. 報告の数字
`runs.csv`（240 走行）と `summary.csv` は、指示書どおりの条件（検証用の 12 か所 × 5 経路 × 4 条件）。表の値（遅れありで `default` 0.217m、`corner_slow` 0.210m など）は `summary.csv` と一致。

## テストの結果
- 042 と 043 を合わせた状態で、`conference/tests/` の 38 本すべてが終了コード 0（`review_all_tests_summary.txt`、NumPy 2.3.5・SciPy 1.17.0）。
