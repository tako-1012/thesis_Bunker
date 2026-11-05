"""Assemble task022's Japanese report/PR body from unedited executed outputs."""

import hashlib
import json
from pathlib import Path
import subprocess
import pandas as pd

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = OUT.parents[1]
REPO = ROOT.parent


def code(text, language='text'):
    return '```'+language+'\n'+text.rstrip('\n')+'\n```\n\n'


def file_block(path, language='text'):
    return code(Path(path).read_text(), language)


def main():
    protocol = json.loads((VERIFY/'protocol.json').read_text())
    tests = (VERIFY/'test_summary.txt').read_text().splitlines()
    assert len(tests) == len(list((ROOT/'tests').glob('test_*.py')))
    assert all(line.endswith('exit=0') for line in tests)
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    baseline = json.loads((VERIFY/'baseline_sha256.json').read_text())
    changed = [name for name, h in baseline.items() if not (REPO/name).is_file() or
               hashlib.sha256((REPO/name).read_bytes()).hexdigest() != h]
    assert changed == ['conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/model.py'], changed
    data = pd.read_csv(OUT/'runs.csv', float_precision='round_trip')
    assert len(data) == 30 and data[data['mode'] == 'lidar'].data_source.isna().all()
    summary = pd.read_csv(OUT/'summary.csv', float_precision='round_trip')
    validation = pd.read_csv(OUT/'validation/height_audit.csv', float_precision='round_trip')
    assert len(validation) == 12 and validation.source.eq('validation_dense_artificial_returns').all()
    implementation = '''- `tapp/pointcloud_map.py`：`decode_xyz`、`transform_points`、`PoseBuffer.add/at`、`PointCloudMap.update/snapshot/save`。PointCloud2互換バッファのデコード、時刻付き姿勢のSO(3)補間、6自由度の座標変換、0.5mセルの中央値融合、観測済みマスク、事前高さを基準にした障害物検出、既存式による傾斜・凸凹・コストと0.5m膨張。
- `thesis_bunker_gz/model.py`：LiDARなしを既定に保つキーワード引数を追加。`lidar.py` に設定とgpu_lidar生成を置き、通常と質量指定の既存SDFのバイト一致を検証した。
- `lidar_bridge.yaml`：PointCloudPackedをROS2のPointCloud2へ渡す。既存bridgeは変更していない。
- `lidar_runtime.py`：`LidarOnlineMission._plan_work/_join`。021の非同期計画・経路引き継ぎを再利用し、観測の両箇所を点群由来に置換。truthはNoneで、virtual_senseを呼ばないことをテストした。
- `lidar_planner.py`：真値地図をロードせず、古い地図・点群・点群時刻のground_truth姿勢だけを使うROS2ノード。別ワーカー、最新1走査の待ち行列、時刻不一致の拒否、センサー停止要求、全探索と地図更新の記録を追加した。
- `lidar_checks.py` と `run_lidar_checks.sh`：021の保存済みの10地形・地点・順番を共有し、最初の3か所から10か所へ広げる。world/入力地図/colconは一時領域。実走時の解析用参照配列を保存する。
- `experiments/gz_lidar_report.py`：`map_quality/tables/summarize`。021の20行の保存値とLiDARの10行を並べ、同じ走行項目、最終観測セルの高さ誤差、地図更新時間を集計する。欠測はNone/NaN/空欄のまま、検定・エネルギー集計は行わない。
- `tests/test_pointcloud_map.py`：平地、箱、未知セル、座標・時刻・データ形式、既存模型、真値を使わないワーカーと経路引き継ぎ、誤差集計、保存済み対照の不変性を確認する。
- `experiments/pointcloud_validation.py`：事前固定した設定でvalidation12地形の人工入力を監査する。パラメータを選択・調整するスクリプトではない。'''
    assumptions = '''利用者から示されたVLP-16の公称値に合わせ、16本、垂直−15°〜+15°を2°刻み、水平360°、10Hzとした。
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
017は地表セルへ直接視線を調べるモデルであり、今回の疎な上下方向の走査線とは観測条件が違う。'''
    commands = '''cd conference
python3 -m tests.test_planners
python3 -m tests.test_pointcloud_map
python3 experiments/pointcloud_validation.py
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 3 --output results/gazebo_lidar
python3 experiments/gz_lidar_report.py
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/gazebo_lidar/physical_3 --patch-count 3
python3 results/gazebo_lidar/verification/run_tests.py'''
    limitations = '''優先順位(1)の点群処理とROS2なしのテストは完了した。(2)のGazebo3か所と(3)の10か所は未実行である。
通常Dockerの起動は標準イメージ `thesis/jazzy-gz:1` がなくexit=125で終了し、Gazebo・colconは開始していない。
ホストにパッケージを追加せず、特殊な名前空間やchrootによる実行も行っていない。
LiDARの場合の完走・接触・転倒・計画時間・実測の高さ誤差・実測の地図更新時間は測れていない。
以下の人工入力の数値をLiDARの実測欄に埋めていない。

Claudeには、通常Dockerでまず3か所を走らせ、PointCloud2のtopic/frame/timestamp、模型の局所座標、ground_truthとの時間整合、
ogre2の画面なし描画、実際の戻り点の密度、待ち行列の取りこぼし、0.5シミュレーション秒のセンサー停止期限を確認してほしい。
実走できた場合にのみ、新しい保存先で10か所へ広げる。処理・探索の壁時計時間と、Gazeboの進行速度を分けて読む必要がある。
模型のmu2=0.1や急旋回による転倒は残りうる。中心軌跡の接触数は車体前端の接触を過少評価する。
021で両条件が転倒した `08OB89_00152` は地図境界の問題として除外せず注記している。
完全な点群ストリームは保存せず、最初の点群と各処理入力のSHA-256、最終地図、更新ログを残すため、全走査の再生はできない。'''
    main_table = file_block(OUT/'gazebo_lidar_log.txt')
    validation_table = file_block(OUT/'validation/validation_log.txt')
    test_table = file_block(VERIFY/'all_tests_log.txt')
    header = '# 指示書022：VLP-16相当の点群からの地図更新と再計画\n\n'
    header += '基準日：'+protocol['client_date']+'（利用者の日付、日本時間）。\n'
    header += 'ブランチ：`codex/022-gazebo-lidar`。基点：`'+protocol['base']+'`。021のマージ後の最新 `realtime-map` から独立して作成し、マージしていない。\n\n'
    header += '**LiDARの実走は未実行**。点群処理・連携スクリプト・集計・テストまで実装した。\n\n'
    report = header+'## 実装したもの\n\n'+implementation+'\n\n'
    report += '## 仕様・仮定\n\n'+assumptions+'\n\n'+file_block(VERIFY/'protocol.json', 'json')
    report += '## 実行したコマンド\n\n'+code(commands, 'bash')
    report += 'Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-022-mpl XDG_CACHE_HOME=/tmp/thesis-022-cache` を指定した。新規Pythonのpy_compileとbash -nも成功した。\n\n'
    report += 'Docker起動の実際の出力（exit=125）：\n\n'+file_block(VERIFY/'docker_launcher_log.txt')
    report += '## テスト出力の全文\n\n変更前：\n\n'+file_block(VERIFY/'planners_before_log.txt')+test_table+file_block(VERIFY/'test_summary.txt')
    report += '## 3条件の集計表（出力をそのまま）\n\n'
    report += 'fixedとonlineは021の保存済み実測値、LiDARは今回の未実行欄である。保存済み20行の指標が数値として完全一致することをテストした。未測定を0と扱わない。対の差は両方完走した地形だけで計算する。\n\n'+main_table
    report += '## 点群からの高さ誤差と地図更新時間\n\n'
    report += 'LiDARの実測値は未取得。実走時は最後の地図の観測済みセルを1回ずつ数え、中央値の表面高さと実際の真値DEMの絶対差（中央値・95%・最大）を評価する。上面が真値DEMに入っていない漂着物では、その高さ差も含む。\n\n'
    report += '更新時間はPointCloud2のデコード・座標変換・融合・特徴量計算を含む成功処理の分布とし、失敗・queue dropを併記する。保存・キュー待ち・ROSの受け渡しは含まない。探索時間とは別に読む。\n\n'
    report += '以下は**validation12地形の密な人工入力による処理監査**で、Gazebo/VLP-16の実測ではない。全て事前固定した設定で実行し、閾値の選択・調整はしていない。セル中心から点を作るため、実際の走査密度・遮蔽・セル内の位置偏り・動力学を評価していない。\n\n'+validation_table
    report += 'この人工入力では更新時間が10Hzの周期を超える例があった。実際の疎な点群での速度や1m/s走行で間に合うかは未測定であり、性能保証とは扱わない。\n\n'
    report += '## 入力のバイト列と過去の結果の保持\n\n'
    report += '021の実走はNumPy1.26.4、今回の環境は2.3.5。漂着物を加えた標高のハッシュが一致しない一方、LASのバイト列・事前地図の高さ・岩とlethalマスクは一致した。旧標高配列が一時領域にしかなかったため差の大きさは確定していない。\n\n'
    report += '古い数値や期待値を書き換えず、入力LASと主要な計画・地形コードのSHA、マスクを検査して違いを記録した。新しい実走は評価用の高さ・マスク配列を保存し、異なる環境での事後評価も実際の入力配列を使う。評価用配列が不明な場合、高さ誤差は未取得のままにする。\n\n'
    report += file_block(OUT/'baseline_input_audit.json', 'json')+file_block(VERIFY/'preservation_audit.json', 'json')
    report += '既存の模型以外のファイルは内容のSHAで一致を確認した。模型は指示書で許可された引数追加のみで、LiDARなしの通常・質量指定SDFのバイト一致をテストした。既存テストの削除・弱体化はない。\n\n'
    report += '## できなかったこと・確認してほしいこと\n\n'+limitations+'\n\n'
    report += '通常Dockerの構築、3か所、10か所の順の実行コマンドとファイル仕様は [README_ja.md](README_ja.md) に記載した。\n\n'
    report += '## 図\n\n各図のfixed/onlineは021の保存済み軌跡で、LiDARの実線は描かず未実行と明記する。\n\n'
    for meta in json.loads((OUT/'manifest.json').read_text())['scenarios']:
        report += '['+meta['patch']+']('+meta['patch']+'.png)\n\n'
    if (OUT/'SUBMISSION_ja.md').exists():
        report += '## 提出状態\n\n'+(OUT/'SUBMISSION_ja.md').read_text()+'\n\n'
    names = subprocess.check_output(['git','diff','--name-only',protocol['base'],'--','conference'],cwd=REPO,text=True).splitlines()
    names += subprocess.check_output(['git','ls-files','--others','--exclude-standard','conference'],cwd=REPO,text=True).splitlines()
    names += ['conference/results/gazebo_lidar/REPORT_ja.md','conference/results/gazebo_lidar/changed_files.txt','conference/results/gazebo_lidar/PR_DESCRIPTION_ja.md']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    report += '## 変更ファイル一覧\n\n'+'\n'.join('- `'+n+'`' for n in names)+'\n'
    (OUT/'REPORT_ja.md').write_text(report)
    pr = '点群から0.5m地図を作って既存の非同期再計画に渡す処理と、VLP-16相当の模型・3→10地形の実行手順を追加した。\n\n'
    pr += '**実走は未実行**（Dockerイメージ不足、起動exit=125）。022は試験的な指示書のため、点群処理とスクリプト・ROS2不要のテストまで完了した。\n\n'
    pr += '## 実装\n\n'+implementation+'\n\n## 仕様と仮定\n\n'+assumptions+'\n\n'
    pr += '## コマンドとテスト全文\n\n'+code(commands, 'bash')+file_block(VERIFY/'planners_before_log.txt')+test_table
    pr += '## 集計表（そのまま）\n\n'+main_table
    pr += '## 高さ・地図更新時間\n\nLiDARの実測は未取得。以下はvalidation12地形のセル中心から作った密な人工入力の監査であり、走査線・遮蔽・動力学を省いている。設定の選択・調整はしていない。\n\n'+validation_table
    pr += '## 未実行と限界\n\n'+limitations+'\n\n'
    pr += '021との標高SHAはNumPy環境で異なったが、LAS・事前高さ・マスクは一致した。元の値を更新せず、新しい実走の評価用配列を保存して正確な入力で高さを評価する。\n\n'
    pr += '変更一覧・全環境・入力監査は [REPORT_ja.md](https://github.com/tako-1012/thesis_Bunker/blob/codex/022-gazebo-lidar/conference/results/gazebo_lidar/REPORT_ja.md)。\n'
    (OUT/'PR_DESCRIPTION_ja.md').write_text(pr)
    print(OUT/'REPORT_ja.md')
    print('PR description characters:', len(pr))


if __name__ == '__main__':
    main()
