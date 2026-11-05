"""Assemble Japanese task023 report and PR body from executed outputs."""

import hashlib
import json
from pathlib import Path
import subprocess
import pandas as pd

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = OUT.parents[1]
REPO = ROOT.parent


def block(path, language='text'):
    return '```'+language+'\n'+Path(path).read_text().rstrip('\n')+'\n```\n\n'


def main():
    protocol = json.loads((VERIFY/'protocol.json').read_text())
    tests = (VERIFY/'test_summary.txt').read_text().splitlines()
    assert len(tests) == len(list((ROOT/'tests').glob('test_*.py')))
    assert all(line.endswith('exit=0') for line in tests)
    final = (VERIFY/'test_fine_final_log.txt').read_text()
    assert 'all fine-grid pointcloud tests passed' in final and 'Traceback' not in final
    for name, h in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == h, name
    original = json.loads((VERIFY/'baseline_sha256.json').read_text())
    modified = [name for name, h in original.items() if hashlib.sha256((REPO/name).read_bytes()).hexdigest() != h]
    assert modified == ['conference/ros2_jazzy/gz_checks/lidar_checks.py',
                        'conference/ros2_jazzy/gz_checks/lidar_planner.py',
                        'conference/ros2_jazzy/gz_checks/run_lidar_checks.sh'], modified
    runs = pd.read_csv(OUT/'runs.csv', float_precision='round_trip')
    assert len(runs) == 40 and runs[runs['mode'] == 'fine'].data_source.isna().all()
    implementation = '''- `tapp/pointcloud_map_fine.py`：`PointCloudMapFine.update/snapshot/save` と `coarse_overlap`。障害物だけを0.1mで検出し、円盤膨張をその格子で1回だけ行う。地面・特徴量は既存の0.5mの式と保持履歴を維持する。
- `ros2_jazzy/gz_checks/lidar_map.py`：`make_pointcloud_map`、`fine_protocol`、`matched_task022_maps`。既定は022の元のクラスそのもの。新方式は022の実走条件と実走時の標高を再利用する。
- `lidar_planner.py`：既定coarseのROSパラメータを追加し、選択したクラスへ渡す。探索・コスト式・再計画・センサー処理は変えない。
- `lidar_checks.py` と `run_lidar_checks.sh`：`--map fine` を追加。省略/明示coarseの既定値とmanifestは維持する。fineでは同一地点・順番・初期配置、メッシュ、0.3倍速、期限1.0秒を使う。
- `experiments/lidar_fine_report.py`：`map_audit`、`box_footprints`、`evaluation_maps`、`summary_table`、`summarize`。保存済み3条件の30行と新方式10行を並べ、観測済みマスクのFP/FN、箱への隣接、更新時間、接触を集計する。
- `tests/test_pointcloud_map_fine.py`：平地、0.02m測距雑音付きの箱、中心の保持、膨張の幾何・再観測・追加シード、保存、旧方式のバイト一致、manifestとDocker引数、4条件の欠測と旧値の保持を確認する。
- `tasks/023_lidar_fine_grid.md`：今回の利用者の指示内容を同じブランチに保存した。'''
    method = '''0.1m・高さ0.3m・3点・半径0.5mは指示書で事前指定された値として固定し、変更・選択・調整していない。
新方式ではこれらと異なる設定を拒否する。点群の登録・範囲除外・古い地面の双線形補間は022と同じで、真値ラベルを観測に流用しない。

0.5mセルを境界に合わせて5×5の0.1mセルに分ける。地面の高さは従来どおり粗セル内の直近64点の中央値。
判定もこの同じ履歴の中で細セルIDを区別する。履歴の長さや保持期間を新たに延ばしていない。
したがって、地面・傾斜・凸凹・コスト・観測済みマスクの計算は同じで、細分化するのは障害物の位置と証拠だけである。

検出した細セルを半径5細セルの円盤で膨張し、その後5×5内に膨張セルが1つでもある粗セルを通行不可にする。
粗セルへまとめたマスクは再膨張させない。追加の観測では新しい生の障害物の膨張との和を取り、膨張済みマスクを入力にしない。
既存の岩の膨張は1回のまま、急斜面は変更していない `footprint.inflate_steep` を使う。
セルの「重なり」は領域の重なりであり、距離の検証も細セル領域と粗セル領域との最小距離で行う。セル中心の距離ではない。

新しい方式のNPZは、従来のelev/seen/obstacle/cost/lethalに加え、細格子の検出・膨張マスクをpackbitsで保存する。
地図更新の公開APIは元と同じ。TA*・TA*-Sのコスト式や探索ロジックを変更していない。'''
    conditions = '''021と022の10地形・world・地点・順番・スタートを共用する。メッシュの見た目とheightmapの衝突、0.3倍速と途切れ期限1.0秒をmanifestに明記した。
fineの場合は、環境変数でこれらと異なる条件を指定すると停止する。LiDARの仕様、取り付け位置、測距雑音も022の実走と同じ設定だけを受け付ける。

ライブラリ版の差で漂着物の標高のビットが変わる問題を避けるため、新しいworldには022の実走時の評価用標高配列を使う。
生の障害物・水・欠損マスクと、通行不能マスクの一致を検査し、開始点・目的地をずらさない。
旧worldファイルそのものは一時領域にしか残っていないためSDF全体のバイト比較は未実施だが、同じ入力標高・マスクと既存のエクスポーター/メッシュ生成処理を使う。
world/入力地図とbuild/installは一時領域に作り、既存の結果は更新しない。'''
    definitions = '''`map_*` は最終lethalを元のtruth lethalと比較した、観測済みの一意な粗セルでのFP/FNである。
CSVの `clearance_*` には、真値にも同じ急斜面の膨張を入れた参照とのFP/FNを併記する。意図した安全余裕まで誤りと解釈しないためである。

`detector_*` は膨張前の検出を生の障害物と比較した指標で、水・欠損を除く。既に事前地図にある障害物も含むため、点群検出器の見落としと最終lethalの見落としは同じではない。
箱の領域はexport_gazeboと同じ連結成分の外接長方形。その外側で4方向に1粗セルだけ隣接する領域を `*_box_adjacent_cells` とする。
022の約7割という原因分析は主に膨張前の検出についてのものなので、最終lethalのFPと区別して表示する。

021の2条件には最終の点群地図スナップショットがないため、地図誤りの欄は未記録とし、0を入れない。
観測した範囲は走行ごとに異なる。件数だけで精度の優劣を断定しない。
漂着物への接触は記録された中心軌跡によるため、車体前端の接触を過少評価する。
地図更新時間は走行ごとの中央値・95%・最大と、その走行単位の集計であり、計画時間とは別である。'''
    limitations = '''**新しいfine方式のGazebo実走は未実行**。通常のDockerラッパーは標準イメージ `thesis/jazzy-gz:1` がなくexit=125で終了した。
新方式の完走・経路なし・誤検出・見落とし・更新時間・接触の実測値はない。表の空欄/NaNを0として扱わない。
合成箱の外側セルが減った結果を、10地形の完走率改善や実機の安全性へ置き換えていない。

細セル内に3点を要求するため、疎な物体や側面の検出を落とす可能性がある。逆に、同じ場所の雑音が繰り返し蓄積すれば外側の細セルが検出される場合もある。
中央値の高さによる急斜面や誤った地面高さ、古い地面基準の限界、観測されない場所のsoft prior、地図境界の転倒は今回変更していない。
細格子化のCPU・メモリ負荷と、点群の取りこぼしも実走では未評価である。

Claudeには、READMEのコマンドで新方式だけを走らせ、022と同じworld/地点/設定を確認した上で、通路の閉塞、見落とし、箱の隣のFP、更新時間、取りこぼしを確認してほしい。
10地形の検定・エネルギー集計は行わない。境界の転倒を除外したり、地点・パラメータを変えて結果を良くしたりしていない。'''
    commands = '''cd conference
python3 -m tests.test_planners
python3 -m tests.test_pointcloud_map_fine
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 10 --map fine --output results/lidar_fine
python3 experiments/lidar_fine_report.py
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/lidar_fine/physical_10 --patch-count 10 --map fine
python3 results/lidar_fine/verification/run_tests.py
python3 -m tests.test_pointcloud_map_fine
python3 results/lidar_fine/verification/plot_fixture.py'''
    command_block = '```bash\n'+commands+'\n```\n\n'
    tests_full = block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    focused = block(VERIFY/'test_fine_final_log.txt')
    tables_full = block(OUT/'lidar_fine_log.txt')
    report = '# 指示書023：細格子の障害物検出と1回だけの膨張\n\n'
    report += '基準日：'+protocol['client_date']+'（利用者環境の日付、UTC）。ブランチ：`codex/023-lidar-fine-grid`。基点：`'+protocol['base']+'`。最新realtime-mapから作成し、他の作業ブランチを積まず、マージしていない。\n\n'
    report += '## 実装したもの\n\n'+implementation+'\n\n## 方法と事前固定した値\n\n'+method+'\n\n'
    report += '## 022と同じ実走条件\n\n'+conditions+'\n\n'+block(OUT/'manifest.json','json')
    report += '## 実行したコマンド\n\n'+command_block
    report += 'Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-023-mpl XDG_CACHE_HOME=/tmp/thesis-023-cache` を指定した。py_compileとbash -nも成功した。\n\n'
    report += 'Docker起動の実際の出力（exit=125）：\n\n'+block(VERIFY/'docker_launcher_log.txt')
    report += '## テスト出力の全文\n\n変更前：\n\n'+block(VERIFY/'planners_before_log.txt')+tests_full
    report += '最終の新方式・選択・比較の確認：\n\n'+focused
    report += 'バイト比較では、旧方式の計測時間は時計を固定する。manifestは機械固有のPython/NumPy欄を同じ実行環境の値へ合わせ、それ以外の全バイトを元のスナップショットと比較する。実走の時刻・浮動小数の軌跡を決定的と主張するものではない。\n\n'
    report += '## 集計表（スクリプト出力をそのまま）\n\n'
    report += '保存済みの021の2条件と022のLiDARはその値を保持し、旧LiDARの地図だけを追加で監査した。fineは未実行。\n\n'+tables_full
    report += '## 指標の意味\n\n'+definitions+'\n\n'
    report += '## 合成箱の確認図\n\n[箱の境界と通行不可セル](box_fixture.png)。固定シード100の合成入力で、実機やGazeboの走査/遮蔽ではない。箱の外側のセル数は正常な安全余白も含み、FP件数と同義ではない。図は目視確認した。\n\n'+block(VERIFY/'plot_fixture_log.txt')
    report += '## 既存ファイルの保持と実行環境\n\n'
    report += '既存の変更は、既定動作を維持する選択引数を加えた3つのROS用ファイルに限定する。pointcloud_map.py、traversability.py、footprint.py、online_mission.py、経路計画とコスト式、および全ての既存結果・地図・world・データは変更していない。既存テストの削除・弱体化は行っていない。\n\n'
    report += block(VERIFY/'preservation_audit.json','json')+block(VERIFY/'protocol.json','json')
    report += '## できなかったこと・確認してほしいこと\n\n'+limitations+'\n\n'
    report += '通常Dockerの実行コマンド、保存形式、粗セル領域の定義、指標の詳細は [README_ja.md](README_ja.md) に記載した。\n\n'
    if (OUT/'SUBMISSION_ja.md').exists():
        report += '## 提出状態\n\n'+(OUT/'SUBMISSION_ja.md').read_text()+'\n\n'
    names = subprocess.check_output(['git','diff','--name-only',protocol['base'],'--','conference'],cwd=REPO,text=True).splitlines()
    names += subprocess.check_output(['git','ls-files','--others','--exclude-standard','conference'],cwd=REPO,text=True).splitlines()
    names += ['conference/results/lidar_fine/REPORT_ja.md','conference/results/lidar_fine/PR_DESCRIPTION_ja.md','conference/results/lidar_fine/changed_files.txt']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    report += '## 変更ファイル一覧\n\n'+'\n'.join('- `'+n+'`' for n in names)+'\n'
    (OUT/'REPORT_ja.md').write_text(report)
    pr = '022の障害物の粗格子丸めによる過大な通行不可領域を調べるため、障害物だけ0.1mで判定し、そこで半径0.5mの膨張を1回だけ行う方式を追加する。地面・コスト・探索・既存方式は維持する。\n\n'
    pr += '**新方式のGazebo実走は未実行**（通常Dockerイメージ不足、起動exit=125）。保存済みの3条件と未実行の新方式を並べた。\n\n'
    pr += '## 実装\n\n'+implementation+'\n\n## 方法と固定値\n\n'+method+'\n\n## 実走条件\n\n'+conditions+'\n\n'
    pr += '## コマンドとテスト全文\n\n'+command_block+block(VERIFY/'planners_before_log.txt')+tests_full+focused
    pr += '## 集計表（そのまま）\n\n'+tables_full+'## 指標\n\n'+definitions+'\n\n'
    pr += '## 未実行と限界\n\n'+limitations+'\n\n'
    pr += '変更一覧・入力/保持の監査・合成図は [REPORT_ja.md](https://github.com/tako-1012/thesis_Bunker/blob/codex/023-lidar-fine-grid/conference/results/lidar_fine/REPORT_ja.md)。\n'
    (OUT/'PR_DESCRIPTION_ja.md').write_text(pr)
    print(OUT/'REPORT_ja.md')
    print('PR body characters:',len(pr))


if __name__ == '__main__':
    main()
