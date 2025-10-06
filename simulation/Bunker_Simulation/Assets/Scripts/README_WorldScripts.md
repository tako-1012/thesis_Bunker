# Unity World Creation Scripts

UnityでBunkerロボットのテスト用ワールドを作成するためのスクリプト集です。

## 作成されたスクリプト

### 1. TestWorldManager.cs（メインスクリプト）
- **機能**: 全体的なワールド作成を管理
- **プリセット**: 5つの異なるワールドタイプを選択可能
  - NavigationTest: ナビゲーションテスト用
  - ObstacleAvoidance: 障害物回避テスト用  
  - RaceTrack: レースコース
  - OpenField: オープンフィールド
  - Urban: 都市環境

### 2. WorldBuilder.cs
- **機能**: 障害物と建物の自動生成
- **設定項目**: 
  - 障害物数、建物数
  - ワールドサイズ
  - 建物の高さ範囲

### 3. PathCreator.cs
- **機能**: レースコースやナビゲーションパスの作成
- **特徴**:
  - 円形・楕円形パス
  - ウェイポイント自動生成
  - パス幅・半径調整可能

### 4. EnvironmentSetup.cs
- **機能**: 基本的な環境設定
- **内容**:
  - 地面の作成
  - ライティング設定
  - 木々の配置
  - カメラ位置調整

## 使用方法

### Unity エディタでの使用

1. **空のGameObjectを作成**:
   ```
   Hierarchy → Create Empty → 名前を "WorldManager" に変更
   ```

2. **TestWorldManagerスクリプトをアタッチ**:
   ```
   WorldManager選択 → Inspector → Add Component → TestWorldManager
   ```

3. **プリセット選択**:
   ```
   Inspector → World Preset → お好みのプリセットを選択
   ```

4. **ワールド作成**:
   ```
   Play Mode に入ると自動でワールドが作成されます
   または Inspector → 右クリック → "Recreate World"
   ```

### プログラム的な使用

```csharp
// ワールドマネージャーをシーンに追加
GameObject worldManager = new GameObject("WorldManager");
TestWorldManager manager = worldManager.AddComponent<TestWorldManager>();

// プリセット設定
manager.worldPreset = TestWorldManager.WorldPreset.NavigationTest;

// ワールド作成
manager.RecreateWorld();
```

## カスタマイズ

### 障害物の設定変更
```csharp
WorldBuilder builder = GetComponent<WorldBuilder>();
builder.obstacleCount = 15;        // 障害物数
builder.worldSize = new Vector2(60, 60);  // ワールドサイズ
```

### パス設定の変更
```csharp
PathCreator path = GetComponent<PathCreator>();
path.pathRadius = 20f;             // パス半径
path.pathWidth = 4f;               // パス幅
path.createWaypoints = true;       // ウェイポイント作成
```

## テスト要素

作成されるワールドには以下のテスト要素が含まれます：

- **Target Markers**: 赤い円柱（目標地点）
- **Spawn Points**: 青い半透明の球（ロボットスポーン地点）
- **Waypoints**: 緑の球（ナビゲーション用）
- **Obstacles**: ランダム色のキューブ（障害物）
- **Buildings**: グレーのキューブ（建物）
- **Trees**: 茶色の幹+緑の葉（木々）

## タグシステム

以下のタグが自動的に設定されます：
- `Obstacle`, `Building`, `Path`, `Waypoint`
- `Target`, `SpawnPoint`, `Tree`, `Ground`

これらのタグはROSナビゲーションシステムと連携可能です。

## 注意事項

- スクリプト実行前にシーンを保存してください
- 既存のオブジェクトは `Recreate World` で削除される場合があります
- 大きなワールドサイズや多数のオブジェクトはパフォーマンスに影響します