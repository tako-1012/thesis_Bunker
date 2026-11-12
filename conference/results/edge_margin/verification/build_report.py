"""Build the Japanese report/PR from saved planner, test and report outputs."""

import hashlib
import json
from pathlib import Path
import subprocess
import pandas as pd

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = OUT.parents[1]
REPO = ROOT.parent


def block(path, language='text'):
    return '```'+language+'\n'+path.read_text().rstrip('\n')+'\n```\n\n'


def main():
    protocol = json.loads((VERIFY/'protocol.json').read_text())
    for name, checksum in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == checksum, name
    original = json.loads((VERIFY/'baseline_sha256.json').read_text())
    changed = [name for name, checksum in original.items() if hashlib.sha256((REPO/name).read_bytes()).hexdigest() != checksum]
    assert changed == ['conference/ros2_jazzy/gz_checks/lidar_checks.py',
                       'conference/ros2_jazzy/gz_checks/online_batch_checks.py', 'conference/tapp/tour.py'], changed
    summary = (VERIFY/'test_summary.txt').read_text().splitlines()
    assert len(summary) == len(list((ROOT/'tests').glob('test_*.py')))
    assert all(line.endswith('exit=0') for line in summary)
    final_edge = (VERIFY/'edge_after_exclusion_log.txt').read_text()
    assert 'all edge-margin tests passed' in final_edge and 'Traceback' not in final_edge
    runs = pd.read_csv(OUT/'runs.csv', float_precision='round_trip')
    assert len(runs) == 40
    assert runs[runs.record_origin.eq('rerun')].completed.isna().all()
    assert runs[runs.record_origin.eq('rerun')].data_source.isna().all()
    assert not any('energy' in c.lower() for c in runs.columns)
    manifest = json.loads((OUT/'manifest.json').read_text())
    audit = manifest['waypoint_audit']
    changed_names = [a['patch'] for a in audit if a['points_changed']]
    unchanged_names = [a['patch'] for a in audit if not a['points_changed']]
    status = f"最新realtime-map（`{protocol['base']}`）から `codex/024-edge-margin` を作成した。023（1f61d0a）とClaudeによる023の実走結果が土台に含まれる。マージはしていない。基準日は{protocol['client_date']}（日本時間）。\n\n"
    status += '**新地点でのGazebo実走は未実行**。通常Dockerのイメージ `thesis/jazzy-gz:1` がなく、ラッパーはexit=125で終了した。既存の実測と未実行の欄を分けて保存した。\n\n'
    implementation = '''- `tapp/tour.py`：`sample_waypoints(..., edge_margin_m=0.0)`。同じ候補の順列のまま、端からの距離が指定値未満の候補だけを除く。既定/明示0では元の12点のJSONバイトと一致する。距離・到達可能性の条件と他の関数は変更していない。
- `ros2_jazzy/gz_checks/edge_margin_checks.py`：`edge_distance_m`、`archived_metadata`、`build_cohort`、`prepare_cases`、`run_checks`。旧/新地点、開始点、巡回順、対象外、再利用の判断を保存し、変更した地点だけを4方式で走らせる。
- `run_edge_margin_checks.sh`：通常Dockerでソースを読み取り専用にし、一時領域でbuild/worldを作る。既存のmanifestがある保存先は拒否する。
- `online_batch_checks.py` と `lidar_checks.py`：既定動作を維持するキーワード引数だけを追加した。前者は渡された部分集合、後者は渡された地点と選択した砂浜を使える。新しい親集計を使う場合だけ旧集計を省略する。LiDARの新しい比較ではcoarse/fineとも022の実走の標高を使う。
- `experiments/edge_margin_report.py`：`cached_row`、`load_maps`、`summary_tables`、`summarize`。再利用値をそのまま保持し、新しい記録を同じ指標で解析して40行へまとめる。両方が完走した同じ砂浜だけで6通りの対比較の差の中央値を計算する。新規の実走記録がある砂浜だけ軌跡図を作る。
- `tests/test_edge_margin.py`：既定のバイト一致、全10か所の12点、開始点の対象外、再利用metadataの完全一致、新しいアダプター、混合記録の集計、対象の振り分け、Docker引数を検証する。偽の記録は一時領域の単体テストだけで使う。
'''
    method = '''**10mは指示書で事前に固定された値**で、仮想センサーの半径R=10mと同じ。testの走行結果で選んだり調整したりしていない。0を試すのは既定値の互換性を確かめるテストだけである。

距離は地図の外側のセル中心 `0..(shape-1)*0.5m` を基準とした。400×400では0〜199.5m。この定義が指示書の参考値と一致する。
Gazeboのheightmap外周は−0.25〜199.75mであり、これより0.25m内側の基準である。10mちょうどを許可する。開始点が10m未満なら、ずらさず対象外にする。

`SeedSequence([0,3000,200,patch_index])` と同じ通行可能セルの順列を使い、12点を引いて最初の5点を使う。
地点と開始点の距離条件だけを追加し、5mの相互間隔・到達可能性、巡回順の計算、TA*-S＋膨張0.5m、コスト・探索の式を変えない。
再利用かどうかは地点だけで決め、以前の走行の成功/失敗で選んでいない。

新しい4方式のworldは022の実走時の標高配列を共用し、元のデータ・障害物・通行不能マスクを照合する。
固定/仮想R10は021のheightmapの見た目・速さ1倍、LiDARの2方式は022/023のメッシュの見た目・速さ0.3倍・途切れ期限1.0秒。
`manifest.json` に記録し、LiDARの異なる速さ・期限を拒否する。LiDARの仕様・高さ・雑音・判定の仮定は変更していない。
'''
    commands = '''```bash
cd conference
python3 -m tests.test_planners
# 変更前に全10か所の従来の12点と、そのJSONバイトを保存
python3 ros2_jazzy/gz_checks/edge_margin_checks.py --prepare-only --output results/edge_margin
python3 -m tests.test_edge_margin
bash ros2_jazzy/gz_checks/run_edge_margin_checks.sh results/edge_margin/physical_run
python3 experiments/edge_margin_report.py
python3 results/edge_margin/verification/run_tests.py
python3 results/edge_margin/verification/build_report.py
```

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-024-mpl XDG_CACHE_HOME=/tmp/thesis-024-cache` を指定した。
`py_compile` と `bash -n` も成功した。保存済みの集計は再生成していない。

'''
    tests = '変更前のプランナー：\n\n'+block(VERIFY/'planners_before_log.txt')
    tests += '全テストの出力全文：\n\n'+block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    tests += '対象外の開始点では抽選前に除外する追加修正後、新規モジュールを再実行した最終の出力全文。その他の実装・既存テストは全体実行中に変更していない。\n\n'+block(VERIFY/'edge_after_exclusion_log.txt')
    tables = block(OUT/'edge_margin_log.txt')
    limits = '''新地点で転倒が消えたかは**未判定**。現在の件数と中央値は各方式の再利用5走行だけで、残り5走行は未実行である。
表の転倒0を、10か所すべての結果と解釈しない。未実行の完走・接触・計画/地図更新時間は0で埋めない。
再実走の軌跡がまだないため、新しい軌跡図もない。実走後に集計すれば作成される。

端の制約は地点と開始点だけで、経路全体を10m内側に制約していない。内側の地点でも経路が端へ向かう可能性はあり、転倒を防げると保証していない。
接触指標は記録された中心軌跡による。車体全体の接触を見落とす限界は従来と同じ。
地形の箱の高さ、急斜面の推定、点群の届くタイミング、以前の経路なしの原因は今回変更していない。

ClaudeにはREADMEのコマンドで変更した5か所を4方式で実走し、地点・順序・開始位置・world入力・LiDAR設定を確認してほしい。
転倒が残った場合は、軌跡と姿勢の生ログから位置・時刻・端との距離を調べてほしい。現在は原因を推測で埋めていない。
10か所なので検定はしない。エネルギーは集計しない。対比較は両方が5地点と帰還を完了した記録だけで、指標ごとの組数も表示する。
'''
    result = '# 指示書024：端から10m以上の地点での比較\n\n'+status
    result += '## 実装したもの\n\n'+implementation+'\n## 方法と固定した条件\n\n'+method+'\n'
    result += '## 地点の変更と再利用\n\n'
    result += '変更した砂浜：'+', '.join('`'+n+'`' for n in changed_names)+'。\n\n'
    result += '地点・順序・初期経路が完全一致し、記録を再利用する砂浜：'+', '.join('`'+n+'`' for n in unchanged_names)+'。\n\n'
    result += '開始点は全10か所で条件を満たし、今回の対象外はない。各地点と新旧の端距離は下の表と `waypoints.csv` に示す。\n\n'
    result += '## 実行したコマンド\n\n'+commands+'Dockerの実際の出力（exit=125）：\n\n'+block(VERIFY/'docker_launcher_log.txt')
    result += '## テスト出力の全文\n\n'+tests
    result += '最終の全テストの前に実行した新規テストの出力：\n\n'+block(VERIFY/'edge_final_log.txt')
    result += '新規テストの初回は、合成地図用の `TraversabilityMap` にrock引数を渡していなかったため失敗した。テストの地図の作り方を直し、期待値や既存テストは変えていない。初回の全文も保存する。\n\n'+block(VERIFY/'edge_initial_log.txt')
    result += '## 集計表（スクリプトが表示した全文をそのまま）\n\n'+tables
    result += '## 既存ファイルの保持と実行環境\n\n'
    result += '既存の変更は、指示書が許可した地点選択と、既定動作を維持する2つのROS用アダプターの3ファイルに限定した。その他の元のファイルはSHA-256で照合した。021〜023の結果、地図、world、データと既存テストは変更していない。\n\n'
    result += block(VERIFY/'preservation_audit.json','json')+block(VERIFY/'protocol.json','json')
    result += '## できなかったこと・Claudeに確認してほしいこと\n\n'+limits+'\n'
    result += '実走方法と保存先は [README_ja.md](README_ja.md) に記載した。\n\n'
    if (OUT/'SUBMISSION_ja.md').exists():
        result += '## 提出状態\n\n'+(OUT/'SUBMISSION_ja.md').read_text()+'\n'
    names = subprocess.check_output(['git','diff','--name-only',protocol['base'],'--','conference'],cwd=REPO,text=True).splitlines()
    names += subprocess.check_output(['git','ls-files','--others','--exclude-standard','conference'],cwd=REPO,text=True).splitlines()
    names += ['conference/results/edge_margin/REPORT_ja.md','conference/results/edge_margin/PR_DESCRIPTION_ja.md','conference/results/edge_margin/changed_files.txt']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    result += '## 変更ファイル一覧\n\n'+'\n'.join('- `'+n+'`' for n in names)+'\n'
    (OUT/'REPORT_ja.md').write_text(result)
    pr = '地図の切れ目に近い地点の影響を調べるため、地点選択へ事前固定の10m条件を加える。既定値0では従来の地点を保持し、変更しない5か所は元の記録を再利用する。\n\n'+status
    pr += '## 実装\n\n'+implementation+'\n## 条件と距離の定義\n\n'+method+'\n'
    pr += '## コマンドとテスト出力全文\n\n'+commands+tests
    pr += '## 集計表（そのまま）\n\n'+tables+'## 未実行・限界\n\n'+limits+'\n'
    pr += '変更一覧・保存元・実行環境の詳細は [REPORT_ja.md](https://github.com/tako-1012/thesis_Bunker/blob/codex/024-edge-margin/conference/results/edge_margin/REPORT_ja.md)。\n'
    (OUT/'PR_DESCRIPTION_ja.md').write_text(pr)
    print(OUT/'REPORT_ja.md')
    print('all test modules:',len(summary),'PR body characters:',len(pr))


if __name__ == '__main__':
    main()
