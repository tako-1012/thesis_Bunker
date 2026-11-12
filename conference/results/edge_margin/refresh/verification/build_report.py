"""Write the refreshed task024 report from executed Python tests/preparation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = VERIFY.parents[3]
REPO = ROOT.parent
RESULTS = OUT.parent

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()

def block(path):
    return '```text\n'+path.read_text().rstrip('\n')+'\n```\n\n'

def main(commit, branch):
    commit = git('rev-parse', commit+'^{commit}')
    p = json.loads((VERIFY/'protocol.json').read_text())
    for name, h in p['source_sha256'].items():
        data = (REPO/name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == h, name
        assert subprocess.check_output(['git', 'show', commit+':'+name], cwd=REPO) == data, name
    digest = hashlib.sha256()
    for name in git('ls-tree', '-r', '--name-only', p['base'], 'conference').splitlines():
        if name not in p['editable']:
            digest.update(name.encode()+b'\0'+hashlib.sha256((REPO/name).read_bytes()).digest())
    assert digest.hexdigest() == p['untouched_sha256']
    tests = sorted((ROOT/'tests').glob('test_*.py'))
    summary = (VERIFY/'test_summary.txt').read_text()
    assert summary.splitlines() == [t.stem+' exit=0' for t in tests]
    assert (VERIFY/'all_tests_log.txt').read_text() == '\n'.join((VERIFY/(t.stem+'_log.txt')).read_text() for t in tests)
    manifest = json.loads((OUT/'manifest.json').read_text())
    audits = manifest['waypoint_audit']
    assert len(audits) == 10 and len(manifest['cases']) == 40
    assert all(a['start_edge_m'] >= 10 and min(a['new_edge_m']) >= 10 for a in audits)
    changed = [a['patch'] for a in audits if a['points_changed']]
    assert len(changed) == 5
    rows = list(csv.DictReader((OUT/'runs.csv').open()))
    assert sum(r['execution'] == '再利用' for r in rows) == 20
    assert all(r['execution'] == '未実行' for r in rows if r['record_origin'] == 'rerun')
    (OUT/'implementation_commit.txt').write_text(commit+'\n')
    old_report = RESULTS/'REPORT_2026-11-06_ja.md'
    if not old_report.exists():
        old_report.write_bytes(subprocess.check_output(['git','show',p['previous_implementation']+':conference/results/edge_margin/REPORT_ja.md'],cwd=REPO))
    report = '# 指示書024：最新realtime-map上での10m余白の実装・検証\n\n'
    report += '作業ブランチ：`'+branch+'`。実装・検証コミット：`'+commit+'`。土台：`'+p['base']+'`（作業開始時の最新realtime-map）。\n\n'
    report += 'Pythonの全'+str(len(tests))+'テストモジュールが成功した。今回Gazebo・実際のDockerは起動していない。\n\n'
    report += '''## 実装

旧実装 `e29320c` を最新の土台へ移植した。旧ブランチ・既存の未追跡ログは変更せず、別の作業領域を使った。過去の報告は `REPORT_2026-11-06_ja.md` に残した。
過去に記録されたDocker起動失敗は旧報告の履歴であり、今回の実行ではない。今回の準備結果と全テストは `refresh/` に保存した。

- `tapp/tour.py`：`sample_waypoints(..., edge_margin_m=0.0)`。同じ候補の順列から余白未満の候補だけを除き、距離・到達可能性の条件と既定の乱数順を維持する。
- `ros2_jazzy/gz_checks/edge_margin_checks.py`：同じ10か所の新旧地点を比較し、開始点が10m未満ならずらさず対象外。旧地点と同じ5か所の記録は再利用し、変更した5か所だけ4方式の再走行を依頼する。
- `run_edge_margin_checks.sh`：研究PCの通常Docker用。ソースは読み取り専用、build/worldは一時領域、新しい記録だけを書き込む。既存のmanifestの上書きは拒否する。
- `online_batch_checks.py` と `lidar_checks.py`：明示的に与えたシナリオと砂浜の集合だけを渡せる引数を追加。既定は変更しない。最新のground_estimate、endpoint_policy、実機センサー、THESIS_ONLY_PATCHの選択を維持し、選択集合はその選択との共通部分にした。親の集計を使う場合だけ子の集計を省略する。
- `experiments/edge_margin_report.py`：40行を再利用・再走行・未実行で区別し、既存の指標を集計する。検定・エネルギー集計は行わず、両方式が完走した同じ砂浜だけで対の差の中央値を計算する。実走がない砂浜の軌跡図は作らない。
- `tests/test_edge_margin.py`：既定と明示0のバイト一致、10か所の12点の余白・間隔・到達可能性、開始点の対象外、再利用metadataの完全一致、混合記録の集計、起動先の振り分け、ラッパーを検証する。Dockerは偽物の引数記録コマンドで、実際には起動しない。

**10mは事前に決めた値で、調整していない。** 仮想センサーのR=10mに由来する。0は互換性テストにだけ使い、他の正の余白は試していない。
距離は外側のセル中心（400セルでは0〜199.5m）を基準とし、10mちょうどを許可する。heightmapの外周より内側の保守的な基準である。
同じSeedSequenceから12点を引き、最初の5点を使う。開始点・順序の決め方・TA*-S＋膨張0.5m・コスト・worldは変えない。
LiDARの2方式は旧022の標高配列を共用し、見た目のmesh・速度0.3倍・途切れの基準1.0秒をmanifestへ記録する。ground_estimateは既定のall_returns、endpoint_policyは既定のnoneのまま比較する。

## 地点の比較と4方式の表（表示をそのまま）

'''
    report += '地点が変わる砂浜：'+', '.join('`'+name+'`' for name in changed)+'。開始点は全10か所で条件を満たし、対象外はなかった。\n\n'
    report += block(OUT/'edge_margin_log.txt')
    report += '''上の再利用行は元の実測値をそのまま使った。再走行が必要な20行は未実行であり、転倒が消えたかは未評価である。
集計の完走数・転倒数・対の差は記録がある部分集合についての値で、10か所の新しい実走結果ではない。
新旧の全地点・開始点・端からの距離は `refresh/waypoints.csv`、記録の由来は `refresh/runs.csv` に保存した。

## 研究PCで後日走らせる手順（今回未実行）

```bash
cd conference
bash ros2_jazzy/gz_checks/run_edge_margin_checks.sh results/edge_margin/physical_run_new
python3 experiments/edge_margin_report.py results/edge_margin/physical_run_new
```

`physical_run_new` は未使用の保存先にする。変わらない砂浜は021〜023を再利用し、変わった砂浜だけ、古い地図・仮想R10・LiDAR coarse・LiDAR fineを走らせる。
元の記録は消さず、転倒・接触・完走と記録の完全性を確認する。実走した砂浜の軌跡図は集計スクリプトが保存する。

## 実行したPython確認と全文ログ

```bash
cd /workspace/thesis-024-refresh/conference
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/edge-refresh-mpl XDG_CACHE_HOME=/tmp/edge-refresh-cache python3 -m tests.test_edge_margin
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/edge-refresh-mpl XDG_CACHE_HOME=/tmp/edge-refresh-cache python3 ros2_jazzy/gz_checks/edge_margin_checks.py --prepare-only --output results/edge_margin/refresh
python3 results/edge_margin/refresh/verification/run_tests.py
```

全テストのランナーもOPENBLAS_NUM_THREADS=1と/tmpのキャッシュを指定した。以下はstdout・stderrの全文と実際の終了コードである。

'''
    report += block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    report += '''## できなかったこと・確認してほしいこと

Gazebo実走、転倒が消えたか、再走行の性能・更新時間の測定、新しい軌跡図は未実施。未測定の値は埋めていない。
接触の監査は中心軌跡についてであり、機体全体の安全性を保証するものではない。経路自体が端の余白内だけを通るという制約も追加していない。
Claudeには、研究PCでの4方式の起動・新旧記録の区別・端での転倒が残るかとその位置を確認してほしい。

最新土台での既存ファイルは、許可された3ソース以外について名前とSHA-256のダイジェストを照合し、不変を確認した。プロトコルは `refresh/verification/protocol.json` に保存した。

'''
    names=git('diff','--name-only',p['base'],'--','conference').splitlines()+git('ls-files','--others','--exclude-standard','conference').splitlines()
    names+=['conference/results/edge_margin/REPORT_ja.md','conference/results/edge_margin/REPORT_2026-11-06_ja.md','conference/results/edge_margin/refresh/changed_files.txt']
    names=sorted(set(names));(OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    report+='## 変更・追加ファイル\n\n'+'\n'.join('- `'+name+'`' for name in names)+'\n'
    (RESULTS/'REPORT_ja.md').write_text(report)
    assert all(f.stat().st_size<5_000_000 for f in RESULTS.rglob('*') if f.is_file())
    print('Report written:',len(tests),'test modules passed; changed patches:',changed)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation-commit',required=True)
    parser.add_argument('--branch',required=True)
    args=parser.parse_args();main(args.implementation_commit,args.branch)
