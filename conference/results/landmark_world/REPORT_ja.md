# 075 目印付きの世界・参照点群・センサー記録

実装コミットは `8fc61a19ba9df8e03b365c3a8b40c745d667feb8`。初期計画の互換性修正を含む検証時点は `f8e57f6320605754921537dd1ff21849cfad443f`。作業ブランチは `codex/075-landmark-world`、比較元は `realtime-map` の `fee31da70ce8b5ae1dd6206bfdd07b6d2bab2c9a`。クラウドの Python と保存済みデータを使った。

## 変更したファイル

| ファイル（conference/ を起点） | 内容 |
| --- | --- |
| `tapp/landmark_world.py` | 配置、既知障害物のマスク、地形と目印の点群 |
| `tapp/sensor_recording.py` | 100 MB 上限付きの圧縮記録、LiDAR の復元 |
| `ros2_jazzy/gz_checks/landmark_sdf.py` | 直方体・円柱の固定衝突形状と描画形状 |
| `ros2_jazzy/gz_checks/lidar_checks.py` | 引数、世界・prior の組み立て、記録プロセス、manifest |
| `ros2_jazzy/gz_checks/run_lidar_checks.sh` | 使用例のコメント。引数は従来の転送経路を使う |
| `tests/test_landmark_world.py` | 同一環境の変更前比較、配置と評価マスク、点群と記録、模擬起動 |
| `results/landmark_world/REPORT_ja.md` | 検証結果とテスト出力 |

## 配置と検証

- 密度の分母は、水域と欠測を除いた陸地の面積とした。急斜面と配置禁止帯を除く前の面積に密度を掛け、最も近い整数に丸めた（0.5 は切り上げ）。物の中心から外接円を引いた距離で、地点まで 2 m、物どうし 1 m を確保した。地図の外、水域、欠測、25°超のマス、評価箱の矩形にはみ出す候補を除いた。物の総数が奇数の場合、形の個数差は 1。密度を増やすと、同じ砂浜とシードの既存の配置を先頭に保つ。
- `manifest.json` の各 case に、陸地面積と物の位置、幅、奥行き、高さ、向き、形を保存する。立体の底面は中心マスの標高に置く。地形や既存の評価箱は元の手順で出力し、別モデルとして目印の衝突形状・描画形状を足す。目印の輪郭と交差するマスを、prior と評価用の真値に追加して従来のロボットの余白を適用する。既存の初期経路探索を、同じ地点と順序で新しい prior 上にかける。
- 保存済みの task022 地図を 10 砂浜で再利用し、シード 0 の密度 10・40・160 を確認した。全 30 条件で `truth_rock & ~prior_rock` の変更マスは **0**。箱の距離評価用 CSV にも目印は入らない。初期経路は **29/30** 条件で見つかった。160 個/ha の 0167 では、5 区間目の `[202, 281] → [137, 294]` の両端が通れる状態でも、間を結ぶ経路を得られなかった。この条件は実行時にも初期計画エラーを記録する。

| 砂浜 | 陸地面積 (m²) | 10 個/ha | 40 個/ha | 160 個/ha | 160 個/ha の初期経路 |
| --- | ---: | ---: | ---: | ---: | --- |
| 08OB86_00294 | 19,699.25 | 20 | 79 | 315 | あり |
| 08OB86_-0205 | 18,804.50 | 19 | 75 | 301 | あり |
| 08OB87_-0706 | 19,623.00 | 20 | 78 | 314 | あり |
| 08OB88_-1417 | 19,040.75 | 19 | 76 | 305 | あり |
| 08OB88_-0167 | 22,748.75 | 23 | 91 | 364 | なし |
| 08OB88_00332 | 19,485.50 | 19 | 78 | 312 | あり |
| 08OB88_01832 | 25,308.25 | 25 | 101 | 405 | あり |
| 08OB89_00152 | 30,143.25 | 30 | 121 | 482 | あり |
| 08OB89_-0347 | 30,075.50 | 30 | 120 | 481 | あり |
| 08OB89_-0847 | 30,146.50 | 30 | 121 | 482 | あり |

`reference_cloud.npz` の `xyz` は Gazebo 座標系の float32 XYZ（m）、`kind` は地形が 0、目印が 1。LiDAR の描画に用いる三角形メッシュを 0.1 m 間隔で補間する。立体の面は 0.05 m 以下の間隔で点にした。OBJ の三角形および直方体・円柱の数式との照合には 0.05 mm の許容差を用いた。0 個の参照点群は `--landmarks 0 --record-sensors` で出力する。

同一環境で変更前の `lidar_checks.py` を読み込み、ROS と外部プロセスを模擬した。引数なし、coarse・fine の姿勢記録付き条件、明示的な 0 個・センサー記録なしで、manifest、起動引数、配信内容、生成した記録一式がバイト単位で一致した。

## 1 走行あたりの保存量

容量は十進 MB。参照点群は `08OB86_00294` で実際に圧縮したサイズ。センサー容量は 120 **シミュレーション秒**の見積もり。

| 条件 | 参照点群の点数（地形＋目印） | 参照点群の実測 | センサー記録の見積もり |
| --- | ---: | ---: | --- |
| 目印 0 個 | 3,984,016＋0 | 19.86 MB | 約 34.85 MB。既存の目印なしの開始スキャンを繰り返した例 |
| 目印 160 個（容量を比べるため、315 個のうち先頭 160 個） | 3,984,016＋274,772 | 20.84 MB | 約 80.63 MB。全画素に有効な距離を入れた合成例 |
| 指定値 160 個/ha（この砂浜で 315 個） | 3,984,016＋552,204 | 21.85 MB | 同じ全画素の合成例では約 80.63 MB |

目印が増えても 1 画像の大きさは同じ。最初の見積もりには 039 の反復走行から距離のある画素が約 44% の開始スキャン 6 枚を用いた。後者は全画素に一様乱数の距離を入れた容量試算で、実際の 160 個条件の受信データは未取得。どちらも 2 秒の圧縮チャンクを 60 倍し、IMU 50 Hz と真値 20 Hz の合成行を含めた。LiDAR の距離画像だけなら 16 × 1800 × 2 バイト × 10 Hz × 120 秒で 69.12 MB、方向テーブルを加えると圧縮前で約 89.86 MB。例外座標の数と圧縮率によって所要容量は変わる。

`raw/<砂浜>/sensors/` のチャンクとメタデータの合計には **100,000,000 バイト**の上限を設けた。次のチャンクが入らない場合は `byte_limit` として、確定済みのチャンクを残す。明示した時刻上限で切れた場合は `duration_limit`、走行終了で閉じた場合は `finished`。各ストリームの受信数と保存数、記録全体の時刻範囲を `metadata.json` とケースの manifest で確認できる。参照点群および従来の走行ログはこの上限とは別に保存する。

LiDAR は受信した点の並びと組織化形状を保ち、距離を uint16 の mm で、方向を画素ごとにチャンク内で共有する。全成分が非有限な組は予約値で NaN と ±inf を保持する。共有した方向で 0.9 mm 以内に復元できない点、通常の距離符号に入らない点、一部成分だけが非有限な点は元の XYZ を保存する。有限点の最大の三次元復元誤差は、テストで **0.501 mm**、039 の開始スキャンを使った照合で **0.501 mm** 未満だった。

姿勢ずれを選んだ場合も記録プロセスは `/lidar/points`、`/imu`、`/ground_truth` を購読する。時刻はメッセージヘッダーのシミュレーション時刻（整数 ns）。IMU はクォータニオン・角速度・加速度・共分散、真値は最初のモデルの XYZ とクォータニオンを保存する。記録時間は最初の受信ヘッダーから数えるため、出発前の静止も含む。

## 研究 PC での記録例

`conference/` から実行。初期経路が全密度で見つかった 00294 を例とした。同じシードと地点で密度だけを変える。新規保存先を用意し、研究 PC の手順に従ってコミット ID と環境を先に記録する。

```bash
for density in 160 40 10 0; do
  THESIS_RENDER=gpu THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH=08OB86_00294 \
    bash ros2_jazzy/gz_checks/run_lidar_checks.sh "/data/landmark075/p00294-d${density}-s0" \
      --map fine --sensors lidar_real --real-time-factor 0.3 \
      --landmarks "$density" --landmark-seed 0 --record-sensors --record-sensors-seconds 120
done
```

姿勢ずれとの組み合わせを確かめる場合は別の出力先を選び、例えば `--pose-error bias --pose-error-bias 0.2,0.4,0` を足す。記録の完全性は `metadata.json` の保存数と、各系列のタイムスタンプの間隔で確認できる。容量の大きい点群とセンサー記録は研究 PC に保存し、リポジトリには保存場所とハッシュを記す。

```python
from pathlib import Path
import numpy as np
from tapp.sensor_recording import iter_lidar

raw = Path('/data/landmark075/p00294-d160-s0/raw/08OB86_00294')
with np.load(raw / 'reference_cloud.npz', allow_pickle=False) as cloud:
    reference_xyz, kind = cloud['xyz'], cloud['kind']

for scan in iter_lidar(raw / 'sensors'):
    stamp_ns, frame, xyz_m = scan.stamp_ns, scan.frame_id, scan.xyz
    # xyz_m の形は受信時の (height, width, 3)

# 各 chunk_*.npz の imu_stamp_ns / imu_frame_id / imu_values と
# ground_truth_stamp_ns / ground_truth_frame_id / ground_truth_values を同じ時刻で照合する。
```

## 未確認の点

- Gazebo、ROS2、研究 PC での実走行は行っていない。実際の描画、ROS2 ブリッジの受信間隔、欠落率、保存プロセスが走行速度に与える影響は未測定。上限で切れた後のサンプルは残らないため、120 秒を超えるコースを通した記録の容量は未確認。
- 参照点群は理想的な形状の全表面を含む。実際のドローンの視点、遮蔽、SDF での高さマップ衝突面と描画メッシュとの差はモデル化していない。LiDAR の XYZ と時刻・座標系を保存し、強度などの付加フィールドは保存対象外とした。
- 0167 の高密度条件で初期経路を失った。シード、密度、間隔、地点はこの結果に合わせて変更していない。共通評価の漂着物指標は使える。元の障害物マスクの再構築とビット一致を条件とする一部の地図監査列は、目印ありでは空になる可能性がある。

## クラウドで実行したコマンド

既存の venv で Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0 を使用した。pip check は依存の破損なし。以下は `conference/` から実行し、フルログを末尾に記載した。

```bash
export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/075-mpl XDG_CACHE_HOME=/tmp/075-cache
mkdir -p /tmp/075-tests
/tmp/venv038/bin/python -m pip check
/tmp/venv038/bin/python -c 'import sys,numpy,scipy; print(sys.version); print("numpy",numpy.__version__,"scipy",scipy.__version__)'
bash -n ros2_jazzy/gz_checks/run_lidar_checks.sh
/tmp/venv038/bin/python -m compileall -q tapp/landmark_world.py tapp/sensor_recording.py \
  ros2_jazzy/gz_checks/{landmark_sdf,sensor_recorder,lidar_checks}.py tests/test_landmark_world.py
/tmp/venv038/bin/python -m ros2_jazzy.gz_checks.lidar_checks --help | rg 'landmark|record-sensors'
THESIS_ONLY_PATCH=08OB86_00294 THESIS_FINE_PROTOCOL=rtf_check \
  /tmp/venv038/bin/python -m ros2_jazzy.gz_checks.lidar_checks \
  --output "$(mktemp -d /tmp/075-prepare-XXXXXX)" --prepare-only --map fine \
  --landmarks 160 --landmark-seed 42 --record-sensors --record-sensors-seconds 120
# 変更前（fee31da7）
/tmp/venv038/bin/python -u -m tests.test_planners > /tmp/075-tests/before-planners.log 2>&1
# 変更後（075 のソース）
find tests -maxdepth 1 -name 'test_*.py' ! -name test_landmark_world.py -print0 | sort -z |
  xargs -0 -n1 -P4 sh -c 'name=${1##*/}; name=tests.${name%.py}; /tmp/venv038/bin/python -u -m "$name" >"/tmp/075-tests/$name.log" 2>&1; printf "%s\n" "$?" >"/tmp/075-tests/$name.status"' _
/tmp/venv038/bin/python -u -m tests.test_landmark_world >/tmp/075-tests/tests.test_landmark_world.log 2>&1
printf '%s\n' "$?" >/tmp/075-tests/tests.test_landmark_world.status
# prior_variant の初期計画分岐の互換性修正後
for name in tests.test_prior_free tests.test_landmark_world; do
  /tmp/venv038/bin/python -u -m "$name" > "/tmp/075-tests/$name.log" 2>&1
  printf '%s\n' "$?" > "/tmp/075-tests/$name.status"
done
cmp /tmp/075-tests/before-planners.log /tmp/075-tests/tests.test_planners.log
git diff --check
git diff --cached --check
```

### 保存地図からの配置・初期経路と参照点群の容量

次の Python を `/tmp/075-audit.py` に保存し、`conference/` から `OPENBLAS_NUM_THREADS=1 PYTHONPATH=. /tmp/venv038/bin/python -u /tmp/075-audit.py` を実行した。

```python
"""Verify the landmark maps and compressed reference sizes without Gazebo."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from ros2_jazzy.gz_checks.lidar_checks import BASELINE, case_world_inputs
from ros2_jazzy.gz_checks.online_batch_runtime import planning_map
from tapp.landmark_world import landmark_mask, place_landmarks, save_reference_cloud, with_landmarks
from tapp.online_mission import run_fixed_mission

scenarios = json.loads((BASELINE / 'manifest.json').read_text())['scenarios']
print('patch,land_m2,density,count,landmark_cells,debris_delta_changed,initial_path')
for meta in scenarios:
    patch = meta['patch']
    truth, prior = case_world_inputs(dict(patch=patch), meta, dict(map_method='fine'))
    before = truth['tmap'].rock & ~prior['tmap'].rock
    previous = []
    for density in (10, 40, 160):
        area, objects = place_landmarks(truth, patch, density, 0, [meta['start'], *meta['points'], *meta['stops']])
        assert objects[:len(previous)] == previous
        previous = objects
        mask = landmark_mask(truth['tmap'].shape, objects)
        tm, pm = [with_landmarks(sc, mask) for sc in (truth, prior)]
        changed = np.count_nonzero((tm['tmap'].rock & ~pm['tmap'].rock) ^ before)
        result = run_fixed_mission(planning_map(pm, 'TA*-S+inflate'), meta['start'], meta['stops'])
        print(f"{patch},{area},{density},{len(objects)},{mask.sum()},{changed},{result['success']}")
        assert not changed
    if meta is scenarios[0]:
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'reference_cloud.npz'
            for tag, subset in [('0', []), ('exactly160', objects[:160]), ('density160', objects)]:
                counts = save_reference_cloud(output, truth['tmap'].elev, subset)
                print('reference', patch, tag, len(subset), *counts, output.stat().st_size)
```

```text
mkdir -p failed for path /home/agent/.config/matplotlib: [Errno 30] Read-only file system: '/home/agent/.config/matplotlib'
Matplotlib created a temporary cache directory at /tmp/matplotlib-3drk9671 because there was an issue with the default path (/home/agent/.config/matplotlib); it is highly recommended to set the MPLCONFIGDIR environment variable to a writable directory, in particular to speed up the import of Matplotlib and to better support multiprocessing.
Fontconfig error: No writable cache directories
patch,land_m2,density,count,landmark_cells,debris_delta_changed,initial_path
08OB86_00294,19699.25,10,20,180,0,True
08OB86_00294,19699.25,40,79,643,0,True
08OB86_00294,19699.25,160,315,2621,0,True
reference 08OB86_00294 0 0 3984016 0 19862615
reference 08OB86_00294 exactly160 160 3984016 274772 20843345
reference 08OB86_00294 density160 315 3984016 552204 21851201
08OB86_-0205,18804.5,10,19,173,0,True
08OB86_-0205,18804.5,40,75,649,0,True
08OB86_-0205,18804.5,160,301,2569,0,True
08OB87_-0706,19623.0,10,20,166,0,True
08OB87_-0706,19623.0,40,78,662,0,True
08OB87_-0706,19623.0,160,314,2628,0,True
08OB88_-1417,19040.75,10,19,145,0,True
08OB88_-1417,19040.75,40,76,600,0,True
08OB88_-1417,19040.75,160,305,2507,0,True
08OB88_-0167,22748.75,10,23,177,0,True
08OB88_-0167,22748.75,40,91,745,0,True
08OB88_-0167,22748.75,160,364,3086,0,False
08OB88_00332,19485.5,10,19,167,0,True
08OB88_00332,19485.5,40,78,654,0,True
08OB88_00332,19485.5,160,312,2738,0,True
08OB88_01832,25308.25,10,25,237,0,True
08OB88_01832,25308.25,40,101,857,0,True
08OB88_01832,25308.25,160,405,3347,0,True
08OB89_00152,30143.25,10,30,222,0,True
08OB89_00152,30143.25,40,121,997,0,True
08OB89_00152,30143.25,160,482,4020,0,True
08OB89_-0347,30075.5,10,30,226,0,True
08OB89_-0347,30075.5,40,120,990,0,True
08OB89_-0347,30075.5,160,481,3977,0,True
08OB89_-0847,30146.5,10,30,258,0,True
08OB89_-0847,30146.5,40,121,1031,0,True
08OB89_-0847,30146.5,160,482,4080,0,True
```

0167 の失敗した区間も、同じ `run_fixed_mission` の `legs` と、両端の `pm.lethal` を読み直した。

```text
08OB88_-0167 start [202, 281] goal [137, 294] leg 5 reason no_path start_lethal False goal_lethal False
```

### センサー記録の容量試算

次の Python を `/tmp/075-storage.py` に保存し、`conference/` から `PYTHONPATH=. /tmp/venv038/bin/python -u /tmp/075-storage.py` を実行した。

```python
"""Size proxies from archived start frames and synthetic full-return scans."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from tapp.sensor_recording import IMU_COLUMNS, SensorArchive, pack_lidar, unpack_lidar
from tests.test_landmark_world import full_scans

files = sorted(Path('results/rtf_check/hayashi_rtf_repeat').rglob('first_cloud.npz'))
scans = []
for path in files:
    with np.load(path, allow_pickle=False) as data:
        scans.append(data['points'].astype(np.float32).reshape(16, 1800, 3))
archived = np.stack([scans[i % len(scans)] for i in range(20)])
print('archived_input_scans', len(scans))
print('proxy,points_with_xyz,exceptions,max_xyz_error_mm,npz_bytes,archive_2s_bytes,estimated_120s_MB')
for label, group in [('repeated_start_scans', archived), ('synthetic_full_returns', full_scans(75, 20))]:
    arrays = pack_lidar(group)
    valid = np.isfinite(group).all(axis=-1)
    decoded = unpack_lidar(arrays)
    np.testing.assert_array_equal(decoded[~valid], group[~valid])
    error = np.linalg.norm(decoded[valid]-group[valid], axis=-1).max()
    assert error <= .001
    with TemporaryDirectory() as temp:
        folder = Path(temp) / 'sensors'
        archive = SensorArchive(folder)
        rng = np.random.default_rng(75)
        for i in range(20):
            for j in range(5):
                archive.add('imu', i*100_000_000+j*20_000_000, 'imu', rng.normal(size=len(IMU_COLUMNS)))
            for j in range(2):
                archive.add('ground_truth', i*100_000_000+j*50_000_000, 'world', rng.normal(size=7))
            archive.add('lidar', i*100_000_000, 'lidar', group[i])
        archive.close()
        metadata = json.loads((folder/'metadata.json').read_text())
        total = metadata['chunk_bytes'] + (folder/'metadata.json').stat().st_size
        estimate = (metadata['chunk_bytes']*60 + (folder/'metadata.json').stat().st_size)/1e6
        print(label, valid.sum(), len(arrays['exception_indices']), f'{error*1000:.6f}',
              metadata['chunk_bytes'], total, f'{estimate:.3f}', sep=',')
```

```text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
archived_input_scans 6
proxy,points_with_xyz,exceptions,max_xyz_error_mm,npz_bytes,archive_2s_bytes,estimated_120s_MB
repeated_start_scans,255016,0,0.500428,580786,582160,34.849
synthetic_full_returns,576000,0,0.500719,1343806,1345181,80.630
```

### 初期計画の互換性修正

全体テスト途中で `tests.test_prior_free` が、初期計画の分岐を取り出して実行する検査で失敗した。prior の変更から初期計画までを同じ分岐に置いたうえで、当該モジュールと 075 を再実行した。既存のテストコードは変更していない。

<details>
<summary>修正前の tests.test_prior_free の出力</summary>

```text
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
2-4 PASS: flat/20deg plane and 0.4m boxes, with exact and +/-0.4m shifted priors
slope_deg box prior_shift_m reference false_positive_cells missed_cells
0.0 False 0.0 prior 0 0
0.0 False 0.0 local 0 0
0.0 False -0.4 prior 81 0
0.0 False -0.4 local 0 0
0.0 False 0.4 prior 0 0
0.0 False 0.4 local 0 0
0.0 True 0.0 prior 0 0
0.0 True 0.0 local 0 0
0.0 True -0.4 prior 80 0
0.0 True -0.4 local 0 0
0.0 True 0.4 prior 0 1
0.0 True 0.4 local 0 0
20.0 False 0.0 prior 0 0
20.0 False 0.0 local 0 0
20.0 False -0.4 prior 81 0
20.0 False -0.4 local 0 0
20.0 False 0.4 prior 0 0
20.0 False 0.4 local 0 0
20.0 True 0.0 prior 0 0
20.0 True 0.0 local 0 0
20.0 True -0.4 prior 80 0
20.0 True -0.4 local 0 0
20.0 True 0.4 prior 0 1
20.0 True 0.4 local 0 0
local support PASS: fewer than 3/collinear minima remain unclassified; both real sensor modes fuse sensor-only evidence and attribution
5 PASS: true world box tops equal component maximum; lower edges/footprints/collision-visual sizes and truth NPZ unchanged
6 PASS: SeedSequence reproducibility, distinct patch seeds, preserved sea/nodata, flat none and immutable input arrays
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis_Bunker/conference/tests/test_prior_free.py", line 265, in <module>
    test()
  File "/workspace/thesis_Bunker/conference/tests/test_prior_free.py", line 254, in test_cli
    exec(compile(ast.fix_missing_locations(ast.Module(body=[initial_branch], type_ignores=[])), '<initial prior>', 'exec'), context)
  File "<initial prior>", line 493, in <module>
NameError: name 'objects' is not defined. Did you mean: 'object'?
```

</details>

## テスト出力全文

変更後の全 59 モジュールが終了コード 0。変更前後のプランナーテスト出力も `cmp` で一致した。

<details>
<summary>変更前の tests.test_planners</summary>

````text
all planner tests passed
roll-aware tests passed
````

</details>

<details>
<summary>tests.test_beach_terrain</summary>

````text
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed
````

</details>

<details>
<summary>tests.test_collision</summary>

````text
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
````

</details>

<details>
<summary>tests.test_common_eval</summary>

````text
beach beach centre n=1 no_path=1
1 runs -> /tmp/tmp8prog6c6/output
synthetic: geometry, revision boundaries, stops, timing, gzip, omissions and overwrite protection passed
030 08OB87_-0706 C0 n=3 completed=3
030 08OB87_-0706 C1 n=3 completed=3
030 08OB87_-0706 C2 n=3 completed=3
030 08OB88_-0167 C0 n=3 no_path=3
030 08OB88_-0167 C1 n=3 no_path=3
030 08OB88_-0167 C2 n=3 rollover=3
030 08OB88_-1417 C0 n=3 no_path=3
030 08OB88_-1417 C1 n=3 completed=3
030 08OB88_-1417 C2 n=3 completed=3
030 08OB89_-0347 C0 n=3 no_path=3
030 08OB89_-0347 C1 n=3 no_path=3
030 08OB89_-0347 C2 n=3 partial=3
030 08OB89_-0847 C0 n=3 no_path=3
030 08OB89_-0847 C1 n=3 completed=1 stuck=2
030 08OB89_-0847 C2 n=3 completed=2 partial=1
45 runs -> /tmp/tmp8prog6c6/030
030 compared per-field counts: {'exit_code': 45, 'outcome': 45, 'status': 45, 'recorded_status': 45, 'goals_reached': 45, 'returned_to_start': 45, 'truth_lethal_len_m': 45, 'truth_lethal_entries': 45, 'debris_len_m': 45, 'debris_entries': 45, 'lethal_cells': 45, 'debris_cells': 45, 'rolled_over': 45, 'deviation_mean_m': 45, 'deviation_max_m': 45, 'n_plans': 45, 'failed_plans': 45, 'fail_goal_cell': 45, 'fail_start_cell': 45, 'fail_start_steep': 45, 'map_fp_cells': 43, 'map_fn_cells': 43, 'map_fp_steep_cells': 43, 'map_fp_obstacle_only_cells': 43, 'detector_fp_cells': 43, 'detector_fn_cells': 43, 'map_updates': 45, 'map_update_s_p95': 45, 'stops_unreachable': 15, 'relaxed_len_m': 15, 'relaxed_truth_lethal_len_m': 15, 'rollover_t_s': 3}
035 08OB86_-0205 S1 n=1 completed=1
035 08OB86_-0205 S2 n=1 other_error=1
035 08OB87_-0706 P1 n=3 completed=3
035 08OB88_-0167 P1 n=3 no_path=3
035 08OB88_-1417 P1 n=3 completed=3
035 08OB89_-0347 P1 n=3 no_path=3
035 08OB89_-0847 P1 n=3 completed=3
17 runs -> /tmp/tmp8prog6c6/035
035 compared per-field counts: {'exit_code': 17, 'outcome': 17, 'status': 17, 'n_plans': 16, 'n_replans': 16, 'failed_plans': 16, 'fail_goal_cell': 16, 'ev_off_path': 16, 'ev_unsafe_tilt': 16, 'ev_safety_replanned': 16, 'map_updates': 16, 'map_update_s_median': 16, 'map_update_s_p95': 16, 'map_update_s_max': 16, 'queue_drops': 16} plus 6 sensor rows
037 08OB86_-0205 L n=3 unknown=3
037 08OB86_-0205 LC n=3 unknown=3
037 08OB88_-0167 L n=3 unknown=3
037 08OB88_-0167 LC n=3 unknown=3
037 08OB88_-1417 L n=3 unknown=3
037 08OB88_-1417 LC n=3 unknown=3
037 08OB88_00332 L n=3 unknown=3
037 08OB88_00332 LC n=3 unknown=3
037 08OB89_-0847 L n=3 unknown=3
037 08OB89_-0847 LC n=3 unknown=3
30 runs -> /tmp/tmp8prog6c6/037
037 matched 30 metadata/exit records; absent raw outcome, geometry, events and updates stayed blank
all common evaluation tests passed
````

</details>

<details>
<summary>tests.test_distance_clearance</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: default/centre/overlap/overlap_goal match the base on this host for maps, plans, manifests and ROS dispatch
2 PASS: hard mask matches centre and exact rectangle distance; quadratic band and endpoint limits
3 PASS: distance increases box clearance and all three forced corridors remain passable
4 PASS: cost-acceptable shortcuts cannot reduce the exact segment-to-box minimum
5 PASS: local queries omit distant tiles and incremental distance/cost match the full rebuild
08OB86_00294 completed
integration PASS: metadata, Docker/ROS options, Multi terrain/safety modes and recorded obstacle costs
all task060 distance clearance tests passed
````

</details>

<details>
<summary>tests.test_dstar</summary>

````text
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
````

</details>

<details>
<summary>tests.test_edge_margin</summary>

````text
sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability
sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed
cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained
synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it
report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance
real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS
dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer
Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest
all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)
````

</details>

<details>
<summary>tests.test_endpoint_component</summary>

````text
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: only two corrected start_steep labels differ in replay; all other fields and four preparation variants unchanged
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
saved component contract: both start_steep cases clear ZERO cells, protect all raw masks, retry once and advance to the next stop
all task028b component tests passed (Python only; Gazebo not run)
````

</details>

<details>
<summary>tests.test_endpoint_policy</summary>

````text
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).
````

</details>

<details>
<summary>tests.test_false_steep_causes</summary>

````text
1 PASS: geometry, exact slope labels, box halo, point counts, missing stencil, relief, sea/nodata and view angles
2 PASS: committed final/first/failure data produce CSVs and a missing run is explicitly skipped
all task053 false-steep-cause tests passed
````

</details>

<details>
<summary>tests.test_false_steep_inspect</summary>

````text
1 PASS: actual lethal and steep layers, true halo and independent obstacles; first/middle/last/max
2 PASS: signed high/low endpoint errors and central/edge stencil, with optional point counts
3 PASS: fine-cell centres, inclusive 0.2 and 0.5 m, empty and absent obstacle maps
4 PASS: missing records have explicit skip reasons; independent final evidence and optional counts retained
all task069 false-steep inspection tests passed
````

</details>

<details>
<summary>tests.test_footprint</summary>

````text
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
````

</details>

<details>
<summary>tests.test_geo</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
````

</details>

<details>
<summary>tests.test_goal_region</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host pre-change versus none manifest, ROS dispatch, command and runtime log bytes
selection PASS: nearest feasible ring, strict visibility/steep filters, blocked start and cost tie
2 PASS: box halo unmodified; centre/overlap_goal/distance, v1/v2, plan snapshots and no reachable candidate
3 PASS: steep halo, restore before arrival, stale substitution rejected by the preserved safety handoff
08OB86_00294 completed
configuration PASS: manifest, ROS options, direct CLI, Docker forwarding and incompatible mode
all task063 goal-region tests passed
````

</details>

<details>
<summary>tests.test_gpu_rendering</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
Docker PASS: implicit/explicit CPU argv and env byte-identical to 045 and 056 bases; GPU mounts read-only vendor, forces EGL selection, rejects missing file before Docker, preserves toolkit errors
08OB86_00294 completed
08OB86_00294 completed
manifest PASS: CPU preparation and final mocked dispatch byte parity; GPU records passed EGL vendor only
renderer/cloud PASS: 054 Mesa/llvmpipe, sample NVIDIA and partial contexts; earliest pre-motion common stamp and matched pose range statistics
summary PASS: valid renderer/RTF/GPU usage kept when a cloud pair is unavailable
08OB86_00294 completed
GPU checkpoint PASS: run folder and Ogre2 verdict remain in the manifest before normal teardown
partial summary PASS: 054 GPU manifest without run_folder, interrupted mission and signal exit keep CPU fields
all task045/056 GPU rendering tests passed
````

</details>

<details>
<summary>tests.test_ground_estimate</summary>

````text
1 PASS: implicit/explicit all_returns match pre-change update JSON, snapshots, histories, NPZ and multi-sensor sidecar bytes
2 PASS: 0.55m box creates false steep neighbours only with all_returns; box detection/inflation and all evidence unchanged
ground_estimate x y slope_deg steep box_lethal
all_returns 9 10 28.810793742973065 True True
all_returns 11 10 28.810793742973065 True True
all_returns 10 9 28.810793742973065 True True
all_returns 10 11 28.810793742973065 True True
non_obstacle 9 10 0.0 False True
non_obstacle 11 10 0.0 False True
non_obstacle 10 9 0.0 False True
non_obstacle 10 11 0.0 False True
3 PASS: all-excluded cells retain prior height and seen status; last-64 ALL returns displace older ground, then ground observations resume
4 PASS: sub-0.3m terrain changes retained; bilinear prior and the unchanged >=0.3m obstacle boundary used
5 PASS: LiDAR+two cameras share unchanged 2+1 detection evidence, source attribution and filtering; ground-only median removes false steep cells
configuration PASS: byte-identical default manifests; opt-in factory, CLI, ROS parameter and actual node constructor propagation; invalid/coarse combinations rejected
all ground-estimate tests passed; requirement 6 is verified by running every conference/tests module separately (Python only)
````

</details>

<details>
<summary>tests.test_ground_near_obstacle</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/implicit/explicit keep map, sensor, plan, ROS and manifest bytes
2 PASS: low box wall induces a false steep cell only in keep; same detections, halo and coverage
3 PASS: the true ramp remains steep and detection is identical for prior and local reference
4 PASS: zero returns preserves prior/previous height; 0.2m boundary; dirty history agrees with full rebuild
08OB86_00294 completed
integration PASS: Fine/Multi, manifest, ROS and Docker args, distance/no_inflate/pose trace/plan maps, prior height only
all task062 ground-near-obstacle tests passed
````

</details>

<details>
<summary>tests.test_gz_compare</summary>

````text
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)
````

</details>

<details>
<summary>tests.test_gz_online_batch</summary>

````text
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)
````

</details>

<details>
<summary>tests.test_lab_geometry</summary>

````text
1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation
2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost
3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253
4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation
5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured
all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite
````

</details>

<details>
<summary>tests.test_landmark_world</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host previous/default bytes for full mocked output trees, launch and dispatch
2 PASS: 161 landmarks over 10045 m², density, seed, nested positions and gaps
3 PASS: serialized prior blocks landmarks, evaluation counts debris but excludes known landmarks
4 PASS: terrain triangles and both static surfaces agree with XYZ within 5e-05 m
5 PASS: 0.500712 mm maximum Euclidean error, exceptions and empty scan preserved
capture PASS: original ROS topics/stamps, endian/row padding, cutoff and strict byte cap
08OB86_00294 completed
dispatch PASS: world, reference, manifest and separate truth-only recorder alongside pose error
all landmark world tests passed
````

</details>

<details>
<summary>tests.test_lidar_figures</summary>

````text
T4: 24 rows
T5: 38 rows
T6: 20 rows
T7: 12 rows
F8–F11, T4–T7, numbers_lidar.tex and sources.json: /tmp/tmp_gfehlf6/archive
archive PASS: all figures/tables, macros recalculated from source CSVs and exact input hashes
missing/044 PASS: remaining outputs and missing-input message; common schema extends the figures
output guard PASS: existing results, pillar-one output and paper paths rejected
050 PASS: completion and both T5 scopes are recalculated from the committed CSV
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/eval_ground_endpoint/runs.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/eval_035/runs.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/real_sensors_compare/runs.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/rtf_compare/stage_b/common_eval/runs.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/eval_064/common_eval_all/runs.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/waypoint_feasibility/goal_cell.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/terrain_from_prior/goals.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/map_speed/timing.csv
Skipped missing results file: /tmp/tmp_gfehlf6/terrain/results/rtf_compare/stage_b/sensor_updates.csv
T4: 10 rows
T5: 15 rows
T6: 4 rows
T7: 0 rows
F8–F11, T4–T7, numbers_lidar.tex and sources.json: /tmp/tmp_gfehlf6/terrain/out
057 PASS: missing input is reported and an added CSV updates F10, the tables and input hashes
legacy PASS: same-environment 030–044 tables, F9 statistics and all prior numeric macros match
064 PASS: 180 committed runs, six GPU cohorts and T4–T6/count macros match the CSV
T7 PASS: exactly 4 comparisons × 3 measures, two-sided Fisher and within-measure Holm p values
pre-068 PASS: T4–T6 rows for 030–057, old macros and F8–F10 match same-host baseline bytes
all LiDAR figure tests passed
````

</details>

<details>
<summary>tests.test_local_speed</summary>

````text
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmp089nf929/ten
024 08OB86_00294 start=[52, 195] points=[[309, 113], [273, 232], [104, 176], [46, 121], [250, 270]] unchanged=False
024 08OB86_-0205 start=[49, 270] points=[[114, 102], [114, 214], [42, 179], [135, 255], [93, 197]] unchanged=True
024 08OB87_-0706 start=[50, 200] points=[[89, 197], [263, 259], [59, 119], [347, 145], [39, 236]] unchanged=False
024 08OB88_-1417 start=[70, 169] points=[[337, 140], [313, 165], [199, 151], [264, 194], [203, 229]] unchanged=True
024 08OB88_-0167 start=[38, 231] points=[[137, 294], [249, 150], [202, 281], [31, 208], [348, 149]] unchanged=True
024 08OB88_00332 start=[45, 228] points=[[142, 207], [38, 131], [203, 180], [136, 171], [70, 116]] unchanged=True
024 08OB88_01832 start=[36, 214] points=[[223, 254], [335, 247], [159, 229], [264, 180], [133, 240]] unchanged=False
024 08OB89_00152 start=[48, 341] points=[[296, 173], [183, 372], [207, 192], [328, 186], [193, 222]] unchanged=False
024 08OB89_-0347 start=[55, 326] points=[[294, 224], [164, 169], [213, 144], [195, 352], [264, 374]] unchanged=False
024 08OB89_-0847 start=[70, 146] points=[[269, 98], [75, 211], [227, 332], [281, 117], [350, 279]] unchanged=True
024 PASS: 10/10 archived waypoint lists, 5/5 unchanged scenarios, default manifest bytes and wrapper forwarding
032 slope=0 box=False shift=0: fine/coarse=(0, 0)
032 slope=0 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0: fine/coarse=(0, 0)
032 slope=0 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0: fine/coarse=(0, 0)
032 slope=20 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0: fine/coarse=(0, 0)
032 slope=20 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0.4: fine/coarse=(0, 0)
CPU AMD EPYC 9V74 80-Core Processor
fixture sensor input accepted repeats before_median_s before_p95_s after_median_s after_p95_s fine_diff coarse_diff
synthetic lidar 28800 28800 12 5.869696 10.965328 0.185692 0.364582 0 0
synthetic camera1 26750 26750 12 8.477438 12.335125 0.033519 0.062566 0 0
saved_b0b lidar 28800 11741 1 2.116090 2.116090 0.073597 0.073597 1 1
saved_b0b camera1 26750 9604 1 2.901701 2.901701 0.061712 0.061712 0 0
saved_b0b camera2 26750 9242 1 3.491410 3.491410 0.032024 0.032024 0 0
all local speed tests passed
````

</details>

<details>
<summary>tests.test_localizability_map</summary>

````text
test_alongshore_gaps_ignore_duplicate_cross_shore_positions (__main__.LocalizabilityTests.test_alongshore_gaps_ignore_duplicate_cross_shore_positions) ... ok
test_extruded_shoreline_leaves_alongshore_ambiguous (__main__.LocalizabilityTests.test_extruded_shoreline_leaves_alongshore_ambiguous) ... ok
test_hessian_includes_mixed_derivatives_in_physical_units (__main__.LocalizabilityTests.test_hessian_includes_mixed_derivatives_in_physical_units) ... ok
test_matching_ignores_samples_shifted_outside_the_patch (__main__.LocalizabilityTests.test_matching_ignores_samples_shifted_outside_the_patch) ... ok
test_off_centre_cone_is_determined (__main__.LocalizabilityTests.test_off_centre_cone_is_determined) ... ok
test_repeated_hill_has_second_minimum (__main__.LocalizabilityTests.test_repeated_hill_has_second_minimum) ... ok
test_uniform_source_height_offset_does_not_change_result (__main__.LocalizabilityTests.test_uniform_source_height_offset_does_not_change_result) ... ok
test_visibility_agrees_with_existing_ray_model_at_edges (__main__.LocalizabilityTests.test_visibility_agrees_with_existing_ray_model_at_edges) ... ok

----------------------------------------------------------------------
Ran 8 tests in 1.722s

OK
````

</details>

<details>
<summary>tests.test_map_speed</summary>

````text
byte-identical replay against the pre-038 implementation: 88 update states; states differing from the hashes stored on the recording machine: 0
````

</details>

<details>
<summary>tests.test_mapfiles_sim</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
````

</details>

<details>
<summary>tests.test_mission</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
````

</details>

<details>
<summary>tests.test_natural_terrain</summary>

````text
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed
````

</details>

<details>
<summary>tests.test_obstacle_clearance</summary>

````text
1 PASS: centre default/explicit, prior/local, fine/multi; maps match the pre-041 implementation on this machine (recorded hashes also match); manifest, ROS-mocked commands and existing none/v1/v2 files match baseline
2 mode min_path_clearance_m lethal_cells path_grid
centre 0.477533728 4 [(10, 15), (11, 7)]
overlap 1.123456796 12 [(10, 15), (12, 10), (12, 8), (11, 7)]
3 PASS: full recompute after 20 updates across prior/local and fine/multi, plus dense/sparse edge cases
3 planning PASS: inferred overlap halo blocks unseen cells in normal and diagnostic planner snapshots
4 B PASS: periodic observed data incl. empty map, exact trajectory-to-box distance, CSV parts and truth-mask fallback
4 C1-C3 PASS: missing plan_history, shared path_distance (300 decisions, 23 rounding cases), class default
4 C4 and routing PASS: env-selected 1.0 honoured, overlap manifest, ROS command and wrapper
4 ROS constructor PASS: v2 runtime, overlap mapper and diagnostics selected together
all task041 obstacle clearance tests passed
````

</details>

<details>
<summary>tests.test_online</summary>

````text
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
````

</details>

<details>
<summary>tests.test_online_deadend</summary>

````text
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed
````

</details>

<details>
<summary>tests.test_online_mission</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
````

</details>

<details>
<summary>tests.test_online_safety</summary>

````text
1 PASS: implicit/explicit none match pre-change runtime command JSON, plans/diagnostic bytes, follower trajectory/mission bytes and manifests
2 PASS: LiDAR and perfect-radius joins exempt only the start cell; later lethal cells remain rejected
3 PASS: actual stuck_0847_C1_r2_t1345 fixture search and handoff
online_fixes search_success handoff path_points outside_start_lethal_cells start_lethal
none True False 0 0 True
v1 True True 5 0 True
4 PASS: consecutive join rejection terminates at exactly 10 simulation seconds; acceptance resets the interval
5 PASS: known free-to-lethal on remaining path triggers lethal_changed only in v1; off-path changes do not replan; pending changes reset on planning
6 PASS: +/-26deg roll/pitch and 0.8m deviation stop; 24/25deg and 0.7/0.75m do not; zero linear and angular speed
safety recovery PASS: stop invalidates old work, replans from measured position, accepts replacement, ignores stale status and ends on no-path
ROS adapter PASS: real callbacks publish zero/status, preserve the open run, relay the stop and resume on a replanned path
diagnostics/concurrency PASS: v1 records diagnostics without 028b relaxation; busy pre-stop work cannot hand off and recovery uses the latest pose
configuration PASS: v1 manifest/CLI and both ROS parameter commands; 028b unchanged and excluded from v1
all online-safety tests passed; requirement 7 is checked by the complete conference/tests run
````

</details>

<details>
<summary>tests.test_overlap_goal</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default, explicit centre and overlap bytes for Fine/Multi, none/v1/v2, manifest, ROS launch, paths, diagnostics and plan maps
2 PASS: overlap-only goal opens even if unseen; centre halo, prior rock and steep halo still block; Fine/Multi and sensor/prior/prior_veto
3 PASS: intermediate and former goals retain overlap, old start handoff rules apply, latest centre blockage triggers v1/v2 replanning
08OB86_00294 completed
4 PASS: manifest, ROS and mocked Docker forwarding, fine-only validation, both synthetic paths and 12 archived goals
all task052 overlap goal tests passed
````

</details>

<details>
<summary>tests.test_path_tracking</summary>

````text
1 PASS: before/current same-host manifest, ROS states, commands, trajectory, replan and stop bytes for none/v1/v2
2 PASS: straight speed, 2m corner window, 60-degree 0.5 m/s cap and strict 45-degree spin
3 PASS: 0.3 s rise/decay, 80% steady turn response, no-lag trace equals robot_sim
wiring PASS: opt-in initial/replacement paths with none/v1/v2, manifest, ROS args and Docker stub
all task043 tracking tests passed
````

</details>

<details>
<summary>tests.test_plan_map_snapshots</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default manifest, missions, commands, plan CSV and diagnostic NPZ bytes; opt-in forwarding
Plan map recording stopped at 4.5 sim s: storage limit
2 PASS: exact search maps, signed-zero/delta cost, paths, prior_veto mask, handoff association and byte cap
approach: 1 rows
goal_cell: 1 rows
skipped: 0 rows
/tmp/tmpeafla_k9/absent [approach and goal_cell] skipped: no saved search maps; cannot inspect box detection or first goal block
3 PASS: interpolated closest approach uses the last handed-off plan; first blocked goal and missing-record handling
all task051 plan map snapshot tests passed
````

</details>

<details>
<summary>tests.test_planners</summary>

````text
all planner tests passed
roll-aware tests passed
````

</details>

<details>
<summary>tests.test_pointcloud_map</summary>

````text
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis_Bunker/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)
````

</details>

<details>
<summary>tests.test_pointcloud_map_fine</summary>

````text
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)
````

</details>

<details>
<summary>tests.test_pose_error</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/default/none manifest, commands, run files and follower bytes
2 PASS (legacy): oblique coast, yaw, same stamped pose for cloud registration, planning, control and arrival
2 PASS (lidar_real+depth2): oblique coast, yaw, same stamped pose for cloud registration, planning, control and arrival
drift L=  1 m theory=0.010000 sample_xy=0.009762,0.009542
drift L= 10 m theory=0.031623 sample_xy=0.030688,0.031450
drift L=100 m theory=0.100000 sample_xy=0.098146,0.096925
3 PASS: 1,000 drift walks, ±10% sample standard-deviation limit, mission start and no yaw drift
4 PASS: eval_runs measures truth clearance, rollover and endpoint-mask travel without estimated fallback
08OB86_00294 completed
Task072 preparation only; Gazebo not executed: /tmp/tmpa95w2xeh/prepared
wiring PASS: selected patch axes and seed, shared topic, CLI parameters and shell forwarding
all task072 pose-error tests passed
````

</details>

<details>
<summary>tests.test_pose_trace</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default manifest, run files, ROS arguments, commands, timeout boundary and control bytes for none/v1/v2
2 PASS: shared upstream, follower receipt, follower processing, missing data, stamp fallback and CPU evidence
Task058 preparation only; Gazebo not executed: /tmp/tmpkorwd9oc/prepared
08OB86_00294 completed
3 PASS: CLI/manifest, ROS trace destinations, fake Docker, bounded CSV rollover and CPU sample
all task058 pose trace tests passed
````

</details>

<details>
<summary>tests.test_prior_free</summary>

````text
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
2-4 PASS: flat/20deg plane and 0.4m boxes, with exact and +/-0.4m shifted priors
slope_deg box prior_shift_m reference false_positive_cells missed_cells
0.0 False 0.0 prior 0 0
0.0 False 0.0 local 0 0
0.0 False -0.4 prior 81 0
0.0 False -0.4 local 0 0
0.0 False 0.4 prior 0 0
0.0 False 0.4 local 0 0
0.0 True 0.0 prior 0 0
0.0 True 0.0 local 0 0
0.0 True -0.4 prior 80 0
0.0 True -0.4 local 0 0
0.0 True 0.4 prior 0 1
0.0 True 0.4 local 0 0
20.0 False 0.0 prior 0 0
20.0 False 0.0 local 0 0
20.0 False -0.4 prior 81 0
20.0 False -0.4 local 0 0
20.0 False 0.4 prior 0 0
20.0 False 0.4 local 0 0
20.0 True 0.0 prior 0 0
20.0 True 0.0 local 0 0
20.0 True -0.4 prior 80 0
20.0 True -0.4 local 0 0
20.0 True 0.4 prior 0 1
20.0 True 0.4 local 0 0
local support PASS: fewer than 3/collinear minima remain unclassified; both real sensor modes fuse sensor-only evidence and attribution
5 PASS: true world box tops equal component maximum; lower edges/footprints/collision-visual sizes and truth NPZ unchanged
6 PASS: SeedSequence reproducibility, distinct patch seeds, preserved sea/nodata, flat none and immutable input arrays
configuration PASS: factory/CLI/manifest/ROS command forwarding; invalid coarse/local rejected; Gazebo not started
all prior-free tests passed; requirement 7 is checked by the separate complete test-module run
````

</details>

<details>
<summary>tests.test_real_beach</summary>

````text
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
````

</details>

<details>
<summary>tests.test_real_beach_las</summary>

````text
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
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed
````

</details>

<details>
<summary>tests.test_real_sensors</summary>

````text
PASS legacy model SDF (with/without LiDAR) and fine-map NPZ SHA256 match pre-change bytes
PASS real preset mounts, symmetry, unchanged LiDAR spec and camera FOV/ranges without intrinsics
A2 camera1: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
A2 camera2: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
PASS A2: three camera-free SDFs byte-identical; depth SDF/spec change only prescribed resolution and intrinsics
PASS arbitrary sensor/model roll-pitch-yaw and translation match independent homogeneous transform
PASS both outward cameras: ground/box registration, shared 2+1 evidence, one inflation and saved provenance
PASS synthetic camera boxes in LiDAR blind zone at 1.5/2/3m; residual 1m blind zone disclosed
PASS per-sensor range/FOV/finite filtering and byte-identical task023 fusion/inflation for registered input
PASS manifest records all real specs/mounts; explicit fine selection; Docker wrapper forwards sensor flags
PASS A2 wrapper: unset flags preserve full legacy argv bytes; individual/both/empty supplied values forwarded (fake Docker only)
PASS analytic 4.105m LiDAR near bound, discrete-beam gap, rear blind zone and camera symmetry
PASS actual ROS adapter: bounded queues, fair sources, stamped transforms, logs and freshness (transport mocked)
all real sensor tests passed (synthetic/geometry only; Gazebo not run)
````

</details>

<details>
<summary>tests.test_review_fixes</summary>

````text
1 PASS: none/v1 commands, ROS follower state and log bytes unchanged; full manifest hashes 8/8
A1 v1 second tilt after 9s: replanned
A1 v2 second tilt after 9s: terminal unsafe_tilt
A1 v2 second tilt after 10s: terminal unsafe_tilt
A1 v2 second tilt after 10.1s: replanned
A2 v1 duplicate segment, 0.8m: running
A2 v2 duplicate segment, 0.8m: off_path
A3 v1 near passed segment and 0.8m from remaining route: running
A3 v2 near passed segment and 0.8m from remaining route: off_path
B6 PASS: the box is detected with support 0.70m from its centre
B9 PASS: dense/cKDTree agree on 298 heights, including unknown support
B8 5f36770 local_ground_032.py SHA-256 5a57c07f09d31e0fcf7508de6ddc28e05253cca13939eeda767ffca2ef7491f5
B8 5f36770 pointcloud_map_multi_032.py SHA-256 710d81185c5a945e9c89d1d679414c6846832f779edbc6a9e9065823ba67dc96
v2 configuration PASS: manifest, CLI, both ROS parameters and async factory
B10 PASS: fine world input NPZ, world SDF and heightmap match byte for byte; coarse matching remains explicit
Task036 task023 aggregation skipped: the waypoint cohort differs from the cached task022 controls. Manifest and available raw results: /tmp/tmpwi39v7by/edge
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpwi39v7by/coarse
Task036 task023 aggregation skipped: opt-in conditions require separate evaluation from task023. Manifest and available raw results: /tmp/tmpwi39v7by/opt-in
B11 PASS: standard aggregation selected only for a comparable fine cohort
B7 controlled scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 0
6 0 0 0
7 0 0 0
8 0 0 0
9 0 0 0
10 0 0 0
11 0 0 0
B7 review scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 2
6 2 2 1
7 4 2 0
8 8 2 0
9 10 3 5
10 13 3 0
11 11 2 0
all task040 review-fix tests passed
````

</details>

<details>
<summary>tests.test_risk_prior</summary>

````text
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
````

</details>

<details>
<summary>tests.test_ros2_gz</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
````

</details>

<details>
<summary>tests.test_rtf_option</summary>

````text
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
default 0.3 PASS: omitted/explicit match, manifest and report match pre-change hashes (full manifest)
1.0 PASS: historical overlay manifest settings and world target match; stale=1.0, step=0.001, LiDAR=10Hz
validation PASS: explicit 0.3 overrides environment; legacy rtf_check still works; invalid factor, stale and coarse rejected
wrapper PASS: split and equals options forward unchanged, with identical Docker setup
run finalization PASS: explicit 1.0 preserves manifest and skips incompatible task023 summary
all task039 RTF option tests passed
````

</details>

<details>
<summary>tests.test_slope_uncertainty</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/default/none Fine and Multi map, manifest, ROS dispatch and plan bytes
2 PASS: 26-degree noisy slope is passable at cost 1.0; supported 30-degree slope keeps its halo
3 PASS: sample and slope errors, shared corner, prior/single/held fallbacks and local ground
08OB86_00294 completed
wiring PASS: manifest, ROS CLI, shell forwarding, independent obstacle clearance and plan fields
all task066 slope uncertainty tests passed
````

</details>

<details>
<summary>tests.test_stale_prior_risk</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: sensor and prior NPZ, snapshot, multi-sensor sidecar and mocked runner bytes match same-host base
2 PASS: cutoff at 32 of 63/64; unchanged height crossing triggers veto, 0.5m halo, subsequent clearing
3 PASS: unchanged real prior slopes in all three modes; both prior modes also forbid unobserved steep cells
08OB86_00294 completed
configuration PASS: manifest, ROS argument, planner CLI, Multi local/overlap, fine-only validation and fake Docker
all task048 stale-prior-risk tests passed
````

</details>

<details>
<summary>tests.test_steep_clearance</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre
2 PASS: unchanged hard stencil, exact square distances and quadratic soft costs add to obstacle costs
3 PASS: route moves farther from slopes and all three forced gaps remain reachable
4 PASS: no clearance-reducing shortcuts; local add/remove and all terrain sources match rebuild
08OB86_00294 completed
integration PASS: CLI, manifest, ROS and fake Docker, Multi and both saved soft layers
all task065 steep clearance tests passed
````

</details>

<details>
<summary>tests.test_steep_near_obstacle</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host implicit and explicit keep, Fine/Multi, all terrain sources, manifests, ROS args and plan logs
2 PASS: covered slope stays lethal, external slope keeps inflation, obstacle/height/cost bytes agree
3 PASS: obstacle-only local update and later height changes match full rebuild for Fine/Multi and all clearances
prior/veto PASS: prior seeds and rocks kept, former inferred halo refreshed, overlap_goal and plan maps work with none/v1/v2
08OB86_00294 completed
CLI PASS: fine-only opt-in, manifest, ROS args and fake Docker forwarding
all task055 steep-near-obstacle tests passed
````

</details>

<details>
<summary>tests.test_terrain_from_prior</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host before/after NPZ, update results, multi-sensor sidecars, snapshots and none/v1/v2 dispatch bytes
2 PASS: apparent steepness blocks the goal only with sensor terrain, with the same sensor elevation and box evidence
3 PASS: Fine/Multi × prior/local with overlap retains box and unobserved true steep hazards; v1/v2 tilt stop intact
08OB86_00294 completed
configuration PASS: manifest, production command, direct planner CLI, real-sensor factory and fake Docker
4 PASS: all 35 failures classified; 9/14 recovered on final maps, 3/6 on failure snapshots, 15 without either
all task047 terrain-source tests passed
````

</details>

<details>
<summary>tests.test_thesis_figures</summary>

````text

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
````

</details>

<details>
<summary>tests.test_tour</summary>

````text
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed
````

</details>

<details>
<summary>tests.test_tour_real_beach</summary>

````text
test_all_orders_use_same_008_legs_and_match_brute_force (__main__.TourRealBeachTests.test_all_orders_use_same_008_legs_and_match_brute_force) ... ok
test_clustered_goals_are_deterministic_separated_and_reachable (__main__.TourRealBeachTests.test_clustered_goals_are_deterministic_separated_and_reachable) ... ok
test_time_accounts_for_overlapping_corner_lookahead (__main__.TourRealBeachTests.test_time_accounts_for_overlapping_corner_lookahead) ... ok
test_time_matches_straight_and_right_angle_controller_speeds (__main__.TourRealBeachTests.test_time_matches_straight_and_right_angle_controller_speeds) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.746s

OK
````

</details>

<details>
<summary>tests.test_tracking_error</summary>

````text
1 PASS: full-path distance, Menger curvature, slope, motion direction and command bins
2 PASS: pre-path samples, same-time revisions, causal switches and task042 percentile parity
approaches PASS: interpolated strict clearance and same-box attribution
3 PASS: committed archive tables, explicit skipped input and published event-evidence coverage
all task061 tracking-error tests passed
````

</details>

<details>
<summary>tests.test_visibility</summary>

````text
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed
````

</details>

<details>
<summary>tests.test_waypoint_feasibility</summary>

````text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
geometry PASS: statuses, 1 m boundary, closest A* cell/tie, no-corner-cut, off-grid and invalid start
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
none PASS: three same-environment manifests, and command/mission bytes at a mocked live dispatch
08OB86_00294 completed
substitute PASS: replanned closed tour, skips and stable order in manifest and published command
Task046 preparation only; Gazebo not executed: /tmp/tmp_k8za4hi/cli
CLI/wrapper/API PASS: prepare-only, 028b conflict, forwarding and read-only preview
all waypoint feasibility tests passed
````

</details>
