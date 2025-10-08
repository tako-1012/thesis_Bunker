# 開発者向けドキュメント

## 目次
1. [開発環境セットアップ](#開発環境セットアップ)
2. [ビルド手順](#ビルド手順)
3. [デバッグ方法](#デバッグ方法)
4. [よくあるエラーと解決法](#よくあるエラーと解決法)
5. [コーディング規約](#コーディング規約)
6. [テスト実行方法](#テスト実行方法)
7. [パフォーマンス最適化](#パフォーマンス最適化)

## 開発環境セットアップ

### 必要なソフトウェア
- **ROS2 Humble**: ロボットオペレーティングシステム
- **Python 3.10+**: プログラミング言語
- **Open3D**: 3D点群処理ライブラリ
- **NumPy**: 数値計算ライブラリ
- **Matplotlib**: 可視化ライブラリ
- **pytest**: テストフレームワーク

### インストール手順

#### 1. ROS2 Humbleのインストール
```bash
# Ubuntu 22.04の場合
sudo apt update
sudo apt install ros-humble-desktop
sudo apt install ros-humble-navigation2
sudo apt install ros-humble-rtabmap-ros
```

#### 2. Python依存関係のインストール
```bash
pip3 install open3d numpy scipy matplotlib seaborn pandas
pip3 install pytest pytest-cov
pip3 install rclpy
```

#### 3. ワークスペースのセットアップ
```bash
cd ~/thesis_work/ros2/ros2_ws
colcon build --packages-select bunker_3d_nav
source install/setup.bash
```

### 開発環境の確認
```bash
# ROS2の動作確認
ros2 node list

# Pythonパッケージの確認
python3 -c "import open3d as o3d; print(o3d.version)"
python3 -c "import numpy as np; print(np.version.version)"
```

## ビルド手順

### 基本的なビルド
```bash
cd ~/thesis_work/ros2/ros2_ws
colcon build --packages-select bunker_3d_nav
```

### デバッグビルド
```bash
colcon build --packages-select bunker_3d_nav --cmake-args -DCMAKE_BUILD_TYPE=Debug
```

### リリースビルド
```bash
colcon build --packages-select bunker_3d_nav --cmake-args -DCMAKE_BUILD_TYPE=Release
```

### クリーンビルド
```bash
rm -rf build/ install/ log/
colcon build --packages-select bunker_3d_nav
```

## デバッグ方法

### 1. ログレベルの設定
```python
# ノード内でログレベルを設定
self.get_logger().set_level(rclpy.logging.LoggingSeverity.DEBUG)
```

### 2. デバッグツールの使用
```bash
# ボクセルグリッド可視化
ros2 run bunker_3d_nav visualize_voxel_grid.py

# 3D経路可視化
ros2 run bunker_3d_nav plot_path_3d.py --sample

# 地形解析デバッグ
ros2 run bunker_3d_nav debug_terrain_analyzer.py --debug-level 2
```

### 3. プロファイリング
```python
import cProfile
import pstats

# プロファイリングの実行
profiler = cProfile.Profile()
profiler.enable()

# 実行したいコード
your_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats()
```

### 4. メモリ使用量の監視
```python
import psutil
import os

# プロセスのメモリ使用量を取得
process = psutil.Process(os.getpid())
memory_info = process.memory_info()
print(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
```

## よくあるエラーと解決法

### 1. ビルドエラー

#### エラー: "Package 'bunker_3d_nav' not found"
**原因**: パッケージが正しくビルドされていない
**解決法**:
```bash
cd ~/thesis_work/ros2/ros2_ws
colcon build --packages-select bunker_3d_nav
source install/setup.bash
```

#### エラー: "ImportError: No module named 'bunker_3d_nav'"
**原因**: Pythonパスが正しく設定されていない
**解決法**:
```bash
export PYTHONPATH=$PYTHONPATH:~/thesis_work/ros2/ros2_ws/install/bunker_3d_nav/lib/python3.10/site-packages
```

### 2. 実行時エラー

#### エラー: "No such file or directory: 'rtabmap/cloud_map'"
**原因**: RTAB-Mapが起動していない
**解決法**:
```bash
ros2 launch bunker_nav kinect_rtabmap.launch.py
```

#### エラー: "Open3D version mismatch"
**原因**: Open3Dのバージョンが古い
**解決法**:
```bash
pip3 install --upgrade open3d
```

### 3. パフォーマンス問題

#### 問題: 処理が遅い
**原因**: ボクセルサイズが小さすぎる
**解決法**: ボクセルサイズを大きくする（0.1 → 0.2）

#### 問題: メモリ使用量が多い
**原因**: データのコピーが多すぎる
**解決法**: 参照渡しを使用、不要なデータを削除

## コーディング規約

### Python
- **スタイル**: PEP 8準拠
- **Type hints**: 必須
- **Docstring**: Google Style
- **命名規則**:
  - 関数・変数: `snake_case`
  - クラス: `PascalCase`
  - 定数: `UPPER_CASE`

### ROS2ノード
- **ノード名**: 明確で一意
- **トピック名**: 階層的で一貫性
- **パラメータ**: 適切なデフォルト値
- **エラーハンドリング**: 必須

### テスト
- **テスト関数**: `test_` で始まる
- **アサーション**: 明確で具体的
- **モック**: 適切に使用
- **カバレッジ**: 80%以上

## テスト実行方法

### 単体テスト
```bash
cd ~/thesis_work/ros2/bunker_ros2/bunker_3d_nav
pytest test/
```

### 特定のテスト
```bash
pytest test/test_voxel_grid_processor.py::TestVoxelGridProcessor::test_initialization
```

### カバレッジ付きテスト
```bash
pytest --cov=bunker_3d_nav test/
```

### 統合テスト
```bash
ros2 launch bunker_3d_nav full_system.launch.py
```

## パフォーマンス最適化

### 1. アルゴリズムの最適化
- **ボクセルサイズ**: 適切なサイズの選択
- **探索空間**: 不要な領域の除外
- **データ構造**: 効率的なデータ構造の使用

### 2. メモリ最適化
- **参照渡し**: コピーを避ける
- **メモリプール**: 頻繁な割り当てを避ける
- **ガベージコレクション**: 適切なタイミングで実行

### 3. 並列処理
- **マルチスレッド**: CPU集約的な処理
- **マルチプロセス**: メモリ集約的な処理
- **GPU**: 可能な場合はGPUを使用

### 4. プロファイリング
```bash
# プロファイリングの実行
python3 -m cProfile -o profile_output.prof your_script.py

# 結果の表示
python3 -c "import pstats; pstats.Stats('profile_output.prof').sort_stats('cumulative').print_stats()"
```

## トラブルシューティング

### 1. システムの状態確認
```bash
# ROS2ノードの確認
ros2 node list

# トピックの確認
ros2 topic list

# メッセージの確認
ros2 topic echo /rtabmap/cloud_map --once
```

### 2. ログの確認
```bash
# ログファイルの確認
tail -f ~/.ros/log/latest/ros2.log

# 特定のノードのログ
ros2 node info /terrain_analyzer
```

### 3. リソースの確認
```bash
# CPU使用率
top -p $(pgrep -f bunker_3d_nav)

# メモリ使用量
ps aux | grep bunker_3d_nav

# ディスク使用量
df -h
```

## 貢献ガイド

### 1. コードの提出
- **ブランチ**: 機能ごとにブランチを作成
- **コミット**: 明確なコミットメッセージ
- **プルリクエスト**: 詳細な説明を記載

### 2. コードレビュー
- **機能性**: 正しく動作するか
- **パフォーマンス**: 効率的か
- **可読性**: 理解しやすいか
- **テスト**: 適切にテストされているか

### 3. 文書化
- **README**: 使用方法の説明
- **API**: 関数・クラスの説明
- **例**: 使用例の提供

## 参考資料

### 公式ドキュメント
- [ROS2 Documentation](https://docs.ros.org/en/humble/)
- [Open3D Documentation](http://www.open3d.org/docs/)
- [Python Documentation](https://docs.python.org/3/)

### 技術ブログ
- [ROS2 Best Practices](https://roboticsbackend.com/ros2-best-practices/)
- [Open3D Tutorials](http://www.open3d.org/docs/latest/tutorial/)

### コミュニティ
- [ROS2 Discourse](https://discourse.ros.org/)
- [Open3D GitHub](https://github.com/isl-org/Open3D)
