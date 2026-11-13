"""Build Japanese task032 report from actual logs, hashes and committed sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent.parent
ROOT=OUT.parents[1]
BASE='d95c41c9c34b50f27ede86d657a6dbc5faa81912'
MODIFIED=['data_prep/export_gazebo.py', 'ros2_jazzy/gz_checks/lidar_checks.py',
          'ros2_jazzy/gz_checks/lidar_map.py', 'ros2_jazzy/gz_checks/lidar_planner.py',
          'tapp/pointcloud_map_fine.py', 'tapp/pointcloud_map_multi.py']
SOURCES=MODIFIED+['tapp/local_ground.py','tapp/prior_variants.py','tests/test_prior_free.py']

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

if '--freeze' in sys.argv:
    (OUT/'verification/protocol.json').write_text(json.dumps(dict(base=BASE,
        source_sha256={p:sha(ROOT/p) for p in SOURCES},
        fixed=dict(fine_resolution_m=.1, obstacle_height_m=.3, min_obstacle_points=3,
                   robot_radius_m=.5, local_square_side_m=1.5, trim_m=.15, fits=2,
                   hills=20, sigma_m=5., amplitude_m=[-.3,.3], seed='SeedSequence([32, patch_index])'),
        gazebo='not executed', default_fixture='captured before task032 source edits'),indent=2)+'\n')
    sys.exit(0)

protocol=json.loads((OUT/'verification/protocol.json').read_text())
assert {p:sha(ROOT/p) for p in SOURCES}==protocol['source_sha256']
summary=(OUT/'verification/final_test_summary.txt').read_text()
modules=sorted(p.stem for p in (ROOT/'tests').glob('test_*.py'))
assert summary.splitlines()==[m+' exit=0' for m in modules]
commit_file=OUT/'implementation_commit.txt'
implementation=commit_file.read_text().strip() if commit_file.exists() else git('rev-parse','HEAD')
changed=git('diff','--relative','--name-only',BASE,'HEAD','--','.').splitlines()
assert set(p for p in changed if not p.startswith('results/prior_free/'))==set(SOURCES)
originals=git('diff','--relative','--diff-filter=M','--name-only',BASE,'HEAD','--','.').splitlines()
assert set(originals)==set(MODIFIED),originals
# Protected trees remain the very same Git blobs (sparse checkout does not
# materialize every old result). Also require no unstaged tracked changes.
assert not git('diff','--name-only')
for path in ('data','maps','gazebo_worlds','paper','webui'):
    assert git('rev-parse',BASE+':conference/'+path)==git('rev-parse','HEAD:conference/'+path)
old_result_names=git('ls-tree','-r','--name-only',BASE,'--','results').splitlines()
for path in old_result_names:
    # Content identity is proved in bulk below; retain the full name inventory.
    assert not path.startswith('results/prior_free/')
base_tree=subprocess.check_output(['git','ls-tree','-rz',BASE,'--','conference/results'],cwd=ROOT.parent)
current_tree=subprocess.check_output(['git','ls-tree','-rz','HEAD','--','conference/results'],cwd=ROOT.parent)
current_old=b'\0'.join(r for r in current_tree.split(b'\0') if r and b'\tconference/results/prior_free/' not in r)+b'\0'
assert base_tree==current_old
assert all(p.stat().st_size<5_000_000 for p in OUT.rglob('*') if p.is_file())
audit=dict(base=BASE,implementation_commit=implementation,source_sha256=protocol['source_sha256'],
           existing_modified_files=originals,existing_results_changed=False,
           existing_results_tree_sha256=hashlib.sha256(base_tree).hexdigest(),
           existing_result_files=len(old_result_names),data_maps_world_paper_webui_tree_unchanged=True,
           tests=dict(modules=len(modules),failed=0),gazebo='not executed')
(OUT/'verification/preservation_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
(OUT/'implementation_commit.txt').write_text(implementation+'\n')
files=sorted(set(changed+['results/prior_free/REPORT_ja.md','results/prior_free/changed_files.txt',
                         'results/prior_free/implementation_commit.txt','results/prior_free/verification/preservation_audit.json']))
(OUT/'changed_files.txt').write_text('\n'.join('conference/'+p for p in files)+'\n')
logs=(OUT/'verification/all_tests_log.txt').read_text()+'\n$ python3 -m tests.test_lab_geometry # 保存済みCSVを展開後の再実行\n'+(OUT/'verification/retry_test_lab_geometry_log.txt').read_text()+'\nexit=0\n'
results=(OUT/'prior_free_log.txt').read_text()
readme=(OUT/'README_ja.md').read_text()
report=f'''# 指示書032：古い地図に依存しない局所障害物判定の実装報告

## 1. コミット・実装・実行コマンド・全テスト

- 土台：最新の `realtime-map` を取得した `{BASE}`。
- ブランチ：`codex/032-prior-free`。マージせず push する。
- 実装と検証データのコミット：`{implementation}`。この報告は後続の記録用コミットに保存する。
- 実行環境は `verification/environment.json`。専用venvを `--system-site-packages` で作成し、既存の依存関係を使用した。新しいパッケージ・sudo操作はない。
- Gazebo・Docker・ROS2の実プロセスは未実行。Pythonで計算し、ROSの通信部分はモックで確認した。

変更した既存ファイルは6つだけ（既定値を変えない選択式の追加）：

- `tapp/pointcloud_map_fine.py`：コンストラクタの `obstacle_reference` と local の分岐。
- `tapp/pointcloud_map_multi.py`：local のときだけ高い点のカウンタを局所基準で記録。センサーごとの保持履歴と初回検出の帰属は同じ。
- `ros2_jazzy/gz_checks/lidar_map.py`：`make_pointcloud_map` の選択と不正な組み合わせの拒否。
- `ros2_jazzy/gz_checks/lidar_checks.py`：3つのCLI、manifest、worldの選択、priorだけの変更、変更後priorでの初期経路の再計画、ROSパラメータの受け渡し。
- `ros2_jazzy/gz_checks/lidar_planner.py`：CLI・ROSパラメータから局所判定へ接続。
- `data_prep/export_gazebo.py`：`debris_box_height='true'` とSDFコメント・READMEへの条件記録。既定のXML/PNG/READMEは同一。

追加した実装：

- `tapp/local_ground.py`：`fine_cells`、`local_planes`、`update_local`。点群だけで2回の平面当てはめ・障害物検出・地面の中央値を計算し、既存のTraversabilityMap・膨張を呼ぶ。
- `tapp/prior_variants.py`：`prior_variant`。exact は元のオブジェクトをそのまま返し、perturbed/none のときだけ新しい標高と統計値を作る。
- `tests/test_prior_free.py`：指示書の1〜6、平面が決まらない場合、取り付けを含む複数センサー、古い地図からの独立性、CLI/ROS受け渡し、初期経路の再計画を検証。
- `results/prior_free/`：この報告、README、実行したCSV/ログ、変更前ハッシュ、再実行用スクリプト。

完全なファイル一覧：`changed_files.txt`。
既存のデータ・地図・world・paper・webuiのGitツリーは同一。既存結果は {len(old_result_names)} ファイルすべて同じGitオブジェクト。
`traversability.py`・`footprint.py`・`online_mission.py`・既存の経路計画・旧PointCloudMap・既存テストは変更していない。
根拠は `verification/preservation_audit.json`。非既定のROS接続は今回の指示書の許可範囲として変更した。

実行した主なコマンド（カレントディレクトリを明記）：

```bash
# /workspace/thesis_Bunker
cat AGENTS.md
git fetch origin realtime-map
git fetch origin refs/heads/realtime-map:refs/remotes/origin/realtime-map
# 全展開は容量不足で失敗。新規作業コピーだけを検証して除き、必要ファイルをsparse checkoutした。
# 過去の作業ツリーや結果は削除していない。

# /workspace/thesis-032/conference
python3 -m venv --system-site-packages /workspace/venvs/thesis-032
/workspace/venvs/thesis-032/bin/python -m tests.test_planners
PYTHONPATH=. /workspace/venvs/thesis-032/bin/python results/prior_free/verification/capture_defaults.py > results/prior_free/verification/defaults_before.json
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-032-mpl XDG_CACHE_HOME=/tmp/thesis-032-cache /workspace/venvs/thesis-032/bin/python -m tests.test_prior_free
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-032-mpl XDG_CACHE_HOME=/tmp/thesis-032-cache PYTHONPATH=. /workspace/venvs/thesis-032/bin/python results/prior_free/verification/diagnostics.py > results/prior_free/prior_free_log.txt
/workspace/venvs/thesis-032/bin/python results/prior_free/verification/run_tests.py
/workspace/venvs/thesis-032/bin/python results/prior_free/verification/build_report.py --freeze
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-032-mpl XDG_CACHE_HOME=/tmp/thesis-032-cache /workspace/venvs/thesis-032/bin/python ros2_jazzy/gz_checks/lidar_checks.py --output results/prior_free/prepared --patch-count 3 --map fine --sensors lidar_real+depth2 --ground-estimate non_obstacle --obstacle-reference local --debris-box-height true --prior-variant perturbed --prepare-only
/workspace/venvs/thesis-032/bin/python results/prior_free/verification/finalize_tests.py
git diff --check
```

初回の新規合成テストは、地面が1細格子1点だけで「3点以上」の誤検出を再現できず、テストの前提のassertで失敗した。
点群を各位置3点にして検出条件を満たすよう修正した。既存のテスト・期待値は変更していない。
修正後の個別テストは成功した。全モジュール実行の初回は、sparse checkoutで保存済みCSVの展開を漏らしていたため、test_lab_geometryだけFileNotFoundErrorになった。\n同じコミットの入力CSVを展開し、このテストを再実行して終了コード0を確認した。テストや期待値は変えず、初回の失敗も下の全文に残した。\n最終結果は {len(modules)} 件すべて終了コード0（final_test_summary.txt）。
`run_tests.py` はテストを省略せず、各 `test_*.py` を独立したPythonプロセスで実行して標準出力と標準エラーを保存する。

### 全テスト出力（省略なし）

```text
{logs.rstrip()}
```

## 2. 合成点群の取り違え・見落とし、事前地図の変化量

以下は `verification/diagnostics.py` の出力そのまま。障害物そのものの0.5mセルを数え、膨張後の通行不可セルとは区別した。
箱は1セル、高さ0.4m。平面・20°斜面の真の地面を生成し、判定に渡すpriorだけを0・−0.4・+0.4m変えた。
local の箱なし・箱ありはいずれも誤検出0、箱の見落とし0。prior は−0.4mで地面を誤検出し、+0.4mで箱を見落とした。
実センサーのノイズ・遮蔽を含む精度の結論ではない。

perturbed は validation 12か所、200m、seed=0の clean 地図で計算した。指示書の固定値を一度適用しただけで、値の調整は行っていない。
最大・平均の絶対差は陸域だけの実測した配列差。ガウス形の山が重なるため和は±0.3mに収まるとは限らない。

```text
{results.rstrip()}
```

## 3. 研究PCでの引数と評価の案

CLIの `--prepare-only` も実行し、`prepared/manifest.json` と `verification/prepare_only_log.txt` を保存した。実行状態は not_started で、world生成・Gazebo起動・物理走行は行っていない。manifestの scenarios は既存コホートの地点・初期経路の記録で、perturbed/noneの実走時の初期経路は変更後priorで再計画してmission.jsonに保存する。

{readme[readme.index('## 研究PCでの実行案'):readme.index('## 限界・確認が必要なこと')]}

## 4. 解釈・できなかったこと・Claudeに確認してほしいこと

{readme[readme.index('## 局所平面の解釈'):readme.index('## 研究PCでの実行案')]}

{readme[readme.index('## 限界・確認が必要なこと'):]}

Claudeには、特に疎な実機LiDARで局所面の支持点が足りるか、処理が10Hzに追いつくか、
箱の上面が広いときや砂が局所平面ではないときの失敗を研究PCで確認してほしい。
030のC2の転倒・停止原因はこの変更では扱っておらず、解消したとは主張しない。
'''
(OUT/'REPORT_ja.md').write_text(report)
print('report saved:', OUT/'REPORT_ja.md')
print('all test modules:',len(modules),'failures: 0; existing result files unchanged:',len(old_result_names))
