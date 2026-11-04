# 指示書020の再実行

最新の結果・テスト全文・変更一覧は `REPORT_ja.md` にある。

```bash
cd conference
python3 -m tests.test_footprint
python3 experiments/footprint_steep.py --workers 3
python3 experiments/footprint_annotation.py
python3 experiments/footprint_report.py
```

`protocol.json` は半径・条件・統計・ソース・入力データ・ライブラリ版を固定する。
同じ条件なら完了済みキャッシュを再利用する。条件やソースが変わる場合は `--output` で新しい保存先を選ぶ。
0.39mと0.5mは、岩と同じ0.5m格子への切り上げで同じマスクになる。結果を見て片方を選定していない。

`footprint_annotation.py` は019の原記録から転倒を判定し、元の数値の文字列表現を保って派生集計を更新する。
019の原mission・軌跡・図・走行別の数値と、既存の対の差は変更しない。

## 追加Gazebo走行（このクラウドでは未実行）

```bash
cd conference
bash ros2_jazzy/gz_checks/run_compare_checks.sh results/footprint_steep/gazebo_inflate --planners 'TA*-S+inflate'
python3 experiments/footprint_report.py --inflated results/footprint_steep/gazebo_inflate
```

`THESIS_ROS_IMAGE` で使用イメージを指定できる。
既存manifestがある保存先は上書きせず停止するため、再試行時は別の保存先を指定する。

今回の `gazebo_comparison/planning_only/` はROS2不要の計画確認で、実走の保存先と分けた。
追加走行がない場合、`footprint_report.py` は新手法の物理測定値を空欄にする。
`no_path` は計画不可であり、転倒なしの実測として数えない。

このクラウドでは、準備した名前空間での実行について権限確認が中断されたため、追加のGazeboプロセスを開始していない。
`verification/unexecuted_namespace_run.sh` はその準備スクリプトを記録したもの（クラウド固有のパスを含む）。
