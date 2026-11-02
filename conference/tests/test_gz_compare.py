"""ROS-free scenario parity and clearly labelled kinematic recording/report fixtures."""

import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
from scipy.ndimage import map_coordinates
from ros2_jazzy.gz_checks.compare_checks import scenario_cases,prepare_cases
from experiments.gz_compare_report import summarize,MEASURES
from experiments.gz_run_report import analyze_run
from tapp.config import RESOLUTION
from tapp.mapfile import load_map_file
from tapp.real_beach import build_real,list_patches
from tapp.exact_planners import run_planner_exact
from tapp.robot_sim import simulate
from tapp.run_log import RunLog


def test_scenarios():
    cases=scenario_cases()
    expected=list_patches("test",dataset="shizuoka_beach_las")[:6]
    assert [(c["patch"],c["planner"]) for c in cases]==[(r["name"],p) for r in expected for p in ("A*","TA*-S")]
    for row in expected:
        sc=build_real(row["name"],200,0,dataset="shizuoka_beach_las")
        for case in [c for c in cases if c["patch"]==row["name"]]:
            direct=run_planner_exact(case["planner"],sc)
            assert case["start"]==list(sc["start"]) and case["goal"]==list(sc["goal"])
            assert np.array_equal(case["path_cells"],direct["path"])
    print("comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls",flush=True)
    return cases


def test_report(cases):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);manifest=prepare_cases(root,cases=cases)
        raw_hashes={}
        for case in manifest["cases"]:
            sc=load_map_file(root/case["map_file"]);tm=sc["tmap"]
            path=np.asarray(case["path_cells"])*RESOLUTION
            simulation=simulate(sc,path,[*path[0],0.0])
            trace=np.asarray(simulation["trajectory"])
            t,x,y,yaw=trace.T
            coords=np.array([x,y])/RESOLUTION
            z=map_coordinates(tm.elev,coords,order=1,mode="nearest")
            gx=map_coordinates(tm.gx,coords,order=1,mode="nearest");gy=map_coordinates(tm.gy,coords,order=1,mode="nearest")
            roll=np.arctan(-gx*np.sin(yaw)+gy*np.cos(yaw));pitch=np.arctan(gx*np.cos(yaw)+gy*np.sin(yaw))
            v=np.hypot(np.gradient(x,t),np.gradient(y,t));w=np.gradient(np.unwrap(yaw),t)
            mission=dict(map_id="file/"+Path(case["map_file"]).name,map_file=str(root/case["map_file"]),
                         data_source="kinematic_test_fixture",path=path.tolist(),lookahead_m=1.0)
            log=RunLog(mission,root/"raw")
            for values in zip(t,x,y,z,roll,pitch,yaw,v,w):
                log.write(dict(zip(("t","x","y","z","roll","pitch","yaw","v","w"),map(float,values))))
            log.close("completed" if simulation["completed"] else "time_limit_fixture")
            case["run_folder"]=str(log.folder.relative_to(root))
            raw_hashes[str(log.folder/"mission.json")]=hashlib.sha256((log.folder/"mission.json").read_bytes()).hexdigest()
        (root/"manifest.json").write_text(json.dumps(manifest)+"\n")
        # Suppress fixture measurement tables: these are never published as Gazebo data.
        from contextlib import redirect_stdout
        import io
        with redirect_stdout(io.StringIO()):data,paired=summarize(root)
        assert len(data)==12 and set(data.data_source)=={"kinematic_test_fixture"}
        for case in manifest["cases"]:
            with redirect_stdout(io.StringIO()):
                direct=analyze_run(root/case["run_folder"],root/"direct"/case["patch"]/case["planner"].replace("*","star"))
            row=data[(data.patch==case["patch"])&(data.planner==case["planner"])].iloc[0]
            for key in ["elapsed_s","deviation_mean_m","deviation_max_m","path_lethal_cells","roll_p95_actual_deg","pitch_p95_actual_deg"]:
                assert row[key]==direct[key],(case["patch"],case["planner"],key)
            import pandas as pd
            from tapp.metrics import evaluate
            trace=pd.read_csv(root/case["run_folder"]/"trajectory.csv")
            assert row.roll_max_actual_deg==np.max(np.abs(np.degrees(trace.roll)))
            assert row.pitch_max_actual_deg==np.max(np.abs(np.degrees(trace.pitch)))
            assert row.climb_actual_m==np.maximum(np.diff(trace.z),0).sum()
            planned=evaluate(np.asarray(case["path_cells"]),load_map_file(root/case["map_file"])["tmap"])
            for key in case["map_metrics"]:
                assert row["map_"+key]==planned[key]
            assert (root/"report"/(case["patch"]+".png")).is_file()
        for metric in MEASURES:
            pivot=data.pivot(index="patch",columns="planner",values=metric)
            completed=data.pivot(index="patch",columns="planner",values="completed").all(axis=1)
            difference=(pivot.loc[completed,"TA*-S"]-pivot.loc[completed,"A*"]).median()
            actual=paired.loc[paired.metric==metric,"delta_median"].iloc[0]
            assert actual==difference or (np.isnan(actual) and np.isnan(difference))
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in raw_hashes.items())
        for path in root.rglob("*"):
            if path.suffix in (".json",".csv",".txt"):assert "energy" not in path.read_text().lower(),path
        # No physical recording must never turn into fabricated zero measurements.
        for case in manifest["cases"]:case["run_folder"]=None
        (root/"manifest.json").write_text(json.dumps(manifest)+"\n")
        with redirect_stdout(io.StringIO()):missing,effects=summarize(root,root/"missing")
        assert set(missing.status)=={"未実行"}
        assert missing[MEASURES].isna().all().all()
        assert (effects.paired_completed==0).all() and effects.delta_median.isna().all()
    print("comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed",flush=True)
    print("fixture values are simulated test data, not Gazebo measurements",flush=True)


def test_failed_preparation(cases):
    """A failed exporter must retain all comparisons without physical numbers."""
    from contextlib import redirect_stdout
    import io
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        with patch('ros2_jazzy.gz_checks.compare_checks.export_gazebo',
                   side_effect=ValueError('intentional unavailable-world fixture')) as export:
            manifest=prepare_cases(root,root/'worlds',cases=cases)
        assert export.call_count==6
        assert len(manifest['cases'])==12 and len(manifest['world_errors'])==6
        assert not manifest['world_exports']
        assert all(c['run_folder'] is None and c['error'].startswith('world export failed:') for c in manifest['cases'])
        (root/'manifest.json').write_text(json.dumps(manifest)+'\n')
        with redirect_stdout(io.StringIO()):data,effects=summarize(root)
        assert set(data.status)=={'実行失敗'}
        assert data[MEASURES].isna().all().all()
        assert (effects.paired_completed==0).all() and effects.delta_median.isna().all()
    print('unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements',flush=True)


if __name__=="__main__":
    cases=test_scenarios()
    test_failed_preparation(cases)
    test_report(cases)
    print("all Gazebo comparison tests passed (ROS2/Gazebo not required)",flush=True)
