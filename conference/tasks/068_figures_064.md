# 指示書 068：論文用の図と表に、064（180 回）と前もって決めた検定の結果を足す

> **状態：完了（出力は `thesis/out_lidar/`、レビューは `results/lidar_figures/REVIEW_068_ja.md`）**。実装は **クラウドの Codex**。Gazebo・研究 PC は使わない（コミットされた結果を読むだけ）。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/thesis/make_lidar_figures.py`、`conference/results/lidar_figures/REPORT_ja.md`・`REVIEW_ja.md`・`REPORT_059_ja.md`・`REVIEW_059_ja.md`（049・059）、
> `conference/tasks/064_eval_2x2.md`、`conference/results/eval_064/REPORT_stage2_ja.md`・`REVIEW_stage2_ja.md`、`conference/results/common_eval/REPORT_ja.md` を読むこと。
> ブランチは `codex/068-figures-064`（その時点の `realtime-map` の最新から）。出力は `conference/thesis/out_lidar/`、報告は `conference/results/lidar_figures/REPORT_068_ja.md`。

## 背景（別の環境の会話は共有されないので、ここに書く）
- `make_lidar_figures.py` は、研究 PC の走行の結果（030〜057）から、論文用の表（T4〜T6）・図（F8〜F10）・本文用の数値（`numbers_lidar.tex`）を作る。数字を手で写さず、結果のファイルから作る決まり。
- 064 は修論の中心の評価（GPU・1.0 倍、6 条件 × 5 か所 × 6 回 ＝ 180 回）。結果は `conference/results/eval_064/common_eval_all/runs.csv`。
  条件：S（標準）・P（古い地図の傾き）・D（障害物の余白を距離で）・PD・G（地面の点だけで高さ）・GD。
- 前もって決めた検定：1 条件 30 回で、Fisher の両側正確検定。比べる組み合わせは PD と S、GD と S、PD と P、GD と G の 4 つ。
  指標は「完走」「漂着物のマスを通った走行」「箱から 0.5m 未満に近づいた走行」で、指標ごとに 4 比較を Holm で補正する。
  Claude が自分で計算し直した値：箱から 0.5m 未満は PD・GD とも 0/30、S・P 7/30、G 5/30。補正後 p は 0.042・0.042・0.042・0.052。

## やること
- `STUDIES` に 064（`eval_064/common_eval_all/runs.csv`、条件 S・P・D・PD・G・GD）を足す。段階 1 だけの `common_eval/runs.csv` は使わない。今までの実験（0.3 倍・CPU 描画）とは別の条件と分かる名前にする（例：「064 S（GPU・1 倍）」）。
- **T7（新しい表）**：前もって決めた検定の表。比べ方 × 指標ごとに、両方の回数・未補正の p・Holm 補正後の p。**`runs.csv` からスクリプトの中で計算する**（報告の数字を写さない）。
- **F11（新しい図）**：064 の 6 条件の、箱から 0.5m 未満の走行・漂着物のマスの走行・完走の回数（30 回中）を並べた図。距離の余白の有無が分かる並べ方にする（地形 3 通り × 余白 2 通り）。
- T4〜T6 に 064 の行を足す（今までの行は変えない）。`numbers_lidar.tex` に 064 の主な数値と、検定の補正後 p のマクロを足す。

## 守ること・やらないこと
- 既存の結果・`thesis/out/`・`conference/paper/` には書き込まない。数値を手で写さない。報告にない解釈の文（「〜が効いた」など）を図や表に入れない。
- 今までの 030〜057 の行・数値は変えない。検定は前もって決めた 4 比較 × 3 指標だけ（ほかの組み合わせを足さない）。

## テスト（`conference/tests/test_lidar_figures.py` に足す）
1. 064 の行が出て、`numbers_lidar.tex` の値が `runs.csv` から計算した値と一致する。
2. T7 の p 値が、scipy の `fisher_exact` と Holm の補正で計算した値と一致する（例：箱から 0.5m 未満の PD と S で、補正後 0.042170）。
3. 030〜057 の表の行・値が、直す前と同じ。
4. 既存のテストがすべて通る。

## Mac の Claude に持ち帰る報告（`REPORT_068_ja.md` にも書く）
1. コミット ID、変えた・足したファイル、実行したコマンドとテストの出力全文。
2. 作った図と表の一覧と、PNG の場所。
3. できなかったこと、自信がないこと。
