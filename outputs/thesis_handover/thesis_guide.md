# 論文執筆ガイド

## 推奨章構成（博士/修士論文形式に合わせる）
1. 序論
  - 背景、研究の動機、目的、貢献の要約
2. 関連研究
  - 経路計画、地形評価、Field D*/A* 系の先行研究
3. 問題定式化
  - 環境モデル、地形コスト定義（斜面・粗さ・密度）、評価指標
4. 提案手法
  - Field D* Hybrid の地形拡張
  - Terrain-Aware A* のアルゴリズム詳細（擬似コード、パラメータ）
5. シナリオ設計
  - `hill_detour`, `roughness_avoidance`, `combined_terrain` の設計意図とパラメータ
6. 実験設定
  - ハードウェア、ソフトウェア、メトリクス、タイムアウト条件
7. 結果と分析
  - 定量比較（表）、トレードオフ図、ケーススタディ（hill_detourの詳細解析）
8. 考察
  - なぜTA*は地形を避けるのか、増加した移動コストの解釈、実用上の指針
9. 結論と今後の課題

## 図表配置案
- Fig.1: システム概念図（手法のフロー） — 序論/提案手法
- Fig.2: シナリオマップ（hill_detour） — シナリオ設計
- Fig.3: `terrain_comparison_both_methods_hill_detour.png` — 結果と分析（セクション7）
- Fig.4: `terrain_tradeoff_analysis_hill_detour.png` — トレードオフ（セクション7）
- Fig.5: path_detail / elevation_profile — ケーススタディ（サブセクション）

## 表（テーブル）案
- Table 1: 各手法の代表性能（path_length, terrain_cost(Method B), nodes, time）
- Table 2: TA* のパラメータスイープ結果（`terrain_astar_tuning.json`の要約）

## 実装ノート（査読者向け補遺）
- 主要設定やランダムシードを `scripts/` に記録
- 再現コマンド例（READMEに追加）:

```bash
python3 scripts/create_terrain_scenarios.py
python3 scripts/run_terrain_experiments.py --scenarios hill_detour
python3 scripts/update_and_plot_terrain_costs.py
```

## 書き方のヒント
- Metric B（セグメント重み）は「実際の移動コスト」に近いため、主要な結果の本文ではこれを説明指標として扱う。
- Method A（点平均）は付録/補助図で示し、地形回避の直観的説明に使う。
- hill_detour のケーススタディでは経路図（拡大）と標高プロファイルをセットで提示する。

## 推奨順序（短期スプリント）
1. 図の最終化（高解像度 PNG / EPS）
2. 論文本文の草稿（序論→関連研究→手法）
3. 結果・考察の章を埋める
4. 査読者向け補遺（再現手順）を整備
