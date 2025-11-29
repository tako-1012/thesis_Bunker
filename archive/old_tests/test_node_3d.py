"""
Node3Dクラスのテスト
"""
from .node_3d import Node3D

def test_node_creation():
    """ノード作成のテスト"""
    print("=== test_node_creation ===")
    
    node = Node3D(position=(0, 0, 0))
    assert node.position == (0, 0, 0)
    assert node.g_cost == float('inf')
    assert node.h_cost == 0.0
    assert node.parent is None
    
    print("✅ ノード作成テスト成功")

def test_f_cost():
    """f_cost計算のテスト"""
    print("=== test_f_cost ===")
    
    node = Node3D(position=(0, 0, 0), g_cost=5.0)
    node.h_cost = 3.0
    
    assert node.f_cost == 8.0
    
    print("✅ f_cost計算テスト成功")

def test_node_equality():
    """ノードの等価性テスト"""
    print("=== test_node_equality ===")
    
    node1 = Node3D(position=(1, 2, 3))
    node2 = Node3D(position=(1, 2, 3))
    node3 = Node3D(position=(4, 5, 6))
    
    assert node1 == node2
    assert node1 != node3
    
    print("✅ ノード等価性テスト成功")

def test_node_comparison():
    """ノード比較のテスト"""
    print("=== test_node_comparison ===")
    
    node1 = Node3D(position=(0, 0, 0), g_cost=5.0)
    node1.h_cost = 3.0  # f_cost = 8.0
    
    node2 = Node3D(position=(1, 1, 1), g_cost=6.0)
    node2.h_cost = 2.0  # f_cost = 8.0
    
    node3 = Node3D(position=(2, 2, 2), g_cost=4.0)
    node3.h_cost = 2.0  # f_cost = 6.0
    
    assert not (node1 < node2)  # f_costが同じ
    assert node3 < node1  # node3の方が小さい
    
    print("✅ ノード比較テスト成功")

def test_node_hash():
    """ノードのハッシュテスト"""
    print("=== test_node_hash ===")
    
    node1 = Node3D(position=(1, 2, 3))
    node2 = Node3D(position=(1, 2, 3))
    node3 = Node3D(position=(4, 5, 6))
    
    # 同じ位置のノードは同じハッシュ
    assert hash(node1) == hash(node2)
    assert hash(node1) != hash(node3)
    
    # dictのキーとして使用可能
    node_dict = {node1: "value1"}
    assert node_dict[node2] == "value1"
    
    print("✅ ノードハッシュテスト成功")

if __name__ == "__main__":
    test_node_creation()
    test_f_cost()
    test_node_equality()
    test_node_comparison()
    test_node_hash()
    
    print("\n✅ 全てのNode3Dテストが成功しました！")
