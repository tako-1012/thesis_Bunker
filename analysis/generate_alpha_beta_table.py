#!/usr/bin/env python3
"""
LaTeX表生成: α, β, γパラメータ調整結果

実行方法:
    python analysis/generate_alpha_beta_table.py
"""
import json
from pathlib import Path

def generate_latex_table():
    """α, β, γパラメータ調整結果のLaTeX表を生成"""
    
    # 実験結果を読み込み
    project_root = Path(__file__).parent.parent
    results_file = project_root / 'results' / 'alpha_beta_tuning.json'
    
    if not results_file.exists():
        print(f"Error: {results_file} が見つかりません")
        print("先に experiments/parameter_tuning_alpha_beta.py を実行してください")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data['results']
    
    # LaTeX表を生成
    latex_lines = []
    latex_lines.append(r"\begin{table}[htbp]")
    latex_lines.append(r"\centering")
    latex_lines.append(r"\caption{地形複雑度重みパラメータの調整結果（hill\_detourシナリオ）}")
    latex_lines.append(r"\label{tab:terrain_weight_tuning}")
    latex_lines.append(r"\begin{tabular}{ccc|ccc}")
    latex_lines.append(r"\hline")
    latex_lines.append(r"$\alpha$ & $\beta$ & $\gamma$ & 経路長[m] & 点平均地形コスト & 総コスト \\")
    latex_lines.append(r"\hline")
    
    # TA*の結果でソート（総コストが小さい順）
    sorted_results = sorted(results, key=lambda x: x['ta_star']['total_cost'])
    
    # 要件に従い、特定の3パターンを表示
    # 1. α=0.3, β=0.3, γ=0.4
    # 2. α=0.4, β=0.4, γ=0.2 (最良)
    # 3. α=0.5, β=0.5, γ=0.0
    target_configs = [
        (0.3, 0.3, 0.4),
        (0.4, 0.4, 0.2),
        (0.5, 0.5, 0.0)
    ]
    
    selected_results = []
    for alpha, beta, gamma in target_configs:
        for result in results:
            if (abs(result['alpha'] - alpha) < 0.01 and 
                abs(result['beta'] - beta) < 0.01 and 
                abs(result['gamma'] - gamma) < 0.01):
                selected_results.append(result)
                break
    
    # 選択された結果を表示
    for result in selected_results:
        alpha = result['alpha']
        beta = result['beta']
        gamma = result['gamma']
        ta_data = result['ta_star']
        
        path_length = ta_data['path_length']
        terrain_cost = ta_data['terrain_cost_avg']
        total_cost = ta_data['total_cost']
        
        latex_lines.append(
            f"{alpha:.1f} & {beta:.1f} & {gamma:.1f} & "
            f"{path_length:.1f} & {terrain_cost:.2f} & "
            f"{total_cost:.1f} \\\\"
        )
    
    latex_lines.append(r"\hline")
    latex_lines.append(r"\end{tabular}")
    latex_lines.append(r"\end{table}")
    
    # LaTeX表を出力
    latex_content = "\n".join(latex_lines)
    
    # ファイルに保存
    output_file = project_root / 'tables' / 'table_3_1_alpha_beta_tuning.tex'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(latex_content)
    
    print("="*70)
    print("LaTeX表を生成しました")
    print("="*70)
    print(f"\n出力ファイル: {output_file}\n")
    print("生成されたLaTeX表:\n")
    print(latex_content)
    print("\n" + "="*70)
    
    # 最良の設定を表示
    best_config = data['best_configuration']
    print("\n最良設定:")
    print(f"  α = {best_config['alpha']:.1f}")
    print(f"  β = {best_config['beta']:.1f}")
    print(f"  γ = {best_config['gamma']:.1f}")
    
    best_result = sorted_results[0]
    print(f"\n性能指標:")
    print(f"  経路長: {best_result['ta_star']['path_length']:.1f} m")
    print(f"  点平均地形コスト: {best_result['ta_star']['terrain_cost_avg']:.2f}")
    print(f"  総コスト: {best_result['ta_star']['total_cost']:.1f}")


if __name__ == '__main__':
    generate_latex_table()
