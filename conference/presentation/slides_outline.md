# 発表スライド構成案（15分発表＋質疑を想定）

スライドの文面は英語、「話すこと」は日本語のメモです。図はすべて `conference/paper/figures/` にあります。
数値は `paper/generated/numbers.tex`（自動生成）と同じ値です。実験をやり直したら、ここも更新してください。

---

### 1. Title
**Terrain-Aware A\* with Robot-Grounded Traversability Costs: A Reproducible Evaluation for Tracked UGVs**
- 話すこと: 名前、所属、共著者。

### 2. Motivation
- Shortest path ≠ best path on uneven terrain
- Steep slopes → tipping and slipping risk, higher energy use
- Question: *how much does terrain awareness actually buy, and at what price?*
- 図: `examples.png` の ridge だけを切り出して大きく表示（A\* が尾根の斜面を越える様子）
- 話すこと: 「最短経路は、このように限界を超える斜面を平気で通ります」

### 3. Gap
- The idea (terrain cost in graph search) is old: Mars rovers, Field D\*
- Missing in many evaluations: robot-related metrics, binary-traversability baselines, a tuning/test split, paired statistics
- 話すこと: アルゴリズムが新しいとは主張しない、と最初にはっきり言う（質疑で突かれにくくなる）。

### 4. Contributions
1. Fully specified planner: robot-normalised cost + hard constraints, TA\* (provably optimal), TA\*-S (shortcutting that never increases cost)
2. Reproducible benchmark: 120 test + 60 validation scenarios, 4 terrain families × 3 scales
3. Evaluation: safety/energy metrics, paired tests with Holm correction, weight optimisation, ablation, noise, infeasible maps, timing

### 5. Traversability cost
- c = α·min(θ/θmax, 1) + β·min(ρ/ρsat, 1); θmax = 25°, ρsat = 0.10 m
- Normalised by **robot limits**, not by the per-map maximum
- Lethal: θ > θmax, or rocks inflated by the footprint
- 話すこと: マップごとの最大値で正規化すると、マップ間で比べられない（卒論のときの反省点でもある）。

### 6. TA\* and TA\*-S
- Edge cost k = d·(1 + w·(c_u + c_v)/2), accumulated in g
- Euclidean heuristic stays consistent → optimal path
- TA\*-S: accept a shortcut only if it is collision-free and not more costly
- 話すこと: 地形項は f ではなく g に入れないと、最適化の対象にならない、という点を強調。

### 7. Benchmark
- 図: `examples.png`（4地形）
- hills / ridge / craters / rocky; 50, 100, 200 m; slope-scaled relief
- Weights (w, α) are optimised on validation seeds only → balanced profile w = 8, α = 0.5

### 8. Main result
- 図: Table I（論文の表）を簡略化して表示
- A\* and Theta\* enter slopes above the limit in **76% / 82%** of scenarios
- TA\*-S: **never**; cost −40%, climb −39%, energy −7.3%, length +3.0% (medians vs A\*)
- 話すこと: いちばん大事なスライド。数字は3つまでに絞って話す。

### 9. Why not just a hard constraint?
- A\*-HC also avoids lethal cells, but hugs the limit: median max slope 23.7° vs 13.7° (TA\*-S)
- Paired tests: lower slope, roughness and climb, all p < 0.001
- 話すこと: 「二値の走行可否だけでよいのでは？」という質問への答えを先に出しておく。

### 10. Per terrain
- 図: Table II
- Largest energy gain on craters (−16.6%), smallest on hills (−3.6%)
- Rocky terrain: roughness along the path 113 mm → 37 mm

### 11. Weight optimisation
- 図: `weights.png`
- 41 weight settings on validation data; three mission profiles: energy (w=1), safety (w=32), balanced (w=8)
- Optimum is flat: neighbouring weights perform almost the same → no fine tuning needed
- 話すこと: 卒論では重みを経験的に決めていたが、今回は検証用データで最適化し、テスト用データで評価した。
- 話すこと: w はミッションごとに選ぶもの（安全重視か、エネルギー重視か）。

### 12. Robustness and time
- 図: `noise.png` と `time.png`、通れないマップの例 `demo/demo_wall_infeasible.png`
- Infeasible maps: TA\* correctly reports "no path" (30/30); A\* and Theta\* return paths over ~48° slopes
- With noisy maps, TA\* keeps a margin → less steep exposure than A\*-HC
- Python: 0.12 s (100 m), 0.48 s (200 m) median (TA\*-S)

### 13. Limitations and next steps
- Synthetic terrain → next: elevation maps from RTAB-Map on our BUNKER UGV
- Isotropic cost (roll not modelled), simple energy model, Python timing
- 話すこと: 実機データでの検証を「次にやること」として明言する。

### 14. Conclusion
- Robot-grounded cost + A\* + cost-aware shortcutting
- Removes excursions beyond the slope limit, cuts the traversability cost by ~40%, +3% length, −7% energy
- Code and data: github.com/tako-1012/thesis_Bunker (`conference/`)

---

## 想定質問と答え方
- **Q. 新規性は？** → アルゴリズムの新規性は主張していない。貢献は「ロボットの限界値で正規化したコスト」「TA\*-S の性質」「再現可能な評価の手順」。
- **Q. Field D\* と比べないのか？** → 補間を使う手法との比較は今後の課題。今回は、同じ実装基盤で公平に比べられる手法に絞った。
- **Q. 実環境では？** → 標高マップさえあれば、そのまま同じ評価ができる。BUNKER＋RTAB-Map での検証を進めている（※実際に進めている場合のみこう答えること）。
- **Q. 重み（w=8, α=0.5）はどう決めた？** → 検証用シードだけで41通りを試し、エネルギーと傾斜のトレードオフの「折り合いが一番良い点」（パレートフロントの膝）を選んだ。テスト用データでは調整していない。最適値の周りは平らなので、多少ずれても性能はほとんど変わらない。
- **Q. 計算時間は実用的か？** → Python で中央値 0.18 秒（100 m 四方）。C++ 化や D\* Lite による再計画でさらに短くできる。
