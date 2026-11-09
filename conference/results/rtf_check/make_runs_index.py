"""List every run saved under results/rtf_check with its conditions, order and time; read-only on runs."""
import csv, json
from pathlib import Path
root = Path(__file__).parent
NOTE = {('hayashi_first_gazebo_check', '08OB87_-0706'): 'no_path run on 08OB87_-0706',
        ('hayashi_first_gazebo_check', '08OB86_-0205'): 'one of the two runs behind the 14.8 m gap',
        ('hayashi_rtf1_check/rtf_0.3', '08OB86_-0205'): 'one of the two runs behind the 14.8 m gap'}
rows = []
def add(group, physical):
    try:
        m = json.loads((physical/'manifest.json').read_text())
    except OSError:
        return
    for c in m['cases']:
        if not c.get('selected') or not c.get('run_folder'):
            continue
        raw = physical/c['run_folder']
        f = sorted(raw.glob('follower/*'))
        conditions = physical.parent/'run_conditions.txt'
        text = conditions.read_text() if conditions.exists() else ''
        soft = 'software' if m.get('software_rendering', '1') == '1' else 'gpu'
        domain = '61' if 'ros_domain_id=61' in text else '50'
        rows.append(dict(group=group, patch=c['patch'], started=f[0].name[:15] if f else '', rendering=soft, real_time_factor=m.get('real_time_factor'),
                         stale_timeout_s=m.get('stale_timeout_s'), map_method=m.get('map_method'), ros_domain_id=domain,
                         termination=c.get('termination'), path=str(raw.relative_to(root)), note=NOTE.get((group, c['patch']), '')))
add('hayashi_first_gazebo_check', root/'hayashi_first_gazebo_check/physical_3')
for p in sorted((root/'hayashi_rtf1_check').glob('rtf_*')):
    add('hayashi_rtf1_check/'+p.name, p/'physical_1')
for p in sorted((root/'hayashi_rtf_repeat').glob('rtf_*')):
    add('hayashi_rtf_repeat/'+p.name, p/'physical_1')
for p in sorted((root/'divergence').glob('R[0-9]_[0-9][0-9]')):
    add('divergence/'+p.name, p/'physical_1')
rows.sort(key=lambda r: r['started'])
for i, r in enumerate(rows, 1):
    r['order'] = i
with (root/'runs_index.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, ['order', 'started', 'group', 'patch', 'rendering', 'real_time_factor', 'stale_timeout_s', 'map_method', 'ros_domain_id', 'termination', 'note', 'path'])
    w.writeheader(); w.writerows(rows)
print((root/'runs_index.csv').read_text())
