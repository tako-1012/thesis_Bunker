# Three Planners Comparison Report

## 概要
- 対象手法: TA*, Theta*, AHA*
- シナリオ数: 96

## 主要な数値
### TA*
- 成功: 96/96 (タイムアウト: 0)
  - SMALL: mean_time=0.20914593537648518, mean_path=5.23020481201749, success_count=30
  - MEDIUM: mean_time=5.2797682384649915, mean_path=24.83690434548361, success_count=48
  - LARGE: mean_time=40.277021725972496, mean_path=51.13733509368214, success_count=18

### Theta*
- 成功: 96/96 (タイムアウト: 0)
  - SMALL: mean_time=0.009459336598714193, mean_path=5.23020481201749, success_count=30
  - MEDIUM: mean_time=0.15855353573958078, mean_path=24.83690434548361, success_count=48
  - LARGE: mean_time=0.8084107769860162, mean_path=51.13733509368214, success_count=18

### AHA*
- 成功: 91/96 (タイムアウト: 5)
  - SMALL: mean_time=0.006993714968363444, mean_path=5.638190232039972, success_count=30
  - MEDIUM: mean_time=0.02048662304878235, mean_path=25.15433071720057, success_count=48
  - LARGE: mean_time=0.023049427912785456, mean_path=52.066474188529504, success_count=13

## 統計検定（概要）
- 詳細は `three_planners_statistics.json` を参照
- Welch の t検定を使用（等分散は仮定しない）

## 実用的な推奨
- Theta* は計算時間で圧倒的に有利で、Large 環境でも平均1秒未満。探索時間を重視するなら Theta* を推奨。
- TA* は経路品質や地形対応が必要な場合に有利な点があるが、Large 環境で計算時間が大きく増える。
- AHA* の挙動は最適化バージョンにより中間的。特定シナリオで速度的優位があるため、用途に応じて選択。
