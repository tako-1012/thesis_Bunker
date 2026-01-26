# 研究概要

## タイトル
不整地環境における自律移動ロボットのための地形考慮型適応的経路計画

## 著者・所属
杉原虎太朗
九州工業大学 知的システム工学科
指導教員: 林英治 教授
実施期間: 2025年度

## 概要（要旨）
本研究は，ロボットが不整地（丘陵・凹凸・高粗さ領域）を走行する際に，単純な最短経路ではなく，「地形コスト」を考慮して安全かつ効率的に経路を生成する手法を提案する。主要な成果として，既存のField D* Hybridの地形考慮改良，および新規に提案したTerrain-Aware A*（TA*）を実装・評価し，複数シナリオで比較を行った。

## 主な貢献
- Field D* Hybridに地形重み（斜面・粗さ・密度）を導入し，経路最適化へ統合。
- Terrain-Aware A*（TA*）を設計・実装（パラメータ: `terrain_weight`, `heuristic_multiplier`, pruning 等）。
- 3つの設計シナリオ（`hill_detour`, `roughness_avoidance`, `combined_terrain`）を生成・公開。
- 6手法（Regular A*, TA*, Field D* Hybrid ほか）を比較し，2種類の地形指標（点平均法とセグメント重み法）を実装・提示。
- hill_detourの詳細解析により，TA*が高地を回避する一方で経路長が増加し得るトレードオフを明示。

## 実験設定（簡潔）
- グリッド: 100×100、ボクセル高20、解像度: 0.2 m
- 指標: path_length（m）、nodes_explored、computation_time（s）、地形コスト（Method A: point-average、Method B: segment-weighted）
- タイムアウトおよびノード上限を設定して大爆発を防止

## 主要結果（ハイライト）
- Field D* Hybrid: 移動コストで平均 4.6% 短縮、計算時間の代表値 1.21 s
- Terrain-Aware A*: 点平均で avg_mult -40.3% の地形改善達成。ただし経路長は +19.7%（hill_detourの代表例）
- 6手法比較を実施し，視覚化・JSON形式での結果を出力

## 解釈と推奨
- 実運用や論文一次指標としてはセグメント重み法（Method B：実際の移動コストに近い）を推奨。点平均法は地形回避の“やり方”を説明する補助指標として有用。
- TA*は局所的な地形回避に有効だが，パラメータ調整（`terrain_weight` と `heuristic_multiplier`）が重要。過度の地形重視はノード爆発を招く。

## 参考図・データ保存場所（ワークスペース）
- 生成図: `figures/` に PNG を保存（`terrain_comparison_*`, `terrain_cost_comparison_*`, `path_detail_comparison.png`, `elevation_profile_comparison.png` 等）
- 結果JSON: `benchmark_results/terrain_methods_comparison.json`, `benchmark_results/terrain_astar_tuning.json`, `benchmark_results/hill_detour_path_analysis.json`

## 次のステップ（短期）
- 図の最終スタイリング（論文規程に合わせた版）
- 地形コスト計算のキャッシュ化でTA*の高速化
- 論文草稿の章割りに基づく図表埋め込みと脚注の追加
