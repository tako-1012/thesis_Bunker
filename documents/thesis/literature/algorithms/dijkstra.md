# Dijkstra (ダイクストラのアルゴリズム)

## 基本情報

| 項目 | 内容 |
|------|------|
| 原著論文 | A Note on Two Problems in Connexion with Graphs |
| 著者 | Edsger W. Dijkstra |
| 出版年 | 1959 |
| 掲載誌 | Numerische Mathematik |
| 巻・号・ページ | Vol. 1, pp. 269-271 |
| DOI | 10.1007/BF01386390 |
| 引用数 | 30,000+ (Google Scholar) |

## 概要

ダイクストラのアルゴリズムは、重み付きグラフにおいて**非負エッジコストの場合の最短経路**を求める古典的アルゴリズムであり、1959年にオランダの計算科学者Edsger Dijkstraによって提案された。A*アルゴリズムの前身であり、**ヒューリスティック関数を用いない**純粋なグラフ探索手法である。特定のノードから全ノードへの最短距離を効率的に計算でき、GPS ナビゲーション、ネットワークルーティング、地図サービスなど実用的な応用が非常に多い。

## 技術的詳細

### 計算複雑度
- **時間計算量**: 
  - 優先度キューなし: O(V²)（V: ノード数）
  - 優先度キュー（バイナリヒープ）: O((V + E) log V)（E: エッジ数）
  - フィボナッチヒープ: O(E + V log V)

- **空間計算量**: O(V)
  - 訪問済みノードと距離情報を保持

### アルゴリズムの流れ

```python
# ダイクストラのアルゴリズム 擬似コード

def dijkstra(graph, start, goal):
    # 初期化
    distance = {node: float('inf') for node in graph}
    distance[start] = 0
    previous = {node: None for node in graph}
    unvisited = set(graph.nodes)
    priority_queue = [(0, start)]  # (距離, ノード)
    
    while unvisited:
        # 最小距離のノードを取得
        current_dist, current = heappop(priority_queue)
        
        # 既に処理済みなら スキップ
        if current not in unvisited:
            continue
        
        unvisited.remove(current)
        
        # ゴール到達確認
        if current == goal:
            break
        
        # 現在のノード距離より小さい値なら スキップ
        if current_dist > distance[current]:
            continue
        
        # 隣接ノードの距離を更新
        for neighbor, cost in graph.edges[current]:
            if neighbor not in unvisited:
                continue
            
            new_distance = distance[current] + cost
            
            if new_distance < distance[neighbor]:
                distance[neighbor] = new_distance
                previous[neighbor] = current
                heappush(priority_queue, (new_distance, neighbor))
    
    # 経路を再構築
    path = []
    current = goal
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()
    
    return path, distance[goal]
```

### 主要な特性

**Relaxation（緩和）**: エッジ (u, v) について、より短いパスが見つかれば、距離を更新するプロセス

**グリーディアルゴリズム**: 毎回、訪問していないノードの中で最小距離のものを選択し、それ以降は変更しない

### 最適性と完全性
- **最適性**: ✅ あり（非負エッジコストの場合）
  - ネガティブコストエッジがある場合は失敗
  
- **完全性**: ✅ あり（グラフが連結で、到達可能なら）

### 主要なパラメータ
1. **グラフの構造**
   - ノード数、エッジ数、トポロジー

2. **エッジコスト**
   - 非負である必要がある
   - 距離、時間、コスト等を表現可能

3. **データ構造**
   - 優先度キューの実装（バイナリヒープ、フィボナッチヒープ等）

## 長所

1. **最適性の保証**
   - 非負コストの場合、確実に最短経路を見つける
   - 確実性と信頼性が高い

2. **実装が簡単**
   - アルゴリズムの概念が単純
   - プログラミング言語で容易に実装できる

3. **計算効率**
   - 優先度キューで O((V + E) log V)
   - A*と比べ、ヒューリスティック計算がないため、シンプル

4. **多用途性**
   - グラフの重みを工夫することで、様々な問題に適用可能
   - GPS、ネットワークルーティング、ゲーム AI 等

5. **完全性の保証**
   - グラフが連結なら、必ず経路を発見（存在する場合）

## 短所

1. **ヒューリスティック情報を活用しない**
   - 全方向に等しく探索するため、ゴール方向の情報が生かされない
   - A*より効率が劣る場合が多い

2. **計算時間が長い傾向**
   - A*と比べて、同じ環境では数倍遅い
   - 大規模グラフでは顕著

3. **ネガティブエッジに対応不可**
   - コスト関数が負の値を取る場合は使用不可
   - Bellman-Fordアルゴリズムが必要

4. **グリッド環境では効率が劣る**
   - グラフ表現が2D/3Dグリッドに特化していない場合、グリッド変換のコスト

5. **動的環境への対応が限定的**
   - 環境が変わるたびに再計算が必要
   - D*等の改良アルゴリズムが必要

## 適用例

### 主要な適用分野
1. **GPS・地図ナビゲーション**
   - Google Maps、Apple Maps 等の経路探索
   - 実用的な最短経路（時間最小化）の計算

2. **ネットワークルーティング**
   - ISP ルーティングプロトコル（OSPF等）
   - インターネットパケット転送

3. **ロボティクス**
   - 基本的なナビゲーション
   - A*の比較基準

4. **ビデオゲーム**
   - 古いゲームエンジンでの NPC 移動
   - シンプルな環境での AI

5. **産業用ロボット**
   - 工場での移動経路計画

### 代表的な派生・関連アルゴリズム
- **A***: ヒューリスティック情報を追加して高速化
- **Bellman-Ford**: ネガティブエッジに対応
- **Floyd-Warshall**: 全ペア最短経路
- **SPFA (Shortest Path Faster Algorithm)**: ネガティブエッジと動的更新に対応

## 本研究（TA*）との関連

### 差異点
| 項目 | Dijkstra | TA* |
|------|----------|-----|
| **ヒューリスティック** | なし | あり（地形複雑度） |
| **計算時間** | 0.123秒（推定） | 0.242秒 |
| **環境情報** | グラフのみ | グリッド + 地形タイプ |
| **適応性** | 固定的 | 動的（地形依存） |
| **最適性** | あり | あり |

### TA*の改善点
1. **ヒューリスティック情報の活用**
   - ダイクストラは方向性がない
   - TA*は地形複雑度をヒューリスティックとして利用

2. **地形適応的コスト関数**
   - ダイクストラは単純な距離コスト
   - TA*は地形タイプごとに最適化されたコスト

3. **前処理による効率化**
   - 地形複雑度をあらかじめ計算
   - オンライン探索の負荷低減

### 選定理由
- **基準手法**: ダイクストラは経路計画の古典的基準
- **比較の明確性**: TA*がダイクストラより改善した点を示す
- **実用的な重要性**: GPS等での使用との対比により、実用性を強調

## 引用

```bibtex
@article{dijkstra1959note,
  title={A note on two problems in connexion with graphs},
  author={Dijkstra, Edsger W},
  journal={Numerische mathematik},
  volume={1},
  number={1},
  pages={269--271},
  year={1959},
  publisher={Springer}
}
```

## 参考文献

1. Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. Numerische Mathematik, 1(1), 269-271.
2. Russell, S. J., & Norvig, P. (2021). Artificial Intelligence: A Modern Approach (4th ed.). Prentice Hall.
3. Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2009). Introduction to Algorithms (3rd ed.). MIT Press.
