# 大きなdJの図の点検

全該当ケース図を inspection_1.png〜inspection_5.png の一覧と個別図で点検した。以下は幾何形状に基づく観察・仮説で、意思決定の原因の証明ではない。

## badlands / 50m / seed 3

図: detour_badlands_50_3.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
      variant         dJ        dL  n_plans
coarse R5 c20 109.147423 96.262939       72
```

## badlands / 50m / seed 6

図: detour_badlands_50_6.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
      variant        dJ        dL  n_plans
coarse R5 c20 38.562073 65.790594       73
```

## badlands / 50m / seed 7

図: detour_badlands_50_7.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 34.080522 52.553346       58
```

## badlands / 50m / seed 8

図: detour_badlands_50_8.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 32.690736 30.300930       72
 coarse R5 c20 36.361811 35.363968       81
```

## badlands / 50m / seed 9

図: detour_badlands_50_9.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
            variant        dJ        dL  n_plans
      coarse R15 c5 31.183239 35.889836       37
      coarse R5 c10 52.023358 21.399880       51
      coarse R5 c20 61.641528 41.251565       58
online adaptive R15 34.032337 17.205437       23
```

## badlands / 100m / seed 0

図: detour_badlands_100_0.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 29.411574  6.146089       86
coarse R5 c20 90.641780 84.668955      152
```

## badlands / 100m / seed 1

図: detour_badlands_100_1.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
            variant         dJ        dL  n_plans
     coarse R10 c10  54.490105 50.772254      143
      coarse R15 c5  34.674742 33.067590      118
      coarse R5 c10  42.697940 47.224827      161
      coarse R5 c20 122.206540 92.552704      189
online adaptive R15  63.005927 32.123230       86
```

## badlands / 100m / seed 2

図: detour_badlands_100_2.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 32.536309 25.942371      141
coarse R5 c20 66.722284 51.327761      163
```

## badlands / 100m / seed 3

図: detour_badlands_100_3.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
       variant       dJ        dL  n_plans
coarse R10 c10 25.91692  7.053424      103
 coarse R5 c20 36.64411 20.770492      128
```

## badlands / 100m / seed 4

図: detour_badlands_100_4.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
            variant        dJ        dL  n_plans
     coarse R10 c10 35.348953 39.848386       86
      coarse R5 c10 32.935565 29.312999       93
online adaptive R15 39.725636 36.233438       59
```

## badlands / 100m / seed 5

図: detour_badlands_100_5.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 41.577499 55.073305      133
coarse R5 c20 27.553737 46.524026      125
```

## badlands / 100m / seed 6

図: detour_badlands_100_6.png

禁止領域の周囲を理想経路と異なる側に回り込む例。経路長差が小さくても真の地形コスト差が寄与し得る。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 46.321645 30.772106      102
coarse R5 c20 40.837083 27.299298      102
```

## dunes / 50m / seed 0

図: detour_dunes_50_0.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
      variant        dJ         dL  n_plans
coarse R5 c10 89.735793 101.783353      161
coarse R5 c20 65.956515  72.070777      153
```

## dunes / 50m / seed 1

図: detour_dunes_50_1.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
      variant         dJ         dL  n_plans
coarse R5 c10 217.175787 273.198636      155
```

## dunes / 50m / seed 2

図: detour_dunes_50_2.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
      variant         dJ         dL  n_plans
coarse R5 c10 219.432834 267.518626      156
coarse R5 c20 226.540035 278.522100      162
```

## dunes / 50m / seed 3

図: detour_dunes_50_3.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 82.176222 90.587641      110
coarse R5 c20 83.645162 94.408931      112
```

## dunes / 50m / seed 4

図: detour_dunes_50_4.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
      variant         dJ         dL  n_plans
coarse R5 c10 186.958610 252.841618      133
coarse R5 c20 186.539133 251.659103      132
```

## dunes / 50m / seed 5

図: detour_dunes_50_5.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant         dJ         dL  n_plans
coarse R10 c10 100.468561 105.451282       60
 coarse R5 c10 205.112157 253.506624      143
 coarse R5 c20 208.160574 256.376199      144
```

## dunes / 50m / seed 6

図: detour_dunes_50_6.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant         dJ         dL  n_plans
coarse R10 c10  74.090482  93.225074       60
 coarse R5 c10 301.447289 390.673012      161
 coarse R5 c20 353.814707 439.970600      172
```

## dunes / 50m / seed 7

図: detour_dunes_50_7.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
            variant        dJ         dL  n_plans
     coarse R10 c10 56.075576  57.314950       72
      coarse R15 c5 38.041204  27.519949       46
      coarse R5 c10 97.201323 111.528689      107
      coarse R5 c20 87.166742 101.802620      103
online adaptive R15 27.812410  22.450270       27
```

## dunes / 50m / seed 8

図: detour_dunes_50_8.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 40.127220 37.410327      103
 coarse R5 c10 75.090171 73.933406      149
 coarse R5 c20 88.610097 91.269191      163
```

## dunes / 50m / seed 9

図: detour_dunes_50_9.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
            variant         dJ         dL  n_plans
     coarse R10 c10  84.932975 105.289805       95
      coarse R15 c5  45.126453  55.717958       54
      coarse R5 c10 210.343235 253.719291      178
      coarse R5 c20 213.862438 257.581092      184
online adaptive R15  43.799338  56.631221       47
```

## dunes / 100m / seed 0

図: detour_dunes_100_0.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant         dJ         dL  n_plans
coarse R10 c10  52.331563  60.269503       92
 coarse R5 c10 224.034268 251.804021      213
 coarse R5 c20 223.495838 256.006710      260
```

## dunes / 100m / seed 1

図: detour_dunes_100_1.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
      variant         dJ         dL  n_plans
coarse R5 c10  98.939714 115.050320      244
coarse R5 c20 112.579181 129.583885      275
```

## dunes / 100m / seed 2

図: detour_dunes_100_2.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
            variant         dJ         dL  n_plans
     coarse R10 c10 103.767817 118.046688      228
      coarse R15 c5  62.906006  71.339681      119
      coarse R5 c10 110.659520 125.039830      266
online adaptive R15  62.496808  70.164067      123
```

## dunes / 100m / seed 3

図: detour_dunes_100_3.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 25.503364 25.763544      209
 coarse R5 c10 37.212538 35.310464      242
 coarse R5 c20 83.923127 82.306203      338
```

## dunes / 100m / seed 4

図: detour_dunes_100_4.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant         dJ         dL  n_plans
coarse R10 c10  79.513484  90.397587      179
 coarse R5 c10 102.048893 116.585555      215
 coarse R5 c20 149.669899 168.052913      298
```

## dunes / 100m / seed 5

図: detour_dunes_100_5.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
            variant         dJ         dL  n_plans
     coarse R10 c10 183.279489 188.412072      244
      coarse R15 c5 161.136230 167.008653      186
      coarse R5 c10 213.075799 212.300387      303
      coarse R5 c20 216.560577 216.846593      409
online adaptive R15 162.749998 168.077127      173
```

## dunes / 100m / seed 6

図: detour_dunes_100_6.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
            variant         dJ         dL  n_plans
     coarse R10 c10 102.998552 111.027280      223
      coarse R15 c5 123.122064 142.998627      169
      coarse R5 c10 119.836804 129.505770      262
      coarse R5 c20 226.783204 254.683980      408
online adaptive R15 135.363033 155.174256      168
```

## dunes / 100m / seed 7

図: detour_dunes_100_7.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant         dJ         dL  n_plans
coarse R10 c10  67.894835  89.801138      157
 coarse R5 c10 183.734834 232.293844      292
 coarse R5 c20 266.714654 326.742252      405
```

## dunes / 100m / seed 8

図: detour_dunes_100_8.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
            variant         dJ         dL  n_plans
     coarse R10 c10 167.861798 203.854694      263
      coarse R15 c5  89.209525  96.869819      144
      coarse R5 c10 182.199239 204.619304      285
      coarse R5 c20 189.184007 214.902849      306
online adaptive R15  72.873054  75.784481      114
```

## dunes / 100m / seed 9

図: detour_dunes_100_9.png

急斜面の帯に沿った長い上下移動と折り返し形状。局所観測で横断可能箇所を探す大回りと整合するが、観測履歴から原因を確定してはいない。

```text
       variant        dJ        dL  n_plans
coarse R10 c10 37.065085 33.960690      260
 coarse R5 c10 73.177553 69.586309      323
 coarse R5 c20 75.454859 74.408826      342
```

## mountain / 50m / seed 2

図: detour_mountain_50_2.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 38.898757 25.751437       67
coarse R5 c20 49.010814 35.046278       73
```

## mountain / 50m / seed 3

図: detour_mountain_50_3.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 43.557861 43.821127       68
```

## mountain / 50m / seed 6

図: detour_mountain_50_6.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
            variant        dJ        dL  n_plans
online adaptive R15 43.315374 17.398332       30
```

## mountain / 100m / seed 0

図: detour_mountain_100_0.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c20 28.071765 26.552358      129
```

## mountain / 100m / seed 2

図: detour_mountain_100_2.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c20 40.751365 35.120277      105
```

## mountain / 100m / seed 5

図: detour_mountain_100_5.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
            variant        dJ        dL  n_plans
     coarse R10 c10 55.036803 36.587927      137
online adaptive R15 44.081766 16.607550       65
```

## mountain / 100m / seed 6

図: detour_mountain_100_6.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c10 31.427689 15.624369      115
coarse R5 c20 30.362546 18.909692      120
```

## mountain / 100m / seed 7

図: detour_mountain_100_7.png

山腹・谷縁の禁止領域周辺で理想と異なる回り込み。形状が近い例もあり、距離差だけで全dJ差を説明しない。

```text
      variant        dJ        dL  n_plans
coarse R5 c20 46.421398 36.878716       93
```
