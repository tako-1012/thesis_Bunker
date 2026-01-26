# RRT* (Rapidly-exploring Random Tree Star)

## 基本情報

| 項目 | 内容 |
|------|------|
| 原著論文 | Sampling-based Algorithms for Optimal Motion Planning |
| 著者 | Sertac Karaman, Emilio Frazzoli |
| 出版年 | 2011 |
| 掲載誌 | The International Journal of Robotics Research |
| 巻・号・ページ | Vol. 30, No. 7, pp. 846-894 |
| DOI | 10.1177/0278364911406761 |
| 引用数 | 6,000+ (Google Scholar) |

## 概要

RRT*は、高次元空間での最適経路計画のためのサンプリングベースのアルゴリズムであり、2011年にSertac KaramanとEmilio Frazzolliによって提案された。RRT（Rapidly-exploring Random Tree）の拡張版であり、**最適性を漸近的に保証**する。ランダムにサンプリングした点を根拠地（スタート）から成長させることで、障害物のある複雑な環境での経路探索を効率的に行える。RRT*では、新しく追加されたノードの近傍を探索し、より良い親ノードがあれば接続を変更することで、探索を進めるにつれて経路が最適に近づく。

## 技術的詳細

### 計算複雑度
- **時間計算量**: O(n log n)
  - n: サンプリング数
  - ログファクタは最近傍探索の効率により発生

- **空間計算量**: O(n)
  - n個のノードと辺の情報を保持

### アルゴリズムの流れ

```python
# RRT* 擬似コード
initialize(start, goal, max_iter, step_size):
    Tree V = {start}
    Tree E = {}
    
    for i in range(max_iter):
        # ランダムサンプルを生成
        x_rand = random_sample()
        
        # 最も近いノードを探索
        x_nearest = nearest_node(Tree V, x_rand)
        
        # 最も近いノードからstep_sizeだけ進む
        x_new = steer(x_nearest, x_rand, step_size)
        
        # 衝突チェック
        if not collision_free(x_nearest, x_new):
            continue
        
        # 近傍のノードを探索（重要）
        X_near = nearest_neighbors(Tree V, x_new, radius)
        
        # x_new の最適な親を探す
        x_min = x_nearest
        c_min = cost(x_nearest) + distance(x_nearest, x_new)
        
        for x_near in X_near:
            if collision_free(x_near, x_new):
                c_new = cost(x_near) + distance(x_near, x_new)
                if c_new < c_min:
                    x_min = x_near
                    c_min = c_new
        
        # x_new を親 x_min の下に追加
        Tree V.add(x_new)
        Tree E.add((x_min, x_new))
        
        # 再配線（rewiring）
        for x_near in X_near:
            c_near = cost(x_new) + distance(x_new, x_near)
            if c_near < cost(x_near):
                if collision_free(x_new, x_near):
                    parent_of_x_near = parent(x_near)
                    Tree E.remove((parent_of_x_near, x_near))
                    Tree E.add((x_new, x_near))
                    propagate_cost_update(x_near)
        
        # ゴール到達チェック
        if distance(x_new, goal) < step_size:
            return path_to_goal(x_new)
    
    return best_path_found()
```

### 最適性と完全性
- **最適性**: ✅ あり（漸近的最適性）
  - サンプリング数 n → ∞ のとき、発見される経路長は最適解に収束
  - 有限の n では準最適解を提供

- **確率的完全性**: ✅ あり
  - 十分なサンプリングがあれば、経路が存在する確率は1に近づく

### 主要なパラメータ
1. **サンプリング数（n）**
   - 多いほど最適に近い経路が得られるが、計算時間増加
   - 環境の複雑度と実時間要件で決定

2. **接続半径（r）**
   - r = r_0 * (log(n) / n)^(1/d)  （d: 次元数）
   - ノード数の増加に応じて動的に調整

3. **ステップサイズ（step_size）**
   - ランダムサンプルからの進む距離
   - 小さい→より正確だが遅い、大きい→高速だが粗い

4. **ゴール領域（goal_region）**
   - ゴール到達の判定閾値
   - 通常、ロボット直径程度

## 長所

1. **高次元空間への対応**
   - グリッドベースのアルゴリズムの次元爆発問題を回避
   - 7次元以上（ロボットアーム等）でも実用的

2. **複雑な環境での経路探索**
   - 障害物が多い、複雑な形状でも対応
   - グラフベース法では困難な問題を解ける

3. **確率的完全性と最適性**
   - 十分なサンプリングで最適性の保証
   - 有限時間での準最適解提供

4. **非ホロノミック制約への拡張が容易**
   - 車両モデル、非ホロノミック制約を組み込みやすい

## 短所

1. **計算コストが高い**
   - A*等と比べて、サンプリングベースのため計算が遅い
   - 実時間処理（リアルタイム0.1-1秒）が困難な場合が多い

2. **近傍探索のボトルネック**
   - 最近傍ノード探索に O(log n) かかる
   - 効率的なKD木などの実装が必須

3. **パラメータチューニングが必要**
   - サンプリング数、接続半径、ステップサイズなど
   - 環境に応じた調整が必要で、汎用性に欠ける場合がある

4. **経路品質の不確実性**
   - 最適性は漸近的であり、有限時間では最適とは限らない
   - 実験ごとに結果が異なる（確率的）

5. **地形情報を考慮できない**
   - サンプリングベースのため、地形複雑度やコストを直接考慮困難
   - カスタムコスト関数の設計が必要

## 適用例

### 主要な適用分野
1. **ロボットアーム（多自由度）**
   - 7軸以上のアームの経路計画で標準的
   - 製造業での利用が多い

2. **自動運転**
   - 高次元空間での軌跡計画
   - 複数の制約を考慮した計画

3. **ドローン・UAV**
   - 3D空間での経路計画
   - 非ホロノミック制約を含む

4. **タンパク質折りたたみ予測**
   - 高次元空間での構造探索
   - バイオインフォマティクス応用

### 代表的な派生アルゴリズム
- **Informed RRT***: サンプリング領域を絞り込んで効率化
- **RRT*-Smart**: 局所的な最適化で高速化
- **Anytime RRT***: リアルタイムで次々と改善する経路を生成
- **Fast Marching Trees (FMT*)**: グラフベースと サンプリングベースの融合

## 本研究（TA*）との関連

### 差異点
| 項目 | RRT* | TA* |
|------|------|-----|
| **アプローチ** | サンプリングベース | グラフベース（グリッド） |
| **計算時間** | 14.8秒（実験値） | 0.242秒 |
| **探索ノード数** | 5658ノード | 96ノード |
| **地形考慮** | 困難 | 直接的 |
| **最適性** | 漸近的 | 完全 |

### TA*の優位性
1. **圧倒的な高速化**
   - RRT*の約61倍高速（14.8秒 → 0.242秒）
   - リアルタイム実装が可能

2. **効率的な探索**
   - グリッドベースにより、5658ノード → 96ノード に削減
   - メモリ効率と速度の両面で優位

3. **地形適応的設計**
   - RRT*では困難な地形複雑度の直接的考慮
   - 安定性や転倒リスクを実装可能

### 選定理由
- **高次元/複雑環境の対比**: RRT*は複雑環境で得意だが、計算コストが課題
- **サンプリング vs グリッド**: 異なるアプローチの効率比較
- **実用性の検証**: リアルロボット実装における実用性の違いを示す

## 引用

```bibtex
@article{karaman2011sampling,
  title={Sampling-based algorithms for optimal motion planning},
  author={Karaman, Sertac and Frazzoli, Emilio},
  journal={The international journal of robotics research},
  volume={30},
  number={7},
  pages={846--894},
  year={2011},
  publisher={Sage Publications Sage UK: London, England}
}
```

## 参考文献

1. Karaman, S., & Frazzoli, E. (2011). Sampling-based algorithms for optimal motion planning. The International Journal of Robotics Research, 30(7), 846-894.
2. LaValle, S. M. (2006). Planning Algorithms. Cambridge University Press.
3. Kuffner Jr, J. J., & LaValle, S. M. (2000). RRT-connect: An efficient approach to single-query path planning. In IEEE International Conference on Robotics and Automation (ICRA), pp. 995-1001.
