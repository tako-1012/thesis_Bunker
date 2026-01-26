# D* Lite

## 基本情報

| 項目 | 内容 |
|------|------|
| 原著論文 | D* Lite |
| 著者 | Sven Koenig, Maxim Likhachev |
| 出版年 | 2002 |
| 掲載誌 | AAAI/IAAI Conference Proceedings |
| 会議 | AAAI National Conference on Artificial Intelligence |
| DOI | - |
| 引用数 | 2,000+ (Google Scholar) |

## 概要

D* Liteは、動的環境における効率的な経路再計画アルゴリズムであり、2002年にSven KoenigとMaxim Likhachevによって提案された。D*アルゴリズムの簡略版（Lite）として設計され、実装が簡単で実行速度も高速である。**環境情報が更新された時、全体の再探索を避けて、影響を受ける部分のみを効率的に更新**する。ロボットがセンサーで環境を探索しながら移動する場合、新たに発見された障害物に対して迅速に経路を変更できるため、リアルタイムロボット制御に適している。

## 技術的詳細

### 計算複雑度
- **時間計算量（1回の更新）**: O(n log n)
  - n: グリッドのセル数
  - ただし、環境変化が限定的であれば O(log n) 程度に削減可能

- **空間計算量**: O(n)
  - グリッドとオープンリスト、閉じたリストの情報を保持

### アルゴリズムの流れ

```python
# D* Lite 擬似コード
initialize():
    for all s:
        rhs[s] = ∞
        g[s] = ∞
    rhs[start] = 0
    open_set = {start}
    km = 0

compute_shortest_path():
    while min_key(open_set) < key(goal):
        u = pop_with_smallest_key(open_set)
        
        if g[u] > rhs[u]:  # Locally inconsistent (overconsistent)
            g[u] = rhs[u]
            for v in successors(u):
                update_vertex(v)
        else:  # Locally inconsistent (underconsistent)
            g[u] = ∞
            update_vertex(u)
            for v in successors(u):
                update_vertex(v)

update_vertex(u):
    if u != goal:
        rhs[u] = min(cost(u, v) + g[v] for v in predecessors(u))
    
    if u in open_set:
        open_set.remove(u)
    
    if g[u] != rhs[u]:
        open_set.add(u)

main():
    compute_shortest_path()
    
    while agent != goal:
        if g[agent] = ∞:
            return "NO PATH"
        
        agent = argmin(cost(agent, v) + g[v] for v in successors(agent))
        agent_move_to_next(agent)
        
        scan_for_changes()
        for all s in changed_set:
            update_vertex(s)
        
        km += heuristic_distance(previous_position, agent)
        compute_shortest_path()
```

### 主要な概念

**g-値**: ゴールからの推定コスト
**rhs-値（right-hand side）**: 先行ノードから計算した最小コスト
**一貫性（consistency）**: g[u] = rhs[u] のとき、ノード u は一貫的

D* Liteは、環境変化に応じて一貫性が失われたノードのみを再計画する。

### 最適性と完全性
- **最適性**: ✅ あり（最初の探索と環境変化時の再計画も）
- **完全性**: ✅ あり（経路が存在する限り）

### 主要なパラメータ
1. **グリッドサイズ**
   - 環境解像度を決定
   - 小さい → 正確だが遅い、大きい → 高速だが粗い

2. **コスト関数**
   - 各グリッドセルのコスト（障害物との距離など）
   - 動的に更新可能

3. **スキャン範囲**
   - ロボットのセンサー範囲
   - この範囲内で環境情報を更新

## 長所

1. **動的環境への効率的対応**
   - 全体の再探索を避け、影響を受ける部分のみ更新
   - 環境変化がローカルな場合、O(log n) の高速更新

2. **最適性の保証**
   - 環境が変化してもなお最適経路を保証
   - 完全性も保持

3. **リアルタイムロボット制御に適している**
   - ロボットがセンサー情報を取得しながら移動する場合に効率的
   - 計画と実行を同時に行える

4. **実装が比較的簡単**
   - D*よりもシンプルな構造
   - メインループが理解しやすい

## 短所

1. **グリッドベースの限界**
   - 2D/3D グリッド環境を前提
   - 高次元空間での直接適用は困難

2. **グリッド解像度に依存**
   - 解像度が粗いと経路品質が低下
   - 解像度が細かいと計算コスト増加

3. **地形情報の考慮が限定的**
   - グリッドセルのコストは単純な値
   - 複雑な地形特性の考慮には工夫が必要

4. **障害物の詳細形状を扱いにくい**
   - グリッド化により、曲線や複雑な形状が矩形化される
   - セーフティマージンの設定が重要だが、調整が難しい

5. **3D環境での計算量**
   - グリッド数が 3 乗で増加 (2D: n^2 → 3D: n^3)
   - 大規模な 3D 環境では計算がボトルネック

## 適用例

### 主要な適用分野
1. **移動ロボット（ナビゲーション）**
   - ROS Nav Stack で採用
   - 動的障害物への対応が必須な環境

2. **自動運転**
   - 動的環境での軌跡計画
   - リアルタイム再計画

3. **ドローン・UAV**
   - 3D グリッド環境でのナビゲーション
   - 計算時間制約のある本体組込システム

4. **探査ロボット**
   - 未知環境でのオンラインナビゲーション

### 代表的な派生アルゴリズム
- **D***: オリジナル版（より複雑だが同様の効率性）
- **LPA* (Lifelong Planning A*)**: A* の動的環境対応版
- **AD* (Anytime D*)**: リアルタイムで改善経路を提供

## 本研究（TA*）との関連

### 差異点
| 項目 | D* Lite | TA* |
|------|---------|-----|
| **設計対象** | 動的環境の再計画 | 静的環境での地形適応 |
| **環境情報** | ロボット移動中に取得 | 事前計算 |
| **適応戦略** | 環境変化への反応 | 地形複雑度への適応 |
| **実装の複雑性** | 中程度（キー管理等） | シンプル |

### 本研究での位置付け
1. **動的環境への対応が限定的**
   - TA*は静的な地形環境を想定（海岸清掃等）
   - D* Liteの動的環境対応は不要だが、技術的参考値

2. **比較対象外の理由**
   - TA*は未知環境探索ではなく、既知のDEM（数値標高モデル）を活用
   - D* Liteの強みである「動的情報更新」がTA*には適用外

### 選定理由（参考）
- D* Liteと組み合わせることで、動的環境対応型のTA*拡張が可能
- 学術的な将来展開として言及できる

## 引用

```bibtex
@inproceedings{koenig2002d,
  title={D* lite},
  author={Koenig, Sven and Likhachev, Maxim},
  booktitle={AAAI/IAAI},
  pages={476--483},
  year={2002}
}
```

## 参考文献

1. Koenig, S., & Likhachev, M. (2002). D* lite. In AAAI/IAAI (Vol. 1, pp. 476-483).
2. Stentz, A. (1995). The focussed D* algorithm for real-time replanning. In Proceedings of the 1995 International Joint Conference on Artificial Intelligence.
3. Koenig, S., & Likhachev, M. (2005). Lifelong planning A. Journal of Artificial Intelligence Research, 23, 95-123.
