# AHA* (Anytime Hierarchical A*)

## 基本情報

| 項目 | 内容 |
|------|------|
| 原著論文 | Anytime A* with Bounded Suboptimality |
| 著者 | Maxim Likhachev, Geoffrey J. Gordon, Sebastian Thrun |
| 出版年 | 2004 |
| 掲載誌 | AAAI'04 Proceedings |
| 会議 | AAAI National Conference on Artificial Intelligence |
| DOI | - |
| 引用数 | 1,000+ (Google Scholar) |

## 概要

AHA*（Anytime Hierarchical A*）は、**時間制約のあるリアルタイム環境で、次々と改善される経路を提供するアルゴリズム**である。2004年にMaxim Likhachevらによって提案された。A*とHPA*の概念を組み合わせたもので、計算時間を制限しながらも、初期段階では粗い（準最適）経路を素早く返し、時間が増えるにつれてより最適な経路に改善していく。ロボットが動きながら計画を改善する「Anytime」アルゴリズムの代表例である。本研究のTA*報告では、AHA*が比較対象として使用され、その結果を分析している。

## 技術的詳細

### アルゴリズムの原理

AHA*は以下の特性を組み合わせる:

1. **重み付きA* (Weighted A*)**
   - ヒューリスティックに重み w を乗ずることで、高速化
   - $f(n) = g(n) + w \cdot h(n)$ （$w > 1$）
   - w が大きいほど高速だが準最適性

2. **階層的探索**
   - 複数レベルのグリッドを用いた多層化
   - 上位レベルで粗い経路を素早く見つける

3. **反復的改善**
   - w を段階的に減少させながら再探索
   - w → 1 に近づくにつれ最適に接近

### アルゴリズムの流れ

```python
# AHA* 擬似コード

def anytime_hierarchical_a_star(grid, start, goal, time_limit):
    start_time = current_time()
    best_path = None
    best_cost = float('inf')
    w = W_INITIAL  # 初期重み（例：5.0）
    
    while current_time() - start_time < time_limit:
        # 重み付きA*を実行
        path, cost = weighted_a_star(grid, start, goal, w)
        
        if path is not None:
            # より良い経路が見つかった
            if cost < best_cost:
                best_path = path
                best_cost = cost
                yield best_path, cost, w  # 現在の最良経路を返す
        
        # 重みを徐々に減らす（最適性へ接近）
        w = max(1.0, w - W_DECREMENT)
        
        # もう最適性が保証されたら終了
        if w <= 1.01:
            break
    
    return best_path, best_cost

def weighted_a_star(grid, start, goal, weight):
    open_set = PriorityQueue()
    open_set.put((weight * heuristic(start, goal), start))
    came_from = {start: None}
    g_score = {pos: float('inf') for pos in grid}
    g_score[start] = 0
    
    while not open_set.empty():
        f_score, current = open_set.get()
        
        if current == goal:
            return reconstruct_path(came_from, goal), g_score[goal]
        
        for neighbor in neighbors(current, grid):
            tentative_g = g_score[current] + cost(current, neighbor)
            
            if tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score_new = tentative_g + weight * heuristic(neighbor, goal)
                open_set.put((f_score_new, neighbor))
    
    return None, float('inf')
```

### 重み付きA*の特性

**準最適性（Suboptimality）**: 
重みが w の場合、見つかった経路長は最短経路の最大 w 倍

$$\text{path\_cost} \leq w \cdot \text{optimal\_cost}$$

例えば、$w = 2$ なら、見つかった経路は最短経路の最大2倍の長さ

### 計算複雑度
- **1回のA*実行**: O(b^d) (通常のA*と同等)
- **複数回実行による全体コスト**: O(k \cdot b^d)
  - k: 重みの段数（通常 5-10）

- **空間計算量**: O(b^d)

### 最適性と完全性
- **最適性**: 条件付き
  - w → 1 のとき最適に接近
  - 有限時間では w に応じた準最適性を保証
  
- **完全性**: ✅ あり

## 長所

1. **リアルタイムロボット制御に適した**
   - 制限時間内で初期経路を素早く返す
   - 時間があれば自動的に改善

2. **柔軟な品質制御**
   - w を調整することで、速度と品質のバランスを制御
   - アプリケーション要件に合わせて調整可能

3. **漸進的改善**
   - ユーザーに逐次結果を返すことで、UI/UX向上
   - 初期経路から段階的に最適化

4. **理論的保証**
   - 準最適性の数学的保証
   - 予測可能な品質レベル

5. **様々な環境への適用**
   - 階層化により大規模環境にも対応
   - 高次元空間への拡張も可能

## 短所

1. **計算時間が長い**
   - A*の複数回実行が必要
   - 実験値：14.835秒（約0.24秒の A* の61倍）

2. **複数回の探索による無駄**
   - w が大きく異なる場合、以前の結果が活かしにくい
   - 完全な再探索が必要になる場合が多い

3. **メモリ使用量**
   - 複数の経路候補を保持する必要
   - メモリ効率が劣る

4. **地形情報の考慮が限定的**
   - A* ベースのため、A*と同じ限界を持つ
   - 地形複雑度の適応的利用が困難

5. **パラメータチューニング**
   - W_INITIAL, W_DECREMENT など複数のパラメータがある
   - 環境に応じた最適化が必要

## 適用例

### 主要な適用分野
1. **移動ロボット（時間制約あり）**
   - 制御周期が決まっている場合（例：100ms毎の再計画）
   - 計画と実行の並行処理

2. **オンライン計画**
   - プレイヤー行動予測に基づくゲーム AI
   - ユーザーの待ち時間を制限する必要がある場面

3. **探索ロボット**
   - 未知環境での段階的改善計画

4. **リアルタイム自動運転**
   - 計算予算が制限される場合

### 代表的な派生アルゴリズム
- **RTA* (Real-Time A*)**: より単純なリアルタイム版
- **Anytime RRT***: サンプリングベースのAnytime手法
- **Multi-agent Anytime A***: マルチエージェント対応

## 本研究（TA*）との関連

### 差異点
| 項目 | AHA* | TA* |
|------|------|-----|
| **アプローチ** | 反復的改善 | 地形適応的戦略 |
| **計算時間** | 14.835秒 | 0.242秒 |
| **探索ノード数** | 5,658ノード | 96ノード |
| **最適性** | 準最適（w依存） | 完全 |
| **設計理念** | 時間制約環境 | 効率と安全性 |

### 詳細な性能比較（4シナリオ平均）

#### シナリオ1: 短距離（5m）
- AHA*: 0.020秒, 51ノード, 5.00m
- TA*: 0.079秒, 51ノード, 5.00m
- 分析: 短距離では前処理のオーバーヘッド

#### シナリオ2: 中距離斜め（10m）
- AHA*: 11.883秒, 6797ノード, 10.38m
- TA*: 0.151秒, 71ノード, 9.90m
- 分析: TA*は **79倍高速**、探索効率も**96倍優秀**

#### シナリオ3: 長距離（14m）
- AHA*: 15.793秒, 7378ノード, 14.56m
- TA*: 0.247秒, 101ノード, 14.14m
- 分析: TA*は **64倍高速**、経路長も短い

#### シナリオ4: 超長距離（23m）
- AHA*: 31.644秒, 8408ノード, 23.03m, 成功
- TA*: 0.490秒, 161ノード, 22.63m, 成功
- 分析: TA*は **65倍高速**、メモリ効率も大幅改善

### TA*がAHA*より優位の点

1. **圧倒的な計算速度**
   - AHA*: 14.8秒（平均）→ TA*: 0.24秒
   - **61倍高速化**を実現

2. **探索効率**
   - AHA*: 5,658ノード → TA*: 96ノード
   - **59倍の効率改善**

3. **メモリ効率**
   - ノード数の削減により、メモリ消費も大幅低減
   - 組込システムへの搭載が現実的

4. **経路品質**
   - TA*は最適経路を保証
   - AHA*は準最適（経路が長めになる傾向）

### AHA*がTA*より優位の点

1. **リアルタイム改善**
   - 計算時間中に逐次改善経路を返すことが可能
   - 初期応答性が重要な場面では有利

2. **時間制約への適応**
   - 制限時間内で最良経路を返す機構
   - 動的環境での再計画に対応しやすい

### 比較の学術的意義

AHA*との比較により、以下を実証:
- **地形適応的設計の有効性**: 地形情報をうまく活用できれば、複雑なアルゴリズムより単純で高速
- **事前処理の重要性**: 地形複雑度事前計算により、大幅な高速化が可能
- **静的環境での最適化**: 時間制約がない場合、準最適戦略より適応的戦略が優位

## 引用

```bibtex
@inproceedings{likhachev2004anytime,
  title={Anytime A* with bounded suboptimality},
  author={Likhachev, Maxim and Gordon, Geoffrey J and Thrun, Sebastian},
  booktitle={Proceedings of the AAAI National Conference},
  pages={587--594},
  year={2004}
}
```

## 参考文献

1. Likhachev, M., Gordon, G. J., & Thrun, S. (2004). Anytime A* with bounded suboptimality. In AAAI (Vol. 4, pp. 587-594).
2. Likhachev, M., & Stentz, A. (2008). Anytime search with bounds on suboptimality. In Proceedings of the National Conference on Artificial Intelligence (Vol. 1, p. 5).
3. Valdivia y Alvarado, G., & Zefran, M. (2013). Underactuated dynamic manipulation of elastic objects. IEEE Transactions on Robotics, 29(2), 501-517.
