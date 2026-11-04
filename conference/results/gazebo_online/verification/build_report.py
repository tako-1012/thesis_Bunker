"""Build the Japanese task021 report from real logs, without filling missing data."""

import hashlib
import json
from pathlib import Path
import subprocess
import pandas as pd

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = OUT.parents[1]
REPO = ROOT.parent
parts = []


def add(text):
    parts.append(text.strip() + '\n\n')


def block(path, language='text'):
    parts.append('```' + language + '\n' + Path(path).read_text().rstrip('\n') + '\n```\n\n')


def main():
    results = (VERIFY / 'test_summary.txt').read_text().splitlines()
    assert len(results) == len(list((ROOT / 'tests').glob('test_*.py')))
    assert all(line.endswith('exit=0') for line in results)
    final = (VERIFY / 'test_gz_online_batch_final_log.txt').read_text()
    assert 'all Gazebo online batch tests passed' in final and 'Traceback' not in final
    protocol = json.loads((VERIFY / 'protocol.json').read_text())
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    baseline = json.loads((VERIFY / 'baseline_sha256.json').read_text())
    changed = [name for name, h in baseline.items()
               if not (REPO / name).is_file() or hashlib.sha256((REPO / name).read_bytes()).hexdigest() != h]
    assert not changed, changed
    audit = dict(baseline_files=len(baseline), changed=changed)
    (VERIFY / 'baseline_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    manifest = json.loads((OUT / 'manifest.json').read_text())
    runs = pd.read_csv(OUT / 'runs.csv')
    assert len(runs) == 20 and runs.data_source.isna().all()
    assert not list(OUT.rglob('*.npz')) and not list(OUT.rglob('*.sdf'))
    preflight = pd.DataFrame([dict(patch=s['patch'], planning_status=s['planning_status'],
                                   fixed_plan_calls=len(s['fixed_plan_times']),
                                   order=str(s['order'])) for s in manifest['scenarios']])
    add('# 指示書021：漂着物のあるLAS砂浜10地形の固定経路・オンライン再計画')
    add('基準日：' + protocol['client_date'] + '（利用者の日付、日本時間）。\n'
        'ブランチ：`codex/021-gazebo-online`。基点：`origin/realtime-map` の `' + protocol['base'] + '`。'
        '020のマージを確認してから、その時点の最新から独立して作成した。他の作業ブランチを積まず、マージしていない。')
    add('## 結果と未実行の部分\n\n'
        '実装、10地形の事前計画、ROS2なしの新規テストと既存テストを完了した。**Gazeboでの20走行は未実行**。'
        '通常のDockerラッパーを起動したが、`thesis/jazzy-gz:1` がなくexit=125で終了した。'
        '既存の `ros:jazzy-ros-base` の確認でもGazeboが見つからず、SciPyのimportに失敗した。'
        'colcon buildや新しいGazeboプロセスは開始していない。特殊な名前空間・chrootでの実行は行っていない。'
        '依存関係の追加インストール、ホストのsudo、パラメータの調整も行っていない。')
    add('先頭10地形すべてで、既定の膨張ありTA*-Sによる事前地図上の巡回を計画できた。'
        'これはPythonで実際に計画した結果であり、走行の完走・転倒・漂着物回避を測った結果ではない。')
    parts.append('```text\n' + preflight.to_string(index=False) + '\n```\n\n')
    add('## 実装したもの\n\n'
        '- `ros2_jazzy/gz_checks/online_batch_checks.py`：10地形×固定/オンラインの20条件を同じworld・地点・初期位置で順に実行する。'
        '地図とworldは一時フォルダ、worldは4097画素上限、Gazebo seed=0。実行途中のエラーと計画不能もmanifestに残す。\n'
        '- `online_batch_runtime.py`：014の `scenarios` と同じ地点の抽出、元の事前地図での巡回順の決定、020の0.5m急斜面膨張を組み合わせる。'
        '既存の `AsyncOnlineMission` の探索・観測・遅延経路の引き継ぎを再利用し、出発前の順番を固定する。'
        '探索の失敗や経路を適用できなかった場合もワーカー側で計画時間を記録する。CSVの分割・読み込みも実装した。\n'
        '- `online_batch_planner.py`：014のROS2ノードのコールバックを継承し、未使用の既定runtimeを新しいruntimeに差し替える。'
        '既存ファイル、既存のエントリーポイント、既定動作は変更しない。\n'
        '- `run_online_batch_checks.sh`：通常のDockerでソースを読み取り専用マウントし、colconのビルドとインストールを一時領域で行う。'
        '`--planner` と出力先を転送する。ローカルのイメージを使い、既存manifestの上書きを拒否する。\n'
        '- `experiments/gz_online_batch_report.py`：元の記録から結果・到達した地点・接触・計画時間・ずれ・姿勢を集計し、20行の表、2条件の集計、'
        '対の差、漂着物を重ねた10枚の図を出す。020の厳密な転倒判定を再利用し、最大値と最初の転倒地点も出す。'
        '未測定は空欄・None・NaNに保つ。\n'
        '- `tests/test_gz_online_batch.py`：直接呼び出しとの10地形の一致、合成記録での分類と到達数、元データの不変性、'
        '全探索の記録、CSV分割と欠落の検出、未実行の分母、完走した対だけの集計、エネルギー列がないことを確認する。'
        '合成記録の値は試験専用の一時フォルダ・メモリ内だけで使い、実験の値として保存しない。')
    add('## 固定した条件と集計の定義\n\n'
        '`shizuoka_beach_las` のtest先頭10地形、200m、seed 0。真値は漂着物あり、事前地図は同じパッチの漂着物なし。'
        '地点は014と同じ `SeedSequence([0, 3000, 200, patch_index])` から12点を抽出した先頭5点である。'
        '巡回順は膨張前の事前地図で決め、両条件とすべての区間で共有する。地点はずらさない。'
        '計画と観測の走行可能マスクには020の急斜面膨張を適用し、地形コストを変えない。'
        '既定は `TA*-S+inflate`、後日の比較用に `TA*-S` を引数で選べる。半径や重みをtestの成績で選んでいない。\n\n'
        '完走はfollowerのcompletedに加えて、事前に決めた順の5点それぞれの0.3m以内を通り、出発点に戻ったことを要求する。'
        '途中の到達は、記録点間の線分も調べた順番付きの接頭部分として数える。'
        'followerがcompletedでも途中地点が欠ける場合は `incomplete_waypoints` とし、原状態は保持する。'
        '転倒はどこかで絶対rollが90度を超えた場合で、立ち往生・時間切れより優先する。'
        '時間切れは019と同じ、120秒と「事前経路長×6＋60秒」の大きい方のシミュレーション時間上限。'
        'ROS/Gazeboの異常終了や時計の停止は実行エラーとして分ける。\n\n'
        '接触は元のtruth lethalと、014と同じ `truth.rock & ~prior.rock` の一意なセル数。'
        '中心軌跡に基づく地図との照合であり、接触力センサーの実測ではない。'
        'ずれはfollowerがstateで確認した適用経路に対して計算し、まだ経路がない初回待機のサンプルは除く。'
        '計画時間は探索と平滑化だけで、膨張・地点選択・巡回順決定・ROSの受け渡しを含まない。'
        '固定経路では出発前の6区間、オンラインでは成功・失敗・適用を拒否されたものを含む全探索を記録する。'
        '`start_leg` 以外の探索を再計画として数えるため、区間の初期計画とROSへの置換通知数は区別する。\n\n'
        '対の差は、両条件とも完走した同じ地形だけを対象に `online - fixed` の中央値と対の数を出す。'
        '完走できなかったケースも走行別表と件数に残す。10地形に検定は行わず、エネルギーは集計しない。'
        '詳細なファイル仕様と通常のDocker手順は [README_ja.md](README_ja.md) に記載した。')
    add('## 実行したコマンド\n\n```bash\n'
        'cd conference\n'
        'python3 -m tests.test_planners\n'
        'python3 ros2_jazzy/gz_checks/online_batch_checks.py --prepare-only --output results/gazebo_online\n'
        'python3 -m tests.test_gz_online_batch\n'
        'python3 results/gazebo_online/verification/run_tests.py\n'
        'python3 -m tests.test_gz_online_batch\n'
        'python3 experiments/gz_online_batch_report.py\n'
        'bash ros2_jazzy/gz_checks/run_online_batch_checks.sh results/gazebo_online/physical_run\n'
        '```\n\n'
        '最後のDocker起動だけexit=125であり、テストの失敗ではない。Pythonには '
        '`OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-021-mpl XDG_CACHE_HOME=/tmp/thesis-021-cache` を指定した。'
        '新規Pythonの `py_compile` とシェルの `bash -n` も成功した。')
    add('Docker起動の実際の出力：')
    block(VERIFY / 'docker_launcher_log.txt')
    add('既存のros:jazzy-ros-base内での依存確認の出力：')
    block(VERIFY / 'docker_probe_log.txt')
    add('## テスト出力の全文\n\n変更前：')
    block(VERIFY / 'planners_before_log.txt')
    add('全モジュール：')
    block(VERIFY / 'all_tests_log.txt')
    block(VERIFY / 'test_summary.txt')
    add('新規の記録処理を最終確認した後の再実行：')
    block(VERIFY / 'test_gz_online_batch_final_log.txt')
    add('## 集計表（スクリプトの出力をそのまま）\n\n'
        '以下の20行はすべて実走未実行である。成功数・転倒数・到達数・接触数・所要時間・計画時間の空欄を0と解釈しない。')
    block(OUT / 'gazebo_online_log.txt')
    add('## できなかったこと・レビューで確認してほしいこと\n\n'
        'Gazeboを実行していないため、古い地図で漂着物に停止したか・転倒したか、オンラインでどの地形が完走できなかったかとその原因は判断できない。'
        '1回の計画が1m/sでの移動に間に合うかも未測定である。速度上限1m/sでは1秒に1m進むが、'
        '探索時間の中央値・95%・最大だけで安全性を判断せず、ROS受け渡し・経路追従・停止・接触を合わせて確認する必要がある。\n\n'
        'センサーは半径10m以内の走行可能ラベルが誤差なく得られる簡略化で、LiDAR・遮蔽・誤差を模擬しない。'
        '膨張済みラベルのため、観測円のすぐ外の急斜面の影響が円内のラベルに入ることもある。'
        '車体の追従ずれや急旋回、模型の横摩擦mu2=0.1による転倒は、膨張しても残りうる。'
        'ROS2でのアダプター統合と通常Dockerでのcolcon buildは未検証なので、準備した手順で実走とログを確認してほしい。')
    add('実走時は次の新しい保存先を使う。今回の事前確認用manifestを上書きしない。\n\n```bash\n'
        'docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference\n'
        'cd conference\n'
        'bash ros2_jazzy/gz_checks/run_online_batch_checks.sh results/gazebo_online/physical_run\n'
        'python3 experiments/gz_online_batch_report.py results/gazebo_online/physical_run\n```')
    add('## 図\n\n'
        '各地形の図は真値の地形と漂着物マスク、実際に計画した事前経路だけを表示し、実走未実行と明記した。'
        '実走後は同じスクリプトが2条件の記録軌跡を重ねる。`08OB88_-0167.png` は目視確認した。')
    for sc in manifest['scenarios']:
        add('[' + sc['patch'] + '](' + sc['patch'] + '.png)')
    add('## 保存の監査と環境\n\n'
        '既存ファイルは1つも変更していない。既存テストの弱体化・枚数確認の修正も行っていない。'
        '地図・worldはこの結果フォルダに保存しておらず、rawの実走記録も作っていない。')
    block(VERIFY / 'baseline_audit.json', 'json')
    block(VERIFY / 'protocol.json', 'json')
    add('## 変更ファイル一覧')
    names = subprocess.check_output(['git', 'diff', '--name-only', protocol['base'], '--', 'conference'], cwd=REPO, text=True).splitlines()
    names += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', 'conference'], cwd=REPO, text=True).splitlines()
    names += ['conference/results/gazebo_online/REPORT_ja.md', 'conference/results/gazebo_online/changed_files.txt']
    names = sorted(set(names))
    (OUT / 'changed_files.txt').write_text('\n'.join(names) + '\n')
    add('\n'.join('- `' + name + '`' for name in names))
    (OUT / 'REPORT_ja.md').write_text(''.join(parts).rstrip() + '\n')
    print(OUT / 'REPORT_ja.md')


if __name__ == '__main__':
    main()
