"""Verify immutable originals and build the Japanese task031 report from logs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import pandas as pd

VERIFY=Path(__file__).resolve().parent
OUT=VERIFY.parent
ROOT=VERIFY.parents[2]
REPO=ROOT.parent

def git(*args):
    return subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()

def block(path,lang='text'):
    return '```'+lang+'\n'+path.read_text().rstrip('\n')+'\n```\n\n'

def main(commit):
    commit=git('rev-parse',commit+'^{commit}')
    p=json.loads((VERIFY/'protocol.json').read_text())
    for name,h in p['source_sha256'].items():
        data=(REPO/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==h
        assert subprocess.check_output(['git','show',commit+':'+name],cwd=REPO)==data
    digest=hashlib.sha256()
    names=git('ls-tree','-r','--name-only',p['base'],'conference').splitlines()
    for name in names:
        digest.update(name.encode()+b'\0'+hashlib.sha256((REPO/name).read_bytes()).digest())
    assert len(names)==p['original_count'] and digest.hexdigest()==p['original_sha256']
    assert all(line.startswith('A\t') for line in git('diff','--name-status',p['base'],'--','conference').splitlines())
    sources=json.loads((OUT/'sources/provenance.json').read_text())
    for source in sources['files']:
        assert hashlib.sha256((OUT/'sources'/Path(source['file']).name).read_bytes()).hexdigest()==source['sha256']
    tests=sorted((ROOT/'tests').glob('test_*.py'))
    assert (VERIFY/'test_summary.txt').read_text().splitlines()==[t.stem+' exit=0' for t in tests]
    assert (VERIFY/'all_tests_log.txt').read_text()=='\n'.join((VERIFY/(t.stem+'_log.txt')).read_text() for t in tests)
    data=pd.read_csv(OUT/'runs.csv');parity=pd.read_csv(OUT/'parity.csv');stats=pd.read_csv(OUT/'tests.csv')
    assert len(data)==768 and data.success.all() and parity.matched.all() and parity.absolute_difference.max()==0
    assert stats.n_beaches.eq(48).all() and stats.excluded_beaches.eq(0).all()
    assert not any('energy' in c.lower() for c in data.columns)
    assert all((OUT/(rule+'.'+ext)).exists() for rule in ('rule_first','rule_max') for ext in ('png','pdf'))
    (OUT/'implementation_commit.txt').write_text(commit+'\n')
    audit=dict(original_files=len(names),unchanged_original_files=len(names),original_sha256=digest.hexdigest(),
               new_files_only=True,parity_fields=len(parity),max_absolute_difference=float(parity.absolute_difference.max()))
    (VERIFY/'preservation_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    report='# 指示書031：研究室GeometryLayer＋NavFnコストのPython比較\n\n'
    report+='ブランチ：`codex/031-lab-baseline`。土台：`'+p['base']+'`。実装・実行ログのコミット：`'+commit+'`。この報告は後続の文書コミットに保存する。マージせずpushまで。\n\n'
    report+='192シナリオ×4方式を実行し、全768経路で解が得られた。A*とTA*-S exactの013との照合は'+str(len(parity))+'フィールドすべて一致し、最大絶対差は0だった（時間・エネルギーを除く）。Pythonの全'+str(len(tests))+'テストモジュールが成功した。\n\n'
    report+='''## 1. 実装・実行・検証

- `tapp/lab_geometry.py`：`geometry_layer_cost`、`navfn_cell_cost`、`obstacle_mask`、`plan_lab`。8方向の高低差/距離の平均、3以下の近傍で不明、1.41と57.3、指定の段階値を固定した。研究室の非公開リポジトリにはアクセスしておらず、指示書031の転記に従った。
- `experiments/lab_baseline.py`：48か所×100/200m×漂着物なし/ありの全シナリオを再生成し、A*・TA*-S exact・lab_geometry・lab_geometry+0.35mを実行する。A*/TA*は既存関数をそのまま呼び、全非エネルギー経路指標・シナリオのシードと切出しを既存offline.csvに照合する。
- `tests/test_lab_geometry.py`：平面の独立した近傍計算、全コスト段階、不明値、NavFnの既知値変換、独立Dijkstraの最適コスト、障害物と開始点の拒否、013との照合を検証した。既存テストは変更していない。
- `README_ja.md`：式、グラフの定義、格子と後処理の違い、障害物の定義、検定ファミリー、ライセンスを記した。
- `sources/`：参照したNav2のソース全文・版・URL・SHA-256を保存した。

**既存ファイルは1つも変更していない。パラメータは調整していない。エネルギーは出力・集計しない。Gazeboは起動していない。**

実行コマンド（作業dirは `/workspace/thesis-031/conference`）：

```bash
python3 -m venv --system-site-packages /workspace/venvs/thesis-031
/workspace/venvs/thesis-031/bin/python -m tests.test_planners
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-031-mpl XDG_CACHE_HOME=/tmp/thesis-031-cache /workspace/venvs/thesis-031/bin/python -m tests.test_lab_geometry
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-031-mpl XDG_CACHE_HOME=/tmp/thesis-031-cache /workspace/venvs/thesis-031/bin/python experiments/lab_baseline.py --workers 3
/workspace/venvs/thesis-031/bin/python results/lab_baseline/verification/run_tests.py
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-031-mpl /workspace/venvs/thesis-031/bin/python results/lab_baseline/verification/diagnostics.py
```

専用venvから既存のインストール済みパッケージを参照した。環境は下記に保存した。
全テストのランナーは同じvenv、OPENBLAS_NUM_THREADS=1、/tmpのMatplotlib/cacheを使用する。
テスト中に図や表を再生成する既存コードも、一時領域を使っている。既存の結果の不変性は全追跡ファイルのダイジェストで確認した。

### テスト出力全文

'''
    report+=block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    report+='## 2. NavFnの式の出どころ\n\n'
    report+='''Nav2 `ros-navigation/navigation2` の **jazzyブランチ、パッケージ版1.3.14**、コミット `94d1c2a345dda6ff637e6a72c9101d927ee99f19` を取得した。版は保存したpackage.xml、定数はnavfn.hppで確認した。

- [nav2_navfn_planner/src/navfn.cpp：NavFn::setCostmap、247行目以降](https://github.com/ros-navigation/navigation2/blob/94d1c2a345dda6ff637e6a72c9101d927ee99f19/nav2_navfn_planner/src/navfn.cpp#L247)
- [nav2_navfn_planner/include/nav2_navfn_planner/navfn.hpp：定数、52行目以降](https://github.com/ros-navigation/navigation2/blob/94d1c2a345dda6ff637e6a72c9101d927ee99f19/nav2_navfn_planner/include/nav2_navfn_planner/navfn.hpp#L52)
- 同cppの `NavFn::setupNavFn(true)`、342行目以降の外周処理も適用した。
- 同じ版の `navfn_planner.cpp`、254行目でROSマップをtrueとして渡し、allow_unknown設定を使う呼出しも確認した。同ファイルもsourcesに保存した。

`isROS=true, allow_unknown=true` のとき、入力0〜252は `int(50 + 0.8*c)`、254以上になる場合は253へ制限。入力253/254は内部254で通行不可。不明の入力255は内部253で通行可能・高コストである。
入力の253と変換後の253の意味は異なる。外側1セルはsetupNavFnと同様に内部254にする。
GeometryLayerの0.1/0.2/0.5/0.8×254は、Nav2のunsigned char境界で25/50/127/203に切り捨てた。非公開のGeometryLayer自体の丸めの実装までは確認できないため、この仮定は明示する。

グラフは8近傍、辺コストは両端セルコストの平均×移動距離、角抜け禁止。Pythonの既存A*を使う。通行コストが50以上なのでEuclidのhは許容的で、このグラフのDijkstraと同じ最適解になることを独立Dijkstraのテストで確かめた。
NavFnのポテンシャル伝播・勾配追跡を再現したものではない。

以下は、仕様の物理角度の平面をコードで計算した監査である。平均8方向の勾配は平面の最大勾配より小さくなり、例えば物理30度でもこの式の角度は25度を超えない。係数を補正していない。

'''
    report+=block(VERIFY/'diagnostics_log.txt')
    report+='## 3. 集計・検定・図\n\n'
    report+='''中立な指標を先に表示する。steep_lenは013と同じ0.1mサンプリングによる25度超の距離、obstacle_cellsは共通の生の障害物に交差したセル数。
max_pitchは013の1m窓、max_pitch_dir/p95_pitch_dirは進行方向の勾配から算出した最大/95%値。
**mean_costとJは私たちの目的関数なので私たちに有利であり、中立な評価ではない。**
計画時間は今回のPython実装の再測定値。旧CSVの時間と一致させたり、C++の実NavFnの時間と解釈したりしない。
記述表の中央値は013と同じく100/200mを含む各条件96ケースについての値。検定表の中央値・対の差は、サイズを平均した48砂浜についての値なので、記述表の中央値の差とは一致しないことがある。

検定は、100/200mを砂浜内で平均した48か所を単位とする両側Wilcoxon＋Holm。013のCSVの各サイズを独立な砂浜として数えない。
事前のHolmファミリーはTA*-S exactを基準とした3対比×漂着物2条件×全14指標（時間を含む）の84検定。失敗があれば両サイズ・両手法が成功した砂浜だけを使い、除外数を表示する。今回の各検定は48か所すべてを含んだ。
ゼロ差の除外・rank-biserial効果量は既存paired_testと同じ。急斜面距離の中央値0だけで安全性を判断せず、steep_runsの件数も示した。

表示された表の全文：

'''
    report+=block(OUT/'lab_baseline_log.txt')
    report+='''同じ規則で選んだ図（labの結果で選択を変えない）：

![規則1：最初の該当砂浜](rule_first.png)

![規則2：既存A*の急斜面距離が最大の砂浜](rule_max.png)

[規則1 PDF](rule_first.pdf) / [規則2 PDF](rule_max.pdf)。選択名はfigure_selection.jsonに保存した。背景は共通の傾斜（25度で色を飽和）、黒線は生の障害物境界、丸が始点・星が終点。

## 4. 研究室の実際の方法との違い

- **格子と高さ**：研究室は0.2mで点の高さの平均。今回は013の0.5m DEMをそのまま使用し、点の集約をやり直していない。既存の欠損補間と水・データなしの障害物マスクを継承するため、実機の不明セルの分布も再現していない。
- **NavFn**：setCostmapの変換・外周はソースどおりだが、実装は8近傍の最短経路グラフ。実NavFnの4方向のポテンシャル更新と勾配追跡の後処理は省略した。ROSノードのclearRobotCellによる始点のFREE_SPACE化も再現せず、共通の障害物から始点を免除しない。NavFn全体との経路一致を主張しない。
- **障害物**：全手法が共通の生の漂着物・水・データなしを除外する。lab通常版は膨張なし、参考版は0.35mの円と閉じたセル正方形との距離による1回の膨張。013のA*/TA*は既存の0.5m膨張を維持し、照合のため変更していない。0.5m格子では膨張の定義・離散化の影響がある。
- **指標**：013のlethal_cellsは私たちの急斜面も含む照合用の値で、中立なobstacle_cellsとは分ける。身体の姿勢・接触の実測ではなくDEM上の中心経路の評価である。
- **平滑化と時間**：TA*-Sの平滑化とグラフの方向制限も姿勢指標に影響するため、差をGeometryLayerのコストだけの効果と断言しない。時間は並列3ワーカーのPython測定で、実Nav2の速度比較ではない。

## 5. できなかったこと・自信がないこと

研究室の非公開コード・設定・実機での同一性は検証できていない。今回は指示書の転記した数式の再現と、許可されたNavFnコストのグラフ近似である。
丸め方・欠損点の扱い・実NavFnの勾配経路の影響は研究室側で確認が必要。実機・Gazeboの完走・転倒・安全性への結論は出していない。
パラメータ調整・エネルギー集計・既存結果の変更はしていない。私たちの指標の有利さと中立指標を分けて、研究室の手法の実装と等価だと過大に解釈しないようにする。

データ出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB Ground。
https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb （CC BY 4.0 / ODbL）。本比較と図は、その加工済みの既存shizuoka_beach_lasを使用した。

### 実行環境・原本の保全

'''
    report+=block(VERIFY/'environment.json','json')+block(OUT/'runtime.json','json')+block(VERIFY/'preservation_audit.json','json')
    files=git('diff','--name-only',p['base'],'--','conference').splitlines()+git('ls-files','--others','--exclude-standard','conference').splitlines()
    files+=['conference/results/lab_baseline/REPORT_ja.md','conference/results/lab_baseline/changed_files.txt']
    files=sorted(set(files));(OUT/'changed_files.txt').write_text('\n'.join(files)+'\n')
    report+='\n### 変更・追加ファイル一覧（新規ファイルのみ）\n\n'+'\n'.join('- `'+n+'`' for n in files)+'\n'
    (OUT/'REPORT_ja.md').write_text(report)
    assert all(f.stat().st_size<5_000_000 for f in OUT.rglob('*') if f.is_file())
    print('Report written;',len(tests),'test modules passed;',len(parity),'exact reference matches; originals unchanged.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--implementation-commit',required=True)
    main(parser.parse_args().implementation_commit)
