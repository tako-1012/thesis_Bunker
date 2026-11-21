# 045 のレビュー（Claude、2026-11-21、取り込む前）

対象：`codex/045-gpu-rendering`（`2dcb6fb`・`47b1bc3`）。元は `realtime-map` の `a048057`。手順は `CLAUDE.md` の 1〜6（046 と合わせて取り込むので、全テストは 2 つを合わせた状態で走らせた）。

## 結論
- **取り込んでよい。** 既定（`cpu`）では、`run_lidar_checks.sh` が組み立てる `docker run` の引数が、直す前と（保存先のパスを除いて）同じ（Claude が偽の Docker で直す前と後を走らせて比べた、49 個の引数すべて一致）。
  034 以来の既定の出力の比較（`none`・`v1`）も一致。
- GPU で本当に描けるか・1 倍が出るかは、研究 PC で確かめるまで分からない（クラウドに GPU がない）。044 のあとに `results/gpu_rendering/README_ja.md` の手順で確かめる。

## 確かめたこと
- 差分：`run_lidar_checks.sh`（`THESIS_RENDER=gpu` のときだけ `--gpus all` を付け、ソフトウェア描画を外す）、`lidar_checks.py`（manifest に描画の方法と、Ogre2 の記録から読んだレンダラ名）、確認のスクリプト、`RESEARCH_PC_ja.md` の追記（研究 PC に何かを入れるときは利用者の確認が要る、と書いてある）。
- `lidar_checks.py` は 046 と同じ場所を触っていて、取り込むときにぶつかった。Claude が両方の分岐を残して解消した（`gpu` の終わり方と `substitute` の終わり方を別々に）。
- わざと壊す：`gpu` のときに `--gpus all` を付けない → `test_gpu_rendering` が検出。
- `/code-review`（low、045＋046 の合わせた差分）：所見なし。

## テストの結果
- 045 と 046 を合わせた状態で、`conference/tests/` の 40 本すべてが終了コード 0（`gpu_rendering/review_all_tests_summary.txt`、NumPy 2.3.5・SciPy 1.17.0）。
