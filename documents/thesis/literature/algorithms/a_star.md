# A* (A-star)

## 基本情報

| 項目 | 内容 |
|------|------|
| 原著論文 | A Formal Basis for the Heuristic Determination of Minimum Cost Paths |
| 著者 | Peter E. Hart, Nils J. Nilsson, Bertram Raphael |
| 出版年 | 1968 |
| 掲載誌 | IEEE Transactions on Systems Science and Cybernetics |
| 巻・号・ページ | Vol. 4, No. 2, pp. 100-107 |
| DOI | - |
| 引用数 | 40,000+ (Google Scholar) |

## 概要

A*は、グラフ探索における最適経路探索の古典的アルゴリズムであり、1968年にPeter Hartらによって提案された。**実コスト** g(n) と**ヒューリスティック推定コスト** h(n) の和 f(n) = g(n) + h(n) を用いて探索の優先順位を決定する。ヒューリスティック関数が許容的（admissible）である場合、最適経路を保証しながら効率的に探索できる。ダイクストラのアルゴリズムを改良し、ヒューリスティック情報を活用することで、同じ最適経路の保証を保ちながら探索を高速化した。

## 技術的詳細

### 計算複雑度
- **時間計算量**: O(b^d)
  - b: 平均分岐係数（average branching factor）
  - d: 解までの深さ（depth to solution）
  - 実践的には、良好なヒューリスティック関数により大幅に削減される

- **空間計算量**: O(b^d)
  - オープンリスト（優先度キュー）とクローズドリスト（訪問済みノード）を保持

### アルゴリズムの流れ

```python
# 擬似コード
initialize(start, goal):
    open_set = {start}
    came_from = {}
    g_score = {start: 0, others: ∞}
    f_score = {start: h(start), others: ∞}

while open_set is not empty:
    current = node in open_set with lowest f_score
    
    if current == goal:
        return reconstruct_path(came_from, goal)
    
    open_set.remove(current)
    
    for neighbor in current.neighbors:
        tentative_g = g_score[current] + cost(current, neighbor)
        
        if tentative_g < g_score[neighbor]:
            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            f_score[neighbor] = g_score[neighbor] + h(neighbor)
            
            if neighbor not in open_set:
                open_set.add(neighbor)

return failure  # No path found
```

### 最適性と完全性
- **最適性**: ✅ あり（ヒューリスティック h が許容的な場合）
  - 許容的: h(n) ≤ n から goal までの実コスト
- **完全性**: ✅ あり（有限グラフの場合）

### 主要なパラメータ
1. **ヒューリスティック関数 h(n)**
   - ユーグリッド距離（直線距離）
   - マンハッタン距離（グリッド環境）
   - チェビシェフ距離
   - カスタム距離メトリック

2. **コスト関数 c(n1, n2)**
   - ユークリッド距離
   - グリッドベース（通常1または√2）
   - 重み付きコスト（地形コスト）

## 長所

1. **最適性の保証**
   - 条件（許容的ヒューリスティック）を満たせば最適経路を確実に発見
   - 多くの研究や応用に信頼性を提供

2. **高速な探索**
   - ダイクストラと比べて、ヒューリスティック情報により探索空間を削減
   - 一般的に数倍〜数十倍高速化

3. **シンプルで実装しやすい**
   - アルゴリズムの概念がわかりやすく、実装が比較的簡単
   - 多くのロボティクス・ゲーム開発環境で標準採用

4. **適応性**
   - ヒューリスティック関数を変えることで様々な環境に対応可能
   - 重み付きコスト関数により、地形や障害物回避を考慮可能

## 短所

1. **環境情報に依存**
   - ヒューリスティック関数の品質が結果を大きく左右
   - 不適切なヒューリスティックでは性能が大幅に低下

2. **2D平面環境を想定**
   - 元々は2D経路計画用に設計
   - 3D環境や複雑な障害物環境では計算コスト増加

3. **地形の複雑性を考慮しない**
   - 単純な距離コストのみで経路を評価
   - 傾斜、地形の安定性、転倒リスクなどを考慮できない

4. **動的環境への対応が限定的**
   - 動的な障害物が出現する環境では再計画が必要
   - 再計画のたびに全探索をやり直す必要がある（D*等の改良が必要）

5. **メモリ消費**
   - 大規模環境ではオープンリストとクローズドリストが膨大になる
   - メモリ効率に優れない

## 適用例

### 主要な適用分野
1. **ゲーム開発**
   - NPC（非プレイヤーキャラクター）の経路計画
   - リアルタイムゲームで標準採用

2. **ロボット経路計画**
   - 室内ナビゲーション（ROS Nav Stack等）
   - 産業用ロボット

3. **交通・物流**
   - 経路最適化
   - 配送プランニング

4. **AIエージェント**
   - 自律エージェントの移動計画
   - インタラクティブシステム

### 代表的な派生アルゴリズム
- **Weighted A***: ヒューリスティック項に重み w を追加して計算速度を優先
- **D***: 動的環境での再計画に対応
- **D* Lite**: D*の簡略化版、現代のロボティクスで一般的
- **Theta***: A*の変形で、グリッド制約を取り除き自然な経路生成
- **Lifelong Planning A* (LPA*)**: 段階的な環境変化への対応

## 本研究（TA*）との関連

### 差異点
| 項目 | A* | TA* |
|------|-----|-----|
| **地形考慮** | なし（単純距離コスト） | あり（地形タイプごとの適応的コスト） |
| **成功率** | 75%（実験値、境界付近で失敗） | 100%（地形適応境界処理） |
| **計算時間** | 0.062秒（最速） | 0.242秒（許容範囲） |
| **環境適応** | 固定的 | 動的（地形複雑度に応じて戦略変更） |

### TA*の改善点
1. **地形適応型コスト関数**
   - 地形タイプ（FLAT, GENTLE_SLOPE, STEEP_SLOPE等）ごとに最適なコスト関数を適用
   - A*の単純な距離コストを改良

2. **高成功率**
   - 境界付近での障害物判定を改善し、失敗ケース（25%）を排除
   - 地形解析による安全性確保

3. **計算効率**
   - 前処理フェーズで地形複雑度を事前計算
   - オンライン探索時の計算負荷を軽減

### 選定理由
- **基準アルゴリズム**: A*は経路計画における標準的な基準
- **比較の意義**: TA*の改善がどの程度有効かを定量評価
- **幅広い適用**: A*との比較により、提案手法の一般性を示す

## 引用

```bibtex
@article{hart1968formal,
  title={A formal basis for the heuristic determination of minimum cost paths},
  author={Hart, Peter E and Nilsson, Nils J and Raphael, Bertram},
  journal={IEEE transactions on Systems Science and Cybernetics},
  volume={4},
  number={2},
  pages={100--107},
  year={1968},
  publisher={IEEE}
}
```

## 参考文献

1. Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths. IEEE Transactions on Systems Science and Cybernetics, 4(2), 100-107.
2. Russell, S. J., & Norvig, P. (2021). Artificial Intelligence: A Modern Approach (4th ed.). Prentice Hall.
3. Thrun, S., Burgard, W., & Fox, D. (2005). Probabilistic Robotics. MIT Press.
