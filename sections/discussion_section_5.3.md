## 5.3 Computational Complexity Analysis

The reason TA* requires an average of 15.46 seconds while FieldD*Hybrid requires only 0.495 seconds (a 31.2-fold difference) can be explained through computational complexity analysis.

### 5.3.1 Theoretical Computational Complexity

TA*'s computational complexity is characterized as $O(b^d \times k)$, where:
- $b$ = branching factor (26-neighborhood)
- $d$ = solution depth (average 50 steps)
- $k$ = terrain cost computation complexity (4 elements per node)

This complexity grows exponentially with respect to search depth $d$.

In contrast, FieldD*Hybrid comprises:
- Initial path generation via D* Lite: $O(n)$
- Local improvement via sliding window: $O(w \times h)$

Total complexity: $O(n)$ (linear), where:
- $n$ = number of grid nodes (~10,000)
- $w$ = window size (5×5 = 25)
- $h$ = improvement iterations (10)

This fundamental difference in theoretical complexity (exponential vs. linear) directly explains the 31.2-fold speedup observed empirically.

### 5.3.2 Computational Time Breakdown

Analysis of TA*'s 15.46-second execution time reveals the following breakdown (Figure 5):
- Terrain cost calculation: 40% (6.18s)
- Node exploration (A*): 35% (5.41s)
- Heuristic calculation: 15% (2.32s)
- Pruning judgment: 10% (1.55s)

Terrain cost calculation dominates the computation because each node requires evaluation of four elements: slope, stability, obstacle proximity, and distance. This detailed evaluation is the source of TA*'s computational overhead but also the foundation of its adaptive decision-making capability.

### 5.3.3 Complexity-Reliability Tradeoff

Table 4 illustrates the fundamental design philosophy difference between the two algorithms:
- **TA***: Exponential complexity enables detailed exploration, achieving 96.9% success rate
- **FieldD*Hybrid**: Linear complexity achieves 100% success rate by leveraging insights from TA*

This demonstrates that the terrain-adaptive concepts discovered through TA*'s detailed analysis were successfully integrated into FieldD*Hybrid's efficient design, enabling simultaneous achievement of computational efficiency and reliability.
