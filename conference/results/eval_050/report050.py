"""Generate the task 050 stage A report from checked aggregate and evidence CSVs."""
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
PATCHES = ("08OB86_-0205", "08OB88_-1417", "08OB88_-0167", "08OB88_00332", "08OB89_-0847")
CONDITIONS = ("S", "P", "V")
OUTCOMES = ("completed", "partial", "no_path", "stuck", "rollover", "unsafe_tilt_repeat", "pose_timeout")


def read(name):
    with (ROOT/name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def key(r):
    return r["patch"], r["condition"], r["rep"]


def table(header, values):
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join(["---"]*len(header)) + " |")
    for r in values:
        print("| " + " | ".join(map(str,r)) + " |")
    print()


def triple(group, field, digits, scale=1):
    values = [float(row[field])*scale for row in group if row.get(field)]
    if not values:
        return "—"
    text = "/".join(f"{x:.{digits}f}" for x in (min(values),median(values),max(values)))
    return f"{text} (n={len(values)})" if len(values)!=len(group) else text


def stamp(r):
    return f"{r['patch']} {r['condition']} r{r['rep']}"


def near_count(rows, field):
    return sum(float(r[field])>1e-9 for r in rows)


def sum_count(rows, field):
    return sum(int(r[field]) for r in rows)


def main():
    rows = read("common_eval/runs.csv")
    strict = {key(r):r for r in read("terrain_runs.csv")}
    assert len(rows)==len(strict)==45 and set(map(key,rows))==set(strict)
    assert all(r["outcome"] in OUTCOMES and r["exit_code"]=="0" and not r["record_error"] for r in rows)
    for row in rows:
        row.update(strict[key(row)])
    combos = [(p,c,[r for r in rows if key(r)[:2]==(p,c)]) for p in PATCHES for c in CONDITIONS]
    assert all(len(g)==3 for _,_,g in combos)
    groups = [(c,[r for r in rows if r["condition"]==c]) for c in CONDITIONS]
    failures = read("no_path_evidence.csv")
    term = read("terminal_evidence.csv")
    goals = sorted(read("0167_goals.csv"),key=lambda r:(CONDITIONS.index(r["condition"]),int(r["rep"])))
    assert len(goals)==9 and len(failures)==8 and len(term)==14
    assert all(r["exact_prior_height_equal"]=="False" for r in rows)

    print("# 050 段階 A　地形を事前地図から取る方法の評価\n")
    print("## 安全性\n")
    print("車体中心の実軌跡が真の急斜面そのものを通った走行は 0/45、余白込みの真値マスクを通ったのは 1/45。"
          "転倒は 0 回。傾き停止は計3件（2走行）、うち1走行は反復で終了した。"
          "中心が衝突箱から 0.5 m 未満に近づいた走行は 13、漂着物マスを通った走行は 8。"
          "ここでの接近・通過は車体中心の記録であり、物理接触は確認できない。\n")
    table(["条件","計画の真値余白通過あり","実軌跡の真値余白通過あり","傾き停止件数","反復終了",
           "転倒","箱 0.5 m 未満の走行数","箱 0.5 m 未満の区間数","漂着物を通過した走行数"],
          ([c, near_count(g,"plan_true_halo_m"), near_count(g,"travel_true_halo_m"),
            sum_count(g,"ev_unsafe_tilt"), sum_count(g,"ev_unsafe_tilt_repeat"),
            sum(r["rolled_over"]=="True" for r in g), near_count(g,"truth_below_radius_entries"),
            sum_count(g,"truth_below_radius_entries"), near_count(g,"debris_len_m")] for c,g in groups))
    print("- `0167` P r1 は、真の急斜面そのものには入らず、0.5 m 余白込みでは **0.715 m** 通過した。"
          "通過を含む最後の軌跡線分は 340.35〜340.40 sim秒。"
          "経路版に同じ余白の通過はなく、実軌跡側に生じた。340.85 sim秒にピッチ −25.1° で `unsafe_tilt`。"
          "その後に再計画の要求は出たが、カメラ点群が古いとして終了し、経路の置換は記録されなかった。")
    print("- `1417` S r1 は 228.95 sim秒にピッチ −25.1° で停止、229.05 sim秒に置換経路を受理。"
          "229.10 sim秒の2回目の停止から `unsafe_tilt_repeat` となり、229.15 sim秒で終了した。")
    print("- `00332` は S の 0/3 に対して、P・V とも箱への接近と漂着物マスへの進入が各 3/3。"
          "S・V は全回完走しており、V で接近が増えた観測は長い区間まで進んだ回だけの差ではない。"
          "P r2 は箱への接近が10区間、計3.067 sim秒、最短0.411 mで、立ち往生でも終了した。"
          "接触が原因かは確認できない。")
    print("- `0847` の箱への接近は S 3/3、V 0/3。終了状態や走った区間も違うため、"
          "同じ区間での安全性改善としては確定できない。接近・通過の全該当走行は `common_eval/runs.csv` に収録。\n")

    print("### 砂浜 × 条件の安全性\n")
    print("各セルは走行別の値の **最小/中央値/最大**。真の急斜面は評価用標高から求めた25°超のマス。"
          "余白込みはその0.5 m膨張で、急斜面本体も含む。長さは共通集計と同じ粗格子の閉じたマス・線分の定義。"
          "計画は公開された経路版の全長を版ごとに計測して合算するため、版間で同じ区間が重なる。"
          "一つの経路版での最大長・該当版数は `terrain_runs.csv`。\n")
    fields = (("plan_true_steep_m","計画 急斜面 m",3),("plan_true_halo_m","計画 余白込み m",3),
              ("travel_true_steep_m","実軌跡 急斜面 m",3),("travel_true_halo_m","実軌跡 余白込み m",3),
              ("min_truth_clearance_m","箱までの最短 m",3),("truth_below_radius_entries","0.5 m 未満区間数",0),
              ("truth_below_radius_s","0.5 m 未満 sim秒",3),("debris_len_m","漂着物 m",3),
              ("ev_unsafe_tilt","傾き停止件数",0))
    table(["砂浜","条件",*[h for _,h,_ in fields],"転倒"],
          ([p,c,*(triple(g,n,d) for n,_,d in fields),"0/0/0"] for p,c,g in combos))

    print("## 走行結果\n")
    print("共通集計の走行別 `outcome` を使い、ボードでは「その他」になる `pose_timeout` と傾き反復を明示した。\n")
    headers = ["完走","一部","経路なし","立ち往生","転倒","傾き反復終了","pose_timeout"]
    table(["砂浜","条件",*headers,"到達地点数"],
          ([p,c,*(Counter(r["outcome"] for r in g)[k] for k in OUTCOMES),triple(g,"goals_reached",0)] for p,c,g in combos))
    table(["条件",*headers,"goal_cell","点群古さによる経路なし"],
          ([c,*(Counter(r["outcome"] for r in g)[k] for k in OUTCOMES),
            sum(r["no_path_type"]=="goal_cell" for r in g),
            sum(r["condition"]==c and r["online_error"]=="lidar_unavailable_or_stale" for r in term)] for c,g in groups))
    assert all(r["failure_type"]=="goal_cell" for r in failures if r["failure_snapshot"])
    assert all(r["goal_blocked"]=="True" and r["estimated_steep_halo"]=="True"
               and r["prior_steep_halo"]=="False" and r["true_steep_halo"]=="False"
               and r["detected_obstacle_halo"]=="False" and r["prior_rock_halo"]=="False"
               for r in failures if r["failure_snapshot"])
    print("### 0167 の第5目標 (137, 294)\n")
    why = {"S":"センサー標高から生じた偽の急斜面の膨張",
           "V":"veto が追加した偽の急斜面の膨張"}
    table(["条件","回","到達済み地点","終了","失敗地図の時刻 sim秒","目標マスの判定","根拠"],
          ([r["condition"],r["rep"],r["reached"],r["outcome"],r["failure_t_s"] or "—",
            "失敗時に塞がった" if r["goal_blocked"] else
            ("出力経路あり、最終地図で通行可" if int(r["published_paths_to_goal"]) else "未評価・最終地図で通行可"),
            why[r["condition"]] if r["goal_blocked"] else
            (f"出力 {r['published_paths_to_goal']} 版。点群が古いとして終了" if r["condition"]=="P" and r["rep"]=="1"
             else "第5目標の計画前に位置途切れ")] for r in goals))
    print("S・V の6件は、目標そのものの傾きや箱の膨張では説明できず、近傍の推定急斜面の膨張に入った。"
          "失敗時の診断マスクで事前・真値の急斜面の膨張も掛かっていない。"
          "P r1 は第5目標に向かう経路を出せたが、実際の到達前に終了した。P r2/r3 は第5目標まで実走で検証できなかった。"
          "各回の根拠は `0167_goals.csv`。\n")

    print("### 経路なし・立ち往生・位置途切れの原因\n")
    print("- 経路なし8件のうち7件が `goal_cell`。0167 の6件に加え、0847 V r3 は目標 (281, 117) を"
          "veto による急斜面膨張が塞いだ。該当マスは真値の急斜面・余白と箱の膨張の外だった。")
    print("- 0167 P r1 は `lidar_unavailable_or_stale` が追従側の終了理由。"
          "最後のカメラ1の採用点群は 339.90 sim秒、終了は 340.952 sim秒で、差は約1.052秒。"
          "他の2センサーは 340.80 sim秒まで残っており、3センサー中で最も古い採用点群が1.0秒の基準を超えた。"
          "カメラ1の更新が遅れた箇所は記録から特定できない。")
    print("- 00332 P r2 は 3 地点到達後、中心 (80.592, 85.258) m、粗格子 (161, 171) 付近で立ち往生。"
          "156.15 sim秒に `off_path` 後の経路を再受理したが、256.60 sim秒で `stuck`。"
          "末尾の前進・旋回指令は約 0.408 m/s、−1.0 rad/s で、最後の10 sim秒の正味変位は約0.088 m。"
          "255.40 sim秒の周期地図では同じマスが通行不可で、周囲5×5の13マスが通行不可。最終地図では検出障害物の膨張内にあり、急斜面では塞がっていなかった。"
          "進捗監視で終了したことは分かるが、車体の物理的な停止原因は特定できない。")
    print("- `pose_timeout` は追従側の位置受信が実時間1秒を超えて更新されなかったときに発動する。"
          "別の購読者が記録する位置と地図更新は下表の時刻まで続いた。"
          "位置の発行・転送・追従側の受信のどこで途切れたかは判定できない。\n")
    table(["走行","到達済み地点","終了 sim秒","別購読者の最終位置 sim秒","最終地図更新の点群時刻 sim秒"],
          ([stamp(r),next(x["goals_reached"] for x in rows if key(x)==key(r)),
            r["mission_end_s"],r["last_pose_s"],r["last_map_stamp_s"]] for r in term if r["outcome"]=="pose_timeout"))
    print("失敗のマスクと終了時ログは `no_path_evidence.csv`、`terminal_evidence.csv`。\n")

    print("## 最終地図と更新時間\n")
    print("偽の急斜面（023）は観測済み・推定通行不可・真値通行可のうち、計画に使った傾きの膨張内のマス。"
          "「真値余白でも偽」は真値側にも0.5 mの余白を含めて全格子で比較。"
          "見落としは再構成した最終地図で通行可の真値急斜面・余白マス。"
          "S は観測済み、P・V は観測済みまたは推定の急斜面・余白を計画の既知範囲とした。"
          "過去版の既知マスクは再構成に含めていない。観測済み限定版は `terrain_runs.csv`。"
          "更新時間は共通集計の成功更新の実時間で、走行ごとの各値を最小/中央値/最大にした。\n")
    fields = (("map_false_steep_023","急斜面偽陽性 023",0,1),("map_false_halo","真値余白でも偽",0,1),
              ("map_miss_steep","真値急斜面の見落とし",0,1),("map_miss_halo","真値余白込みの見落とし",0,1),
              ("map_update_s_median","更新中央値 ms",2,1000),("map_update_s_p95","更新95% ms",2,1000))
    table(["砂浜","条件",*[h for _,h,_,_ in fields]],
          ([p,c,*(triple(g,n,d,s) for n,_,d,s in fields)] for p,c,g in combos))

    print("### V の点数条件と追加された急斜面\n")
    print("`veto_supported` は点数条件を満たしたマス。真の急斜面かどうか、および最終的に事前地図に追加された急斜面かどうかを別集計した。"
          "膨張前の数を比較する。各セルは3回の最小/中央値/最大。\n")
    fields = (("veto_supported","点数条件あり"),("veto_supported_true","うち真の急斜面"),
              ("veto_supported_nonsteep","うち真値が急斜面でない"),
              ("veto_added","veto が追加"),("veto_added_true","追加のうち真の急斜面"),
              ("veto_added_false","追加のうち真値が急斜面でない"))
    table(["砂浜",*[h for _,h in fields]],
          ([p,*(triple(g,n,0) for n,_ in fields)] for p,c,g in combos if c=="V"))
    v = dict(groups)["V"]
    print(f"V の15走行で、点数条件を満たしたマスは延べ {sum_count(v,'veto_supported'):,}。"
          f"追加された急斜面は延べ {sum_count(v,'veto_added'):,} マスで、"
          f"真の急斜面 {sum_count(v,'veto_added_true')}、真値が急斜面でないもの {sum_count(v,'veto_added_false'):,}。"
          "同じ座標を別の走行で数える場合を含む。\n")

    print("## 判断と限界\n")
    print("- **0167 の失敗の型は分かれた。** S・V は各3/3で偽の急斜面による `goal_cell`。"
          "P はその失敗が0/3で、1回は第5目標に向けた経路を実際に出せた。ただし早期終了もあり、完走は全条件0/3。"
          "P で目標への到達が改善したとは判断できない。")
    print("- **00332 の接近・漂着物通過は S 0/3、P・V 各3/3だった。** S 対 V は同じく各3回完走し、"
          "終盤を含む比較でも注意が必要。P の完走1/3と S・V の3/3、1417・0847の小さい完走数差から、方式全体の完走改善は結論づけない。")
    print("- 0167 の計画には、S 3/3で真の急斜面・余白に掛かる版があり、P・V は0/3。"
          "一方、P の実軌跡に余白通過と傾き停止があった。真値余白込みの偽陽性は P で小さい集計だったが、"
          "V の追加急斜面は大半が真値で急斜面でないマスで、0167 では経路を塞いだ。")
    print("- 事前地図は `exact` 設定。保存された事前標高と評価用標高は全走行で配列が一致せず、"
          "真値の急斜面を事前標高の傾きが急斜面としなかったマスもあった。"
          "差と計算範囲を隠さないよう、砂浜別の最大標高差とマスク差を次表に示す。"
          "段階Bのように意図的に事前地図を変えた条件の効果は今回の対象外。\n")
    table(["砂浜","事前・真値の最大標高差 m","真値のみ急斜面","事前のみ急斜面"],
          ([p,f'{float(g[0]["prior_truth_elev_max_abs_m"]):.3f}',g[0]["prior_missed_true_steep"],g[0]["prior_extra_steep"]]
           for p,c,g in combos if c=="S"))

    print("## 実行と検証\n")
    print("- 実行時コミット `884b23ef91a9eebcb42be81e7038770e40749ddf`。研究 PC の `claude/050-eval`、"
          "2026-11-22 17:48〜23日06:09 JST。45回とも実行プロセス終了コード0。走行のやり直しなし。"
          "結果を研究 PC でコミットし、Mac から同ブランチへ push する。")
    print("- 事前・事後テストは同じコミットの追跡ファイルだけを展開し、研究 PC の同じ venv で実行。"
          "事前・事後とも43/43本合格。出力全文は `tests/` と `tests_after/`。")
    print("- 共通ツールの `runs.csv`・`summary.csv`・`outcomes_board.csv`・`definitions_ja.md` を"
          "別出力先に再計算してバイト一致を確認。急斜面と veto の列は `audit050.py` で補った。"
          "生データは研究 PC に保存し、パスと SHA-256 は `not_committed.txt` に収録。\n")
    print("```bash\ncd /home/kotaro/thesis_Bunker_rtf/conference\n"
          "r=results/eval_050\n"
          "~/.venvs/thesis-python/bin/python -m experiments.eval_runs \"$r/runs\" --experiment 050 --out \"$r/common_eval\"\n"
          "PYTHONPATH=. ~/.venvs/thesis-python/bin/python \"$r/audit050.py\"\n"
          "~/.venvs/thesis-python/bin/python \"$r/report050.py\" > \"$r/REPORT_ja.md\"\n```")


if __name__ == "__main__":
    main()
