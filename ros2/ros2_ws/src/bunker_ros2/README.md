# Bunker 3D Navigation Package

## 概要

Bunker 3D Navigation Packageは、不整地環境における3次元経路計画システムです。RTAB-Mapの3D点群データを活用し、地形の傾斜を考慮した安全な経路計画を実現します。

## 機能

- **3D地形解析**: 点群データからボクセルグリッドを生成し、地形情報を抽出
- **3D経路計画**: A*アルゴリズムによる3次元経路計画
- **コスト関数**: 傾斜、障害物、安定性を考慮したコスト計算
- **経路平滑化**: 生成された経路の平滑化処理
- **評価システム**: 経路計画性能の評価と可視化

## システム要件

- ROS2 Humble
- Python 3.10+
- Unity 2021.3+ (シミュレーション用)
- Open3D
- NumPy, SciPy
- Matplotlib, Seaborn

## インストール

### 1. 依存関係のインストール

```bash
pip3 install open3d numpy scipy matplotlib seaborn pandas
```

### 2. ROS2パッケージのビルド

```bash
cd ~/thesis_work/ros2/ros2_ws
colcon build --packages-select bunker_3d_nav
source install/setup.bash
```

## 使用方法

### 1. 地形解析ノードの起動

```bash
ros2 launch bunker_3d_nav terrain_analyzer.launch.py
```

### 2. 3D経路計画ノードの起動

```bash
ros2 launch bunker_3d_nav path_planner_3d.launch.py
```

### 3. 全システムの起動

```bash
ros2 launch bunker_3d_nav full_system.launch.py
```

### 4. Unityシミュレーション環境

UnityプロジェクトでTerrainWorldManager.csを使用して不整地ワールドを生成：

```csharp
// 5つの地形シナリオ
- FlatWithObstacles: 平坦地形+障害物
- GentleSlope: 緩傾斜地形（10-15度）
- SteepSlope: 急傾斜地形（20-30度）
- DenseObstacles: 障害物密集
- MixedTerrain: 複合地形（最も現実的）
```

## 設定

### パラメータ設定

設定ファイルは`config/`ディレクトリにあります：

- `terrain_params.yaml`: 地形解析パラメータ
- `planner_params.yaml`: 経路計画パラメータ

### 主要パラメータ

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `voxel_size` | 0.1 | ボクセルサイズ [m] |
| `max_slope_angle` | 30.0 | 最大走行可能傾斜 [度] |
| `weight_slope` | 3.0 | 傾斜重み |
| `weight_obstacle` | 5.0 | 障害物重み |
| `weight_stability` | 4.0 | 安定性重み |

## 評価

### 評価スクリプトの実行

```bash
# ROSbagからの評価
python3 scripts/evaluation/evaluate_path.py <bag_file> --output-dir results

# 結果の可視化
python3 scripts/evaluation/plot_results.py results --output-dir plots
```

### 評価指標

- **経路長**: 生成された経路の総距離
- **最大傾斜角**: 経路上の最大傾斜角度
- **平均傾斜角**: 経路上の平均傾斜角度
- **総コスト**: 距離、傾斜、障害物、安定性の総合コスト
- **計算時間**: 経路計画にかかった時間
- **成功率**: ゴール到達の成功率

## アーキテクチャ

```
RTAB-Map → Terrain Analyzer → Path Planner 3D → Robot Control
    ↓              ↓                ↓
PointCloud2 → VoxelGrid3D → Path → cmd_vel
```

## 開発状況

- [x] プロジェクト構造作成
- [x] カスタムメッセージ定義
- [x] Unity不整地ワールド作成
- [x] ROSノードスケルトン実装
- [x] 評価システム雛形作成
- [ ] 地形解析実装
- [ ] 3D経路計画実装
- [ ] 統合テスト
- [ ] 実機検証

## トラブルシューティング

### よくある問題

1. **インポートエラー**: パッケージがビルドされていない
   ```bash
   colcon build --packages-select bunker_3d_nav
   source install/setup.bash
   ```

2. **メッセージが見つからない**: カスタムメッセージが生成されていない
   ```bash
   colcon build --packages-select bunker_3d_nav
   ```

3. **Unityでスクリプトが動作しない**: TerrainWorldManager.csが正しく配置されていない

### ログレベル設定

```bash
# デバッグログを有効にする
ros2 launch bunker_3d_nav full_system.launch.py enable_debug:=true
```

## 貢献

このプロジェクトは卒論研究の一部です。問題報告や改善提案は歓迎します。

## ライセンス

MIT License

## 連絡先

- 作成者: Hayashi
- メール: hayashi@example.com
- プロジェクト: 不整地環境における3D経路計画研究
