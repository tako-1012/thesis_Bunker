"""Read-only integrity checks for the completed Gazebo recordings and frozen actor."""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path,nargs='?',default=ROOT/'results/gazebo_compare/physical_run')
args=parser.parse_args();folder=args.folder.resolve()
manifest=json.loads((folder/'manifest.json').read_text())
assert len(manifest['cases'])==12 and not manifest['world_errors']
assert all(c.get('run_folder') for c in manifest['cases'])
assert not any(c.get('error') for c in manifest['cases'])
assert all(r['max_error_m']<=.1 for r in manifest['world_exports'].values())
frozen=json.loads((folder/'actor_source_sha256.json').read_text())['files']
assert all(hashlib.sha256((ROOT.parent/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
rows=[];raw_hashes={}
for case in manifest['cases']:
    record=folder/case['run_folder'];mission=json.loads((record/'mission.json').read_text())
    assert mission['status']!='running' and mission['data_source']=='gazebo'
    assert mission['patch']==case['patch'] and mission['planner']==case['planner']
    assert np.array_equal(mission['path'],np.asarray(case['path_cells'])*.5)
    with (record/'trajectory.csv').open() as stream:records=list(csv.DictReader(stream))
    data={k:np.asarray([float(row[k]) for row in records]) for k in ('t','x','y','z','roll','pitch','yaw','v','w')}
    assert len(records)>0 and all(np.isfinite(a).all() for a in data.values())
    assert (np.diff(data['t'])>=0).all()
    assert np.max(np.abs(data['v']))<=1+1e-12 and np.max(np.abs(data['w']))<=1+1e-12
    goal=np.asarray(case['goal'])*.5
    error=float(np.linalg.norm(np.array([data['x'][-1],data['y'][-1]])-goal))
    if mission['status']=='completed':assert error<=.3+1e-12
    summary=json.loads((folder/'report/runs'/case['patch']/case['planner'].replace('*','star')/'summary.json').read_text())
    assert summary['status']==mission['status'] and summary['data_source']=='gazebo'
    entry=dict(patch=case['patch'],planner=case['planner'],status=mission['status'],samples=len(records),goal_error_m=error,fallen_samples=summary['fallen_samples'],out_of_bounds_samples=summary['out_of_bounds_samples'])
    if mission['status']=='stuck':
        window=mission['controller']['stall_timeout_s']
        tail=np.flatnonzero(data['t']>=data['t'][-1]-window)
        i=tail[0]
        entry['stagnation_diagnostic']=dict(
            window_s=window,
            xy_net_displacement_m=float(np.hypot(data['x'][-1]-data['x'][i],data['y'][-1]-data['y'][i])),
            v_command_mean_m_s=float(data['v'][tail].mean()),
            w_command_abs_mean_rad_s=float(np.abs(data['w'][tail]).mean()),
            roll_abs_final_deg=float(abs(np.degrees(data['roll'][-1]))),
            pitch_abs_final_deg=float(abs(np.degrees(data['pitch'][-1]))))
    rows.append(entry)
    for p in [record/'mission.json',record/'trajectory.csv']:
        raw_hashes[str(p.relative_to(folder))]=hashlib.sha256(p.read_bytes()).hexdigest()
(folder/'raw_recordings_sha256.json').write_text(json.dumps(raw_hashes,indent=2)+'\n')
audit=dict(actor_source_files_checked=len(frozen),worlds=len(manifest['world_exports']),cases=len(rows),runs=rows)
(folder/'integrity_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(audit,ensure_ascii=False,indent=2))
print('Frozen source, real Gazebo provenance, terminal recordings, path identity, finite data, command limits and completed-goal distances passed.')
