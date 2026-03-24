import json

def main():
    with open('aha_param_test_results.json', 'r') as f:
        results = json.load(f)

    best_params = None
    best_time = float('inf')

    param_sets = set(r['param_set'] for r in results)

    for param_set in param_sets:
        param_results = [r for r in results if r['param_set'] == param_set]
        success_count = sum(1 for r in param_results if r['success'])
        avg_time = sum(r['time'] for r in param_results) / len(param_results)

        if success_count == 2 and avg_time < best_time:
            best_params = param_set
            best_time = avg_time

    print("\n=== 判断 ===\n")

    if best_params and best_time < 10:
        print(f"✓ SUCCESS!\n  Best params: {best_params}\n  Avg time: {best_time:.3f}s\n\n→ このパラメータで本実行へ！")
    elif best_params and best_time < 30:
        print(f"△ PARTIAL SUCCESS\n  Best params: {best_params}\n  Avg time: {best_time:.3f}s\n\n→ 遅いが使用可能。本実行するか検討")
    else:
        print("✗ NO IMPROVEMENT\n\n→ AHA*をスキップして本実行（6手法）を推奨")

if __name__ == '__main__':
    main()
