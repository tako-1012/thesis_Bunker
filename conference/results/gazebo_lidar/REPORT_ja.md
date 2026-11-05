# 指示書022：VLP-16相当の点群からの地図更新と再計画

基準日：2026-11-05（利用者の日付、日本時間）。
ブランチ：`codex/022-gazebo-lidar`。基点：`5cd80458dc95e341ff2eef29f150fc92d82723cc`。021のマージ後の最新 `realtime-map` から独立して作成し、マージしていない。

**LiDARの実走は未実行**。点群処理・連携スクリプト・集計・テストまで実装した。

## 実装したもの

- `tapp/pointcloud_map.py`：`decode_xyz`、`transform_points`、`PoseBuffer.add/at`、`PointCloudMap.update/snapshot/save`。PointCloud2互換バッファのデコード、時刻付き姿勢のSO(3)補間、6自由度の座標変換、0.5mセルの中央値融合、観測済みマスク、事前高さを基準にした障害物検出、既存式による傾斜・凸凹・コストと0.5m膨張。
- `thesis_bunker_gz/model.py`：LiDARなしを既定に保つキーワード引数を追加。`lidar.py` に設定とgpu_lidar生成を置き、通常と質量指定の既存SDFのバイト一致を検証した。
- `lidar_bridge.yaml`：PointCloudPackedをROS2のPointCloud2へ渡す。既存bridgeは変更していない。
- `lidar_runtime.py`：`LidarOnlineMission._plan_work/_join`。021の非同期計画・経路引き継ぎを再利用し、観測の両箇所を点群由来に置換。truthはNoneで、virtual_senseを呼ばないことをテストした。
- `lidar_planner.py`：真値地図をロードせず、古い地図・点群・点群時刻のground_truth姿勢だけを使うROS2ノード。別ワーカー、最新1走査の待ち行列、時刻不一致の拒否、センサー停止要求、全探索と地図更新の記録を追加した。
- `lidar_checks.py` と `run_lidar_checks.sh`：021の保存済みの10地形・地点・順番を共有し、最初の3か所から10か所へ広げる。world/入力地図/colconは一時領域。実走時の解析用参照配列を保存する。
- `experiments/gz_lidar_report.py`：`map_quality/tables/summarize`。021の20行の保存値とLiDARの10行を並べ、同じ走行項目、最終観測セルの高さ誤差、地図更新時間を集計する。欠測はNone/NaN/空欄のまま、検定・エネルギー集計は行わない。
- `tests/test_pointcloud_map.py`：平地、箱、未知セル、座標・時刻・データ形式、既存模型、真値を使わないワーカーと経路引き継ぎ、誤差集計、保存済み対照の不変性を確認する。
- `experiments/pointcloud_validation.py`：事前固定した設定でvalidation12地形の人工入力を監査する。パラメータを選択・調整するスクリプトではない。

## 仕様・仮定

利用者から示されたVLP-16の公称値に合わせ、16本、垂直−15°〜+15°を2°刻み、水平360°、10Hzとした。
水平方向1800サンプル、最小距離0.1m、距離の刻み0.01m、平均0・標準偏差0.02mのGaussian測距雑音は未校正の模型の仮定である。
最大距離30mは指示書の条件を維持し、0.5m地図での近傍再計画を扱う試験として描画・処理量を抑えるための上限とした。
実機の100mを検証した値でも、testの成績から最適化した距離でもない。R10対照とは範囲も異なり、遮蔽だけの効果の比較にはならない。

取り付け高さ0.8mは実測値不明のため、017に合わせた仮定である。モデル原点（平地での接地時は地面付近）から車体z方向に測る。
base_linkの原点が0.35mなので、センサーの局所zは `height-0.35` とする。傾斜で地面から常に鉛直0.8mという意味ではない。
`--sensor-height-m` で変更でき、モデルと座標変換に同じ値を渡す。水平の取付位置はモデル中央、姿勢は車体と同じという仮定である。

漂着物の高さ判定0.3mは、017の仮定の流木高さを参考に事前固定した未校正の仮定である。
古い地図の高さの双線形補間より0.3m以上高い点が同じセルに3点以上ある場合に検出する。
実測の地面分離ではなく、地形変化・位置誤差を障害物と誤認することもある。testで閾値や半径を調整していない。
セルの高さは直近64点の中央値で、障害物上面しか見えなければ地面ではなく上面を表す。
既に検出した障害物は保持し、移動物体が去った後の除去や光線による空き領域の推定は行わない。

点のないセルは未知のままで、特徴量の周辺再計算・膨張をしても観測済みに昇格させない。
未知部分は021と同じsoft priorに依存するため、未観測の危険箇所へ進むことはありうる。
時刻の合う姿勢がない点群は使わず、真値ラベルや最新姿勢で穴埋めしない。最大距離で飽和した返り値も地形にしない。
実機の発光順、走査中の運動歪み、反射率・水面・欠測の特性は再現していない。
017は地表セルへ直接視線を調べるモデルであり、今回の疎な上下方向の走査線とは観測条件が違う。

```json
{
  "client_date": "2026-11-05",
  "base": "5cd80458dc95e341ff2eef29f150fc92d82723cc",
  "branch": "codex/022-gazebo-lidar",
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "platform": "Linux-6.18.57-x86_64-with-glibc2.41",
  "versions": {
    "numpy": "2.3.5",
    "scipy": "1.17.0",
    "pandas": "2.2.3",
    "matplotlib": "3.10.8",
    "fastapi": "0.141.1",
    "pydantic": "2.13.4"
  },
  "sensor": {
    "vertical_samples": 16,
    "vertical_min_deg": -15.0,
    "vertical_max_deg": 15.0,
    "horizontal_samples": 1800,
    "update_hz": 10.0,
    "min_range_m": 0.1,
    "max_range_m": 30.0,
    "noise_stddev_m": 0.02,
    "range_resolution_m": 0.01
  },
  "sensor_height_m": 0.8,
  "obstacle_height_m": 0.3,
  "assumptions": "fixed before validation/test, not calibrated; no parameter selection",
  "parameter_audit": "validation 12 dense artificial DEM clouds, not physical LiDAR measurements",
  "lidar_physical_recordings": 0,
  "source_sha256": {
    "experiments/gz_lidar_report.py": "1d22164edd41699589a817b9aaa7fb38b551e9b2edb43b6c2046911d96df502c",
    "experiments/pointcloud_validation.py": "5c2c88bc31d176a5d843cf14eb5e19375b4c9e6a65367b342c901ee406274ef4",
    "ros2_jazzy/gz_checks/lidar_bridge.yaml": "c55ded0c1765d819f3441495b94c4b7160681dad076a51b10e1eb93d860d22da",
    "ros2_jazzy/gz_checks/lidar_checks.py": "746bee57f257c638235f172f7838e590154ab0032de50096ceef52f07e557705",
    "ros2_jazzy/gz_checks/lidar_planner.py": "178f8302e695e520f06d2f0229b97b20cfda47252deaa810f8a1f4ed7a7182df",
    "ros2_jazzy/gz_checks/lidar_runtime.py": "7f002824bec9bcca5a81800dbe59100f0aca694f29c668c720b8b011ece97f35",
    "ros2_jazzy/gz_checks/run_lidar_checks.sh": "49e279b05a9257a53c40e028a24042699c9bdbf03b9e5cf55c502a36aad96e80",
    "ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/__init__.py": "372cbf9480a2374ddd005b4e0bd10a55669e7878b404c5dad0242ff40be1ef9f",
    "ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/lidar.py": "5016dcda408ceda2fa0bd278b42fbfd6f64b50b7f7a9bfd77f1b11802e6c87d6",
    "ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/model.py": "333ce26289b241881c081c6b21c4ba737d00213d95ee3425cc0dc9f9dbe1b7a2",
    "tapp/__init__.py": "6a7303859dfc82ceb05625b64cad5ecba7d947bc6b7a3151d241ab8a34c336c6",
    "tapp/aniso.py": "0bcf1d6474ecb451374b20c6289b3557d67585582ab4560c479ac4ae2559d282",
    "tapp/beach_scenario.py": "e481f68612cf5337f2ec0e3654c8e5fb13cae526a8e757c1e22692dc9efb5528",
    "tapp/beach_terrain.py": "837b9a80cfc8cb79714531e3c010ad7b12ce068a93de6ddb0ca8dedc65966017",
    "tapp/collision.py": "d70551c6bda534a8fdccdc87e20f6599f64fc1b484721fc643158b9b9b9d5f95",
    "tapp/config.py": "5c4cfe860b16f2d4540e970f2ca19a634f563a24deb361d0e85b7daa6e6c7895",
    "tapp/directional.py": "97d7cedcacd6f4883969ced561c8aa79cbbaac15b7f72832ba0316127ac2aba4",
    "tapp/dstar_lite.py": "9bb2a4a801a2e5143822eb1fb7eb834b1fb879b2fe023a6da7de26b8213108a9",
    "tapp/exact_planners.py": "e33e53cbc64ff281c4f9f764de4b910d38dd867abea41dfbd4fd93ea95c3f3ea",
    "tapp/follower.py": "73aa7556390a43f1ddff7e02aa02cf6e43844204a8511bc5d7b77e344de54034",
    "tapp/footprint.py": "2dcfd352570fbbcd9666439dbfeecd1d98fc911e083ff5f489d1a6c7739b1b4e",
    "tapp/geo.py": "a46cad85748b27610be65f53359aff32e85be8e6c63a9d5c20b5c61446c2ab5a",
    "tapp/mapfile.py": "d113b98de911cb86671bbe4087e160f7bc24d735059a2cd01cd269b2e982d6ed",
    "tapp/metrics.py": "ca47f87528abd20e8c87be461d53f5f28a901e9e120cfe6201e6bcf8931d4d1b",
    "tapp/mission.py": "bc1a43794f3a0e9d78792fa6b933719d659e28184b61e286d41c3d402356d24e",
    "tapp/natural_scenario.py": "24f9a2813c3c91d727a01c92f60f7f93f117435b83610abe460d04d0b7b2db8a",
    "tapp/natural_terrain.py": "b697774741c396e8e47dcfc3fe48c26a832f268a8ab07b155888a3313fefc494",
    "tapp/online.py": "b0d42ba2c9dc87c46d831a6f59fd65c038783b823b55ecce0b904831e6ff5a3e",
    "tapp/online_deadend.py": "d76f63a3f39c9dae64e22fe6ab8ff32139787b8341b5c51d539d72798a3cfe50",
    "tapp/online_mission.py": "cb6256d33524a7121a79c4cb12e406b3be32f741bc072ebb4eb01481935882b9",
    "tapp/planners.py": "0b7fae68b5df6c3930e8b2311727f8a721fc64d8e9d8b66f0512df4a34a70b35",
    "tapp/pointcloud_map.py": "c385c4c90d4b6eb5cf2107a0ece8c79f33d06ca814b34b813dc7e10791c94c99",
    "tapp/prior.py": "7d88a2f97d57eeacc44b454a1cdfb271982646cf6b7e8ed839fdb05349ac21c2",
    "tapp/pure_pursuit.py": "117e82c76afa4d458d24d717cbd31989bcd9fc4821f932c86de7d9330e775ad1",
    "tapp/real_beach.py": "34e61730bbf27f4156d7533f93eaf3e1200678e0de21ace6a9707080d7cddf67",
    "tapp/risk_prior.py": "45e1c7e2d0b2c95797ffd685fdc6c2d1b3b75290db7d4b44234892dc1d8a6388",
    "tapp/robot_sim.py": "72945c0e7869798990d2dabc501eb59fd8b58c8425e1c6940840bcc9f5ddafc3",
    "tapp/run_log.py": "49f90c088cb72b92fb51c8b1127256657d7bb59fc9b679c101dcb2fbc2d0c3a3",
    "tapp/scenario.py": "1b72375f95c8f8deaa07c16dbacbea282ce52f20cd9d23fdc546ea0bbc7ccce7",
    "tapp/terrain.py": "57eede9a8dde604c067f00973e6e9a3a966629d166cb5a6dd70e74a98ebd8864",
    "tapp/terrain_baselines.py": "72ee46f517bc0e50e8a8483473c138bff921f3030e62ec37d3ad68ac1745bc4d",
    "tapp/tour.py": "f95e6d95c456a887768596e2e32d10ae1d8960ebfac6af0a1b1697eaac9d37a9",
    "tapp/traversability.py": "b655d1b97aef36a74a636bb1ff5089b421f9f5ef1aa8a3e489ac024d4597d9c2",
    "tapp/visibility.py": "45e5a3e78553acf571651d00e855044948018603fec10c17bbc5c57df8e65482",
    "tests/test_pointcloud_map.py": "66fd00e3e096a7fc8e465f146f6de401c67007abc5cebea020732551afe156ee"
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
    "data/shizuoka_beach_las/08PD00_-1730.npz": "1e7a83c021f2f90061a6392cec1538491b3d5b2e52d33e622593e515d9e5490e"
  }
}
```

## 実行したコマンド

```bash
cd conference
python3 -m tests.test_planners
python3 -m tests.test_pointcloud_map
python3 experiments/pointcloud_validation.py
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 3 --output results/gazebo_lidar
python3 experiments/gz_lidar_report.py
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/gazebo_lidar/physical_3 --patch-count 3
python3 results/gazebo_lidar/verification/run_tests.py
```

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-022-mpl XDG_CACHE_HOME=/tmp/thesis-022-cache` を指定した。新規Pythonのpy_compileとbash -nも成功した。

Docker起動の実際の出力（exit=125）：

```text
docker: Error response from daemon: No such image: thesis/jazzy-gz:1

Run 'docker run --help' for more information
```

## テスト出力の全文

変更前：

```text
all planner tests passed
roll-aware tests passed
```

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
three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)
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

$ python3 -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

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

$ python3 -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis-022/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

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
test_gz_online_batch exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_deadend exit=0
test_online_mission exit=0
test_planners exit=0
test_pointcloud_map exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

## 3条件の集計表（出力をそのまま）

fixedとonlineは021の保存済み実測値、LiDARは今回の未実行欄である。保存済み20行の指標が数値として完全一致することをテストした。未測定を0と扱わない。対の差は両方完走した地形だけで計算する。

```text
Task022: task021 fixed/R10 controls plus LiDAR, ten identical LAS scenarios; descriptive only.
Controls are cached task021 physical measurements. Unknown LiDAR outcomes remain blank/None/NaN.
       patch   mode       planner planning_status    status recorded_status completed data_source error goals_reached lethal_cells debris_cells n_replans  elapsed_s  deviation_mean_m  deviation_max_m  roll_p95_deg  roll_max_deg  pitch_p95_deg  pitch_max_deg  plan_s_median  plan_s_p95  plan_s_max returned_to_start n_plans calls_over_1s deviation_samples out_of_bounds_samples rolled_over  rollover_t_s  rollover_elapsed_s  rollover_x_m  rollover_y_m  selected height_cells height_abs_error_median_m height_abs_error_p95_m height_abs_error_max_m map_update_s_median map_update_s_p95 map_update_s_max map_updates map_failed_updates queue_drops sim_to_wall_ratio sensor_error
08OB86_00294  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0       29.2         0.0652804         0.612124       4.49186       8.22018        5.59533        8.97691       0.131676    0.257081    0.283574             False       6             0               585                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_00294 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       106    473.408         0.0376759          1.05408       3.91119        6.6159        5.04514        17.9686      0.0776092     0.29242    0.733161              True     112             0              9465                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_-0205  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            1            1         0       64.7          0.129093          0.62619        4.9228       9.68489         4.7532        10.4313      0.0684066    0.101999      0.1069             False       6             0              1295                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_-0205 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0        92    244.199         0.0591287          1.00063       4.82593       11.2399        6.09306        11.2888       0.069355    0.134001    0.261372              True      98             0              4881                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB87_-0706  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0      42.45         0.0381514         0.446409       2.72025       6.16175        4.55938        6.67419       0.114647    0.447735    0.513411             False       6             0               849                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB87_-0706 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       105     458.65         0.0448017          1.53707       3.60804        18.629        5.08675        19.5165       0.110614    0.617138     1.04776              True     111             2              9170                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-1417  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0     19.652          0.460207         0.611346       4.28389       5.30703        4.31249        4.31769      0.0646924    0.122185    0.123105             False       6             0               394                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-1417 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            1            1       103     299.45         0.0413632         0.813067       5.09445       18.8408        4.60072        18.6673      0.0593737    0.157099    0.182353              True     109             0              5985                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-0167  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            0            0         0     119.15         0.0257854         0.569815       2.92837        5.2383        3.42202         5.7893       0.132403    0.223228    0.225747             False       6             0              2384                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-0167 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5           27            0       304    612.901           0.10154          4.03871         7.394       42.9836        8.88529        52.4828      0.0785826    0.384144    0.567933              True     310             0             12256                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_00332  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0     51.549         0.0682241         0.574867       3.51936       4.69489        10.4422        14.4091      0.0377247   0.0866617   0.0977732             False       6             0              1031                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_00332 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       185     241.85         0.0604261         0.967311       5.48962       9.31724          6.885        14.4478      0.0452776   0.0907293    0.192564              True     191             0              4833                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_01832  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            0            0         0    251.401         0.0329133         0.350719       3.40124       8.21047        3.13815        15.0864       0.102191    0.218828    0.253852             False       6             0              5028                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_01832 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0        90      427.4         0.0316318          1.05007       2.88807       7.20092        3.22917        11.9953       0.106325    0.868195     1.15409              True      96             1              8542                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_00152  fixed TA*-S+inflate         planned  rollover           stuck     False      gazebo   NaN             2            0            0         0    110.249          0.163156          2.68832       90.0564       178.441        7.74643        15.7963       0.140243     0.52322    0.541079             False       6             0              2206                   242        True       103.851                98.8       100.112       199.653      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_00152 online TA*-S+inflate         planned  rollover         no_path     False      gazebo   NaN             2            0            0        14     100.45           0.15281          1.34311       22.1221       172.636        6.81007        41.9431       0.115844    0.361512    0.361652             False      17             0              2003                   161        True         105.2              100.15        99.631       199.564      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0347  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            1            1         0      37.25         0.0893584         0.349333       3.65141       4.14532        3.44566        4.78677      0.0917351      0.1884    0.196287             False       6             0               745                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0347 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       130    385.849         0.0373097          1.18912        3.8667        7.5727        4.99498        9.37978      0.0879499    0.195575    0.319513              True     136             0              7713                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0847  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            2            2         0     126.75         0.0282698         0.497471       4.60119       7.53312         3.6828        8.49752       0.110015    0.203834    0.215019             False       6             0              2535                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0847 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            1            1       303      421.6         0.0394325         0.709465       3.33601       7.59398        3.68824        13.6144       0.112321     0.27778    0.386705              True     309             0              8428                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_00294  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB86_-0205  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB87_-0706  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_-1417  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_-0167  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_00332  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_01832  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB89_00152  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB89_-0347  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB89_-0847  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None

Counts use actual recordings; selected is the requested 3/10 LiDAR rollout stage.
  mode  scheduled  selected  executed  unexecuted  completed  stuck  rollover  timeout  no_path  incomplete_waypoints  runtime_error  goals_reached_median  lethal_cells_median  debris_cells_median  n_replans_median  elapsed_s_median  deviation_mean_m_median  deviation_max_m_median  roll_p95_deg_median  roll_max_deg_median  pitch_p95_deg_median  pitch_max_deg_median  plan_s_median_median  plan_s_p95_median  plan_s_max_median height_cells_median height_abs_error_median_m_median height_abs_error_p95_m_median height_abs_error_max_m_median map_update_s_median_median map_update_s_p95_median map_update_s_max_median map_updates_median map_failed_updates_median queue_drops_median sim_to_wall_ratio_median
 fixed         10        10        10           0          0      9         1        0        0                     0              0                   0.5                    0                    0                 0           58.1245                0.0667522                0.572341              3.96765              6.84744               4.43593               8.73722              0.106103           0.211331           0.220383                None                             None                          None                          None                       None                    None                    None               None                      None               None                     None
online         10        10        10           0          9      0         1        0        0                     0              0                     5                    0                    0             105.5           403.725                0.0430825                 1.05207              4.36856              10.2786               5.06595               16.2082             0.0832662             0.2851           0.374179                None                             None                          None                          None                       None                    None                    None               None                      None               None                     None
 lidar         10         3         0          10        NaN    NaN       NaN      NaN      NaN                   NaN            NaN                   NaN                  NaN                  NaN               NaN               NaN                      NaN                     NaN                  NaN                  NaN                   NaN                   NaN                   NaN                NaN                NaN                None                             None                          None                          None                       None                    None                    None               None                      None               None                     None

Method minus reference; only both completed physical tours; no hypothesis tests or energy.
method reference           metric  paired_completed delta_median
online     fixed    goals_reached                 0         None
online     fixed     lethal_cells                 0         None
online     fixed     debris_cells                 0         None
online     fixed        n_replans                 0         None
online     fixed        elapsed_s                 0         None
online     fixed deviation_mean_m                 0         None
online     fixed  deviation_max_m                 0         None
online     fixed     roll_p95_deg                 0         None
online     fixed     roll_max_deg                 0         None
online     fixed    pitch_p95_deg                 0         None
online     fixed    pitch_max_deg                 0         None
online     fixed    plan_s_median                 0         None
online     fixed       plan_s_p95                 0         None
online     fixed       plan_s_max                 0         None
 lidar     fixed    goals_reached                 0         None
 lidar     fixed     lethal_cells                 0         None
 lidar     fixed     debris_cells                 0         None
 lidar     fixed        n_replans                 0         None
 lidar     fixed        elapsed_s                 0         None
 lidar     fixed deviation_mean_m                 0         None
 lidar     fixed  deviation_max_m                 0         None
 lidar     fixed     roll_p95_deg                 0         None
 lidar     fixed     roll_max_deg                 0         None
 lidar     fixed    pitch_p95_deg                 0         None
 lidar     fixed    pitch_max_deg                 0         None
 lidar     fixed    plan_s_median                 0         None
 lidar     fixed       plan_s_p95                 0         None
 lidar     fixed       plan_s_max                 0         None
 lidar    online    goals_reached                 0         None
 lidar    online     lethal_cells                 0         None
 lidar    online     debris_cells                 0         None
 lidar    online        n_replans                 0         None
 lidar    online        elapsed_s                 0         None
 lidar    online deviation_mean_m                 0         None
 lidar    online  deviation_max_m                 0         None
 lidar    online     roll_p95_deg                 0         None
 lidar    online     roll_max_deg                 0         None
 lidar    online    pitch_p95_deg                 0         None
 lidar    online    pitch_max_deg                 0         None
 lidar    online    plan_s_median                 0         None
 lidar    online       plan_s_p95                 0         None
 lidar    online       plan_s_max                 0         None
Height errors: absolute errors in the final unique hit cells; median return surface versus truth DEM.
Mapping times include PointCloud2 decoding, registration, fusion and feature recomputation; not planning/ROS handoff.
R10 control and 30m LiDAR differ in range/beam sparsity/occlusion/noise; this is not an isolated occlusion comparison.
Keep 08OB89_00152: task021 rollover is a map-boundary artifact, not a measured planner effect.
```

## 点群からの高さ誤差と地図更新時間

LiDARの実測値は未取得。実走時は最後の地図の観測済みセルを1回ずつ数え、中央値の表面高さと実際の真値DEMの絶対差（中央値・95%・最大）を評価する。上面が真値DEMに入っていない漂着物では、その高さ差も含む。

更新時間はPointCloud2のデコード・座標変換・融合・特徴量計算を含む成功処理の分布とし、失敗・queue dropを併記する。保存・キュー待ち・ROSの受け渡しは含まない。探索時間とは別に読む。

以下は**validation12地形の密な人工入力による処理監査**で、Gazebo/VLP-16の実測ではない。全て事前固定した設定で実行し、閾値の選択・調整はしていない。セル中心から点を作るため、実際の走査密度・遮蔽・セル内の位置偏り・動力学を評価していない。

```text
VALIDATION ONLY: dense artificial DEM returns, not Gazebo/VLP-16 measurements; no tuning.
                             source        patch  observed_cells  error_median_m  error_p95_m  update_s  input_points
validation_dense_artificial_returns 08OB87_-0206           11086     0.000352349   0.00193533  0.384788         33258
validation_dense_artificial_returns 08OB88_01332           11250     0.000377498   0.00221333  0.281524         33750
validation_dense_artificial_returns 08OB89_-1597            9887     0.000330137   0.00274032  0.241511         29664
validation_dense_artificial_returns 08OC90_00270           10081     0.000351986   0.00212163  0.236031         30243
validation_dense_artificial_returns 08OC91_00811           11256     0.000263028    0.0020687  0.267921         33768
validation_dense_artificial_returns 08OC93_-1519           11144     0.000323986   0.00191017  0.274128         33435
validation_dense_artificial_returns 08OC95_-0321           11260     0.000308378   0.00232001  0.320561         33780
validation_dense_artificial_returns 08OC96_-0676            8818     0.000491998   0.00334322  0.226692         26454
validation_dense_artificial_returns 08OC97_-0077           11261     0.000318206   0.00206651  0.286032         33783
validation_dense_artificial_returns 08OC98_-1101           10647     0.000383787   0.00225024  0.269964         31941
validation_dense_artificial_returns 08OC98_01898           10299     0.000542452   0.00259834  0.259226         30897
validation_dense_artificial_returns 08OC99_00983            9802      0.00040039    0.0021909  0.245144         29409
```

この人工入力では更新時間が10Hzの周期を超える例があった。実際の疎な点群での速度や1m/s走行で間に合うかは未測定であり、性能保証とは扱わない。

## 入力のバイト列と過去の結果の保持

021の実走はNumPy1.26.4、今回の環境は2.3.5。漂着物を加えた標高のハッシュが一致しない一方、LASのバイト列・事前地図の高さ・岩とlethalマスクは一致した。旧標高配列が一時領域にしかなかったため差の大きさは確定していない。

古い数値や期待値を書き換えず、入力LASと主要な計画・地形コードのSHA、マスクを検査して違いを記録した。新しい実走は評価用の高さ・マスク配列を保存し、異なる環境での事後評価も実際の入力配列を使う。評価用配列が不明な場合、高さ誤差は未取得のままにする。

```json
[
  {
    "patch": "08OB86_00294",
    "las_sha256": "a28761a28ecd3b99b26d1d7e9899c0eba55a43047c726a74361f08e022b81e72",
    "signatures": {
      "truth": {
        "elev": "94cc055485e28df40f325ac36c7f1eebf185e90657ceb21d2dcd1d5c692e5260",
        "lethal": "7ed14f758ece6fc21fe49419454b3e62c3f88c30d2d6052f5bbf897a7561ea62",
        "rock": "b0b52cb5a9e764910ac8d4e69dcc4f950d853240096a466b437693facb96ba87"
      },
      "prior": {
        "elev": "06f417823b36cea218cf5ed2897911e772bdf63080178a788b43885321ab75bf",
        "lethal": "955836072744a537ab22514c7fc14a73acf7a02f3575e252da1a69a042fcb6c7",
        "rock": "8b51c5179bc998be8bb2d0b63e48a869b2c0beb9ce0c65f3adc0bbdf6e878e5b"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB86_-0205",
    "las_sha256": "5a363b942c0991542b46e1e8657088b641647726fd5a2af684327cb3cdb762c9",
    "signatures": {
      "truth": {
        "elev": "ee7107ae1bb024141fc778a510c2f6917669f212d55a4f9f651fd1c857f9641f",
        "lethal": "e46b1e845737da313eac2b893c2b750e71c919a453356fbf749cb6e2ae706bcc",
        "rock": "221072c1cab9f2f48b7c03b74f7af552462697afe4c72881f3ce2b99bcf4b3da"
      },
      "prior": {
        "elev": "7692fc79e1b4099af724d33ef3eab8949539cd4735aa57077f897cf2dfbac2a8",
        "lethal": "f1225d7397f8e3937d5664ebb7e26d2ba78b04c0d7d962bd99fca9a250c737cb",
        "rock": "6feb83e08f8cfefae386d327f9a32481b855a6548e753f343825a4f60f4b722c"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB87_-0706",
    "las_sha256": "040ed7b94cd70b41e9d2b94259b40ab8c1210d849732b1132f34cb5230c64d64",
    "signatures": {
      "truth": {
        "elev": "369ba3c0af8e5589606799dabf72484a0d0e3799fe0db23646aa66e9596fffb0",
        "lethal": "77b9a58bec28a3f123f8cabee901a87a98be8d30b0f9c479b9efee2a5342ffb6",
        "rock": "2c94c6c1ac6bd3ca4e50f2456d1ea65506785e1325cd58dd5ef78b2919b8acc7"
      },
      "prior": {
        "elev": "53c049b7e1cf1940b928740f60e7f58eba47db505cfcdf76b8bc0c18db59869a",
        "lethal": "053b5221d06b4dcd5ccbddbd8a0943db4109a85336637f3608f132dfb1c5f179",
        "rock": "bba4745e20744684f84c4896c52ff0f8f222650dcd0fc5774bdf3b03542e683a"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB88_-1417",
    "las_sha256": "f0ecb31bd4d851ea4c88ce0057e3c379591572d3b2308066f6120c061dd7c7cd",
    "signatures": {
      "truth": {
        "elev": "7232e4b567c90110d8bf3163f83a197a7d406d6f53eff1cfd6e11715f093dc41",
        "lethal": "f38c6a901e4a0ffbc99ef00207abecd9e42693bdd64bf70db1b6c09a870dfbf6",
        "rock": "9733aa5ad147ecf7fecbc03ca331fbb493be5728ff32f063cafba28cb33a9762"
      },
      "prior": {
        "elev": "0d68ad3e7b83d8ff2a9c31b7015a9716638cf627cf1452216c3f4feeb49c6b54",
        "lethal": "2a4fa502deb5b40343bbffbd947c6221d87a39cf618615da804fdc887e59b14d",
        "rock": "0110056d01ebf0cb4213f3efce21092b32c1f2c12ccaaa6ae19a6026a3efd955"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB88_-0167",
    "las_sha256": "9896a3892eef5fc439daad325c22f149e0a2157c94daec0be60296ebbc5f06dc",
    "signatures": {
      "truth": {
        "elev": "fd559506b166e7dc110b6085723dc4c0dd7c54069187a0cc6750bff7a620145c",
        "lethal": "764a684bb1ff899bb2f01cd36131052e5dbf99ad993814321262a01fcc4e7b1a",
        "rock": "b18ca235bff3c9fa4b9d6d05f3c8a463b687bb4f99c4dc6340d329b2530c8cd4"
      },
      "prior": {
        "elev": "23722bc88cf47c848bc9e12321d347247b75f09c27f10492985146ca14779aed",
        "lethal": "259f3907787df5b726fefee3cf1026dbae420f1e0fccd9eb532a06b6c5326d94",
        "rock": "71842a3c59c1ccbe171d140914a1ac4c1b3b4458171e7a718434b44b023b5d1e"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB88_00332",
    "las_sha256": "36aa756efe874f15dbd9ce45d1ccb85997c6d9131ac20bbaeab3ed2c368e172d",
    "signatures": {
      "truth": {
        "elev": "5c4a73d0c89104750ca5d49d2a6d233cf716cc20751b0ce2216c6947605c2222",
        "lethal": "aa52077035de8a49b5cdb396c3f2c0e2c504d5fcfabcc2a2d4ef1bb9f3be2bd1",
        "rock": "1e013680f6df39c44e88e3c8cd5b14d2539b662e3100216c0501e9cad03c0e54"
      },
      "prior": {
        "elev": "1f6774027103f5d3629c0e993ff7b8aa5fbb356a1e84ee5e1dee6c9d828b4928",
        "lethal": "e908c08af69bb5ace1d25e8f3b4cc043f50f553718100511c9d57fa0b35775a1",
        "rock": "739172300967b99e78a2cd0d5afa164e1cff83c5ba4e8893a93d40fa8763ef08"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB88_01832",
    "las_sha256": "709d8f2f68753a49293a315091a595bc6f489439cbfcf763920c23abbeb71d84",
    "signatures": {
      "truth": {
        "elev": "679dbc21c4d062f280211f239e953418a7a7a8c9828cb5152bb942a533a0a59c",
        "lethal": "0f428c5f00ed2725d62cb89cad4d476b4b83cf7f4fee2ed92ad2bf8d130a242d",
        "rock": "9f8cb7448827d13f6c0eebbdbdf450eaccb7045ffb2129f8c50817ee93537c53"
      },
      "prior": {
        "elev": "23565122185b3529415815b007f6b63b5c51a859312db88a5e036b0d8bc18790",
        "lethal": "7ec00b5a8f1d0c948d0c422a712530266fbeccf532244961c26a37212156def5",
        "rock": "f7bd00cdfbd51194bef9aed8718d5f91053d207ae9abe954d44b4567bcbebca1"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB89_00152",
    "las_sha256": "82dfbd220de3f07afa0161c884941f8dba65c3d8d2ad4d8fef59d18d5efd7b50",
    "signatures": {
      "truth": {
        "elev": "8dce8ea160b98bfc11adb8348369408cae08af59e263bff6c3a2d2074ca5376b",
        "lethal": "569476611522d38cb2a37dd7a31581e779de501dff490e56fe887ac74c1fb588",
        "rock": "a39ec589d5c1e7cf1fb8f817d0e047411c8e6c7a0b3fd9559a3771bf7b65a8d4"
      },
      "prior": {
        "elev": "aafbb2e5214391454aa2888c6350759d726267104c65135b34b8a44a498121fd",
        "lethal": "83ff4866c6d7474aae926d5498e2fb9289f6734ecb152d54b43b5dd785e80a60",
        "rock": "f31bc10da7931780eda075fe9aadcad104962beb2d0ac630ed0c3470f5f009bd"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB89_-0347",
    "las_sha256": "4308458273952d62958f2f4a080253e9a676337594dd1c6ea87f277c92e12882",
    "signatures": {
      "truth": {
        "elev": "e16bfaedcb368b6ffbeb6f197942367d8354f06c6b9f252af1a3475bb5b36a28",
        "lethal": "604b8b1c47e6506d4fd34257ccfb4525cef5b2f0b5a99125613220dc6b3792fa",
        "rock": "97aee29b11e415025f724ff0c227af7945f6d890b5c739586c250a9d54bdaca2"
      },
      "prior": {
        "elev": "ecac9095660a758f9efb52f296d0cfcf537eca082e8df4446339084989faf076",
        "lethal": "616ec5d0c56be61768cd4ee0757e9008fce35525f7d5fbfcf38074abdd026491",
        "rock": "bc189b89ffe4726466e714a404498fdaab2f1220dec9b7dda8ee302f10d2dfdf"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  },
  {
    "patch": "08OB89_-0847",
    "las_sha256": "c530894cc3784c412abc8a15837e638b852236450421106136e63463814e6476",
    "signatures": {
      "truth": {
        "elev": "573d8819a9f15ec784a1d79cedfc2a5d6cb9430e8a27c6ecea6e1951fc764b6d",
        "lethal": "a931a54c08d67cc4e953a21af7a9cc911ef0917fa3a2ec66854e98a137cb0055",
        "rock": "6f2c0c9e9e6ebf92b8c533e5335c2f4fe778591a81eacd26aee19a4211589755"
      },
      "prior": {
        "elev": "b95f74dfd95d40020642542121ae54ae6726638b4d54001d2cbe7f2c5bb7320d",
        "lethal": "3df5176470c9487cef2af37fb0084d12330d6b37c6672889351969f1809055b0",
        "rock": "1319048c6ee1bb2f24933d31835d212ee40aad1e23ed6fec55e7bdf11b93ee2d"
      }
    },
    "historical_truth_elevation_equal": false,
    "note": "If historical elevation SHA differs, its magnitude is unknown without the old transient grid; masks/LAS match."
  }
]
```

```json
{
  "original_files": 2139,
  "changed": [
    "conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/model.py"
  ],
  "reason": "Task022 explicitly permits an opt-in LiDAR keyword; default/mass SDF bytes are frozen and tested unchanged."
}
```

既存の模型以外のファイルは内容のSHAで一致を確認した。模型は指示書で許可された引数追加のみで、LiDARなしの通常・質量指定SDFのバイト一致をテストした。既存テストの削除・弱体化はない。

## できなかったこと・確認してほしいこと

優先順位(1)の点群処理とROS2なしのテストは完了した。(2)のGazebo3か所と(3)の10か所は未実行である。
通常Dockerの起動は標準イメージ `thesis/jazzy-gz:1` がなくexit=125で終了し、Gazebo・colconは開始していない。
ホストにパッケージを追加せず、特殊な名前空間やchrootによる実行も行っていない。
LiDARの場合の完走・接触・転倒・計画時間・実測の高さ誤差・実測の地図更新時間は測れていない。
以下の人工入力の数値をLiDARの実測欄に埋めていない。

Claudeには、通常Dockerでまず3か所を走らせ、PointCloud2のtopic/frame/timestamp、模型の局所座標、ground_truthとの時間整合、
ogre2の画面なし描画、実際の戻り点の密度、待ち行列の取りこぼし、0.5シミュレーション秒のセンサー停止期限を確認してほしい。
実走できた場合にのみ、新しい保存先で10か所へ広げる。処理・探索の壁時計時間と、Gazeboの進行速度を分けて読む必要がある。
模型のmu2=0.1や急旋回による転倒は残りうる。中心軌跡の接触数は車体前端の接触を過少評価する。
021で両条件が転倒した `08OB89_00152` は地図境界の問題として除外せず注記している。
完全な点群ストリームは保存せず、最初の点群と各処理入力のSHA-256、最終地図、更新ログを残すため、全走査の再生はできない。

通常Dockerの構築、3か所、10か所の順の実行コマンドとファイル仕様は [README_ja.md](README_ja.md) に記載した。

## 図

各図のfixed/onlineは021の保存済み軌跡で、LiDARの実線は描かず未実行と明記する。

[08OB86_00294](08OB86_00294.png)

[08OB86_-0205](08OB86_-0205.png)

[08OB87_-0706](08OB87_-0706.png)

[08OB88_-1417](08OB88_-1417.png)

[08OB88_-0167](08OB88_-0167.png)

[08OB88_00332](08OB88_00332.png)

[08OB88_01832](08OB88_01832.png)

[08OB89_00152](08OB89_00152.png)

[08OB89_-0347](08OB89_-0347.png)

[08OB89_-0847](08OB89_-0847.png)

## 提出状態

`codex/022-gazebo-lidar` はpush済み。実装コミットは `ce2790e04f9ed85062fc84b9b78514a12cb89867`。
マージは行っていない。報告の追記はこのコミットの後に保存する。

`realtime-map` 向けのPR作成を試みたが、GraphQLとRESTの両方が `Forbidden` で拒否されたため、PRは作成していない。
実際の出力は `verification/pr_create_log.txt` と `verification/pr_rest_log.txt` に保存した。
共通ルールの代替手順に従い、全テスト出力・集計表・仮定・未実行事項を含む本文を `PR_DESCRIPTION_ja.md` に保存した。

通常Docker用の標準イメージがないため、LiDARの3か所・10か所でのGazebo実走は未実行。
点群処理とROS2不要の検証、通常Dockerでの実行・集計スクリプトまでを提出する。


## 変更ファイル一覧

- `conference/experiments/gz_lidar_report.py`
- `conference/experiments/pointcloud_validation.py`
- `conference/results/gazebo_lidar/08OB86_-0205.png`
- `conference/results/gazebo_lidar/08OB86_00294.png`
- `conference/results/gazebo_lidar/08OB87_-0706.png`
- `conference/results/gazebo_lidar/08OB88_-0167.png`
- `conference/results/gazebo_lidar/08OB88_-1417.png`
- `conference/results/gazebo_lidar/08OB88_00332.png`
- `conference/results/gazebo_lidar/08OB88_01832.png`
- `conference/results/gazebo_lidar/08OB89_-0347.png`
- `conference/results/gazebo_lidar/08OB89_-0847.png`
- `conference/results/gazebo_lidar/08OB89_00152.png`
- `conference/results/gazebo_lidar/PR_DESCRIPTION_ja.md`
- `conference/results/gazebo_lidar/README_ja.md`
- `conference/results/gazebo_lidar/REPORT_ja.md`
- `conference/results/gazebo_lidar/SUBMISSION_ja.md`
- `conference/results/gazebo_lidar/baseline_input_audit.json`
- `conference/results/gazebo_lidar/changed_files.txt`
- `conference/results/gazebo_lidar/gazebo_lidar_log.txt`
- `conference/results/gazebo_lidar/manifest.json`
- `conference/results/gazebo_lidar/paired_differences.csv`
- `conference/results/gazebo_lidar/runs.csv`
- `conference/results/gazebo_lidar/summary.csv`
- `conference/results/gazebo_lidar/validation/height_audit.csv`
- `conference/results/gazebo_lidar/validation/protocol.json`
- `conference/results/gazebo_lidar/validation/validation_log.txt`
- `conference/results/gazebo_lidar/verification/all_tests_log.txt`
- `conference/results/gazebo_lidar/verification/baseline_sha256.json`
- `conference/results/gazebo_lidar/verification/build_report.py`
- `conference/results/gazebo_lidar/verification/docker_launcher_log.txt`
- `conference/results/gazebo_lidar/verification/model_default_before.sdf`
- `conference/results/gazebo_lidar/verification/model_mass_before.sdf`
- `conference/results/gazebo_lidar/verification/planners_before_log.txt`
- `conference/results/gazebo_lidar/verification/pr_create_log.txt`
- `conference/results/gazebo_lidar/verification/pr_rest_log.txt`
- `conference/results/gazebo_lidar/verification/prepare_console_log.txt`
- `conference/results/gazebo_lidar/verification/preservation_audit.json`
- `conference/results/gazebo_lidar/verification/protocol.json`
- `conference/results/gazebo_lidar/verification/report_console_log.txt`
- `conference/results/gazebo_lidar/verification/run_tests.py`
- `conference/results/gazebo_lidar/verification/test_beach_terrain_log.txt`
- `conference/results/gazebo_lidar/verification/test_collision_log.txt`
- `conference/results/gazebo_lidar/verification/test_dstar_log.txt`
- `conference/results/gazebo_lidar/verification/test_footprint_log.txt`
- `conference/results/gazebo_lidar/verification/test_geo_log.txt`
- `conference/results/gazebo_lidar/verification/test_gz_compare_log.txt`
- `conference/results/gazebo_lidar/verification/test_gz_online_batch_log.txt`
- `conference/results/gazebo_lidar/verification/test_mapfiles_sim_log.txt`
- `conference/results/gazebo_lidar/verification/test_mission_log.txt`
- `conference/results/gazebo_lidar/verification/test_natural_terrain_log.txt`
- `conference/results/gazebo_lidar/verification/test_online_deadend_log.txt`
- `conference/results/gazebo_lidar/verification/test_online_log.txt`
- `conference/results/gazebo_lidar/verification/test_online_mission_log.txt`
- `conference/results/gazebo_lidar/verification/test_planners_log.txt`
- `conference/results/gazebo_lidar/verification/test_pointcloud_final_log.txt`
- `conference/results/gazebo_lidar/verification/test_pointcloud_initial_log.txt`
- `conference/results/gazebo_lidar/verification/test_pointcloud_map_log.txt`
- `conference/results/gazebo_lidar/verification/test_pointcloud_runtime_log.txt`
- `conference/results/gazebo_lidar/verification/test_real_beach_las_log.txt`
- `conference/results/gazebo_lidar/verification/test_real_beach_log.txt`
- `conference/results/gazebo_lidar/verification/test_risk_prior_log.txt`
- `conference/results/gazebo_lidar/verification/test_ros2_gz_log.txt`
- `conference/results/gazebo_lidar/verification/test_summary.txt`
- `conference/results/gazebo_lidar/verification/test_thesis_figures_log.txt`
- `conference/results/gazebo_lidar/verification/test_tour_log.txt`
- `conference/results/gazebo_lidar/verification/test_visibility_log.txt`
- `conference/results/gazebo_lidar/verification/validation_console_log.txt`
- `conference/ros2_jazzy/gz_checks/lidar_bridge.yaml`
- `conference/ros2_jazzy/gz_checks/lidar_checks.py`
- `conference/ros2_jazzy/gz_checks/lidar_planner.py`
- `conference/ros2_jazzy/gz_checks/lidar_runtime.py`
- `conference/ros2_jazzy/gz_checks/run_lidar_checks.sh`
- `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/lidar.py`
- `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/model.py`
- `conference/tapp/pointcloud_map.py`
- `conference/tests/test_pointcloud_map.py`
