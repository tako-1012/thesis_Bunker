# A* 3D経路計画テスト計画書

## 1. 概要

A* 3D経路計画アルゴリズムの包括的なテスト計画。単体テスト、統合テスト、パフォーマンステスト、エッジケーステストを含む。

## 2. テスト戦略

### 2.1 テストレベル
- **単体テスト**: 個別クラス・メソッドのテスト
- **統合テスト**: 複数コンポーネント間の連携テスト
- **システムテスト**: 全体システムの動作テスト
- **パフォーマンステスト**: 計算時間・メモリ使用量のテスト

### 2.2 テスト環境
- **開発環境**: Ubuntu 22.04, Python 3.10, ROS2 Humble
- **シミュレーション環境**: Unity 2021.3, Gazebo
- **実機環境**: Bunker移動ロボット（最終段階）

## 3. 単体テスト計画

### 3.1 Node3Dクラステスト
```python
def test_node3d_creation():
    """ノード作成テスト"""
    node = Node3D(position=(10, 20, 30))
    assert node.position == (10, 20, 30)
    assert node.g_cost == float('inf')
    assert node.h_cost == 0.0
    assert node.parent is None

def test_node3d_f_cost():
    """f_cost計算テスト"""
    node = Node3D(position=(0, 0, 0))
    node.g_cost = 5.0
    node.h_cost = 3.0
    assert node.f_cost == 8.0

def test_node3d_equality():
    """ノード等価性テスト"""
    node1 = Node3D(position=(1, 2, 3))
    node2 = Node3D(position=(1, 2, 3))
    node3 = Node3D(position=(1, 2, 4))
    
    assert node1 == node2
    assert node1 != node3

def test_node3d_hash():
    """ハッシュ値テスト"""
    node = Node3D(position=(5, 10, 15))
    hash_val = hash(node)
    assert isinstance(hash_val, int)

def test_node3d_comparison():
    """ノード比較テスト"""
    node1 = Node3D(position=(0, 0, 0))
    node1.g_cost = 1.0
    node1.h_cost = 2.0
    
    node2 = Node3D(position=(1, 1, 1))
    node2.g_cost = 2.0
    node2.h_cost = 1.0
    
    assert node1 < node2  # f_cost: 3.0 < 3.0 (同じ場合は位置で比較)
```

### 3.2 AStarPlanner3Dクラステスト
```python
def test_astar_planner_initialization():
    """A*プランナー初期化テスト"""
    planner = AStarPlanner3D(voxel_size=0.1)
    assert planner.voxel_size == 0.1
    assert planner.voxel_grid is None
    assert planner.terrain_data is None

def test_heuristic_function():
    """ヒューリスティック関数テスト"""
    planner = AStarPlanner3D()
    
    # ユークリッド距離テスト
    pos1 = (0, 0, 0)
    pos2 = (3, 4, 0)
    h_cost = planner._heuristic(pos1, pos2)
    expected = 5.0 * planner.voxel_size  # √(3²+4²+0²) = 5
    assert abs(h_cost - expected) < 1e-6

def test_get_neighbors():
    """26近傍取得テスト"""
    planner = AStarPlanner3D()
    pos = (5, 5, 5)
    neighbors = planner._get_neighbors(pos)
    
    # 26近傍の数チェック
    assert len(neighbors) == 26
    
    # 自分自身が含まれていないかチェック
    assert pos not in neighbors
    
    # 近傍の範囲チェック
    for neighbor in neighbors:
        dx = abs(neighbor[0] - pos[0])
        dy = abs(neighbor[1] - pos[1])
        dz = abs(neighbor[2] - pos[2])
        assert dx <= 1 and dy <= 1 and dz <= 1

def test_calculate_move_cost():
    """移動コスト計算テスト"""
    planner = AStarPlanner3D(voxel_size=0.1)
    
    # 直交移動テスト
    from_pos = (0, 0, 0)
    to_pos = (1, 0, 0)
    cost = planner._calculate_move_cost(from_pos, to_pos)
    assert abs(cost - 0.1) < 1e-6
    
    # 斜め移動テスト
    to_pos = (1, 1, 0)
    cost = planner._calculate_move_cost(from_pos, to_pos)
    expected = 0.1 * np.sqrt(2)
    assert abs(cost - expected) < 1e-6
    
    # 空間対角線移動テスト
    to_pos = (1, 1, 1)
    cost = planner._calculate_move_cost(from_pos, to_pos)
    expected = 0.1 * np.sqrt(3)
    assert abs(cost - expected) < 1e-6

def test_reconstruct_path():
    """経路復元テスト"""
    planner = AStarPlanner3D()
    
    # テスト経路作成
    node1 = Node3D(position=(0, 0, 0))
    node2 = Node3D(position=(1, 0, 0))
    node3 = Node3D(position=(2, 0, 0))
    
    node2.parent = node1
    node3.parent = node2
    
    path = planner._reconstruct_path(node3)
    expected = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
    assert path == expected
```

### 3.3 CostCalculatorクラステスト
```python
def test_cost_calculator_initialization():
    """コスト計算器初期化テスト"""
    calc = CostCalculator()
    assert calc.weight_slope == 2.0
    assert calc.weight_obstacle == 5.0
    assert calc.weight_risk == 3.0
    assert calc.weight_smoothness == 1.0

def test_slope_cost():
    """傾斜コストテスト"""
    calc = CostCalculator()
    
    # 緩い傾斜
    cost = calc._slope_cost(10.0)
    assert cost == 0.0
    
    # 中程度の傾斜
    cost = calc._slope_cost(20.0)
    assert abs(cost - 0.5) < 1e-6
    
    # 急な傾斜
    cost = calc._slope_cost(30.0)
    assert abs(cost - 2.0) < 1e-6
    
    # 走行不可傾斜
    cost = calc._slope_cost(40.0)
    assert cost == 1000.0

def test_obstacle_cost():
    """障害物コストテスト"""
    calc = CostCalculator()
    
    # 障害物なし
    cost = calc._obstacle_cost(False)
    assert cost == 0.0
    
    # 障害物あり
    cost = calc._obstacle_cost(True)
    assert cost == 1000.0

def test_risk_cost():
    """転倒リスクコストテスト"""
    calc = CostCalculator()
    
    # 低リスク
    cost = calc._risk_cost(0.1)
    assert abs(cost - 1.0) < 1e-6
    
    # 高リスク
    cost = calc._risk_cost(0.9)
    assert abs(cost - 9.0) < 1e-6

def test_total_cost():
    """統合コストテスト"""
    calc = CostCalculator()
    
    total = calc.calculate_total_cost(
        base_cost=1.0,
        slope_deg=20.0,
        is_obstacle=False,
        risk_score=0.2,
        turn_angle=0.1
    )
    
    expected = 1.0 + 0.5*2.0 + 0.0*5.0 + 2.0*3.0 + 0.1*1.0
    assert abs(total - expected) < 1e-6
```

### 3.4 PathSmootherクラステスト
```python
def test_path_smoother_initialization():
    """経路平滑化器初期化テスト"""
    smoother = PathSmoother()
    assert smoother.num_points == 100
    assert smoother.max_slope_deg == 35.0
    assert smoother.min_curve_radius == 0.5

def test_smooth_path():
    """経路平滑化テスト"""
    smoother = PathSmoother(num_points=10)
    
    # 直線経路
    path = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]
    smoothed = smoother.smooth_path(path)
    
    assert len(smoothed) == 10
    assert smoothed[0] == path[0]
    assert smoothed[-1] == path[-1]
    
    # ジグザグ経路
    path = [(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0)]
    smoothed = smoother.smooth_path(path)
    
    assert len(smoothed) == 10
    assert smoothed[0] == path[0]
    assert smoothed[-1] == path[-1]

def test_calculate_path_parameter():
    """経路パラメータ計算テスト"""
    smoother = PathSmoother()
    
    path = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]])
    t = smoother._calculate_path_parameter(path)
    
    assert len(t) == 3
    assert t[0] == 0.0
    assert abs(t[1] - 1.0) < 1e-6
    assert abs(t[2] - 2.0) < 1e-6
```

## 4. 統合テスト計画

### 4.1 経路計画統合テスト
```python
def test_path_planning_integration():
    """経路計画統合テスト"""
    # テスト環境セットアップ
    planner = AStarPlanner3D(voxel_size=0.1)
    
    # 仮想地形データ作成
    voxel_grid = create_test_voxel_grid(50, 50, 10)
    terrain_data = create_test_terrain_data()
    
    planner.set_terrain_data(voxel_grid, terrain_data)
    
    # 経路計画実行
    start = (0.0, 0.0, 0.0)
    goal = (5.0, 5.0, 0.0)
    path = planner.plan_path(start, goal)
    
    # 結果検証
    assert path is not None
    assert len(path) > 0
    assert path[0] == start
    assert path[-1] == goal
    
    # 経路の連続性チェック
    for i in range(len(path) - 1):
        dist = np.linalg.norm(np.array(path[i+1]) - np.array(path[i]))
        assert dist <= planner.voxel_size * np.sqrt(3) + 1e-6

def test_cost_function_integration():
    """コスト関数統合テスト"""
    planner = AStarPlanner3D()
    planner.cost_calculator = CostCalculator()
    
    # 傾斜地経路テスト
    start = (0.0, 0.0, 0.0)
    goal = (10.0, 0.0, 2.0)  # 上り坂
    
    path = planner.plan_path(start, goal)
    assert path is not None
    
    # コスト計算テスト
    total_cost = planner.calculate_path_cost(path)
    assert total_cost > 0

def test_smoothing_integration():
    """平滑化統合テスト"""
    planner = AStarPlanner3D()
    planner.path_smoother = PathSmoother()
    
    # ジグザグ経路生成
    start = (0.0, 0.0, 0.0)
    goal = (10.0, 10.0, 0.0)
    
    # 平滑化なし
    path_raw = planner.plan_path(start, goal, smooth_path=False)
    
    # 平滑化あり
    path_smooth = planner.plan_path(start, goal, smooth_path=True)
    
    assert path_raw is not None
    assert path_smooth is not None
    
    # 平滑化後の経路がより滑らかかチェック
    smoothness_raw = calculate_path_smoothness(path_raw)
    smoothness_smooth = calculate_path_smoothness(path_smooth)
    assert smoothness_smooth < smoothness_raw
```

### 4.2 ROS2統合テスト
```python
def test_ros_node_integration():
    """ROSノード統合テスト"""
    # ノード起動
    node = PathPlanner3DNode()
    
    # パラメータ設定
    node.set_parameter('voxel_size', 0.1)
    node.set_parameter('max_slope_deg', 30.0)
    
    # サービス呼び出し
    request = PlanPath3D.Request()
    request.start_pose = create_test_pose(0, 0, 0)
    request.goal_pose = create_test_pose(10, 10, 0)
    
    response = node.plan_path_callback(request, PlanPath3D.Response())
    
    # 結果検証
    assert response.success == True
    assert len(response.path.points) > 0
    assert response.stats.path_length > 0
    assert response.cost_info.total_cost > 0

def test_topic_communication():
    """トピック通信テスト"""
    # パブリッシャー・サブスクライバー作成
    pub = node.create_publisher(PoseStamped, '/goal_pose', 10)
    sub = node.create_subscription(Path, '/path_3d', path_callback, 10)
    
    # メッセージ送信
    goal_msg = create_test_pose_stamped(10, 10, 0)
    pub.publish(goal_msg)
    
    # 結果受信待機
    time.sleep(1.0)
    
    # 経路受信確認
    assert received_path is not None
    assert len(received_path.poses) > 0
```

## 5. パフォーマンステスト計画

### 5.1 計算時間テスト
```python
def test_computation_time():
    """計算時間テスト"""
    planner = AStarPlanner3D()
    
    # 小規模テスト（100×100×10）
    start_time = time.time()
    path = planner.plan_path((0, 0, 0), (10, 10, 0))
    end_time = time.time()
    
    computation_time = end_time - start_time
    assert computation_time < 1.0  # 1秒以内
    
    # 中規模テスト（500×500×20）
    # TODO: 実装
    
    # 大規模テスト（1000×1000×50）
    # TODO: 実装

def test_memory_usage():
    """メモリ使用量テスト"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # 大規模経路計画実行
    planner = AStarPlanner3D()
    path = planner.plan_path((0, 0, 0), (100, 100, 0))
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    assert memory_increase < 500  # 500MB以内

def test_scalability():
    """スケーラビリティテスト"""
    sizes = [(50, 50, 10), (100, 100, 20), (200, 200, 30)]
    times = []
    
    for size in sizes:
        planner = AStarPlanner3D()
        start_time = time.time()
        path = planner.plan_path((0, 0, 0), (size[0]-1, size[1]-1, 0))
        end_time = time.time()
        
        times.append(end_time - start_time)
    
    # 計算時間の増加が線形以下かチェック
    for i in range(1, len(times)):
        ratio = times[i] / times[i-1]
        assert ratio < 4.0  # 4倍以下
```

### 5.2 経路品質テスト
```python
def test_path_quality():
    """経路品質テスト"""
    planner = AStarPlanner3D()
    
    # 直線経路テスト
    start = (0, 0, 0)
    goal = (10, 0, 0)
    path = planner.plan_path(start, goal)
    
    # 経路長チェック
    path_length = calculate_path_length(path)
    straight_distance = np.linalg.norm(np.array(goal) - np.array(start))
    assert path_length <= straight_distance * 1.5  # 50%以内の増加
    
    # 傾斜チェック
    max_slope = calculate_max_slope(path)
    assert max_slope <= 30.0  # 30度以内
    
    # 障害物回避チェック
    min_clearance = calculate_min_clearance(path)
    assert min_clearance >= 0.5  # 0.5m以上
```

## 6. エッジケーステスト

### 6.1 異常入力テスト
```python
def test_invalid_inputs():
    """無効入力テスト"""
    planner = AStarPlanner3D()
    
    # 同じ開始点と目標点
    start = (0, 0, 0)
    goal = (0, 0, 0)
    path = planner.plan_path(start, goal)
    assert path is None or len(path) == 1
    
    # 無効な座標
    start = (-1, -1, -1)
    goal = (1000, 1000, 1000)
    path = planner.plan_path(start, goal)
    assert path is None
    
    # None入力
    path = planner.plan_path(None, None)
    assert path is None

def test_boundary_conditions():
    """境界条件テスト"""
    planner = AStarPlanner3D()
    
    # グリッド境界
    start = (0, 0, 0)
    goal = (99, 99, 9)  # グリッド端
    path = planner.plan_path(start, goal)
    assert path is not None
    
    # 極端な傾斜
    # TODO: 実装
    
    # 密集した障害物
    # TODO: 実装
```

### 6.2 障害物テスト
```python
def test_obstacle_avoidance():
    """障害物回避テスト"""
    planner = AStarPlanner3D()
    
    # 単一障害物
    # TODO: 実装
    
    # 複数障害物
    # TODO: 実装
    
    # 障害物で囲まれた環境
    # TODO: 実装
    
    # 動的障害物
    # TODO: 実装

def test_narrow_passages():
    """狭い通路テスト"""
    planner = AStarPlanner3D()
    
    # ロボット幅より狭い通路
    # TODO: 実装
    
    # 複雑な迷路
    # TODO: 実装
```

### 6.3 地形テスト
```python
def test_terrain_variations():
    """地形変化テスト"""
    planner = AStarPlanner3D()
    
    # 平坦地
    # TODO: 実装
    
    # 丘陵地
    # TODO: 実装
    
    # 峡谷
    # TODO: 実装
    
    # 複雑な3D地形
    # TODO: 実装
```

## 7. テスト実行計画

### 7.1 テストスケジュール
- **Day 9**: 単体テスト（Node3D, AStarPlanner3D基本）
- **Day 10**: 単体テスト（CostCalculator, コスト関数）
- **Day 11**: 統合テスト（経路計画、平滑化）
- **Day 12**: パフォーマンステスト、エッジケーステスト

### 7.2 テスト環境セットアップ
```bash
# テスト環境構築
cd ~/thesis_work/ros2/ros2_ws
colcon build --packages-select bunker_3d_nav

# テスト実行
python3 -m pytest src/bunker_ros2/bunker_3d_nav/path_planner_3d/test_*.py -v

# カバレッジ測定
python3 -m pytest --cov=path_planner_3d --cov-report=html
```

### 7.3 継続的インテグレーション
```yaml
# .github/workflows/test.yml
name: A* 3D Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v3
      - name: Setup ROS2
        run: |
          sudo apt update
          sudo apt install ros-humble-desktop
      - name: Run Tests
        run: |
          cd ros2/ros2_ws
          colcon build --packages-select bunker_3d_nav
          python3 -m pytest src/bunker_ros2/bunker_3d_nav/path_planner_3d/test_*.py -v
```

## 8. テスト結果評価

### 8.1 成功基準
- **単体テスト**: 100%パス
- **統合テスト**: 95%以上パス
- **パフォーマンステスト**: 要件を満たす
- **エッジケーステスト**: 80%以上パス

### 8.2 品質指標
- **コードカバレッジ**: 90%以上
- **計算時間**: 要件以内
- **メモリ使用量**: 要件以内
- **経路品質**: 基準を満たす

### 8.3 テストレポート
```python
def generate_test_report():
    """テストレポート生成"""
    report = {
        'test_summary': {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0
        },
        'performance_metrics': {
            'avg_computation_time': 0.0,
            'max_memory_usage': 0.0,
            'path_quality_score': 0.0
        },
        'coverage_report': {
            'line_coverage': 0.0,
            'branch_coverage': 0.0,
            'function_coverage': 0.0
        }
    }
    return report
```

---

**作成日**: 2025-10-11  
**更新日**: 2025-10-11  
**作成者**: AI研究アシスタント


