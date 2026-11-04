# 影を含む仮想観測

`conference/` から `python3 experiments/online_visibility.py --workers 4` を実行する。
点群のtest 48砂浜、200m、seed 0、5点と巡回順・oracle分母は指示書014と同じ。
元の実装・既存結果は変更しない。陰なしの対照は014の件数とdJを照合する。

`visible_cells` は半径内の各セルに向けた線を `segment_cells` の全通過セルで調べる。
途中セルの中心を視線へ射影し、その位置の視線高がセルの標高以下なら隠れる。
源点と目標セルは途中の遮蔽物から除く。観測位置は014と同じくセルへ丸める。
線上の比較位置はセンサー高さによらないので、高くすると可視セルが減らない。
これは0.5m DEM上の離散モデルであり、実際のLiDARの走査・反射・雑音のモデルではない。

センサー高さ0.5・0.8・1.2mは全て仮定として比較し、test結果で高さを選ばない。
岩の隆起は `build_real` の標高に含まれるので二重に加えない。
高さが入っていない `terrain['driftwood']` には仮定の0.3mを加える。
`virtual_sense_los` の追加キーワード `rock_mask` は、この高さ未設定の**膨張前**マスクを受け付ける。
`tm.rock` は水・データなし・ロボット半径の余白も含むため、遮蔽物の高さとして使わない。

```python
mask, cost, lethal = virtual_sense_los(
    sc['tmap'], pos_cell, 10, sensor_height_m=0.8,
    rock_mask=sc['terrain']['driftwood'], obstacle_height_m=0.3,
)
```

見えないセルを観測済みにはしない。過去に見えたセルの知識は保持し、未知セルには元のprior方針を使う。
観測・移動の周期、再計画の発火・結合、6倍の打切りは014のまま。接触を見て新たに停止させる変更は加えない。
記録の `contact_events` は動いた区間を後から監査するだけで、経路や状態を変更しない。

- `missions.csv`, `summary.csv`: 完走、打切り、失敗走行を含む接触、完走時dJ、計画回数・時間。
- `observations/*.npz`: 毎観測の可視割合。集計は失敗走行を含め全観測を連結した中央値で、走行別中央値の中央値ではない。
- `contact_details/*.json`, `contact_reasons.csv`: 接触前の知識、最後の観測での可視性・半径内外を記録する。
- `python3 experiments/audit_visibility.py`: 同じセルの初回侵入だけを `first_contacts.csv` に抽出する。侵入後に既知となったセルから出る際の接触を、既知の危険セルへ新たに入った事例と混同しない。
- `traces/*.npz`, `contact_*.png`: 実行した軌跡と、接触があった場合の例。
- `paired_runs.csv`, `paired_summary.csv`: 両条件で完走した走行のdJ差。完走の喪失・新規完走を別に数える。
- `protocol.json`, `runtime.json`: 仮定、環境、コードのハッシュと総実行時間。

計画時間は探索と平滑化だけを測り、視線計算・地図組立を含まない。4ワーカー実行の時間から実機の応答保証はしない。
