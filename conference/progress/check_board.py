"""進捗ボードが指示書・記録と食い違っていないかを確かめる（Claude Code の Stop フックから呼ぶ）。

調べること：
1. conference/tasks/NNN_*.md の指示書ごとに、tasks.csv に同じ番号の行がある。
2. 指示書の冒頭の「状態」の行に、tasks.csv のその行の状態の語（完了・実行中・未着手・保留・使わない・負の結果）が含まれている。
3. tasks.csv・outcomes.csv・policy.csv の中身が、最後にボードに上げたもの（board_synced.json の sha256）と同じ。
   ボードは Dashboard 型で、ページは保管場所の datasets/* が指すファイルを読む。上げ方：
   (a) CSV を Artifact の asset: true で上げる（結果に sha256 と /_blob/<id> が出る）、
   (b) ArtifactData で datasets/<名前> の source.url をその /_blob/<id> に書き換える、
   (c) 変わったファイルごとに、上げたときの sha256 と /_blob を渡して記録する：
       python3 conference/progress/check_board.py --mark-synced tasks.csv=<sha256>@/_blob/<id> ...
   渡した sha256 が手元のファイルと違う・変わったファイルの分が渡されていない場合は記録しない
   （2026-11-23、上げたつもりでページに反映されていなかったことへの対策）。
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
FILES = ('tasks.csv', 'outcomes.csv', 'policy.csv')
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
        entry = synced.get(name)
        if (entry.get('sha256') if isinstance(entry, dict) else entry) != digest:
            found.append(f'{name} がボードに上がっていない（上げたら --mark-synced で記録する）')
    return found


def mark_synced(args):
    synced = json.loads(SYNCED.read_text()) if SYNCED.exists() else {}
    given = {}
    for arg in args:
        name, _, rest = arg.partition('=')
        sha, _, blob = rest.partition('@')
        if name not in FILES or not re.fullmatch(r'[0-9a-f]{64}', sha) or not re.fullmatch(r'/_blob/[0-9a-f]{32}', blob):
            print(f'形が違う：{arg}（例 tasks.csv=<sha256>@/_blob/<id>）', file=sys.stderr)
            return 1
        given[name] = dict(sha256=sha, blob=blob)
    errors = []
    for name, digest in digests().items():
        entry = synced.get(name)
        old = entry.get('sha256') if isinstance(entry, dict) else entry
        if name in given:
            if given[name]['sha256'] != digest:
                errors.append(f'{name}：渡した sha256 が手元のファイルと違う（上げ直す）')
            else:
                synced[name] = given[name]
        elif old != digest:
            errors.append(f'{name}：変わっているのに、上げた記録（sha256@/_blob）が渡されていない')
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        print('記録しなかった。datasets/* の source.url を上げたファイルに書き換えたかも確かめること。', file=sys.stderr)
        return 1
    SYNCED.write_text(json.dumps(synced, indent=2, ensure_ascii=False)+'\n')
    print('board_synced.json を更新した（datasets/* の source.url が同じ /_blob を指していること）')
    return 0


def main():
    if '--mark-synced' in sys.argv:
        return mark_synced(sys.argv[sys.argv.index('--mark-synced')+1:])
    found = problems()
    hook = {}
    # The Stop hook passes JSON on stdin and closes it. A manual run from a
    # non-interactive shell may leave stdin open, so never wait for it.
    import select
    if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 1.)[0]:
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
