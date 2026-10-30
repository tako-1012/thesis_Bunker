# 指示書 014：走りながら地図を更新して計画し直す部分を、ROS2・Gazebo に入れる

> **状態：未着手**。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
修論の柱は2つです。(1) 既にある地図の上で、人が選んだ複数の地点を効率よく回る。(2) 走りながら地図を更新して、経路を計画し直す。
(1) は Web 画面 → ROS2 → Gazebo の流れができました（指示書010〜012）。(2) は Python のシミュレーションの中だけにあり
（`tapp/online.py` の `run_online`）、地図の把握・再計画・移動が1つの関数にまとまっているので、ROS2 から使えません。
この指示書では、(2) を **ROS2 から1ステップずつ呼べる形**に作り直し、Gazebo の BUNKER で動かします。

### 決めたこと
- **センサー**：LiDAR などは模擬しない。**「ロボットのまわり半径 R の地形が見えた」とみなす**（`run_online` と同じ考え方）。
  見えた場所の値は、Gazebo の world を作ったのと同じ地図ファイル（＝本当の地形）から読む。この簡単化は README と報告に必ず書くこと。
- **「既にある地図」（事前の地図）の 3 種類**：
  | 名前 | 事前の地図 | 本当の地形 | 意味 |
  |---|---|---|---|
  | `oracle` | 本当の地形そのもの | — | 比べるための理想 |
  | `coarse c10` | 本当の地形を 10m でブロック平均したもの（`tapp.prior.coarse_prior`） | 漂着物なし | 粗い地図しかない（指示書009と同じ） |
  | `stale` | 漂着物のない地図 | 漂着物のある地図 | **地図が古く、そのあと漂着物が来た**（海岸清掃で一番ありそうな場面） |
  `stale` の本当の地形は `build_real(..., debris=True, dataset="shizuoka_beach_las")`、事前の地図は同じパッチの `debris=False`。
- 回る順番は、**出発の前に事前の地図で決める**（`tapp/tour.py`、指示書010の `terrain` と同じ）。走りながら変えるのは、各区間の経路だけ。

## 1. ROS2 に依存しない中身：新しいファイル `conference/tapp/online_mission.py`
```python
class OnlinePlanner:
    def __init__(self, prior_cost, prior_lethal, robot_weights, *, w=DEFAULT_W, prior_lethal_mode="soft",
                 unknown_cost="adaptive", replan_every_m=10.0, exact_los=True): ...
    def observe(self, mask, cost, lethal) -> np.ndarray      # 見えたマスの値を入れる。新しく見えたマスを返す
    def start_leg(self, pos_cell, goal_cell) -> dict           # 区間の最初の計画
    def update(self, pos_xy) -> dict                           # 今の位置で、計画し直すかを判断し、必要なら計画し直す
def virtual_sense(truth_tm, pos_cell, radius_m) -> (mask, cost, lethal)   # 半径 R のマスの本当の値
def run_online_mission(truth_tm, prior, start, waypoints, *, radius_m, step_m=1.0, **kw) -> dict
```
- 計画し直す規則（いつ、何で計画するか）は **`run_online` と同じにする**：新しく見えたマスが残りの経路の上で通れない、
  または想定より 0.05 以上コストが高いとき、または前の計画から `replan_every_m` 進んだとき。新しい計画を今の位置につなぐ方法も同じ。
  計画は TA\*-S exact（A\* ＋ コストを考えた平滑化、`exact_los=True`）。
- `run_online_mission` は、`OnlinePlanner` と `virtual_sense` を、`step_m` ずつ経路の上を進む簡単な動き（`run_online` と同じ）で回す関数。
  巡回の各区間を順に走り、走った軌跡・計画し直した回数・計画にかかった時間（1 回ごと）・各区間の結果を返す。
- **`run_online` を変更しないこと。** 作り直した中身が同じであることは、下のテスト 1 で確かめる。

## 2. 地図ファイルと Gazebo の world
- `data_prep/export_maps.py` で、`stale` 用の地図ファイルを加える：点群の砂浜の `validation` のうち 1 か所（`08OB87_-0206`、200m、シード 0）の
  漂着物あり（`real_las_08OB87_-0206_200m_0_debris.npz`）。漂着物なしは既にある `real_las_08OB87_-0206_200m_0.npz` を使う。
- 漂着物ありの Gazebo の world を `data_prep/export_gazebo.py` で加える（漂着物は箱として置かれる）。
- 今ある地図ファイルと world は変えない。

## 3. ROS2：`conference/ros2_jazzy/src/thesis_bunker_mission/` にノード `online_planner` を加える
- 起動の引数：`truth_map`（本当の地形の地図ファイル。Gazebo の world と同じもの）、`prior_map`（事前の地図ファイル、または `coarse:10`）、
  `sense_radius_m`（既定 10）。
- 本当の位置（`/ground_truth`）を受け取り、`virtual_sense` で見えた場所を `OnlinePlanner` に入れ、計画し直したら新しい経路を `path_follower` に渡す。
- **計画は別のスレッドで行う**。計画している間、ロボットは前の経路を走り続ける。1 回の計画にかかった時間を記録する。
- `path_follower` は、同じ走行の途中で経路が差し替わっても、**記録（`trajectory.csv`）を切らずに**新しい経路を追う（新しい走行と区別する）。
  差し替えの時刻と理由を `replans.csv` に書く。
- `sim.launch.py` に `online:=true prior_map:=...` を加える。`online:=false`（既定）のときは、今までと同じ動きにする。
- Web 画面（`conference/webui/`）：ロボットの状態に「今の経路」と「計画し直した回数」を加え、地図の上に今の経路を表示する。
  指示書012までの API と表示は変えないこと。

## 4. 実験（Gazebo なし）：`conference/experiments/online_mission.py`
結果は `conference/results/online_mission/` に置く。
- シナリオ：点群の砂浜の `test` 48 か所、200m、シード 0。巡回の地点は 5 点
  （`np.random.SeedSequence([0, 3000, 200, パッチの番号])`、指示書009の (D) と同じ選び方。ただし `stale` では、漂着物ありの地図で通れる地点だけ）。
- 条件：事前の地図 3 種類 × 見える半径 5・10・15m。
- 集計：巡回全体の地形を考えたコスト J の、`oracle`（事前に本当の地形を知っていた場合）との差 dJ [%]（中央値・悪い側 10%・最大）、
  計画し直した回数、**1 回の計画にかかった時間（中央値・95% 値・最大）**、通れない場所に触れた走行の数、完走できなかった走行の数と理由。
- `stale` では、比べるために「計画し直さない」（事前の地図の経路をそのまま走る）場合も走らせ、通れない場所（漂着物）に触れた走行の数を出す。
  **これが、走りながら計画し直す意味を示す一番大事な数字**です。
- パラメータは今までの値のまま。何か決める必要があれば `validation` の 12 か所だけを使う。表示した集計表を `online_mission_log.txt` に保存する。

## 5. Gazebo で確かめるスクリプト
`conference/ros2_jazzy/gz_checks/` に、`online` の確認を加える：漂着物ありの world で、`prior_map` = 漂着物なしの地図、半径 10m、
5 点の巡回を走らせ、完走、漂着物（通れない場所）に触れたマスの数、計画し直した回数、1 回の計画の時間を `results.json` に書く。
同じ地点で、計画し直さない場合（`online:=false`、漂着物なしの地図で計画した経路）も走らせて並べる。
Codex の環境で Docker が使えなければ、スクリプトだけ書けばよい（Claude が走らせる）。

## テスト：新しいファイル `conference/tests/test_online_mission.py`（ROS2・Gazebo なしで動くこと）
1. **`run_online` と同じであること**：A から B への 1 区間で、`run_online_mission`（地点 1 つ）が `run_online`（`planner="TA*-S"`、`exact_los=True`、
   `unknown_cost="adaptive"`、`prior_lethal="soft"`、事前の地図なし、および `coarse_prior(tm, 10)`）と**同じ軌跡・同じ計画の回数**になること。
   人工の砂浜 2 枚と点群の砂浜 2 か所、100m。
2. **安全性**：テスト 1 のシナリオと `stale` のシナリオ（点群の砂浜 3 か所、5 点）で、走った軌跡の `path_lethal_cells` が 0。
3. **`stale` の意味**：漂着物を通る経路になる事前の地図で、計画し直さない場合は通れない場所に触れ、計画し直す場合は触れないシナリオが少なくとも 1 つあること
   （シードを固定して、そのシナリオを探してテストに書いてよい）。
4. **ROS2 のノードの中身**：`online_planner` の、ROS に依存しない部分（スレッドで計画して差し替える流れ）を、時間を進める模擬で確かめる。
   計画中は前の経路を出し続けること、差し替えが記録されること。
5. **既定の動きが変わらないこと**：`online:=false` の起動・`path_follower`・Web の API が、指示書012のテスト（`tests.test_ros2_gz`）どおりに動くこと。
6. 既存のテストがすべて通ること。

## この指示書で変更してよい既存ファイル
- `conference/ros2_jazzy/` の中のファイル（上の 3・5 のため）。指示書012の動きは、既定値のとき変えないこと。
- `conference/webui/` の中のファイル（上の 3 のため）。指示書010〜012の API と結果は変えないこと。
- `conference/data_prep/export_maps.py`、`conference/maps/`、`conference/gazebo_worlds/`（上の 2 のため。加えるだけ）。
- **`conference/tests/test_mapfiles_sim.py` の地図の数の確認**：地図ファイルを加えると数が変わる。今ある 35 枚（指示書011の 23 枚と
  指示書013の 12 枚）がそのまま残っていることの確認に直し、加えた枚数も確かめること（確かめる中身を弱めないこと）。
それ以外の既存ファイルは変更しない。

## 完了の条件
- すべてのテストが通る。
- `python3 experiments/online_mission.py` が最後まで動き、CSV・ログ・図（`stale` で計画し直した例と、し直さなかった例を並べた図を数枚）ができている。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。
  PR を作れない場合は、ブランチを push して、報告をリポジトリの中（`conference/results/online_mission/REPORT_ja.md`）に置く。

## 結果の報告で必ず書くこと
- 集計表（そのまま）。とくに `stale` で、計画し直さない場合と計画し直す場合の、漂着物に触れた走行の数。
- 1 回の計画にかかった時間（200m の地図で、実際のロボットの速さ 1m/s で走りながら間に合うか）。
- センサーを「半径 R が見える」とした簡単化と、それで分からないこと（見えない陰、センサーの誤差など）。

## 対象外
LiDAR・カメラの模擬、点群からの地図作り、回る順番を走りながら変えること、実機、地形コストの式の変更。
