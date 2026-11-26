"""008 の保存した行列（pair_costs.csv）から、比べていなかった順番の決め方のコストを出し直す（Claude、2026-11-26）。

あとから足した確かめ（008 の指示書では前もって決めていない）。地点・行列・最適な順（terrain dir）は 008 の記録をそのまま使う。
- 選んだ順のまま：008 で地点を引いた順（0→1→…→n→0）。人が選んだ順の代わり（ランダムなので、人の順より悪い側に寄る）
- 近い順：直線距離で、いちばん近い未訪問の地点へ行く（同点は番号の小さい方）
コストはどれも同じ行列（κ=1/μ の向きのあるコスト、区間は平滑化済み）の和。
実行：cd conference && python3 results/tour_order_baselines/recompute.py
"""
import collections
import csv
import json
import math
import statistics as st
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]/'multi_goal_tour'
C = collections.defaultdict(dict)
for r in csv.DictReader(open(SRC/'pair_costs.csv')):
    k = (r['kind'], r['side_m'], r['seed'])
    i, j = int(r['i']), int(r['j'])
    C[k][(i, j)] = float(r['C_ij'])
    C[k][(j, i)] = float(r['C_ji'])
opt, pts = {}, {}
for r in csv.DictReader(open(SRC/'tours.csv')):
    k = (r['kind'], r['side_m'], r['seed'])
    if r['method'] == 'terrain dir':
        opt[(k, int(r['n_goals']))] = json.loads(r['order'])
    if int(r['n_goals']) == 12:
        pts[k] = json.loads(r['points'])


def cost(k, order):
    o = list(order)+[0]
    return sum(C[k][(a, b)] for a, b in zip(o, o[1:]))


def nearest(points, n):
    rem, cur, order = set(range(1, n+1)), 0, [0]
    while rem:
        cur = min(rem, key=lambda j: (math.dist(points[cur], points[j]), j))
        rem.remove(cur)
        order.append(cur)
    return order


def q90(v):
    return sorted(v)[int(.9*len(v))]


rows = []
for (k, n), order in sorted(opt.items()):
    best = cost(k, order)
    rows.append(dict(kind=k[0], side_m=k[1], seed=k[2], n_goals=n, optimal=best,
                     selected_pct=(cost(k, range(n+1))-best)/best*100,
                     nearest_pct=(cost(k, nearest(pts[k], n))-best)/best*100))
with open(Path(__file__).with_name('baselines.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
for n in (5, 8, 12):
    a = [r['selected_pct'] for r in rows if r['n_goals'] == n]
    b = [r['nearest_pct'] for r in rows if r['n_goals'] == n]
    print(f'{n} 地点 {len(a)} 件：選んだ順のまま 中央値 {st.median(a):.1f}% 90%値 {q90(a):.1f}% 最大 {max(a):.1f}% ｜ '
          f'近い順 中央値 {st.median(b):.1f}% 90%値 {q90(b):.1f}% 最大 {max(b):.1f}%')
