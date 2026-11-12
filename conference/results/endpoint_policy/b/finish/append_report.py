"""Append the corrected contract's report, retaining the historical report."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
ROOT = REPO/'conference'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()

def main(commit):
    commit = git('rev-parse', commit+'^{commit}')
    p = json.loads((OUT/'protocol.json').read_text())
    for name, checksum in p['source_sha256'].items():
        assert hashlib.sha256((REPO/name).read_bytes()).hexdigest() == checksum
        assert subprocess.check_output(['git', 'show', commit+':'+name], cwd=REPO) == (REPO/name).read_bytes()
    digest = hashlib.sha256()
    for name in git('ls-tree', '-r', '--name-only', p['merge_commit'], 'conference').splitlines():
        if name not in p['source_sha256'] and name != 'conference/results/endpoint_policy/b/REPORT_ja.md':
            digest.update(name.encode()+b'\0'+hashlib.sha256((REPO/name).read_bytes()).digest())
    assert digest.hexdigest() == p['untouched_sha256']
    tests = sorted((ROOT/'tests').glob('test_*.py'))
    summary = (OUT/'test_summary.txt').read_text()
    assert summary.splitlines() == [s.stem+' exit=0' for s in tests]
    assert (OUT/'all_tests_log.txt').read_text() == '\n'.join((OUT/(s.stem+'_log.txt')).read_text() for s in tests)
    report_path = OUT.parent/'REPORT_ja.md'
    original = subprocess.check_output(['git', 'show', p['merge_commit']+':conference/results/endpoint_policy/b/REPORT_ja.md'], cwd=REPO).decode()
    assert report_path.read_text() == original
    names = git('diff', '--name-only', p['merge_commit'], '--', 'conference').splitlines()
    names += git('ls-files', '--others', '--exclude-standard', 'conference').splitlines()
    names += ['conference/results/endpoint_policy/b/REPORT_ja.md',
              'conference/results/endpoint_policy/b/finish/changed_files.txt',
              'conference/results/endpoint_policy/b/finish/implementation_commit.txt']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    (OUT/'implementation_commit.txt').write_text(commit+'\n')
    text = '\n\n## 追記（2026-11-11）：前提を訂正した028bの仕上げ（全テスト成功）\n\n'
    text += '実装・検証コミット：`'+commit+'`。最新realtime-map：`'+p['realtime_map']+'`。取り込みmerge：`'+p['merge_commit']+'`。rebaseは行っていない。作業ブランチからrealtime-mapへの統合は行わず、pushまで。\n\n'
    text += '''**前提が誤っていたためテストを直した。** Claudeの指示書028末尾（2026-11-10）と利用者の明示的な依頼に基づく訂正である。
保存済み2例は始点そのものが推定DEMの急斜面であり、「経路が見つかる」を要求する前提が誤っていた。
上記の旧報告・失敗ログは当時の記録として残す。今回の完了判定はこの追記と `finish/` のログによる。

- `tapp/endpoint_policy.py`：通行不可の始点が急斜面なら `start_steep` と分類する。終点型の分類を先に行う従来の優先順を保つ。解除・計画・コスト・閾値は変更していない。
- `tests/test_endpoint_component.py`：指定された保存済み2例を必ず検査し、start_steep・解除0・全生マスクの保護をassertする。保存地図を固定した実際の非同期ランタイムで、待機中の停止、1秒後の1回の再試行、次の別地点への移行、有限の終了、経路を送らないこと、保存した解除マスクが全て空であることも検証する。
- 保存地図の読み取りを模擬するcaptureは、実際のcaptureと同様に `planner.observe` を呼び、保存データの配列をコピーして使用する。元の配列は不変であることを確認する。点群の時間順再生やGazebo走行ではない。
- 既存の急斜面のない合成地図では、膨らませた輪の連結成分によって探索と最新地図での受け渡しが成功するテストを継続した。禁止マスク・4近傍・再試行・古い経路の拒否も継続した。
- 旧再現JSONとの比較は、明示的に許可された2例の診断名だけをstart_steepに置き換えて照合する。数値・経路・解除数・その他の全フィールドの比較は維持する。元の参照JSON・既存の結果は変更しない。

論文へも「前提が誤っていたためテストを直した」と明記する必要がある。この作業の範囲は仕上げ1・2と報告であり、保護対象の `conference/paper/` は編集していない。
この定義は test の砂浜の失敗を見たあとで決めた、という従来の注記も維持する。

実行したコマンド（Pythonの全テストのみ。作業dirは `/workspace/thesis-028b`）：

```bash
git fetch origin realtime-map:refs/remotes/origin/realtime-map
git merge --no-edit -m '最新のrealtime-mapを取り込む' origin/realtime-map
cd conference
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-finish-mpl python3 -m tests.test_endpoint_component
python3 results/endpoint_policy/b/finish/run_tests.py
python3 results/endpoint_policy/b/finish/append_report.py --implementation-commit <上記ID>
```

全テストの環境は `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-finish-mpl XDG_CACHE_HOME=/tmp/thesis-finish-cache PYTHONUNBUFFERED=1`。
以下はstdoutとstderrの全文で、モジュールごとの実際の終了コードを併記する。

'''
    text += '```text\n'+(OUT/'all_tests_log.txt').read_text().rstrip()+'\n```\n\n'
    text += '```text\n'+summary+'```\n\n'
    text += '全'+str(len(tests))+'モジュールが成功した。merge後に変更した既存ソースは分類と対象テストの2ファイルのみ。その他の追跡対象ファイルは名前とSHA-256をまとめたダイジェストで照合し不変を確認した。\n\n'
    text += 'できなかったこと：Gazebo・研究PCでの物理的評価は指定どおり未実行。029との組合せの効果、実走の安全性・完走率は未評価であり、新しい数値は報告していない。\n\n'
    text += '今回の変更・追加ファイル（最新realtime-mapを取り込むmergeによるファイルは含めない）：\n\n'
    text += '\n'.join('- `'+name+'`' for name in names)+'\n'
    report_path.write_text(original+text)
    assert all(f.stat().st_size < 5_000_000 for f in OUT.rglob('*') if f.is_file())
    print('Report appended; all', len(tests), 'test modules passed; historical files preserved.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation-commit', required=True)
    main(parser.parse_args().implementation_commit)
