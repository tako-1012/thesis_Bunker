# 指示書029：障害物の点を地面の高さから除く

`PointCloudMapFine` と `PointCloudMapMulti` に、選択時だけ働く
`ground_estimate='non_obstacle'` を追加した。既定は従来の `all_returns`。
Gazeboはこの作業では実行しない。Pythonの確認と出力全文は `REPORT_ja.md` を参照。

直近64点の履歴自体は、障害物の点も含めて保持する。その履歴から、
「点の高さ − 古い地図の双線形補間の高さ」が既存の障害物判定値0.3m以上の点を除き、
残った点の中央値を地面の高さにする。点が残らなければ、そのセルの古い地図の高さに戻す。
観測済みの扱い、細かい格子の障害物の証拠、センサーごとの寄与、膨張は変更しない。

限界：古い地図から0.3m以上高くなった**本当の地形の変化**も地面の高さには使われない。
新しくできた砂の盛り上がりなども、既存の点数条件を満たせば障害物として扱われる。
上面しか見えていないセルの地面を観測・復元できるわけではなく、古い地図を使う仮定である。
古い地図の誤差・位置合わせの誤差・0.3m未満の障害物の点による高さの誤りは残り得る。

## 引数と記録

- `lidar_checks.py --map fine --ground-estimate non_obstacle`
- `lidar_planner.py --ground-estimate non_obstacle --ros-args -p map_method:=fine ...`
- ROSパラメータでも `-p ground_estimate:=non_obstacle` を指定できる。ROSの指定はノードの既定値より優先する。
- `non_obstacle` はfine地図専用。coarseとの組合せはエラーにする。
- 新方式のmanifestは `ground_estimate` と高さの定義を記録する。
  既定のmanifestはバイト列を保つため項目を追加しない。項目なしは `all_returns` を意味する。
- 新方式の実走では生の記録を保存する。従来の4方式の集計へ新方式を同じ名前で混ぜない。

研究PCで後日実行する例（今回は未実行。保存先は毎回新しくする）：

```bash
cd conference
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/ground_estimate/physical_3_non_obstacle_r1 \
  --patch-count 3 --map fine --ground-estimate non_obstacle
```
