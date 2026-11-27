# 指示書 081：研究室のドローンの地図（ODM の点群）を取り込み、本物の地図での位置の決まりやすさを調べる

> **状態：実行中（段階 A：研究 PC、チャット：研究PC実行）**。段階 B はクラウドの Codex（チャット：研究実装1）で、段階 A を取り込んでから頼む。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/progress/policy.csv`、
> `conference/research/drone_sim_ja.md`（**研究室のドローンの地図の調べ。NAS の場所・レポートの数字**）、
> `conference/tasks/079_localizability_scan.md`・`conference/results/localizability_scan/REPORT_ja.md`・`REVIEW_ja.md`（同じやり方の見本）を読むこと。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 修論の範囲：ドローンが撮ったばかりの地図を正とし、その上で人が選んだ地点を効率よく回る。BUNKER には GNSS がなく、位置は LiDAR で積み上げ、ドローンの地図に重ねて直す予定。
- 079 で、静岡の LAS（0.5m のマス）の砂浜に仮の LiDAR のスキャンを重ねると、目印なしでは 69〜95% の地点で位置が決まりにくい（情報行列の最小の固有値が 076 の基準 1.0 以下）と予測した。
- 研究室の NAS に、**本物のドローンの地図**（OpenDroneMap、2024-04-24 撮影、約 33m × 42m、点群 4,354 万点、地上の画素 0.2cm、地図の中の正しさは mm 単位、地球上の位置は GPS だけで約 0.6m）があった（`drone_sim_ja.md`）。
- 細かい本物の地図なら、LAS では写らない凹凸まで写るので、**位置が決まりやすくなるのか**を確かめたい。
- 研究室のデータをリポジトリに入れること（間引いた小さな版）と、研究 PC の専用の venv（`conference/.venv-localization`）に `laspy`・`lazrs` を足すことは、11/27 に利用者が認めた。

## 段階 A（研究 PC、チャット：研究PC実行）：点群の小さな版を作る
- 元のファイル：利用者が `~/thesis_data/drone_odm/2024-04-24/` に置く（`odm_georeferenced_model.laz`・`coords.txt`・`proj.txt`・`odm_georeferenced_model.info.json`・`odm_orthophoto.tif`・`report.pdf`）。**元のファイルは変えない・消さない。** 各ファイルの sha256 を記録する。
- venv：`conference/.venv-localization` がなければ、078 の手順と同じく `python3.12 -m venv .venv-localization` で作り、`requirements_localization.txt` を入れる。足すのは `laspy` と `lazrs`（版を固定し、`requirements_drone_map.txt` に書く）。**ほかの venv・システムの Python・ROS・Docker には入れない。**
- 作るもの：`conference/experiments/drone_map_downsample.py` と、出力 `conference/data/drone_odm/2024-04-24/`。
  - 点群を **5cm の立方体の格子**で間引く（各格子の点の平均の位置、色があれば平均の色、点の数）。座標は `coords.txt`・`proj.txt` の基準（UTM 52N）を記録したうえで、**点群の最小の点を原点にした局所の座標（m）**で float32 に保存する（`npz`、圧縮）。
  - あわせて、**10cm のマスの標高の地図**（各マスの点の高さの最大・最小・中央値、点の数）を作る。
  - `README_ja.md` に、元のファイルの sha256、点の数、範囲、座標の基準、作り方を書く。
  - 出力の合計は 30MB 以内を目安にする。超えるなら止めて報告する（格子を 10cm にするなどは、利用者に確かめてから）。
- CPU を控えめにする：`nice -n 19` で、スレッド数は 2 まで。073・078 の走行中でも、それを止めたり遅くしたりしない。
- 研究 PC で作ったものを Mac を経由して push する（ブランチ `claude/081-drone-map`）。

## 段階 B（クラウド、チャット：研究実装1。段階 A のあとで別に頼む）
- 段階 A の小さな版を使い、079 と同じやり方で、場所ごと（1m おき）の仮の LiDAR のスキャンと、情報行列の最小の固有値・弱い向きを出す。
- 比べる相手：同じ大きさの範囲を、079 の LAS の砂浜（目印なし）から切り出したもの。
- 地図の範囲の端では、地図の外が見えないので、端からの距離ごとにも分けて示す。
- くわしくは、段階 A を取り込んだあとで、この指示書に書き足してから頼む。

## 守ること
- 元のデータは変えない・消さない。研究室のデータの扱いは、利用者が認めた範囲（間引いた小さな版をリポジトリに入れる）だけ。
- 既存のファイルの出力はバイト単位で変えない。

## Mac の Claude に持ち帰る報告（段階 A）
1. コミット ID、push、venv に足したものの一覧（`pip freeze` の差分）。
2. 元のファイルの sha256、点の数、範囲（局所の座標と UTM）、座標の基準。
3. 小さな版の大きさ、点の数、10cm の標高の地図の大きさと、穴（点のないマス）の割合。
4. できなかったこと、自信がないこと。
