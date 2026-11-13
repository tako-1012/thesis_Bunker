"""Keep initial failures verbatim and record the separately executed input retry."""
import json
from pathlib import Path
OUT=Path(__file__).resolve().parent
root=OUT.parents[2]
initial=(OUT/'test_summary.txt').read_text().splitlines()
modules=sorted(p.stem for p in (root/'tests').glob('test_*.py'))
assert [row.split()[0] for row in initial]==modules
assert [row for row in initial if not row.endswith('exit=0')]==['test_lab_geometry exit=1']
retry=json.loads((OUT/'retry_metadata.json').read_text())
assert retry['exit_code']==0
assert 'all lab-geometry tests passed' in (OUT/'retry_test_lab_geometry_log.txt').read_text()
assert 'FileNotFoundError' in (OUT/'test_lab_geometry_log.txt').read_text()
(OUT/'final_test_summary.txt').write_text('\n'.join(
    'test_lab_geometry exit=0' if row=='test_lab_geometry exit=1' else row for row in initial)+'\n')
print('Final test modules:',len(modules),'failed: 0; initial missing-CSV error retained in all_tests_log.txt')
