"""Apply task020's explicitly permitted annotation; preserve all old numeric text."""
import csv,hashlib,io,json,re,subprocess,sys
from pathlib import Path
from textwrap import dedent


def main():
    REPO=Path(__file__).resolve().parents[2];ROOT=REPO/'conference'
    sys.path.insert(0,str(ROOT))
    from experiments.gz_compare_report import annotate_existing

    base='e511ee8acc83bac7451a300667479d6b5ed636ab'
    folder=ROOT/'results/gazebo_compare/physical_run'
    out=ROOT/'results/footprint_steep'
    def original(path):
        return subprocess.check_output(['git','show',base+':'+str(path.relative_to(REPO))],cwd=REPO).decode()
    def rows(text):return list(csv.DictReader(io.StringIO(text)))
    old=rows(original(folder/'report/runs.csv'))
    raw=json.loads((folder/'raw_recordings_sha256.json').read_text())
    assert len(raw)==24
    assert all(hashlib.sha256((folder/p).read_bytes()).hexdigest()==h for p,h in raw.items())
    annotate_existing(folder)
    new=rows((folder/'report/runs.csv').read_text())
    assert len(new)==len(old)==12
    checked=0
    for before,after in zip(old,new):
        assert (before['patch'],before['planner'])==(after['patch'],after['planner'])
        for key,value in before.items():
            if key=='status':continue
            assert after[key]==value,(before['patch'],before['planner'],key,value,after[key])
            checked+=1
        assert after['recorded_status']==before['status']
        assert after['status']==('rollover' if after['rolled_over']=='True' else before['status'])
    assert all(hashlib.sha256((folder/p).read_bytes()).hexdigest()==h for p,h in raw.items())
    events=[row for row in new if row['rolled_over']=='True']
    fields=['patch','planner','recorded_status','status','rolled_over','rollover_t_s','rollover_elapsed_s','rollover_x_m','rollover_y_m','roll_p95_actual_deg','roll_max_actual_deg','pitch_p95_actual_deg','pitch_max_actual_deg']
    with (out/'rollover_events.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in events)

    report=ROOT/'results/gazebo_compare/REPORT_ja.md'
    text=original(report)
    old_log=original(folder/'report/compare_log.txt').rstrip('\n')
    assert old_log in text
    text=text.replace(old_log,(folder/'report/compare_log.txt').read_text().rstrip('\n'))
    # Change prose and graph captions only; historical raw-status JSON/test logs stay exact.
    chunks=re.split(r'(```.*?```)',text,flags=re.S)
    replacements={
        ' / stuck：':' / rollover：',
        '停滞記録':'転倒記録（原記録ではstuck終了）',
        '同じ地形で両方法が停滞し':'同じ地形で両方法が転倒し',
        '停滞した記録':'転倒した記録',
        '停滞原因':'転倒原因',
        'A*: stuck':'A*: rollover（原記録stuck）',
        'TA*-S: stuck':'TA*-S: rollover（原記録stuck）',
    }
    for i,chunk in enumerate(chunks):
        if chunk.startswith('```'):continue
        for before,after in replacements.items():chunk=chunk.replace(before,after)
        chunks[i]=chunk
    text=''.join(chunks)
    title,rest=text.split('\n',1)
    note='''

    ## 指示書020による転倒判定の追記

    集計に `rolled_over` を追加した。走行中のどこかで絶対rollが90度を超えた走行は、集計の `status` を `rollover` とする。
    `recorded_status` には元の終了状態を保持する。最初に閾値を超えた記録のシミュレーション時刻・開始からの経過秒・地図上のx,y位置も追加した。
    この判定で `08OB88_-0167` の両方法が転倒に該当した。原missionの終了状態は両方 `stuck` のままである。

    変更した既存結果は、この報告書、`physical_run/report/runs.csv`（転倒の列と派生status）、
    `physical_run/report/compare_log.txt`（同じ列を表示する表）の3ファイルだけ。
    既存の数値はCSVの文字列表現を含めて維持し、原mission・軌跡、地図、図、走行別数値、対の差の数値は変更していない。
    以下に残している当時の整合性監査JSONの `stuck` は原記録の終了状態であり、集計の `rollover` と区別して読む。
    再分類の監査は `../footprint_steep/rollover_annotation_audit.json`、新しい対策の検証は `../footprint_steep/REPORT_ja.md` に記載する。
    '''
    report.write_text(title+dedent(note)+rest)
    audit=dict(original_rows=len(old),original_cells_preserved=checked,raw_files_preserved=len(raw),
               rollover_runs=len(events),changed_old_result_files=[str(p.relative_to(ROOT)) for p in [report,folder/'report/runs.csv',folder/'report/compare_log.txt']],
               reason='Add strict >90-degree rollover classification and first recorded event; preserve all original numeric strings and raw statuses.')
    (out/'rollover_annotation_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(audit,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
