"""Verify preservation and write the Japanese task029 handoff from real logs."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from capture_legacy import untouched_digest

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = VERIFY.parents[2]
REPO = ROOT.parent


def block(path, language='text'):
    return '```'+language+'\n'+path.read_text().rstrip('\n')+'\n```\n\n'


def main(commit):
    commit = subprocess.check_output(['git', 'rev-parse', commit+'^{commit}'], cwd=REPO, text=True).strip()
    protocol = json.loads((VERIFY/'protocol.json').read_text())
    for name, checksum in protocol['source_sha256'].items():
        source = (REPO/name).read_bytes()
        assert hashlib.sha256(source).hexdigest() == checksum, name
        assert subprocess.check_output(['git', 'show', commit+':'+name], cwd=REPO) == source, name
    count, digest = untouched_digest()
    assert count == protocol['baseline_conference_files'] and digest == protocol['untouched_sha256']
    original_changes = [name for name, checksum in protocol['original_source_sha256'].items()
                        if hashlib.sha256((REPO/name).read_bytes()).hexdigest() != checksum]
    assert set(original_changes) == set(protocol['editable_existing_files'])
    tests = sorted((ROOT/'tests').glob('test_*.py'))
    summary = (VERIFY/'test_summary.txt').read_text().splitlines()
    assert summary == [source.stem+' exit=0' for source in tests], summary
    logs = [(VERIFY/(source.stem+'_log.txt')).read_text() for source in tests]
    assert (VERIFY/'all_tests_log.txt').read_text() == '\n'.join(logs)
    rows = list(csv.DictReader((OUT/'box_slopes.csv').open()))
    assert len(rows) == 8 and all(row['box_lethal'] == 'True' for row in rows)
    old = [float(row['slope_deg']) for row in rows if row['ground_estimate'] == 'all_returns']
    new = [float(row['slope_deg']) for row in rows if row['ground_estimate'] == 'non_obstacle']
    assert len(old) == len(new) == 4
    assert len(set(old)) == len(set(new)) == 1
    (OUT/'implementation_commit.txt').write_text(commit+'\n')
    audit = dict(base=protocol['base'], original_conference_files=count,
                 changed_existing_files=original_changes, unchanged_original_files=count-len(original_changes),
                 untouched_sha256=digest, all_existing_tests_unchanged=True,
                 original_results_data_maps_worlds_and_protected_planning_code_unchanged=True)
    (VERIFY/'preservation_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    report = '# 指示書029：障害物の点を除いた地面の高さの推定\n\n'
    report += '実装・検証ログのコミットID：`'+commit+'`。この報告書は後続の文書コミットで追加する。\n\n'
    report += 'ブランチ：`codex/029-ground-estimate`。基点：`'+protocol['base']+'`（作業開始時の最新realtime-map）。日付：'+protocol['client_date']+'（日本時間）。マージせずpushまで。\n\n'
    report += 'Pythonの全'+str(len(tests))+'テストモジュールが成功した。既定の出力と既存の結果は維持し、Gazebo・実際のDocker・研究PCでの走行は実行していない。\n\n'
    report += '''## 1. 実装と検証

- `tapp/pointcloud_map_fine.py`：`ground_estimate='all_returns'|'non_obstacle'` を追加。直近64点はすべて残し、地面の中央値を計算するときだけ、既存の双線形補間の古い地図より0.3m以上高い点を除く。残る点が0ならそのセルの古い地図の高さを使う。以前の推定値は使わない。
- `tapp/pointcloud_map_multi.py`：同じ引数を共有のFine地図へ渡す。LiDARとカメラで履歴を分けたり、障害物の証拠や寄与元の履歴から高い点を消したりしない。
- `ros2_jazzy/gz_checks/lidar_map.py`：factoryで方式を選ぶ。新方式はfine専用とし、coarseとの組合せ・未知の方式はエラーにする。既定のcoarseは従来のクラスそのもの。
- `ros2_jazzy/gz_checks/lidar_checks.py`：`--ground-estimate` を追加。新方式のmanifestへ方式と中央値の定義を記録し、ROS引数へ渡す。新方式の生記録を従来の4方式の集計へ同じ名前で混ぜない。`--prepare-only` でも新方式の記録を準備できる。
- `ros2_jazzy/gz_checks/lidar_planner.py`：同名のROSパラメータと、直接起動時の `--ground-estimate` を追加。指定なしでは従来と同じargsオブジェクトをROSへ渡す。ROSパラメータはノードの既定値より優先する。
- `tests/test_ground_estimate.py`：変更前に採取した既定のバイト列、箱と隣接4セル、全点除外・履歴の入れ替わり、0.3m未満の地形変化、双線形参照、閾値の境界、LiDAR＋カメラの共有証拠、実際のノードのコンストラクタとCLIの受け渡しを検証する。ROSのtransportはモックで、ROS/Gazeboを起動しない。
- `results/ground_estimate/README_ja.md`：引数・記録・既存閾値による限界を記した。

既定は `all_returns` のまま。0.1m・0.3m・3点・0.5m、傾斜上限、コスト・傾斜・凸凹の式、膨張と観測済みの扱いは変えていない。
既定manifestのバイト列を保つため、方式の項目を追加するのは新方式を選んだときだけである。項目がない従来のmanifestは、既存の高さの定義どおり `all_returns` と解釈する。

変更前に採取したfine・実機LiDAR・実機LiDAR＋深度カメラ2台の更新JSON・snapshot・64点履歴・NPZ・センサーsidecarのSHA-256を、暗黙の既定と明示的なall_returnsの両方で照合した。
更新時間には制御した時計を使う。実機性能の測定値ではない。同じ環境の4通りの既定manifestも全文のバイト列のSHA-256で照合した。
別環境でテストする場合はPython/NumPyの機械情報だけを除いた比較も行う。元の環境と全文のハッシュは `verification/legacy_bytes.json` に残してある。
既存テストの削除・skip・xfail・期待値変更はない。

028bの報告書は土台ブランチにはまだ存在しないため、`codex/028b-start-component` のコミット `ad0f0a7` にある報告を参照した。028bをマージしたり、始点解除や失敗分類をこの作業で変更したりしていない。

### 実行したコマンド

```bash
git fetch origin realtime-map:refs/remotes/origin/realtime-map
git worktree add -b codex/029-ground-estimate /workspace/thesis-029 origin/realtime-map
cd conference
python3 -m tests.test_planners
python3 results/ground_estimate/verification/capture_legacy.py  # 変更前に一度実行
python3 -m tests.test_ground_estimate
python3 results/ground_estimate/verification/run_tests.py
python3 results/ground_estimate/verification/build_report.py --implementation-commit <上記ID>
```

全テストのランナーは `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-029-mpl XDG_CACHE_HOME=/tmp/thesis-029-cache PYTHONUNBUFFERED=1` を指定した。
最初の確認時には読み取り専用のhomeに対するMatplotlibのキャッシュ警告があったが、その実行も成功した。全テストでは上記の書き込み可能なキャッシュを指定している。

### 変更前のプランナーテストと採取ログ（全文）

'''
    report += block(VERIFY/'planners_before_log.txt')+block(VERIFY/'capture_legacy_log.txt')
    report += '### 初回の対象テスト出力（全文）\n\n'+block(VERIFY/'ground_initial_log.txt')
    report += 'この初回の後に、箱の高さと生成ROSコマンドの検証を加えた。最終の全テストにはその追加も含む。\n\n'
    report += '### 最終の全テスト出力（全文）\n\n'+block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    report += '## 2. 箱の隣接セルの傾斜（テスト2の表示をそのまま）\n\n'
    report += block(OUT/'box_slopes_log.txt')
    report += '合成点群のPythonテスト値であり、Gazeboの測定値ではない。従来方式の隣接4セルはすべて `'+repr(old[0])+'°`、新方式はすべて `'+repr(new[0])+'°` だった。箱自体は両方式で障害物のまま通行不可であり、障害物の膨張範囲も一致した。\n\n'
    report += '''隣接セルが地面として平らになっても、ロボット半径に基づく正しい障害物の膨張によって通行不可になる範囲は残る。このテストは障害物の見落としや膨張の削除で傾斜を下げたものではない。

## 3. 研究PCで後日評価する案（未実行）

今回の作業ではGazeboを走らせていない。以下は将来の実行案で、得られた結果ではない。
まず既存の先頭3か所を使い、all_returnsとnon_obstacleを各3回、合計18走行で比較する案とする。既存のworld・地点・スタート・障害物・センサー・地形mesh・シミュレーション速度0.3倍・点群の途切れの基準1.0秒を両方式でそろえる。
始点処理は両方noneとし、変更点を地面の推定方式だけにする。保存先を実行ごとに新しくして元の結果を上書きしない。
LiDARのノイズは実走ごとに変わるため、単発の成功で結論を出さない。3か所の確認後、10か所への拡張を別途判断する。
実機センサー＋カメラで比べる場合は別の比較として、両方式とも同じ `--sensors lidar_real+depth2` にする。

```bash
cd conference
# 研究PCで後日実行する例。この作業では実行していない。
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/ground_estimate/physical_3_all_returns_r1 \\
  --patch-count 3 --map fine --ground-estimate all_returns --endpoint-policy none --diagnostics
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/ground_estimate/physical_3_non_obstacle_r1 \\
  --patch-count 3 --map fine --ground-estimate non_obstacle --endpoint-policy none --diagnostics
```

完走・経路なし・立ち往生・転倒・漂着物との接触を分け、失敗瞬間のdiagとその前の地図で、始点と周囲の高さ・傾斜・生の急斜面・膨張を比較する。
真値は評価専用とし、高さの誤差・急斜面の誤検出・見落とし・地図の更新時間も比較する。testの結果を見て閾値を変えない。
028bとの組合せの評価は、そのブランチのレビューと仕上げ後に別の条件として行う。

## 4. 限界・未実行・確認してほしいこと

古い地図より0.3m以上高くなった本当の地形も除かれる。新しい砂の盛り上がりなどは、既存の点数条件を満たすと障害物として扱われる。
上面しか見えていないセルでは地面を測れていないため古い地図へ戻す仮定である。古い地図の誤差、位置合わせの誤差、閾値より低い障害物による高さの誤りまでは解決しない。
保存済みの最終DEMだけでは、当時の全64点履歴や全点群ストリームを復元できないため、研究PCの2失敗を新方式で走り直したという結果は作っていない。
Gazeboでの完走率・安全性・地図の更新性能は未測定。合成点群で問題の機序が除かれることまで確認した。
Claudeには、実走で偽の急斜面が減るか、古い地図への代入が真の地形変化を見落とす影響、028bの解除範囲と組み合わせた場合の安全性を確認してほしい。

### 実行環境と既存ファイルの保全

'''
    report += block(VERIFY/'protocol.json', 'json')+block(VERIFY/'preservation_audit.json', 'json')
    names = subprocess.check_output(['git', 'diff', '--name-only', protocol['base'], '--', 'conference'], cwd=REPO, text=True).splitlines()
    names += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', 'conference'], cwd=REPO, text=True).splitlines()
    names += ['conference/results/ground_estimate/REPORT_ja.md', 'conference/results/ground_estimate/changed_files.txt']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    report += '\n### 変更・追加ファイル一覧\n\n'+'\n'.join('- `'+name+'`' for name in names)+'\n'
    (OUT/'REPORT_ja.md').write_text(report)
    assert all(path.stat().st_size < 5_000_000 for path in OUT.rglob('*') if path.is_file())
    print('Report written:', len(tests), 'test modules passed;', count-len(original_changes), 'original files unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation-commit', required=True)
    main(parser.parse_args().implementation_commit)
