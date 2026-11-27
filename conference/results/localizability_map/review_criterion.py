"""Claude のレビュー（2026-11-27）：「位置が決まらない」の判定を、点の数を考えた判定に変えると、結果がどう変わるか。

あとから足した確かめ（071 の指示書では前もって決めていない）。071 の判定は「1m 以上ずらした所の二乗平均の差が σ²（σ=0.05m）未満なら決まらない」。
比べる判定：「その差に重なったマスの数 N を掛けた和が 9σ²（3σ 相当）未満なら決まらない」（マスごとに独立な雑音だけを考えた場合）。
実行：cd conference && python3 results/localizability_map/review_criterion.py
"""
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for path in sorted((HERE/'points').glob('*.npz')):
    a = np.load(path)
    T, mse, n, cat, R = a['trials_cell_cell_deg'], a['mse_m2'], a['overlap_n'], a['category'], a['radii_m']
    origin = (T == 0).all(1)
    for ri, r in enumerate(R):
        base = mse[:, ri, origin][:, 0]
        loose = np.zeros(len(base), bool)
        for ax in range(3):
            scale = .5 if ax < 2 else r*np.pi/180
            sel = [j for j, t in enumerate(T) if (t != 0).sum() == 1 and t[ax] != 0 and abs(t[ax])*scale >= 1.]
            loose |= ((mse[:, ri, sel]-base[:, None])*n[:, ri, sel] < 9*.05**2).any(1)
        print(f'{path.stem} R={int(r)} 071 の判定で決まる点以外 {100*(cat[:, ri] != "determined").mean():.1f}% '
              f'| 点の数を考えた判定で決まらない {100*loose.mean():.1f}% | 重なったマスの数の中央値 {int(np.median(n[:, ri, origin]))}')
