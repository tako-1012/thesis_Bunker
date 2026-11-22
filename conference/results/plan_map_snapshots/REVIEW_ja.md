# 051 のレビュー（Claude、2026-11-22、取り込む前）

対象：`codex/051-plan-map-snapshots`（`245e3a6`・`fcf9310`・`555e8c1`）。元は `realtime-map` の `cb6bdf4`。手順は `CLAUDE.md` の 1〜6。

## 結論
- **取り込んでよい。** 問題は見つからなかった。

## 確かめたこと
1. 差分：`gz_checks` の `endpoint_runtime.py`・`lidar_checks.py`・`lidar_planner.py`・`safety_runtime.py`・`run_lidar_checks.sh`、新しい `plan_maps.py`・`experiments/plan_map_inspect.py`、テスト、結果。保護されたファイル・既存の結果・`ros2/`・既存のテストは変わっていない。
2. 全テスト：Claude の環境で全 44 本が exit=0（1 本ずつ）。
3. 既定の出力：新しいテストの 1 が、元のコミット `cb6bdf4` の実装をその場で読み込み、同じ環境で manifest・起動の引数・計画の CSV・診断の NPZ をバイト単位で比べている（`none`・`v1`・`v2`）。
4. 中心の差分を 1 行ずつ読んだ：
   - `capture()` の既定の辞書は、キーと順序が前と同じ。
   - 地図を保存する仕組みは、`self.pending` が使われたあと `None` に戻る（`online_runtime.py`）ので、同じ計画が二重に記録されることはない。
   - コストの XOR 差分は float64 のビットを失わない。書き込みに失敗したら、そこで記録を止める（`incomplete.json`）。
   - `prior_inflated` は `tm.rock`（膨らませ済み）で、名前どおり。
   - `/code-review`（low）でも指摘はなかった。
5. わざと壊す：
   - 差分の戻し方を壊す（`previous = delta`）→ テスト 2 が検出。
   - 既定の診断の記録にキーを 1 つ足す → テスト 1 が検出。
6. 数字の出し直し：`estimate.py` を走らせ直し、`size_log.txt` と同じ（255 計画で 26.594MB、最大の見積もりで 32.390MB）。

## 残ること
- 保存は計画の処理の中で行うので、研究 PC で地図の更新・計画の時間と実時間の倍率への影響を確かめる（050 のあと）。
