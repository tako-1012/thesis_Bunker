"""Generate task034 Japanese report from executed logs and immutable source evidence."""
from pathlib import Path
import hashlib,json,subprocess
OUT=Path(__file__).resolve().parent.parent
ROOT=OUT.parents[1]
BASE='09cc219b10ed69589fd4b7611c1555924e11efa4'

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
protocol=json.loads((OUT/'verification/protocol.json').read_text())
assert protocol['base']==BASE
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protocol['source_sha256'].items())
original=json.loads((OUT/'verification/defaults_original.json').read_text())
portable=json.loads((OUT/'verification/defaults_before.json').read_text())
assert all(original[k]==portable[k]['full_sha256'] for k in ('coarse','fine','real'))
modules=sorted(p.stem for p in (ROOT/'tests').glob('test_*.py'))
summary=(OUT/'verification/test_summary.txt').read_text().splitlines()
assert summary==[name+' exit=0' for name in modules]
assert not git('diff','--name-only')
record=OUT/'implementation_commit.txt'
implementation=record.read_text().strip() if record.exists() else git('rev-parse','HEAD')
changed=git('diff','--relative','--name-only',BASE,'HEAD','--','.').splitlines()
assert set(p for p in changed if not p.startswith('results/online_safety/'))==set(protocol['source_sha256'])
for p in ['data','maps','gazebo_worlds','paper','webui','tapp/online_mission.py','tapp/follower.py',
          'tapp/endpoint_policy.py','ros2_jazzy/gz_checks/endpoint_runtime.py','tapp/traversability.py','tapp/footprint.py']:
    assert git('rev-parse',BASE+':conference/'+p)==git('rev-parse','HEAD:conference/'+p),p
base_tree=subprocess.check_output(['git','ls-tree','-rz',BASE,'--','conference/results'],cwd=ROOT.parent)
new_tree=subprocess.check_output(['git','ls-tree','-rz','HEAD','--','conference/results'],cwd=ROOT.parent)
new_old=b'\0'.join(x for x in new_tree.split(b'\0') if x and b'\tconference/results/online_safety/' not in x)+b'\0'
assert base_tree==new_old
count=len([x for x in base_tree.split(b'\0') if x])
original_modified=git('diff','--relative','--diff-filter=M','--name-only',BASE,'HEAD','--','.').splitlines()
assert len(original_modified)==5
assert all(p.stat().st_size<5_000_000 for p in OUT.rglob('*') if p.is_file())
audit=dict(base=BASE,implementation_commit=implementation,source_sha256=protocol['source_sha256'],
           original_modified=original_modified,old_results_files=count,old_results_changed=False,
           old_results_tree_sha256=hashlib.sha256(base_tree).hexdigest(),
           endpoint_028_code_changed=False,protected_data_maps_world_paper_webui_changed=False,
           tests=dict(modules=len(modules),failed=0),gazebo='not executed')
(OUT/'verification/preservation_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
record.write_text(implementation+'\n')
files=sorted(set(changed+['results/online_safety/REPORT_ja.md','results/online_safety/changed_files.txt',
                         'results/online_safety/implementation_commit.txt','results/online_safety/verification/preservation_audit.json']))
(OUT/'changed_files.txt').write_text('\n'.join('conference/'+p for p in files)+'\n')
readme=(OUT/'README_ja.md').read_text()
logs=(OUT/'verification/all_tests_log.txt').read_text()
replay=(OUT/'replay_log.txt').read_text()
report=f'''# 034：オンライン再計画の安全修正の実装報告

## 1. コミット・変更・実行コマンドとテスト全文

- 土台：最新の realtime-map を取得した `{BASE}`。
- ブランチ：`codex/034-online-safety`。realtime-mapへマージせず、pushまでで止める。
- 実装と検証データのコミット：`{implementation}`。この報告は後続の記録用コミットに保存する。
- Python専用venv：`/workspace/venvs/thesis-034`（`--system-site-packages`）。既存の依存関係を使用し、パッケージ追加・sudo操作はしていない。
- 実行環境：`verification/environment.json`。Gazebo・Docker・ROS2の実プロセスは未実行。

既存ファイルの変更は次の5つ（すべて非既定オプションの受け渡し）：

- `ros2_jazzy/gz_checks/lidar_checks.py`：`--online-fixes`、v1のmanifest・事前値の記録、両ノードのROSパラメータ、旧集計からの分離。
- `ros2_jazzy/gz_checks/lidar_planner.py`：CLI/ROSパラメータとv1ランタイムの選択。
- `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_planner.py`：仮想センサー側の選択と、安全停止の状態を計画側に渡す処理。LiDAR側もこのコールバックを共有する。
- 同 `path_follower.py`：CLI/ROSパラメータ、姿勢・IMUを含む追従、0速度と停止状態の発信、ログを保ったままの再開、安全停止と終了理由の記録。
- 同 `online_runtime.py`：`replace_running_path` に選択式の追従クラスを渡すキーワード引数。既定の計画・受け渡し処理は変更していない。

追加した実装：

- `tapp/online_safety.py`：`SafetyOnlinePlanner`、`SafetyMissionFollower`、`make_follower`、事前値と選択の検証。
- `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_safety.py`：`SafetyRuntimeMixin`、`SafetyAsyncOnlineMission`、`make_async_runtime`、`handle_safety_state`、安全イベントの記録。
- `ros2_jazzy/gz_checks/safety_runtime.py`：LiDAR用のv1ランタイムと、028bの解除を使わない診断用ランタイム、`make_safety_lidar_runtime`。
- `tests/test_online_safety.py`：指示書1〜6、全体をまとめた停止・再計画・受け渡し・追従の再開、計算中の旧結果の破棄、診断との併用。
- `results/online_safety/`：この報告、README、停止状態の比較CSV・表示ログ、変更前のバイト比較用ハッシュ、実行した全テストのログと再実行スクリプト。

全ファイル一覧は `changed_files.txt`。既存結果 {count} ファイルは同じGitオブジェクトのまま。
データ・地図・world・paper・webui、既存テスト、`online_mission.py`・`follower.py`・`traversability.py`・`footprint.py`、
028bの `endpoint_policy.py`・`endpoint_runtime.py` は変更していない。根拠は `verification/preservation_audit.json`。

主な実行コマンド：

```bash
# /workspace/thesis_Bunker
git fetch origin refs/heads/realtime-map:refs/remotes/origin/realtime-map
git worktree add --no-checkout -b codex/034-online-safety /workspace/thesis-034 origin/realtime-map
# 容量を抑えるためsparse checkout。必要な既存の入力は内容を変えず展開。

# /workspace/thesis-034/conference
python3 -m venv --system-site-packages /workspace/venvs/thesis-034
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-034-mpl XDG_CACHE_HOME=/tmp/thesis-034-cache /workspace/venvs/thesis-034/bin/python -m tests.test_planners
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-034-mpl XDG_CACHE_HOME=/tmp/thesis-034-cache PYTHONPATH=. /workspace/venvs/thesis-034/bin/python results/online_safety/verification/capture_defaults.py > results/online_safety/verification/defaults_before.json
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-034-mpl XDG_CACHE_HOME=/tmp/thesis-034-cache /workspace/venvs/thesis-034/bin/python -m tests.test_online_safety
/workspace/venvs/thesis-034/bin/python results/online_safety/verification/run_tests.py
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-034-mpl XDG_CACHE_HOME=/tmp/thesis-034-cache /workspace/venvs/thesis-034/bin/python ros2_jazzy/gz_checks/lidar_checks.py --output results/online_safety/prepared --patch-count 3 --map fine --ground-estimate non_obstacle --endpoint-policy none --diagnostics --online-fixes v1 --prepare-only
/workspace/venvs/thesis-034/bin/python results/online_safety/verification/build_report.py
git diff --check
```

`capture_defaults.py` は実装前に実行した。実装後、implicit/explicit none の両方で、ランタイムのコマンドJSON、
plans.csvと診断の記録、追従のtrajectory/mission、manifestのハッシュが一致した。
時計はテスト用に固定し、実際の性能値を捏造していない。
manifestは同じPython/NumPy環境なら全文のバイトを照合する。他の環境で実行する場合は、環境名だけを記録したinput_environment以外の全文を厳密に照合する。
変更前に保存した元の全文ハッシュはdefaults_original.jsonに保ち、環境を除く比較を加える前に、生成した全文がこの元のハッシュと一致することを確認した。

開発中の新規テストの初回は、仮想センサー用の事前地図にも始点の障害物を入れてしまい、巡回経路が作れず失敗した。
目的は点群で後から始点が塞がったときの受け渡しなので、事前地図を通れるままにし、観測側だけを塞ぐ形に直した。
初回の出力は `verification/development_first_log.txt` に残した。既存テスト・期待値は変えていない。

最終検証は全 {len(modules)} モジュールが終了コード0。全モジュールを別のPythonプロセスで実行し、最大2プロセスを同時に動かした。
新しい安全処理・ROSコールバックはモックを用いたPythonテストで、ROS2/Gazeboの起動はない。

### 全テスト出力（省略なし）

```text
{logs.rstrip()}
```

## 2. 保存した実際の停止状態の再生

入力：`results/diagnosis_033/fixtures/stuck_0847_C1_r2_t1345.npz`。
SHA-256：`{protocol['fixture_sha256']}`。読み取りだけで使い、再保存していない。
033と同じ保存されたlethal/cost/pose/goalでA*とコスト考慮の平滑化を実行し、その結果をそれぞれの実装の `_join` に渡した。
真値を計画の入力に追加していない。

以下は実行して得た出力そのまま（`replay_log.txt`、配列は `replay.csv`）：

```text
{replay.rstrip()}
```

両方とも探索には成功した。noneは受け渡せず、v1は受け渡せた。v1の経路が、始点以外の通行不可セルに触れないことも確認した。
これは保存した状態での経路の受け渡しの確認であり、物理的な脱出・完走の実験ではない。

## 3. 研究PCでの引数と評価案

{readme[readme.index('## 研究PCでの評価案'):readme.index('## 未確認の点')]}

CLIの準備だけは `--prepare-only` で実行し、`prepared/manifest.json` と `verification/prepare_only_log.txt` を保存した。
実行状態はnot_started。Gazebo・world生成・走行は未実行。

## 4. 実装の解釈・できなかったこと・Claudeに確認してほしいこと

{readme[readme.index('## 選択と既定の保持'):readme.index('## 研究PCでの評価案')]}

{readme[readme.index('## 未確認の点'):]}
'''
(OUT/'REPORT_ja.md').write_text(report)
print('Report saved; modules:',len(modules),'failed: 0; original result files unchanged:',count)
