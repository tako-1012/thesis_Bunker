"""Render the 073 report from the immutable CSV summaries."""

from collections import Counter
import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PATCHES = ("08OB86_-0205", "08OB88_-1417", "08OB88_00332", "08OB89_-0847")
CONDITIONS = ("none", "bias025", "bias050", "bias100", "yaw2", "drift05", "drift1", "drift2")


def records(name):
    with (ROOT / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def table(headers, rows):
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for line in rows:
        print("| " + " | ".join(map(str, line)) + " |")
    print()


def number(rows, field):
    return [float(row[field]) for row in rows if row.get(field) not in ("", None)]


def three(values, q=(0, 50, 100), places=3):
    return "/".join(f"{v:.{places}f}" for v in np.percentile(values, q)) if values else "—"


def main():
    runs, arrivals = records("run_metrics.csv"), records("arrivals.csv")
    failures = records("abnormal_runs.csv")
    fisher = records("fisher_holm.csv")
    causes = records("box_approaches.csv")
    grouped = [(patch, condition, [row for row in runs if (row["patch"], row["condition"]) == (patch, condition)])
               for patch in PATCHES for condition in CONDITIONS]
    assert len(runs) == 160 and all(len(group) == 5 for _, _, group in grouped)
    assert len(arrivals) == 869 and all(row.get("true_distance_m") for row in arrivals)
    assert len(failures) == 98 and len(fisher) == 21 and len(causes) == 3

    print("""# 073　自己位置にずれを入れた Gazebo 評価

## 安全性

箱への 0.5 m 未満の接近は **3/160 回**で、それぞれ 1 区間だった。
最短は **1417 の drift05 r3、0.422 m**。この走行は漂着物の粗マスも 0.213 m 通過した。
真の急斜面本体・0.5 m の余白への進入、転倒はそれぞれ 0/160 回。
箱と地形は、Gazebo の正解位置を記録した車体中心の平面軌跡から評価した。
物理的な車体接触は判定できない。

以下の連続値は各 5 回の最小／中央値／最大。急斜面は正解標高の傾きが 25°を超えるマス。
0.5 m の余白は 064・067 と同じ格子膨張で急斜面本体を含む。走行数は通過長が正の回を数えた。
""")
    safety = []
    for patch, condition, group in grouped:
        box, steep, halo, debris, tilt = (number(group, name) for name in (
            "min_truth_clearance_m", "travel_true_steep_m", "travel_true_halo_m", "debris_len_m", "unsafe_tilt"))
        present = lambda values: sum(v > 0 for v in values)
        format_slope = lambda values: f"{present(values)}（{three(values)}）"
        safety.append((patch, condition, three(box), sum(v < .5 for v in box), format_slope(steep),
                       format_slope(halo), f"{present(tilt)}/{int(sum(tilt))}",
                       sum(r["rollover"] == "True" for r in group), format_slope(debris)))
    table(("砂浜", "条件", "箱最短 m", "箱 <0.5 m", "急斜面 回（m）", "余白 回（m）",
           "傾き停止 回/件", "転倒", "漂着物 回（m）"), safety)

    table(("砂浜", "条件・回", "最接近 sim 秒", "箱まで m", "採用経路から箱まで m", "0.5m 未満 sim 秒"),
          ((r["patch"], f"{r['condition']} r{r['rep']}", f"{float(r['time']):.3f}",
            f"{float(r['min_truth_clearance_m']):.3f}", f"{float(r['applied_path_distance_m']):.3f}",
            f"{float(r['duration_s']):.3f}") for r in causes))
    print("""箱への接近 3 件では、そのときの計画地図に箱の検出点があった。
1417 の drift05 r3 と 0847 の none r3 は、採用経路上の最短距離が 0.5 m を上回った。
0847 の drift2 r2 では採用経路自体が箱の 0.5 m 以内に入った。
[接近区間の CSV](box_approaches.csv)

傾き停止はすべて 1417 で **3 回の走行、計 5 件**。bias025 r5 と drift1 r3 は
各 1 回目の停止後に再計画したが、0.35・0.15 シミュレーション秒後に傾き停止が再発し終了した。
yaw2 r5 は 235.45 シミュレーション秒で停止し、再計画後に再開して完走した。

## 走行結果

共通集計の完走は、ロボットが完走を報告し、正解軌跡が 5 地点を順に各 0.3 m 以内で通り、
最後に出発点の 0.3 m 以内へ戻った走行。一部は完走報告と正解軌跡の条件が一致しなかった走行。
ロボット側では 141 回が完走、正解軌跡では **完走 62 回、一部 79 回**だった。
残りは経路なし 17 回と傾き停止の反復 2 回。止まったまま・転倒・点群の古さ・位置受信の
タイムアウトによる終了は 0 回。距離と時間は 5 回の最小／中央値／最大。

条件名は none（誤差なし）、bias025・bias050・bias100（海岸方向の固定ずれ 0.25・0.5・1.0 m）、
yaw2（向き 2°）、drift05・drift1・drift2（距離ドリフト 0.5・1・2%）。
""")
    outcome = []
    for patch, condition, group in grouped:
        count = Counter(r["termination_type"] for r in group)
        outcome.append((patch, condition, count["completed"], count["partial"], count["no_path"],
                        count["unsafe_tilt_repeat"], sum(r["controller_status"] == "completed" for r in group),
                        three(number(group, "true_goals_reached"), places=1),
                        three(number(group, "controller_stops"), places=1),
                        three(number(group, "travel_m"), places=2),
                        three(number(group, "elapsed_s"), places=2), three(number(group, "wall_s"), places=2)))
    table(("砂浜", "条件", "完走", "一部", "経路なし", "傾き反復", "ロボット完走報告",
           "正解軌跡の到達数", "ロボットの到達数", "実走距離 m", "sim 秒", "実秒"), outcome)

    print("""経路なし 17 回はすべて `goal_cell`。0847 では固定ずれ 3 条件の全 15 回で第 2 地点
(281, 117) が塞がった。最終地図の内訳は検出障害物の膨張 10 回と検出障害物 5 回。
1417 の drift2 r1・r3 は第 1 地点 (199, 151) が検出障害物の膨張で塞がった。
両目標の中心から真の箱まではそれぞれ 0.791 m と 0.750 m。
[計画地図の照合](plan_map_inspect/goal_cell.csv) · [未完走 98 回の一覧](abnormal_runs.csv)

## 到着判定時の正解位置

第 1～5 地点は、現在の推定位置で 0.3 m 以内と判定して次の区間を探索した時点の
§start_leg§ スナップショットを使った。次の探索が失敗した場合も直前の到着は数えた。
帰還は追従側が完走を報告した時点の pose を使った。
ずれのある走行ではその推定 XY と一致する §pose_error.csv§ の行を時刻で照合し、同一行の
真値 XY を採用した。判定時刻から元の pose スタンプまで 0.001～0.052 sim 秒だった。
none は同じ判定記録の XY が真値である。巡回地点と帰還の **計 869 件すべて**を測定した。
""".replace("§", chr(96)))
    arrival_table = []
    for condition in CONDITIONS:
        selected = [r for r in arrivals if r["condition"] == condition]
        stops = number([r for r in selected if r["kind"] == "stop"], "true_distance_m")
        returns = number([r for r in selected if r["kind"] == "return"], "true_distance_m")
        arrival_table.append((condition, len(stops), three(stops, (50, 95, 100)), len(returns),
                              three(returns, (50, 95, 100)), sum(x > .3 for x in stops)))
    table(("条件", "巡回到着件数", "巡回地点までの真値距離 m 中央/95%/最大",
           "帰還件数", "出発点までの真値距離 m 中央/95%/最大", "巡回の真値距離 >0.3m"), arrival_table)
    print("[全到着の座標・時刻と距離](arrivals.csv)\n")

    print("""## 実際に入った位置のずれ

開始から終了までの中継ログ（現在・前世代の CSV）を照合した。
最後は終了以前の最終標本。固定ずれは全標本で指定どおりの海岸方向ずれと向きの差だった。
ドリフトは 1 m ごとの乱数歩数・種から全標本の XY の差を再現した。
none は中継を使わず、注入誤差を 0 とした。ドリフト % は 1 m ごとに加える
各軸の正規乱数の標準偏差で、走行距離の一定割合がそのまま位置差になる設定ではない。
各セルは 20 回の最小／中央値／最大。
""")
    errors = []
    for condition in CONDITIONS:
        group = [r for r in runs if r["condition"] == condition]
        errors.append((condition, three(number(group, "last_xy_error_m")), three(number(group, "max_xy_error_m")),
                       three(number(group, "max_abs_yaw_error_deg")), three(number(group, "relay_travel_m"), places=2),
                       three(number(group, "travel_m"), places=2)))
    table(("条件", "最後の XY 差 m", "走行中最大の XY 差 m", "最大の向き差 °",
           "中継での累積走行距離 m", "評価軌跡の距離 m"), errors)
    print("[各走行のずれ、記録範囲と走行時間](run_metrics.csv)\n")

    print("""## 事前に定めた検定

各条件 20 回と none 20 回の Fisher の両側正確検定。指標ごとに 7 比較を Holm で補正した。
完走は共通集計の正解軌跡を含む基準。箱への接近は真値の最短距離が厳密に 0.5 m 未満、
急斜面の余白への進入は真値の余白を通過した長さが正という基準。
""")
    labels = dict(box_close="箱 <0.5 m", true_steep_halo="急斜面の余白に進入", completed="完走")
    table(("指標", "条件 対 none", "条件 回数", "none 回数", "未補正 p", "Holm 補正 p"),
          ((labels[r["metric"]], r["condition"], f"{r['count']}/20", f"{r['reference_count']}/20",
            f"{float(r['p_raw']):.8g}", f"{float(r['p_holm']):.8g}") for r in fisher))
    print("""正解軌跡での完走は、試した最小の固定ずれ **0.25 m で 4/20**、最小のドリフト
**0.5% で 12/20** まで減った（none は 20/20）。0.5 m と 1.0 m では各 0/20。
向き 2° では 20/20 が完走した。箱への接近と急斜面の余白進入は全比較で補正後 p=1。
固定ずれの 0847 では早期終了が集中したため、箱に近づく機会も条件で違う。
20 回・4 砂浜の結果から有意差が出なかった指標の同等性や、実機で必要な精度の境界までは決められない。
[検定の全桁 CSV](fisher_holm.csv)

## 実行・保存・検証

- 研究 PC §hayashi§ で §e0066a5ec29bbd10ed98fe7441d146289b64a1d7§ を実行。
  JST 2026-11-27 10:46:34～23:42:42、tmux §eval-073§、ROS ドメイン 73。
  各周の先頭は、正解と推定の両方が記録される bias025 にした。次に none、bias050、
  bias100、yaw2、drift05、drift1、drift2 の順。全回で seed 0、rep 1～5。
- **160/160 回**の実行順、引数、終了コード、manifest が一致した。欠け・重複・プロセスの
  非ゼロ終了は 0。全回 NVIDIA 描画、実測倍率 0.9878～1.0000。計画地図の記録打ち切りは 0。
  [走行条件の照合](run_inventory.csv) · [初回の確認](first_check.json)
- テストは研究 PC の同じ venv、同じコミットで前後とも **57/57 本合格**。
  初回の作業ツリーには過去実験の未追跡生記録があり、§test_common_eval§ が 030 の集計を
  45 件として検出した（想定 43）。独立した作業ツリーで前後の全テストを実行した。
  [走行前](tests/summary.txt) · [走行後](tests_after/summary.txt)
- 生記録 18,593 ファイル（約 4.04 GB）は研究 PC に保管し、SHA-256 を再照合した。
  [保管場所とハッシュ](not_committed.txt)

§§§sh
cd /home/kotaro/thesis_Bunker_rtf/conference
py="$HOME/.venvs/thesis-python/bin/python"
"$py" -m experiments.eval_runs results/eval_073/runs --experiment 073 --out results/eval_073/common_eval
"$py" -m experiments.plan_map_inspect "$PWD/results/eval_073/runs" --out "$PWD/results/eval_073/plan_map_inspect"
"$py" -m experiments.pose_trace_inspect "$PWD/results/eval_073/runs" --out "$PWD/results/eval_073/pose_trace_inspect.csv"
PYTHONPATH=. "$py" results/eval_073/audit073.py
"$py" results/eval_073/render073.py
§§§

同じ砂浜での反復が含まれる。到着時の分布は到着判定まで進んだ地点が母集団で、早期終了した
走行の未到達地点は含まれない。Yaw・固定ずれ・距離ドリフトは単独で与えた条件で、
複合したずれや実機センサーの誤差の分布は評価していない。
""".replace("§", chr(96)))


if __name__ == "__main__":
    main()
