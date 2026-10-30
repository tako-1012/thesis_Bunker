# 砂浜の巡回計画 Web 画面

ROS2・Unity なしで、地図に置いた1〜12地点を回って基地へ戻る経路を計画します。
Python 3 とブラウザで動作します。初回の依存関係のインストール後は、インターネット接続は不要です。
Leaflet 1.9.4 の JavaScript・CSS・画像・BSD-2-Clauseライセンスは `static/vendor/leaflet/` に同梱しています。
外部タイルやCDNは使用しません。

## 起動

リポジトリ直下から実行します。

```bash
pip install numpy scipy matplotlib pandas
pip install fastapi uvicorn httpx
cd conference
python3 -m webui.server --host 0.0.0.0 --port 8080
```

パソコンでは `http://localhost:8080` を開きます。引数なしの `python3 -m webui.server` も同じ設定です。
終了はターミナルで Ctrl+C。単一プロセスで起動してください（計算中の排他制御はプロセス内です）。

iPad はパソコンと同じWi-Fi／ローカルネットワークにつなぎ、Safari で
`http://<パソコンのIP>:8080`（例：`http://192.168.1.10:8080`）を開きます。
IP は Windows の `ipconfig`、macOS の「システム設定 → ネットワーク → Wi-Fi → 詳細 → TCP/IP」、
Linux の `hostname -I` または `ip addr` で調べられます。ループバックの `127.0.0.1` は使いません。
接続できない場合はパソコンのファイアウォールのTCP 8080許可と、Wi-Fiの端末間通信設定を確認します。
クラウド実行環境ではポート8080への転送URLを使ってください。

## 使い方

1. 「地図を選ぶ」で従来の人工5種類・実測12パッチ、または地図ファイル23枚を選択します。
   地図ファイルには100m／200mの人工地形、実測12か所、平地と箱3つの `flat_test` があります。すべて0.5m格子です。
   従来の地図IDのシード100は変えていません。実測の地図ファイルはシード0、漂着物追加なしです。
2. 地図をタップ／クリックして地点を追加します。オレンジの番号は入力番号です。
   ドラッグで移動し、タップして開く「この地点を削除」で削除できます。◆の基地も移動できます。
3. 「地点の座標」に `x, y` を1行1点で入力して「座標を適用」すると、地点一覧を置き換えます。
   基地は別の座標欄で「適用」。地図外や水上の地点も置けますが、計画時に理由付きで受付外になります。
   「JSONで保存」「読み込み」で地図ID・基地・地点・方式を保存／復元できます。
4. 順番の決め方を選び「経路を計画」。計算中も地図の拡大縮小や移動は可能です。
   12地点では数十秒かかる場合があります。地点編集は計算中だけ無効になります。
   「両方を比べる」は地形を考慮（緑の実線）と直線距離（青の破線）を順に計算し、経路と指標を並べます。
5. 計算後のマーカーは巡回順です。元の入力番号はマーカーのツールチップと経路順の欄で確認できます。
   比較時のマーカーは地形を考慮した順番です。受付外は「×」です。
6. 「再生」で経路に沿ってロボットのマーカーが1.388m/s（約5km/h）で動きます。「停止」で終了。
   比較時は地形を考慮した経路を再生します。地点を編集すると古い経路と結果は消えます。
7. 計画後に「先読みの距離」を0.5〜3.0m（初期値1.0m）から選び、「走行をシミュレーション」を押します。
   Pure Pursuitによる走行軌跡を橙で重ね、所要時間・経路からのずれの平均／最大・通行不可との接触数・完走の有無を表示します。
   比較後は地形方式の経路を使います。先読みの距離を変えると以前の走行結果は消えます。
   シミュレーション後の「再生」は走行軌跡を計算時刻どおりに再生します。
   速度上限1.0m/s、角速度上限1.0rad/s、時間刻み0.05秒、到達許容距離0.3mです。
   滑り・傾斜による減速・衝突回避は入れていません。計画が安全でも、追従時に角を内側へ曲がって接触する可能性があります。

## 座標・計算・API

画面とAPIの座標はローカルなメートル単位です。xは海岸線方向、yは海から陸へ向かう方向。
`round(x / 0.5), round(y / 0.5)` で格子へ変換します（ちょうど半分はPythonの偶数丸め）。
格子中心は200m地図で0〜199.5m、100m地図で0〜99.5mです。これを超える座標は拒否します。
画像境界は格子中心から半マス分延長し、マーカーと画素の中心を一致させています。
実測データREADMEの元の範囲（x=−100〜100m、y=−50〜150m）に対し、ここでは最初の格子中心を(0,0)とします。
方向は同じです。緯度・経度やGPS座標ではありません。丘陵・起伏地の軸はローカルなx・yです。

順番は既存の `tapp.tour.cost_matrix`・`solve_tour` を使用します。
地形を考慮する場合は `kappa=1/robot.rolling_coeff`、直線距離の場合はユークリッド行列で順番を選びます。
両方式とも区間は同一の向き付きコストとexact LOS平滑化を使います。既存の重み・閾値は変更しません。
開始地点と同じ地点や重複した地点も受け付けます。安全な開始地点から行けない地点は除外します。
開始地点自体が無効なら空の経路と理由を返します。すべての地点が受付外なら基地だけを返します。

| API | 内容 |
|---|---|
| `GET /api/maps` | ID・日本語名・大きさ |
| `GET /api/maps/{map_id}` | 大きさ・解像度・形状・基地・Leaflet用画像境界 |
| `GET /api/maps/{map_id}/image.png` | 1マス1画素PNG（x右向き、y上向き） |
| `POST /api/plan` | `{map_id, start: [x,y], points: [[x,y],...], method: "terrain" または "euclid"}` |
| `POST /api/simulate` | `{map_id, path: [[x,y],...], lookahead_m: 1.0}` |

IDは `synthetic/beach_gentle/200/100`、`real/<パッチ名>/200`、`file/<ファイル名>.npz` の形式です。スラッシュを含むままで指定できます。
地図ファイルは `conference/maps/` に置き、サーバーを再起動してください。形式と出典は `maps/README_ja.md` を参照してください。
計画結果の `order` は基地0・入力地点1始まり、末尾の基地の繰り返しは省略します。
`path` は復路も含むメートル単位の点列。`legs` は元の入力番号での始点・終点、経路、長さ[m]、コスト。
`tour_cost` は両方式とも実際に通る区間の向き付きコストの合計（既存コードの格子コスト単位）。
`ordering_cost` は順番選択に使った行列の合計（直線距離方式では格子単位の距離）。
`metrics` は `tapp.metrics.evaluate` の出力そのままで、長さ・登った高さ・急斜面長はm、横傾きは度、エネルギーはkJです。
区間の `length_m` は折れ線の幾何学的な長さ、全体の `length_xy` は既存評価器の0.1m再サンプリング後の長さなので、
折れ曲がる位置でわずかな差が出ることがあります。評価器は変更していません。
エネルギーはA*比ではなくモデルの推定値であり、実機測定値ではありません。
`path_lethal_cells` は経路が接触する通行不可マスの数です。0であることをサーバーでも検査します。
`timing` は行列・順番・計画全体の秒数（地図初回生成と画像生成、通信時間は含まない）。
`rejected` は元の入力番号（基地は0）と日本語の理由です。

地図不明は404、0個／13個以上の地点や不正形式は422、先行計画の計算中はすぐ409を返します。
計画と地図生成はワーカースレッドで実行し、計算依頼を待ち行列に積みません。
走行シミュレーションも同じ排他制御を使います。`trajectory` の各行は `[時刻秒,xメートル,yメートル,yawラジアン]`。
`elapsed_s`、`deviation_mean_m`、`deviation_max_m`、`path_lethal_cells`、`lethal_cells`（マス座標）、
`out_of_bounds_samples`、`completed` を返します。初期の向きは最初の長さのある区間に合わせます。
閉じた巡回の終点が基地でも開始直後に終了しないよう、経路に沿う進捗も使って到達を判断します。
ログイン・実機への送信・複数人の同時利用は対象外です。

## テストと画面の検証

```bash
cd conference
python3 -m tests.test_mission
python3 -m tests.test_mapfiles_sim
python3 -m tests.test_ros2_gz
```

タスク010の記録は `REPORT_ja.md`、タスク011の当時の結果は `REPORT_mapfiles_sim_ja.md` を参照してください。
旧17件固定の検査は上流のrealtime-mapで修正済みです。タスク012の最新結果・制約は `conference/ros2_jazzy/REPORT_ja.md` にまとめています。
走行模型の画面は `screenshots/mapfiles_sim_*.png`、模擬ロボット表示の画面は `screenshots/ros2_robot_*.png` です。

画面の自動検証を再実行する場合だけ、開発用に `pip install playwright` を実行し、
Chromiumをシステムに用意するか `python3 -m playwright install chromium` で取得します。
サーバーを起動したまま、別のターミナルで次を実行します（通常の利用には不要です）。

```bash
cd conference
python3 -m webui.check_mapfiles_sim
```

実際のプランナーでファイル地図の計画・走行・再生を行い、スクリーンショットと `results/mapfiles_sim/` の検証CSV・入力JSONを更新します。
`WEBUI_BASE_URL` 環境変数で接続先を変更できます。iPad相当の検証はChromiumのタッチエミュレーションです。
Safari実機の検証を代替するものではありません。

タスク011の実装・テスト結果・接触の記録・Gazebo変換誤差は `REPORT_mapfiles_sim_ja.md` を参照してください。
タスク011の画面確認は `python3 -m webui.check_mapfiles_sim` で再実行できます。
Gazebo用の地形は次のコマンドで書き出します（Gazeboのインストールは不要）。

```bash
cd conference
python3 data_prep/export_gazebo.py maps/flat_test_100m.npz gazebo_worlds/flat_test
```

Ubuntu 24.04のGazebo Harmonicでの起動方法は、出力先の `README_ja.md` を参照してください。
この環境ではGazeboの実行は検証していません。

## ROS2・Gazeboのロボットへ送る（タスク012）

Ubuntu側のセットアップ・模型の値と出典・起動方法は `conference/ros2_jazzy/README_ja.md` を参照してください。
WebサーバーにはROS2をインストールする必要はありません。
同じファイル地図をGazeboとWebで選び、計画結果の「ロボットに送る」で送信します。
比較後は地形方式を送ります。紫のマーカー・線はロボットから届いたworld座標の位置・走行軌跡です。
送信番号と走行中／完了／立ち往生を表示し、3秒以上状態が届かなければ未接続と表示します。
停止はUbuntu側で行います。サーバーの再起動時にはUbuntu側の橋渡しノードも再起動してください。

`POST /api/robot/mission` は `{map_id,path,lookahead_m}`（任意の `points` も可）を保存し、`id` 付きで返します。
`GET /api/robot/mission?after=<id>` は新しい指示がなければ204。
`POST /api/robot/state` は `{map_id,mission_id,status,pose:[x,y,z,roll,pitch,yaw],sim_time,message}`、
`GET /api/robot/state` は最終状態と `connected`・`age_s` を返します。座標はm、角度はradです。
保存は単一プロセスのメモリ内・最新指示1件です。従来の地図・計画・シミュレーションAPIはそのまま使用できます。

実機やGazeboがないときの表示確認用（**模擬状態であり、走行の測定値ではありません**）：

```bash
cd conference
python3 -m webui.mock_robot --map-id file/flat_test_100m.npz --pose 10,10,0,0,0,0
```

`python3 -m webui.check_ros2_gz` で計画・送信・模擬位置・軌跡・未接続表示のブラウザ検証を再実行できます。
`screenshots/ros2_robot_desktop.png` と `screenshots/ros2_robot_ipad.png` はこの表示確認の画面です。

## 実測地形の出典（共通）

- 出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB グリッドデータ（0.5m）
  https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb
- ライセンス：CC BY 4.0 / ODbL。**このフォルダのデータは、上のデータを加工して作成したものです**
  （論文や発表で使うときは、この出典を書くこと）。
- 元データの座標：日本測地系2024・平面直角座標系第8系、高さは東京湾平均海面（T.P.）。

詳細は変更していない `conference/data/shizuoka_beach/README_ja.md` を参照してください。
水・データなしは通行不可です。データから漂着物・植生・砂の湿潤状態はわかりません。
