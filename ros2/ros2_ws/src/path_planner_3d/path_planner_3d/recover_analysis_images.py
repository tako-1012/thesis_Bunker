import os
import sys
import subprocess
import argparse

IMAGE_LIST = [
    "fallback_analysis_comparison.png",
    "path_quality_analysis.png",
    "scalability_analysis.png",
    "statistical_analysis.png",
    "ablation_analysis.png",
    "ablation_by_complexity.png",
    "sensitivity_analysis.png",
    "sensitivity_by_complexity.png"
]
SEARCH_DIRS = [".", "benchmark_results", "ablation_results", "sensitivity_results"]
SCRIPT_MAP = {
    "fallback_analysis_comparison.png": "analyze_fallback.py",
    "path_quality_analysis.png": "analyze_path_quality.py",
    "scalability_analysis.png": "analyze_scalability.py",
    "statistical_analysis.png": "analyze_statistics.py",
    "ablation_analysis.png": "analyze_ablation.py",
    "ablation_by_complexity.png": "analyze_ablation.py",
    "sensitivity_analysis.png": "analyze_sensitivity.py",
    "sensitivity_by_complexity.png": "analyze_sensitivity.py"
}

LOG_FILE = "recover_analysis_images.log"

def color(text, c):
    codes = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m", "end": "\033[0m"}
    return codes.get(c, "") + text + codes["end"] if sys.stdout.isatty() else text

def find_image(filename):
    for d in SEARCH_DIRS:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    return None

def run_script(script):
    print(color(f"[実行中] {script} を実行中...", "yellow"))
    try:
        result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
        with open(LOG_FILE, "a") as log:
            log.write(f"==== {script} ====" + "\n" + result.stdout + "\n" + result.stderr + "\n")
        if result.returncode == 0:
            print(color(f"[完了] {script} が完了しました", "green"))
            return True
        else:
            print(color(f"[失敗] {script} 実行失敗", "red"))
            return False
    except Exception as e:
        print(color(f"[エラー] {script}: {e}", "red"))
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="全画像を強制再生成")
    parser.add_argument("--check-only", action="store_true", help="検索のみ（再生成しない）")
    args = parser.parse_args()

    print("="*65)
    print("分析画像の復旧処理")
    print("="*65)
    print("\n[検索中] 画像ファイルを探しています...")

    found = []
    missing = []
    regenerated = []

    for img in IMAGE_LIST:
        path = find_image(img)
        if path and not args.force:
            print(f"  {color('✅', 'green')} {img}: 見つかりました ({path})")
            found.append(img)
        else:
            print(f"  {color('❌', 'red')} {img}: 見つかりません → 再生成します")
            missing.append(img)
            if not args.check_only:
                script = SCRIPT_MAP.get(img)
                if script and os.path.exists(script):
                    ok = run_script(script)
                    if ok:
                        # 再生成後、再検索
                        new_path = find_image(img)
                        if new_path:
                            print(f"  {color('✅', 'green')} {img}: 再生成成功 ({new_path})")
                            regenerated.append(img)
                        else:
                            print(f"  {color('❌', 'red')} {img}: 再生成失敗")
                    else:
                        print(f"  {color('❌', 'red')} {img}: スクリプト実行失敗")
                else:
                    print(f"  {color('❌', 'red')} {img}: 対応スクリプトが見つかりません")

    print("\n" + "="*65)
    print("復旧完了レポート")
    print("="*65)
    print(f"  元から存在: {len(found)}枚")
    print(f"  再生成完了: {len(regenerated)}枚")
    print(f"  合計: {len(found) + len(regenerated)}枚\n")
    if len(found) + len(regenerated) == len(IMAGE_LIST):
        print(color("  ✅ 全ての画像が揃いました！", "green"))
    else:
        lack = [img for img in IMAGE_LIST if img not in found + regenerated]
        print(color(f"  ❌ まだ不足: {lack}", "red"))
    print("\n" + "="*65)

if __name__ == "__main__":
    main()
