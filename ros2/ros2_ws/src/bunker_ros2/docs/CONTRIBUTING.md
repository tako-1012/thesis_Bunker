# コントリビューションガイド

## 目次
1. [コーディング規約](#コーディング規約)
2. [コミットメッセージ規約](#コミットメッセージ規約)
3. [プルリクエストの方法](#プルリクエストの方法)
4. [テスト要件](#テスト要件)
5. [文書化要件](#文書化要件)
6. [レビュープロセス](#レビュープロセス)

## コーディング規約

### Python

#### スタイル
- **PEP 8準拠**: Pythonの標準コーディング規約に従う
- **行の長さ**: 最大88文字（Black formatter準拠）
- **インデント**: 4スペース
- **文字エンコーディング**: UTF-8

#### 命名規則
```python
# 関数・変数: snake_case
def calculate_slope_angle():
    max_slope_angle = 30.0

# クラス: PascalCase
class VoxelGridProcessor:
    pass

# 定数: UPPER_CASE
MAX_SLOPE_ANGLE = 30.0

# プライベート: _leading_underscore
def _internal_method():
    pass
```

#### Type Hints
```python
from typing import List, Dict, Optional, Tuple

def process_pointcloud(self, msg: PointCloud2) -> Dict[str, Any]:
    """点群データを処理"""
    pass

def calculate_slopes(self, voxel_grid: np.ndarray, 
                    normals: np.ndarray) -> Dict[str, Any]:
    """傾斜角度を計算"""
    pass
```

#### Docstring
```python
def calculate_slope_angle(self, normal_vector: np.ndarray) -> float:
    """法線ベクトルから傾斜角度を計算
    
    Args:
        normal_vector: 法線ベクトル (3次元)
        
    Returns:
        傾斜角度 [度]
        
    Raises:
        ValueError: 無効な法線ベクトルの場合
        
    Example:
        >>> normal = np.array([0.0, 0.0, 1.0])
        >>> angle = calculator.calculate_slope_angle(normal)
        >>> print(angle)
        0.0
    """
    pass
```

### ROS2ノード

#### ノード構造
```python
#!/usr/bin/env python3
"""
モジュールの説明
"""

import rclpy
from rclpy.node import Node
from typing import Optional
import numpy as np

class ExampleNode(Node):
    """ノードの説明"""
    
    def __init__(self) -> None:
        super().__init__('example_node')
        
        # パラメータ宣言
        self.declare_parameter('param_name', default_value)
        
        # Subscriber
        self.subscription = self.create_subscription(
            MessageType,
            'topic_name',
            self.callback,
            10
        )
        
        # Publisher
        self.publisher = self.create_publisher(
            MessageType,
            'topic_name',
            10
        )
        
        self.get_logger().info('Node initialized')
    
    def callback(self, msg: MessageType) -> None:
        """コールバック関数"""
        try:
            # 処理
            pass
        except Exception as e:
            self.get_logger().error(f'Error: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = ExampleNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
```

#### エラーハンドリング
```python
def process_data(self, data: np.ndarray) -> Optional[np.ndarray]:
    """データを処理"""
    try:
        # 入力検証
        if data is None or len(data) == 0:
            self.get_logger().warn('Empty data received')
            return None
        
        # 処理
        result = self._process(data)
        
        # 結果検証
        if result is None:
            self.get_logger().error('Processing failed')
            return None
        
        return result
        
    except ValueError as e:
        self.get_logger().error(f'Invalid input: {e}')
        return None
    except RuntimeError as e:
        self.get_logger().error(f'Runtime error: {e}')
        return None
    except Exception as e:
        self.get_logger().error(f'Unexpected error: {e}')
        return None
```

### C++

#### スタイル
- **Google C++ Style Guide準拠**
- **インデント**: 2スペース
- **行の長さ**: 最大100文字

#### 命名規則
```cpp
// 関数・変数: snake_case
void calculate_slope_angle();
int max_slope_angle = 30;

// クラス: PascalCase
class VoxelGridProcessor {
public:
    // メンバ変数: trailing_underscore_
    int voxel_size_;
    
    // メソッド: snake_case
    void process_pointcloud();
};

// 定数: kConstantName
const int kMaxSlopeAngle = 30;
```

## コミットメッセージ規約

### 形式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type
- **feat**: 新機能
- **fix**: バグ修正
- **docs**: 文書の変更
- **style**: コードスタイルの変更
- **refactor**: リファクタリング
- **test**: テストの追加・修正
- **chore**: ビルドプロセス、補助ツールの変更

### Scope
- **terrain**: 地形解析モジュール
- **path**: 経路計画モジュール
- **evaluation**: 評価システム
- **docs**: 文書
- **test**: テスト
- **ci**: CI/CD

### 例
```
feat(terrain): add slope calculation for voxel grid

- Implement slope angle calculation from normal vectors
- Add stability assessment for robot navigation
- Include unit tests for slope calculation

Closes #123
```

```
fix(path): resolve memory leak in A* algorithm

- Fix memory allocation in neighbor search
- Add proper cleanup in destructor
- Update memory usage tests

Fixes #456
```

```
docs(api): update VoxelGridProcessor documentation

- Add detailed method descriptions
- Include usage examples
- Fix parameter documentation

Refs #789
```

## プルリクエストの方法

### 1. ブランチ作成
```bash
# メインブランチから最新を取得
git checkout main
git pull origin main

# 機能ブランチを作成
git checkout -b feature/terrain-slope-calculation
```

### 2. 開発
```bash
# 変更をコミット
git add .
git commit -m "feat(terrain): add slope calculation"

# 定期的にプッシュ
git push origin feature/terrain-slope-calculation
```

### 3. プルリクエスト作成
- GitHubのWebインターフェースを使用
- タイトル: コミットメッセージのsubject部分
- 説明: 変更内容の詳細説明

### 4. プルリクエストテンプレート
```markdown
## 概要
このプルリクエストの概要を記述

## 変更内容
- 変更点1
- 変更点2
- 変更点3

## テスト
- [ ] 単体テストが通る
- [ ] 統合テストが通る
- [ ] 手動テストを実施

## チェックリスト
- [ ] コードがコーディング規約に従っている
- [ ] 適切なテストが追加されている
- [ ] 文書が更新されている
- [ ] 破壊的変更がない

## 関連Issue
Closes #123
```

## テスト要件

### 1. 単体テスト
```python
import pytest
import numpy as np
from unittest.mock import Mock, patch

class TestVoxelGridProcessor:
    """VoxelGridProcessorのテスト"""
    
    def setUp(self):
        """テストの準備"""
        self.processor = VoxelGridProcessor(voxel_size=0.1)
    
    def test_initialization(self):
        """初期化のテスト"""
        assert self.processor.voxel_size == 0.1
        assert self.processor.ground_normal_threshold == 80.0
    
    def test_process_pointcloud_success(self):
        """正常な点群処理のテスト"""
        # テストデータの準備
        mock_msg = Mock(spec=PointCloud2)
        
        # モックの設定
        with patch.object(self.processor, '_ros_to_numpy') as mock_convert:
            mock_convert.return_value = np.array([[0, 0, 0], [1, 1, 1]])
            
            result = self.processor.process_pointcloud(mock_msg)
            
            assert 'voxel_grid' in result
            assert 'classified_voxels' in result
    
    def test_process_pointcloud_empty(self):
        """空の点群のテスト"""
        mock_msg = Mock(spec=PointCloud2)
        
        with patch.object(self.processor, '_ros_to_numpy') as mock_convert:
            mock_convert.return_value = np.array([])
            
            result = self.processor.process_pointcloud(mock_msg)
            
            assert result['metadata']['point_count'] == 0
```

### 2. 統合テスト
```python
class TestIntegration:
    """統合テスト"""
    
    def test_terrain_analysis_pipeline(self):
        """地形解析パイプラインのテスト"""
        # テストデータの準備
        pointcloud_data = self.create_sample_pointcloud()
        
        # 地形解析の実行
        processor = VoxelGridProcessor()
        terrain_data = processor.process_pointcloud(pointcloud_data)
        
        calculator = SlopeCalculator()
        slope_data = calculator.calculate_slopes(
            terrain_data['voxel_grid'],
            terrain_data['normals']
        )
        
        # 結果の検証
        assert 'slopes' in slope_data
        assert 'statistics' in slope_data
        assert slope_data['statistics']['avg_slope'] >= 0
```

### 3. パフォーマンステスト
```python
import time

def test_performance():
    """パフォーマンステスト"""
    processor = VoxelGridProcessor()
    
    # 大きな点群データを作成
    large_pointcloud = create_large_pointcloud(10000)
    
    # 処理時間を測定
    start_time = time.time()
    result = processor.process_pointcloud(large_pointcloud)
    processing_time = time.time() - start_time
    
    # パフォーマンス要件をチェック
    assert processing_time < 1.0  # 1秒以内
    assert result is not None
```

## 文書化要件

### 1. コードコメント
```python
def calculate_slope_angle(self, normal_vector: np.ndarray) -> float:
    """法線ベクトルから傾斜角度を計算
    
    この関数は、3次元の法線ベクトルから地面の傾斜角度を計算します。
    傾斜角度は、法線ベクトルと垂直方向（Z軸）のなす角として定義されます。
    
    Args:
        normal_vector: 法線ベクトル (3次元配列)
        
    Returns:
        傾斜角度 [度] (0-90度の範囲)
        
    Raises:
        ValueError: 法線ベクトルが無効な場合
        RuntimeError: 計算に失敗した場合
        
    Example:
        >>> normal = np.array([0.0, 0.0, 1.0])  # 垂直
        >>> angle = calculator.calculate_slope_angle(normal)
        >>> print(angle)
        0.0
        
        >>> normal = np.array([1.0, 0.0, 0.0])  # 水平
        >>> angle = calculator.calculate_slope_angle(normal)
        >>> print(angle)
        90.0
    """
    # 入力検証
    if normal_vector is None or len(normal_vector) != 3:
        raise ValueError("Invalid normal vector")
    
    # 法線ベクトルの正規化
    normalized_normal = normal_vector / np.linalg.norm(normal_vector)
    
    # 垂直方向との内積を計算
    vertical = np.array([0.0, 0.0, 1.0])
    dot_product = np.dot(normalized_normal, vertical)
    
    # 傾斜角度を計算（ラジアンから度に変換）
    slope_angle = np.degrees(np.arccos(np.clip(dot_product, -1.0, 1.0)))
    
    return slope_angle
```

### 2. README更新
```markdown
## 新機能: 傾斜計算

### 概要
地形の傾斜角度を計算する機能を追加しました。

### 使用方法
```python
from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator

calculator = SlopeCalculator(max_slope_angle=30.0)
slope_data = calculator.calculate_slopes(voxel_grid, normals)
```

### パラメータ
- `max_slope_angle`: 最大傾斜角度 [度] (デフォルト: 30.0)

### 出力
- `slopes`: 傾斜角度の配列
- `statistics`: 統計情報（平均、最大、最小傾斜角度）
```

## レビュープロセス

### 1. 自動チェック
- **コードフォーマット**: Black, isort
- **リンター**: flake8, mypy
- **テスト**: pytest
- **カバレッジ**: 80%以上

### 2. レビュー項目
- **機能性**: 正しく動作するか
- **パフォーマンス**: 効率的か
- **可読性**: 理解しやすいか
- **テスト**: 適切にテストされているか
- **文書化**: 適切に文書化されているか

### 3. 承認条件
- 2名以上の承認
- すべての自動チェックが通る
- テストカバレッジが80%以上
- 文書が適切に更新されている

### 4. マージ
- プルリクエストが承認されたらマージ
- マージ後はブランチを削除
- リリースノートを更新

## トラブルシューティング

### よくある問題

#### 1. ビルドエラー
```bash
# 依存関係の確認
rosdep install --from-paths src --ignore-src -r -y

# クリーンビルド
rm -rf build/ install/ log/
colcon build --packages-select bunker_3d_nav
```

#### 2. テストエラー
```bash
# テストの実行
pytest test/ -v

# 特定のテストの実行
pytest test/test_voxel_grid_processor.py::TestVoxelGridProcessor::test_initialization -v
```

#### 3. リンターエラー
```bash
# コードフォーマット
black bunker_3d_nav/
isort bunker_3d_nav/

# リンター
flake8 bunker_3d_nav/
mypy bunker_3d_nav/
```

## 連絡先
- **メンテナー**: [名前] <email@example.com>
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Slack**: #bunker-3d-nav
