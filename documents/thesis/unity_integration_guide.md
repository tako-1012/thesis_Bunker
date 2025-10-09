# Unity連携統合ガイド

## 🎯 概要

ROS2のterrain_analyzerとUnityを連携させるための完全ガイドです。
TCP/IP通信を使用してROS2から地形解析データをUnityに送信し、リアルタイムで可視化します。

## 🏗️ システム構成

```
ROS2 (terrain_analyzer) → TCP/IP → Unity (TerrainDataReceiver)
     ↓                           ↓
 地形解析データ               3D可視化
```

### コンポーネント
- **ROS2側**: `unity_bridge`パッケージ
  - `ros_to_unity_converter.py`: データ変換
  - `tcp_server_node.py`: TCP/IPサーバー
- **Unity側**: `TerrainDataReceiver.cs`
  - TCP/IPクライアント
  - データ受信・可視化

## 📋 セットアップ手順

### 1. ROS2環境準備

```bash
# ROS2環境設定
cd ~/thesis_work/ros2/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

# パッケージビルド
colcon build --packages-select bunker_3d_nav
```

### 2. Unity環境準備

#### 必要なUnityバージョン
- Unity 2021.3 LTS以上
- .NET Standard 2.1対応

#### プロジェクト設定
1. **Player Settings**:
   - API Compatibility Level: .NET Standard 2.1
   - Scripting Backend: Mono

2. **Package Manager**:
   - 追加パッケージ不要（標準ライブラリのみ使用）

### 3. スクリプト配置

#### Unity側
```
Assets/Scripts/TerrainDataReceiver.cs
```

#### ROS2側
```
~/thesis_work/ros2/ros2_ws/src/bunker_ros2/unity_bridge/
├── ros_to_unity_converter.py
├── tcp_server_node.py
└── test_unity_bridge.py
```

## 🚀 実行手順

### 1. ROS2側起動

```bash
# ターミナル1: terrain_analyzer起動
cd ~/thesis_work/ros2/ros2_ws
./run_terrain_analyzer.sh

# ターミナル2: Unity Bridge起動
ros2 run bunker_3d_nav tcp_server_node
```

### 2. Unity側起動

1. **TerrainDataReceiver設定**:
   - Server Host: `127.0.0.1`
   - Server Port: `10000`
   - Voxel Prefab: ボクセル表示用Prefab
   - Terrain Materials: 傾斜別マテリアル配列

2. **Prefab作成**:
   - キューブ（1x1x1）
   - マテリアル設定可能
   - TerrainDataReceiverにアサイン

3. **マテリアル設定**:
   - [0]: 平坦（緑）
   - [1]: 緩傾斜（黄）
   - [2]: 中傾斜（オレンジ）
   - [3]: 急傾斜（赤）
   - [4]: 障害物（グレー）

### 3. 接続確認

```bash
# ROS2側で接続確認
ros2 topic echo /bunker/terrain_info

# Unity側で接続確認
# Consoleに "Connected to ROS2 Bridge!" が表示される
```

## 📊 データフォーマット仕様

### TerrainInfo JSON
```json
{
  "message_type": "terrain_info",
  "timestamp": 1699123456.789,
  "frame_id": "map",
  "statistics": {
    "avg_slope": 15.5,
    "max_slope": 35.2,
    "min_slope": 2.1,
    "traversable_ratio": 0.75
  },
  "voxels": {
    "total": 1000,
    "ground": 750,
    "obstacle": 250
  },
  "risk": {
    "avg_score": 0.3,
    "max_score": 0.8
  },
  "cost": {
    "avg_cost": 2.5,
    "impassable_ratio": 0.25
  },
  "performance": {
    "processing_time": 0.05,
    "point_count": 5000
  }
}
```

### VoxelGrid3D JSON
```json
{
  "message_type": "voxel_grid",
  "timestamp": 1699123456.789,
  "frame_id": "map",
  "grid_info": {
    "voxel_size": 0.1,
    "num_voxels": 100,
    "bounds": {
      "min": {"x": -5.0, "y": -5.0, "z": -1.0},
      "max": {"x": 5.0, "y": 5.0, "z": 2.0},
      "size": {"x": 10.0, "y": 10.0, "z": 3.0}
    }
  },
  "voxel_samples": [
    {
      "index": 0,
      "position": {"x": 0, "y": 0, "z": 0},
      "type": 1,
      "slope": 15.0,
      "risk": 0.3,
      "cost": 2.0
    }
  ],
  "sampling_info": {
    "total_voxels": 100,
    "sampled_voxels": 100,
    "sampling_ratio": 1.0
  }
}
```

### 統合地形データ JSON
```json
{
  "message_type": "unified_terrain",
  "timestamp": 1699123456.789,
  "frame_id": "map",
  "terrain_info": {
    "statistics": {
      "avg_slope": 15.5,
      "max_slope": 35.2,
      "traversable_ratio": 0.75
    },
    "voxels": {
      "total": 1000,
      "ground": 750,
      "obstacle": 250
    },
    "risk": {
      "avg_score": 0.3,
      "max_score": 0.8
    }
  },
  "voxel_grid": {
    "voxel_size": 0.1,
    "num_voxels": 100,
    "bounds": {
      "min": {"x": -5.0, "y": -5.0, "z": -1.0},
      "max": {"x": 5.0, "y": 5.0, "z": 2.0}
    }
  },
  "unity_metadata": {
    "version": "1.0",
    "data_format": "terrain_analysis",
    "compression": "none",
    "coordinate_system": "ros_map"
  }
}
```

## 🔧 設定パラメータ

### ROS2側パラメータ
```yaml
# unity_bridgeパラメータ
unity_bridge:
  tcp_port: 10000
  tcp_host: "127.0.0.1"
  max_connections: 5
  send_interval: 0.1  # 10Hz
```

### Unity側パラメータ
```csharp
[Header("Connection Settings")]
public string serverHost = "127.0.0.1";
public int serverPort = 10000;
public float reconnectInterval = 5.0f;

[Header("Visualization Settings")]
public GameObject voxelPrefab;
public Material[] terrainMaterials;
public Transform terrainParent;
```

## 🧪 テスト方法

### 1. 統合テスト実行
```bash
cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/unity_bridge
python3 test_unity_bridge.py
```

### 2. 手動テスト
```bash
# ROS2側
ros2 topic echo /bunker/terrain_info
ros2 topic echo /bunker/voxel_grid

# Unity側
# Consoleで接続状態とメッセージ受信を確認
```

### 3. パフォーマンステスト
```bash
# 通信速度テスト
python3 test_unity_bridge.py

# 結果例:
# ✅ 接続時間: 2.1ms
# ✅ データ送受信: 成功
# ✅ スループット: 100.0 messages/sec
```

## 🛠️ トラブルシューティング

### よくある問題

#### 1. 接続エラー
**問題**: Unity側で接続できない
**原因**: ROS2側のTCPサーバーが起動していない
**解決方法**:
```bash
# ROS2側確認
ros2 node list | grep unity_bridge
netstat -an | grep 10000
```

#### 2. データ受信エラー
**問題**: Unity側でデータが受信されない
**原因**: terrain_analyzerが動作していない
**解決方法**:
```bash
# terrain_analyzer確認
ros2 topic list | grep bunker
ros2 topic echo /bunker/terrain_info --once
```

#### 3. 可視化エラー
**問題**: Unity側でボクセルが表示されない
**原因**: Prefabまたはマテリアルが設定されていない
**解決方法**:
- Voxel Prefabを設定
- Terrain Materials配列を設定
- Debug Logを有効にしてエラー確認

#### 4. パフォーマンス問題
**問題**: 通信が遅い、フレームレートが低下
**原因**: データ量が多すぎる
**解決方法**:
```yaml
# ROS2側パラメータ調整
send_interval: 0.2  # 5Hzに変更
max_voxels_for_unity: 50  # ボクセル数削減
```

### デバッグ方法

#### ROS2側デバッグ
```bash
# デバッグレベルで起動
ros2 run bunker_3d_nav tcp_server_node --ros-args --log-level debug

# 接続統計確認
ros2 topic echo /unity_bridge/stats
```

#### Unity側デバッグ
```csharp
// Debug Log有効化
public bool enableDebugLog = true;

// Console出力例:
// [TerrainDataReceiver] Connected to ROS2 Bridge at 127.0.0.1:10000
// [TerrainDataReceiver] Terrain Info: Avg Slope=15.5°, Traversable=75.0%
// [TerrainDataReceiver] Voxel Grid: 100 voxels
```

## 📈 パフォーマンス最適化

### 1. データ圧縮
```python
# ros_to_unity_converter.py
self.compression_enabled = True
self.max_voxels_for_unity = 50  # ボクセル数制限
```

### 2. 送信頻度調整
```yaml
# リアルタイム性重視
send_interval: 0.1  # 10Hz

# パフォーマンス重視
send_interval: 0.5  # 2Hz
```

### 3. Unity側最適化
```csharp
// オブジェクトプール使用
private Queue<GameObject> voxelPool = new Queue<GameObject>();

// 不要なオブジェクトの再利用
void ReuseVoxelObject(GameObject obj)
{
    obj.SetActive(false);
    voxelPool.Enqueue(obj);
}
```

## 🔄 拡張機能

### 1. カスタムデータ追加
```python
# ros_to_unity_converter.py
def add_custom_data(self, data: Dict[str, Any]) -> str:
    """カスタムデータを追加"""
    pass
```

### 2. 複数クライアント対応
```python
# tcp_server_node.py
self.max_connections = 10  # 接続数増加
```

### 3. データ圧縮
```python
# ros_to_unity_converter.py
import gzip
import base64

def compress_data(self, data: str) -> str:
    """データ圧縮"""
    compressed = gzip.compress(data.encode('utf-8'))
    return base64.b64encode(compressed).decode('utf-8')
```

## 📚 参考資料

### ROS2公式ドキュメント
- [ROS2 Python API](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Publisher-And-Subscriber.html)
- [Custom Messages](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html)

### Unity公式ドキュメント
- [Networking](https://docs.unity3d.com/Manual/UNet.html)
- [JSON Serialization](https://docs.unity3d.com/Manual/JSONSerialization.html)

### 関連プロジェクト
- [ROS-TCP-Endpoint](https://github.com/Unity-Technologies/ROS-TCP-Endpoint)
- [Unity Robotics Hub](https://github.com/Unity-Technologies/Unity-Robotics-Hub)

## 🎯 次のステップ

1. **3D経路計画連携**: Unity側で経路計画結果を可視化
2. **リアルタイム制御**: Unity側からロボット制御コマンド送信
3. **マルチロボット対応**: 複数ロボットの同時可視化
4. **VR/AR対応**: VR/AR環境での地形可視化

---

**作成日**: 2025-10-06  
**バージョン**: 1.0  
**更新者**: Hayashi
