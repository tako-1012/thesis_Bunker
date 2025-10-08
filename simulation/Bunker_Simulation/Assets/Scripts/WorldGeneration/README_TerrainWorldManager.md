# TerrainWorldManager 使用ガイド

## 概要
TerrainWorldManagerは、不整地環境における3D経路計画研究のために、5つの異なる地形シナリオを自動生成するUnityスクリプトです。

## 機能
- **5つの地形シナリオ**: 平坦+障害物、緩傾斜、急傾斜、障害物密集、複合地形
- **プロシージャル生成**: ランダムだが再現可能な地形生成
- **障害物配置**: 流木、岩、木などの障害物を自動配置
- **スタート/ゴール設定**: 自動または手動でのスタート・ゴール地点設定
- **地形解析**: 傾斜角度の計算とデバッグ表示

## 地形シナリオ

### 1. FlatWithObstacles（平坦地形+障害物）
- **特徴**: 平坦な地面に障害物をランダム配置
- **用途**: 基本的な障害物回避テスト
- **障害物密度**: 中程度

### 2. GentleSlope（緩傾斜地形）
- **特徴**: 10-15度の緩やかな丘陵地形
- **用途**: 傾斜を考慮した経路計画の基礎テスト
- **障害物**: 少数

### 3. SteepSlope（急傾斜地形）
- **特徴**: 20-30度の急な傾斜
- **用途**: 登坂・降坂能力のテスト
- **障害物**: 少なめ

### 4. DenseObstacles（障害物密集）
- **特徴**: 障害物が密集した環境
- **用途**: 複雑な経路計画のテスト
- **難易度**: 高

### 5. MixedTerrain（複合地形）
- **特徴**: 傾斜+障害物の組み合わせ
- **用途**: 最も現実的なシナリオ
- **実験**: メインシナリオとして使用

## 使用方法

### 1. 基本セットアップ
```csharp
// GameObjectにTerrainWorldManagerコンポーネントを追加
TerrainWorldManager manager = gameObject.AddComponent<TerrainWorldManager>();
```

### 2. シナリオ選択
```csharp
// Inspectorでシナリオを選択
manager.scenario = TerrainWorldManager.TerrainScenario.MixedTerrain;
```

### 3. パラメータ調整
- **Terrain Size**: 地形のサイズ（0.1-2.0）
- **Terrain Resolution**: 地形の解像度（0.1-0.5）
- **Obstacle Count**: 障害物の数（0-100）
- **Obstacle Scale**: 障害物のサイズ範囲

### 4. 実行
- **Start()**: 自動実行
- **Regenerate Terrain**: 手動で再生成
- **Switch to Next Scenario**: 次のシナリオに切り替え

## パラメータ詳細

### Terrain Generation Settings
- `terrainSize`: 地形の基本サイズ倍率
- `terrainResolution`: 地形の詳細度（小さいほど詳細）
- `terrainDetail`: 地形の複雑さレベル

### Obstacle Settings
- `obstaclePrefabs`: 使用する障害物プレハブの配列
- `obstacleCount`: 生成する障害物の基本数
- `obstacleScaleMin/Max`: 障害物のサイズ範囲

### Debug Settings
- `showSlopeDebug`: 傾斜角度のデバッグ表示
- `showTerrainInfo`: 地形情報の表示

## 出力データ

### 地形情報
- 高さマップ（heightMap）
- 傾斜角度分析
- 障害物位置情報

### スタート/ゴール地点
- `startPoint`: スタート地点のTransform
- `goalPoint`: ゴール地点のTransform

### デバッグ情報
- 地形の高さ範囲
- 平均傾斜角度
- 障害物数
- 傾斜分布（急/中/緩）

## カスタマイズ

### 障害物プレハブの追加
```csharp
// InspectorでobstaclePrefabsにプレハブを追加
// またはCreatePrimitiveObstacle()を修正して新しい障害物タイプを追加
```

### 地形生成のカスタマイズ
```csharp
// GenerateHeightMap()内の各シナリオ関数を修正
// 例: GenerateGentleSlopeTerrain()で傾斜角度を調整
```

### スタート/ゴール地点のカスタマイズ
```csharp
// SetStartGoalPoints()を修正して配置ロジックを変更
// autoGenerateStartGoal = falseにして手動設定も可能
```

## 使い方の手順

### 1. Unity 2021.3でのセットアップ
1. Unity 2021.3を起動
2. 新しいシーンを作成
3. 空のGameObjectを作成し、"TerrainManager"と命名
4. TerrainWorldManager.csスクリプトをアタッチ

### 2. 基本設定
1. Inspectorで以下のパラメータを設定:
   - **Scenario**: 使用する地形シナリオを選択
   - **Terrain Size**: 1.0（推奨）
   - **Terrain Resolution**: 0.1（推奨）
   - **Obstacle Count**: 20（推奨）
   - **Auto Generate Start Goal**: ✓（チェック）

### 3. 実行と確認
1. Playボタンを押して実行
2. Consoleで生成ログを確認
3. Sceneビューで地形と障害物を確認
4. Hierarchyで生成されたオブジェクトを確認

### 4. シナリオ切り替え
- **Context Menu**: TerrainWorldManagerコンポーネントを右クリック
- **Regenerate Terrain**: 現在のシナリオで再生成
- **Switch to Next Scenario**: 次のシナリオに切り替え

## 各シナリオの詳細説明

### FlatWithObstacles（平坦地形+障害物）
- **地形**: ほぼ平坦（高さ変動±5cm）
- **障害物**: 岩、流木、木の幹をランダム配置
- **用途**: 基本的な障害物回避アルゴリズムのテスト
- **難易度**: ★☆☆☆☆

### GentleSlope（緩傾斜地形）
- **地形**: 10-15度の緩やかな丘陵
- **特徴**: 正弦波とコサイン波の組み合わせ
- **障害物**: 少なめ（基本数の60%）
- **用途**: 傾斜を考慮した経路計画の基礎
- **難易度**: ★★☆☆☆

### SteepSlope（急傾斜地形）
- **地形**: 20-30度の急な傾斜
- **特徴**: 山と谷が明確に分かれた地形
- **障害物**: さらに少なめ（基本数の30%）
- **用途**: 登坂・降坂能力の限界テスト
- **難易度**: ★★★★☆

### DenseObstacles（障害物密集）
- **地形**: 平坦だが障害物が密集
- **障害物**: 基本数の2倍（40個）
- **配置**: ランダムだが密度が高い
- **用途**: 複雑な経路計画のテスト
- **難易度**: ★★★★☆

### MixedTerrain（複合地形）
- **地形**: 複数の周波数成分を組み合わせた複雑な地形
- **特徴**: 丘陵、尾根、谷が混在
- **障害物**: 基本数（20個）
- **用途**: 最も現実的なシナリオ
- **難易度**: ★★★★★

## トラブルシューティング

### 地形が生成されない
**症状**: Sceneビューに地形が表示されない
**原因と対処法**:
- Terrainコンポーネントが正しく設定されているか確認
- Consoleでエラーメッセージを確認
- terrainDataの設定を確認
- ScriptableObject.CreateInstance<TerrainData>()が正しく動作しているか確認

### 障害物が配置されない
**症状**: 地形は生成されるが障害物が表示されない
**原因と対処法**:
- obstaclePrefabsが設定されているか確認
- 地形の境界内に障害物が配置されているか確認
- obstacleCountが0以上に設定されているか確認
- Consoleで"Generated X obstacles"のログを確認

### パフォーマンス問題
**症状**: フレームレートが低下する
**対処法**:
- terrainResolutionを0.2以上に設定して解像度を下げる
- obstacleCountを10以下に減らす
- showSlopeDebugとshowTerrainInfoを無効にする
- 不要なデバッグ表示を無効にする

### コンパイルエラー
**症状**: スクリプトがコンパイルされない
**対処法**:
- using System.Linq;が追加されているか確認
- ScriptableObject.CreateInstance<TerrainData>()を使用しているか確認
- Application.isPlayingの判定が正しく実装されているか確認

### メモリ不足
**症状**: 地形生成時にメモリエラーが発生
**対処法**:
- terrainSizeを小さくする（0.5以下）
- terrainResolutionを大きくする（0.2以上）
- 不要なオブジェクトを手動で削除

### スタート/ゴール地点が表示されない
**症状**: 緑と赤の円柱が表示されない
**原因と対処法**:
- autoGenerateStartGoalが有効になっているか確認
- startPointとgoalPointのTransformが正しく設定されているか確認
- SceneビューでGizmosが有効になっているか確認

## 研究での活用

### 3D経路計画のテスト
1. 各シナリオで経路計画アルゴリズムをテスト
2. 傾斜角度と経路コストの関係を分析
3. 障害物密度と経路の複雑さの関係を評価

### データ収集
- 各シナリオの地形データをROS2に送信
- RTAB-Mapとの連携で3D点群データを取得
- 経路計画結果と地形特徴の相関分析

### 評価指標
- 経路長
- 最大傾斜角度
- 平均傾斜角度
- 障害物回避回数
- 計算時間

## 今後の拡張予定
- 動的障害物の追加
- 天候効果の実装
- 複数ロボットの同時テスト
- リアルタイム地形変更

