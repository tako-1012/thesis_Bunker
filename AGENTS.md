# コーディングエージェント（Codex など）への指示

このリポジトリは、クローラー型ロボット AgileX BUNKER のための「地形を考慮した経路計画」に関する、
修士学生の研究リポジトリです。信頼できる現役のコードは `conference/` にあります。
`conference/` の外にあるものは、使うことも変更することもしないでください。
- `ros2/` は研究室のリポジトリ（`hayashilab/bunker_ros2`、`hayashilab/bunker_unity`）から持ってきたもの
- `scripts/`、`analysis/`、`benchmark_results/`、`results/`、`tables/`、`figures/`、`thisis_write/` は卒論の保管用。
  卒論の数値は信頼できないことがわかっている（`conference/AUDIT_ja.md` を参照）

## 言語
- **PR の説明、最終報告、コミットメッセージは日本語で書くこと。**
- コードの中のコメントと変数名は、周りのコードに合わせて英語でよい。論文（`conference/paper/`）は英語。

## セットアップと確認
```bash
pip install numpy scipy matplotlib pandas
cd conference
python3 -m tests.test_planners        # 変更の前後で必ず通ること
python3 -m tests.test_online
python3 -m tests.test_dstar
python3 -m tests.test_risk_prior
python3 -m tests.test_collision
python3 -m tests.test_natural_terrain
python3 -m tests.test_beach_terrain
```
作業を終える前に、`conference/tests/` の下にあるすべてのテストを実行すること。

## ブランチ
- `realtime-map`：新しい研究作業の土台。PR は必ず `realtime-map` に向けて作る
  （`main` や `claude/laughing-tesla-igaehc` には向けない）。
- 作業を始める前に、`realtime-map` の最新の状態を取得すること。
- コミット `ac9d9e7` は ICAROB 2026 に出した時点の状態。履歴の書き換えは絶対にしない。

## 変更禁止のファイル（指示書で明示的に許可された場合を除く）
- `conference/paper/`（論文、自動生成の表と図）
- `conference/results/*.csv`、`conference/results/*.json`、`conference/results/explore/`、
  `conference/results/online/`、`conference/results/online_prior/`、`conference/results/online_dstar/`、`conference/results/risk_prior/`、`conference/results/exact_los/`、
  `conference/results/natural_terrain/`、`conference/results/beach_terrain/`
- `conference/tapp/planners.py`、`metrics.py`、`scenario.py`、`terrain.py`、
  `traversability.py`、`config.py`、`aniso.py`、`prior.py`、`dstar_lite.py`、`risk_prior.py`、`collision.py`、`online.py`、
  `natural_terrain.py`、`natural_scenario.py`、`beach_terrain.py`、`beach_scenario.py`、`exact_planners.py`
- `conference/experiments/run_all.py`、`analyze*.py`、`run_weight_opt.py`、`run_roll.py`、
  `run_infeasible.py`、`online_replanning.py`、`online_prior.py`、`online_dstar.py`、`risk_prior.py`、`exact_los.py`、
  `natural_terrain.py`、`beach_terrain.py`

既存の結果は、1ビットも変わらずに再現できる状態を保つこと。新しい機能は、新しいファイルに追加するか、
既定値で今までと同じ動きをする新しいキーワード引数の後ろに追加すること。

## 研究の信頼性に関する決まり（厳守）
- 実験結果を手で書いたり、式で作ったり、「埋めたり」しないこと。すべての数値はプランナーを実行して得ること。
  計算できなかったものがあれば、PR にそう書くこと。
- テスト用のシード（`range(10)`）でパラメータを調整しないこと。検証用のシードは `range(100, 105)`。
- 乱数はすべてシードを固定し、Python の `hash()` に依存させないこと。
- テストを通すために、テストを弱めたり消したりしないこと。

## 書き方
- Python 3、numpy と scipy だけを使う（重いライブラリを新しく増やさない）。周りのコードの書き方に合わせる：
  ファイルの先頭に方法を説明する短い docstring を書き、コメントは必要なところだけにする。
- 新しい実験の結果は、新しいフォルダ `conference/results/<タスク名>/` に置く
  （CSV と、表示した集計結果を `*_log.txt` として保存）。ファイルは 5 MB 未満にする。

## 報告（PR の説明、日本語で）
1. 実装したもの（ファイル、関数）
2. 実行したコマンドと、テストの出力の全文
3. 実験スクリプトが表示した集計表（そのまま貼る）
4. できなかったこと、自信がないこと

指示書は `conference/tasks/` にあります。指示書に正確に従うこと。
あいまいな点があれば、より単純な方を選び、そう選んだことを PR に書くこと。
