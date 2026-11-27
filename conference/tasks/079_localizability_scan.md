# 指示書 079：「ドローンの地図」の点群から仮の LiDAR のスキャンを作り、場所ごとの位置の決まりやすさ（情報行列の固有値）を前もって出す

> **状態：完了（結果は `results/localizability_scan/`、レビューは `REVIEW_ja.md`。078 との照らし合わせは 078 のあと）**。Gazebo・研究 PC は使わない。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/progress/policy.csv`（今後の方針）、`conference/research/literature_check_ja.md`（自己位置推定の文献の節。Kondo 2023・LF-3PM・X-ICP）、
> `conference/results/localizability_map/REVIEW_ja.md`（**071 の判定がなぜ使えなかったか**）、`conference/tasks/075_landmark_world.md`・`076_offline_localization.md`・`078_landmark_localization_eval.md`、
> `conference/tapp/landmark_world.py`、`conference/experiments/offline_localization.py`（`information`・`MapRegistration`・`MIN_INFORMATION`）、`conference/ros2_jazzy/gz_checks/lidar_checks.py`（目印の置き方の入口・初めの経路）、
> `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/lidar.py`（`LidarSpec`）・`conference/tapp/sensor_geometry.py`（取り付け位置）を読むこと。
> ブランチは `codex/079-localizability-scan`（その時点の `realtime-map` の最新から）。結果は `conference/results/localizability_scan/`、報告は同じ場所の `REPORT_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 修論の範囲：ドローンが撮ったばかりの地図を正とし、その上で人が選んだ地点を効率よく回る。BUNKER には GNSS がなく、位置は LiDAR で積み上げ、ドローンの地図に重ねて直す予定。
- 071 で、標高どうしをずらして比べる簡単なやり方で「位置が決まりやすいか」を地図にしたが、判定のしかたで 0〜80% と数字が決まらなかった（071 の REVIEW）。
- 文献では、**その場所で LiDAR が見るはずの点を地図に重ねたときの情報行列（ヘッセ行列）の小さい固有値**で、位置の決まりやすさを前もって出す（Kondo 2023、LF-3PM、X-ICP）。076 の道具は、重ね合わせのたびにこの固有値を出し、1.0 以下なら直さない。
- 078（研究 PC）で、目印の数（1ha あたり 0・10・40・160 個）を変えた世界を走らせ、実際の位置の誤差を測る。**この 079 の予測の地図が、078 の実際の誤差と合うか**を、あとで照らし合わせる。

## 作るもの：`conference/experiments/localizability_scan.py`
1. **世界**：078 と**同じ目印の置き方**になるよう、`lidar_checks.py` と同じ入口（`--prepare-only` で作られる manifest の地点、`place_landmarks`）で目印を置き、`reference_cloud.npz` と同じ点群を作る。
   対象は 078 と同じ：砂浜 `08OB88_-1417`・`08OB86_-0205` × 目印 1ha あたり 0・10・40・160 個 × シード 0・1・2。078 の manifest と目印の一覧が一致することを確かめる。
2. **仮のスキャン**：地図の上の各地点（陸で通れるマス、5m おき）に、BUNKER の LiDAR（`LidarSpec` の 16 本・±15°・1800 点・30m、取り付け位置は `sensor_geometry` の値をモデルの原点から）を置き、地形のメッシュと目印の形に対して光線を飛ばして、見えるはずの点を作る（隠れた所は見えない）。雑音は `LidarSpec` の 0.02m。向きは海岸に沿う向きの 1 通り（LiDAR は 360° 見えるので）。
3. **決まりやすさ**：その仮のスキャンを、正しい位置を初めの値にして 076 の `MapRegistration` で地図の点群に重ね、076 の `information` で、正規化した最小の固有値、並進と回転のそれぞれの固有値、いちばん弱い向きを出す。076 の基準 `MIN_INFORMATION`（1.0）以下の割合も出す。
4. **経路に沿った予測**：各回の初めの経路（manifest の `path`）に沿って 1m おきに同じことをし、経路のうち基準以下の区間の長さと、いちばん長く続く区間の長さを出す。078 の結果と照らし合わせるのに使う。
5. 出すもの：場所ごとの CSV、砂浜 × 目印の数 × シードごとの集計（基準以下の割合、固有値の中央値・10% 値）、地図の図（固有値を色、弱い向きを短い線で）、経路に沿った固有値の図。

## 守ること・やらないこと
- 値（5m おき、1m おき、LiDAR の設定、雑音、基準 1.0）は上のとおり。基準は 076 で合成データから決めたもので、ここで変えない。結果を見て変えない。
- 既存のファイルの出力はバイト単位で変えない（075・076 の関数は呼ぶだけ）。Gazebo・研究 PC は使わない。
- 光線の計算は、Gazebo の GPU の LiDAR と細かい所（地形のメッシュの三角形の分け方など）で違いうる。違いの大きさを、075 の合成のスキャンなどで確かめて報告に書く。

## テスト `conference/tests/test_localizability_scan.py`（ROS2・Gazebo なしで動くこと。kiss-icp・small_gicp がない環境では、要るテストだけ飛ばして、そう表示する）
1. 光線：平らな地面に立てた箱の後ろが隠れて見えない。届く距離・角度が `LidarSpec` どおり。
2. 平らな面だけの世界では最小の固有値が基準以下になり、弱い向きが面に沿う向きになる。目印のある世界では基準を超える。
3. 目印の置き方が、同じ条件の `lidar_checks.py --prepare-only` の manifest と一致する。
4. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文、使った版。
2. 砂浜 × 目印の数ごとの、基準以下の割合と固有値の表、代表の地図の図。
3. 経路に沿った予測の表（078 と照らし合わせるための形）。
4. 光線の計算と Gazebo の違いの見積もり。できなかったこと、自信がないこと。
