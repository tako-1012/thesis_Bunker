"""Build the task 039 B comparison from the common evaluation outputs."""
import csv
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median

BASE = Path(__file__).resolve().parent
EVAL = BASE / "common_eval"
RUNS = BASE / "runs"
FACTORS = ("0.3", "1.0")
PATCHES = ("08OB86_-0205", "08OB88_-1417", "08OB88_-0167", "08OB88_00332", "08OB89_-0847")
KEYS = [(patch, factor, str(rep)) for patch in PATCHES for factor in FACTORS for rep in (1, 2, 3)]
OUTCOMES = ("completed", "partial", "no_path", "stuck", "rollover", "unsafe_tilt_repeat")


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def tri(values, digits, scale=1):
    return "/".join(f"{x * scale:.{digits}f}" for x in (min(values), median(values), max(values)))


def numbers(group, field):
    return [Decimal(row[field]) for row in group]


def triple(group, field, digits, scale=1):
    return tri(numbers(group, field), digits, scale)


def table(header, data):
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join(["---"] * len(header)) + " |")
    for row in data:
        print("| " + " | ".join(map(str, row)) + " |")
    print()


def main():
    records = rows(EVAL / "runs.csv")
    common = {(r["patch"], r["condition"], r["rep"]): r for r in records}
    old = {(r["patch"], r["factor"], r["rep"]): r for r in rows(BASE / "runs.csv")}
    assert len(records) == len(common) == len(old) == 30
    assert set(common) == set(old) == set(KEYS)
    decisions = {}
    for key in KEYS:
        patch, factor, rep = key
        r = common[key]
        assert Decimal(r["target_rtf"]) == Decimal(factor)
        assert r["outcome"] in OUTCOMES and r["exit_code"] == "0"
        observed = Decimal(r["sim_to_wall_ratio"])
        target = Decimal(factor)
        drops = int(r["queue_drops"])
        reference = int(common[patch, "0.3", rep]["queue_drops"])
        errors = int(r["map_failed_updates"])
        share = Decimal(r["update_over_period_share"])
        hz = Decimal(r["cmd_vel_hz_sim"])
        age = Decimal(r["cloud_age_sim_max_s"])
        assert all(Decimal(r[new]) == Decimal(old[key][before]) for new, before in (
            ("sim_to_wall_ratio", "measured_rtf"), ("queue_drops", "queue_drops"),
            ("cmd_vel_hz_sim", "cmd_vel_hz_sim_aligned"), ("update_over_period_share", "over_period_share"),
            ("cloud_age_sim_max_s", "cloud_age_max_sim_s"),
        ))
        assert not old[key].get("measurement_error")
        ratio_ok = abs(observed - target) <= target / 100
        valid = ratio_ok and errors == 0
        is_fast = factor == "1.0"
        drops_ok = drops <= reference
        period_ok = share <= Decimal(".01")
        hz_ok = hz >= 19
        age_ok = age < 1
        decisions[key] = dict(patch=patch, factor=factor, rep=rep, measured_rtf=observed,
            ratio_ok=ratio_ok, map_errors=errors, valid=valid, queue_drops=drops, paired_03_drops=reference,
            drops_ok=drops_ok if is_fast else "", over_period_share=share, period_ok=period_ok,
            cmd_vel_hz_sim=hz, cmd_vel_ok=hz_ok, cloud_age_sim_max_s=age, age_ok=age_ok,
            keeps_up=valid and drops_ok and period_ok and hz_ok and age_ok if is_fast else "")
    with (BASE / "criteria.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(next(iter(decisions.values()))), lineterminator="\n")
        writer.writeheader()
        writer.writerows(decisions.values())

    groups = [(patch, factor, [common[patch, factor, str(i)] for i in (1, 2, 3)])
              for patch in PATCHES for factor in FACTORS]
    totals = [(factor, [r for r in records if r["condition"] == factor]) for factor in FACTORS]
    print("# 039 段階 B　研究 PC での 0.3 倍と 1.0 倍の比較\n")
    print("**0.3 倍を継続する。** 1.0 倍設定は 15 回とも実測が目標の ±1% に入らず、切り替え条件を満たさなかった。\n")
    print("## 安全性\n")
    print("30 回とも転倒、真値通行不可マス・漂着物マスへの進入、箱までの中心距離 0.5 m 未満、"
          "`unsafe_tilt` とその反復終了は 0 件だった。表の距離は車体中心の XY 軌跡を使う。"
          "車体と箱の物理接触はこの集計では判定できない。\n")
    table(["目標倍率", "実行数", "転倒", "通行不可 m 計", "漂着物 m 計", "箱までの最短距離 m",
           "0.5 m 未満 s 計", "unsafe_tilt", "傾き反復終了", "off_path", "30 sim s 以内に再計画し 1 m 超移動"],
          ([factor, len(g), sum(r["rolled_over"] == "True" for r in g),
            sum(numbers(g, "truth_lethal_len_m")), sum(numbers(g, "debris_len_m")),
            triple(g, "min_truth_clearance_m", 4), sum(numbers(g, "truth_below_radius_s")),
            sum(numbers(g, "ev_unsafe_tilt")), sum(numbers(g, "ev_unsafe_tilt_repeat")),
            sum(numbers(g, "ev_off_path")), sum(numbers(g, "stops_replanned_and_moved_30s"))] for factor, g in totals))
    print("距離欄は走行ごとの最短距離の最小/中央値/最大。砂浜ごとの回数と距離は次表。\n")
    table(["砂浜", "目標倍率", "通行不可 m 計", "漂着物 m 計", "箱までの最短距離 m",
           "0.5 m 未満の区間数", "unsafe_tilt / 反復終了", "off_path 計"],
          ([patch, factor, sum(numbers(g, "truth_lethal_len_m")), sum(numbers(g, "debris_len_m")),
            triple(g, "min_truth_clearance_m", 4), sum(numbers(g, "truth_below_radius_entries")),
            f'{sum(numbers(g, "ev_unsafe_tilt"))} / {sum(numbers(g, "ev_unsafe_tilt_repeat"))}',
            sum(numbers(g, "ev_off_path"))] for patch, factor, g in groups))

    print("## 倍率と処理の判定\n")
    print("有効は実測倍率が目標の ±1% 以内で地図更新の誤りが 0。"
          "1.0 倍の処理判定にはさらに、同じ砂浜・反復番号の 0.3 倍よりキュー落ちが増えない、"
          "周期超過が 1% 以下、`/cmd_vel` が 19 Hz 以上、点群の古さが最大 1.0 sim s 未満を使った。\n")
    print("周期は 0.1 sim s を各走行の**実測**倍率で実時間に換算し、ミッション区間の成功更新を数えた。"
          "点群の古さは 1 実秒ごとのプローブ標本の最大であり、3 センサーの有効な最新点群のうち最も古いものを測る。"
          "速度指令は共通ツールの定義に従い、分母の区間外となる最初の標本のカウントを除いた。\n")
    table(["目標倍率", "有効", "実測倍率", "地図更新エラー 計", "キュー落ち 計", "周期超過 % 最大",
           "速度指令 sim Hz", "点群の古さ sim s", "追いついた回"],
          ([factor, f"{sum(d['valid'] for d in decisions.values() if d['factor'] == factor)}/15",
            triple(g, "sim_to_wall_ratio", 6), sum(numbers(g, "map_failed_updates")), sum(numbers(g, "queue_drops")),
            f'{max(numbers(g, "update_over_period_share")) * 100:.4f}',
            triple(g, "cmd_vel_hz_sim", 3), triple(g, "cloud_age_sim_max_s", 3),
            f"{sum(d['keeps_up'] is True for d in decisions.values())}/15" if factor == "1.0" else "—"]
           for factor, g in totals))
    print("1.0 倍設定では各項目単独で、キュー落ちが増えなかった回は "
          f"{sum(d['drops_ok'] is True for d in decisions.values())}/15、"
          "周期超過割合・速度指令頻度・点群の古さは各 15/15 回だった。"
          "周期超過・古さの結果は、実測約 0.6 倍での計測である。\n")
    table(["砂浜", "目標倍率", "有効/実行", "実測倍率", "キュー落ち", "周期超過 %", "速度指令 sim Hz", "点群の古さ sim s"],
          ([patch, factor, f"{sum(decisions[patch, factor, r['rep']]['valid'] for r in g)}/3",
            triple(g, "sim_to_wall_ratio", 6), triple(g, "queue_drops", 0),
            triple(g, "update_over_period_share", 4, 100), triple(g, "cmd_vel_hz_sim", 3),
            triple(g, "cloud_age_sim_max_s", 3)] for patch, factor, g in groups))
    print("各欄は 3 回の最小/中央値/最大。走行別の判定は `stage_b/criteria.csv`。\n")

    print("### センサー別の地図更新時間\n")
    print("成功した更新の実時間。各セルは、走行ごとに求めた 95% 値を 3 回で集計した最小/中央値/最大（ms）。"
          "同じ定義の中央値・最大値・件数は `stage_b/common_eval/summary.csv` を参照。\n")
    table(["砂浜", "目標倍率", "LiDAR", "camera1", "camera2"],
          ([patch, factor, *(triple(g, f"{sensor}_map_update_s_p95", 2, 1000)
                              for sensor in ("lidar", "camera1", "camera2"))] for patch, factor, g in groups))

    print("## 走行結果\n")
    print("1.0 倍設定の結果は、目標未達の走行で実際に起きたこととして示す。\n")
    table(["砂浜", "目標倍率", "完走", "一部", "経路なし", "止まったまま", "転倒", "傾き反復終了", "到達地点数"],
          ([patch, factor, *(Counter(r["outcome"] for r in g)[o] for o in OUTCOMES),
            triple(g, "goals_reached", 0)] for patch, factor, g in groups))
    table(["目標倍率", "完走", "一部", "経路なし", "止まったまま", "転倒", "傾き反復終了"],
          ([factor, *(Counter(r["outcome"] for r in g)[o] for o in OUTCOMES)] for factor, g in totals))
    print("### 完走できなかった走行\n")
    table(["砂浜", "目標倍率", "回", "結果", "到達地点", "ノードの終了判定", "末尾の静止 sim s"],
          ([r["patch"], r["condition"], r["rep"], r["outcome"], r["goals_reached"],
            r["no_path_type"] or r["recorded_status"], f'{Decimal(r["stationary_tail_s"]):.2f}']
           for key in KEYS if (r := common[key])["outcome"] != "completed"))
    print("- `08OB88_-0167` の経路なし 6 回は、5 地点目のマス (137, 294) を推定急斜面の 0.5 m 膨張が塞いだ。"
          "`08OB89_-0847` の 1.0 倍設定 3 回目も、目標 (281, 117) が推定急斜面の膨張に入っていた。"
          "各失敗時の保存地図ではいずれも通行不可で、評価用の真値地図では通行可。")
    print("- 0.3 倍の `08OB86_-0205` 2 回目と `08OB89_-0847` 1 回目は追従側が `stuck` として終了。"
          "両回とも先行する `off_path` の後には再計画して 1 m 超移動した。最後に動けなくなった物理的な原因は特定できなかった。\n")

    print("## 判断と限界\n")
    print("1.0 倍設定は 0.585〜0.613 倍で、15/15 回有効かつ追いつくという最初の条件を満たさなかった。"
          "完走数は目標設定別で 10/15 対 11/15 だったが、1.0 倍で同じ結果を得られるかは未検証。"
          "今回の結果から、描画・物理・通信など個々の処理が実測倍率に与えた寄与は切り分けられない。\n")

    print("## 実行と再集計\n")
    print("- 研究 PCの `claude/039-rtf-compare`、実験コミット `fa86d83aa72ad2eb086e8c1f448aa063971cfa9d`。"
          "2026-11-21 01:24〜07:20 JST。全 30 回は終了コード 0。事前テストは 36/36 本合格。")
    print("- ROS ドメイン 64、ソフトウェア描画、fine、non_obstacle、v2、LiDAR と深度カメラ 2 台、診断有効。"
          "最初の起動確認では非 root の受動プローブが受信できず中断した。"
          "記録を別に残し、ROS ノードと同じコンテナ UID で受動プローブを開始してから本計測を実施した。"
          "本計測 30 回のやり直しは行っていない。")
    print(f"- 共通集計は `{(BASE / 'common_eval_commit.txt').read_text().strip()}` の `experiments.eval_runs` を使用。"
          "倍率・キュー落ち・周期超過・古さ・区間を揃えた速度指令頻度は起動スクリプトの集計と 30 回とも一致した。")
    print("- 共通集計の走行別 CSV、砂浜別集計、定義、実行ログは `stage_b/`。"
          "毎回の周期診断地図の全履歴は保存していないため、全引き渡しに対する周期地図の監査は対象外。"
          "生データは研究 PC にあり、相対パスと SHA-256 は `stage_b/not_committed.txt`。\n")
    print("```bash\ncd /home/kotaro/thesis_Bunker_rtf/conference\n"
          "r=results/rtf_compare/stage_b\n"
          "~/.venvs/thesis-python/bin/python -m experiments.eval_runs \"$r/runs\" --experiment 039 --out \"$r/common_eval\"\n"
          "~/.venvs/thesis-python/bin/python \"$r/report_b.py\" > results/rtf_compare/REPORT_B_ja.md\n```")


if __name__ == "__main__":
    main()
