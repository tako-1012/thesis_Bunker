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
3. Evaluation: safety/energy metrics, paired tests with Holm correction, sweep, ablation, noise, timing

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
- w is chosen on validation seeds by a fixed rule → w = 16

### 8. Main result
- 図: Table I（論文の表）を簡略化して表示
- A\* and Theta\* enter slopes above the limit in **76% / 82%** of scenarios
- TA\*-S: **never**; cost −48%, climb −40%, energy −5%, length +6.6% (medians vs A\*)
- 話すこと: いちばん大事なスライド。数字は3つまでに絞って話す。

### 9. Why not just a hard constraint?
- A\*-HC also avoids lethal cells, but hugs the limit: median max slope 23.7° vs 12.9° (TA\*-S)
- Paired tests: lower slope, roughness and climb, all p < 0.001
- 話すこと: 「二値の走行可否だけでよいのでは？」という質問への答えを先に出しておく。

### 10. Per terrain
- 図: Table II
- Largest energy gain on craters (−14.7%), smallest on hills (−0.7%)
- Rocky terrain: roughness along the path 113 mm → 43 mm

### 11. Trade-off over w
- 図: `sweep.png`
- Energy is lowest at w ≈ 2 (−9.6%); w = 16 is safety-oriented
- 話すこと: w はミッションごとに選ぶもの（安全重視か、エネルギー重視か）。

### 12. Robustness and time
- 図: `noise.png` と `time.png`
- With noisy maps, TA\* keeps a margin → less steep exposure than A\*-HC
- Python: 0.18 s (100 m), 0.82 s (200 m) median

### 13. Limitations and next steps
- Synthetic terrain → next: elevation maps from RTAB-Map on our BUNKER UGV
- Isotropic cost (roll not modelled), simple energy model, Python timing
- 話すこと: 実機データでの検証を「次にやること」として明言する。

### 14. Conclusion
- Robot-grounded cost + A\* + cost-aware shortcutting
- Removes excursions beyond the slope limit, halves the traversability cost, a few % longer
- Code and data: github.com/tako-1012/thesis_Bunker (`conference/`)

---

## 想定質問と答え方
- **Q. 新規性は？** → アルゴリズムの新規性は主張していない。貢献は「ロボットの限界値で正規化したコスト」「TA\*-S の性質」「再現可能な評価の手順」。
- **Q. Field D\* と比べないのか？** → 補間を使う手法との比較は今後の課題。今回は、同じ実装基盤で公平に比べられる手法に絞った。
- **Q. 実環境では？** → 標高マップさえあれば、そのまま同じ評価ができる。BUNKER＋RTAB-Map での検証を進めている（※実際に進めている場合のみこう答えること）。
- **Q. w=16 はどう決めた？** → 検証用シードで、事前に決めた規則（経路長の増加の中央値が10%以内）で選んだ。テスト用データでは調整していない。
- **Q. 計算時間は実用的か？** → Python で中央値 0.18 秒（100 m 四方）。C++ 化や D\* Lite による再計画でさらに短くできる。
