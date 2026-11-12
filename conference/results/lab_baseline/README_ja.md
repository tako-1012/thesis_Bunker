# 研究室の地形コストとの比較（指示書031）

既存の地図・プランナー・結果は編集しない。研究室の非公開コードは読まず、指示書031の説明だけからGeometryLayerの式を実装する。
格子は研究室の0.2mではなく013の0.5mで、点の平均を計算し直さず既存DEMを入力する。
8方向の絶対高低差/距離の平均なので、平面の幾何学的な勾配の大きさとは違う。斜めの距離1.41、角度換算57.3をそのまま使う。
0.1/0.2/0.5/0.8×254はROSのunsigned charの境界で切り捨てる（25/50/127/203）。非公開コードの丸め方自体は再確認できないため、この境界の仮定を開示する。

## NavFnの確認したソース

Nav2 navigation2、Jazzy、nav2_navfn_planner **1.3.14**。
コミット `94d1c2a345dda6ff637e6a72c9101d927ee99f19`。

- [navfn.cpp / NavFn::setCostmap](https://github.com/ros-navigation/navigation2/blob/94d1c2a345dda6ff637e6a72c9101d927ee99f19/nav2_navfn_planner/src/navfn.cpp#L247)
- [navfn.hpp / 定数](https://github.com/ros-navigation/navigation2/blob/94d1c2a345dda6ff637e6a72c9101d927ee99f19/nav2_navfn_planner/include/nav2_navfn_planner/navfn.hpp#L52)
- `sources/` に取得したソース全文とURL・SHA-256・版を保存した。ソースの著作権・ライセンス表示はそのまま。

`isROS=true, allow_unknown=true`：0〜252は `int(50 + 0.8*c)`、254以上になる場合は253へ制限。入力253/254は内部254（通行不可）。入力255（不明）は内部253（通行可能、高コスト）。
Pythonはそのコストを使う8近傍グラフのA*を用いる。辺は両端コストの平均×移動距離で、角抜けを禁止する。全通行コストが50以上なので既存のEuclidヒューリスティックは許容的で、同じグラフのDijkstraと同じ最適解になる。
`NavFn::setupNavFn(true)`（同じcppの342行目以降）に合わせ、外周の1セルを通行不可にする。始点・終点がそこにある場合も移動せず失敗として記録する。
NavFn自体の4方向のポテンシャル更新と勾配追跡による後処理は再現しない。**NavFn全体とのバイト一致や経路一致を主張する比較ではない。**
保存した `navfn_planner.cpp` の254行目で、実ノードも `setCostmap(..., true, allow_unknown_)` を呼ぶことを確認した。
同ノードの `clearRobotCell`（245/520行目以降）は始点をFREE_SPACEへ上書きするが、この比較では共通の障害物から始点を免除せず、GeometryLayer出力をそのまま変換する。これもノード全体との違いである。

## 障害物・評価・統計

研究室版は生の障害物（漂着物・水・データなし）を通行不可にし、通常版には膨張を加えない。
参考版は0.35mの円と障害物セルの閉じた正方形の距離で1回だけ膨張する。0.5m格子の離散化の影響が残る。
A*とTA*-S exactは013の設定をそのまま使い、元からある0.5mの障害物膨張も維持する。全手法で同じ生の障害物を除外するが、膨張範囲は方式で異なる。
したがって「全手法の障害物マスクが同じ」とは言わない。参考版も含めて明示して比較する。

中立な指標を先に出す。`obstacle_cells` は共通の生の障害物に対する正確な交差セル数。
`lethal_cells` は013の照合用で、私たちの急斜面マスクも含むため中立な障害物接触指標と混同しない。
傾斜・経路長・登った高さ・横傾きは共通のevaluateで算出する。`max_pitch` は013の1m窓、`max_pitch_dir/p95_pitch_dir` は進行方向勾配の最大/95%値。
mean_costとJは私たちの目的関数なので私たちに有利と注記する。エネルギーは出力・集計しない。
013との照合は非エネルギーの全経路指標とシナリオ識別子（rtol=atol=1e-9、既存abstract_figureと同じ）で、時間は実行機依存なので再測定し一致判定しない。

検定単位は砂浜。両サイズで両手法が成功した砂浜だけ、100/200mを砂浜内で平均して、両側Wilcoxon＋Holmを使う。
失敗数と除外数は別記する。事前の1つのHolmファミリーは、TA*-Sを基準とする3対比×漂着物2条件×全報告指標（計画時間を含む）。既存paired_testと同じゼロ差の扱い。
図は既存abstract_figure.chooseの規則1（最初）・規則2（急斜面距離最大）の2か所だけ。選択はlabの結果を見る前に既存CSVから決める。

```bash
cd conference
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-031-mpl XDG_CACHE_HOME=/tmp/thesis-031-cache \
  /workspace/venvs/thesis-031/bin/python experiments/lab_baseline.py --workers 3
```

中断時は同じソース・同じ出力先で `--resume` を指定できる。コードと既存offline.csvのハッシュが異なれば拒否する。

データ出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB Ground。
https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb （CC BY 4.0 / ODbL）。
この比較と図は、上記を加工して作成した既存のshizuoka_beach_lasを使っている。
図の背景は共通DEMの傾斜（25度で色を飽和）、黒線は生の障害物境界、丸が始点・星が終点。経路の格子方向制限やTA*-Sの平滑化も傾き指標に影響するため、差をGeometryLayerの式だけの効果と解釈しない。
