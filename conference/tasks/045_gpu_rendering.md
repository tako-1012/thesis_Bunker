# 指示書 045：研究 PC の GPU で Gazebo のセンサーを描けるようにする（準備）

> **状態：完了（準備。研究 PC での確認は 044 のあと。結果は `results/gpu_rendering/`、レビューは `REVIEW_ja.md`）**。実装は **クラウドの Codex**。クラウドには GPU がないので、**作るところまで**。研究 PC での確認は 044 のあとに別に行う。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/ros2_jazzy/gz_checks/run_lidar_checks.sh`・`lidar_checks.py`・`terrain_mesh.py`、
> `conference/ros2_jazzy/SETUP_AGENT_ja.md`、`conference/results/rtf_compare/REPORT_B_ja.md`・`REVIEW_B_ja.md`（039）を読むこと。
> ブランチは `codex/045-gpu-rendering`（その時点の `realtime-map` の最新から）。結果は `conference/results/gpu_rendering/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- Gazebo の走行は Docker（`thesis/jazzy-gz:1`）で、`LIBGL_ALWAYS_SOFTWARE=1`（CPU で描く）で動かしている。研究 PC には RTX 5060（ドライバ 595.99.02、CUDA 13.2）があるが使っていない。
- 039 で、実機と同じセンサー（LiDAR＋深度カメラ 2 台）では、1.0 倍に設定しても実測 0.6 倍だった。地図の更新は追いついており、**遅いのは Gazebo**。
  2026-11-07 の確認（LiDAR だけ）では 1 倍で動いたので、**深度カメラの描画を CPU で行っていること**が原因の第一候補。
- `terrain_mesh.py` のとおり、ogre2 の GPU LiDAR は見た目（visual）を描くので、地形をメッシュにしている（heightmap の visual は GPU なしで落ちるため）。

## 作るもの（選んだときだけ働く。既定は今までどおり CPU）
1. `run_lidar_checks.sh` に、GPU で描く選択（例：環境変数 `THESIS_RENDER=gpu`、既定 `cpu`）を足す。`gpu` のとき：
   - Docker に GPU を渡す（`--gpus all`、`NVIDIA_DRIVER_CAPABILITIES=all` など。研究 PC に NVIDIA Container Toolkit があることが前提。なければ分かりやすい誤りで止まる）。
   - `LIBGL_ALWAYS_SOFTWARE` を外す。必要なら EGL で画面なしに GPU で描く設定（`gz sim` の `--render-engine ogre2` と、EGL を使う環境変数）を入れる。
   - manifest に、描画の方法（`cpu`/`gpu`）と、実際に使われた描画の情報（OpenGL のレンダラ名など、取れるもの）を記録する。
2. 研究 PC で最初に確かめるための**短い確認の手順とスクリプト**を `conference/results/gpu_rendering/` に置く：
   - コンテナの中で GPU が見えるか（`nvidia-smi`、OpenGL のレンダラ名）。
   - 1 か所・1 回だけ、LiDAR＋深度カメラ 2 台で、`cpu` と `gpu` をそれぞれ 1.0 倍設定で走らせ、実測の倍率と GPU の使用率を記録する。
   - **センサーの出力が CPU と GPU で同じとは限らない**ので、同じ姿勢で受け取った最初の点群（LiDAR・カメラ）を比べる手順（点の数、距離の差の分布）も入れる。
3. `conference/RESEARCH_PC_ja.md` に、GPU で描くための準備（NVIDIA Container Toolkit の確認など）を追記する。研究 PC で何かを入れる必要があるときは、**利用者の確認が要る**と書く（勝手に入れない）。

## 守ること・やらないこと
- 既定（`cpu`）の動きと manifest は、バイト単位で変えない。テストで示す（直す前のコードと同じ環境でその場で比べる）。
- 研究 PC での実行、研究 PC へのソフトの導入はしない（この指示書は準備だけ）。Docker のイメージを作り直す必要があるなら、その手順を書くだけにする。
- センサーの設定（解像度・周期・雑音）は変えない。

## テスト `conference/tests/test_gpu_rendering.py`（ROS2・Gazebo・GPU なしで動くこと）
1. 既定（`cpu`）の `run_lidar_checks.sh` が組み立てる `docker run` の引数と manifest が、直す前と同じ（引数を記録する偽の Docker を使う、039 と同じやり方）。
2. `gpu` のとき、`--gpus all` が付き、`LIBGL_ALWAYS_SOFTWARE` が付かず、manifest に描画の方法が記録される。
3. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 研究 PC で確かめる手順（044 が終わったあとに「研究PC実行」に頼む内容）。研究 PC で入れる必要がありそうなもの。
3. できなかったこと、自信がないこと。
