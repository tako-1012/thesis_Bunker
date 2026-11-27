# 081 段階 A　研究室の ODM 点群の間引き

研究 PC `hayashi` で、`42b0eb167c09b36a5e66e337c7716c45131a8d50` を起点に変換した。
公開先は Mac 経由の `origin/claude/081-drone-map`。
073 が使用していた `~/thesis_Bunker_rtf` と同じ Git リポジトリに、
081 専用の作業ツリー `~/thesis_Bunker_rtf_081` を作った。

## 変換結果

| 項目 | 数値 |
| --- | ---: |
| 元の点数 | 43,539,562 |
| 5 cm 点群 | 649,172 ボクセル、13,319,782 バイト、NPZ 5 分割 |
| 10 cm 標高地図 | X 385 × Y 426 マス、645,692 バイト |
| 点のないマス | 18,190 / 164,010（11.0908%） |
| 出力合計（README と JSON を含む） | 13,972,309 バイト |

水平座標系は **WGS 84 / UTM zone 52N（EPSG:32652）**。
元の XYZ の範囲は 655194.349〜655232.826、3725159.720〜3725202.245、
77.771〜78.161 m。局所 XYZ はそれぞれ 0〜38.477、0〜42.525、0〜0.390 m。
ヘッダーの境界値は、デコードした点の境界値と 0.5 mm 未満の差があった。
実際に格納された点を 1 mm 精度の整数座標で照合し、成分ごとの最小を局所原点にした。
この原点を加えると元の座標系へ戻せる。鉛直基準は LAZ の値を使用した。
[元ファイルの SHA-256 と生成物の使い方](../../data/drone_odm/2024-04-24/README_ja.md)

10 cm 地図では元点すべての高さを集計した。空マスの分母は外接長方形全体。
地面以外の点も標高の集計に含み、鉛直測地基準の外部照合は未実施。
間引いた点群の座標・色は float32、元点数は uint32。
リポジトリのファイルサイズに収まるよう、色付き点群を連続した 5 個の NPZ に分割した。

## 再現・検証

研究 PC の `conference/.venv-localization` は Python 3.12.3。
`requirements_localization.txt` の導入後に加わったのは
`laspy==2.6.1` と `lazrs==0.7.0` の 2 行。`pip check` は合格。
変換は tmux 上で `nice -n 19`、`ionice -c 3`、単一スレッドの LAZ 展開と
数値ライブラリのスレッド上限 1 を設定し、約 12 秒で終了した。073 の継続を確認した。
[依存の差分](pip_freeze_diff.txt) · [変換ログ](convert_log.txt) · [実行時間とメモリ](convert_resources_log.txt)

```bash
cd ~/thesis_Bunker_rtf_081/conference
python3.12 -m venv .venv-localization
.venv-localization/bin/python -m pip install -r requirements_localization.txt
.venv-localization/bin/python -m pip install -r requirements_drone_map.txt
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
nice -n 19 ionice -c 3 .venv-localization/bin/python -u -m experiments.drone_map_downsample \
  --source "$HOME/thesis_data/drone_odm/2024-04-24" \
  --out data/drone_odm/2024-04-24
PYTHONPATH=. nice -n 19 ionice -c 3 .venv-localization/bin/python -u results/drone_map_081/verify081.py
```

- 変換後に元ファイル 6 点すべての SHA-256 とサイズを再照合した。
- 2 通りの NPZ の点数の和が元点数と一致した。元 LAZ から 164,010 マスすべての
  点数と境界値を再計算し、代表 11 マスの最小・最大・中央値も一致した。
  合成 LAZ で 5 cm 境界、チャンクをまたぐ座標・色の平均、偶数個の中央値、空マスを検査した。
  [独立検証ログ](verify_log.txt)
- 既存テストは **63/63 モジュール合格**。研究 PC の専用 venv と Mac の一時環境で確認した。
  研究 PC の `tests.test_planners` は前後で出力が一致し、
  `tests.test_offline_localization` と `tests.test_recording_bridge` は各 7 件合格。
  Mac での `tests.test_localizability_scan` は後から任意依存もそろえて検査した。
  [テスト一覧](test_summary.tsv) · [Mac 側の全出力](mac_tests_log.txt)
- Mac の初回で失敗した既存テストは Bash 5 と実体の一時ディレクトリのパスで再確認した。
  `tests.test_online` は Mac で経路長が既存の基準値と異なり、研究 PC で合格した。
  `tests.test_local_speed` は Linux の `/proc/cpuinfo` から出力する CPU 名だけを Mac の実機名で補い、
  テストの判定条件をそのまま実行した。
