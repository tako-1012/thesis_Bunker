# 論文用図一覧と推奨キャプション
以下は論文本文に入れることを推奨する図と短いキャプション案。

- [figures/terrain_comparison_hill_detour.png](figures/terrain_comparison_hill_detour.png)
  - キャプション案: "Hill detour scenario: comparison of Regular A*, Terrain-Aware A*, and Field D* Hybrid using point-average and segment-weighted terrain metrics."
  - 配置: 結果・分析セクションの主要図

- [figures/terrain_cost_comparison_hill_detour.png](figures/terrain_cost_comparison_hill_detour.png)
  - キャプション案: "Trade-off analysis between path length and terrain cost for hill_detour: TA* reduces point-average terrain multiplier but may increase total movement cost due to longer paths."
  - 配置: 同上（隣接して表示）

- [figures/path_detail_comparison.png](figures/path_detail_comparison.png)
  - キャプション案: "Detailed overlay of paths on elevation map (hill_detour). TA* avoids central hill peak whereas Regular A* crosses the peak."
  - 配置: ケーススタディ（サブセクション）

- [figures/elevation_profile_comparison.png](figures/elevation_profile_comparison.png)
  - キャプション案: "Elevation profiles along the planned paths: TA* shows lower peak and mean elevation compared to Regular A*."
  - 配置: ケーススタディ（サブセクション）

- その他シナリオ図
  - `figures/terrain_comparison_roughness_avoidance.png`
  - `figures/terrain_comparison_combined_terrain.png`

備考: 論文投稿先の形式に合わせて EPS/PDF 形式への変換を推奨（Matplotlib の `savefig(..., format='pdf')` など）。