# 🎓 卒論研究プロジェクト: 不整地環境における3D経路計画

このディレクトリは、**Bunker移動ロボット**を基盤とした卒論研究プロジェクトです。不整地環境での自律移動ロボットの3次元ナビゲーション技術を開発しています。

## 🤖 研究概要

**研究テーマ**: 不整地環境での自律移動ロボットの3次元ナビゲーション技術
**目的**: RTAB-Mapの3D点群データを活用し、地形の傾斜を考慮した安全な経路計画を実現
**期間**: 4ヶ月（2025年10月〜2026年1月）
**ロボット**: Bunker移動ロボット
**環境**: 不整地（傾斜地、障害物が複雑な環境）

### 研究の新規性
1. **応用的新規性**: RTAB-Mapを不整地ナビゲーションに適用
2. **コスト関数設計**: 傾斜・転倒リスクの統合的考慮
3. **統合システム**: 3D SLAM + 地形解析 + 3D経路計画
4. **実用性**: 災害対応、農業、林業ロボットへの応用可能性

## 📁 ディレクトリ構造

```
thesis_work/
├── ros2/bunker_ros2/
│   ├── bunker_base/         # 既存: ハードウェア制御
│   ├── bunker_description/  # 既存: URDFモデル
│   ├── bunker_nav/          # 既存: 2Dナビゲーション・SLAM
│   ├── bunker_3d_nav/       # ★新規開発領域★
│   │   ├── terrain_analyzer/      # 地形解析モジュール
│   │   ├── path_planner_3d/       # 3D経路計画モジュール
│   │   ├── config/                # 設定ファイル
│   │   ├── launch/                 # 起動ファイル
│   │   ├── msg/                    # カスタムメッセージ
│   │   └── scripts/evaluation/     # 評価スクリプト
│   ├── bunker_gazebo/       # 既存: Gazeboシミュレーション
│   ├── bunker_tomato/       # 既存: トマト関連機能
│   ├── bunker_gps/          # 既存: GPS連携
│   ├── bunker_vis/          # 既存: 可視化ツール
│   └── bunker_msgs/         # 既存: カスタムメッセージ
├── simulation/Bunker_Simulation/  # Unity環境
│   └── Assets/Scenes/UnrealTerrain/  # 新規: 不整地ワールド
├── documents/thesis/        # 卒論関連文書・資料
├── .cursorrules             # Cursor設定ファイル
├── AI研究アシスタント用スクリプト.md  # AI支援用スクリプト
└── README.md               # このファイル
```

## 🚀 クイックスタート

### 1. Unityシミュレーション（推奨）

**5つのターミナルで順次実行:**

```bash
cd ~/thesis_work/ros2/ros2_ws
source install/setup.bash

# ターミナル1: Unity起動
ros2 launch bunker_unity launcher.launch.py

# ターミナル2: Bunkerスポーン（Unity起動後）
ros2 launch bunker_unity spawn_bunker.launch.py

# ターミナル3: URDF公開・Rviz
ros2 launch bunker_unity bunker_description.launch.py

# ターミナル4: ROS-Unity通信
ros2 run ros_tcp_endpoint default_server_endpoint

# ターミナル5: コントローラー
ros2 launch bunker_unity controllers.launch.py
```

### 2. Gazeboシミュレーション

```bash
cd ~/thesis_work/ros2/ros2_ws
source install/setup.bash

# Gazeboシミュレーション起動
ros2 launch bunker_gazebo gazebo.launch.py

# SLAM開始（別ターミナル）
ros2 launch bunker_nav kinect_rtabmap.launch.py
```

### 3. 実機制御

```bash
cd ~/thesis_work/ros2/ros2_ws
source install/setup.bash

# CAN-USB設定（初回のみ）
sudo modprobe gs_usb
cd src/ugv_sdk/scripts/
bash setup_can2usb.bash

# 実機制御開始
ros2 launch bunker_base bunker_base.launch.py
```

## 🛠️ 主要機能

### 基盤システム（既存）
- **RTAB-Map**: 3D SLAMによる地図作成
- **Nav2**: 2D自律ナビゲーション
- **EKF**: センサーフュージョン（IMU + GPS + オドメトリ）
- **農業応用**: トマト認識・収穫支援

### 新規開発機能（研究対象）
- **地形解析**: 点群から地形情報を抽出・解析
- **3D経路計画**: 傾斜を考慮した3次元経路生成
- **不整地ナビゲーション**: 傾斜地・障害物環境での自律移動

```bash
# 基盤SLAM実行
ros2 launch bunker_nav kinect_rtabmap.launch.py

# 3D経路計画（開発予定）
ros2 launch bunker_3d_nav terrain_analyzer.launch.py
ros2 launch bunker_3d_nav path_planner_3d.launch.py
```

### 技術スタック
- **言語**: Python 3.10+ (メイン), C++ (高速化用)
- **ROS**: ROS2 Humble/Jazzy
- **主要ライブラリ**: Open3D, NetworkX, NumPy, SciPy
- **シミュレーション**: Unity 2021.3+, Gazebo

## 🔧 開発・カスタマイズ

### 新規開発モジュール
- **terrain_analyzer**: 地形解析ノード（点群→ボクセル変換）
- **path_planner_3d**: 3D経路計画ノード（A*アルゴリズム）
- **不整地ワールド**: Unityでの傾斜地・障害物環境

### パラメータ調整
主要設定ファイル：
- `bunker_3d_nav/config/terrain_params.yaml`: 地形解析設定
- `bunker_3d_nav/config/planner_params.yaml`: 経路計画設定
- `bunker_nav/config/nav2_params.yaml`: 基盤ナビゲーション設定

### AI支援開発
- **Cursor設定**: `.cursorrules`でプロジェクト仕様を自動認識
- **AIスクリプト**: `AI研究アシスタント用スクリプト.md`で効率的な開発支援

## 📚 依存関係

### ROS2パッケージ
- `ugv_sdk`: Bunkerハードウェア制御
- `rtabmap_ros`: 3D SLAM
- `nav2`: ナビゲーション
- `ros_tcp_endpoint`: Unity連携

### Pythonライブラリ
- `open3d`: 点群処理（必須）
- `networkx`: グラフ探索
- `numpy`, `scipy`: 数値計算
- `matplotlib`, `pandas`: 可視化・解析

### Unityパッケージ
- `ROS-TCP-Connector`: ROS通信
- `URDF-Importer`: ロボットモデル
- `UnitySensors`: センサーシミュレーション

## ⚠️ 注意事項

1. **安全対策**: 実機使用時は必ずリモコンを準備
2. **CAN設定**: 実機接続前にCAN-USB設定が必要
3. **依存関係**: `libasio-dev`のインストールが必要
4. **Unity起動**: Unityシミュレーションは5つのターミナルが必要

## 📖 詳細ドキュメント

- [研究室プロジェクト詳細](./卒論研究内容整理.md)
- [研究計画・新機能候補](./卒論研究計画.md)
- [AI研究アシスタント用スクリプト](./AI研究アシスタント用スクリプト.md)
- [Cursor設定ファイル](./.cursorrules)
- [ROS2パッケージ詳細](./ros2/bunker_ros2/README.md)

## 🎯 研究目標

この卒論研究は以下の目標を掲げています：
- **不整地ナビゲーション**: 傾斜地・障害物環境での自律移動
- **3D経路計画**: 地形の傾斜を考慮した安全な経路生成
- **統合システム**: 3D SLAM + 地形解析 + 3D経路計画
- **実用性**: 災害対応、農業、林業ロボットへの応用

## 📊 実装優先順位

### Phase 1: 基盤構築 (Week 1-4)
1. プロジェクト構造作成
2. カスタムメッセージ定義
3. Unity不整地ワールド作成
4. ROSノードのスケルトン実装

### Phase 2: 地形解析 (Week 5-8)
1. 点群→ボクセル変換
2. 地面/障害物分類
3. 傾斜角度計算
4. Rviz可視化

### Phase 3: 経路計画 (Week 9-12)
1. A* 3Dの基本実装
2. コスト関数実装
3. 経路平滑化
4. Nav2との連携

### Phase 4: 評価 (Week 13-16)
1. シミュレーション実験
2. データ収集・解析
3. 実機検証（状況次第）
4. 論文執筆