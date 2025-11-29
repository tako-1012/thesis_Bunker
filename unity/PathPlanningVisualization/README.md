# Unity可視化デモシステム

## プロジェクト概要
ROS2経路計画システムとUnityを統合し、リアルタイムで地形・経路を可視化するデモシステムです。

## 機能
- 3D地形可視化（障害物・勾配）
- 経路のアニメーション表示
- ロボットの移動シミュレーション
- インタラクティブカメラコントロール
- UI制御システム
- ROS2統合（オプション）

## セットアップ手順

### 1. Unityプロジェクト作成
1. Unity Hubで新規3Dプロジェクト作成
2. プロジェクト名: `PathPlanningVisualization`
3. テンプレート: 3D (URP - Universal Render Pipeline)
4. 場所: `~/thesis_work/unity/`

### 2. 必要なパッケージ導入
Unityエディタで以下をインストール:
- Universal RP
- TextMeshPro
- Input System (New)
- Recorder (動画撮影用)

### 3. スクリプト配置
以下のスクリプトを対応するディレクトリに配置:
```
Assets/Scripts/
├── Visualization/
│   ├── TerrainVisualizer.cs
│   ├── PathVisualizer.cs
│   ├── RobotController.cs
│   └── CameraController.cs
├── UI/
│   └── UIController.cs
├── ROS2Bridge/
│   ├── ROS2Connector.cs
│   └── UnityMainThreadDispatcher.cs
└── SimulationManager.cs
```

### 4. シーン設定
1. メインカメラに`CameraController`スクリプトをアタッチ
2. 空のGameObjectを作成し、`SimulationManager`スクリプトをアタッチ
3. UI Canvasを作成し、`UIController`スクリプトをアタッチ
4. ロボット用のGameObjectを作成し、`RobotController`スクリプトをアタッチ

### 5. マテリアル作成
以下のマテリアルを作成:
- `TerrainMaterial.mat` (地形用)
- `PathMaterial.mat` (経路用)
- `ObstacleMaterial.mat` (障害物用)
- `RobotMaterial.mat` (ロボット用)

## 使用方法

### 基本操作
- **WASD**: カメラ移動
- **マウス右ドラッグ**: カメラ回転
- **マウスホイール**: ズーム
- **F**: フォーカス対象にカメラを向ける
- **Shift + WASD**: 高速移動

### UI操作
- **シナリオドロップダウン**: シナリオ選択
- **Play**: シミュレーション開始
- **Pause**: シミュレーション一時停止
- **Reset**: シミュレーションリセット
- **Toggle**: 各種表示のON/OFF

## ROS2統合（オプション）

### ROS2ノード起動
```bash
cd ~/thesis_work/unity/ROS2Integration
python3 unity_visualization_node.py
```

### シナリオパブリッシュ
```bash
python3 scenario_publisher.py [scenario_id]
```

## デモ動画撮影

### Recorder使用
1. `Window` → `General` → `Recorder` → `Recorder Window`
2. 設定:
   - 解像度: 1920x1080
   - フレームレート: 60fps
   - フォーマット: MP4

### 撮影シナリオ
1. **オープニング** (10秒): タイトル表示
2. **地形タイプ紹介** (30秒): 7種類の地形を順に表示
3. **経路計画デモ** (60秒): 複数シナリオでの経路表示
4. **ロボット移動** (30秒): ロボットの移動アニメーション
5. **インタラクティブ操作** (30秒): カメラ操作・UI操作
6. **統計結果表示** (30秒): 100%成功率・グラフ表示

## トラブルシューティング

### よくある問題
1. **スクリプトエラー**: 必要なコンポーネントがアタッチされていない
2. **マテリアルエラー**: マテリアルが作成されていない
3. **UI表示されない**: Canvas設定を確認
4. **ROS2接続エラー**: ポート11000が使用中

### デバッグ
- Unity Consoleでエラーメッセージを確認
- ROS2ノードのログを確認
- ネットワーク接続を確認

## ファイル構成
```
PathPlanningVisualization/
├── Assets/
│   ├── Scripts/
│   │   ├── Visualization/
│   │   ├── UI/
│   │   ├── ROS2Bridge/
│   │   └── SimulationManager.cs
│   ├── Materials/
│   ├── Prefabs/
│   └── Scenes/
└── ProjectSettings/
```

## 更新履歴
- 2025-10-17: 初版作成
- 基本可視化システム実装
- ROS2統合機能追加
- デモ動画撮影機能追加


