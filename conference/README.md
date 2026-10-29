# 地形考慮型 A* — 再現可能な実験一式

卒論の研究を、国際学会（ICAROB 2026）に向けて一から作り直し、評価し直したものです。
卒論の数値を使わない理由は `AUDIT_ja.md` にまとめてあります。

## フォルダ構成
```
tapp/            ライブラリ（地形の生成、走行可能性のコスト、プランナー、評価指標、再計画）
tests/           正しさのテスト（A*/TA* が最適な経路を返すか、再計画が安全か、など）
experiments/     実験スクリプト（run_*.py）と、表・図・数値を作る分析スクリプト（analyze*.py）
results/         実験の生データ（CSV）と集計結果
paper/           ICAROB の論文（IEEE 形式、英語）。generated/ と figures/ は分析スクリプトが自動で作る
presentation/    発表スライドの構成案
tasks/           Codex などに渡す指示書
AUDIT_ja.md      卒論の問題点と、作り直した内容の記録
```

## 主なファイル
| ファイル | 中身 |
|---|---|
| `tapp/terrain.py` | 4種類の地形（丘陵・尾根・クレーター・岩場）と、通れない壁の地形を生成 |
| `tapp/traversability.py` | 傾斜・凸凹・岩から、地形コストと通行禁止の場所を計算（ロボットの限界値で正規化） |
| `tapp/planners.py` | A\*、TA\*（地形コスト付き A\*）、Lazy Theta\*、地形を考慮した平滑化（TA\*-S） |
| `tapp/aniso.py` | 横傾き（ロール）を考慮した TA\*（TA\*-R、TA\*-S-R） |
| `tapp/metrics.py` | 経路の評価（急斜面の走行距離、傾斜、ロール、凸凹、エネルギー推定など） |
| `tapp/online.py` | 走りながらの再計画（センサーの届く範囲だけが見える状況） |
| `tapp/prior.py` | 粗い全体地図（5m・10m 間隔）を、見えない場所の推定に使う |
| `tapp/terrain_baselines.py` | 比較用の地形考慮型プランナー（探索的、論文には未掲載） |

## 再現手順（`conference/` で実行）
```bash
pip install numpy scipy matplotlib pandas
python3 -m tests.test_planners
python3 -m tests.test_online
python3 experiments/run_weight_opt.py   # 重み (w, α) の全組み合わせを試す（約6分）
python3 experiments/analyze_weights.py  # 検証用データだけで重みを選ぶ → results/selected_weights.json
python3 experiments/run_all.py          # 選んだ重みで本実験（約3分）
python3 experiments/run_infeasible.py   # 通れないマップの実験
python3 experiments/run_roll.py         # 横傾きを考慮した拡張（約1分）
python3 experiments/analyze.py          # 論文の表・図・数値を作る
python3 experiments/analyze_roll.py
python3 experiments/demo_figures.py     # 経路の説明用の図（paper/figures/demo/）
python3 experiments/demo_roll.py craters 0
cd paper && latexmk -pdf main.tex
```

探索的な実験（論文には未掲載）：
```bash
python3 experiments/explore_terrain_baselines.py  # 他の地形考慮型手法との比較 → results/explore/
python3 experiments/online_replanning.py          # 走りながらの再計画 → results/online/
python3 experiments/online_prior.py               # 粗い全体地図を使った再計画 → results/online_prior/
```

## 大事な決まり
- 論文の数値は、すべて `analyze.py` が `results/` から作る `paper/generated/numbers.tex` から来ています。**`main.tex` の数値を手で書き換えないでください。**
- 重みは検証用のシード（`range(100, 105)`）だけで選び、テスト用のシード（`range(10)`）では調整しません。
