# 指示書 054：研究 PC で、GPU でセンサーを描けるか・1.0 倍が出るかを確かめる（045 の初回確認）

> **状態：実行中（2026-11-23 に再確認を研究 PC（チャット：研究PC実行）へ依頼。057 の集計のあとに行う）**。実行は**研究 PC の担当**（Mac の Codex から `ssh hayashi`）。コードは変えない。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/tasks/045_gpu_rendering.md`（あれば）、
> `conference/results/gpu_rendering/README_ja.md`（**手順の正本**）・`REPORT_ja.md`・`REVIEW_ja.md`、`conference/results/rtf_compare/REVIEW_B_ja.md` を読むこと。
> 作業ツリー `~/thesis_Bunker_rtf`、ブランチ `claude/054-gpu-check`（`origin/realtime-map` から）。持ち帰る結果は `conference/results/gpu_check_054/`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 039 で、Gazebo を 1.0 倍に設定しても、実際は 0.585〜0.613 倍しか出なかった。地図の更新は間に合っていて、遅いのは Gazebo そのもの。
  LiDAR だけのとき（11/7）は 1 倍で動いたので、**深度カメラ 2 台を CPU（ソフトウェア描画）で描いていることが原因の第一候補**。そのため、比べる実験は 0.3 倍で走らせている（1 回 15〜30 分）。
- 045 で、`THESIS_RENDER=gpu` を付けると研究 PC の GPU（RTX 5060）で描くようにした（既定は CPU のまま）。クラウドには GPU がないので、まだ一度も試していない。
- 1.0 倍が出れば、これからの評価（052 の `overlap_goal`、050 の段階 B など）の待ち時間が大きく減る。

## やること
- `results/gpu_rendering/README_ja.md` の手順どおり、`run_smoke.sh` で `08OB88_-1417` の CPU と GPU を 1 回ずつ走らせる（fine、LiDAR＋深度カメラ 2 台、1.0 倍設定）。
- 確かめること：
  1. ホストとコンテナの両方で `nvidia-smi` に GPU が出るか。
  2. GPU 側で、Ogre2 が実際に NVIDIA のレンダラを選んだか（空欄・`llvmpipe` なら GPU で描けていない）。
  3. 実測の倍率（CPU・GPU、その比）と GPU の使用率。
  4. CPU と GPU で、センサーの点群が同じか（距離の差）。
- 別の Gazebo の走行がないときに行う（050 の走行と集計が終わってから）。

## 守ること・やらないこと
- コードを変えない。**研究 PC に何かを入れる・設定を変える必要が出たら（NVIDIA の Docker 用の道具など）、入れずにそこで止め、何が足りないかを報告する**（利用者の確認が要る）。
- 1 組だけの初回確認として扱う。倍率や点群の一致を、ほかの条件へ広げて書かない。
- 既存の結果は上書きしない。認証情報は記録しない。

## Mac の Claude に持ち帰る報告（`results/gpu_check_054/REPORT_ja.md` にも書く）
1. コミット ID、push（Mac を経由）、実行したコマンド。
2. `summary.json`、両方の manifest、`conditions.txt`、`console.txt`、`probe.txt`・`probe_exit.txt`（README の持ち帰るもの）。点群の NPZ と生の記録は研究 PC に置き、パスと SHA-256 を残す。
3. 上の 1〜4 の結果。
4. 止まった場合は、どこで止まったか・何が足りないか。

## 再確認（2026-11-23 に追加。056 の直しのあと）
- 056 で、`THESIS_RENDER=gpu` のときだけ、ホストの `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` を読み取り専用でコンテナに見せ、`__EGL_VENDOR_LIBRARY_FILENAMES` で指すようにした（利用者が了承済み）。
  描画の判定（`gpu_rendered`）と、片方が止まったときの `summary.json` も直した。
- 057 の走行と集計が終わってから、`results/gpu_rendering/README_ja.md` の手順で、`run_smoke.sh` をもう一度走らせる（出力先は新しく `$HOME/thesis_checks/gpu_rendering_054b`）。結果は `conference/results/gpu_check_054/retry/` に持ち帰る。
- **GPU で描けなかった場合だけ**：代わりの道を見積もるため、LiDAR だけ（`--sensors lidar_real`、カメラなし）・1.0 倍設定・CPU 描画で、同じ砂浜（`08OB88_-1417`）を 1 回走らせ、実測の倍率を測る（11/7 に LiDAR だけで 1 倍が出た確認の、今のコミットでのやり直し）。
- 研究 PC に何かを入れる・設定を変える必要が出たら、入れずに止めて報告する。
