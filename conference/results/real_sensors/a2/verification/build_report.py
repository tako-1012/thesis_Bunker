"""Assemble the A2 Japanese handoff from Python-only verification outputs."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

VERIFY = Path(__file__).resolve().parent
OUT = VERIFY.parent
ROOT = VERIFY.parents[3]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from tapp.sensor_geometry import DepthCameraSpec


def block(path, language='text'):
    return '```'+language+'\n'+path.read_text().rstrip('\n')+'\n```\n\n'


def main(commit):
    commit = subprocess.check_output(['git','rev-parse',commit+'^{commit}'],cwd=REPO,text=True).strip()
    protocol = json.loads((VERIFY/'protocol.json').read_text())
    for name, checksum in protocol['source_sha256'].items():
        source = (REPO/name).read_bytes()
        assert hashlib.sha256(source).hexdigest() == checksum, name
        assert subprocess.check_output(['git','show',commit+':'+name],cwd=REPO) == source, name
    baseline = json.loads((VERIFY/'baseline_sha256.json').read_text())
    changed = [name for name,h in baseline.items() if hashlib.sha256((REPO/name).read_bytes()).hexdigest() != h]
    assert changed == list(protocol['source_sha256']), changed
    tests = (VERIFY/'test_summary.txt').read_text().splitlines()
    assert len(tests) == len(list((ROOT/'tests').glob('test_*.py')))
    assert all(line.endswith('exit=0') for line in tests)
    focused = (VERIFY/'real_sensors_log.txt').read_text()
    assert 'all real sensor tests passed' in focused and 'Traceback' not in focused
    (OUT/'implementation_commit.txt').write_text(commit+'\n')
    report = '# 指示書027・段階A2：深度カメラの投影の修正\n\n'
    report += '実装・テストログのコミットID：`'+commit+'`。この報告書は後続の文書コミットで追加する。\n\n'
    report += '作業ブランチ：`codex/027a2-camera-fov`。基点は最新取得したrealtime-mapの `'+protocol['base']+'`。基準日は'+protocol['client_date']+'（日本時間）。マージしない。\n\n'
    report += '''## 実装したものと変更範囲

指定された段階A2の1〜4だけを実装した。背景は [段階B0の報告](../b0/REPORT_ja.md) を参照する。

- `tapp/sensor_geometry.py`：`DepthCameraSpec.width/height` を事前指定の214×125へ変更した。それ以外の仕様・取り付け位置・向きは変えていない。
- `ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py`：`add_depth_camera` が `lens/intrinsics` を出力する処理を削除した。`horizontal_fov` と画像の縦横比からGazeboが投影を決める。
- `ros2_jazzy/gz_checks/run_lidar_checks.sh`：`THESIS_FINE_PROTOCOL` と `THESIS_ONLY_PATCH` を、設定されている場合だけ `-e` で転送する。未設定なら引数を追加しない。個別・両方・空文字を明示設定した場合の転送をテストした。
- `tests/test_real_sensors.py`：カメラ有効時の旧212×120・独立fx/fyの期待値を、指定された214×125・intrinsicsなし・縦FOV58°±0.1°の条件へ置き換えた。取り付け位置・向き・範囲・頻度・雑音の検証は保持した。さらに全SDFの差分、既定のバイト一致、起動引数の転送を確認するテストを追加した。

`prepare_cases` は既存の `sensor_configuration` を使うため、新しい画素数は実走時のmanifestの `sensor_configuration.depth_camera_spec` にそのまま記録される。既存の「仮定」という記載も維持する。manifestへの記録はPythonのテストで確認した。

現在のカメラ仕様（Pythonの `asdict(DepthCameraSpec())`）：

'''
    report += '```json\n'+json.dumps(asdict(DepthCameraSpec()),indent=2)+'\n```\n\n'
    report += '''## 投影と既定出力の検証

生成したSDFの横FOVと画素数から `2*atan(height/width*tan(horizontal_fov/2))` を計算した。結果の全文は下の対象テスト出力に含めた。両カメラで58°±0.1°を満たし、生成するSDFにintrinsicsはない。

変更前に保存した比較入力と、カメラなしの既定SDF・既定LiDAR付きSDF・実機位置のLiDARだけのSDFを**そのままのバイトで比較**し、一致した。既存の既定Fine地図NPZのSHA-256も一致した。
カメラ付きSDFは、旧SDFから指定された画素数とintrinsicsの削除だけを反映したものと全体で一致した。カメラ仕様もwidth/height以外は変更前の辞書と一致した。

Docker起動引数は、実行機固有のソース/出力パスとUID/GIDだけを置き換え、変更前に捕捉した既定/coarse・fineの全引数のJSONバイトと比較した。2変数の未設定時は一致した。追加される引数以外も一致した。
この確認では実際のDockerを使わず、引数を保存するだけのPythonスタブをPATHの先頭へ置いた。コンテナやGazeboは起動していない。

`verification/legacy/` のSDFと仕様は変更前の比較入力として保持した。新しいSDFの出力を確認するのはテスト中の一時領域である。

## 実行したコマンドとテストの出力全文

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-027a2-mpl XDG_CACHE_HOME=/tmp/thesis-027a2-cache` を指定した。

```bash
cd conference
python3 -m tests.test_planners
python3 results/real_sensors/a2/verification/capture_legacy.py  # 修正前に一度実行
python3 -m tests.test_real_sensors
python3 results/real_sensors/a2/verification/run_tests.py
python3 results/real_sensors/a2/verification/build_report.py --implementation-commit <上記の実装コミットID>
```

変更前のプランナー：

'''
    report += block(VERIFY/'planners_before_log.txt')
    report += '変更前の比較入力の保存：\n\n'+block(VERIFY/'capture_legacy_log.txt')
    report += '変更後の対象テスト：\n\n'+block(VERIFY/'real_sensors_log.txt')
    report += '全Pythonテストの出力全文：\n\n'+block(VERIFY/'all_tests_log.txt')+block(VERIFY/'test_summary.txt')
    report += '## 既存ファイルの保持と実行環境\n\n'
    report += '既存ファイルの変更は上記4ファイルだけ。B0を含む既存結果、地図、world、入力データ、LiDAR仕様、既定のfine_protocol、地図更新・経路計画の処理は変更していない。\n\n'
    report += block(VERIFY/'preservation_audit.json','json')+block(VERIFY/'protocol.json','json')
    report += '''## できなかったこと・研究PCで確認してほしいこと

利用者の指定どおり、Gazebo・実際のDocker・研究PCでの実走は実施していない。PythonのSDF・幾何学・既定出力のテストで確認した。
点群の地面の8〜10cmの差が解消したかは**実測未確認**。原因がintrinsicsであることも、今回のPythonテストだけでは確定しない。
研究PCで段階B0の確認2（点群の向き・高さ）を再実行して確かめる必要がある。新しい高さ誤差や完走率の数値は作っていない。
範囲外の段階B0/Bの実行、別の値の調整、他の条件の変更は行っていない。
'''
    names = subprocess.check_output(['git','diff','--name-only',protocol['base'],'--','conference'],cwd=REPO,text=True).splitlines()
    names += subprocess.check_output(['git','ls-files','--others','--exclude-standard','conference'],cwd=REPO,text=True).splitlines()
    names += ['conference/results/real_sensors/a2/REPORT_ja.md','conference/results/real_sensors/a2/changed_files.txt']
    names = sorted(set(names))
    (OUT/'changed_files.txt').write_text('\n'.join(names)+'\n')
    report += '\n## 変更・追加ファイル一覧\n\n'+'\n'.join('- `'+n+'`' for n in names)+'\n'
    (OUT/'REPORT_ja.md').write_text(report)
    print('Report written for implementation',commit,';',len(tests),'test modules passed.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation-commit',required=True)
    main(parser.parse_args().implementation_commit)
