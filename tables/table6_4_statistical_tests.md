# 表6.4 統計的検定結果の詳細

| 比較ペア | 指標 | t値 | p値 | Cohen's d | 効果サイズ |
|---------|------|-----|-----|-----------|------------|
| TA* vs AHA* | 経路長 | -0.250 | 0.803 | -0.037 | Negligible |
| TA* vs AHA* | 計算時間 | 6.548 | <0.001 | 0.955 | Large |
| TA* vs Theta* | 経路長 | -0.683 | 0.496 | -0.099 | Negligible |
| TA* vs Theta* | 計算時間 | 6.457 | <0.001 | 0.955 | Large |
| TA* vs FieldD*Hybrid | 経路長 | -0.665 | 0.507 | -0.096 | Negligible |
| TA* vs FieldD*Hybrid | 計算時間 | 6.482 | <0.001 | 0.958 | Large |
| AHA* vs Theta* | 経路長 | -0.415 | 0.679 | -0.061 | Negligible |
| AHA* vs Theta* | 計算時間 | -4.877 | <0.001 | -0.695 | Medium |
| AHA* vs FieldD*Hybrid | 経路長 | -0.397 | 0.691 | -0.058 | Negligible |
| AHA* vs FieldD*Hybrid | 計算時間 | -3.989 | <0.001 | -0.568 | Medium |
| Theta* vs FieldD*Hybrid | 経路長 | 0.017 | 0.987 | 0.002 | Negligible |
| Theta* vs FieldD*Hybrid | 計算時間 | 0.982 | 0.327 | 0.142 | Negligible |

## 注記

- **t値**: Welchのt検定統計量
- **p値**: 両側検定の有意確率（p < 0.05で有意）
- **Cohen's d**: 効果量（|d| < 0.2: Negligible, 0.2-0.5: Small, 0.5-0.8: Medium, ≥0.8: Large）
- **サンプル数**: 各手法について96シナリオ（成功したケースのみ）
- **検定方法**: Welchのt検定（等分散を仮定しない）
