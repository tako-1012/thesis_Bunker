# 指示書 013：点群から作り直した本物の砂浜で、指示書009の実験をやり直す

> **状態：完了**（Codex が実装・実験。報告は `conference/results/real_beach_las/REPORT_ja.md`、比較の全文は `compare_log.txt`）。
> Claude が `tests/test_mapfiles_sim.py` の地図の数と大きさの確認を、指示書011の 23 枚がそのまま残っていることの確認に直した。
> TA\*-S の利点（地形コスト・登る高さ・横傾き・エネルギー）は変わらず成り立った。走りながらの再計画の理想との差は、
> 段々をなくすと大きく小さくなった（例：200m・センサー 5m・粗い地図 10m（`coarse R5 c10`）で中央値 18.0% → 6.8%）。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
指示書009の本物の砂浜（`conference/data/shizuoka_beach/`）は、静岡県の ALB の 0.5m グリッドから作りました。
ところが、そのグリッドの**標高は 0.1m 単位に丸めてあり**、ゆるやかな砂浜が 0.1m の段々になっていました
（段の上は傾き 0、段の境は約 11°）。Claude が、同じ測量の**地面の点群**から、同じ 60 か所・同じ位置・同じ向きで
作り直しました（`conference/data/shizuoka_beach_las/`）。まず、そのフォルダの `README_ja.md` を読むこと。
12 か所で比べると、陸の凸凹の中央値は 1.95cm → 0.89cm、地形コストの中央値は 0.195 → 0.121 に下がり、
通れない陸の割合（1.8%）はほとんど変わりませんでした。

この指示書では、**指示書009の実験を、新しいデータでそのままやり直し、前の結果と比べます。**
- パラメータ（`w` など）は今までの値のまま使い、調整しない。
- 新しいデータの結果を見て、実験の方法を変えない。
- **両方のデータ（`shizuoka_beach/`、`shizuoka_beach_las/`）は変更しないこと。** ネットワークからのダウンロードも不要。

## この指示書で変更してよい既存ファイル
- `conference/tapp/real_beach.py`：`list_patches`・`load_patch`・`build_real` に、キーワード引数
  `dataset="shizuoka_beach"` を**一番後ろに**加える（`"shizuoka_beach_las"` を選べるようにする）。
  **既定値のときは、今までと 1 ビットも同じ結果になること**（`tests.test_real_beach` がそのまま通ること）。
  乱数のシードの作り方（`SeedSequence([seed, 4000, side_m, パッチの番号])`）は変えない。パッチの番号は、どちらのデータでも同じ順番になっている。
- `conference/experiments/real_beach.py`：コマンドの引数 `--dataset`（既定 `shizuoka_beach`）を加え、`shizuoka_beach_las` のときは
  結果を `conference/results/real_beach_las/` に書く。**既定のときの動きと出力先は変えないこと**（`results/real_beach/` は変更しない）。
- `conference/data_prep/export_maps.py` と `conference/maps/`：本物の砂浜の地図ファイルに、新しいデータの `validation` 12 か所
  （`real_las_<名前>_200m_0.npz`）を**加える**。今ある地図ファイルは変えない。`maps/README_ja.md` に説明と出典を足す。
- `conference/gazebo_worlds/`：`real_las_08OB87_-0206` の world を `data_prep/export_gazebo.py` で**加える**（今ある world は変えない）。
それ以外の既存ファイルは変更しない。

## 実験：`python3 experiments/real_beach.py --dataset shizuoka_beach_las`
指示書009と同じ (A)〜(D) を、同じシナリオ（`test` の 48 か所 × 100m・200m × シード 0、漂着物なし・あり）・同じプランナー・同じ集計で行う。
結果は `conference/results/real_beach_las/` に置く。

### 比べる：新しいスクリプト `conference/experiments/compare_real_beach_las.py`
`results/real_beach/` と `results/real_beach_las/` の CSV を読み、**同じシナリオどうしを対にして**比べる。結果は `results/real_beach_las/` に置く。
1. (A) の地形の値（傾き・前浜の勾配・陸の幅・凸凹・スペクトルの傾き・通れない割合）：前と新の中央値と、対にした差の中央値。
   人工の砂浜が本物の 10〜90% の範囲から外れる項目の一覧が、前と新でどう変わったか。
2. (B) TA\*-S exact と A\* の差（急斜面を通った経路の割合、地形コスト、登った高さ、エネルギー、経路長、横傾きの 95% 値）：
   前と新のそれぞれで、指示書009と同じ検定（対応のある Wilcoxon ＋ Holm）。**結論（有意かどうか、向き）が変わった指標**の一覧。
3. (C) 走りながらの再計画の理想との差 dJ：条件ごとに、前と新の中央値・悪い側 10%・最大。同じ走行どうしの dJ の差の中央値。
   通行禁止のマスに触れた走行の数。
4. (D) 巡回の `euclid` と `terrain dir` の差：地点数ごとに、前と新の中央値・悪い側 10%。
表示した集計表を `compare_log.txt` に保存する。

## テスト：新しいファイル `conference/tests/test_real_beach_las.py`（`python3 -m tests.test_real_beach_las`）
1. **データ**：60 か所すべてが読め、大きさが 400×400、名前・`split`・`origin_xy`・`tangent`・`normal` が `shizuoka_beach/` と同じであること。
2. **段々がないこと**：各パッチで、データのあるマスのうち 0.1m の倍数のマスが 2% 未満であること。前のデータでは 20% を超えること（違いの確認）。
3. **向き**：指示書009のテストと同じ（y = −50m 側で平均の標高が 0 未満、y = 0〜50m のどこかで 0 を超える）。
4. **既定値が変わらないこと**：`build_real(name, 100, 0)` と `build_real(name, 100, 0, dataset="shizuoka_beach")` が、`test` の最初の 3 か所で
   `tmap.cost`・`tmap.lethal`・`start`・`goal` まで完全に一致すること。
5. **シナリオ**：`dataset="shizuoka_beach_las"` の `build_real` が、`test` の最初の 5 か所・100m と 200m で解ける地図を返し、海・データなしのマスが
   `lethal` に含まれること。同じ引数で 2 回作ると同じになること。
6. **安全性**：指示書009のテスト 5 と同じこと（TA\*-S exact の経路と `coarse R5 c10` の再計画の軌跡で `path_lethal_cells` が 0）を、新しいデータで。
7. **地図ファイル**：`maps/real_las_*.npz` が 12 枚あり、`load_map_file` で読め、`build_real(..., dataset="shizuoka_beach_las")` と
   `tmap.cost`・`tmap.lethal` が一致すること。
8. 既存のテストがすべて通ること（`tests.test_real_beach`・`tests.test_mission`・`tests.test_mapfiles_sim` を含む）。

## 完了の条件
- すべてのテストが通る。
- `python3 experiments/real_beach.py --dataset shizuoka_beach_las` と `compare_real_beach_las.py` が最後まで動き、CSV・ログ・図ができている。
- `results/real_beach/`、`data/` の両方のフォルダ、今ある地図ファイルと world は 1 つも変更しない。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。
  PR を作れない場合は、ブランチを push して、報告をリポジトリの中（`conference/results/real_beach_las/REPORT_ja.md`）に置く。

## 結果の報告で必ず書くこと
- `compare_log.txt` の表（そのまま）。
- **指示書009の結論のうち、変わったものと変わらなかったもの**（TA\*-S の利点、再計画の理想との差、巡回の順番の効果）。
- 各実験にかかった時間。

## 対象外
地形コストの式やパラメータの変更、人工の砂浜の作り方の変更、論文の変更、Gazebo での走行（Claude が行う）。
