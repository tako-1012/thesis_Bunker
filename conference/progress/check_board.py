"""進捗ボードが指示書・記録と食い違っていないかを確かめる（Claude Code の Stop フックから呼ぶ）。

調べること：
1. conference/tasks/NNN_*.md の指示書ごとに、tasks.csv に同じ番号の行がある。
2. 指示書の冒頭の「状態」の行に、tasks.csv のその行の状態の語（完了・実行中・未着手・保留・使わない・負の結果）が含まれている。
3. tasks.csv・outcomes.csv の中身が、最後にボードに上げたもの（board_synced.json の sha256）と同じ。
   ボードに上げたら `python3 conference/progress/check_board.py --mark-synced` で記録する。
食い違いがあれば内容を表示して終了コード 2（Stop フックでは、Claude が返答を終える前に直すよう求められる）。
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent/'tasks'
FILES = ('tasks.csv', 'outcomes.csv')
SYNCED = HERE/'board_synced.json'
STATUS_WORDS = ('未着手', '実行中', '完了', '保留', '使わない', '負の結果')


def digests():
    return {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in FILES}


def problems():
    found = []
    rows = {r['番号']: r for r in csv.DictReader((HERE/'tasks.csv').open(encoding='utf-8'))}
    for spec in sorted(TASKS.glob('[0-9][0-9][0-9]_*.md')):
        number = spec.name[:3]
        match = re.search(r'\*\*状態：(.*?)\*\*', spec.read_text(encoding='utf-8'))
        if number not in rows:
            found.append(f'指示書 {number} の行が tasks.csv にない（{spec.name}）')
            continue
        status = rows[number]['状態']
        if status not in STATUS_WORDS:
            found.append(f'tasks.csv の {number} の状態「{status}」が決めた語のどれでもない')
        elif match and status not in match.group(1):
            found.append(f'指示書 {number} の状態「{match.group(1)[:40]}」と tasks.csv の「{status}」が食い違う')
    synced = json.loads(SYNCED.read_text()) if SYNCED.exists() else {}
    for name, digest in digests().items():
        if synced.get(name) != digest:
            found.append(f'{name} がボードに上がっていない（上げたら --mark-synced で記録する）')
    return found


def main():
    if '--mark-synced' in sys.argv:
        SYNCED.write_text(json.dumps(digests(), indent=2, ensure_ascii=False)+'\n')
        print('board_synced.json を更新した')
        return 0
    found = problems()
    hook = {}
    if not sys.stdin.isatty():
        try:
            hook = json.loads(sys.stdin.read() or '{}')
        except ValueError:
            hook = {}
    if found and hook.get('stop_hook_active'):
        # Already blocked once in this stop: report but do not loop forever
        # (e.g. a session without access to the board must still be able to stop).
        print('進捗ボードがまだ食い違っている：'+' / '.join(found), file=sys.stderr)
        return 0
    if found:
        print('進捗ボードの更新が必要です（conference/progress/check_board.py）：', file=sys.stderr)
        for line in found:
            print(' - '+line, file=sys.stderr)
        print('tasks.csv・outcomes.csv を直し、ボード（https://claude.ai/artifact/T627sMmE9VFZQFwaamScrV）に上げて、'
              '--mark-synced で記録してから終えること。', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
