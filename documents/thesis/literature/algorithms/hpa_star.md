# HPA* (Hierarchical Pathfinding A*)

## 基本情報

| 項目 | 内容 |
|------|------|
| 原著論文 | Hierarchical Path Planning |
| 著者 | Adi Botea, Martin Müller, Jonathan Schaeffer |
| 出版年 | 2004 |
| 掲載誌 | AAAI'04 Proceedings |
| 会議 | AAAI National Conference on Artificial Intelligence |
| DOI | - |
| 引用数 | 800+ (Google Scholar) |

## 概要

HPA*（Hierarchical Pathfinding A*）は、大規模グリッド環境での高速経路計画を実現するアルゴリズムであり、2004年にAdi BoteaらによってゲームAIの文脈で提案された。**環境を階層的に抽象化**し、上位レベルの粗いグリッド上で経路計画を行い、その後に下位レベルの詳細グリッド上で局所的な経路を計算する。この多層構造により、大規模な環境でも A* に比べて数倍〜数百倍高速化できる。ゲーム開発やリアルタイムシステムでの採用実績が多い。

## 技術的詳細

### 計算複雑度
- **時間計算量**:
  - オフライン前処理: O((n/c)² log(n/c))
  - クエリ時間: O(n/c * log(n/c))
  - n: グリッドセル数、c: クラスタサイズ

- **空間計算量**: O(n)
  - マルチレベルグラフ、クラスタ情報を保持

### 階層的構造

```
レベル 1 (粗い抽象化)
┌─────────────────┐
│ ┌─────┬─────┐   │
│ │◎   │  ◎  │   │    ◎: ノード (大規模エリア)
│ ├─────┼─────┤   │
│ │     │  ◎  │   │
│ └─────┴─────┘   │
└─────────────────┘
         ↓ 詳細化
レベル 0 (詳細な実グリッド)
┌─────────────────┐
│············▓····│    ·: 自由セル
│·●····▓····▓····│    ●: スタート
│·····················│    ◎: ゴール
│····▓▓▓▓▓▓▓····│    ▓: 障害物
│···········◎····│
└─────────────────┘
```

### アルゴリズムの流れ

```python
# HPA* 擬似コード

# 前処理フェーズ（オフライン）
preprocess():
    # グリッドをクラスタに分割
    clusters = divide_into_clusters(grid, CLUSTER_SIZE)
    
    # 各クラスタ内のエントランス（接続点）を同定
    for cluster in clusters:
        entrances[cluster] = identify_entrances(cluster)
    
    # クラスタレベルのグラフを構築
    abstract_graph = create_abstract_graph(clusters, entrances)
    
    # クラスタ内の エントランス間を接続
    for cluster in clusters:
        intra_cluster_paths = compute_intra_cluster_paths(cluster, entrances)

# クエリフェーズ（オンライン）
find_path(start, goal):
    # スタート/ゴール点に最も近いエントランスを見つける
    start_entrance = find_nearest_entrance(start)
    goal_entrance = find_nearest_entrance(goal)
    
    # 抽象グラフ上で A* を実行
    abstract_path = A_star(abstract_graph, start_entrance, goal_entrance)
    
    # 抽象経路から詳細な経路を構築
    detailed_path = []
    detailed_path += local_path(start, start_entrance)
    
    for i in range(len(abstract_path) - 1):
        entrance1 = abstract_path[i]
        entrance2 = abstract_path[i+1]
        detailed_path += precomputed_path(entrance1, entrance2)
    
    detailed_path += local_path(goal_entrance, goal)
    
    return detailed_path
```

### 主要な概念

**クラスタ（Cluster）**: グリッドを一定サイズ（通常 8×8, 16×16）で分割した領域

**エントランス（Entrance）**: クラスタ境界上で、異なるクラスタ間を移動できる点

**抽象グラフ**: クラスタレベルでのノードとエッジを表現

### 最適性と完全性
- **最適性**: ✗ なし（層状構造により最適性は保証されない）
  - ただし、実装次第で十分に最適に近い経路を得られる
  
- **完全性**: ✅ あり（経路が存在する限り）

## 長所

1. **大規模環境での高速化**
   - 数百×数百グリッド環境でも A* より数倍〜数百倍高速
   - ゲーム環境（数千×数千セル）での実装が現実的

2. **キャッシング効果**
   - クラスタ内の経路をあらかじめ計算（前処理）
   - クエリ時にはキャッシュから即座に取得

3. **メモリ効率**
   - オープンリストが小さく、メモリ節約が顕著
   - コンソールゲーム等の制限環境で採用

4. **並列化可能**
   - 複数クラスタの前処理を並列実行可能
   - マルチスレッド実装に適した構造

## 短所

1. **最適性の喪失**
   - 階層抽象化により、最短経路を見落とす場合がある
   - クラスタサイズが大きいほど、誤差が大きくなる可能性

2. **前処理コストが大きい**
   - エントランス同定、エントランス間経路計算に時間が必要
   - 動的環境では前処理を頻繁に更新する必要がある

3. **パラメータ（クラスタサイズ）に敏感**
   - クラスタサイズが小さい→高精度だが高速化の効果が限定的
   - クラスタサイズが大きい→高速だが経路品質低下

4. **地形複雑度を考慮しにくい**
   - 階層化により地形情報が失われやすい
   - 傾斜や安定性といった複雑な属性の組み込みが困難

5. **不規則環境への適用が限定的**
   - 正方形クラスタ前提のため、不規則な障害物配置には工夫が必要

## 適用例

### 主要な適用分野
1. **ゲーム開発**
   - リアルタイムRTS（Real-Time Strategy）ゲーム
   - 大規模マップでの NPC 移動計画

2. **ゲームエンジン**
   - Unity、Unreal Engine の AI ナビゲーションの参考
   - 実装は簡略化されているが、コンセプトは継承

3. **オンラインゲーム**
   - サーバー側の複数プレイヤーパス計画
   - スケーラビリティが必須

### 代表的な派生アルゴリズム
- **PHA* (Partial Hierarchical A*)**: より細粒度な階層化
- **AAA* (Approximate Autonomy Algorithm)**: 誤差許容度を動的に調整
- **Multi-level Pathfinding**: 3 層以上の多層化

## 本研究（TA*）との関連

### 差異点
| 項目 | HPA* | TA* |
|------|------|-----|
| **階層化** | あり（複数レベル） | なし（単一グリッド） |
| **地形考慮** | 限定的 | 直接的（地形タイプごと） |
| **計算時間** | 0.020秒（実験値） | 0.242秒 |
| **最適性** | なし | あり（条件付き） |
| **環境適応** | クラスタサイズ依存 | 地形複雑度依存 |

### TA*がHPA*より優位の点
1. **最適性の保証**
   - HPA*は最適性なし
   - TA*は条件付き最適性を提供

2. **地形適応**
   - HPA*は地形情報を層状化で失いやすい
   - TA*は地形複雑度を直接的に活用

3. **パラメータの単純性**
   - HPA*はクラスタサイズ調整が複雑
   - TA*は地形分析パラメータで統一的

### TA*がHPA*より劣る点
1. **計算速度**
   - HPA*: 0.020秒 vs TA*: 0.242秒 (約12倍遅い)
   - ただし HPA*は最適性がない

2. **大規模環境での スケーラビリティ**
   - HPA*は階層化により超大規模環境に対応
   - TA*はグリッドサイズに線形依存

### 選定理由
- **階層化アプローチの対比**: グリッド分割戦略の異なるアプローチ
- **速度と精度のトレードオフ**: HPA* は速度重視、TA* は精度重視
- **ゲーム vs ロボティクス**: 異なる応用分野での最適化の違い

## 引用

```bibtex
@inproceedings{botea2004hierarchical,
  title={Hierarchical pathfinding},
  author={Botea, Adi and M{\"u}ller, Martin and Schaeffer, Jonathan},
  booktitle={Proceedings of the AAAI National Conference},
  pages={194--200},
  year={2004}
}
```

## 参考文献

1. Botea, A., Müller, M., & Schaeffer, J. (2004). Hierarchical pathfinding. In AAAI (Vol. 4, pp. 194-200).
2. Sturtevant, N. R. (2007). Benchmarks for grid-based pathfinding. Transactions on Computational Intelligence and AI in Games, 1(2), 144-148.
3. Demyen, D., & Buro, M. (2006). Efficient triangulation-based pathfinding. In AAAI (Vol. 6, pp. 942-947).
