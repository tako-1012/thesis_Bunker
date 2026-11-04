# 修論の図表の再生成

`conference/` で `python3 thesis/make_figures.py` を実行する。出力は `thesis/out/`。
PDF・PNG、LaTeX・Markdown・CSV、本文用 `numbers.tex`、入力ハッシュ `sources.json` を生成する。
既存結果・地図・論文には書き込まない。F1 の経路計画以外に新しい実験は行わない。

|出力|入力・列と計算|
|---|---|
|F1|`shizuoka_beach_las` の test の先頭2砂浜、200m、seed 0、漂着物なし・あり。`build_real` と既定重みの `run_planner_exact("A*"/"TA*-S")`。標高の陰影と2経路。|
|F2・T1|`results/real_beach_las/offline.csv` の `A*`, `TA*-S exact`。各 `kind,debris,planner` で100m・200mを平均し、48砂浜の `mean_cost,climb,p95_roll` を比較。長さ `length_xy` は差だけを表に含める。|
|T1の検定|上記48対の TA*-S − A* に両側Wilcoxon。ゼロ差しかなければ p=1。漂着物2条件×4指標の8検定を1つのHolm族として補正する。サイズを独立標本として扱わない。|
|F3|`results/real_beach_las/compare_C_online.csv` の `old_median,old_p90,new_median,new_p90`。各 `variant,side_m,debris` をそのまま並べる。旧データは対照として明記する。|
|F4・T2|`results/online_mission/missions.csv` の stale の `success,lethal_cells,dJ,n_replans`。半径・方法別に完走、接触走行数、完走時dJ中央値・90%、全走行再計画回数中央値。失敗走行も接触監査に含める。|
|F5・T2|`results/online_mission/plan_times_*.csv` の `seconds`。T2は半径・方法別、F5は事前地図・方法別で全呼出しの中央値・95%・最大。時間と1m/sでの走行距離は同じ数値の目盛り。CPU負荷に依存する既存測定値。|
|F6・T3|`results/online_mission/gazebo_claude/results.json` と既存 `trajectory.csv`、`ros2_jazzy/gz_checks/results/claude_docker_run_las/results.json`。既存走行のxy軌跡、roll/pitchの時系列、絶対角度95%。オンライン側の地図推定は記録xyから既存 `evaluate` と勾配の進行方向成分で計算。旧DEMと平地は対照として名前を明記。|
|F7|`results/weight_opt.csv` の test の `w,alpha,length_xy,p95_slope`。同じkind・size・seedのA*に対する長さ差[%]と傾斜95%値、それぞれの中央値。全既存重みを表示し、新たなパラメータ選択はしない。|

エネルギーの列・数値は出力しない。長さが短いという主張の文章も生成しない。
数値マクロは表・F5/F7統計の行順と列名から作り、値を手で転記しない。
Gazeboは過去の記録を読むだけで、今回物理シミュレーターを実行したものではない。
