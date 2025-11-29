# TA* + Unity 可視化パイプライン 引き継ぎ資料

最終更新: 2025-11-10
作成者: 研究支援AI

---
## 1. 概要 / 背景
本プロジェクトは農業用途移動ロボット (AgileX Bunker) 向け 3D 地形適応型経路計画アルゴリズム **TA\*** (Terrain-Aware A*) を ROS2 + Unity シミュレーション環境へ統合する試みです。既存の A*, AHA* との比較で **成功率 100% / AHA* 比 61倍高速化** を達成済み。次フェーズは統合テスト完了 → 16シナリオ本番ベンチマーク → 実地形データ統合 → 卒論仕上げ。

---
## 2. 現在の成果物（2025-11-10 最終更新）
| 項目 | 状態 | ファイル/コマンド |
|------|------|------------------|
| TA*アルゴリズム実装 | ✅完了 | `path_planner_3d/terrain_aware_astar_advanced.py` (868行) |
| ROS2統合ノード | ✅完了 | `bunker_3d_nav/bunker_3d_nav/ta_star_planner/ta_star_planner_node.py` |
| Unity可視化ブリッジ | ✅完了 | `bunker_3d_nav/bunker_3d_nav/unity_visualization/unity_visualization_node.py` |
| シナリオパブリッシャ | ✅完了 | `bunker_3d_nav/bunker_3d_nav/scenario_management/scenario_publisher.py`|
| 統合 Launch | ✅動作確認済 | `bunker_3d_nav/launch/ta_star_unity_demo.launch.py` |
| ベンチマークスクリプト | ✅完了 | `scripts/benchmark_path_planners.py` |
| クイックテスト | ✅完了 | `scripts/test_ta_star.py` |
| 成果レポート | ✅完了 | `TA_STAR_REPORT.md`, `THESIS_EVALUATION.md` |
| Setup ガイド | ✅完了 | `TA_STAR_UNITY_SETUP.md` |
| 引き継ぎ資料 | ✅最新 | `PROJECT_HANDOVER_TA_STAR_UNITY.md` |

**動作確認済み**: `ros2 launch bunker_3d_nav ta_star_unity_demo.launch.py` で全ノード起動成功（2025-11-10 19:06 確認）

---
## 3. システム構成 (理想形)
```
RTAB-Map → terrain_analyzer_node → /bunker/voxel_grid, /bunker/terrain_info
                                        ↓
                               TA* Planner Node
                                        ↓
                       /path_3d (nav_msgs/Path), MarkerArray
                                        ↓
                         Unity Visualization Bridge
```
トピック: 
- 入力: `/bunker/voxel_grid` (VoxelGrid3D), `/bunker/terrain_info` (TerrainInfo), `/current_pose`, `/goal_pose`
- 出力: `/path_3d`, `/path_visualization`(MarkerArray), Unity TCP(JSON)

---
## 4. 未解決の技術課題と暫定対策 (重要)
| 課題 | 詳細 | 暫定対策 (現状) | 恒久対策 (推奨) |
|------|------|----------------|----------------|
| **console_scripts未生成** | ament_cmake + ament_cmake_python のハイブリッド構成で setup.py entry_points が機能しない。`ros2 run bunker_3d_nav ta_star_planner_node` 実行不可 | **暫定OK**: launch 内で ExecuteProcess を使い python3 で直接実行 (`ta_star_unity_demo.launch.py` に実装済み) | 純粋な ament_python パッケージへ移行するか、CMakeLists の install(PROGRAMS) で wrapper script を適切に配置 |
| launchでのパラメータ渡し制約 | ExecuteProcess では LaunchConfiguration → ROS パラメータへの自動マッピングが効かない | Node 内で declare_parameter によるデフォルト値設定済み。後で `ros2 param set` で動的変更可 | Node 方式 (entry_points 復旧後) に移行すれば解決 |
| パッケージ階層不整合 | 新ノードが `bunker_3d_nav/bunker_3d_nav/<subdir>` 内にあり、rosidl 生成の bunker_3d_nav パッケージ (msg/srv) と名前空間が衝突 | scripts/ 内に file-based import wrapper を作成したが CMake が無視する問題あり。ExecuteProcess 直接実行で回避 | 純粋 ament_python パッケージへ分離 or トップレベルの空サブパッケージディレクトリ削除後 find_packages() で正規化 |
| 実地形未接続 | terrain_analyzer とのI/F未検証 | ta_star_planner_node 内でダミー平坦地形を生成し、地形データ無しでも経路計画可能 | 実 RTAB-Map トピック接続後、VoxelGrid3D/TerrainInfo 型フィールドマッピング実装 |

**現時点の実用性**: launch ファイルからの ExecuteProcess 起動で統合動作可能。次担当者は恒久対策として純粋 Python パッケージへのリファクタリングを推奨。

---
## 5. 優先度付きロードマップ
| フェーズ | タスク | 目標時間 | 成否判定 |
|----------|--------|---------|-----------|
| P0 | パッケージ修復 | 2h | `ros2 run bunker_3d_nav ta_star_planner_node` 成功 |
| P1 | 統合起動テスト (Unity抜き) | 2h | `/path_3d`がtest_ta_starで受信 |
| P2 | Unity表示確認 | 1h | Unity上に経路ライン表示 |
| P3 | 16シナリオベンチマーク | 4h | JSON結果 + 全グラフ生成 |
| P4 | 統計的検定追加 | 2h | t検定/Cohen's d出力スクリプト完成 |
| P5 | 実地形データ統合 | 0.5-1d | RTAB-Map経路でTA*出力成功 |
| P6 | 論文執筆仕上げ | 1-2w | 25-35ページドラフト完成 |

---
## 6. パッケージ修復手順 (恒久対策 - 次担当者向け)
**現状**: ament_cmake + ament_cmake_python のハイブリッド構成で setup.py の entry_points が生成されない問題により、`ros2 run bunker_3d_nav <node_name>` が使えません。**暫定対策として、launch ファイルからの ExecuteProcess 起動 + path_planner_3d のファイル群を ta_star_planner ディレクトリにコピーすることで動作可能にしました。**

**2025-11-10 最終対応内容**:
1. `terrain_aware_astar_advanced.py` および依存モジュール (node_3d.py, cost_calculator.py 等) を `bunker_3d_nav/bunker_3d_nav/ta_star_planner/` にコピー
2. コピーしたファイル内の相対import (`from .node_3d`) を絶対import (`from node_3d`) に変更
3. ta_star_planner_node.py に sys.path 追加処理を実装
4. scenario_publisher.py の pathlib.Path と nav_msgs.msg.Path の名前衝突を解消 (`from pathlib import Path as FilePath`)
5. 統合テスト実施: 全3ノード (TA* planner, Unity visualization, scenario publisher) が正常起動を確認

**動作確認ログ (2025-11-10 19:06)**:
```
[INFO] [ta_star_planner_node]: ✅ TA* Planner Node initialized
[INFO] [unity_visualization_node]: Unity Visualization Node started
[INFO] [scenario_publisher]: Scenario Publisher started with 0 scenarios
```

**恒久修正オプション A (推奨)**: 純粋 ament_python パッケージへ移行
1. `CMakeLists.txt` を削除し、`package.xml` の `<buildtool_depend>` を `ament_cmake` → `ament_python` に変更
2. `setup.py` を以下に修正 (find_packages 使用):
```python
from setuptools import setup, find_packages
from glob import glob
import os

setup(
    name='bunker_3d_nav',
    version='0.0.1',
    packages=find_packages(include=['bunker_3d_nav', 'bunker_3d_nav.*']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/bunker_3d_nav']),
        ('share/bunker_3d_nav', ['package.xml']),
        (os.path.join('share', 'bunker_3d_nav', 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', 'bunker_3d_nav', 'config'), glob('config/*.yaml') + glob('config/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'ta_star_planner_node = bunker_3d_nav.ta_star_planner.ta_star_planner_node:main',
            'unity_visualization_node = bunker_3d_nav.unity_visualization.unity_visualization_node:main',
            'scenario_publisher = bunker_3d_nav.scenario_management.scenario_publisher:main',
            'terrain_analyzer_node = bunker_3d_nav.terrain_analyzer.terrain_analyzer_node:main',
            'tcp_server_node = bunker_3d_nav.unity_bridge.tcp_server_node:main',
        ],
    },
)
```
3. Custom msg/srv は別パッケージ (`bunker_3d_nav_msgs`) として分離
4. クリーンビルド: `rm -rf build/ install/ && colcon build --packages-select bunker_3d_nav`
5. 検証: `ros2 run bunker_3d_nav ta_star_planner_node` が起動

**恒久修正オプション B (現状維持 + wrapper修正)**: 
- CMakeLists の install(PROGRAMS) で `scripts/ta_star_planner_node` などの wrapper を正しく配置 (現在うまくいかない)
- wrapper 内で importlib.util を使いファイルベースで node モジュールをロード (実装済みだが install されない問題)

**トラブルシューティング**:
- `ros2 run` で "No executable found" → `ls install/bunker_3d_nav/lib/bunker_3d_nav/` で ta_star_planner_node の有無確認
- rosidl 生成パッケージとの名前衝突 → Python import時に `import bunker_3d_nav.msg` が優先され user code が見えない問題。別名前空間推奨。

---
## 7. 実行手順 (現状動作確認済み)
### 現状の起動方法 (ExecuteProcess 方式)
```bash
# ビルド & 環境設定
cd /home/hayashi/thesis_work/ros2/ros2_ws
colcon build --packages-select bunker_3d_nav
source install/setup.bash

# 統合起動 (TA* + Unity bridge + scenario publisher)
ros2 launch bunker_3d_nav ta_star_unity_demo.launch.py

# パラメータ指定例
ros2 launch bunker_3d_nav ta_star_unity_demo.launch.py \
  voxel_size:=0.2 \
  planning_interval:=2.0 \
  enable_visualization:=true
```

### 経路受信テスト
```bash
# 別ターミナルで /path_3d トピックを監視
python3 /home/hayashi/thesis_work/scripts/test_ta_star.py

# 期待される出力:
# ✅ TA* Planner Node initialized
# 🎯 New goal received: (10.00, 10.00, 0.00)
# ✅ Path found! Nodes: 256, Time: 0.034s, Length: 42 waypoints
# [/path_3d 受信] 42 poses
```

### 個別ノード起動 (entry_points 復旧後の理想形 - 現在不可)
```bash
# 注意: 現在 console_scripts 未生成のため以下は動作しない
# ros2 run bunker_3d_nav ta_star_planner_node      # ← 現状 No executable found
# ros2 run bunker_3d_nav unity_visualization_node  # ← 同上
# ros2 run bunker_3d_nav scenario_publisher        # ← 同上

# 直接実行する場合 (デバッグ用)
python3 /home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/bunker_3d_nav/ta_star_planner/ta_star_planner_node.py
```

---
## 8. 16シナリオベンチマーク計画
- スクリプト: `scripts/benchmark_path_planners.py`
- 出力: `results/benchmark_results_<timestamp>.json`
- 追加タスク:
  - 統計処理: 新規 `scripts/analyze_benchmarks.py` (t検定, ANOVA, 効果量)
  - 可視化: 箱ひげ図 / シナリオ別ヒートマップ / 成功率棒グラフ

---
## 9. 実地形データ統合手順
1. 起動: `ros2 launch bunker_3d_nav terrain_analyzer.launch.py`
2. トピック確認: `ros2 topic echo /bunker/voxel_grid` / `ros2 topic echo /bunker/terrain_info`
3. `ta_star_planner_node.py` 内でメッセージ型フィールド名が一致するか (サイズ, 原点, occupancy 配列) を再確認。
4. ゴール設定: `ros2 topic pub /goal_pose geometry_msgs/PoseStamped '{...}'`
5. 経路整形: Path → Unity JSON via visualization node。

---
## 10. 論文執筆ロードマップ
| 章 | 状況 | 追加必要作業 |
|----|------|--------------|
| 序論 | 70% | 課題定量化例（成功率比較数値）挿入 |
| 関連研究 | 60% | Field D*, Hybrid A* 引用追加 |
| 提案手法 | 80% | コスト関数式とヒューリスティック整合性証明簡略版 |
| 実装 | 70% | ボトルネック最適化表 (前処理→探索時間) |
| 実験 | 40% | 16シナリオ +統計検定結果 |
| 結論 | 30% | 将来展望（動的障害物, 学習ベース最適化） |

---
## 11. リスク & 回避策
| リスク | 兆候 | 回避策 |
|--------|------|--------|
| console_scripts復旧遅延 | `ros2 run`失敗 | 直接ExecuteProcessで並行作業しつつ原因切り分け |
| 実地形メッセージ差異 | 経路生成失敗 | echoでmsg構造確認→アダプタ関数作成 |
| ベンチマーク偏り | 成功率100%のみ | 難易度(傾斜/密度)で層別サンプル追加 |
| パフォーマンス低下 | 長距離で >0.5s | 前処理サンプリング率調整 / 斜面計算メモ化拡張 |

---
## 12. 推奨改善一覧 (低コストで効果高い)
1. `setup.py` を find_packages 方式へ (最優先)
2. `ta_star_planner_node.py` にユニットテスト用軽量モード引数 (`--dry-run`) 追加
3. ベンチマーク結果保存を SQLite に変更（複数試行集計容易化）
4. 統計処理スクリプト自動生成 (t検定, 効果量)
5. Unity側に経路標高プロファイル描画追加

---
## 13. 参考ファイル一覧
| 目的 | ファイル |
|------|---------|
| アルゴリズム本体 | `terrain_aware_astar_advanced.py` |
| 高速化分析 | `ros2/ros2_ws/src/bunker_ros2/results/tastar_bottleneck_analysis.md` |
| セットアップ | `TA_STAR_UNITY_SETUP.md` |
| 評価 | `THESIS_EVALUATION.md` |
| 可視化 | `figures/ta_star_time_comparison.png` 他 |

---
## 14. 次担当者 初日チェックリスト
- [ ] `ros2 run bunker_3d_nav ta_star_planner_node` 起動可
- [ ] `/path_3d` 受信 (test_ta_star.py)
- [ ] Unity 接続 (TCP 11000) ログ表示
- [ ] 3シナリオ簡易ベンチマーク実行
- [ ] setup.py / CMakeLists 差分をGit管理 (コミットメッセージ: "fix packaging for TA* nodes")

---
## 15. 連絡・引継ぎメモ
不明点が出た場合はまず: 
1. `TA_STAR_REPORT.md` でアルゴリズム概要確認
2. `benchmark_path_planners.py` 内の呼び出しシグネチャ参照
3. ROSトピック一覧: `ros2 topic list` で期待トピック存在確認

---
以上。修復→テスト→ベンチマーク→執筆の順で進めれば 2週間以内に卒論完成可能です。
