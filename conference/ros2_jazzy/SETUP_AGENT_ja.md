# Ubuntu 24.04 の環境構築（コーディングエージェント向けの指示書）

この文書は、**Ubuntu 24.04 のパソコンで動く Claude Code や Codex** が読んで、このリポジトリの
ROS2 Jazzy ＋ Gazebo Harmonic の環境を作り、動くことを確かめるためのものです。
人が読んでも同じ手順で進められます。詳しい説明は `conference/ros2_jazzy/README_ja.md` にあります。

## 守ること
- **リポジトリのファイルを変更しない・コミットしない・push しない。** この作業は環境を作って確かめるだけです。
  手順書に誤りを見つけたら、直さずに最後の報告に書くこと。
  `colcon build` が作る `build/`・`install/`・`log/` は `.gitignore` に入っているので、作ってよい。
- `ros2/`（研究室のリポジトリから来たもの）には触らない。研究室のリポジトリ（`hayashilab/...`）には何もしない。
- `sudo` が必要なコマンドは、**利用者（人）に確認してから**実行する。パスワードの入力が必要なら、利用者に実行してもらう。
- 各段階の「確かめること」が満たされなければ、先に進まずに止まり、出力をそのまま報告する。結果を推測で埋めないこと。
- ネットワークは大学の Wi-Fi などでもよい。`apt` や `git` がつながらない場合は、そのエラーを報告する。

## 0. 今の状態を調べる（変更なし）
```bash
lsb_release -ds          # Ubuntu 24.04 であること
uname -m                 # x86_64 または aarch64
df -h ~                  # 空きが 15GB 以上あること
nvidia-smi || true       # GPU（なくてもよい。あれば画面の表示が速い）
ls /opt/ros 2>/dev/null; which gz ros2 2>/dev/null   # すでに ROS2・Gazebo が入っているか
```
- すでに `/opt/ros/jazzy` があれば、1 の ROS2 のインストールは飛ばしてよい。**Humble など別の版しかない場合は、利用者に確認する**（Jazzy を追加で入れる）。
- Unity などほかのソフトが入っていても、そのままにしておく。

## 1. ROS2 Jazzy と Gazebo Harmonic を入れる（sudo が必要）
ROS 公式の手順（https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html ）に従う。標準的な形：
```bash
sudo apt update
sudo apt install -y locales software-properties-common curl git
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
sudo add-apt-repository -y universe
ROS_APT_SOURCE_VERSION=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
curl -fL -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.noble_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt install -y ros-jazzy-desktop ros-jazzy-ros-gz python3-colcon-common-extensions
```
Python のライブラリは、**ROS2・Gazebo 用（apt）と、テスト・Web 画面用（venv）を分ける**。
Ubuntu 24.04 の apt の版（NumPy 1.26、Pydantic 1）では、テストと Web 画面が動かないため。
```bash
# ROS2・Gazebo の確認スクリプト用（システムの python3）
sudo apt install -y python3-numpy python3-scipy python3-matplotlib python3-pandas python3.12-venv
```
テスト・Web 画面用の venv は、2 でリポジトリを取ってきたあとに作る（版は `conference/requirements-venv.txt` で固定）：
```bash
python3 -m venv ~/.venvs/thesis-python
~/.venvs/thesis-python/bin/python -m pip install -r ~/thesis_Bunker/conference/requirements-venv.txt
```
**venv は、3 のテストと 6 の Web 画面のときだけ有効にする。4・5（colcon・Gazebo）は venv を有効にしないターミナルで行う**
（ROS2 はシステムの python3 に合わせて作られているため）。

**確かめること**
```bash
source /opt/ros/jazzy/setup.bash
echo $ROS_DISTRO                      # jazzy
gz sim --versions                     # 8.x（Harmonic）
python3 -c "import numpy, scipy, matplotlib, pandas; print('ok')"   # システム側（apt）
timeout 30 gz sim -s -r --iterations 2000 shapes.sdf; echo "exit=$?"   # 画面なしで Gazebo が動くこと（exit=0）
```

## 2. リポジトリを取ってくる
置き場所は利用者に確認する（決まっていなければ `~/thesis_Bunker`）。すでにあれば `git pull` だけにする。
```bash
git clone https://github.com/tako-1012/thesis_Bunker.git ~/thesis_Bunker   # 非公開なら、利用者の GitHub の認証が必要
cd ~/thesis_Bunker && git checkout main && git pull
```

## 3. Python のテスト（ROS2・Gazebo なしで動く。10〜20 分）
```bash
source ~/.venvs/thesis-python/bin/activate     # テストは venv で
cd ~/thesis_Bunker/conference
for t in $(ls tests/test_*.py | sed 's#tests/##;s#\.py##'); do python3 -m tests.$t > /tmp/$t.log 2>&1; echo "$t exit=$?"; done
```
**確かめること**：すべて `exit=0`（2026年10月時点で 14 個）。落ちたものは、その `.log` の最後の 30 行を報告する。
終わったら `deactivate` で venv を抜ける（または新しいターミナルを開く）。

## 4. ROS2 のパッケージを作る
```bash
cd ~/thesis_Bunker/conference/ros2_jazzy
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 pkg list | grep thesis_bunker     # thesis_bunker_gz と thesis_bunker_mission
```

## 5. 画面なしで Gazebo の確認を一通り走らせる（30〜60 分）
クラウドでは Docker の中で走らせた確認を、この Ubuntu で**直接**走らせる。
```bash
cd ~/thesis_Bunker/conference
source /opt/ros/jazzy/setup.bash && source ros2_jazzy/install/setup.bash
export PYTHONPATH=$PWD:$PYTHONPATH THESIS_CONFERENCE_DIR=$PWD ROS_DOMAIN_ID=47
mkdir -p ~/thesis_checks
python3 ros2_jazzy/gz_checks/checks.py --output ~/thesis_checks/basic
python3 ros2_jazzy/gz_checks/online_checks.py --output ~/thesis_checks/online
```
**確かめること**：`~/thesis_checks/basic/results.json` の `errors` が空で `failed` が false、`~/thesis_checks/online/results.json` の `errors` が空。
クラウドの Docker で走らせたときの値（`conference/ros2_jazzy/gz_checks/results/claude_docker_run_las/README_ja.md` と
`conference/results/online_mission/gazebo_claude/README_ja.md`）と並べて報告する。目安：
- 平地・前の砂浜・点群の砂浜とも、巡回 5 点を完走し、通れない場所に触れたマスは 0。
- 前進は指令の約 99%、その場旋回は約 89%。
- 漂着物ありの砂浜で、計画し直さない（`fixed`）は立ち往生、計画し直す（`online`）は完走。
値が大きく違っても（パソコンの速さで変わる値もある）、直さずにそのまま報告する。

## 6. 画面ありで動かす（利用者が見て確かめる）
ターミナルを 2 つ使う。

ターミナル 1（Web 画面のサーバー。この Ubuntu の中で動かすので、大学の Wi-Fi でも問題ない。**venv を使う**）：
```bash
source ~/.venvs/thesis-python/bin/activate
cd ~/thesis_Bunker/conference
python3 -m webui.server --host 127.0.0.1 --port 8080
```
ターミナル 2（Gazebo と BUNKER。**venv は使わない**）：
```bash
cd ~/thesis_Bunker/conference/ros2_jazzy
source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch thesis_bunker_gz sim.launch.py map:=flat_test_100m webui:=http://localhost:8080
```
利用者に次をお願いする：
1. Gazebo の画面に、平らな地面・箱 3 つ・BUNKER（箱の形）が出る。
2. ブラウザ（Chrome）で `http://localhost:8080` を開き、地図「`flat_test_100m.npz`」を選ぶ。地点を 3〜5 個置いて「経路を計画」→「ロボットに送る」。
3. Gazebo の BUNKER が経路どおりに走り、Web 画面に紫のマーカーと軌跡が出る。
4. 止めるのは、それぞれのターミナルで Ctrl+C。

余裕があれば、走りながら計画し直す版も見てもらう（ターミナル 2 を止めてから）：
```bash
ros2 launch thesis_bunker_gz sim.launch.py map:=real_las_08OB87_-0206_200m_0_debris online:=true \
  prior_map:=real_las_08OB87_-0206_200m_0.npz sense_radius_m:=10.0 webui:=http://localhost:8080
```
Web 画面では地図「`real_las_08OB87_-0206_200m_0_debris.npz`」を選んで、同じように送る。
200m の地図で、Gazebo が重い場合がある（その場合は報告する）。

## 7. 報告（日本語で、利用者に）
次の形でまとめる。利用者は、この報告をクラウドの Claude に貼って続きを相談する。
1. パソコンの情報（0 の出力：Ubuntu の版、CPU の種類、GPU、空き容量）
2. 入れたもの（ROS2 Jazzy・Gazebo の版、すでに入っていたもの）
3. 3 のテストの結果（14 個それぞれの exit）
4. 4 の colcon build の結果
5. 5 の `results.json` の主な値（errors、各 world の完走・接触、前進・旋回の比、online と fixed の結果）と、クラウドの値との違い
6. 6 で利用者が見たこと（画面が出たか、走ったか、重さ）
7. うまくいかなかったこと、手順書の誤りや分かりにくかったところ（直さずに書く）

## 確認の記録
- 2026-10-31：利用者の Ubuntu 24.04（Intel Core Ultra 7 255HX、Gazebo 8.15.0、venv は `requirements-venv.txt` の版）で手順1〜5を実行した。
  - colcon build：成功
  - 画面なしの Gazebo の確認：`errors` は空。巡回は全 world で完走し、接触は 0（平地 249 秒、前の砂浜 348 秒、点群の砂浜 289 秒）。
    前進 99.2%、旋回 89.2%。古い地図では、計画し直さないと 94.5 秒で立ち往生し、計画し直すと 192 秒で完走した。
    クラウドの Docker の結果とほぼ同じ。
  - テスト：14 個中 13 個が通った。`test_online_mission` は、保存した地図との比べ方が CPU によって最後の桁で変わるため落ちていた
    （AVX-512 のない CPU。標高の差 8.9e-16m、コストの差 3.9e-9。通れない場所と漂着物は完全に一致）。
    通れない場所などの判定は完全一致のまま、標高とコストだけごくわずかな誤差を許すよう、テストを直した。
