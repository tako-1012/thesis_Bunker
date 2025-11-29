"""
論文用データ抽出

論文執筆に必要なデータを抽出・整理
"""
from pathlib import Path
import json

def extract_paper_data():
    """論文用データを抽出"""
    print("="*70)
    print("📝 論文用データ抽出")
    print("="*70)
    
    base_dir = Path(__file__).parent
    results_dir = base_dir.parent / 'results'
    
    paper_data = {
        'abstract_numbers': {},
        'results_summary': {},
        'key_findings': []
    }
    
    # Phase 2結果から数値を抽出
    phase2_file = results_dir / 'efficient_terrain_results.json'
    if phase2_file.exists():
        with open(phase2_file) as f:
            data = json.load(f)
            
            if 'statistics' in data:
                stats = data['statistics']
                paper_data['abstract_numbers'] = {
                    'total_experiments': stats.get('total_experiments', 0),
                    'terrains_evaluated': len(data.get('results', {})),
                    'algorithms_compared': 4
                }
            
            # TA-A*の成功率
            if 'results' in data:
                tastar_successes = 0
                tastar_total = 0
                
                for terrain, terrain_results in data['results'].items():
                    if 'TA-A* (Proposed)' in terrain_results:
                        tastar = terrain_results['TA-A* (Proposed)']
                        tastar_successes += sum(1 for r in tastar if r.get('success', False))
                        tastar_total += len(tastar)
                
                if tastar_total > 0:
                    success_rate = tastar_successes / tastar_total * 100
                    paper_data['abstract_numbers']['ta_astar_success_rate'] = round(success_rate, 1)
                    
                    paper_data['key_findings'].append(
                        f"TA-A* achieved {success_rate:.1f}% success rate across all terrains"
                    )
    
    # 新規性データ
    novelty_file = results_dir / 'novelty_analysis.json'
    if novelty_file.exists():
        with open(novelty_file) as f:
            data = json.load(f)
            
            paper_data['novelty'] = {
                'total_elements': len(data.get('novelty_elements', [])),
                'completion_rate': data.get('overall', {}).get('completion_rate', 0)
            }
            
            if 'top_novelties' in data:
                paper_data['top_5_novelties'] = [
                    item['name'] for item in data['top_novelties'][:5]
                ]
    
    # 統計データ
    stat_file = results_dir / 'statistical_analysis_simple.json'
    if stat_file.exists():
        with open(stat_file) as f:
            data = json.load(f)
            
            paper_data['statistical_significance'] = {
                'a_star_success_rate': data.get('a_star', {}).get('success_rate', 0),
                'ta_astar_success_rate': data.get('ta_a_star', {}).get('success_rate', 0),
                'improvement': data.get('improvement', 0)
            }
            
            if data.get('improvement', 0) > 5:
                paper_data['key_findings'].append(
                    f"TA-A* showed {data['improvement']:.1f} percentage point improvement over A*"
                )
    
    # 出力
    output_file = results_dir / 'paper_data.json'
    with open(output_file, 'w') as f:
        json.dump(paper_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ データ保存: {output_file}")
    
    # 論文用テキスト生成
    print("\n" + "="*70)
    print("論文用テキスト（Abstract用）")
    print("="*70)
    
    if paper_data['abstract_numbers']:
        nums = paper_data['abstract_numbers']
        print("\nAbstract用の数値:")
        print(f"  総実験数: {nums.get('total_experiments', 0)}")
        print(f"  評価地形数: {nums.get('terrains_evaluated', 0)}")
        print(f"  比較アルゴリズム数: {nums.get('algorithms_compared', 0)}")
        print(f"  TA-A*成功率: {nums.get('ta_astar_success_rate', 0)}%")
    
    print("\n" + "-"*70)
    print("Abstract文例:")
    print("-"*70)
    
    if paper_data['abstract_numbers']:
        nums = paper_data['abstract_numbers']
        print(f"""
We propose Terrain-Aware A* (TA-A*), a novel path planning algorithm
for unmanned ground vehicles in unstructured environments. We evaluated
TA-A* through {nums.get('total_experiments', 0)} experiments across 
{nums.get('terrains_evaluated', 0)} representative terrain types, 
comparing it with {nums.get('algorithms_compared', 0)} baseline algorithms.
TA-A* achieved {nums.get('ta_astar_success_rate', 0)}% success rate, 
demonstrating superior performance in challenging terrains.
""")
    
    print("\n" + "="*70)
    print("主要な発見:")
    print("="*70)
    
    for i, finding in enumerate(paper_data['key_findings'], 1):
        print(f"{i}. {finding}")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    extract_paper_data()


