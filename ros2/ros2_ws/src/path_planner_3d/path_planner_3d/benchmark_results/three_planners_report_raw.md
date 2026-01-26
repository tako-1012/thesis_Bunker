# Three Planners Comparison Report (Raw TA* nosmooth)

## 概要
- TA* の `nosmooth` 結果を用いて Theta*, AHA* と比較

## 数値サマリ
### TA*
- 成功: 93/96 (タイムアウト: 3)
  - SMALL: mean_time=0.309, mean_path=5.485, success_count=30
  - MEDIUM: mean_time=10.662, mean_path=26.225, success_count=48
  - LARGE: mean_time=65.908, mean_path=48.222, success_count=15

### Theta*
- 成功: 96/96 (タイムアウト: 0)
  - SMALL: mean_time=0.009, mean_path=5.230, success_count=30
  - MEDIUM: mean_time=0.159, mean_path=24.837, success_count=48
  - LARGE: mean_time=0.808, mean_path=51.137, success_count=18

### AHA*
- 成功: 91/96 (タイムアウト: 5)
  - SMALL: mean_time=0.007, mean_path=5.638, success_count=30
  - MEDIUM: mean_time=0.020, mean_path=25.154, success_count=48
  - LARGE: mean_time=0.023, mean_path=52.066, success_count=13

## 注意点
- 入力の元データファイルが欠けている場合、該当手法のデータは空になります。
