# dJ>25%の図の点検

全5ケース図を目視確認。図からの解釈であり、各意思決定の原因の証明ではない。

## beach_scarp / 50m / seed 2

図: detour_beach_scarp_50_2.png

浜崖の海側・陸側で理想と異なる経路を取る。局所的な進路変更・回り込みが見える。地形コスト差もdJに含むため、全増加を距離だけには帰属しない。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 29.372925 39.933463       43
 coarse R15 c5 29.058034 39.318365       34
 coarse R5 c10 29.833849 39.797541       52
```

## beach_scarp / 50m / seed 4

図: detour_beach_scarp_50_4.png

浜崖の海側・陸側で理想と異なる経路を取る。局所的な進路変更・回り込みが見える。地形コスト差もdJに含むため、全増加を距離だけには帰属しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c20 36.856014 18.443976       41
```

## beach_scarp / 50m / seed 6

図: detour_beach_scarp_50_6.png

浜崖の海側・陸側で理想と異なる経路を取る。局所的な進路変更・回り込みが見える。地形コスト差もdJに含むため、全増加を距離だけには帰属しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 45.544353 10.343723       55
coarse R5 c20 48.078251 10.092280       44
```

## beach_scarp / 100m / seed 9

図: detour_beach_scarp_100_9.png

浜崖の海側・陸側で理想と異なる経路を取る。局所的な進路変更・回り込みが見える。地形コスト差もdJに含むため、全増加を距離だけには帰属しない。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 28.363019 17.383050       91
 coarse R5 c10 45.803802 27.317890       99
 coarse R5 c20 47.306513 29.933135      102
```

## hills / 50m / seed 3

図: detour_hills_50_3.png

理想より谷側を回り、局所的な禁止領域の周辺を通る。迂回と地形コストの差が寄与する解釈と整合するが、観測履歴に基づく因果検証ではない。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 44.204486 22.219435       49
```
