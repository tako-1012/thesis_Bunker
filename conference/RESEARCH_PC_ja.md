# 研究 PC「hayashi」での実験の進め方（Claude Code・Codex 向け）

重い比較実験・学習・Gazebo のシミュレーションは、研究 PC「hayashi」が使えるときは**この PC で優先して実行する**。
（クラウドの Docker で Gazebo を走らせると、CPU の描画のため実時間の 0.3 倍まで落とす必要があった。022・023 を参照。）
この文書は利用者が確認した情報（2026-11-07 時点。同日、Mac からの公開鍵認証を設定）。変わったら更新すること。

## 研究 PC の位置づけ
- 研究 PC は**重い処理の実行先**であり、Claude の作業場所を全面的に移すものではない。役割分担は `CLAUDE.md` を参照
  （窓口は Mac の Claude デスクトップアプリ、実装は主に Codex、依頼文と報告の受け渡しは利用者が手で行う）。
- 研究 PC で行うこと：シミュレーション（Gazebo）・GPU の学習・重い評価。必要なら研究 PC の上で Claude Code や Codex を起動し、
  動作の確認・実験の実行・その場での修正に使う。その場で直したコードは、作業用のブランチにコミットして push し、報告に含める。
- 研究 PC の上のエージェントに頼むときも、依頼文には実行先・対象・目的と完了の条件・環境と確かめ方・持ち帰る報告を書く（`CLAUDE.md` の「依頼文の書き方」）。

## 接続
- Mac からは **`ssh hayashi`**（公開鍵認証、2026-11-07 に設定済み）。Mac の `~/.ssh/config` の別名で、実体は `kotaro@100.86.47.99`（Tailscale 経由）。
  同じ LAN と、Mac のテザリング（別の回線）の両方で接続を確認済み。
- 別名のない端末からは `ssh kotaro@100.86.47.99`（その端末に鍵がなければパスワードの入力が必要。パスワード・秘密鍵はリポジトリに書かない。エージェントは聞き出さない）。
- つながらないときは、原因を区別して報告する：
  - `Permission denied (password/publickey)` など → **認証の誤り**（PC は動いている）
  - `Connection timed out`／`No route to host` → **PC の停止、Tailscale が切れている、ネットワーク不通**
  - `Connection refused` → PC には届いたが SSH が動いていない、または**この実行環境が Tailscale に入っていない**
- **クラウドの Claude Code のセッション（claude.ai/code）からは、この PC に届かない**（2026-11-07 に確認。Tailscale の外のため `Connection refused`）。
  クラウドのセッションは、実行の手順を書いて利用者に渡すか、研究 PC の上で動く Claude Code・Codex に頼む。

## 研究 PC
- Ubuntu 24.04.4 LTS、Core Ultra 7 255HX、RAM 約 16GB
- RTX 5060 Laptop GPU（VRAM 約 8GB）
- ROS 2 Jazzy、Gazebo Sim 8.15.0（画面を出すときは `gui_render_engine:=ogre`。`ros2_jazzy/SETUP_AGENT_ja.md` を参照）
- tmux あり。SSH を切っても処理が続くことを確認済み。

## プロジェクトと環境
| 用途 | 場所 |
|---|---|
| 経路計画（このリポジトリ） | `/home/kotaro/thesis_Bunker` |
| 強化学習（別のリポジトリ） | `/home/kotaro/master_thesis/terrain-tour-rl` |
| GPU 用の venv | `/home/kotaro/.venvs/terrain-tour-gpu-cu132`（PyTorch 2.13.0+cu132、CUDA runtime 13.2） |

- このリポジトリのテストと Web 画面は、`ros2_jazzy/SETUP_AGENT_ja.md` の venv（`conference/requirements-venv.txt` の版）を使う。
- ROS・Gazebo を動かすときは、そのプロジェクトが指定する環境を使う（このリポジトリでは `source /opt/ros/jazzy/setup.bash` と apt の Python。venv と混ぜない）。

## 確認済みのこと
- GPU での行列の積・逆伝播、研究プロジェクトの小さな GPU の推論
- 画面なしの Gazebo の時刻の進み、ROS–Gazebo の橋渡し、姿勢・IMU の受信、速度の指令による移動
- **まだ確かめていないこと**：長い時間の安定性、研究のミッション全体（022・023 のような 10 か所の LiDAR の走行など）。
  最初に走らせるときは、クラウドの Docker の結果（`results/gazebo_lidar/physical_10/`・`results/lidar_fine/physical_10/`）と 1〜3 か所で比べて、同じ動きになるか確かめる。

## 実験を走らせるときの決まり
1. **始める前に確認して記録する**：実行するコミット（`git rev-parse HEAD`）、まだコミットしていない変更（`git status --short`）、
   依存の環境（venv の `pip freeze`、`nvidia-smi`、`gz sim --versions`）。
2. **長い処理は tmux の中で動かす**（例：`tmux new -s <実験名>`、離れるときは `Ctrl-b d`、戻るときは `tmux attach -t <実験名>`）。
3. **実験ごとに保存先を分ける**：条件・乱数のシード・コミット ID・ログ・結果（学習ではチェックポイントも）を同じフォルダに残す
   （このリポジトリでは `conference/results/<タスク名>/`。既存の保存先・既存の環境は上書きしない）。
4. **GPU が使える処理は GPU を使う**。
5. エージェントのサンドボックスの中で GPU や通信が制限されるときは、通常の Ubuntu の端末か SSH の先で動かす方法を使う。
6. 秘密鍵・パスワードなどの認証情報は、ログ・結果・文書に記録しない。
7. **PC が使えない場合**（停止・ネットワーク不通・認証の誤り）は、その状況を報告し、代わりの実行先（クラウドの Docker など）を利用者と相談する。
   黙ってクラウドに切り替えない。

## 次回からの手順（例：Gazebo の LiDAR の 10 か所）
```bash
ssh hayashi                             # Mac から（公開鍵認証）
tmux new -s lidar_fine10
cd /home/kotaro/thesis_Bunker && git fetch origin && git checkout realtime-map && git pull
git rev-parse HEAD; git status --short   # 記録する
cd conference
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/<新しい保存先> --patch-count 10 --map fine
# Ctrl-b d で離れる。あとで tmux attach -t lidar_fine10
```
- `run_lidar_checks.sh` は Docker（`thesis/jazzy-gz:1`）を使う。研究 PC の上で直接 ROS・Gazebo を使う形に替えるかどうかは、
  最初の比較（上の「まだ確かめていないこと」）のあとで決める。GPU で描画できれば、実時間の 0.3 倍に落とす必要はなくなるかもしれない。
