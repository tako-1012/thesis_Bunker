# GPU 描画の短い確認（段階3の数に含めない）
どちらも R2 の条件で 130 秒で打ち切った。

| 回 | Docker の指定 | コンテナ内の /dev/dri | NVIDIA の EGL 登録 | GPU メモリ | GPU 使用率の最大 |
|---|---|---|---|---|---|
| `gpu_smoke1_no_render_device` | `--gpus all` | なし | なし | 15 MiB（Xorg だけ） | 0% |
| `gpu_smoke` | `--device nvidia.com/gpu=all`（CDI） | あり | あり（10_nvidia.json） | 134 MiB（`world.sdf` のプロセス） | 1% |

- `--gpus all` では描画が GPU に載らず、実質ソフトウェア描画だった。R2 と呼べないため、CDI の指定に直した。
- 直したのは `divergence/run_one.sh` の R2 の Docker 引数だけ。`/var/run/cdi/nvidia.yaml` は既存のもので、システムの設定は変えていない。
- 2 回目の実測倍率は 0.9999。ただし GPU の使用率は 1% と小さく、GPU 描画で処理の余裕が増えたとはこの確認からは言えない。
