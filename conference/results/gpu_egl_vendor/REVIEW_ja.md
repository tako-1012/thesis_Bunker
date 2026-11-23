# 056 のレビュー（Claude、2026-11-23、取り込む前）

対象：`codex/056-gpu-egl-vendor`（`16a5edd`・`4fa0d71`）。元は `realtime-map` の `9014c19`。手順は `CLAUDE.md` の 1〜6。

## 結論
- **取り込んでよい。** 問題は見つからなかった。NVIDIA で描けるかは、研究 PC で 054 をやり直すまで分からない（057 のあと）。

## 確かめたこと
1. **差分**
   - 変わったのは `run_lidar_checks.sh`、`gpu_rendering.py`、`lidar_checks.py`、`results/gpu_rendering/cloud_pair.py`・`README_ja.md`、テスト。
   - 保護されたファイル・既存の結果・`ros2/`・既存のテストは変わっていない（`test_gpu_rendering.py` は足しただけ）。
2. **全テスト**：取り込んだ状態で、Claude の環境で全 47 本が exit=0（1 本ずつ）。
3. **既定の出力**：
   - `cpu` の分岐は変わっていない（`run_lidar_checks.sh` の差分は `gpu` の分岐の中だけ）。
   - `lidar_checks.py` で足した処理は、すべて `if gpu:` の中か `render_mode == 'gpu'` の中。
   - テストも、直す前の版と同じ環境で `cpu` の引数・環境変数・manifest を比べている。
4. **中心の差分を読んだ**：
   - **`gpu` の起動**：ホストの `10_nvidia.json` を読み取り専用でコンテナに見せ、`__EGL_VENDOR_LIBRARY_FILENAMES` でそのファイルを指す。ファイルがなければ Docker を起動する前に止まる。
   - **描画の判定**：Ogre2 の記録の最後の `GL_VENDOR`・`GL_RENDERER` の組で判定する。Mesa・`llvmpipe` などなら `gpu_rendered: false`。
   - **集計**：片方の走行が止まっても `summary.json` が作れ、比べられない欄は空になる。
   - `/code-review`（low）でも指摘はなかった。
5. **わざと壊す**（2 つとも検出）：
   - Mesa の判定をなくす → テストが検出。
   - 読み取り専用で見せる引数を消す → テストが検出。
6. **数字**：この作業は新しい数値を出さない（054 の止まった記録で `summary.json` が作れることは、テストが確かめている）。
