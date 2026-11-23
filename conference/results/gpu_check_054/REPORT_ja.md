# 054　研究 PC の Gazebo GPU 描画の初回確認

`08OB88_-1417` で、1.0 倍設定の CPU 側は完走した。GPU を指定した側の Ogre2 は `llvmpipe` を選んだため、2026-11-23 13:07:53 JST にその試行を停止した。NVIDIA 描画での実測倍率、GPU/CPU の倍率比、ハードウェア描画による点群差は未測定。

## 1. 実行と 050 の完了確認

- 実行時コミットは `bbaa7c7a8b5f13152d66c0bf26e7552a1deaa7d2`。Mac で取得した `origin/realtime-map` を Git bundle で研究 PC に移し、`~/thesis_Bunker_rtf` に `claude/054-gpu-check` を作った。結果のコミットの push は Mac を経由する。
- 050 段階 A は45回および共通集計が完了済みで、バッチ終了コードは0。054 の開始時に同時稼働中の Gazebo と Docker コンテナがないことを確認した。
- セッションは `gpu-054`。fine、LiDAR と深度カメラ2台、`non_obstacle`、`v2`、診断あり、1.0 倍設定、ROS ドメイン65。イメージは `conditions.txt` に記録した `thesis/jazzy-gz:1`。

```bash
cd ~/thesis_Bunker_rtf/conference
mkdir -p "$HOME/thesis_checks"
# 2026-11-23 12:58:05 JST に tmux セッション gpu-054 内で一度だけ実行
bash results/gpu_rendering/run_smoke.sh "$HOME/thesis_checks/gpu_rendering_054" "$HOME/.venvs/thesis-python/bin/python"

# NVIDIA 指定側を停止した後、保存記録だけを集計
"$HOME/.venvs/thesis-python/bin/python" results/gpu_rendering/cloud_pair.py compare "$HOME/thesis_checks/gpu_rendering_054"
```

## 2. GPU の認識と描画

| 項目 | 実測・確認結果 |
| --- | --- |
| ホストの `nvidia-smi` | NVIDIA GeForce RTX 5060 Laptop GPU、ドライバ 595.99.02 |
| `--gpus all` のコンテナ内 `nvidia-smi` | 同じ GPU を認識。スクリプトの Docker 事前確認は通過 |
| GPU 指定側の実レンダラ | `llvmpipe (LLVM 20.1.2, 256 bits)`。稼働中の Ogre2 ログに `GL_RENDERER` と `Device Name` の両方が記録 |
| ホストの EGL ベンダー定義 | `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` と `50_mesa.json`。Toolkit CLI は1.19.1 |
| GPU 指定コンテナの EGL ベンダー定義 | 調べた標準ディレクトリには `50_mesa.json` のみ。NVIDIA の JSON は見えず、`libEGL.so.1`、`libEGL_nvidia.so.0`、`libglvnd0` は存在 |

現行の GPU コンテナで確認できた不足は、GLVND が NVIDIA の EGL ベンダーを登録するための定義ファイル。ホストの NVIDIA 定義が当該コンテナから読めるようにした上で、実際のレンダラを再確認する必要がある。この対処で NVIDIA 描画が成立するかは未検証。現行の Toolkit と EGL ローダーは確認済み。環境変更は利用者の確認待ち。

GPU 指定側の稼働中に、`docker exec` で Ogre2 ログ、`ldconfig -p`、GLVND のベンダー定義ディレクトリ、パッケージ状態とGPUデバイスを読み取った。対象の smoke スクリプトに `TERM` を送って停止し、終了コード143を記録した。終了後に稼働中のコンテナがないことを確認した。導入・設定変更・再走行は実施していない。

## 3. 実測倍率と GPU 使用率

| 試行 | 状態 | ミッション sim秒 / 実秒 | 実測倍率 | GPU 使用率の中央値 / 最大 | 標本数 |
| --- | --- | --- | ---: | ---: | ---: |
| CPU | 完走 | 297.030 / 484.583 | 0.612961 | 0% / 8% | 448 |
| GPU 指定 | llvmpipe で起動後に停止 | — | — | 0% / 8% | 71 |

使用率はスクリプトが起動・ビルドを含めて約1実秒ごとに採った GPU 全体の値。停止した側の標本を NVIDIA 描画負荷としては扱えない。GPU/CPU の倍率比と 1.0 倍の達成は判定不能。停止後に既存の比較コマンドを実行して `summary.json` を出した。GPU 指定側の manifest は起動時点までで `run_folder` が空のため、比較ツールは部分結果を出して終了コード2を返した。レンダラ名の根拠は保存した実ログ。

## 4. 点群の参考照合

両試行のプローブ出力に LiDAR・camera1・camera2 各8フレームが記録された。保存済みのフレームから、既存ツールの `load_poses` と `compare_sensor` を使い、ミッション開始前の同時刻・許容姿勢の規則で補足照合した。3センサーとも点群と真値姿勢の時刻は 0.100 sim秒、両試行の位置差・角度差は0。有限レイは全て対応し、片方だけ有限なレイは0。XYZ 配列は全センサーで完全一致しなかった。

| センサー | 対になった有限レイ | 符号付き距離差の中央値 m | 絶対距離差の中央値 m | 絶対距離差の95%値 m | 絶対距離差の最大 m |
| --- | ---: | ---: | ---: | ---: | ---: |
| LiDAR | 12,173 | 0.000309 | 0.018885 | 0.054969 | 0.123579 |
| camera1 | 10,554 | -0.000006 | 0.004086 | 0.023192 | 0.058230 |
| camera2 | 9,328 | 0.000031 | 0.004527 | 0.023019 | 0.056602 |

符号付き差は GPU 指定側から CPU 側を引いた値。これは CPU 試行と GPU を指定して llvmpipe にフォールバックした試行の参考値で、NVIDIA 描画の有無による点群差は測れていない。

## 5. 持ち帰った記録

- `summary.json`、`conditions.txt`、ホストとコンテナの `nvidia-smi`、`cpu/`・`gpu/` の manifest、`console.txt`、`probe.txt`。CPU の `probe_exit.txt` は0。GPU 指定側もプローブログにフレーム数が残るものの、試行停止がプローブの終了コードを書き出す前だったため、その `probe_exit.txt` は生成されなかった。
- `gpu/ogre2_live.log`、`gpu/egl_diagnostics.txt`、`host_egl_diagnostics.txt`、`fallback_cloud_comparison.json`、セッションの停止証跡を添付。
- 点群 NPZ、走行の生記録、GPU 使用率の全時系列は研究 PC の `~/thesis_checks/gpu_rendering_054/` に保存。パスと SHA-256 は `not_committed.txt`。

## 6. テスト

計測停止後に、同じコミットの追跡ファイルだけを一時展開し、研究 PC の `thesis-python` venv で全46本を実行してすべて合格した。コマンドは各モジュールの `python -m tests.<モジュール名>`。出力全文と終了コードは `tests/`。このオフラインテストでは NVIDIA EGL 描画そのものは検証していない。
