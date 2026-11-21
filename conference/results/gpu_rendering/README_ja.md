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
