# 045 研究 PC での初回確認

044 の走行が終わってから、研究 PC「hayashi」の `tmux` で実施する。045 を含むコミットと `thesis/jazzy-gz:1` のイメージを揃え、別の Gazebo 走行がないときに1組だけ測る。準備は [研究 PC の手順](../../RESEARCH_PC_ja.md) を参照。

```bash
cd /home/kotaro/thesis_Bunker/conference
mkdir -p "$HOME/thesis_checks"
bash results/gpu_rendering/run_smoke.sh "$HOME/thesis_checks/gpu_rendering_045" \
    "$HOME/.venvs/thesis-python/bin/python"
```

1. スクリプトはホストとコンテナの `nvidia-smi` を実行する。両方に RTX 5060 が出ることを確かめる。Docker が GPU を渡せないときは、`container_nvidia_smi.txt` に出力を残して走行前に止まる。
2. `08OB88_-1417` で `THESIS_RENDER=cpu` と `gpu` を順に1回ずつ実行する。どちらも fine、LiDAR と深度カメラ2台、1.0倍設定、点群の古さ1.0 sim秒、同じ地形・地点。GPU側の manifest の `rendering` に要求した描画方式が入り、選択したケースの `rendering.renderer` に Gazebo の Ogre2 が記録した実際の OpenGL レンダラ名が入る。NVIDIA が選ばれたことを確認する。空欄や `llvmpipe` は GPU 動作の確認未了として、ケースの `ogre2.log` と `process_0.txt` を保存する。
3. `summary.json` に走行中の実測倍率（ミッションの sim 秒 ÷ 実秒）、GPU/CPU の実測倍率の比、GPU 使用率の中央値・最大値を出す。使用率は起動・ビルドを含むラッパー実行全体の約1実秒ごとの標本で、GPU ごとの時系列は `gpu_usage.csv` に残す。
4. 既存の ROS トピックから、LiDAR・camera1・camera2 の最初の8フレームを各走行で受動取得する。各センサーについて、両走行でミッション開始より前の最初の共通点群時刻を探す。点群時刻の30 ms以内で両走行に共通する真値姿勢時刻があり、姿勢の差が1 mm・0.1°以内の組を採用する。比較に使った時刻・姿勢差も出力する。
5. 元の配列形状とフレーム名が揃った点群で同じレイ位置を比較する。スロット数、有限な XYZ の数、片方だけ有限な数、両方有効なレイのセンサー原点からの距離差（GPU−CPU の最小・5%値・中央値・95%値・最大と、絶対差の中央値・95%値・最大）を記録する。`xyz_array_equal` は XYZ 配列の一致で、RGB・強度などの判定は含まない。姿勢の組や配列の対応が取れないときは `clouds` に理由を記録し、距離差の数値は出さない。

`summary.json`、両 manifest、`conditions.txt`、`console.txt`、`probe.txt`、`probe_exit.txt` を持ち帰る。点群の NPZ と走行の生記録は研究 PC に置き、必要なファイルのパスと SHA-256 を残す。比較だけやり直すときは `cloud_pair.py compare <出力先>` を venv で実行する。1組の結果は初回確認として扱い、倍率やセンサーの一致を広い条件へ外挿しない。

## 056 での再確認

054では両方の `nvidia-smi` がRTX 5060を認識した。CPU試行の実測は0.613倍で、GPU指定側のOgre2は `GL_VENDOR = Mesa`、`GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)` だったため試行を停止した。GPU指定側では `libEGL_nvidia.so.0` が見えていたが、EGLのベンダー定義は `50_mesa.json` だけだった。NVIDIA描画での倍率と点群差は未測定。 [054の報告](../gpu_check_054/REPORT_ja.md) · [コンテナのEGL診断](../gpu_check_054/gpu/egl_diagnostics.txt)

056では `THESIS_RENDER=gpu` の場合だけ、ホストの `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` をコンテナの同じ場所へ読み取り専用でマウントし、`__EGL_VENDOR_LIBRARY_FILENAMES` で指定する。ファイルがなければGPUの走行起動前にエラーを出す。manifest の `rendering.egl_vendor_file` と、選択ケースの `rendering.gl_vendor`・`gl_renderer`・`gpu_rendered` を確認する。 `true` はNVIDIAのGLベンダーとレンダラがそろった場合、`false` はMesaなどのソフトウェア描画を示す。 `null` は描画を確認できる記録が不足している。ヘッドレス起動と実測の手順には引き続き `run_smoke.sh` を使う。

実測倍率と点群差をNVIDIA描画の結果に使う条件は、GPU側の `gpu_rendered` が `true` であること。

057の走行後に研究PCのtmux内で、056を含むコミットと既存のイメージで再確認する。054と同じ砂浜・機材・倍率で、保存先は新しくする。

```bash
cd ~/thesis_Bunker_rtf/conference
mkdir -p "$HOME/thesis_checks"
out="$HOME/thesis_checks/gpu_rendering_056"
py="$HOME/.venvs/thesis-python/bin/python"
bash results/gpu_rendering/run_smoke.sh "$out" "$py"
```

途中で停止したときは、比較コマンドから別名のJSONを作成できる。停止理由と残った走行の実測は残り、比較できない倍率・点群の統計は空欄になる。終了コード2は部分結果を示す。

```bash
"$py" results/gpu_rendering/cloud_pair.py compare "$out" > "$out/summary_after_stop.json"
```
