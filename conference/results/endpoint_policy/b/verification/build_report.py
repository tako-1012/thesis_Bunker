"""Write an honest task028b handoff, including the unsatisfied saved-start test."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = VERIFY.parents[3]
REPO = ROOT.parent


def block(path, language='text'):
    return '```'+language+'\n'+path.read_text().rstrip('\n')+'\n```\n\n'


def main(commit):
    commit = subprocess.check_output(['git','rev-parse',commit+'^{commit}'],cwd=REPO,text=True).strip()
    protocol = json.loads((VERIFY/'protocol.json').read_text())
    for name, checksum in protocol['source_sha256'].items():
        source = (REPO/name).read_bytes()
        assert hashlib.sha256(source).hexdigest() == checksum, name
        assert subprocess.check_output(['git','show',commit+':'+name],cwd=REPO) == source, name
    baseline = json.loads((VERIFY/'baseline_sha256.json').read_text())
    changed = [name for name,h in baseline.items() if hashlib.sha256((REPO/name).read_bytes()).hexdigest() != h]
    assert changed == list(protocol['source_sha256'])[:4], changed
    summary = (VERIFY/'test_summary.txt').read_text().splitlines()
    assert len(summary) == len(list((ROOT/'tests').glob('test_*.py')))
    failed = [line for line in summary if not line.endswith('exit=0')]
    assert failed == ['test_endpoint_component exit=1'], failed
    rows = json.loads((OUT/'replay.json').read_text())
    assert len(rows) == 6 and {r['policy'] for r in rows} == {'escape','escape_component'}
    assert all(r['raw_cells_cleared'] == r['raw_path_cells'] == 0 for r in rows)
    (OUT/'implementation_commit.txt').write_text(commit+'\n')
    report = '# 指示書028b：始点の連結成分による解除（完了条件未達）\n\n'
    report += '**保存済み始点型2例で経路を見つける条件は未達。急斜面の保護条件と衝突している。テストを弱めず、失敗したまま記録した。**\n\n'
    report += '実装・検証ログのコミットID：`'+commit+'`。この報告書は後続の文書コミットで追加する。\n\n'
    report += '作業ブランチ：`codex/028b-start-component`。基点：`'+protocol['base']+'`（作業開始時の最新realtime-map）。日付：'+protocol['client_date']+'（日本時間）。マージしない。\n\n'
    report += '''## 定義と実装

**この定義は test の砂浜の失敗を見たあとで決めた。** 保存済みの失敗を使う再現は独立した評価ではない。新しいGazeboの反復評価は今回実施していない。

- `tapp/endpoint_policy.py`：`escape_maps(snapshot, policy='escape')` に `escape_component` を追加。`lethal & ~(detected | prior_raw | steep)` のうち、始点セルを含む4近傍の成分だけを解除する。始点が生の障害物なら解除は0。始点が元から通行可能な場合も成分は作らない。
- 4近傍を明示した `binary_propagation` を使用する。通行可能セルや斜めだけの接触を経由して広げない。距離・面積・セル数の上限や新しい数値パラメータは加えていない。既存の0.5m解除は `escape` のまま。
- `ros2_jazzy/gz_checks/endpoint_runtime.py`：探索時と、最新地図での受け渡し時の両方で選択した方針を使う。代替終点・有限の再試行・停止・次地点への移行・診断・解除マスクの保存を両方式で利用する。
- `ros2_jazzy/gz_checks/lidar_checks.py`：`--endpoint-policy escape_component` を追加し、manifestとROSパラメータへ渡す。既定は `none`。
- `experiments/endpoint_replay.py`：`compare_replay()` と `--compare` を追加。3例×2定義の6行をJSON/CSV/表示ログに保存する。真値は計画後の監査だけで読み込む。引数なしの従来の3例の再現はそのまま。
- `tests/test_endpoint_component.py`：4近傍の独立BFSとの一致、禁止マスクの保護、コピーの不変性、合成地図での脱出と実際の非同期アダプターの受け渡し、代替終点・再試行・遅延した経路の拒否、旧出力のバイト一致を検証。保存例での要求された成功条件のassertionも残した。

既定のnoneランタイムは従来の `LidarOnlineMission` そのもの。既存の0.5m・1.0m・1.0秒、障害物判定・コスト式は変えない。
旧none/coarse、none/fine、escape、escape＋診断の準備出力を変更前のJSONバイトと比較し、実行機のPython/NumPy欄だけを合わせた上で一致した。
旧escapeによる3例の再現のJSONも、変更前に保存した全文と一致した。既存テストファイルは変更していない。

## 保存データで見つかった条件の衝突

既存の `saved_snapshot` は、保存済み推定DEMから `TraversabilityMap(...).steep` を作る。既存の `raw_mask` は検出障害物・事前の生マスク・この急斜面マスクのORである。
指定された始点型2例では、始点 `(154,142)` の `steep` がどちらもtrueだった。推定傾斜は下記の診断結果のとおりで、既存上限30°を超えている。
`detected` と `prior_raw` はfalseだが、急斜面そのものとして保護するマスクに含まれる。そのため、膨張のみの成分に始点は入らず、解除数は0になる。

同じセルは真値では通行可能だが、真値を使って計画用の急斜面判定を置き換えることはしていない。
現在のrawマスク定義を維持したまま、「急斜面を決して開けない」と「この2例で始点から経路を得る」を同時に満たすことはできない。
これは保存済みの最後の地図についての事実であり、実走の失敗瞬間も同じ急斜面だったと確定するものではない。

利用者に急斜面の扱いの確認を求めた。追加の急斜面解除やしきい値変更は行わず、依頼で明示された保護条件を維持している。
始点のrawラベルを書き換えたり、真値を計画へ渡したり、要求された成功assertionを削除・skip・xfailにしたりしていない。

診断は元ファイルのSHA-256を処理前後で照合した読み取り専用の処理である。傾斜はPythonで保存配列から計算した。

'''
    report += block(VERIFY/'saved_start_diagnosis_log.txt')
    report += '## 3例×両定義の再現の表（表示をそのまま）\n\n'+block(OUT/'replay_log.txt')
    report += '''解除マス数と、解除マス中の真値lethal数を別々に表示した。生の障害物の解除と、返された経路が生の障害物を通ったマス数は全行0。
失敗行の空の経路で0と出ることは、安全に走行・脱出した証拠ではない。始点型2例は両方とも未解決で、終点型1例では両方式で同じ仮の終点への経路が得られた。
この再現は最後の地図での計画であり、実走の地図更新や再試行を時間順に再生したものではない。有限の再試行と次地点への移行は合成地図のアダプターテストで確認した。

## 実行したコマンドとテスト出力の全文

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-028b-mpl XDG_CACHE_HOME=/tmp/thesis-028b-cache` を指定した。

```bash
cd conference
python3 -m tests.test_planners
python3 results/endpoint_policy/b/verification/capture_legacy.py  # 変更前に一度実行
python3 -m experiments.endpoint_replay --compare --output results/endpoint_policy/b
python3 -m tests.test_endpoint_component
python3 results/endpoint_policy/b/verification/diagnose_saved_starts.py
python3 results/endpoint_policy/b/verification/run_tests.py
python3 results/endpoint_policy/b/verification/run_tests.py --resume
python3 results/endpoint_policy/b/verification/refresh_replay.py
python3 results/endpoint_policy/b/verification/build_report.py --implementation-commit <上記ID>
```

全体のランナーは既知の新規テストの失敗を隠さず、独立した残りのモジュールも実行して全出力を集めた。終了コードは非0である。
最初のランナーは13モジュールのログを保存した後にプロセスが失われたため、ソースのSHA-256と既存の完了ログを照合し、`--resume` で未完了の残りを実行した。既知の非0終了もそのまま保持した。
全テスト実行後、静的再現の失敗の表示だけを `no_path` に直した。再現と、それに依存する新規テストを再実行し、全文ログを更新した。時間順の再試行を実施したように読める表示を避けるためで、計画・実行時の処理は変えていない。従来の `replay()` の出力はそのままである。

変更前のプランナー：

'''
    report += block(VERIFY/'planners_before_log.txt')+block(VERIFY/'capture_legacy_log.txt')
    report += '対象テストの出力全文：\n\n'+block(VERIFY/'component_log.txt')
    report += '全テストの出力全文：\n\n'+block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    report += '## 既存ファイルと実行環境\n\n'+block(VERIFY/'preservation_audit.json','json')+block(VERIFY/'protocol.json','json')
    report += '''## できなかったこと・次に確認が必要なこと

完了条件の「保存済み始点型2例の成功」と「全テスト成功」は未達。既存25モジュールは成功し、新規 `test_endpoint_component` の保存済み成功条件が1モジュール分失敗した。
合成地図の新しい解除・受け渡し・保護・旧出力の比較はその失敗より前にすべて成功している。
どのマスクを「急斜面そのもの」とするか、既存の推定DEM由来の定義と今回の期待が一致しているかを再確認する必要がある。

Gazebo・実際のDocker・研究PCでの実走は、指定どおり実行していない。走行の完走率や、物理的に安全に脱出できるかは未評価である。
成分が長くつながる地図では、解除範囲も長くなる。0.5m以内という距離制限は新方式にはない。生マスクが推定である限り、真の障害物をすべて除外できるという保証もない。
定義を確認してから、別途研究PCで旧escape・新escape_componentを同じ条件で繰り返し評価する必要がある。
実行時の選択引数は `--map fine --endpoint-policy escape` と `--map fine --endpoint-policy escape_component`。既定はnoneのままである。
'''
    names = subprocess.check_output(['git','diff','--name-only',protocol['base'],'--','conference'],cwd=REPO,text=True).splitlines()
    names += subprocess.check_output(['git','ls-files','--others','--exclude-standard','conference'],cwd=REPO,text=True).splitlines()
    names += ['conference/results/endpoint_policy/b/REPORT_ja.md','conference/results/endpoint_policy/b/changed_files.txt']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    report += '\n## 変更・追加ファイル一覧\n\n'+'\n'.join('- `'+n+'`' for n in names)+'\n'
    (OUT/'REPORT_ja.md').write_text(report)
    print('Report written; completion conditions unmet. Modules:',len(summary),'failed:',failed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation-commit', required=True)
    main(parser.parse_args().implementation_commit)
