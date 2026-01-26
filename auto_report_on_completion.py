import time
import json
import subprocess
from pathlib import Path
import datetime


def is_benchmark_running():
    """ベンチマークが実行中か確認"""
    try:
        pid_path = Path('benchmark.pid')
        if not pid_path.exists():
            return False
        pid = pid_path.read_text().strip()

        # プロセスが存在するか確認
        result = subprocess.run(['ps', '-p', pid], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def check_completion():
    """完了を確認"""
    result_file = Path('benchmark_results/dataset2_6planners_results.json')

    if not result_file.exists():
        return False, 0

    try:
        with result_file.open('r') as f:
            results = json.load(f)
    except Exception:
        return False, 0

    total_expected = 6 * 144
    completed = len(results)

    return completed >= total_expected, completed


def generate_summary_report(results):
    """要約レポート生成"""
    report = []
    report.append("=" * 60)
    report.append("DATASET 2 BENCHMARK COMPLETE")
    report.append("=" * 60)
    report.append("")

    total_tasks = len(results)
    success_count = sum(1 for r in results if r.get('success', False))

    report.append(f"Total tasks: {total_tasks}")
    report.append(f"Success: {success_count}/{total_tasks} ({(success_count/total_tasks*100) if total_tasks>0 else 0:.1f}%)")
    report.append("")

    planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']

    report.append("=" * 60)
    report.append("BY PLANNER")
    report.append("=" * 60)
    report.append("")

    for planner in planners:
        planner_results = [r for r in results if r.get('planner') == planner]
        if not planner_results:
            continue

        planner_success = sum(1 for r in planner_results if r.get('success', False))
        times = [r.get('computation_time', 0) for r in planner_results if r.get('success', False)]
        paths = [r.get('path_length_meters', 0) for r in planner_results if r.get('success', False)]

        report.append(f"{planner}:")
        report.append(f"  Success: {planner_success}/{len(planner_results)} ({(planner_success/len(planner_results)*100):.1f}%)")

        if times:
            report.append(f"  Avg time: {sum(times)/len(times):.3f}s")
            report.append(f"  Min time: {min(times):.3f}s")
            report.append(f"  Max time: {max(times):.3f}s")

        if paths:
            report.append(f"  Avg path: {sum(paths)/len(paths):.1f}m")

        report.append("")

    report.append("=" * 60)
    report.append("BY ENVIRONMENT")
    report.append("=" * 60)
    report.append("")

    env_types = ['steep', 'dense', 'complex']

    for env_type in env_types:
        env_results = [r for r in results if env_type in r.get('scenario_id', '').lower()]
        if not env_results:
            continue

        env_success = sum(1 for r in env_results if r.get('success', False))

        report.append(f"{env_type.upper()}:")
        report.append(f"  Total: {len(env_results)}")
        report.append(f"  Success: {env_success}/{len(env_results)} ({(env_success/len(env_results)*100):.1f}%)")
        report.append("")

    report_text = "\n".join(report)

    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)
    with (outdir / 'dataset2_summary_report.txt').open('w') as f:
        f.write(report_text)

    return report_text


def main():
    print("Waiting for benchmark completion...")
    print("Checking every 5 minutes...")

    check_interval = 300  # 5分

    while True:
        running = is_benchmark_running()
        completed, count = check_completion()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if completed:
            print(f"\n[{current_time}] BENCHMARK COMPLETE!")
            print(f"Total results: {count}")
            print("\nGenerating summary report...")

            with open('benchmark_results/dataset2_6planners_results.json', 'r') as f:
                results = json.load(f)

            report = generate_summary_report(results)
            print("\n" + report)
            print("\nReport saved: benchmark_results/dataset2_summary_report.txt")
            break

        elif not running and count > 0:
            print(f"\n[{current_time}] WARNING: Process stopped but incomplete ({count}/864)")
            print("Check benchmark.log for errors")
            break

        else:
            print(f"[{current_time}] Running... ({count}/864 completed)")

        time.sleep(check_interval)

    print("\nMonitoring complete.")


if __name__ == '__main__':
    main()
