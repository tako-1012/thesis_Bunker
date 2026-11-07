# 研究 PC「hayashi」の使い方（重い実験の実行先）

重い比較実験・学習・Gazebo のシミュレーションは、研究 PC「hayashi」が使えるときは、**このPC で優先して実行する**。
クラウドのセッションや Codex のサンドボックスは、GPU・Docker・ネットワークが制限されることがあるため。
2026-11-07 時点の情報（利用者が確認したもの）。

## 接続
- SSH：利用者の Mac からは `ssh hayashi` で、**公開鍵認証**で接続できる（2026-11-07 に設定済み）。
  - 中身は `kotaro@100.86.47.99`（Tailscale 経由）。`hayashi` は Mac の SSH の設定に書いた別名で、ほかのマシンでは使えない。
  - 同じ LAN と、Mac をテザリングに切り替えた別の回線の両方で、接続を確認済み。
  - 鍵が登録されていないマシンからは、今までどおりパスワードが必要。
  - パスワードや秘密鍵は、リポジトリ・ログ・チャットに書かない。
- 接続できないときは、原因を分けて報告する：
  - 認証エラー（`Permission denied` など）：PC は動いている。パスワード・ユーザー名・鍵の問題。
  - タイムアウト・`No route to host`・`tailscale ping` に応答なし：PC の停止、スリープ、Tailscale の切断、ネットワークの不通。
- **クラウドの Claude のセッションからは、直接 SSH できない**（コンテナに Tailscale がなく、Mac の鍵もないため）。
  クラウドから使うときは、次のどちらかにする：
  1. 利用者が Mac から `ssh hayashi` で入り、tmux の中でコマンドを実行する（Claude は実行するコマンドを、そのまま貼れる形で示す）。
  2. 研究 PC で Remote Control を有効にして（例：`/home/kotaro/thesis_Bunker` で `claude remote-control`）、
     クラウドのセッションをそのフォルダにつなぐ。

## 研究 PC の構成
| 項目 | 内容 |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| CPU・メモリ | Core Ultra 7 255HX、RAM 約 16GB |
| GPU | RTX 5060 Laptop GPU、VRAM 約 8GB |
| ROS・Gazebo | ROS 2 Jazzy、Gazebo Sim 8.15.0 |
| その他 | tmux あり（SSH を切っても処理が続くことを確認済み） |

## プロジェクトと環境
| 用途 | 場所 |
|---|---|
| 経路計画（このリポジトリ） | `/home/kotaro/thesis_Bunker` |
| 強化学習 | `/home/kotaro/master_thesis/terrain-tour-rl` |
| GPU 用の venv | `/home/kotaro/.venvs/terrain-tour-gpu-cu132`（PyTorch 2.13.0+cu132、CUDA runtime 13.2） |

- ROS を使うときは、そのプロジェクトが決めている環境（`setup.bash` の読み込みや Docker のイメージなど）を使う。
  このリポジトリの Gazebo の確認は `conference/ros2_jazzy/` の手順（`gz_checks/*.sh`）に従う。

## 確認済みのこと
- GPU での行列積と逆伝播
- 研究のプロジェクトの小さな GPU 推論
- 画面なしの Gazebo で、時刻が進むこと
- ROS と Gazebo のブリッジ、姿勢・IMU の受信、速度の指令でロボットが動くこと

**まだ確かめていないこと**：長時間の安定性と、研究のミッション全体の実行。初めて長い実験を回すときは、
まず短い条件で動くことを確かめてから広げる。

## 実験を始める前
1. 実行するコミットを確かめる：`git -C /home/kotaro/thesis_Bunker fetch && git -C /home/kotaro/thesis_Bunker status && git -C /home/kotaro/thesis_Bunker log -1 --oneline`
   - 未コミットの変更があれば、何かを確かめてから始める（勝手に消さない）。
2. 依存の環境を確かめる（Python・venv・ROS・Docker のイメージ、GPU：`nvidia-smi`）。
3. GPU が使える処理（学習・推論、GPU の LiDAR の描画など）では GPU を使う。

## 実験の実行と記録
- 長い処理は tmux の中で実行する。例：
  ```bash
  tmux new -s exp_<タスク名>
  # 実験を実行する
  # Ctrl-b d で抜ける。tmux attach -t exp_<タスク名> で戻る
  ```
- 実験ごとに保存先を分け（このリポジトリなら `conference/results/<タスク名>/`）、次を残す：
  実験の条件、コミット ID、未コミットの変更の有無、使った環境（venv・イメージ・GPU）、ログ、結果。
- `AGENTS.md` の研究の信頼性の決まり（値を作らない、テスト用のシードで調整しない、など）は、研究 PC でも同じ。

## 研究 PC が使えないとき
状況（認証エラーか、PC・ネットワークの問題か）を報告し、代わりの実行先（クラウドの Docker、Codex の環境など）を利用者と相談する。
黙って別の場所で実行したり、実行していない結果を書いたりしない。
