# 📚 卒論: TA* (Terrain-Aware A*) アルゴリズム

**研究テーマ**: 地形適応型3D経路計画アルゴリズムの開発  
**提案手法**: TA* (Terrain-Aware A*)  
**応用分野**: 農業ロボットの自律ナビゲーション

---

## 🎯 研究概要

地形の局所特性を分析し、最適なコスト関数を動的に選択する適応型経路計画アルゴリズム「TA*」を提案。
従来のA*やハイブリッドA*と比較して、**100%の成功率**と**61倍の高速化**を達成。

### 主要な貢献
1. **8種類の地形タイプ分類**（平地、傾斜、障害物密集など）
2. **地形適応型コスト戦略**の動的選択
3. **前処理+オンライン探索のハイブリッド設計**
4. **性能最適化**（サンプリング、キャッシュ機構）

---

## 📂 プロジェクト構成

```
thesis_work/
├── ta_star_plus.py               # TA* アルゴリズム本体
├── terrain_cost_calculator.py    # 地形コスト計算モジュール
├── ros2/                         # ROS2ワークスペース
│   └── ros2_ws/src/bunker_ros2/path_planner_3d/
│       └── terrain_aware_astar_advanced.py  # ROS2統合実装
├── scripts/                      # ベンチマーク・分析・可視化スクリプト群
├── scenarios/                    # ベンチマークシナリオ定義
├── terrain_test_scenarios/       # 地形テストデータ（.npz形式）
├── results/                      # 実験結果
├── benchmark_results/            # ベンチマーク出力JSON
├── figures/                      # 論文・発表用図表
│   ├── final/                    # 最終版の図
│   └── presentation/             # 発表スライド用の図
├── thisis_write/                 # 論文執筆ファイル（LaTeX等）
├── documents/                    # 参考文献・関連資料
├── docs/                         # 調査・分析レポート（Markdown）
├── archive/                      # 過去の実装・記録
└── unity/                        # Unity可視化プロジェクト
```

---

## 🖥️ 実験環境

- OS: Ubuntu 22.04 LTS
- Python: 3.10
- 主要ライブラリ: NumPy, Matplotlib, SciPy, Open3D, NetworkX
- ロボットOS: ROS2 Humble

---

## 📦 データセットについて

`dataset*.json` は容量が大きいため **Git管理対象外**（`.gitignore` に設定済み）です。

| ファイル | サイズ | 内容 |
|---------|--------|------|
| `dataset3_scenarios.json` | 270MB | 主要ベンチマークデータ（96シナリオ） |
| `dataset3_scenarios_no_terrain.json` | 78MB | 地形情報なし版 |
| `dataset2_scenarios.json` | 50MB | 旧バージョンデータ |

**復元方法**: バックアップからプロジェクトルートに配置してください。

---

## 🚀 実行手順

### **1. ベンチマーク実行**
```bash
python3 scripts/run_fieldd_96_benchmark.py
```

### **2. 結果サマリー確認**
```bash
python3 scripts/final_results_summary.py
```

### **3. 論文用図表生成**
```bash
python3 scripts/generate_figures.py
```

---

## 📊 主要結果

| アルゴリズム | 成功率 | 平均計算時間 | 平均探索ノード |
|------------|--------|------------|--------------|
| A* | 75.0% | 0.062秒 | 74ノード |
| AHA* | 100.0% | 14.835秒 | 5658ノード |
| **TA*** | **100.0%** | **0.242秒** | **96ノード** |

---

**最終更新**: 2026年3月24日
