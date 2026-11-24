# 054 再確認　研究 PC の Gazebo センサー描画

**NVIDIA の EGL 描画を確認した。** `08OB88_-1417` の 1.0 倍設定で CPU・GPU とも完走し、実測は CPU **0.613960 倍**、GPU **0.996972 倍**。GPU/CPU は **1.623839** で、この 1 組の GPU 試行は実時間ほぼ 1.0 倍で走った。点群の XYZ 配列には 3 センサーとも差があった。

## 実行と描画の確認

実行コミットは `58e3b1003e993a5f26e534c202dab1f0cede8678`。Mac で取得した `origin/realtime-map` を Git bundle で `hayashi` に移し、`claude/054-gpu-retry` を作成した。報告・集計のコミットはこのブランチを Mac 経由で公開する。

057 は 45 回と集計が終了コード 0 で完了していた。開始直前にほかの Gazebo と Docker コンテナがないことを確認した。研究 PC の tmux セッション `gpu-054b` で 2026-11-25 00:13:14 から 00:27:02 まで 1 組を実行した（日本時間）。既存の `thesis/jazzy-gz:1`、ROS ドメイン 65、fine、LiDAR ＋ 深度カメラ 2 台、1.0 倍設定。共通の引数とイメージ ID は [conditions.txt](conditions.txt)。

```bash
cd ~/thesis_Bunker_rtf/conference
bash results/gpu_rendering/run_smoke.sh "$HOME/thesis_checks/gpu_rendering_054b" "$HOME/.venvs/thesis-python/bin/python"
```

- ホストとコンテナの `nvidia-smi` はどちらも RTX 5060 Laptop GPU を認識した。ドライバは 595.99.02。 [ホスト](host_nvidia_smi.txt) · [コンテナ](container_nvidia_smi.txt)
- GPU 側の manifest に EGL ベンダー定義 `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` が記録され、実コンテナで同じパスへの読み取り専用マウントと `__EGL_VENDOR_LIBRARY_FILENAMES` を確認した。 [マウント記録](gpu_egl_mount.txt)

| 試行 | GL ベンダー | GL レンダラ | manifest の `gpu_rendered` |
| --- | --- | --- | --- |
| CPU | Mesa | `llvmpipe (LLVM 20.1.2, 256 bits)` | 項目なし |
| GPU | NVIDIA Corporation | `NVIDIA GeForce RTX 5060 Laptop GPU/PCIe/SSE2` | `true` |

CPU 側は試行中に取得した [Ogre2 ログ](cpu/ogre2.log) から、GPU 側は [manifest](gpu/manifest.json) と [Ogre2 ログ](gpu/ogre2.log) の両方から描画を確認した。056 の修正後はこの条件で NVIDIA が選ばれた。

## 実測倍率と GPU 使用率

| 試行 | 結果 | ミッション sim 秒 | 実秒 | 実測倍率 | GPU 使用率の中央値 / 最大 | 標本数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| CPU | 完走 | 299.530 | 487.865 | 0.613960 | 0% / 8% | 451 |
| GPU | 完走 | 297.310 | 298.213 | 0.996972 | 8% / 12% | 315 |

実測倍率はミッションのシミュレーション秒 ÷ 実秒。GPU 使用率は起動・ビルドを含む各試行の NVIDIA GPU 全体を約 1 実秒ごとに採った値。GPU 描画を確認したため、LiDAR のみの追加走行は条件に該当しない。 [summary.json](summary.json)

## 点群比較

各側で LiDAR・camera1・camera2 を 8 フレームずつ取得し、プローブは両側とも終了コード 0。センサーごとにミッション開始前の最初の共通時刻・姿勢の 1 組を照合した。3 センサーとも真値姿勢の時刻は点群時刻と一致し、両試行の位置差・角度差は 0。元の配列形状・フレーム名が揃い、XYZ 配列はどれも完全一致しなかった。

| センサー | 時刻 sim 秒 | 有限レイの組数 | CPU のみ / GPU のみ有限 | 距離差の中央値 mm（GPU−CPU） | 絶対差の中央値 / 95% 値 / 最大 mm |
| --- | ---: | ---: | ---: | ---: | ---: |
| LiDAR | 0.100 | 12,173 | 0 / 0 | −0.525 | 19.032 / 55.682 / 117.513 |
| camera1 | 0.200 | 11,811 | 1 / 0 | +0.012 | 3.953 / 22.926 / 53.643 |
| camera2 | 0.100 | 9,328 | 0 / 0 | −0.043 | 4.403 / 22.855 / 53.518 |

距離は有限なレイのセンサー原点からの距離。XYZ の一致判定は色や強度を含まない。この 1 組では点群差を確認できたが、別々に実行したため、各センサーのノイズと描画方式の寄与は切り分けられない。倍率・点群の結果はこの砂浜と設定での観測。 [summary.json](summary.json)

## 記録とテスト

- [CPU](cpu/)・[GPU](gpu/) の manifest、console.txt、probe.txt、probe_exit.txt、ogre2.log を収録。両試行と smoke 全体の終了コードは 0。
- 点群 NPZ、軌跡などの生記録と GPU 使用率の時系列は研究 PC の `/home/kotaro/thesis_checks/gpu_rendering_054b/` に保管した。全 129 ファイルの SHA-256 を照合済み。 [パスと SHA-256](not_committed.txt)
- 保存記録から下記の比較を再実行し、終了コード 0 と `summary.json` のバイト一致を確認した。 [照合結果](verification.txt)
- 走行後のオフラインテストは **52/52 本合格**。同じコミットの追跡ファイルを一時作業ツリーに展開し、研究 PC の既存 venv で `python -m tests.<モジュール名>` を全件実行した。 [テスト結果](tests/summary.txt)

```bash
cd ~/thesis_Bunker_rtf/conference
"$HOME/.venvs/thesis-python/bin/python" results/gpu_rendering/cloud_pair.py compare "$HOME/thesis_checks/gpu_rendering_054b"
```
