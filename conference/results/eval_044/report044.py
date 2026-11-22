"""Format the task 044 common-evaluation tables and per-event evidence."""
import csv
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
PATCHES = ("08OB86_-0205", "08OB88_-1417", "08OB88_-0167", "08OB88_00332", "08OB89_-0847")
CONDITIONS = ("B", "O", "T", "OT")
OUTCOMES = ("completed", "partial", "no_path", "stuck", "rollover", "unsafe_tilt_repeat", "pose_timeout")


def read(name):
    with (ROOT / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def table(header, rows):
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join(["---"] * len(header)) + " |")
    for row in rows:
        print("| " + " | ".join(map(str, row)) + " |")
    print()


def triple(group, field, places):
    values = [float(row[field]) for row in group if row.get(field)]
    if not values:
        return "—"
    text = "/".join(f"{x:.{places}f}" for x in (min(values), median(values), max(values)))
    return f"{text} (n={len(values)})" if len(values) != len(group) else text


def fmt(row, key, places=3):
    value = row.get(key)
    return f"{float(value):.{places}f}" if value else "—"


def stamp(row):
    return f"{row['patch']} {row['condition']} r{row['rep']}"


def count(group, field):
    return sum(int(row[field]) for row in group)


def main():
    data = read("common_eval/runs.csv")
    keys = {(r["patch"], r["condition"], r["rep"]) for r in data}
    assert len(data) == len(keys) == 60
    assert all(r["outcome"] in OUTCOMES and r["exit_code"] == "0" and not r["record_error"] for r in data)
    assert all(float(r["target_rtf"]) == .3 for r in data)
    groups = [(p, c, [r for r in data if r["patch"] == p and r["condition"] == c])
              for p in PATCHES for c in CONDITIONS]
    assert all(len(group) == 3 for _, _, group in groups)
    by_condition = [(c, [r for r in data if r["condition"] == c]) for c in CONDITIONS]
    approaches = read("approach_evidence.csv")
    no_path = read("no_path_evidence.csv")
    terminals = {r["outcome"]: r for r in read("terminal_evidence.csv")}
    assert len(approaches) == 2 and len(no_path) == 25 and len(terminals) == 3
    assert all(count(data, f) == 0 for f in ("truth_lethal_entries", "debris_entries", "ev_unsafe_tilt_repeat"))

    print("# 044　障害物の膨らませと曲がり角での減速の評価\n")
    print("## 安全性\n")
    print("60 回のうち、車体中心と衝突箱の XY 投影との距離が 0.5 m 未満となった走行は 2 回。"
          "傾き停止は 1 回。転倒、傾き停止の反復終了、真値通行不可マス・漂着物マスへの中心軌跡の進入は 0 回だった。"
          "箱との距離は中心軌跡の指標で、車体の物理接触は確認できない。時刻と時間はシミュレーション秒。\n")

    print("### 箱への接近 2 件\n")
    table(["走行", "0.5 m 未満の区間 s", "継続 s", "最接近時刻 s", "中心位置 x,y m", "中心→箱 m",
           "経路版 s", "経路→同じ箱 m", "射影点→箱 m", "最接近時の偏差 m", "区間内の最大偏差 m", "主因"],
          ([stamp(r), f"{fmt(r,'entered_s')}–{fmt(r,'exited_s')}", fmt(r,"duration_s"),
            fmt(r,"nearest_t_s"), f"({fmt(r,'x')}, {fmt(r,'y')})", fmt(r,"min_box_m"),
            fmt(r,"path_t_s"), fmt(r,"path_to_same_box_m"), fmt(r,"projected_point_to_box_m"),
            fmt(r,"deviation_at_nearest_m"), fmt(r,"deviation_max_during_m"),
            "経路が近すぎた" if r["condition"] == "T" else "追う側のずれ"] for r in approaches))
    print("- `08OB86_-0205` T r2 は、最接近時の経路上の射影点も箱から 0.421 m。中心の偏差はその時点で 0.013 m で、"
          "計画された線に沿っても 0.5 m の余裕がない位置だった。接近区間中には経路版が 2 回変わった。")
    print("- `08OB89_-0847` B r3 は、接近中に経路版は変わらず、経路全体と箱の最短距離は 0.747 m。"
          "射影点から箱までは 0.791 m あり、中心はその経路から 0.356 m ずれて箱に接近した。")
    print("- 箱と面積が重なる 0.1 m の細格子は、前者ではシミュレーション時刻 28.0 s から最接近時までに 50 個、"
          "後者では 95.6 s から 25 個が障害物として初回登録されていた。地図の見落としを主因とする証拠は得られなかった。"
          "登録履歴は箱の位置に検出があったことを示す。接近時の計画用マスクそのものは残っていないため、"
          "見えていない膨張マスの扱いを含む計画側の細かな機序は確認できない。")
    print("- 0.5 m 未満の区間と最短距離は、座標を標本間で線形補間した。偏差は該当時刻の経路への最近距離。"
          "区間内の最大値は軌跡標本と最接近時を対象とする。箱の四隅、経路版、最近線分までの距離は `approach_evidence.csv`。\n")

    tilt = terminals["unsafe_tilt"]
    print("### 傾き停止\n")
    table(["走行", "停止 s", "停止位置 x,y m", "姿勢 roll / pitch °", "再計画 s", "30 s 以内の最大移動 m", "その後"],
          [[stamp(tilt),fmt(tilt,"t_s",2),f"({fmt(tilt,'x',2)}, {fmt(tilt,'y',2)})",
            f"{fmt(tilt,'roll_deg',1)} / {fmt(tilt,'pitch_deg',1)}",fmt(tilt,"replan_s",2),
            fmt(tilt,"moved_30s_m",2),"傾きの再発なし、後続の off_path からも復帰し完走"]])
    print("姿勢は追従ノードの停止ログに書かれた値。\n")

    print("### 砂浜 × 条件の安全性\n")
    print("各セルは走行別の値の最小/中央値/最大。箱は衝突箱の投影、検出距離は `clearance.csv` の周期標本。\n")
    safety = (("min_truth_clearance_m","箱までの最短 m",3),("truth_below_radius_s","0.5 m 未満 s",3),
              ("truth_below_radius_entries","0.5 m 未満 区間数",0),("truth_lethal_len_m","真値通行不可 m",3),
              ("debris_len_m","漂着物 m",3),("min_observed_clearance_m","検出障害物までの最短 m",3))
    table(["砂浜","条件",*[h for _,h,_ in safety]],
          ([p,c,*(triple(g,k,d) for k,_,d in safety)] for p,c,g in groups))

    print("## 走行結果\n")
    headers = ["完走","一部","経路なし","止まったまま","転倒","傾き反復終了","pose_timeout"]
    table(["砂浜","条件",*headers,"到達地点数"],
          ([p,c,*(Counter(r["outcome"] for r in g)[k] for k in OUTCOMES),triple(g,"goals_reached",0)] for p,c,g in groups))
    table(["条件",*headers],
          ([c,*(Counter(r["outcome"] for r in g)[k] for k in OUTCOMES)] for c,g in by_condition))

    print("### 経路なしの型と失敗時地図\n")
    classes = ("goal_cell","start_cell","start_steep","corridor","other")
    table(["条件",*classes,"急斜面","overlap の障害物膨張"],
          ([c,*(sum(r["condition"] == c and r["failure"] == k for r in no_path) for k in classes),
            sum(r["condition"] == c and r["steep"] == "True" for r in no_path),
            sum(r["condition"] == c and r["actual_obstacle_halo"] == "True" for r in no_path)] for c in CONDITIONS))
    assert all(r["lethal"]=="True" and r["known"]=="True" and r["truth_lethal"]=="False" for r in no_path)
    assert all((r["steep"]=="True") != (r["actual_obstacle_halo"]=="True") and r["prior_rock"]=="False" for r in no_path)
    assert all(r["centre_halo"]=="False" for r in no_path if r["actual_obstacle_halo"]=="True")
    print("- `08OB88_-0167` は全条件 3/3 回、4 地点到達後に目標 (137, 294) が推定急斜面の膨張で塞がった。"
          "`08OB89_-0847` B r2 は目標 (281, 117) が推定急斜面の膨張で塞がった。計 13 件。")
    print("- `08OB88_-1417` の O・OT 各 3 回は最初の目標 (199, 151)、"
          "`08OB89_-0847` の O・OT 各 3 回は目標 (281, 117) が障害物の膨張で塞がった。"
          "この 12 件の失敗時細格子から既存の膨張規則を再計算すると、同じ細格子の `centre` では目標まで膨張が届かず、"
          "`overlap` では届く。急斜面にも既存の岩にも該当しなかった。"
          "1417 の 6 件中 4 件では、目標が未観測でも膨張で計画上既知になっていた。")
    print("- 全 25 件とも判定は `goal_cell`。評価用真値では該当する目標マスは通行可能だった。"
          "同じ細格子マスクの再判定は障害物膨張の寄与を調べるもので、別条件の走行経路全体を再現するものではない。"
          "走行ごとの失敗地図の時刻と判定根拠は `no_path_evidence.csv`。\n")

    print("### 位置途切れと立ち往生\n")
    pose, stuck = terminals["pose_timeout"], terminals["stuck"]
    table(["走行","結果","終了 s","最後の中心 x,y m","末尾3 s の変位 m","最後の速度指令 v / w"],
          ([stamp(r),r["outcome"],fmt(r,"finish_t_s",2),f"({fmt(r,'x')}, {fmt(r,'y')})",
            fmt(r,"pose_displacement_last_3s_m"),f"{fmt(r,'v_last')} / {fmt(r,'w_last')}"] for r in (pose,stuck)))
    print("- `08OB88_00332` T r2。3 地点を通過後、追従ノードの `pose_timeout` が発動した。"
          "この判定は受信済みの位置を実時間 1 秒超更新できないと発動する。"
          "別の購読者が記録する軌跡は 126.60 s、地図の点群処理も 126.60 s まで残り、終了は 126.65 s。"
          "末尾 3 s の軌跡標本の最大間隔は 0.05 sim s。Gazebo・ブリッジ・追従のログには途切れの発生箇所を示すエラーがなく、"
          "発行・転送・追従側の受信処理のどこで更新が途絶えたかは特定できなかった。")
    print("- `08OB89_-0847` B r1。2 地点を通過し、134.55 s に `off_path`、134.65 s に再計画。"
          "その後の最大変位は約 0.10 m。末尾にも前進約 0.414 m/s と旋回 −1.0 rad/s の指令があり、"
          "最後の 3 s の変位は約 3.5 mm だった。10 sim s の進捗監視で `stuck` に至った。"
          "135.40 s の保存地図では、停止位置の粗格子 (280, 117) は既知・通行不可。"
          "中心判定の検出障害物の膨張が掛かり、急斜面・事前地図の岩・真値通行不可には該当しない。"
          "周囲 5×5 は通行不可 12 マス、検出 12 マスだった。"
          "箱への最短距離は走行全体で約 0.504 m。接触や履帯の滑りを示すログはなく、物理的に動けなかった原因は特定できない。\n")

    print("## 経路からのずれと走行時間\n")
    print("以下も最小/中央値/最大。曲率は最大偏差に対応する経路頂点の Menger 曲率。"
          "定義できない 1 回は除外し、集計件数を表示した。停止後の列は `off_path` と `unsafe_tilt` の両方を含む。"
          "走行時間は終了までで、完走できなかった走行を含む。\n")
    tracking = (("deviation_max_m","最大偏差 m",3),("deviation_p95_m","偏差95% m",3),
                ("deviation_max_curvature_inv_m","最大偏差位置の曲率 1/m",4),
                ("ev_off_path","off_path",0),("ev_unsafe_tilt","unsafe_tilt",0),
                ("stops_replanned_30s","30 s 内に再計画",0),
                ("stops_replanned_and_moved_30s","再計画後 30 s 内に 1 m 超移動",0),("elapsed_s","走行 sim s",1))
    table(["砂浜","条件",*[h for _,h,_ in tracking]],
          ([p,c,*(triple(g,k,d) for k,_,d in tracking)] for p,c,g in groups))
    table(["条件","off_path 計","unsafe_tilt 計","30 s 内に再計画 計","再計画して 1 m 超移動 計"],
          ([c,*(count(g,k) for k in ("ev_off_path","ev_unsafe_tilt","stops_replanned_30s",
                                      "stops_replanned_and_moved_30s"))] for c,g in by_condition))
    print("各停止の時刻と回復を `common_eval/runs.csv` の `stops_detail` に、全走行の位置・時刻を偏差欄に収録。\n")

    print("## 指示書の基準に沿った判断\n")
    print("- **overlap の到達性への影響が明確だったのは 1417 と 0847。** 1417 は B・T とも完走 3/3、O・OT とも経路なし 3/3。"
          "0847 は T の完走 3/3 に対し OT は経路なし 3/3。0847 の B 対 O は B の完走が 1/3 のため、同じ明瞭さでの判定はしない。"
          "0167 は全条件とも同じ第5目標で経路なし 3/3。")
    print("- O・OT の実測された箱までの最短距離は、各砂浜で B・T より大きい範囲だった。"
          "1417 と 0847 は一部の条件が手前で終了したため、通った区間の差も含む。"
          "全条件が完走した 0205 でも O・OT の最短距離は大きかった。"
          "0.5 m 未満の発生はそれぞれ 1 回のため、3 回ずつの安全性の発生回数に明瞭な差があるとは判断しない。")
    print("- **corner_slow では 0205 の B と T で off_path の発生回数が分かれた。** 全回完走の中で、B は発生あり 3/3、T は 0/3。"
          "0167 の O と OT も、同じ目標で終了するまでに O は発生あり 3/3、OT は 0/3。"
          "00332 の O と OT はともに全回完走し、O は発生あり 3/3、OT は 0/3。"
          "1417 の T は 3 回とも off_path があり、最大偏差 0.977 m の回もあった。"
          "追従改善の傾向は場所によって異なり、完走率全体の差や一律の安全性向上は結論づけない。")
    print("- 条件間の完走や安全性は砂浜ごとの 3 回ずつを基に評価した。"
          "停止や経路なしで終了した走行を含む偏差、箱距離、走行時間の全体集約は、同一区間の比較と区別する。\n")

    print("## 実行・再集計・限界\n")
    print("- 実行時コミット `eb00319851b85a0d6b49e35aed8c4ecdb0c1f65f`、作業ブランチ `claude/044-eval`。"
          "2026-11-21 14:13 から 2026-11-22 03:47 JST。60 回のプロセス終了コードはすべて 0。再走行なし。"
          "結果のコミットは研究 PC で作り、Mac から push。")
    print("- 事前・事後の全テストは同じコミットの追跡ファイルのみを一時展開し、研究 PC の同じ venv で実施した。"
          "事前・事後とも 38/38 本合格。出力全文は `tests/` と `tests_after/`。")
    print("- `experiments.eval_runs` の元出力は `common_eval/`、標準出力は `common_eval_log.txt`。"
          "元のボード CSV では `pose_timeout` の専用列がないため、走行別 `outcome` から表に明示した。"
          "比較は走行時のコミットを使用した。")
    print("- 処理はロボット中心の位置と経路の記録に基づく。物理接触、姿勢トピック途切れの発生箇所、立ち往生の物理原因は未確定。"
          "周期地図は末尾の3枚が残る仕様で、全経路の引き渡し時地図は未保存。"
          "容量の大きい生データは研究 PC に保存し、パスと SHA-256 は `not_committed.txt`。\n")
    print("```bash\ncd /home/kotaro/thesis_Bunker_rtf/conference\n"
          "r=results/eval_044\n"
          "~/.venvs/thesis-python/bin/python -m experiments.eval_runs \"$r/runs\" --experiment 044 --out \"$r/common_eval\"\n"
          "PYTHONPATH=. ~/.venvs/thesis-python/bin/python \"$r/audit044.py\"\n"
          "~/.venvs/thesis-python/bin/python \"$r/report044.py\" > \"$r/REPORT_ja.md\"\n```")


if __name__ == "__main__":
    main()
