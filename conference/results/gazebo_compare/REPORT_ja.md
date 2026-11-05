# 指示書019：LAS砂浜6地形のA*・TA*-S Gazebo比較

## 指示書020による転倒判定の追記

集計に `rolled_over` を追加した。走行中のどこかで絶対rollが90度を超えた走行は、集計の `status` を `rollover` とする。
`recorded_status` には元の終了状態を保持する。最初に閾値を超えた記録のシミュレーション時刻・開始からの経過秒・地図上のx,y位置も追加した。
この判定で `08OB88_-0167` の両方法が転倒に該当した。原missionの終了状態は両方 `stuck` のままである。

変更した既存結果は、この報告書、`physical_run/report/runs.csv`（転倒の列と派生status）、
`physical_run/report/compare_log.txt`（同じ列を表示する表）の3ファイルだけ。
既存の数値はCSVの文字列表現を含めて維持し、原mission・軌跡、地図、図、走行別数値、対の差の数値は変更していない。
以下に残している当時の整合性監査JSONの `stuck` は原記録の終了状態であり、集計の `rollover` と区別して読む。
再分類の監査は `../footprint_steep/rollover_annotation_audit.json`、新しい対策の検証は `../footprint_steep/REPORT_ja.md` に記載する。

報告更新日：2026-11-03（日本時間）。
ブランチ：`codex/019-gazebo-compare`。基点：`origin/realtime-map` の `b4c92a1ccaf60eff85362564d2f0d9915c3d10ae`。他の指示書を取り込まず、マージしていない。

## 実行結果

Gazeboで全ケースを実行し、実際の記録から集計した。完走・終了状態の件数（記録から計算）：

- A* / completed：5
- A* / rollover：1
- TA*-S / completed：5
- TA*-S / rollover：1

未完走の走行も原記録と表に残し、再試行・設定の調整はしていない。転倒記録（原記録ではstuck終了）の終端値：

- 08OB88_-0167 / A*：目標誤差 10.329m、最終絶対roll 167.111度、最終絶対pitch 17.0482度。

- 08OB88_-0167 / TA*-S：目標誤差 30.5485m、最終絶対roll 170.075度、最終絶対pitch 26.281度。

同じ地形で両方法が転倒し、終端の姿勢は車体の反転と整合する大きなrollを示した。原因は接触力などを記録していないため確定していない。未完走の値は部分走行の測定として扱う。完走した対の中央値と、全ケースの終了状態の両方を読む必要がある。

## 実装

- `data_prep/export_gazebo.py` にキーワード専用 `max_pixels=2049` を追加。既定値と高さ誤差上限0.1mを維持し、019だけ上限4097画素を指定する。基準を満たす最小の2^n+1画像を選び、地形・開始終了点・プランナーの重みは変更しない。AGENTS.mdの変更禁止一覧にこのスクリプトは含まれておらず、既定動作を保つキーワード追加の方針に従った。
- `ros2_jazzy/gz_checks/compare_checks.py`：`shizuoka_beach_las` のtest先頭6地形、200m、seed 0、漂着物なし。`build_real` の開始終了点から既定の `run_planner_exact` のA*とTA*-Sで計画し、同じworld・同じ初期位置・yaw=0で既存 `path_follower` を実行する。5シミュレーション秒の静置後に出発する。worldは既存exporterで一時フォルダにのみ生成する。変換失敗・プロセス異常は残し、記録は上書きしない。
- `run_compare_checks.sh`：既存Dockerfile（osrf/ros:jazzy-desktop-full + pandas）を使い、`THESIS_ROS_IMAGE` に対応。ソースは読取専用で、ビルド・worldは一時領域、出力だけを保存する。
- `experiments/gz_compare_report.py`：変更していない `analyze_run` を使用し、12走行の表と完走した対のTA*-S−A*の中央値を出す。実測roll/pitchの絶対値の95%と最大、記録zの正の増分、計画経路に対する `evaluate` の地図指標、各砂浜の2軌跡とroll時系列を保存する。原mission JSONを書き換えず、一時ビューで地図パスを解決する。
- `tests/test_gz_compare.py`：直接呼出しとの開始終了点・経路一致、運動学の試験用記録と `analyze_run` の値の一致、最大角度・登り・地図指標・対の中央値、原記録の不変性、未実行や変換失敗を測定値0にしないことを検証する。生成PNGを独立に復号し、6地形すべてで元格子中心への復元誤差を確認する。
- `followup/audit_physical.py`：実走記録の出所、終端状態、経路同一性、有限値・時刻、指令上限、完走時の到着誤差、凍結したソースのハッシュを確認する。

エネルギーは集計しない。6砂浜の記述比較として傾向を見るだけで、検定は行わない。走行中に計画・追従パラメータを調整していない。画像解像度は従来からの固定誤差基準で決め、走行の性能値を使っていない。

## 変更ファイル一覧

コード・報告・生成物を含む全ファイル（`changed_files.txt` にも保存）：

<details><summary>全ファイル</summary>

- `conference/data_prep/export_gazebo.py`
- `conference/experiments/gz_compare_report.py`
- `conference/results/gazebo_compare/REPORT_ja.md`
- `conference/results/gazebo_compare/changed_files.txt`
- `conference/results/gazebo_compare/docker_attempt_log.txt`
- `conference/results/gazebo_compare/followup/audit_physical.py`
- `conference/results/gazebo_compare/followup/baseline_audit.json`
- `conference/results/gazebo_compare/followup/default_export_after_log.txt`
- `conference/results/gazebo_compare/followup/default_export_before_log.txt`
- `conference/results/gazebo_compare/followup/headless_dependency_probe_log.txt`
- `conference/results/gazebo_compare/followup/headless_https_probe_log.txt`
- `conference/results/gazebo_compare/followup/namespace_first_attempt_log.txt`
- `conference/results/gazebo_compare/followup/namespace_resolver_failure_log.txt`
- `conference/results/gazebo_compare/followup/namespace_run_log.txt`
- `conference/results/gazebo_compare/followup/namespace_run_log.txt.gz`
- `conference/results/gazebo_compare/followup/oci_extract_log.txt`
- `conference/results/gazebo_compare/followup/physical_audit_log.txt`
- `conference/results/gazebo_compare/followup/planners_before_log.txt`
- `conference/results/gazebo_compare/followup/runtime_setup/README_ja.md`
- `conference/results/gazebo_compare/followup/runtime_setup/image_manifest.json`
- `conference/results/gazebo_compare/followup/runtime_setup/image_source.json`
- `conference/results/gazebo_compare/followup/runtime_setup/namespace_run.sh`
- `conference/results/gazebo_compare/followup/runtime_setup/pull_runtime.py`
- `conference/results/gazebo_compare/followup/test_environment_log.txt`
- `conference/results/gazebo_compare/followup/test_gz_compare_initial_log.txt`
- `conference/results/gazebo_compare/followup/tests/all_tests_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_beach_terrain_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_collision_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_dstar_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_gz_compare_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_mapfiles_sim_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_mission_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_natural_terrain_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_online_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_online_mission_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_planners_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_real_beach_las_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_real_beach_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_risk_prior_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_ros2_gz_log.txt`
- `conference/results/gazebo_compare/followup/tests/test_summary.txt`
- `conference/results/gazebo_compare/followup/tests/test_tour_log.txt`
- `conference/results/gazebo_compare/followup/world_preparation_log.txt`
- `conference/results/gazebo_compare/physical_run/actor_source_sha256.json`
- `conference/results/gazebo_compare/physical_run/environment_details.json`
- `conference/results/gazebo_compare/physical_run/integrity_audit.json`
- `conference/results/gazebo_compare/physical_run/manifest.json`
- `conference/results/gazebo_compare/physical_run/maps/real_las_08OB86_-0205_200m_0.npz`
- `conference/results/gazebo_compare/physical_run/maps/real_las_08OB86_00294_200m_0.npz`
- `conference/results/gazebo_compare/physical_run/maps/real_las_08OB87_-0706_200m_0.npz`
- `conference/results/gazebo_compare/physical_run/maps/real_las_08OB88_-0167_200m_0.npz`
- `conference/results/gazebo_compare/physical_run/maps/real_las_08OB88_-1417_200m_0.npz`
- `conference/results/gazebo_compare/physical_run/maps/real_las_08OB88_00332_200m_0.npz`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_Astar/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_Astar/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_Astar/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_Astar/runs/20261103T015631_761023_file_real_las_08OB86_-0205_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_Astar/runs/20261103T015631_761023_file_real_las_08OB86_-0205_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_TAstar-S/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_TAstar-S/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_TAstar-S/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_TAstar-S/runs/20261103T015921_202775_file_real_las_08OB86_-0205_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_-0205_TAstar-S/runs/20261103T015921_202775_file_real_las_08OB86_-0205_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_Astar/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_Astar/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_Astar/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_Astar/runs/20261103T015041_310441_file_real_las_08OB86_00294_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_Astar/runs/20261103T015041_310441_file_real_las_08OB86_00294_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_TAstar-S/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_TAstar-S/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_TAstar-S/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_TAstar-S/runs/20261103T015338_462198_file_real_las_08OB86_00294_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB86_00294_TAstar-S/runs/20261103T015338_462198_file_real_las_08OB86_00294_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_Astar/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_Astar/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_Astar/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_Astar/runs/20261103T020216_963337_file_real_las_08OB87_-0706_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_Astar/runs/20261103T020216_963337_file_real_las_08OB87_-0706_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_TAstar-S/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_TAstar-S/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_TAstar-S/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_TAstar-S/runs/20261103T020513_700111_file_real_las_08OB87_-0706_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB87_-0706_TAstar-S/runs/20261103T020513_700111_file_real_las_08OB87_-0706_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_Astar/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_Astar/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_Astar/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_Astar/runs/20261103T021340_015434_file_real_las_08OB88_-0167_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_Astar/runs/20261103T021340_015434_file_real_las_08OB88_-0167_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_TAstar-S/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_TAstar-S/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_TAstar-S/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_TAstar-S/runs/20261103T021821_357115_file_real_las_08OB88_-0167_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-0167_TAstar-S/runs/20261103T021821_357115_file_real_las_08OB88_-0167_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_Astar/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_Astar/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_Astar/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_Astar/runs/20261103T020807_910128_file_real_las_08OB88_-1417_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_Astar/runs/20261103T020807_910128_file_real_las_08OB88_-1417_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_TAstar-S/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_TAstar-S/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_TAstar-S/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_TAstar-S/runs/20261103T021053_705544_file_real_las_08OB88_-1417_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_-1417_TAstar-S/runs/20261103T021053_705544_file_real_las_08OB88_-1417_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_Astar/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_Astar/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_Astar/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_Astar/runs/20261103T022410_663181_file_real_las_08OB88_00332_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_Astar/runs/20261103T022410_663181_file_real_las_08OB88_00332_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_TAstar-S/process_0.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_TAstar-S/process_1.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_TAstar-S/process_2.log`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_TAstar-S/runs/20261103T022717_239390_file_real_las_08OB88_00332_200m_0_npz/mission.json`
- `conference/results/gazebo_compare/physical_run/raw/08OB88_00332_TAstar-S/runs/20261103T022717_239390_file_real_las_08OB88_00332_200m_0_npz/trajectory.csv`
- `conference/results/gazebo_compare/physical_run/raw_recordings_sha256.json`
- `conference/results/gazebo_compare/physical_run/report/08OB86_-0205.png`
- `conference/results/gazebo_compare/physical_run/report/08OB86_00294.png`
- `conference/results/gazebo_compare/physical_run/report/08OB87_-0706.png`
- `conference/results/gazebo_compare/physical_run/report/08OB88_-0167.png`
- `conference/results/gazebo_compare/physical_run/report/08OB88_-1417.png`
- `conference/results/gazebo_compare/physical_run/report/08OB88_00332.png`
- `conference/results/gazebo_compare/physical_run/report/compare_log.txt`
- `conference/results/gazebo_compare/physical_run/report/paired_differences.csv`
- `conference/results/gazebo_compare/physical_run/report/runs.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/Astar/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/Astar/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/Astar/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/Astar/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/Astar/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/TAstar-S/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/TAstar-S/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/TAstar-S/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/TAstar-S/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_-0205/TAstar-S/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/Astar/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/Astar/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/Astar/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/Astar/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/Astar/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/TAstar-S/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/TAstar-S/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/TAstar-S/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/TAstar-S/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB86_00294/TAstar-S/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/Astar/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/Astar/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/Astar/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/Astar/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/Astar/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/TAstar-S/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/TAstar-S/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/TAstar-S/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/TAstar-S/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB87_-0706/TAstar-S/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/Astar/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/Astar/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/Astar/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/Astar/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/Astar/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/TAstar-S/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/TAstar-S/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/TAstar-S/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/TAstar-S/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-0167/TAstar-S/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/Astar/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/Astar/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/Astar/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/Astar/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/Astar/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/TAstar-S/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/TAstar-S/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/TAstar-S/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/TAstar-S/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_-1417/TAstar-S/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/Astar/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/Astar/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/Astar/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/Astar/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/Astar/summary.json`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/TAstar-S/attitude.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/TAstar-S/paths.png`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/TAstar-S/report_log.txt`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/TAstar-S/summary.csv`
- `conference/results/gazebo_compare/physical_run/report/runs/08OB88_00332/TAstar-S/summary.json`
- `conference/results/gazebo_compare/physical_run/runtime_source.json`
- `conference/results/gazebo_compare/verification/all_tests_log.txt`
- `conference/results/gazebo_compare/verification/baseline_audit.json`
- `conference/results/gazebo_compare/verification/environment_log.txt`
- `conference/results/gazebo_compare/verification/planners_before_log.txt`
- `conference/results/gazebo_compare/verification/test_beach_terrain_log.txt`
- `conference/results/gazebo_compare/verification/test_collision_log.txt`
- `conference/results/gazebo_compare/verification/test_dstar_log.txt`
- `conference/results/gazebo_compare/verification/test_gz_compare_final_log.txt`
- `conference/results/gazebo_compare/verification/test_gz_compare_log.txt`
- `conference/results/gazebo_compare/verification/test_mapfiles_sim_log.txt`
- `conference/results/gazebo_compare/verification/test_mission_log.txt`
- `conference/results/gazebo_compare/verification/test_natural_terrain_log.txt`
- `conference/results/gazebo_compare/verification/test_online_log.txt`
- `conference/results/gazebo_compare/verification/test_online_mission_log.txt`
- `conference/results/gazebo_compare/verification/test_planners_log.txt`
- `conference/results/gazebo_compare/verification/test_real_beach_las_log.txt`
- `conference/results/gazebo_compare/verification/test_real_beach_log.txt`
- `conference/results/gazebo_compare/verification/test_risk_prior_log.txt`
- `conference/results/gazebo_compare/verification/test_ros2_gz_log.txt`
- `conference/results/gazebo_compare/verification/test_summary.txt`
- `conference/results/gazebo_compare/verification/test_tour_log.txt`
- `conference/results/gazebo_compare/verification/world_preparation_log.txt`
- `conference/ros2_jazzy/gz_checks/README_compare_ja.md`
- `conference/ros2_jazzy/gz_checks/compare_checks.py`
- `conference/ros2_jazzy/gz_checks/run_compare_checks.sh`
- `conference/tests/test_gz_compare.py`

</details>

## 既存結果と既定出力の互換性

既存テストを変更していない。基点のファイルのSHA-256監査結果：

```json
{
  "tracked_baseline_files": 804,
  "changed": [
    "conference/data_prep/export_gazebo.py"
  ]
}
```

基点の既存ファイルでは、後方互換の引数追加をしたexporter以外のファイルはすべて一致した。既存データ・地図・world・結果は変更していない。修正前に保存した2地図の既定出力と修正後の出力について、返り値とPNG・SDF・READMEのSHA-256がすべて一致することも確認した。

```text
{
  "flat_test_100m.npz": {
    "summary": {
      "map": "flat_test_100m.npz",
      "pixels": 257,
      "side_m": 100.0,
      "z_min": 0.0,
      "z_span": 0.001,
      "max_error_m": 0.0,
      "quantization_bound_m": 7.629510948348211e-09,
      "obstacle_boxes": 3
    },
    "sha256": {
      "README_ja.md": "cb92ab0fdb0d32c76986630bfc9049fe33796347dd06159e4ff2529d792989b1",
      "heightmap.png": "03166ac1d06b01905a6f66391cb422384b2869ab8732e863f5adc71f0c3776e7",
      "world.sdf": "41c6e85b78aa36357c1fb65a9da4603015a6cee51850cd63118c8545bc31315e"
    }
  },
  "real_08OB87_-0206_200m_0.npz": {
    "summary": {
      "map": "real_08OB87_-0206_200m_0.npz",
      "pixels": 2049,
      "side_m": 200.0,
      "z_min": -1.2999999523162842,
      "z_span": 8.099952459335327,
      "max_error_m": 0.06374200885325632,
      "quantization_bound_m": 6.179867596959889e-05,
      "obstacle_boxes": 0
    },
    "sha256": {
      "README_ja.md": "b8ff3ebc7cb2f20d003cd3100ea29fd6ba98f7a6bbfddd610316ad2c9aa8e073",
      "heightmap.png": "108b5f25d7601d56627e6c2e793b9a20aaeecf2247d5c14e0c8286534ab2b40b",
      "world.sdf": "559020b37cfddf8fe7314ab9df6dfa90c3d6176aa3534bc2c83e12336fdeb77f"
    }
  }
}
Default exporter outputs before/after: metadata, PNG, SDF and README all match byte-for-byte.
```

## world生成の確認

独立のPNG復号による誤差検証は新規テストで実行した。以下はPythonテスト用venvでの一時world準備の出力全文で、走行測定値ではない。実走時の変換結果は `physical_run/manifest.json` に別途保存している。

```text
Temporary world generation only; no physical Gazebo measurements.
{
  "world_max_pixels": 4097,
  "world_exports": {
    "08OB86_00294": {
      "map": "real_las_08OB86_00294_200m_0.npz",
      "pixels": 2049,
      "side_m": 200.0,
      "z_min": -1.3849999904632568,
      "z_span": 7.694166421890259,
      "max_error_m": 0.061695935096075516,
      "quantization_bound_m": 5.8702726954224906e-05,
      "obstacle_boxes": 0
    },
    "08OB86_-0205": {
      "map": "real_las_08OB86_-0205_200m_0.npz",
      "pixels": 2049,
      "side_m": 200.0,
      "z_min": -1.2760000228881836,
      "z_span": 6.869285583496094,
      "max_error_m": 0.06354209578655112,
      "quantization_bound_m": 5.240928956661397e-05,
      "obstacle_boxes": 0
    },
    "08OB87_-0706": {
      "map": "real_las_08OB87_-0706_200m_0.npz",
      "pixels": 1025,
      "side_m": 200.0,
      "z_min": -1.2669999599456787,
      "z_span": 7.20799994468689,
      "max_error_m": 0.09197745315509853,
      "quantization_bound_m": 5.4993514493681925e-05,
      "obstacle_boxes": 0
    },
    "08OB88_-1417": {
      "map": "real_las_08OB88_-1417_200m_0.npz",
      "pixels": 4097,
      "side_m": 200.0,
      "z_min": -1.3049999475479126,
      "z_span": 10.07099974155426,
      "max_error_m": 0.06239859486475474,
      "quantization_bound_m": 7.683680278900023e-05,
      "obstacle_boxes": 0
    },
    "08OB88_-0167": {
      "map": "real_las_08OB88_-0167_200m_0.npz",
      "pixels": 4097,
      "side_m": 200.0,
      "z_min": -1.2259999513626099,
      "z_span": 9.790000081062317,
      "max_error_m": 0.06638817009318743,
      "quantization_bound_m": 7.469291280279481e-05,
      "obstacle_boxes": 0
    },
    "08OB88_00332": {
      "map": "real_las_08OB88_00332_200m_0.npz",
      "pixels": 4097,
      "side_m": 200.0,
      "z_min": -1.4709999561309814,
      "z_span": 9.908000230789185,
      "max_error_m": 0.056513540446618826,
      "quantization_bound_m": 7.559319623704268e-05,
      "obstacle_boxes": 0
    }
  },
  "world_errors": {}
}
All six worlds satisfy the unchanged 0.1m error bound; temporary worlds removed on exit.
```

## 実行環境とGazeboの起動

ホストのDocker VFS領域では既定イメージのレイヤー展開が容量不足となった。軽量構成の依存関係取得もROS配布サーバーへの403で失敗したため、公開Dockerイメージを空きのある `/tmp` に取得し、各レイヤーのSHA-256を照合して展開した。一般ユーザーのuser/mount namespace内で一時rootfsにchrootし、既存Dockerfileと同じくpandasを追加して実行した。ソースは読取専用、結果は書込可能なマウントとし、ホストへのsudo・パッケージ導入は行っていない。通常のDocker起動スクリプトの経路は、このクラウドの容量制約では最後まで実行していない。

```json
{
  "image": "osrf/ros:jazzy-desktop-full",
  "index_digest": "sha256:ae7ad3ac243da1dfd8bd402a2fa08e149ffbf7a385013bd8ef798d0800accdc8",
  "manifest_digest": "sha256:ae7ad3ac243da1dfd8bd402a2fa08e149ffbf7a385013bd8ef798d0800accdc8",
  "runtime": "temporary root filesystem in an unprivileged user/mount namespace; default image flattened after SHA-256 verification"
}
```

```json
{
  "runtime": "unprivileged user/mount namespace and chroot; source read-only, output writable",
  "versions": {
    "numpy": "1.26.4",
    "scipy": "1.11.4",
    "matplotlib": "3.6.3",
    "pandas": "2.1.4"
  },
  "colcon_build": "both thesis_bunker_mission and thesis_bunker_gz finished successfully; full output in followup/namespace_run_log.txt"
}
```

Gazebo記録のmanifestに保存した実測環境：

```json
{
  "image": "osrf/ros:jazzy-desktop-full@sha256:ae7ad3ac243da1dfd8bd402a2fa08e149ffbf7a385013bd8ef798d0800accdc8",
  "gazebo": "8.11.0",
  "python": "3.12.3 (main, Jul 15 2026, 23:46:41) [GCC 13.3.0]",
  "numpy": "1.26.4",
  "scipy": "1.11.4"
}
```

実行したコマンド：

```bash
python3 /tmp/task019_pull_runtime.py
bash /tmp/task019_namespace_run.sh > conference/results/gazebo_compare/followup/namespace_run_log.txt 2>&1
```

実際に使った補助手順とイメージmanifestは `followup/runtime_setup/` に保存した。クラウド固有のパスをそのまま残した実行記録であり、通常の再実行にはDockerスクリプトを使用する。ROS2のcolcon buildとGazebo起動を含む全ログは `followup/namespace_run_log.txt`（端末進捗のCR改行をLFに統一し行末空白を除去）。元のバイト列は `followup/namespace_run_log.txt.gz` に損失なく保存した。

## テストのコマンドと出力全文

Pythonテストは `/tmp/thesis-apt-compat/bin/python`、`OPENBLAS_NUM_THREADS=1`、`MPLCONFIGDIR=/tmp/thesis-batch-mpl`、`XDG_CACHE_HOME=/tmp/thesis-batch-cache` で実行した。実走側のPython/NumPy/SciPyとは環境を区別している。変更前：

```bash
cd conference
python3 -m tests.test_planners
```

```text
executable: /tmp/thesis-apt-compat/bin/python
Python: 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]
numpy 2.3.5
scipy 1.17.0
matplotlib 3.10.8
pandas 2.2.3
pydantic 2.13.4
fastapi 0.141.1
httpx 0.28.1
```

```text
all planner tests passed
roll-aware tests passed
```

変更後は全 `conference/tests/test_*.py` を順番に実行：

```bash
python3 /tmp/thesis_batch_tools.py suite /workspace/thesis-019 /workspace/thesis-019/conference/results/gazebo_compare/followup/tests
```

```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ python3 -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ python3 -m tests.test_mapfiles_sim
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed
all mapfiles/simulation tests passed

exit=0

$ python3 -m tests.test_mission
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed
parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed
validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed
safety: synthetic/beach_gentle/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_steep/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_scarp/200/100, 5 points, terrain/euclid contact=0
safety: real/08OB87_-0206/200, 5 points, terrain/euclid contact=0
safety: real/08OB88_01332/200, 5 points, terrain/euclid contact=0
API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed
all mission tests passed

exit=0

$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ python3 -m tests.test_online_mission
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
beach_gentle: no-prior/coarse exact trajectory and plan-count parity; contact=0
beach_steep: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB88_01332: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206 stale five-point tour: online contact=0; fixed debris cells= 11
08OB88_01332 stale five-point tour: online contact=0; fixed debris cells= 18
08OB89_-1597 stale five-point tour: online contact=0; fixed debris cells= 6
async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed
follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run
maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed
all online-mission tests passed

exit=0

$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ python3 -m tests.test_real_beach
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
all 60 patches satisfy sea-to-land orientation
08OB86_00294: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_-0205: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0706: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-1417: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0167: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00294: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB86_-0205: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0706: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-1417: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0167: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 0
all real-beach tests passed

exit=0

$ python3 -m tests.test_real_beach_las
data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed
quantized_0.1m_fraction: new_max 0.0035301084084904803 old_min 0.27882342564826246
defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches
08OB86_00294: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_-0205: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB87_-0706: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-1417: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-0167: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_00294: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB86_-0205: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB87_-0706: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-1417: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-0167: exact offline and coarse R5 c10 safety, clean/debris contact=0
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ python3 -m tests.test_ros2_gz
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed
packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed
follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 34.2 0.02959598405434589 0.3173397734180379 0
kinematic True 34.2 0.02959598405434589 0.3173397734180379 0
attitude actual_p95_deg map_p95_deg
roll 0.0 0.0
pitch 0.0 0.0
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 7.7 0.0 0.0 0
kinematic True 7.7 0.0 0.0 0
attitude actual_p95_deg map_p95_deg
roll 0.0 11.309932474020224
pitch 0.0 5.710593137499648
report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)
API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed
worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added
all ROS-free ROS2/Gazebo tests passed

exit=0

$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0
```

```text
test_beach_terrain exit=0
test_collision exit=0
test_dstar exit=0
test_gz_compare exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_mission exit=0
test_planners exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_tour exit=0
Failed modules: []
```

## 物理記録の整合性確認

```bash
cd conference
python3 results/gazebo_compare/followup/audit_physical.py
```

```text
{
  "actor_source_files_checked": 44,
  "worlds": 6,
  "cases": 12,
  "runs": [
    {
      "patch": "08OB86_00294",
      "planner": "A*",
      "status": "completed",
      "samples": 3320,
      "goal_error_m": 0.2878517765733064,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB86_00294",
      "planner": "TA*-S",
      "status": "completed",
      "samples": 3225,
      "goal_error_m": 0.29802869850362,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB86_-0205",
      "planner": "A*",
      "status": "completed",
      "samples": 3150,
      "goal_error_m": 0.28356093062032933,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB86_-0205",
      "planner": "TA*-S",
      "status": "completed",
      "samples": 3079,
      "goal_error_m": 0.2752664307753353,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB87_-0706",
      "planner": "A*",
      "status": "completed",
      "samples": 3272,
      "goal_error_m": 0.28724313456587347,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB87_-0706",
      "planner": "TA*-S",
      "status": "completed",
      "samples": 3183,
      "goal_error_m": 0.28567395649416455,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB88_-1417",
      "planner": "A*",
      "status": "completed",
      "samples": 3090,
      "goal_error_m": 0.26458450154887525,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB88_-1417",
      "planner": "TA*-S",
      "status": "completed",
      "samples": 3102,
      "goal_error_m": 0.28301032144092236,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB88_-0167",
      "planner": "A*",
      "status": "stuck",
      "samples": 2891,
      "goal_error_m": 10.329048979724575,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0,
      "stagnation_diagnostic": {
        "window_s": 10.0,
        "xy_net_displacement_m": 0.004006097292327659,
        "v_command_mean_m_s": 0.9950248756218906,
        "w_command_abs_mean_rad_s": 0.1649956333528573,
        "roll_abs_final_deg": 167.11136960843143,
        "pitch_abs_final_deg": 17.048164112044738
      }
    },
    {
      "patch": "08OB88_-0167",
      "planner": "TA*-S",
      "status": "stuck",
      "samples": 5430,
      "goal_error_m": 30.548497888149896,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0,
      "stagnation_diagnostic": {
        "window_s": 10.0,
        "xy_net_displacement_m": 0.029881162846267007,
        "v_command_mean_m_s": 0.0,
        "w_command_abs_mean_rad_s": 0.9950248756218906,
        "roll_abs_final_deg": 170.0752826120545,
        "pitch_abs_final_deg": 26.280991492972632
      }
    },
    {
      "patch": "08OB88_00332",
      "planner": "A*",
      "status": "completed",
      "samples": 3489,
      "goal_error_m": 0.2609872033492553,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    },
    {
      "patch": "08OB88_00332",
      "planner": "TA*-S",
      "status": "completed",
      "samples": 3427,
      "goal_error_m": 0.2918503473954353,
      "fallen_samples": 0,
      "out_of_bounds_samples": 0
    }
  ]
}
Frozen source, real Gazebo provenance, terminal recordings, path identity, finite data, command limits and completed-goal distances passed.
```

## experiments/gz_compare_report.py の集計表（そのまま）

以下はGazeboで実際に測定した軌跡から、比較スクリプトが出力した全文。運動学の試験用データは含めない。

```text
Six beaches x two planners; descriptive trends only, no hypothesis tests.
rollover: first recorded |roll| > 90 deg; recorded_status preserves the original mission status.
       patch planner    status  completed data_source  error  elapsed_s  deviation_mean_m  deviation_max_m  path_lethal_cells  roll_p95_actual_deg  pitch_p95_actual_deg  roll_max_actual_deg  pitch_max_actual_deg  climb_actual_m  map_length_xy  map_climb  map_mean_cost  map_p95_slope  map_p95_roll  map_max_roll  map_max_pitch_dir  roll_p95_recorded_xy_map_deg  pitch_p95_recorded_xy_map_deg recorded_status  rolled_over  rollover_t_s  rollover_elapsed_s  rollover_x_m  rollover_y_m
08OB86_00294      A* completed       True      gazebo    NaN        166         0.0155309         0.283747                  0              4.57977               3.20701              6.34223               7.33646         1.35143         166.45    2.09937       0.116112        5.10152       4.75077       6.12944            5.80548                       4.69694                        2.93522       completed        False           NaN                 NaN           NaN           NaN
08OB86_00294   TA*-S completed       True      gazebo    NaN      161.2         0.0110132         0.293225                  0              4.16851               2.23449              5.58198               6.51558        0.889737        160.949    1.29658      0.0993425        4.54547       4.20589       5.98096             4.2124                       4.21586                        2.25498       completed        False           NaN                 NaN           NaN           NaN
08OB86_-0205      A* completed       True      gazebo    NaN     157.45          0.267778          6.19138                  0              11.8057                6.9483              19.6117                10.297         2.79364        155.085    2.98103       0.175112        13.7217       12.7104        25.748            10.3288                        10.157                        6.75867       completed        False           NaN                 NaN           NaN           NaN
08OB86_-0205   TA*-S completed       True      gazebo    NaN        154         0.0698109          3.31719                  0              3.13187               1.88349              5.27948               5.86883        0.912171        156.831    1.13326      0.0794646        3.78309       3.18944       5.69173            9.61358                        3.0554                        2.02659       completed        False           NaN                 NaN           NaN           NaN
08OB87_-0706      A* completed       True      gazebo    NaN     163.55         0.0217786         0.266098                  0              5.14706               3.18229              6.40325               7.10212        0.721888        164.493    1.57973       0.129899        5.96148       5.12886        6.6874            6.96167                       5.14935                        3.59127       completed        False           NaN                 NaN           NaN           NaN
08OB87_-0706   TA*-S completed       True      gazebo    NaN     159.15        0.00647007         0.128161                  0              3.15048               2.63982              5.63635               5.22304        0.506069        159.351   0.812158      0.0835471        4.15879       3.34804       4.86051            4.61208                       3.34949                        3.03682       completed        False           NaN                 NaN           NaN           NaN
08OB88_-1417      A* completed       True      gazebo    NaN     154.45         0.0154969         0.227642                  0              5.21845               2.35925              9.30999               7.15519         1.23867        155.002    1.74114       0.115239        5.36712       5.08998       8.37479             5.8079                       5.09578                        2.50166       completed        False           NaN                 NaN           NaN           NaN
08OB88_-1417   TA*-S completed       True      gazebo    NaN     155.05        0.00410578          0.23445                  0              2.29267              0.807219              3.49959               3.37278         0.52038        155.199   0.733826      0.0526041         2.5868       2.41772       3.07078            3.11248                       2.38563                       0.820092       completed        False           NaN                 NaN           NaN           NaN
08OB88_-0167      A*  rollover      False      gazebo    NaN      144.5          0.843477           5.2174                 90              167.111               33.0629              176.682               43.7947         9.66845         157.68    8.10689       0.451117        33.7886       33.6112       39.1973            25.4503                       31.8871                        18.1473           stuck         True         138.9               133.8       155.523       138.025
08OB88_-0167   TA*-S  rollover      False      gazebo    NaN     271.45         0.0796587          1.28426                  9              13.2141                26.281               176.26                79.867         7.44885        289.767    7.90873       0.137976        10.2882       5.98149       18.0338            23.7975                       5.80491                        9.28437           stuck         True        265.35              260.25       196.387       141.841
08OB88_00332      A* completed       True      gazebo    NaN      174.4         0.0105396         0.285094                  0              4.04249               4.76705              8.38286               12.5081        0.281719        174.858   0.599038      0.0863766        5.70541        3.8628       6.83518            10.9966                       3.87505                        4.69552       completed        False           NaN                 NaN           NaN           NaN
08OB88_00332   TA*-S completed       True      gazebo    NaN      171.3        0.00999076          0.39661                  0              3.77867               4.55179              5.11535               9.66308        0.231823         170.97    0.38637      0.0749039        5.37827       3.75626       5.20394            9.60764                       3.69879                        4.28301       completed        False           NaN                 NaN           NaN           NaN

TA*-S minus A*: paired median differences (both completed, without rollover)
              metric  paired_completed  delta_median
           elapsed_s                 5         -3.45
    deviation_mean_m                 5    -0.0113911
     deviation_max_m                 5    0.00680795
   path_lethal_cells                 5             0
 roll_p95_actual_deg                 5      -1.99658
pitch_p95_actual_deg                 5     -0.972516
 roll_max_actual_deg                 5      -3.26751
pitch_max_actual_deg                 5      -2.84502
      climb_actual_m                 5     -0.461692
Climb sums positive recorded z increments without denoising; it includes physical/logging noise.
```

## 図

各図の左は両方法の実測軌跡、右は実測rollの時系列。6枚すべてを目視確認した。軌跡は各走行の終了時までを表示し、転倒した記録も残している。rollはEuler角で±180度で折り返す。

- [08OB86_00294](physical_run/report/08OB86_00294.png)（A*: completed、TA*-S: completed）

- [08OB86_-0205](physical_run/report/08OB86_-0205.png)（A*: completed、TA*-S: completed）

- [08OB87_-0706](physical_run/report/08OB87_-0706.png)（A*: completed、TA*-S: completed）

- [08OB88_-1417](physical_run/report/08OB88_-1417.png)（A*: completed、TA*-S: completed）

- [08OB88_-0167](physical_run/report/08OB88_-0167.png)（A*: rollover（原記録stuck）、TA*-S: rollover（原記録stuck））

- [08OB88_00332](physical_run/report/08OB88_00332.png)（A*: completed、TA*-S: completed）

監査の `fallen_samples` は、既存analyze_runの定義で「zが地図標高より1m以上低い記録数」を表す。rollによる反転した姿勢は別に読む。

## 解釈の範囲・残る制約

所要時間は記録の最終tと最初のtの差（シミュレーション秒）で、準備と静置を含めない。対の中央値は両方法が完走した砂浜だけで算出する。登りは記録zの正の増分をノイズ除去せず合計するため、車体の揺れも含む。地図の指標は計画経路に対する値、実測姿勢は走行記録からの値として区別する。接触セルは、実測xy軌跡が通過した地図上の通行不可セル数を既存analyze_runで数えたもの。

車体形状・摩擦・heightmap補間・水面の扱いは既存モデルの仮定を引き継ぐ。実砂での接地・沈下や実機の走行を検証したものではない。6砂浜だけの記述比較であり、有意差や一般的な性能保証は主張しない。Gazeboの版とPython環境は上の記録に固定して読む必要がある。

## 再実行

十分なディスク容量がある環境で、新しい出力先を指定する：

```bash
git switch codex/019-gazebo-compare
cd conference
bash ros2_jazzy/gz_checks/run_compare_checks.sh results/gazebo_compare/new_run
python3 experiments/gz_compare_report.py results/gazebo_compare/new_run
```

既存manifestがある保存先は上書きせず停止する。`THESIS_ROS_IMAGE` でイメージを変更できる。今回の原記録は `physical_run/`、最新のPython検証は `followup/tests/`、初回実装時の検証ログは `verification/` に保管している。
