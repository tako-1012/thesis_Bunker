# 重要ファイル一覧
以下は本研究の重要なソース・データ・結果ファイルのワークスペース内パス。

- データ生成 / シナリオ
  - [scripts/create_terrain_scenarios.py](scripts/create_terrain_scenarios.py)
  - [terrain_test_scenarios/hill_detour_data.npz](terrain_test_scenarios/hill_detour_data.npz)
  - [terrain_test_scenarios/hill_detour_meta.json](terrain_test_scenarios/hill_detour_meta.json)

- プランナー実装
  - [ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py](ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py)
  - [ros2/ros2_ws/src/path_planner_3d/path_planner_3d/field_d_hybrid.py](ros2/ros2_ws/src/path_planner_3d/path_planner_3d/field_d_hybrid.py)

- 実験・可視化スクリプト
  - [scripts/run_terrain_experiments.py](scripts/run_terrain_experiments.py)
  - [scripts/tune_terrain_astar.py](scripts/tune_terrain_astar.py)
  - [scripts/update_and_plot_terrain_costs.py](scripts/update_and_plot_terrain_costs.py)

- 結果（JSON・解析）
  - [benchmark_results/terrain_methods_comparison.json](benchmark_results/terrain_methods_comparison.json)
  - [benchmark_results/terrain_astar_tuning.json](benchmark_results/terrain_astar_tuning.json)
  - [benchmark_results/hill_detour_path_analysis.json](benchmark_results/hill_detour_path_analysis.json)

- 生成図（figures/） — 論文用に高解像度出力済み
  - [figures/terrain_comparison_hill_detour.png](figures/terrain_comparison_hill_detour.png)
  - [figures/terrain_cost_comparison_hill_detour.png](figures/terrain_cost_comparison_hill_detour.png)
  - [figures/path_detail_comparison.png](figures/path_detail_comparison.png)
  - [figures/elevation_profile_comparison.png](figures/elevation_profile_comparison.png)
  - その他: `figures/terrain_comparison_roughness_avoidance.png`, `figures/terrain_comparison_combined_terrain.png`

- 補助ファイル
  - [README.md](README.md)
  - [scripts/README_experiments.md] (作成推奨)

※ 再現性のため、`scripts/` のコマンド順を `thesis_guide.md` に記載しています。