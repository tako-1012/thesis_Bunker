"""Append the centre-clearance revision without rewriting the original report."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import scipy

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
REPO = ROOT.parent
BASE = 'a6bf889c763484640bda6139e6291d2492d191ff'
REPORT = OUT.parent/'REPORT_ja.md'
REPORT_NAME = str(REPORT.relative_to(REPO))
SOURCE_NAMES = ['conference/tapp/pointcloud_map_fine.py', 'conference/tests/test_pointcloud_map_fine.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block(path):
    return '```text\n'+path.read_text().rstrip('\n')+'\n```\n\n'


def main():
    summary = (OUT/'test_summary.txt').read_text().splitlines()
    assert len(summary) == len(list((ROOT/'tests').glob('test_*.py')))
    assert all(line.endswith('exit=0') for line in summary)
    original = subprocess.check_output(['git', 'show', BASE+':'+REPORT_NAME], cwd=REPO)
    assert REPORT.read_bytes().startswith(original), 'previous report was modified'
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=REPO, text=True).splitlines()
    allowed = SOURCE_NAMES+[REPORT_NAME]
    assert set(changed).issubset(allowed), changed
    tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE], cwd=REPO, text=True).splitlines()
    protocol = dict(base=BASE, branch='codex/023-lidar-fine-grid',
                    python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                    fine_resolution_m=.1, obstacle_height_m=.3, min_obstacle_points=3, robot_radius_m=.5,
                    criterion='coarse centre to nearest point on closed raw fine-cell square <= 0.5m',
                    contact_boundary='inclusive; exact integer half-fine-cell coordinate comparison',
                    parameter_tuning=False, new_gazebo_runs=0,
                    source_sha256={name: sha(REPO/name) for name in SOURCE_NAMES})
    (OUT/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
    audit = dict(base=BASE, original_tracked_files=len(tracked),
                 permitted_existing_changes=allowed,
                 other_original_files_unchanged=True,
                 previous_report_is_byte_identical_prefix=True,
                 old_results_unchanged='All previous result files except the explicitly requested REPORT_ja.md append')
    (OUT/'preservation_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    text = '\n\n## 追記：粗セル中心から障害物セルの端までの距離で判定\n\n'
    text += 'この追記が現行の実装を説明する。上記の方法・図・出力・SHA-256は `a6bf889` 時点の記録として保持した。既存の数値やファイルは再生成していない。\n\n'
    text += '''### 変更の理由と範囲

経路計画でロボットの中心を粗セルの中心とみなすため、粗セルの領域が膨張マスクに少しでも重なることを禁止条件にすると、余分な粗セルまで通行不可になる。
`PointCloudMapFine._add_obstacles` の膨張後の集約を、粗セル中心の距離判定へ変更した。
`detected_obstacle = coarse_overlap(self.fine_obstacle)` はそのまま。0.1m・0.3m・3点・0.5mは変更・調整していない。
022の方式、地面の高さ、コスト、急斜面の膨張、ROS用の選択引数、経路計画は変更していない。

### セルの端と境界の扱い

障害物の細セルは、中心から各軸±0.05mの**閉じた正方形**として扱う。粗セル中心と障害物の細セル中心の差を各軸Δx、Δyとすると、
最も近い端または角までの距離は `sqrt(max(abs(Δx)-0.05,0)^2 + max(abs(Δy)-0.05,0)^2)`。
これが0.5m以下なら通行不可で、円とセルがちょうど接する場合も含む。障害物セル中心までの距離ではない。

粗セルの中心は、5×5分割した細セルの中央と一致する。円と正方形の距離を表す構造要素で、生の障害物を1回だけ膨張し、
`fine_inflated[2::5, 2::5]` の値を選ぶ。粗セルの領域に対するany集約を使わない。
距離計算を0.05m単位の整数座標で表し、各軸の距離 `max(2*abs(offset)-1,0)` の二乗和を100以下と判定する。
これにより、斜めの角も含めて正方形までの距離をそのまま判定する。EDTの中心間距離から一律0.05mを引く近似は使わない。
既に膨張した結果を再膨張させず、新しい生の障害物に対する結果との和を取る。

点の細セルへの割り当ては従来のfloor式とclipを変更していない。数学的には境界の正方向のセルへ割り当てる半開区間で、
浮動小数の丸めによる境界直近の割り当ても従来のまま。一方、衝突の距離計算では割り当てられたセルの両端を含める。
地図の端では配列外へ折り返さずに切り取り、観測のない外側セルを新たに作らない。

### テストで変更した期待値

- `test_noisy_box`：膨張済み細格子のany集約を期待する式を、全障害物の正方形と全粗セル中心との距離を列挙する独立の参照計算へ変更した。高さ・コスト・seenのバイト一致、中心の検出、022より外側セルが少ないことは引き続き確認する。
- `test_one_dilation`：細セル中心からの円盤と粗セル領域間の距離を期待していた部分を、障害物正方形の端までの距離と粗セル中心の判定へ変更した。繰り返し・追加の観測で二重に膨張しないことと保存マスクの検証は保持した。
- `test_side_spill_and_centre_clearance` を追加：箱の側面の点が隣セル内の0.1mの細セルを占めても、次の粗セル中心が0.5mより遠ければ通れることを確認した。全25通りの細セルの位置、地図の四隅、斜め方向について、半径内の中心を含めたマスク全体を独立計算と完全一致で比較する。
- 既存の他のテストファイルは変更していない。022の既定/明示選択で出力バイトが一致する確認も成功した。

### 箱周辺の通行不可セル数：変更前後を実行して比較

`a6bf889` の `pointcloud_map_fine.py` をGitから読み、変更後と同じ点群をそれぞれ処理した。
`before_total/after_total` は通行不可セルの総数、`*_outside` は真の箱の中心セル(10,10)を除いた数。
`*_next_cell` は中心(6.0,5.0)mの粗セル(12,10)の通行不可判定。
数値はすべて下記スクリプトを実行して得た。実機/Gazeboの値やFPの件数ではない。

'''
    text += block(OUT/'box_comparison_log.txt')
    text += '''元のノイズ付き箱の5ケースではセル数に変化がなかった。追加した0.1mはみ出しの回帰ケースで、次の粗セルが通れることを確認した。
比較した全入力で、高さ・コスト・seen・障害物そのものの粗格子/細格子のバイトは変更前後で一致した。

### 実行コマンドとテストの出力全文

変更前に `cd conference && python3 -m tests.test_planners` を実行し、出力は次のとおりだった。

```text
all planner tests passed
roll-aware tests passed
```

続いて以下を実行した。Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-023-mpl XDG_CACHE_HOME=/tmp/thesis-023-cache` を指定した。

```bash
cd conference
python3 -m tests.test_pointcloud_map_fine
python3 results/lidar_fine/center_update/compare_boxes.py
python3 results/lidar_fine/center_update/run_tests.py
python3 results/lidar_fine/center_update/append_report.py
```

最初の集中確認の出力全文：

'''
    text += block(OUT/'focused_log.txt')
    text += '全テストの出力全文：\n\n'+block(OUT/'all_tests_log.txt')+block(OUT/'test_summary.txt')
    text += '### 既存ファイルの保持と現在のソース\n\n'
    text += block(OUT/'preservation_audit.json')+block(OUT/'protocol.json')
    text += '''### 未実行・確認してほしいこと

今回もGazebo実走は実施していない。完走率・実走の誤検出・更新時間への影響は未測定で、合成箱の結果から補っていない。
保存済みのmanifest、図、比較表、旧プロトコルは修正前の記録として残した。現在の細格子の幾何とソースハッシュはこの追記と `center_update/protocol.json` を参照する。
Claudeには実走時に、同じ10地形・world・地点・速さ・途切れ期限を保ち、特に閉塞した通路と疎な障害物の見落としを確認してほしい。
同じ作業ブランチを更新し、マージは行わない。
'''
    REPORT.write_bytes(original+text.encode())
    assert REPORT.read_bytes().startswith(original)
    names = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=REPO, text=True).splitlines()
    names += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    names += [str((OUT/'changed_files.txt').relative_to(REPO))]
    (OUT/'changed_files.txt').write_text('\n'.join(sorted(set(names)))+'\n')
    print('Appended report; all', len(summary), 'test modules passed; previous report prefix unchanged.')


if __name__ == '__main__':
    main()
