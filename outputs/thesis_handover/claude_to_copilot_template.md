# Claude → Copilot 受け渡しテンプレート

このテンプレートは、Claude（草稿生成）からMac Copilot（実装・図整備）へ作業を受け渡すときに使う。

## 構造
- Context（概要）
- 目的（何を実行してほしいか）
- 入力ファイル一覧（パス）
- 期待出力（ファイル名・フォーマット）
- 追加注意点（優先度・厳守事項）

## 例（テンプレート）

Context:
- "We have generated draft of Results and Discussion for the hill_detour scenario. The draft references Figures X and Y and uses numbers from `outputs/thesis_handover/key_results.json`."

目的:
- "Produce high-resolution PDF/EPS versions of the referenced figures, and create a short README `scripts/README_experiments.md` with exact commands to reproduce the figures."

入力ファイル:
- `figures/terrain_comparison_hill_detour.png`
- `figures/terrain_cost_comparison_hill_detour.png`
- `benchmark_results/terrain_methods_comparison.json`

期待出力:
- `figures/terrain_comparison_hill_detour.pdf`
- `figures/terrain_cost_comparison_hill_detour.pdf`
- `scripts/README_experiments.md` (Markdown)

追加注意点:
- Use 300 dpi, embed fonts, ensure legends are legible at column width.
- Do not change figure content semantics; only re-render and export.

---

このテンプレートをコピーして、Claudeの出力（文章）を受け取り、Copilotへ確実に指示を渡してください。