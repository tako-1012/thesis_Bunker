# 第3段階削除候補の詳細分析レポート

生成日時: 2025年12月24日

---

## 📊 分析概要

第3段階では以下の3つのカテゴリを分析しました：
1. **archive_20251117_old/** - 過去の実験データ
2. **presentation/** - プレゼン用画像
3. **重複設定ファイル** - nav2設定のコピー

---

## 1️⃣ archive_20251117_old/ の分析

### 基本情報
- **総ファイル数**: 29 件
- **総サイズ**: 208.27 KB
- **ファイル種類**: すべてJSON（実験結果）
- **期間**: 2025年11月9日〜11月17日

### ファイルリスト（サイズ順上位10件）

| ファイル名 | サイズ | 更新日時 |
|---|---|---|
| benchmark_results_20251114_143341.json | 12.89 KB | 2025-11-14 14:33:41 |
| benchmark_results_20251117_201445.json | 12.79 KB | 2025-11-17 20:14:45 |
| benchmark_results_20251114_155341.json | 12.78 KB | 2025-11-14 15:53:41 |
| benchmark_results_20251114_132704.json | 12.75 KB | 2025-11-14 13:27:04 |
| benchmark_results_20251117_191213.json | 11.10 KB | 2025-11-17 19:12:13 |
| benchmark_results_20251117_192826.json | 11.07 KB | 2025-11-17 19:28:26 |
| benchmark_results_20251117_194758.json | 10.92 KB | 2025-11-17 19:47:58 |
| benchmark_results_20251117_120210.json | 10.86 KB | 2025-11-17 12:02:10 |
| benchmark_results_20251117_145711.json | 10.86 KB | 2025-11-17 14:57:11 |
| benchmark_results_20251117_182935.json | 10.84 KB | 2025-11-17 18:29:35 |

### 内容分析
これらは実験の試行データで、最終結果は以下に保存されています：

**最終実験結果の保存場所**:
- `ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results/`
  - `full_benchmark_results.json` (139.13 KB) ← **最終版・保持必須**
  - `dijkstra_dwa_results.json` (29.95 KB) ← **最終版・保持必須**
  - `benchmark_results.json` (139.13 KB)
  - `multiscale_benchmark_results.json` (130.42 KB)

### ✅ 結論・推奨
- **削除推奨**: archive_20251117_old/ 全体（29ファイル、208KB）
- **理由**: 
  - 最終結果ファイルが別途保存済み
  - 中間試行データは再現性に不要
  - 削除しても論文・実験の再現に影響なし
- **削除コマンド**: `rm -rf results/archive_20251117_old/`

---

## 2️⃣ presentation/ 画像の分析

### 基本情報
- **総画像数**: 7 件
- **総サイズ**: 602.03 KB
- **すべて300dpi高解像度版**（プレゼン/論文用）

### 画像リスト

| ファイル名 | サイズ | 更新日時 | 用途推測 |
|---|---|---|---|
| all_planners_by_size_linear_300dpi.png | 91.59 KB | 2025-12-23 02:55:09 | 全プランナー比較（線形） |
| complexity_boxplot_300dpi.png | 99.58 KB | 2025-12-19 13:18:11 | 複雑度ボックスプロット |
| complexity_comparison_300dpi.png | 83.48 KB | 2025-12-19 13:18:11 | 複雑度比較 |
| complexity_comparison_linear_300dpi.png | 91.98 KB | 2025-12-23 02:13:40 | 複雑度比較（線形） |
| complexity_deviation_300dpi.png | 112.72 KB | 2025-12-23 01:33:19 | 複雑度偏差 |
| complexity_two_panel_300dpi.png | 103.77 KB | 2025-12-23 02:24:36 | 複雑度2パネル |
| legend_all_planners_300dpi.png | 18.91 KB | 2025-12-23 02:30:28 | 凡例 |

### 重複パターン
**complexity_comparison** に2つのバージョン:
- `complexity_comparison_300dpi.png` (83.48 KB)
- `complexity_comparison_linear_300dpi.png` (91.98 KB) ← 線形スケール版

→ これらは異なる可視化（対数 vs 線形）なので両方とも有効

### 使用状況
- **マークダウンファイルでの参照**: 0 件
- **注意**: ファイル名での検索のため、PowerPoint等での使用は未確認

### ✅ 結論・推奨
- **すべて保持推奨**
- **理由**:
  - すべて300dpi高解像度版（プレゼン/論文用）
  - 低解像度版の重複なし
  - 最終版として生成されたもの
  - サイズも小さい（合計602KB）
  - 削除して再生成するコストの方が高い
- **削除対象**: なし

---

## 3️⃣ 重複設定ファイルの分析

### 対象ファイル
```
ros2/bunker_ros2/bunker_gazebo/config/
├── nav2_purepursuit_w_shim.yaml       (11.32 KB, 2025-09-05 17:44:56)
└── nav2_purepursuit_w_shim copy.yaml  (11.58 KB, 2025-09-05 17:44:56)
```

### 差分の詳細

| パラメータ | オリジナル | コピー | 意味 |
|---|---|---|---|
| desired_linear_vel | 0.5 | 1.0 | 目標速度 (2倍) |
| max_linear_accel | 1.0 | 2.5 | 最大加速度 (2.5倍) |
| max_linear_decel | 1.0 | 2.5 | 最大減速度 (2.5倍) |
| rotate_to_heading_angular_vel | 0.6 | 3.2 | 回転速度 (5.3倍) |
| min_approach_linear_velocity | 0.05 | 0.3 | アプローチ速度 (6倍) |
| max_angular_accel | 0.6 | 3.2 | 角加速度 (5.3倍) |
| regulated_linear_scaling_min_speed | 0.25 | 2.0 | 最小速度 (8倍) |

**その他の変更**:
- `use_collision_detection: true` 追加（衝突検知有効化）
- `allow_reversing: false` 追加（後退禁止）
- `approach_velocity_scaling_dist` など新パラメータ追加

### 特徴比較

#### オリジナル版の特徴
- ✅ 保守的・安全な設定
- ✅ シンプルなパラメータ構成
- ✅ 低速動作（デバッグ向き）
- ❌ 本番実験には遅すぎる可能性

#### コピー版（copy.yaml）の特徴
- ✅ 高速・積極的な動作設定
- ✅ 衝突検知などの安全機能追加
- ✅ より詳細なパラメータチューニング
- ✅ 本番実験向けの設定
- ❌ パラメータが複雑

### launchファイルでの使用状況
**確認結果**: launchファイルでの明示的な参照は見つかりませんでした。

### ⚠️ 判断が必要
以下を確認してください：

1. **実験で使用した設定はどちらか？**
   - ROSのlaunchファイルを確認
   - 実験ログを確認
   - パラメータ値から推測

2. **判断基準**:
   - **実験で使用した方を保持**
   - 使用していない方を削除
   - または両方を保持して、`copy.yaml` → `_high_speed.yaml` などにリネーム

3. **推奨アクション（実験設定が不明な場合）**:
   ```bash
   # オリジナルを保持、copyを削除
   rm "ros2/bunker_ros2/bunker_gazebo/config/nav2_purepursuit_w_shim copy.yaml"
   
   # または、copyをリネーム（両方保持）
   mv "ros2/bunker_ros2/bunker_gazebo/config/nav2_purepursuit_w_shim copy.yaml" \
      "ros2/bunker_ros2/bunker_gazebo/config/nav2_purepursuit_w_shim_alternative.yaml"
   ```

---

## 📝 第3段階削除候補まとめ

### 削除推奨（確実に安全）
1. ✅ **archive_20251117_old/** 全体
   - 29ファイル、208 KB
   - コマンド: `rm -rf results/archive_20251117_old/`

### 保持推奨
2. ✅ **presentation/** の全画像
   - 7ファイル、602 KB
   - すべて最終版の300dpi画像

### 要判断（実験設定確認必要）
3. ⚠️ **nav2_purepursuit_w_shim copy.yaml**
   - 実験で使用した設定を確認後に削除
   - または代替設定としてリネーム

---

## 🎯 推奨削除コマンド（第3段階）

```bash
# archive_20251117_old/ を削除
cd /home/hayashi/thesis_work
rm -rf results/archive_20251117_old/

# nav2設定ファイル（どちらか選択）
# オプション1: copyを削除（オリジナルを使用していた場合）
rm "ros2/bunker_ros2/bunker_gazebo/config/nav2_purepursuit_w_shim copy.yaml"

# オプション2: copyをリネーム（両方保持したい場合）
mv "ros2/bunker_ros2/bunker_gazebo/config/nav2_purepursuit_w_shim copy.yaml" \
   "ros2/bunker_ros2/bunker_gazebo/config/nav2_purepursuit_w_shim_alternative.yaml"
```

---

## 💾 削除後の期待効果

- **削除ファイル数**: 約30件（archive + 設定ファイル1件）
- **削減サイズ**: 約220 KB
- **保持する重要ファイル**: 
  - 最終実験結果（full_benchmark_results.json等）
  - プレゼン用300dpi画像（7件）
  - 使用した設定ファイル（1件）

---

## 🔍 追加確認事項

1. **presentation/ 画像の実際の使用状況**
   - PowerPointファイルを確認
   - LaTeX論文を確認
   - 実際に使用した画像を特定

2. **nav2設定ファイルの使用実績**
   - 実験ログからパラメータ値を確認
   - 速度・加速度の実測値と照合
   - どちらの設定を使用していたか特定

3. **アーカイブの必要性**
   - 卒論提出後も研究を続ける場合
   - 過去の試行データが必要な場合
   - → その場合は外部バックアップ推奨
