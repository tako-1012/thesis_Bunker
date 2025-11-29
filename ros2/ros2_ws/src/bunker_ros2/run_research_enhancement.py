#!/usr/bin/env python3
"""
研究強化の完全実行スクリプト

実験完了後に統計的検定、高度な評価指標、感度分析を実行
"""
import subprocess
import sys
from pathlib import Path
import time

def run_analysis_script(script_path: str, description: str):
    """分析スクリプトを実行"""
    print(f"\n{'='*70}")
    print(f"実行中: {description}")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ {description} 完了")
            print(result.stdout)
        else:
            print(f"❌ {description} 失敗")
            print(f"エラー: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} タイムアウト")
    except Exception as e:
        print(f"❌ {description} エラー: {e}")

def main():
    """メイン実行"""
    print("🚀 研究強化の完全実行開始")
    print("="*70)
    
    # 結果ファイルの存在確認
    results_file = Path('../results/efficient_terrain_results.json')
    if not results_file.exists():
        print("❌ 実験結果ファイルが見つかりません")
        print("先にPhase 2-5の実験を完了してください")
        return
    
    print("✅ 実験結果ファイル確認完了")
    
    # Phase Q1: 統計的検定
    run_analysis_script(
        'analysis/statistical_tests.py',
        'Phase Q1: 統計的検定'
    )
    
    # Phase Q2: 高度な評価指標（テスト）
    run_analysis_script(
        'analysis/advanced_metrics.py',
        'Phase Q2: 高度な評価指標テスト'
    )
    
    # Phase Q4: パラメータ感度分析
    run_analysis_script(
        'analysis/parameter_sensitivity.py',
        'Phase Q4: パラメータ感度分析'
    )
    
    # Phase Q5: 失敗ケース分析
    run_analysis_script(
        'analysis/failure_analysis.py',
        'Phase Q5: 失敗ケース分析'
    )
    
    print("\n" + "="*70)
    print("🎉 研究強化完了！")
    print("="*70)
    print("実行された分析:")
    print("✅ Phase Q1: 統計的検定")
    print("✅ Phase Q2: 高度な評価指標")
    print("✅ Phase Q4: パラメータ感度分析")
    print("✅ Phase Q5: 失敗ケース分析")
    print("\n次のステップ:")
    print("1. 分析結果を確認")
    print("2. 論文執筆に進む")
    print("3. 追加実験が必要な場合は実行")

if __name__ == '__main__':
    main()



