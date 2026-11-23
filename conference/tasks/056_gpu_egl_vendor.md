# 指示書 056：GPU で描くときに、コンテナから NVIDIA の EGL を選べるようにする（`THESIS_RENDER=gpu` のときだけ）

> **状態：実行中（2026-11-23 にクラウドの Codex（研究実装1）へ依頼）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（研究 PC での確かめは、057 の走行のあとに 054 をやり直す）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/results/gpu_check_054/REPORT_ja.md`・`REVIEW_ja.md`（**この指示書の根拠**）・`gpu/egl_diagnostics.txt`・`host_egl_diagnostics.txt`・`gpu/ogre2_live.log`、
> `conference/results/gpu_rendering/README_ja.md`・`run_smoke.sh`・`cloud_pair.py`、`conference/ros2_jazzy/gz_checks/run_lidar_checks.sh`・`gpu_rendering.py`、`conference/tests/test_gpu_rendering.py`（あれば）を読むこと。
> ブランチは `codex/056-gpu-egl-vendor`（その時点の `realtime-map` の最新から）。報告は `conference/results/gpu_egl_vendor/REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- Gazebo を 1.0 倍に設定しても実際は 0.6 倍しか出ない。深度カメラ 2 台を CPU（ソフトウェア描画）で描いていることが原因の第一候補。
- 045 で `THESIS_RENDER=gpu`（`--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all`）を作ったが、054 で研究 PC で試すと、Ogre2 の記録は `GL_VENDOR = Mesa` で、GPU で描けていなかった。
- 研究 PC のホストには `/usr/share/glvnd/egl_vendor.d/10_nvidia.json`（`libEGL_nvidia.so.0` を指す）がある。コンテナの中には `libEGL_nvidia.so.0` はあるが、EGL の定義のファイルは Mesa（`50_mesa.json`）しか見えない。そのため EGL が NVIDIA を選べない、と考えられる。
- 研究 PC に何かを入れたり設定を変えたりはしない（利用者の決まり）。**起動の引数を足すだけ**で直す。この引数を付けることは、2026-11-23 に利用者が了承した。

## 作るもの（`THESIS_RENDER=gpu` のときだけ変わる。既定の `cpu` の起動の引数・出力はバイト単位で変えない）
1. `run_lidar_checks.sh` の `gpu` のとき：
   - ホストに `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` があれば、それを**読み取り専用で**コンテナの同じ場所に見せる（`-v …:ro`）。
   - あわせて `__EGL_VENDOR_LIBRARY_FILENAMES` でそのファイルを指す（Mesa に落ちないように）。
   - ホストにそのファイルがなければ、走らせる前に分かりやすい文で止める（黙って CPU で走らない）。
2. `gpu_rendering.py`（または manifest を書く所）：GPU のとき、manifest に「渡した EGL の定義のファイル」と、Ogre2 の記録から読んだ `GL_VENDOR`・`GL_RENDERER` を残す。`GL_VENDOR` が Mesa なら、その走行を「GPU で描けていない」として記録する。
3. `results/gpu_rendering/cloud_pair.py compare`：片方の走行が途中で止まった場合も、`summary.json` が作れること（054 では `unsupported operand type(s) for /: 'PosixPath' and 'NoneType'` で GPU の欄が壊れた）。止まった走行は理由を書いて、比べられない欄は空にする。
4. `results/gpu_rendering/README_ja.md` に、054 の結果とこの直しを書き足す（再確認の手順はそのまま使えること）。

## 守ること・やらないこと
- 既定（`cpu`）の起動の引数・環境変数・manifest は、バイト単位で変えない（直す前のスクリプトと同じ環境でその場で比べるテスト）。
- 研究 PC に何かを入れる手順を書かない。Gazebo は走らせない。

## テスト（`conference/tests/test_gpu_rendering.py` に足すか、新しく `test_gpu_egl_vendor.py`。ROS2・Gazebo・GPU なしで動くこと）
1. `cpu` の起動の引数が直す前と同じ。
2. `gpu` のとき、偽のホストの定義のファイルがあれば `-v …10_nvidia.json:…:ro` と `__EGL_VENDOR_LIBRARY_FILENAMES` が付き、なければ走らせる前に止まる。
3. Ogre2 の記録の例（054 の `ogre2_live.log` の `GL_VENDOR = Mesa` と、NVIDIA の場合の例）から、描けた・描けていないを正しく判定する。
4. 片方が止まった記録で `summary.json` が作れる。
5. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 研究 PC で 054 をやり直すときのコマンド（README の手順のまま使えるか）。
3. できなかったこと、自信がないこと（この直しで NVIDIA が選ばれる見込みと、選ばれなかったときに次に疑う所）。
