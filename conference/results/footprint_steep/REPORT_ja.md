# 指示書020：急斜面の車体半径による膨張と転倒の集計

報告日：2026-11-04（日本時間）。
ブランチ：`codex/020-footprint`。基点：`origin/realtime-map` の `e511ee8acc83bac7451a300667479d6b5ed636ab`。他の作業ブランチを積まず、この最新の土台から独立して作成した。マージしていない。

## 結果と残っていること

Pythonの全比較と既存・新規テストを実行した。追加のGazebo走行は、サンドボックス外実行の権限確認が中断されたため未実行である。準備した起動スクリプトは実行開始しておらず、新方法の実測値は作っていない。

地図全体を知る192条件についての解けた数（実行結果から計算）：

planner  scenarios  solved
                 A*        192     192
              TA*-S        192     192
 TA*-S+inflate r0.5        192     190
TA*-S+inflate r0.39        192     190

オンラインR10の完走数：

prior             planner  runs  completed  failed
coarse c10               TA*-S    48         45       3
coarse c10  TA*-S+inflate r0.5    48         44       4
coarse c10 TA*-S+inflate r0.39    48         44       4
     stale               TA*-S    48         46       2
     stale  TA*-S+inflate r0.5    48         45       3
     stale TA*-S+inflate r0.39    48         45       3

膨張なしの013・014の対照条件も実行し直した。経路評価、成功・失敗、計画回数、接触、J・dJ・oracle Jは保存済み結果との差が0だった。計画時間は今回の実行から独立に測定した。

019の原記録から2走行を転倒に分類した。原missionの `stuck` はそのまま保持し、集計の `status` を `rollover`、`recorded_status` を原状態とした。初めて絶対rollが90度を超えた記録の時刻とx,yも追加した。

```csv
patch,planner,recorded_status,status,rolled_over,rollover_t_s,rollover_elapsed_s,rollover_x_m,rollover_y_m,roll_p95_actual_deg,roll_max_actual_deg,pitch_p95_actual_deg,pitch_max_actual_deg
08OB88_-0167,A*,stuck,rollover,True,138.9,133.8,155.5228775852522,138.02537760075458,167.11136883482112,176.68240863873373,33.06292227518301,43.79474235132325
08OB88_-0167,TA*-S,stuck,rollover,True,265.35,260.25,196.38693502330693,141.84068766422286,13.214100243930908,176.26005611636418,26.28098805500159,79.86697190179804
```

## 実装したもの

- `tapp/footprint.py`：`inflate_steep` は急斜面だけを膨らませ、元のlethalと合わせる。`with_inflated_steep` はシナリオとtmapを浅くコピーし、lethalだけを差し替える。コスト・標高・開始終了点は変更しない。既存の `traversability.py` は変更していない。
- 膨張には岩と同じ `traversability.inflate` の切り上げ規則を使う。既定は `tm.robot.footprint_radius` の0.5mで、指定された0.39mも固定して比較した。0.5m格子ではどちらも1セルの円盤となり、同じマスクになる。テスト結果から半径を選んでいない。
- 急斜面への近接率は、経路の折れ線と急斜面セル中心の半径0.5m円の交差区間を解析的に求め、重なりを統合した長さ割合。サンプリング刻みを追加していない。格子の丸めとは区別して名目の0.5mを使う。
- `run_footprint_mission`：事前地図と真値の急斜面ラベルを膨張させ、014の既存の観測・再計画・移動処理を呼ぶ。半径0では既存処理をそのまま呼ぶ。開始・目的地点が膨張後の真値で通れなければ `blocked_endpoint` とし、移動・地点の補正をしない。
- `experiments/footprint_steep.py`：192条件×4手法の全知地図比較、48地形×2事前地図×3手法のオンラインR10比較。未完走の理由、接触の監査有無、計画1回ごとの時間、経路長、平均地形コスト、登り、横傾き、近接率を保存する。エネルギーは集計しない。
- `experiments/gz_compare_report.py`：転倒の最初のサンプルを検出し、最大値・95%値・転倒フラグを表に併記する。複数手法の対の差は、それぞれの対が完走した地形だけで計算する。
- `experiments/footprint_annotation.py`：019のCSVの既存値を文字列のまま保って新列とstatusを付け、019の報告書にも反映する。原記録・走行別数値・図・既存の対の差のファイルは書き換えない。
- `ros2_jazzy/gz_checks/compare_checks.py` と起動スクリプト：`--planners TA*-S+inflate` を追加。既定のA*・TA*-Sの計画と走行条件は維持する。膨張版の計画だけに新マスクを使い、物理worldは元の地形から作る。経路なしは空の計画で記録し、Gazeboを走らせない。
- `experiments/footprint_report.py`：既存019と新しい膨張版の3手法を並べる。新しい原記録がなければ計画だけを生成し、物理の測定欄は空欄・None・NaNにする。追加実測後は `--inflated` で読み直せる。
- `tests/test_footprint.py`：円盤の範囲、半径0、コスト・元のマスクの不変性、端点不動、実地形の経路、厳密な90度閾値、原記録のハッシュ、数値文字列の保持、砂浜単位の統計、実走の分母、3手法の対ごとの集計を検証する。

## 比較条件と統計

全知地図はLASのtest48地形×100m・200m×漂着物なし・あり、seed 0。4手法はA*、TA*-S、TA*-S＋膨張0.5m、TA*-S＋膨張0.39mである。開始・終了点は元のbuild_realの結果を保ち、膨張で不適格な場合は解けないと記録する。

Wilcoxonは砂浜を単位とする。各手法対について両サイズが双方で解けた地形だけを残して、100m・200mを砂浜内で平均する。どちらか一方のサイズが欠ければ、その砂浜全体をその対の検定から除く。条件の枚数を独立標本として扱わない。漂着物2条件×事前定義した3比較（TA*-S−A*、各膨張版−TA*-S）×5指標で、Holm補正の1家族30検定とした。利用不能な比較はp=1として補正し、表ではNAを出す。追加の最大増加率は記述集計で、検定を追加していない。

オンラインは014と同じLAS48地形、200m、seed 0、5地点の閉巡回、staleとcoarse c10、観測半径10m。順番は014の元の事前地図で決めたものを全手法で共用し、各区間の経路だけに膨張を反映する。dJの分母も014の膨張なし全知oracle Jを共用するため、差には安全余裕の制約によるコストと、事前地図の不完全さによる差の両方が入る。

センサーは014の「半径内の真値の走行可能ラベルが見える」という理想化を保つ。膨張済みラベルなので、観測円のすぐ外の急斜面が円内のラベルに影響しうる。生の点群・遮蔽・誤差を模擬しているとは解釈しない。端点不適格を開始前に真値で分類したものは移動せず、接触監査の分母にも入れない。計画時間・再計画回数が小さく見える場合は、未実行・未完走の件数と併せて読む。

計画時間は014の既存処理が測る探索と経路平滑化の時間であり、事前の地形生成・急斜面膨張・巡回順序の計算は含まない。今回の3ワーカー環境での計測であり、実機の実時間性能は検証していない。Pythonの接触評価は理想的な経路追従と地図ラベルに基づく。

実行前に固定したパラメータ、ソース・データのハッシュ、ライブラリ版、統計の定義：

```json
{
  "dataset": "shizuoka_beach_las",
  "split": "test",
  "seed": 0,
  "radii_m": [
    0.5,
    0.39
  ],
  "raster_rule": "same ceil(radius/0.5) disk as rocks; both prescribed radii map to one grid cell",
  "proximity": "exact arc length within 0.5m of steep cell centres",
  "statistics": "48 beach units; both sizes paired then averaged; 30-test Holm family",
  "online": "same task014 prior-fixed order, truth-label sensing, R10; shared unchanged oracle",
  "environment": {
    "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
    "numpy": "2.3.5",
    "scipy": "1.17.0",
    "pandas": "2.2.3"
  },
  "dataset_sha256": {
    "data/shizuoka_beach_las/08OB86_-0205.npz": "5a363b942c0991542b46e1e8657088b641647726fd5a2af684327cb3cdb762c9",
    "data/shizuoka_beach_las/08OB86_00294.npz": "a28761a28ecd3b99b26d1d7e9899c0eba55a43047c726a74361f08e022b81e72",
    "data/shizuoka_beach_las/08OB87_-0206.npz": "2362e64b3b2e83a3cb145b90546adaf603fb2db703d323ffe778683d6abc1cd6",
    "data/shizuoka_beach_las/08OB87_-0706.npz": "040ed7b94cd70b41e9d2b94259b40ab8c1210d849732b1132f34cb5230c64d64",
    "data/shizuoka_beach_las/08OB88_-0167.npz": "9896a3892eef5fc439daad325c22f149e0a2157c94daec0be60296ebbc5f06dc",
    "data/shizuoka_beach_las/08OB88_-1417.npz": "f0ecb31bd4d851ea4c88ce0057e3c379591572d3b2308066f6120c061dd7c7cd",
    "data/shizuoka_beach_las/08OB88_00332.npz": "36aa756efe874f15dbd9ce45d1ccb85997c6d9131ac20bbaeab3ed2c368e172d",
    "data/shizuoka_beach_las/08OB88_01332.npz": "32e4309a268d329bca1e6529ec4831945e8ee14033b4f9b3d111928fb3cc46e8",
    "data/shizuoka_beach_las/08OB88_01832.npz": "709d8f2f68753a49293a315091a595bc6f489439cbfcf763920c23abbeb71d84",
    "data/shizuoka_beach_las/08OB89_-0347.npz": "4308458273952d62958f2f4a080253e9a676337594dd1c6ea87f277c92e12882",
    "data/shizuoka_beach_las/08OB89_-0847.npz": "c530894cc3784c412abc8a15837e638b852236450421106136e63463814e6476",
    "data/shizuoka_beach_las/08OB89_-1597.npz": "4ebdcb75d55527756c94ed51a960364cadeb36b8a0becdc19417083fa37f4cb4",
    "data/shizuoka_beach_las/08OB89_00152.npz": "82dfbd220de3f07afa0161c884941f8dba65c3d8d2ad4d8fef59d18d5efd7b50",
    "data/shizuoka_beach_las/08OC80_-0589.npz": "eea8c50a2eca6e505e5eeece7a64ce201fd5e1c889d060737be471d0e8e7c1fd",
    "data/shizuoka_beach_las/08OC80_-1089.npz": "2e1686f878e977f90ab335e485a3ce7927064322f4a486c325d3477234117a01",
    "data/shizuoka_beach_las/08OC80_00160.npz": "2baafd354e5f6800730a7deb2294a70540e1cc89f2498150a99b611d2e383885",
    "data/shizuoka_beach_las/08OC80_00660.npz": "ac74e66f9f2f5ecd1468663b23e804e9ec7ac2d2861cfc73b835ba642ae9241c",
    "data/shizuoka_beach_las/08OC90_00270.npz": "d61029eead58d69dc206e9d5e46f020d7d72619b91379e3b76e3003d0b8ba0bd",
    "data/shizuoka_beach_las/08OC91_-0438.npz": "a17eb68228634a29834a2133e90a5efa7a5fcd5577e22b43ee4b1295439d1edb",
    "data/shizuoka_beach_las/08OC91_-0938.npz": "47b60bde15dbae4dcfb88c3bbaec6bf68d0794862c5977db1a683b7583971f65",
    "data/shizuoka_beach_las/08OC91_-1688.npz": "ffee643083a86ef72a018473902f47e5230d90d8803237f1f862b7b30e9cfaf3",
    "data/shizuoka_beach_las/08OC91_00061.npz": "fa7176fc45b2a7291036608b6ef43fe417e5c214a5731ca35ce5fdddd659e111",
    "data/shizuoka_beach_las/08OC91_00811.npz": "d8a9c076262f01b55dd85c25e8068beab4ba92847c5036b38c8c04f76accdc6e",
    "data/shizuoka_beach_las/08OC91_01311.npz": "6d8cd32bf392602f2acdd7992de7b15d101a82ca8d60184ae310d48fd29e6a21",
    "data/shizuoka_beach_las/08OC92_-0141.npz": "80c52dac9cf15949b1f4a2b7e7d816d1ab8cba82de502595da663641307f0ed1",
    "data/shizuoka_beach_las/08OC92_-0891.npz": "f70131bd9344a7172d3611156a6fb6345533aa62a8073f93644b06414909bd77",
    "data/shizuoka_beach_las/08OC92_00608.npz": "617151648ebf383e0e5dbab49941f9a08c885560e674e3e3e1f92d9d55956b5f",
    "data/shizuoka_beach_las/08OC93_-1519.npz": "30e6d400d4d97739d79233f0b2301ac17c5e34c929ed877f0f1e7d52427204dc",
    "data/shizuoka_beach_las/08OC94_-0954.npz": "c916987689c917ca98db03f9658c3980ee4ffcc1ff47c8bb3e74ed9bfeb5879a",
    "data/shizuoka_beach_las/08OC95_-0321.npz": "782bc2e68a619572144659c1ac696680405521970835a3ba8721284713765240",
    "data/shizuoka_beach_las/08OC95_-0821.npz": "2552fb8363fd16b8f1a37655005550092135402812bec556c8b2e1646478515b",
    "data/shizuoka_beach_las/08OC95_-1321.npz": "12eaa6ec89c8c065910bbd81b6f1fd14e59863798597d6b3bd3b6098a5965ef4",
    "data/shizuoka_beach_las/08OC95_-2071.npz": "bbc000d3d7bf0b9c4820a0e19cd2095c373ff65e6517473c91fe9af4d4101346",
    "data/shizuoka_beach_las/08OC95_00428.npz": "e292357d5794ef49074f5dcbd6561276b5e4e9c7964379d22ff9b87cb5c92d7d",
    "data/shizuoka_beach_las/08OC95_00928.npz": "d1e9456f2e5415ac1ba28a8536d252407a0fd633983e9dd8ec5785393a46c879",
    "data/shizuoka_beach_las/08OC95_01428.npz": "5495ca1edf62578c66b4ccf3398a86208c4c4dcbbe3beeb5fabac48279e6922a",
    "data/shizuoka_beach_las/08OC96_-0676.npz": "fb89920533861f6e60d41a537806c9fc85341ff37088f3ad1491aac485fc1577",
    "data/shizuoka_beach_las/08OC96_-1426.npz": "eb34cb9ad444e37f7f2d87d7e5de44f7471331c027a8b16d6166e651a046bcc5",
    "data/shizuoka_beach_las/08OC96_00073.npz": "2436f1e21cbb40397963ca950b6f5728ef8177e15800ebb73b3c910278c77d13",
    "data/shizuoka_beach_las/08OC97_-0077.npz": "f7d637689d09a62d951003f5881fd0a0cb90bb8da7e48fc670cecf50a2cfcfcb",
    "data/shizuoka_beach_las/08OC97_-0577.npz": "c09d884e87996ee4decb45546351e75b2a60122bf3f89465651e6f275d062cf9",
    "data/shizuoka_beach_las/08OC97_-1077.npz": "b78f75e005c4b008affca8e2bd8a836af470bbe2f467d2ba9b090c2966148b74",
    "data/shizuoka_beach_las/08OC97_-1827.npz": "57ede7154178f9a5a8dfefa8a23e6b012ef451f1723ce00ed3e105e7b1c3ba7f",
    "data/shizuoka_beach_las/08OC97_00422.npz": "a83cbfc1265076c923db7718c7c9e0e3552d204f5905741e03866bce66558a22",
    "data/shizuoka_beach_las/08OC97_01172.npz": "854073987b0fbdb9400dc55d784613a18fedfb1c058ef37961d54c143e2c791e",
    "data/shizuoka_beach_las/08OC97_01672.npz": "37433c0d5c4dcfdda1228a386c1000f40794c1e4773185efac9169d6c181bce3",
    "data/shizuoka_beach_las/08OC98_-0351.npz": "245a5882232d6473647a9ba86037c32c2821a0e496b8a1b558485a8ffcae2121",
    "data/shizuoka_beach_las/08OC98_-1101.npz": "6ae24b2018eaee29c65674fde5f02618070d3843e553c5c988800350adb342ba",
    "data/shizuoka_beach_las/08OC98_-1601.npz": "3713853d938780f9c7d363a84d5b481b90508aa24efc01553310aafb3e65e023",
    "data/shizuoka_beach_las/08OC98_00148.npz": "0a440dcac8a4feb16facc1bdc165f99cafb9815d9c304346caf47229e3120050",
    "data/shizuoka_beach_las/08OC98_00648.npz": "10b70e5a20e6ae4060199272d52538752677db9482716540b579fed931a615c7",
    "data/shizuoka_beach_las/08OC98_01398.npz": "922a8bc3ac72a641cc16aff3d7471853ebe02342e927ea3c67801b89de29842d",
    "data/shizuoka_beach_las/08OC98_01898.npz": "73b78a263b6d512a54d7d6e49824f65bb9d87800e72425017ee9d1c63aef8fd8",
    "data/shizuoka_beach_las/08OC99_-0016.npz": "9fcfbe2f3aac0425d8aee4f4dad9197ceb9aef5ce885afe50f79429803b6a619",
    "data/shizuoka_beach_las/08OC99_-1016.npz": "d334b6ea08b6b02f034c00182f65dbcdee1b02a927b18b9a04704ac2d92ba0fc",
    "data/shizuoka_beach_las/08OC99_-1516.npz": "2e90bda69483623fc1fa086128df8dbcc0226bbf59bc22a5ca5fe24999c66ccb",
    "data/shizuoka_beach_las/08OC99_00483.npz": "1ffe155a61640731d9bdbb8209b76c13c7e43284978e10497da57d7cbdf3d744",
    "data/shizuoka_beach_las/08OC99_00983.npz": "6f8ca55cefaace6f09d10a4805b8f6c3dd1500adc776a328069f0957eb4386a5",
    "data/shizuoka_beach_las/08OC99_01733.npz": "41d4ca54c77e6ccbb78d568386a44d1b45dc2ca8318fc7a330cf57ffa29b2dfc",
    "data/shizuoka_beach_las/08PD00_-1730.npz": "1e7a83c021f2f90061a6392cec1538491b3d5b2e52d33e622593e515d9e5490e",
    "data/shizuoka_beach_las/README_ja.md": "bc3bf35293f0f67b7ba79adc71cf1c9c6b0183aa7677f969c527bd36dfc4e6a6",
    "data/shizuoka_beach_las/index.json": "7033159d7042f492decf4a190178b1453493518441eac539da9aa5887a7107e2"
  },
  "source_sha256": {
    "tapp/footprint.py": "2dcfd352570fbbcd9666439dbfeecd1d98fc911e083ff5f489d1a6c7739b1b4e",
    "experiments/footprint_steep.py": "082a7b13e88ccb9a26660cdcd89e3cc379efd5922bf42f8956579ebe83ca7860",
    "tapp/config.py": "5c4cfe860b16f2d4540e970f2ca19a634f563a24deb361d0e85b7daa6e6c7895",
    "tapp/real_beach.py": "34e61730bbf27f4156d7533f93eaf3e1200678e0de21ace6a9707080d7cddf67",
    "tapp/online_mission.py": "cb6256d33524a7121a79c4cb12e406b3be32f741bc072ebb4eb01481935882b9",
    "tapp/exact_planners.py": "e33e53cbc64ff281c4f9f764de4b910d38dd867abea41dfbd4fd93ea95c3f3ea"
  }
}
```

```json
{
  "workers": 3,
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "numpy": "2.3.5"
}
```

## 実行したコマンド

```bash
cd conference
python3 -m tests.test_planners
python3 experiments/footprint_steep.py --workers 3
python3 experiments/footprint_annotation.py
python3 experiments/footprint_report.py
```

テストは全モジュールを下記ドライバーで順に実行した。3手法の対ごとの集計修正後、関連する新規テストと既存Gazebo比較テストを再実行した。

```bash
python3 /tmp/task020_verify.py suite
cd conference
python3 -m tests.test_footprint
python3 -m tests.test_gz_compare
```

Pythonには既存のpython3を使用し、`OPENBLAS_NUM_THREADS=1`、`MPLCONFIGDIR=/tmp/thesis-020-mpl`、`XDG_CACHE_HOME=/tmp/thesis-020-cache` を指定した。追加パッケージの導入・ホストへのsudoは行っていない。

```text
3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]
Linux-6.18.57-x86_64-with-glibc2.41
{'numpy': '2.3.5', 'scipy': '1.17.0', 'pandas': '2.2.3', 'matplotlib': '3.10.8', 'fastapi': '0.141.1', 'pydantic': '2.13.4', 'httpx': '0.28.1'}
Worker processes: 3; OPENBLAS_NUM_THREADS=1
```

## テスト出力の全文

変更前：

```text
$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0
```

全20モジュール：

```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ python3 -m tests.test_footprint
dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed
proximity: analytic line-circle lengths, overlapping unions and tangencies passed
requested LAS case: inflated planner reports no_path without moving endpoints
online: zero radius preserves exact task014 trajectory and planning count
rollover: strict +/-90deg threshold, first time/position and immutable fake records passed
statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)
Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed
comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)
all footprint and rollover tests passed

exit=0

$ python3 -m tests.test_geo
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
zone VIII reference differences [latitude_deg, longitude_deg]:
-4.25145429972e-09 2.46816966865e-09
-4.06389943919e-09 -3.64556740351e-09
2.36028796508e-09 -3.05306002701e-10
2.78198797332e-10 -4.38916458734e-10
projection round-trip max error [m]: 7.10133463144e-09
geographic sidecars: 13 maps; source axes, coastline anchor, half-cell offset, round trips and NPZ hashes passed
Web APIs: geographic map conversions, unavailable-map response and unchanged legacy metadata/image passed
all geographic conversion tests passed

exit=0

$ python3 -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ python3 -m tests.test_mapfiles_sim
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed
all mapfiles/simulation tests passed

exit=0

$ python3 -m tests.test_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed
parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed
validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed
safety: synthetic/beach_gentle/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_steep/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_scarp/200/100, 5 points, terrain/euclid contact=0
safety: real/08OB87_-0206/200, 5 points, terrain/euclid contact=0
safety: real/08OB88_01332/200, 5 points, terrain/euclid contact=0
API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed
all mission tests passed

exit=0

$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ python3 -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ python3 -m tests.test_online_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
beach_gentle: no-prior/coarse exact trajectory and plan-count parity; contact=0
beach_steep: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB88_01332: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206 stale five-point tour: online contact=0; fixed debris cells= 11
08OB88_01332 stale five-point tour: online contact=0; fixed debris cells= 18
08OB89_-1597 stale five-point tour: online contact=0; fixed debris cells= 6
async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed
follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run
maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed
all online-mission tests passed

exit=0

$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ python3 -m tests.test_real_beach
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
all 60 patches satisfy sea-to-land orientation
08OB86_00294: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_-0205: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0706: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-1417: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0167: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00294: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB86_-0205: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0706: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-1417: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0167: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 0
all real-beach tests passed

exit=0

$ python3 -m tests.test_real_beach_las
data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed
quantized_0.1m_fraction: new_max 0.0035301084084904803 old_min 0.27882342564826246
defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches
08OB86_00294: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_-0205: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB87_-0706: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-1417: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-0167: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_00294: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB86_-0205: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB87_-0706: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-1417: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-0167: exact offline and coarse R5 c10 safety, clean/debris contact=0
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ python3 -m tests.test_ros2_gz
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed
packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed
follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 34.2 0.02959598405434589 0.3173397734180379 0
kinematic True 34.2 0.02959598405434589 0.3173397734180379 0
attitude actual_p95_deg map_p95_deg
roll 0.0 0.0
pitch 0.0 0.0
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 7.7 0.0 0.0 0
kinematic True 7.7 0.0 0.0 0
attitude actual_p95_deg map_p95_deg
roll 0.0 11.309932474020224
pitch 0.0 5.710593137499648
report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)
API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed
worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added
all ROS-free ROS2/Gazebo tests passed

exit=0

$ python3 -m tests.test_thesis_figures

T1
 debris    metric  n    A_median   TAS_median  delta_median              p         p_holm
  False mean_cost 48 0.110342949 0.0767774554 -0.0352167333 7.10542736e-15 5.68434189e-14
  False     climb 48  1.50126915  0.890802236  -0.410943017 7.10542736e-15 5.68434189e-14
  False  p95_roll 48  5.45746622     3.567633   -1.89097743 7.10542736e-15 5.68434189e-14
  False length_xy 48         NaN          NaN   -2.00026809   0.0276182014   0.0552364028
   True mean_cost 48 0.154226921 0.0855587032 -0.0582350381 7.10542736e-15 5.68434189e-14
   True     climb 48  2.07159806   1.30575231  -0.803948405 2.13162821e-14 6.39488462e-14
   True  p95_roll 48  6.86720155   3.63401103   -2.80093993 7.10542736e-15 5.68434189e-14
   True length_xy 48         NaN          NaN  -0.764154874    0.947340222    0.947340222

T2
 radius_m   mode  runs  completed  touching   dJ_median     dJ_p90  replans_median  plan_s_median  plan_s_p95  plan_s_max
        5  fixed    48         48        46   3.8297614 10.8951737               0   0.0943159025 0.513914058  1.09228056
        5 online    48         46         0   1.9542052 10.2738521             101   0.0464642375  0.28593965  1.26618145
       10  fixed    48         48        46   3.8297614 10.8951737               0   0.0960627685 0.506711613  1.25659096
       10 online    48         46         0 0.945069248  6.6029207            94.5   0.0510014495 0.292423272  1.32438343
       15  fixed    48         48        46   3.8297614 10.8951737               0    0.094235528 0.485409814  1.26557115
       15 online    48         47         0 0.688622405 5.29694595              85    0.057362561 0.305458798  1.76405173

T3
                                world         mode  completed  path_lethal_cells  elapsed_s  roll_p95_actual_deg  pitch_p95_actual_deg  roll_p95_map_deg  pitch_p95_map_deg
              file/flat_test_100m.npz offline tour       True                  0    249.412       8.05631294e-09        6.79662109e-10                 0                  0
    file/real_08OB87_-0206_200m_0.npz offline tour       True                  0      348.2           4.76005563            6.20167607        4.58473933         6.31735413
file/real_las_08OB87_-0206_200m_0.npz offline tour       True                  0    289.516           3.83941424            2.47900287        3.84957483         2.58651471
       real_las_08OB87_-0206 / debris        fixed      False                  0      96.15           4.54713144            5.69114628        5.33797683         6.55378208
       real_las_08OB87_-0206 / debris       online       True                  0     190.95           4.31378469            4.21973305        4.30333238         3.67841423
thesis: F1-F7 PDF/PNG, T1-T3 LaTeX/Markdown and numbers.tex generated
statistics: 48 paired beaches, size means, medians and archived contact counts verified
outputs: no excluded measurement columns or values; all thesis figure tests passed

exit=0

$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ python3 -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0
```

```text
test_beach_terrain exit=0
test_collision exit=0
test_dstar exit=0
test_footprint exit=0
test_geo exit=0
test_gz_compare exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_deadend exit=0
test_online_mission exit=0
test_planners exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

関連修正後の再実行（両方成功）：

```text
dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed
proximity: analytic line-circle lengths, overlapping unions and tangencies passed
requested LAS case: inflated planner reports no_path without moving endpoints
online: zero radius preserves exact task014 trajectory and planning count
rollover: strict +/-90deg threshold, first time/position and immutable fake records passed
statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)
Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed
comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)
three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)
all footprint and rollover tests passed
```

```text
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)
```

## Python実験の集計表（スクリプト出力をそのまま）

```text

A: complete-map LAS test scenarios; proximity is path length within 0.5m of steep cell centres
 debris  side_m             planner  runs  solved  blocked_endpoints  length_xy_median  mean_cost_median  climb_median  p95_roll_median  steep_near_fraction_median
  False     100                  A*    48      48                  0           82.5379          0.109997      0.893688          5.13232                           0
  False     100               TA*-S    48      48                  0           79.9381          0.077131      0.697998          3.41686                           0
  False     100  TA*-S+inflate r0.5    48      48                  0           79.9381          0.077131      0.697998          3.41686                           0
  False     100 TA*-S+inflate r0.39    48      48                  0           79.9381          0.077131      0.697998          3.41686                           0
   True     100                  A*    48      48                  0           82.5391          0.130638       1.15501          5.55472                           0
   True     100               TA*-S    48      48                  0           81.3635         0.0895878       0.83999          3.67915                           0
   True     100  TA*-S+inflate r0.5    48      48                  0           81.3635         0.0895878       0.83999          3.67915                           0
   True     100 TA*-S+inflate r0.39    48      48                  0           81.3635         0.0895878       0.83999          3.67915                           0
  False     200                  A*    48      48                  0           161.023          0.116468        1.9024          5.87802                           0
  False     200               TA*-S    48      48                  0           161.296          0.077346       1.21992          3.65797                           0
  False     200  TA*-S+inflate r0.5    48      47                  0            161.28         0.0773394       1.14326          3.64844                           0
  False     200 TA*-S+inflate r0.39    48      47                  0            161.28         0.0773394       1.14326          3.64844                           0
   True     200                  A*    48      48                  0           162.354          0.163323       2.97632          7.57515                           0
   True     200               TA*-S    48      48                  0            165.22         0.0872846       1.68975          3.85708                           0
   True     200  TA*-S+inflate r0.5    48      47                  0           164.769         0.0860286       1.62638          3.83922                           0
   True     200 TA*-S+inflate r0.39    48      47                  0           164.769         0.0860286       1.62638          3.83922                           0

Inflation versus unchanged TA*-S: feasibility and paired length/cost increases
 debris  side_m             planner  lost_solutions  gained_solutions  paired_success  length_delta_median  length_delta_pct_median  cost_delta_median  cost_delta_pct_median
  False     100  TA*-S+inflate r0.5               0                 0              48                    0                        0                  0                      0
  False     100 TA*-S+inflate r0.39               0                 0              48                    0                        0                  0                      0
   True     100  TA*-S+inflate r0.5               0                 0              48                    0                        0                  0                      0
   True     100 TA*-S+inflate r0.39               0                 0              48                    0                        0                  0                      0
  False     200  TA*-S+inflate r0.5               1                 0              47                    0                        0                  0                      0
  False     200 TA*-S+inflate r0.39               1                 0              47                    0                        0                  0                      0
   True     200  TA*-S+inflate r0.5               1                 0              47                    0                        0                  0                      0
   True     200 TA*-S+inflate r0.39               1                 0              47                    0                        0                  0                      0

48 beaches as units; both sizes paired before averaging; one Holm family of 30 tests
 debris              method reference              metric  n_beaches  excluded_beaches  delta_median           p  rank_biserial      p_holm
  False               TA*-S        A*           length_xy         48                 0      -2.00027   0.0276182      -0.363946      0.6076
  False               TA*-S        A*           mean_cost         48                 0    -0.0352167 7.10543e-15             -1 2.13163e-13
  False               TA*-S        A*               climb         48                 0     -0.410943 7.10543e-15             -1 2.13163e-13
  False               TA*-S        A*            p95_roll         48                 0      -1.89098 7.10543e-15             -1 2.13163e-13
  False               TA*-S        A* steep_near_fraction         48                 0             0  0.00195312      -0.969697    0.046875
  False  TA*-S+inflate r0.5     TA*-S           length_xy         47                 1             0           1      -0.333333           1
  False  TA*-S+inflate r0.5     TA*-S           mean_cost         47                 1             0           1       0.333333           1
  False  TA*-S+inflate r0.5     TA*-S               climb         47                 1             0         0.5              1           1
  False  TA*-S+inflate r0.5     TA*-S            p95_roll         47                 1             0           1       0.333333           1
  False  TA*-S+inflate r0.5     TA*-S steep_near_fraction         47                 1             0           1             -1           1
  False TA*-S+inflate r0.39     TA*-S           length_xy         47                 1             0           1      -0.333333           1
  False TA*-S+inflate r0.39     TA*-S           mean_cost         47                 1             0           1       0.333333           1
  False TA*-S+inflate r0.39     TA*-S               climb         47                 1             0         0.5              1           1
  False TA*-S+inflate r0.39     TA*-S            p95_roll         47                 1             0           1       0.333333           1
  False TA*-S+inflate r0.39     TA*-S steep_near_fraction         47                 1             0           1             -1           1
   True               TA*-S        A*           length_xy         48                 0     -0.764155     0.94734     -0.0119048           1
   True               TA*-S        A*           mean_cost         48                 0     -0.058235 7.10543e-15             -1 2.13163e-13
   True               TA*-S        A*               climb         48                 0     -0.803948 2.13163e-14      -0.996599 5.32907e-13
   True               TA*-S        A*            p95_roll         48                 0      -2.80094 7.10543e-15             -1 2.13163e-13
   True               TA*-S        A* steep_near_fraction         48                 0             0  0.00195312             -1    0.046875
   True  TA*-S+inflate r0.5     TA*-S           length_xy         47                 1             0         0.5             -1           1
   True  TA*-S+inflate r0.5     TA*-S           mean_cost         47                 1             0         0.5              1           1
   True  TA*-S+inflate r0.5     TA*-S               climb         47                 1             0           1       0.333333           1
   True  TA*-S+inflate r0.5     TA*-S            p95_roll         47                 1             0           1             -1           1
   True  TA*-S+inflate r0.5     TA*-S steep_near_fraction         47                 1             0           1              0           1
   True TA*-S+inflate r0.39     TA*-S           length_xy         47                 1             0         0.5             -1           1
   True TA*-S+inflate r0.39     TA*-S           mean_cost         47                 1             0         0.5              1           1
   True TA*-S+inflate r0.39     TA*-S               climb         47                 1             0           1       0.333333           1
   True TA*-S+inflate r0.39     TA*-S            p95_roll         47                 1             0           1             -1           1
   True TA*-S+inflate r0.39     TA*-S steep_near_fraction         47                 1             0           1              0           1

Re-executed baseline versus archived task013 LAS results
   metric  max_abs_difference
length_xy                   0
mean_cost                   0
    climb                   0
 p95_roll                   0

B: task014 fixed prior tour order, R10; dJ vs unchanged full-truth oracle
     prior             planner  runs  completed  failed  contact_audited  touching  debris_touching  dJ_median  dJ_p90  dJ_max  replans_median  replans_max  completed_replans_median  plan_calls  plan_s_median  plan_s_p95  plan_s_max  calls_over_1s
coarse c10               TA*-S    48         45       3               48         0                0     4.2116 27.6546 58.1804           181.5          443                       175        9347      0.0324025    0.178425    0.536284              0
coarse c10  TA*-S+inflate r0.5    48         44       4               46         0                0    4.26327  28.718 75.6173           174.5          358                     174.5        8921      0.0338732    0.209061    0.796838              0
coarse c10 TA*-S+inflate r0.39    48         44       4               46         0                0    4.26327  28.718 75.6173           174.5          358                     174.5        8921      0.0345219    0.228574    0.587901              0
     stale               TA*-S    48         46       2               48         0                0   0.945069 6.60292 22.8123            94.5          224                      94.5        5428      0.0322038    0.180929    0.766565              0
     stale  TA*-S+inflate r0.5    48         45       3               46         0                0   0.994251 7.54903 99.4886            95.5          308                        98        5553      0.0351382    0.223907    0.898632              0
     stale TA*-S+inflate r0.39    48         45       3               46         0                0   0.994251 7.54903 99.4886            95.5          308                        98        5553      0.0365247    0.216726    0.757317              0

Incomplete tours (endpoints never moved)
     prior             planner           reason  runs
coarse c10               TA*-S         too_long     3
coarse c10 TA*-S+inflate r0.39 blocked_endpoint     2
coarse c10 TA*-S+inflate r0.39         too_long     2
coarse c10  TA*-S+inflate r0.5 blocked_endpoint     2
coarse c10  TA*-S+inflate r0.5         too_long     2
     stale               TA*-S         too_long     2
     stale TA*-S+inflate r0.39 blocked_endpoint     2
     stale TA*-S+inflate r0.39         too_long     1
     stale  TA*-S+inflate r0.5 blocked_endpoint     2
     stale  TA*-S+inflate r0.5         too_long     1

Re-executed online control versus task014 archive (timings independently measured)
       field  max_abs_difference
     success                   0
     n_plans                   0
   n_replans                   0
lethal_cells                   0
           J                   0
          dJ                   0
    oracle_J                   0
```

平均・中央値だけで増加を隠さないため、対が解けた場合の最大増加と、オンラインの完走が失われた・得られた件数も比較スクリプトで集計した。この後に示す比較ログ末尾に含めている。多くの条件で経路が同じで中央値が0でも、個別条件ではコスト増加がある。

## 019の転倒判定と数値保持の監査

```json
{
  "original_rows": 12,
  "original_cells_preserved": 276,
  "raw_files_preserved": 24,
  "rollover_runs": 2,
  "changed_old_result_files": [
    "results/gazebo_compare/REPORT_ja.md",
    "results/gazebo_compare/physical_run/report/runs.csv",
    "results/gazebo_compare/physical_run/report/compare_log.txt"
  ],
  "reason": "Add strict >90-degree rollover classification and first recorded event; preserve all original numeric strings and raw statuses."
}
```

変更した既存結果と理由は上の3ファイルに限定する。元の集計276セルはstatus以外を文字列のまま確認し、原記録24ファイルはSHA-256で一致を確認した。最初の転倒時刻は絶対シミュレーション時刻、経過秒は最初の記録からの差であり、閾値を超えた最初のサンプルをそのまま出している。

## Gazeboの3手法比較・未実行の扱い

追加走行は未実行。名前空間用の一時イメージは展開したが、サンドボックス外実行の権限確認が中断され、実走のプロセスは開始していない。以下のA*・TA*-Sは019の保存済み実測値、新方法は実際に計画した結果だけである。新方法の実測欄は空欄で、経路なしも「転倒しなかった走行」と数えない。

```json
{
  "baseline": "results/gazebo_compare/physical_run",
  "inflated": "results/footprint_steep/gazebo_comparison/planning_only",
  "new_physical_records": 0,
  "note": "Cached baseline numeric values reused; no raw recording changed."
}
```

```text
Task020: three-method comparison; six beaches; descriptive only, no hypothesis tests.
Unknown physical values are blank/None/NaN. Planning failure is not a rollover-free physical trial.
       patch       planner    status completed data_source             error elapsed_s deviation_mean_m deviation_max_m path_lethal_cells  roll_p95_actual_deg  pitch_p95_actual_deg  roll_max_actual_deg  pitch_max_actual_deg  climb_actual_m  map_length_xy  map_climb  map_mean_cost  map_p95_slope  map_p95_roll  map_max_roll  map_max_pitch_dir  roll_p95_recorded_xy_map_deg  pitch_p95_recorded_xy_map_deg recorded_status rolled_over  rollover_t_s  rollover_elapsed_s  rollover_x_m  rollover_y_m
08OB86_00294            A* completed      True      gazebo               NaN       166        0.0155309        0.283747                 0              4.57977               3.20701              6.34223               7.33646         1.35143         166.45    2.09937       0.116112        5.10152       4.75077       6.12944            5.80548                       4.69694                        2.93522       completed       False           NaN                 NaN           NaN           NaN
08OB86_00294         TA*-S completed      True      gazebo               NaN     161.2        0.0110132        0.293225                 0              4.16851               2.23449              5.58198               6.51558        0.889737        160.949    1.29658      0.0993425        4.54547       4.20589       5.98096             4.2124                       4.21586                        2.25498       completed       False           NaN                 NaN           NaN           NaN
08OB86_-0205            A* completed      True      gazebo               NaN    157.45         0.267778         6.19138                 0              11.8057                6.9483              19.6117                10.297         2.79364        155.085    2.98103       0.175112        13.7217       12.7104        25.748            10.3288                        10.157                        6.75867       completed       False           NaN                 NaN           NaN           NaN
08OB86_-0205         TA*-S completed      True      gazebo               NaN       154        0.0698109         3.31719                 0              3.13187               1.88349              5.27948               5.86883        0.912171        156.831    1.13326      0.0794646        3.78309       3.18944       5.69173            9.61358                        3.0554                        2.02659       completed       False           NaN                 NaN           NaN           NaN
08OB87_-0706            A* completed      True      gazebo               NaN    163.55        0.0217786        0.266098                 0              5.14706               3.18229              6.40325               7.10212        0.721888        164.493    1.57973       0.129899        5.96148       5.12886        6.6874            6.96167                       5.14935                        3.59127       completed       False           NaN                 NaN           NaN           NaN
08OB87_-0706         TA*-S completed      True      gazebo               NaN    159.15       0.00647007        0.128161                 0              3.15048               2.63982              5.63635               5.22304        0.506069        159.351   0.812158      0.0835471        4.15879       3.34804       4.86051            4.61208                       3.34949                        3.03682       completed       False           NaN                 NaN           NaN           NaN
08OB88_-1417            A* completed      True      gazebo               NaN    154.45        0.0154969        0.227642                 0              5.21845               2.35925              9.30999               7.15519         1.23867        155.002    1.74114       0.115239        5.36712       5.08998       8.37479             5.8079                       5.09578                        2.50166       completed       False           NaN                 NaN           NaN           NaN
08OB88_-1417         TA*-S completed      True      gazebo               NaN    155.05       0.00410578         0.23445                 0              2.29267              0.807219              3.49959               3.37278         0.52038        155.199   0.733826      0.0526041         2.5868       2.41772       3.07078            3.11248                       2.38563                       0.820092       completed       False           NaN                 NaN           NaN           NaN
08OB88_-0167            A*  rollover     False      gazebo               NaN     144.5         0.843477          5.2174                90              167.111               33.0629              176.682               43.7947         9.66845         157.68    8.10689       0.451117        33.7886       33.6112       39.1973            25.4503                       31.8871                        18.1473           stuck        True         138.9               133.8       155.523       138.025
08OB88_-0167         TA*-S  rollover     False      gazebo               NaN    271.45        0.0796587         1.28426                 9              13.2141                26.281               176.26                79.867         7.44885        289.767    7.90873       0.137976        10.2882       5.98149       18.0338            23.7975                       5.80491                        9.28437           stuck        True        265.35              260.25       196.387       141.841
08OB88_00332            A* completed      True      gazebo               NaN     174.4        0.0105396        0.285094                 0              4.04249               4.76705              8.38286               12.5081        0.281719        174.858   0.599038      0.0863766        5.70541        3.8628       6.83518            10.9966                       3.87505                        4.69552       completed       False           NaN                 NaN           NaN           NaN
08OB88_00332         TA*-S completed      True      gazebo               NaN     171.3       0.00999076         0.39661                 0              3.77867               4.55179              5.11535               9.66308        0.231823         170.97    0.38637      0.0749039        5.37827       3.75626       5.20394            9.60764                       3.69879                        4.28301       completed       False           NaN                 NaN           NaN           NaN
08OB86_00294 TA*-S+inflate       未実行      None        None                        None             None            None              None                  NaN                   NaN                  NaN                   NaN             NaN        160.949    1.29658      0.0993425        4.54547       4.20589       5.98096             4.2124                           NaN                            NaN            None        None           NaN                 NaN           NaN           NaN
08OB86_-0205 TA*-S+inflate       未実行      None        None                        None             None            None              None                  NaN                   NaN                  NaN                   NaN             NaN        156.831    1.13326      0.0794646        3.78309       3.18944       5.69173            9.61358                           NaN                            NaN            None        None           NaN                 NaN           NaN           NaN
08OB87_-0706 TA*-S+inflate       未実行      None        None                        None             None            None              None                  NaN                   NaN                  NaN                   NaN             NaN        159.351   0.812158      0.0835471        4.15879       3.34804       4.86051            4.61208                           NaN                            NaN            None        None           NaN                 NaN           NaN           NaN
08OB88_-1417 TA*-S+inflate       未実行      None        None                        None             None            None              None                  NaN                   NaN                  NaN                   NaN             NaN        155.199   0.733826      0.0526041         2.5868       2.41772       3.07078            3.11248                           NaN                            NaN            None        None           NaN                 NaN           NaN           NaN
08OB88_-0167 TA*-S+inflate   no_path     False        None planning: no_path      None             None            None              None                  NaN                   NaN                  NaN                   NaN             NaN            NaN        NaN            NaN            NaN           NaN           NaN                NaN                           NaN                            NaN            None        None           NaN                 NaN           NaN           NaN
08OB88_00332 TA*-S+inflate       未実行      None        None                        None             None            None              None                  NaN                   NaN                  NaN                   NaN             NaN         170.97    0.38637      0.0749039        5.37827       3.75626       5.20394            9.60764                           NaN                            NaN            None        None           NaN                 NaN           NaN           NaN

Planning/execution denominators (rollovers among executed recordings only)
      planner  scenarios  planning_failed  executed  completed  rolled_over  unexecuted
           A*          6                0         6          5            1           0
        TA*-S          6                0         6          5            1           0
TA*-S+inflate          6                1         0        NaN          NaN           5

Paired median method minus reference; only both completed without rollover
       method reference               metric  paired_completed  delta_median
        TA*-S        A*            elapsed_s                 5         -3.45
        TA*-S        A*     deviation_mean_m                 5    -0.0113911
        TA*-S        A*      deviation_max_m                 5    0.00680795
        TA*-S        A*    path_lethal_cells                 5             0
        TA*-S        A*  roll_p95_actual_deg                 5      -1.99658
        TA*-S        A* pitch_p95_actual_deg                 5     -0.972516
        TA*-S        A*  roll_max_actual_deg                 5      -3.26751
        TA*-S        A* pitch_max_actual_deg                 5      -2.84502
        TA*-S        A*       climb_actual_m                 5     -0.461692
TA*-S+inflate        A*            elapsed_s                 0           NaN
TA*-S+inflate        A*     deviation_mean_m                 0           NaN
TA*-S+inflate        A*      deviation_max_m                 0           NaN
TA*-S+inflate        A*    path_lethal_cells                 0           NaN
TA*-S+inflate        A*  roll_p95_actual_deg                 0           NaN
TA*-S+inflate        A* pitch_p95_actual_deg                 0           NaN
TA*-S+inflate        A*  roll_max_actual_deg                 0           NaN
TA*-S+inflate        A* pitch_max_actual_deg                 0           NaN
TA*-S+inflate        A*       climb_actual_m                 0           NaN
TA*-S+inflate     TA*-S            elapsed_s                 0           NaN
TA*-S+inflate     TA*-S     deviation_mean_m                 0           NaN
TA*-S+inflate     TA*-S      deviation_max_m                 0           NaN
TA*-S+inflate     TA*-S    path_lethal_cells                 0           NaN
TA*-S+inflate     TA*-S  roll_p95_actual_deg                 0           NaN
TA*-S+inflate     TA*-S pitch_p95_actual_deg                 0           NaN
TA*-S+inflate     TA*-S  roll_max_actual_deg                 0           NaN
TA*-S+inflate     TA*-S pitch_max_actual_deg                 0           NaN
TA*-S+inflate     TA*-S       climb_actual_m                 0           NaN

Offline increases versus TA*-S (descriptive maxima, no extra tests)
 debris  side_m             planner  paired_success  lost_solutions  length_xy_increased_cases  length_xy_delta_max  length_xy_delta_pct_p90  length_xy_delta_pct_max  mean_cost_increased_cases  mean_cost_delta_max  mean_cost_delta_pct_p90  mean_cost_delta_pct_max
  False     100  TA*-S+inflate r0.5              48               0                          0                    0                        0                        0                          1           0.00368178                        0                  2.70963
  False     100 TA*-S+inflate r0.39              48               0                          0                    0                        0                        0                          1           0.00368178                        0                  2.70963
  False     200  TA*-S+inflate r0.5              47               1                          1             0.362239                        0                 0.183231                          0                    0                        0                        0
  False     200 TA*-S+inflate r0.39              47               1                          1             0.362239                        0                 0.183231                          0                    0                        0                        0
   True     100  TA*-S+inflate r0.5              48               0                          0                    0                        0                        0                          1           0.00983083                        0                  7.01709
   True     100 TA*-S+inflate r0.39              48               0                          0                    0                        0                        0                          1           0.00983083                        0                  7.01709
   True     200  TA*-S+inflate r0.5              47               1                          0                    0                        0                        0                          1          0.000141689                        0                0.0953843
   True     200 TA*-S+inflate r0.39              47               1                          0                    0                        0                        0                          1          0.000141689                        0                0.0953843

Online paired changes versus unchanged TA*-S (descriptive, no extra tests)
     prior             planner  paired_success  lost_completed  gained_completed  J_delta_median  J_delta_pct_p90  J_delta_pct_max  length_delta_pct_max
coarse c10  TA*-S+inflate r0.5              43               2                 1               0         0.507015          7.81397               3.94511
coarse c10 TA*-S+inflate r0.39              43               2                 1               0         0.507015          7.81397               3.94511
     stale  TA*-S+inflate r0.5              44               2                 1               0          1.19015          62.4337               60.0615
     stale TA*-S+inflate r0.39              44               2                 1               0          1.19015          62.4337               60.0615
```

追加走行に使うコマンド（準備済み、未実行）：

```bash
cd conference
bash ros2_jazzy/gz_checks/run_compare_checks.sh results/footprint_steep/gazebo_inflate --planners 'TA*-S+inflate'
python3 experiments/footprint_report.py --inflated results/footprint_steep/gazebo_inflate
```

`THESIS_ROS_IMAGE` で利用可能なイメージを指定できる。既存manifestのある保存先は上書きせず停止する。計画だけの検証フォルダは `gazebo_comparison/planning_only/` とし、実走の保存先と分けている。

## 問題の地形の図と解釈

[019の計画・実測、追加した急斜面の余裕、最初の転倒地点の全体図と拡大図](08OB88_-0167_clearance.png)

この図は元の019の計画と原記録を使った。膨張版はこの200mシナリオで経路なしとなったため、新しい経路を描いていない。端点は動かしていない。図は目視確認した。

[3手法の転倒例の比較図](gazebo_comparison/08OB88_-0167.png) では、019の実測2本と、新方法の計画不可を明記した。実測線がないことを転倒抑制の実証として解釈しない。

膨張で通れる場所が減ることと、物理的に転倒しなくなることは分けて評価する必要がある。今回、転倒した地形が計画不可に変わった。新方法の実走をしていないため、転倒の抑制効果は未検証である。格子上の円盤とセル中心を使う近接率は車体形状の近似で、追従ずれまで保証しない。模型の横の摩擦 `mu2=0.1` と、角速度上限1.0rad/sでの急旋回などの仮定は変更しておらず、膨張しても転倒は残りうる。6地形でのGazeboの比較に検定は行わない。

## 既存ファイルと原記録の保存

作業前の1448ファイルのSHA-256と比較した結果：

```json
{
  "baseline_files": 1448,
  "changed": [
    "conference/experiments/gz_compare_report.py",
    "conference/results/gazebo_compare/REPORT_ja.md",
    "conference/results/gazebo_compare/physical_run/report/compare_log.txt",
    "conference/results/gazebo_compare/physical_run/report/runs.csv",
    "conference/ros2_jazzy/gz_checks/compare_checks.py",
    "conference/ros2_jazzy/gz_checks/run_compare_checks.sh"
  ]
}
```

変更は禁止対象の例外として020が指定した集計・比較用ファイルに限定した。`run_compare_checks.sh` は選択した手法をDocker内の比較スクリプトへ渡すための引数転送だけを追加し、既定のA*・TA*-Sは維持した。既存の地形データ、地図、world、元の走行記録、旧プランナー・オンライン処理は変更していない。

## 変更ファイル一覧

<details><summary>コード・検証・CSV・キャッシュ・図の全ファイル</summary>

- `conference/experiments/footprint_annotation.py`
- `conference/experiments/footprint_report.py`
- `conference/experiments/footprint_steep.py`
- `conference/experiments/gz_compare_report.py`
- `conference/results/footprint_steep/08OB88_-0167_clearance.png`
- `conference/results/footprint_steep/README_ja.md`
- `conference/results/footprint_steep/REPORT_ja.md`
- `conference/results/footprint_steep/all_log.txt`
- `conference/results/footprint_steep/changed_files.txt`
- `conference/results/footprint_steep/comparison_console_log.txt`
- `conference/results/footprint_steep/execution.json`
- `conference/results/footprint_steep/experiment_console_log.txt`
- `conference/results/footprint_steep/gazebo_comparison/08OB86_-0205.png`
- `conference/results/footprint_steep/gazebo_comparison/08OB86_00294.png`
- `conference/results/footprint_steep/gazebo_comparison/08OB87_-0706.png`
- `conference/results/footprint_steep/gazebo_comparison/08OB88_-0167.png`
- `conference/results/footprint_steep/gazebo_comparison/08OB88_-1417.png`
- `conference/results/footprint_steep/gazebo_comparison/08OB88_00332.png`
- `conference/results/footprint_steep/gazebo_comparison/comparison_log.txt`
- `conference/results/footprint_steep/gazebo_comparison/paired_differences.csv`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/manifest.json`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/maps/real_las_08OB86_-0205_200m_0.npz`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/maps/real_las_08OB86_00294_200m_0.npz`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/maps/real_las_08OB87_-0706_200m_0.npz`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/maps/real_las_08OB88_-0167_200m_0.npz`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/maps/real_las_08OB88_-1417_200m_0.npz`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/maps/real_las_08OB88_00332_200m_0.npz`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/report/compare_log.txt`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/report/paired_differences.csv`
- `conference/results/footprint_steep/gazebo_comparison/planning_only/report/runs.csv`
- `conference/results/footprint_steep/gazebo_comparison/runs.csv`
- `conference/results/footprint_steep/gazebo_comparison/sources.json`
- `conference/results/footprint_steep/gazebo_comparison/summary.csv`
- `conference/results/footprint_steep/offline.csv`
- `conference/results/footprint_steep/offline_baseline_audit.csv`
- `conference/results/footprint_steep/offline_cache/08OB86_-0205_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB86_-0205_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB86_-0205_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB86_-0205_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB86_00294_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB86_00294_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB86_00294_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB86_00294_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB87_-0706_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB87_-0706_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB87_-0706_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB87_-0706_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-0167_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-0167_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-0167_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-0167_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-1417_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-1417_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-1417_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_-1417_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_00332_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_00332_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_00332_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_00332_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_01832_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_01832_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB88_01832_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB88_01832_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0347_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0347_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0347_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0347_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0847_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0847_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0847_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB89_-0847_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OB89_00152_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OB89_00152_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OB89_00152_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OB89_00152_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-0589_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-0589_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-0589_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-0589_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-1089_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-1089_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-1089_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_-1089_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00160_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00160_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00160_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00160_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00660_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00660_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00660_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC80_00660_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0438_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0438_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0438_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0438_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0938_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0938_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0938_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-0938_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-1688_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-1688_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-1688_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_-1688_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_00061_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_00061_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_00061_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_00061_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_01311_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_01311_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC91_01311_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC91_01311_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0141_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0141_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0141_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0141_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0891_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0891_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0891_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC92_-0891_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC92_00608_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC92_00608_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC92_00608_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC92_00608_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC94_-0954_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC94_-0954_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC94_-0954_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC94_-0954_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-0821_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-0821_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-0821_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-0821_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-1321_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-1321_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-1321_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-1321_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-2071_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-2071_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-2071_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_-2071_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00428_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00428_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00428_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00428_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00928_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00928_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00928_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_00928_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_01428_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_01428_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC95_01428_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC95_01428_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC96_-1426_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC96_-1426_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC96_-1426_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC96_-1426_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC96_00073_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC96_00073_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC96_00073_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC96_00073_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-0577_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-0577_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-0577_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-0577_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1077_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1077_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1077_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1077_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1827_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1827_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1827_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_-1827_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_00422_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_00422_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_00422_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_00422_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01172_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01172_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01172_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01172_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01672_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01672_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01672_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC97_01672_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-0351_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-0351_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-0351_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-0351_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-1601_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-1601_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-1601_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_-1601_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00148_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00148_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00148_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00148_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00648_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00648_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00648_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_00648_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_01398_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_01398_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC98_01398_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC98_01398_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-0016_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-0016_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-0016_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-0016_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1016_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1016_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1016_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1016_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1516_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1516_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1516_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_-1516_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_00483_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_00483_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_00483_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_00483_200_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_01733_100_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_01733_100_1.json`
- `conference/results/footprint_steep/offline_cache/08OC99_01733_200_0.json`
- `conference/results/footprint_steep/offline_cache/08OC99_01733_200_1.json`
- `conference/results/footprint_steep/offline_cache/08PD00_-1730_100_0.json`
- `conference/results/footprint_steep/offline_cache/08PD00_-1730_100_1.json`
- `conference/results/footprint_steep/offline_cache/08PD00_-1730_200_0.json`
- `conference/results/footprint_steep/offline_cache/08PD00_-1730_200_1.json`
- `conference/results/footprint_steep/offline_increase_audit.csv`
- `conference/results/footprint_steep/offline_penalties.csv`
- `conference/results/footprint_steep/offline_statistics.csv`
- `conference/results/footprint_steep/offline_summary.csv`
- `conference/results/footprint_steep/online.csv`
- `conference/results/footprint_steep/online_baseline_audit.csv`
- `conference/results/footprint_steep/online_cache/08OB86_-0205.json.gz`
- `conference/results/footprint_steep/online_cache/08OB86_00294.json.gz`
- `conference/results/footprint_steep/online_cache/08OB87_-0706.json.gz`
- `conference/results/footprint_steep/online_cache/08OB88_-0167.json.gz`
- `conference/results/footprint_steep/online_cache/08OB88_-1417.json.gz`
- `conference/results/footprint_steep/online_cache/08OB88_00332.json.gz`
- `conference/results/footprint_steep/online_cache/08OB88_01832.json.gz`
- `conference/results/footprint_steep/online_cache/08OB89_-0347.json.gz`
- `conference/results/footprint_steep/online_cache/08OB89_-0847.json.gz`
- `conference/results/footprint_steep/online_cache/08OB89_00152.json.gz`
- `conference/results/footprint_steep/online_cache/08OC80_-0589.json.gz`
- `conference/results/footprint_steep/online_cache/08OC80_-1089.json.gz`
- `conference/results/footprint_steep/online_cache/08OC80_00160.json.gz`
- `conference/results/footprint_steep/online_cache/08OC80_00660.json.gz`
- `conference/results/footprint_steep/online_cache/08OC91_-0438.json.gz`
- `conference/results/footprint_steep/online_cache/08OC91_-0938.json.gz`
- `conference/results/footprint_steep/online_cache/08OC91_-1688.json.gz`
- `conference/results/footprint_steep/online_cache/08OC91_00061.json.gz`
- `conference/results/footprint_steep/online_cache/08OC91_01311.json.gz`
- `conference/results/footprint_steep/online_cache/08OC92_-0141.json.gz`
- `conference/results/footprint_steep/online_cache/08OC92_-0891.json.gz`
- `conference/results/footprint_steep/online_cache/08OC92_00608.json.gz`
- `conference/results/footprint_steep/online_cache/08OC94_-0954.json.gz`
- `conference/results/footprint_steep/online_cache/08OC95_-0821.json.gz`
- `conference/results/footprint_steep/online_cache/08OC95_-1321.json.gz`
- `conference/results/footprint_steep/online_cache/08OC95_-2071.json.gz`
- `conference/results/footprint_steep/online_cache/08OC95_00428.json.gz`
- `conference/results/footprint_steep/online_cache/08OC95_00928.json.gz`
- `conference/results/footprint_steep/online_cache/08OC95_01428.json.gz`
- `conference/results/footprint_steep/online_cache/08OC96_-1426.json.gz`
- `conference/results/footprint_steep/online_cache/08OC96_00073.json.gz`
- `conference/results/footprint_steep/online_cache/08OC97_-0577.json.gz`
- `conference/results/footprint_steep/online_cache/08OC97_-1077.json.gz`
- `conference/results/footprint_steep/online_cache/08OC97_-1827.json.gz`
- `conference/results/footprint_steep/online_cache/08OC97_00422.json.gz`
- `conference/results/footprint_steep/online_cache/08OC97_01172.json.gz`
- `conference/results/footprint_steep/online_cache/08OC97_01672.json.gz`
- `conference/results/footprint_steep/online_cache/08OC98_-0351.json.gz`
- `conference/results/footprint_steep/online_cache/08OC98_-1601.json.gz`
- `conference/results/footprint_steep/online_cache/08OC98_00148.json.gz`
- `conference/results/footprint_steep/online_cache/08OC98_00648.json.gz`
- `conference/results/footprint_steep/online_cache/08OC98_01398.json.gz`
- `conference/results/footprint_steep/online_cache/08OC99_-0016.json.gz`
- `conference/results/footprint_steep/online_cache/08OC99_-1016.json.gz`
- `conference/results/footprint_steep/online_cache/08OC99_-1516.json.gz`
- `conference/results/footprint_steep/online_cache/08OC99_00483.json.gz`
- `conference/results/footprint_steep/online_cache/08OC99_01733.json.gz`
- `conference/results/footprint_steep/online_cache/08PD00_-1730.json.gz`
- `conference/results/footprint_steep/online_failures.csv`
- `conference/results/footprint_steep/online_paired_audit.csv`
- `conference/results/footprint_steep/online_summary.csv`
- `conference/results/footprint_steep/plan_times_08OB86_-0205_0.csv`
- `conference/results/footprint_steep/plan_times_08OB86_00294_0.csv`
- `conference/results/footprint_steep/plan_times_08OB87_-0706_0.csv`
- `conference/results/footprint_steep/plan_times_08OB88_-0167_0.csv`
- `conference/results/footprint_steep/plan_times_08OB88_-1417_0.csv`
- `conference/results/footprint_steep/plan_times_08OB88_00332_0.csv`
- `conference/results/footprint_steep/plan_times_08OB88_01832_0.csv`
- `conference/results/footprint_steep/plan_times_08OB89_-0347_0.csv`
- `conference/results/footprint_steep/plan_times_08OB89_-0847_0.csv`
- `conference/results/footprint_steep/plan_times_08OB89_00152_0.csv`
- `conference/results/footprint_steep/plan_times_08OC80_-0589_0.csv`
- `conference/results/footprint_steep/plan_times_08OC80_-1089_0.csv`
- `conference/results/footprint_steep/plan_times_08OC80_00160_0.csv`
- `conference/results/footprint_steep/plan_times_08OC80_00660_0.csv`
- `conference/results/footprint_steep/plan_times_08OC91_-0438_0.csv`
- `conference/results/footprint_steep/plan_times_08OC91_-0938_0.csv`
- `conference/results/footprint_steep/plan_times_08OC91_-1688_0.csv`
- `conference/results/footprint_steep/plan_times_08OC91_00061_0.csv`
- `conference/results/footprint_steep/plan_times_08OC91_01311_0.csv`
- `conference/results/footprint_steep/plan_times_08OC92_-0141_0.csv`
- `conference/results/footprint_steep/plan_times_08OC92_-0891_0.csv`
- `conference/results/footprint_steep/plan_times_08OC92_00608_0.csv`
- `conference/results/footprint_steep/plan_times_08OC94_-0954_0.csv`
- `conference/results/footprint_steep/plan_times_08OC95_-0821_0.csv`
- `conference/results/footprint_steep/plan_times_08OC95_-1321_0.csv`
- `conference/results/footprint_steep/plan_times_08OC95_-2071_0.csv`
- `conference/results/footprint_steep/plan_times_08OC95_00428_0.csv`
- `conference/results/footprint_steep/plan_times_08OC95_00928_0.csv`
- `conference/results/footprint_steep/plan_times_08OC95_01428_0.csv`
- `conference/results/footprint_steep/plan_times_08OC96_-1426_0.csv`
- `conference/results/footprint_steep/plan_times_08OC96_00073_0.csv`
- `conference/results/footprint_steep/plan_times_08OC97_-0577_0.csv`
- `conference/results/footprint_steep/plan_times_08OC97_-1077_0.csv`
- `conference/results/footprint_steep/plan_times_08OC97_-1827_0.csv`
- `conference/results/footprint_steep/plan_times_08OC97_00422_0.csv`
- `conference/results/footprint_steep/plan_times_08OC97_01172_0.csv`
- `conference/results/footprint_steep/plan_times_08OC97_01672_0.csv`
- `conference/results/footprint_steep/plan_times_08OC98_-0351_0.csv`
- `conference/results/footprint_steep/plan_times_08OC98_-1601_0.csv`
- `conference/results/footprint_steep/plan_times_08OC98_00148_0.csv`
- `conference/results/footprint_steep/plan_times_08OC98_00648_0.csv`
- `conference/results/footprint_steep/plan_times_08OC98_01398_0.csv`
- `conference/results/footprint_steep/plan_times_08OC99_-0016_0.csv`
- `conference/results/footprint_steep/plan_times_08OC99_-1016_0.csv`
- `conference/results/footprint_steep/plan_times_08OC99_-1516_0.csv`
- `conference/results/footprint_steep/plan_times_08OC99_00483_0.csv`
- `conference/results/footprint_steep/plan_times_08OC99_01733_0.csv`
- `conference/results/footprint_steep/plan_times_08PD00_-1730_0.csv`
- `conference/results/footprint_steep/protocol.json`
- `conference/results/footprint_steep/rollover_annotation_audit.json`
- `conference/results/footprint_steep/rollover_annotation_log.txt`
- `conference/results/footprint_steep/rollover_events.csv`
- `conference/results/footprint_steep/verification/all_tests_log.txt`
- `conference/results/footprint_steep/verification/annotation_log.txt`
- `conference/results/footprint_steep/verification/baseline_audit.json`
- `conference/results/footprint_steep/verification/environment_log.txt`
- `conference/results/footprint_steep/verification/oci_extract_log.txt`
- `conference/results/footprint_steep/verification/online_smoke_log.txt`
- `conference/results/footprint_steep/verification/planners_before_log.txt`
- `conference/results/footprint_steep/verification/test_beach_terrain_log.txt`
- `conference/results/footprint_steep/verification/test_collision_log.txt`
- `conference/results/footprint_steep/verification/test_dstar_log.txt`
- `conference/results/footprint_steep/verification/test_footprint_final_log.txt`
- `conference/results/footprint_steep/verification/test_footprint_initial_log.txt`
- `conference/results/footprint_steep/verification/test_footprint_log.txt`
- `conference/results/footprint_steep/verification/test_geo_log.txt`
- `conference/results/footprint_steep/verification/test_gz_compare_final_log.txt`
- `conference/results/footprint_steep/verification/test_gz_compare_log.txt`
- `conference/results/footprint_steep/verification/test_mapfiles_sim_log.txt`
- `conference/results/footprint_steep/verification/test_mission_log.txt`
- `conference/results/footprint_steep/verification/test_natural_terrain_log.txt`
- `conference/results/footprint_steep/verification/test_online_deadend_log.txt`
- `conference/results/footprint_steep/verification/test_online_log.txt`
- `conference/results/footprint_steep/verification/test_online_mission_log.txt`
- `conference/results/footprint_steep/verification/test_planners_log.txt`
- `conference/results/footprint_steep/verification/test_real_beach_las_log.txt`
- `conference/results/footprint_steep/verification/test_real_beach_log.txt`
- `conference/results/footprint_steep/verification/test_risk_prior_log.txt`
- `conference/results/footprint_steep/verification/test_ros2_gz_log.txt`
- `conference/results/footprint_steep/verification/test_summary.txt`
- `conference/results/footprint_steep/verification/test_thesis_figures_log.txt`
- `conference/results/footprint_steep/verification/test_tour_log.txt`
- `conference/results/footprint_steep/verification/test_visibility_log.txt`
- `conference/results/footprint_steep/verification/unexecuted_namespace_run.sh`
- `conference/results/gazebo_compare/REPORT_ja.md`
- `conference/results/gazebo_compare/physical_run/report/compare_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs.csv`
- `conference/ros2_jazzy/gz_checks/compare_checks.py`
- `conference/ros2_jazzy/gz_checks/run_compare_checks.sh`
- `conference/tapp/footprint.py`
- `conference/tests/test_footprint.py`

</details>
