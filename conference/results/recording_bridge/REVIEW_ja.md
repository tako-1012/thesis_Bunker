# 077 のレビュー（Claude、2026-11-27、取り込む前）

対象：`codex/077-recording-bridge`（`46fd958`・`ec04abe`）。元は `realtime-map` の `eb5ee12`。手順は `CLAUDE.md` の 1〜6。

## 結論
- **取り込んでよい。** 問題は見つからなかった。075 の走行のフォルダを、076 の道具がそのまま読めるようになった。
- 次は研究 PC で、目印 0・10・40・160 個の世界を走らせて記録を取り、この道具で位置のずれを測る。

## 確かめたこと
1. **差分**：
   - 新しいファイル：`experiments/recording_bridge.py`、テスト、結果。
   - 変えたファイル：`experiments/offline_localization.py`（フォルダを渡されたときの分岐を足しただけ）。
   - 既存の結果・`ros2/`・既存のテストは変わっていない。
2. **全テスト**：Claude の環境（KISS-ICP・small_gicp 入り）で全テストを走らせた（下の「全テストの結果」）。
3. **既定の出力**：076 のとき Claude が走らせた `--synthetic landmarks` の出力（`summary.csv`・`alignments.csv`・`trajectory.csv`）と標準出力が、077 でも**バイト単位で同じ**だった（同じ環境）。
4. **中心の差分を読んだ**：
   - LiDAR の点は 075 の `iter_lidar` で元に戻し、正解の位置と時刻をそろえ、スキャンの時刻が合わなければ止める。
   - **取り付け位置の基準**：正解の位置（`/ground_truth`）は BUNKER のモデルの原点。Gazebo のモデルでは `base_link` が原点から 0.35m 上にあり、LiDAR は `base_link` から「取り付け位置 − 0.35m」の所に置かれる（`thesis_bunker_gz/model.py`・`lidar.py`、`tapp/sensor_geometry.py` の `base_link_xyz`）。なので、モデルの原点から見た LiDAR の位置は manifest の `sensor_configuration.mounts.lidar.xyz` そのもので、077 はこれを使っている。`world.sdf` から取る場合も、`base_link` の位置と LiDAR の位置を掛け合わせていて、同じ値になる。
   - 取り付け位置が見つからないときと、別の走行の地図の点群を渡したときは、エラーで止まる。
   - `/code-review`（low）でも指摘はなかった。
5. **わざと壊す**：取り付け位置を `base_link` 基準の値（0.35m 低い）に取り違える → テスト 2 つ（取り付け位置の基準、075 の形での 3 通りの通し）が検出した。
6. **数字の出し直し**：テストと同じ合成の 075 形式の記録を作り、`--recording` で走らせ直した。重ね合わせの平均誤差 2.57mm を含め、`summary.csv` は報告と一致した（違いは 1e-15 程度の浮動小数の差だけ）。

## 全テストの結果
- `codex/077-recording-bridge`（`realtime-map` の `eb5ee12` から）で、`conference/tests/test_*.py` の 61 本を `python3 -m tests.<名前>` で走らせ、**61 本すべて exit=0**（4 本ずつ並べて実行。KISS-ICP・small_gicp 入りで、飛ばしたテストはない）。
