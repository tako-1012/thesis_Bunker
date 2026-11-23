# 054 のレビュー（Claude、2026-11-23、取り込む前）

対象：`claude/054-gpu-check`（`5200ea8`）。コードの変更はなく、`results/gpu_check_054/` だけ。

## 結論
- **取り込んでよい。GPU での描画は、まだ確かめられていない（保留）。**
  - CPU の実測の倍率は 0.613 倍（1.0 倍の設定）で、039 と同じ。
  - GPU を指定した側も、Ogre2 の記録は `GL_VENDOR = Mesa`（ソフトウェア描画）だった。
- **原因の見立て**
  - ホストには `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` がある。コンテナの中には NVIDIA の EGL のライブラリ（`libEGL_nvidia.so.0`）がある。
  - ところが、コンテナから見える EGL の定義は Mesa のものだけで、EGL が NVIDIA を選べない。`NVIDIA_DRIVER_CAPABILITIES=all` を渡していても、この定義のファイルは入っていない。
- **直し方の案**（どちらも研究 PC に何かを入れるのではなく、`run_lidar_checks.sh` の `THESIS_RENDER=gpu` のときの起動の引数を足すだけ）
  1. ホストの定義のファイルを、読み取り専用でコンテナに見せる（`-v /usr/share/glvnd/egl_vendor.d/10_nvidia.json:/usr/share/glvnd/egl_vendor.d/10_nvidia.json:ro`）。
  2. `__EGL_VENDOR_LIBRARY_FILENAMES` でそのファイルを指す。
  - 研究 PC で走らせる前に、利用者の確認をもらう。
- 小さな不具合：GPU 側が途中で止まったため、`summary.json` の GPU の欄が `unsupported operand type(s) for /: 'PosixPath' and 'NoneType'` になっている（集計のスクリプトが、止まった走行を想定していない）。結論には影響しない。

## 確かめたこと
- 差分：`results/gpu_check_054/` だけ。
- `gpu/ogre2_live.log` の `GL_VENDOR = Mesa`、`host_egl_diagnostics.txt`・`gpu/egl_diagnostics.txt` の中身を読み、報告と一致。
- テスト：取り込んだ状態で全 47 本が exit=0。
