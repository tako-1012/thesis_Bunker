# 新チャット（Claude）とMac Copilot向け作業手順

目的: ClaudeやMac Copilotを使って論文草稿を効率的に作成するための具体的手順とプロンプトテンプレート。

## 準備（共通）
1. ワークスペース内の最新図表とJSONを確認:
   - `outputs/thesis_handover/` 内のファイルを参照
   - 元データ: `benchmark_results/terrain_methods_comparison.json`, `figures/` フォルダ
2. 再現コマンド（必要時）:

```bash
python3 scripts/create_terrain_scenarios.py
python3 scripts/run_terrain_experiments.py --scenarios hill_detour
python3 scripts/update_and_plot_terrain_costs.py
```

## Claude（新チャット）への指示例
Claudeは草稿の生成・文体調整・セクション構成に向いています。以下の順で投げます。

1) 序論の草稿作成（プロンプト）
- 入力: 研究タイトル、目的、背景1段落、貢献リスト（research_summary.md を貼る）
- 出力要求: 700–900語の草稿、冒頭3文は研究動機、最後に本文でカバーする項目を列挙

2) 関連研究の草稿作成
- 入力: 主要キーワード（A*、Field D*、地形コスト、ロバスト経路計画）と簡単な比較観点
- 出力: 800語、各関連研究の短い比較表をMarkdownで出力

3) 結果と考察の草稿作成
- 入力: `key_results.json` の数値、`figures_for_thesis.md` のキャプション案
- 出力: 図を参照する本文（図番号のプレースホルダ付き）、主要メッセージを3つ程度に要約

## Mac Copilot（コード補助・図整備）への指示
Copilotには技術的なファイル編集、スクリプト作成、図の最終化を任せます。

- タスク例:
  - Matplotlib を用いた高解像度図の再出力（EPS/PDF, フォント埋め込み）スクリプト作成
  - `scripts/` の README に再現コマンドを追加
  - `ros2` 側の `terrain_aware_astar.py` にパラメータ注釈を追加（ドキュメント文字列）

- 具体プロンプト（短）:
  - "Create a `save_figure_pdf.py` that reads `figures/*.png` and writes PDF/EPS with 300dpi and embedded fonts."

## 連携ワークフロー（推奨）
1. Claude に本文のドラフトを作成させる（序論→関連研究→手法）。
2. Copilot に図表の最終化・スクリプト整備を依頼して高解像度版を出力。
3. Claude に更新済み図を渡し，結果章の本文と図キャプションを生成させる。
4. 最後に人間（杉原氏）が全体をレビューして学術語調・査読者向け改定を行う。

## 注意点
- 数値や図のキャプションは `key_results.json` と `figures_for_thesis.md` を参照させて固定する。
- 再現可能性のため、スクリプト実行ログとseedを添付すること。