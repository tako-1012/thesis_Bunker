"""
CostCalculatorクラスのテスト
"""
import numpy as np
from cost_calculator import CostCalculator

def test_cost_calculator_creation():
    """コスト計算器作成のテスト"""
    print("=== test_cost_calculator_creation ===")
    
    # デフォルト設定
    calc = CostCalculator()
    assert calc.weight_distance == 1.0
    assert calc.weight_slope == 3.0
    assert calc.weight_obstacle == 5.0
    assert calc.weight_risk == 4.0
    assert calc.weight_smoothness == 1.0
    
    # カスタム設定
    calc_custom = CostCalculator(
        weight_distance=2.0,
        weight_slope=5.0,
        weight_obstacle=10.0,
        weight_risk=3.0,
        weight_smoothness=0.5
    )
    assert calc_custom.weight_distance == 2.0
    assert calc_custom.weight_slope == 5.0
    
    print("✅ コスト計算器作成テスト成功")

def test_slope_cost():
    """傾斜コスト計算のテスト"""
    print("=== test_slope_cost ===")
    
    calc = CostCalculator()
    
    # 緩やかな傾斜（0-15度）
    assert calc._calculate_slope_cost(0.0) == 0.0
    assert calc._calculate_slope_cost(10.0) == 0.0
    assert calc._calculate_slope_cost(15.0) == 0.0
    
    # 中程度の傾斜（15-25度）
    assert calc._calculate_slope_cost(20.0) == 0.5  # (20-15)/10
    assert calc._calculate_slope_cost(25.0) == 1.0
    
    # 急な傾斜（25-35度）
    assert calc._calculate_slope_cost(30.0) == 3.0  # 1.0 + (30-25)/2.5
    assert abs(calc._calculate_slope_cost(34.9) - 4.96) < 0.01  # 浮動小数点誤差を考慮
    
    # 35度ちょうどは走行不可
    assert calc._calculate_slope_cost(35.0) == 1000.0
    
    # 非常に急な傾斜（35度以上）
    assert calc._calculate_slope_cost(40.0) == 1000.0
    assert calc._calculate_slope_cost(90.0) == 1000.0
    
    # 負の傾斜（下り坂）
    assert calc._calculate_slope_cost(-20.0) == 0.5  # 絶対値を使用
    
    print("✅ 傾斜コスト計算テスト成功")

def test_obstacle_cost():
    """障害物コスト計算のテスト"""
    print("=== test_obstacle_cost ===")
    
    calc = CostCalculator()
    
    # 障害物なし
    assert calc._calculate_obstacle_cost(False) == 0.0
    
    # 障害物あり
    assert calc._calculate_obstacle_cost(True) == 1000.0
    
    print("✅ 障害物コスト計算テスト成功")

def test_risk_cost():
    """転倒リスクコスト計算のテスト"""
    print("=== test_risk_cost ===")
    
    calc = CostCalculator()
    
    # 安全
    assert calc._calculate_risk_cost(0.0) == 0.0
    
    # 中程度のリスク
    assert calc._calculate_risk_cost(0.5) == 5.0
    
    # 高いリスク
    assert calc._calculate_risk_cost(1.0) == 10.0
    
    print("✅ 転倒リスクコスト計算テスト成功")

def test_smoothness_cost():
    """平滑化コスト計算のテスト"""
    print("=== test_smoothness_cost ===")
    
    calc = CostCalculator()
    
    # 直進
    assert calc._calculate_smoothness_cost(0.0) == 0.0
    
    # 緩やかな旋回
    assert calc._calculate_smoothness_cost(0.5) == 0.5
    
    # 急な旋回
    assert calc._calculate_smoothness_cost(1.0) == 1.0
    
    # 負の角度（逆方向）
    assert calc._calculate_smoothness_cost(-0.5) == 0.5  # 絶対値
    
    print("✅ 平滑化コスト計算テスト成功")

def test_total_cost():
    """統合コスト計算のテスト"""
    print("=== test_total_cost ===")
    
    calc = CostCalculator()
    
    # 基本ケース（平地、障害物なし）
    cost = calc.calculate_total_cost(
        base_distance=1.0,
        slope_deg=0.0,
        is_obstacle=False,
        risk_score=0.0,
        turn_angle=0.0
    )
    expected = 1.0 * 1.0 + 0.0 * 3.0 + 0.0 * 5.0 + 0.0 * 4.0 + 0.0 * 1.0
    assert abs(cost - expected) < 0.001
    
    # 傾斜あり
    cost = calc.calculate_total_cost(
        base_distance=1.0,
        slope_deg=20.0,
        is_obstacle=False,
        risk_score=0.0,
        turn_angle=0.0
    )
    expected = 1.0 * 1.0 + 0.5 * 3.0 + 0.0 * 5.0 + 0.0 * 4.0 + 0.0 * 1.0
    assert abs(cost - expected) < 0.001
    
    # 障害物あり
    cost = calc.calculate_total_cost(
        base_distance=1.0,
        slope_deg=0.0,
        is_obstacle=True,
        risk_score=0.0,
        turn_angle=0.0
    )
    expected = 1.0 * 1.0 + 0.0 * 3.0 + 1000.0 * 5.0 + 0.0 * 4.0 + 0.0 * 1.0
    assert abs(cost - expected) < 0.001
    
    print("✅ 統合コスト計算テスト成功")

def test_traversability():
    """走行可能性判定のテスト"""
    print("=== test_traversability ===")
    
    calc = CostCalculator()
    
    # 走行可能
    assert calc.get_traversability(0.0, 0.0) == True
    assert calc.get_traversability(20.0, 0.5) == True
    assert calc.get_traversability(34.0, 0.7) == True
    
    # 傾斜が急すぎる
    assert calc.get_traversability(35.0, 0.0) == False
    assert calc.get_traversability(40.0, 0.0) == False
    
    # リスクが高すぎる
    assert calc.get_traversability(0.0, 0.8) == False
    assert calc.get_traversability(0.0, 1.0) == False
    
    # 両方とも危険
    assert calc.get_traversability(40.0, 0.9) == False
    
    print("✅ 走行可能性判定テスト成功")

def test_weight_setting():
    """重み設定のテスト"""
    print("=== test_weight_setting ===")
    
    calc = CostCalculator()
    
    # 個別設定
    calc.set_weights(distance=2.0)
    assert calc.weight_distance == 2.0
    assert calc.weight_slope == 3.0  # 変更されていない
    
    # 複数設定
    calc.set_weights(slope=5.0, obstacle=10.0)
    assert calc.weight_slope == 5.0
    assert calc.weight_obstacle == 10.0
    assert calc.weight_distance == 2.0  # 前回の設定が保持
    
    # None指定（変更なし）
    calc.set_weights(distance=None, risk=7.0)
    assert calc.weight_distance == 2.0  # 変更されていない
    assert calc.weight_risk == 7.0
    
    print("✅ 重み設定テスト成功")

def test_edge_cases():
    """エッジケースのテスト"""
    print("=== test_edge_cases ===")
    
    calc = CostCalculator()
    
    # 極端な値
    cost = calc.calculate_total_cost(
        base_distance=0.0,  # 距離0
        slope_deg=90.0,    # 最大傾斜
        is_obstacle=True,  # 障害物あり
        risk_score=1.0,    # 最大リスク
        turn_angle=np.pi   # 180度旋回
    )
    
    # コストが非常に大きくなることを確認
    assert cost > 1000.0
    
    # 負の値
    cost = calc.calculate_total_cost(
        base_distance=-1.0,  # 負の距離（異常値）
        slope_deg=-90.0,    # 負の傾斜
        is_obstacle=False,
        risk_score=-0.5,    # 負のリスク
        turn_angle=-np.pi   # 負の旋回
    )
    
    # 結果が計算されることを確認（エラーにならない）
    assert isinstance(cost, float)
    
    print("✅ エッジケーステスト成功")

if __name__ == "__main__":
    test_cost_calculator_creation()
    test_slope_cost()
    test_obstacle_cost()
    test_risk_cost()
    test_smoothness_cost()
    test_total_cost()
    test_traversability()
    test_weight_setting()
    test_edge_cases()
    
    print("\n✅ 全てのCostCalculatorテストが成功しました！")
