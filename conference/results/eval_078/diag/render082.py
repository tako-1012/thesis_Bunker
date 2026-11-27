"""Render the diagnostic report using the saved 082 tables."""

from collections import Counter
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SELECTED = (("08OB88_-1417", "d160_s0"), ("08OB88_-1417", "d0_s0"), ("08OB86_-0205", "d40_s1"))

NAMES = {
    "baseline": "正解姿勢 × 077 の取り付け",
    "no_mount": "取り付け変換を省略",
    "mount_z_-0.35m": "取り付け高さ −0.35 m",
    "mount_z_+0.35m": "取り付け高さ +0.35 m",
    "swap_xy": "LiDAR の x・y を交換",
    "flip_x": "LiDAR の x を反転",
    "flip_y": "LiDAR の y を反転",
    "flip_z": "LiDAR の z を反転",
    "flip_xyz": "LiDAR の 3 軸を反転",
    "lidar_yaw_-90deg": "LiDAR を Z 軸まわりに −90°",
    "lidar_yaw_+90deg": "LiDAR を Z 軸まわりに +90°",
    "lidar_yaw_+180deg": "LiDAR を Z 軸まわりに 180°",
    "truth_time_-0.5s": "真値を早い方へ 0.5 秒",
    "truth_time_-0.1s": "真値を早い方へ 0.1 秒",
    "truth_time_+0.1s": "真値を遅い方へ 0.1 秒",
    "truth_time_+0.5s": "真値を遅い方へ 0.5 秒",
    "truth_misread_as_wxyz": "真値の xyzw を wxyz として解釈",
}


def rows(name):
    with (ROOT/name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def table(headers, values):
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in values:
        print("| " + " | ".join(map(str, row)) + " |")
    print()


def number(row, field, places=3, scale=1.):
    value = row[field]
    return f"{float(value)*scale:.{places}f}" if value else "—"


def pair(row):
    return f"{number(row, 'median_m', 2, 100)}/{number(row, 'p90_m', 2, 100)}"


def main():
    frames = rows("frame_hypotheses.csv")
    poses = rows("truth_pose_comparison.csv")
    historical = rows("078_timing.csv")
    compare = rows("082_comparison.csv")
    process = rows("082_process_usage_summary.csv")
    alignment = rows("first_replay_alignments.csv")
    stamps = rows("lidar_stamp_comparison.csv")
    assert len(frames) == 51 and len(poses) == 3 and len(historical) == 24 and len(stamps) == 26
    assert len(rows("frame_baseline_scans.csv")) == 60
    assert [r["status"] for r in compare] == ["completed", "no_path"]
    assert all(r["oldest_sensor"] == "lidar" and float(r["age_lidar_s"]) > 1 for r in historical)
    assert all(r["position_max_m"] == "0.0" for r in poses)
    assert all(r["ambiguous_observer_rows"] == "0" and r["observer_rows_without_recorded_header"] == "0" for r in poses)
    variants = {(r["beach"], r["trial"], r["hypothesis"]): r for r in frames}
    for beach, run in SELECTED:
        group = [r for r in frames if (r["beach"], r["trial"]) == (beach, run)]
        assert {row["hypothesis"] for row in group} == set(NAMES)
        for key in ("median_m", "p90_m"):
            assert min(group, key=lambda r: float(r[key]))["hypothesis"] == "baseline"

    print("""# 082　078 の座標照合と LiDAR 点群の鮮度

- 正解姿勢と 077 が読む取り付け位置で LiDAR を変換すると、3 回すべてで最近傍距離の
  中央値は 3.9～4.3 cm、90% 値は 6.0～6.1 cm。指定した取り違えはいずれも改善しなかった。
- 同条件の確認走行は、センサー記録なしが完走、ありは LiDAR の古さで 8.752 sim 秒後に終了。
  記録ありでも実測倍率はほぼ 1.0 だった。記録を有効にしたときの LiDAR の途切れを再現した。

## A　LiDAR・正解姿勢・地図の座標

砂浜 2 か所、密度 0・40・160 個/ha から、078 の初回を含む次の 3 走行を選んだ。
±0.5 秒でも正解姿勢の時刻範囲に収まる区間から各 20 スキャンを等間隔で採り、
076 と同じ距離フィルターを通る有限な全点を使った。
077 が各 manifest から取得した取り付け位置は 3 回ともモデル原点基準で
§(-0.24, 0, 1.40) m§、取り付け回転は 0°。
正解姿勢の並進を線形補間、回転を SLERP で補間し、正解姿勢と取り付けの積で
世界座標へ移した。各点の §reference_cloud.npz§ への最近傍距離をスキャン全体で集計した。
[各スキャン](frame_baseline_scans.csv)
""".replace("§", chr(96)))
    table(("砂浜・走行", "スキャン数", "照合点数", "中央値/90%値 cm"),
          ((f"{p} {run}", variants[p, run, "baseline"]["scans"], variants[p, run, "baseline"]["points"],
            pair(variants[p, run, "baseline"])) for p, run in SELECTED))
    print("それぞれ一つの条件だけを変えた。数値は **中央値／90% 値（cm）**。\n")
    table(("試した変換", "1417・160・s0", "1417・0・s0", "0205・40・s1"),
          ((label, *(pair(variants[p, run, hypothesis]) for p, run in SELECTED))
           for hypothesis, label in NAMES.items()))
    print("[取り違えの全桁と標本数](frame_hypotheses.csv)\n")
    print("""### 正解位置どうしの照合

§pose_trace/observer_pose.csv§ は姿勢の値に代わり受信側のシミュレーション時刻と
送信元のヘッダー時刻を持つ。受信時刻で観測側の §trajectory.csv§ の座標に結び、
同じヘッダー時刻のセンサー記録との XYZ 差と回転差を測った。
照合対象は走行中に観測側が記録した行。姿勢差は四元数の相対回転で比較した。
""".replace("§", chr(96)))
    table(("砂浜・走行", "センサー記録の真値件数", "観測軌跡と照合できた件数", "位置差最大 m", "回転差最大 °"),
          ((f"{r['beach']} {r['trial']}", r["recorded_truth"], r["exact_header_join_rows"], r["position_max_m"],
            f"{float(r['orientation_max_deg']):.2e}") for r in poses))
    print("[真値の照合と外部パラメータの取得元](truth_pose_comparison.csv)\n")
    map_only = next(r for r in alignment if r["method"] == "map_only")
    print(f"""### 30 m の誤差が出た経過

初回保存済みの 076 出力では、地図照合の最初の位置誤差は
**{float(map_only['first_error_m']):.3f} m**。以降、{map_only['attempted']} 回の照合で
{map_only['accepted']} 回採用、{map_only['not_converged']} 回が未収束だった。
最後の採用は記録の LiDAR 先頭から {float(map_only['last_accept_s']):.1f} sim 秒で、
その位置はすでに正解から {float(map_only['last_accept_error_m']):.2f} m 離れていた。
その位置のまま最終フレームまで進み、最終誤差は {float(map_only['final_error_m']):.2f} m になった。
正解姿勢を使った投影では座標が cm 単位で整合し、今回試した固定的な座標の取り違えを支持する結果は得られなかった。
照合が最初に外れた理由や、誤った位置で収束した原因は今回の比較だけでは特定できない。
[初回再生の照合内訳](first_replay_alignments.csv)

## B　078 の全 24 回

全ての終了状態が §no_path§ で、追従ログは §lidar_unavailable_or_stale§。
終了時の LiDAR、カメラ 1・2 の古さは、観測されたミッション終了シミュレーション時刻から
最後に地図が採用した各点群のタイムスタンプを引いた値。
センサー容量は §sensors/metadata.json§ とチャンクの合計で、参照地図は別。
""".replace("§", chr(96)))

    for density in (0, 10, 40, 160):
        group = [r for r in historical if int(r["density_per_ha"]) == density]
        print(f"### {density} 個/ha（LiDAR の古さによる終了 {len(group)}/6）\n")
        table(("砂浜", "seed", "停止まで sim 秒", "実測倍率", "LiDAR 古さ 秒", "カメラ1 古さ 秒",
               "カメラ2 古さ 秒", "記録 MB", "LiDAR/IMU/正解位置"),
              ((r["beach"], r["seed"], number(r,"duration_sim_s"), number(r,"measured_rtf", 4),
                number(r,"age_lidar_s"), number(r,"age_camera1_s"), number(r,"age_camera2_s"),
                number(r,"sensor_bytes", 2, 1e-6),
                "/".join(r[k] for k in ("saved_lidar", "saved_imu", "saved_ground_truth"))) for r in group))
    print("[全走行の時刻・受信数・容量・地図更新時間](078_timing.csv)\n")
    cap = [r for r in historical if r["record_state"] == "duration_limit"]
    by_trial = {(r["beach"], r["trial"]): r for r in stamps if r["experiment"] == "078"}
    if cap:
        print("次の走行は 120 秒の記録期間を使い切った後に停止した。"
              "記録の確定後も記録ノードの購読は走行終了まで残る。\n")
        table(("砂浜", "密度・seed", "記録期間 sim 秒", "最後の保存 LiDAR から停止まで sim 秒"),
              ((r["beach"], f"{r['density_per_ha']}・{r['seed']}", number(r,"record_sim_s"),
                number(by_trial[r["beach"], f"d{r['density_per_ha']}_s{r['seed']}"], "recorder_age_at_stop_s"))
               for r in cap))
        print("これらの停止時点では、センサーの記録ファイルはすでに確定していた。\n")

    print("""### 082 の確認走行 2 回

08OB88_-1417、目印 0 個/ha、シード 0。順番は記録なし、記録あり。
078 と同一の Docker イメージ、同一の実行コード・共通引数・ROS ドメインで 1 回ずつ走行した。
""")
    table(("記録", "終了", "終了まで sim 秒", "実測倍率", "LiDAR 古さ 秒", "カメラ1 古さ 秒", "カメラ2 古さ 秒",
           "記録 MB", "LiDAR 枚数"),
          ((r["mode"], r["status"], number(r,"duration_sim_s"), number(r,"measured_rtf",4),
            number(r,"age_lidar_s"), number(r,"age_camera1_s"), number(r,"age_camera2_s"),
            number(r,"sensor_bytes",2,1e-6), r["saved_lidar"] or "—") for r in compare))
    print("""記録ありではカメラの点群が新しいまま、LiDAR が 1.0 秒の監視条件を超えた。
シミュレーション全体の倍率は 1.0 に近く、倍率だけではこの停止を見分けられなかった。
[比較の詳細](082_comparison.csv) · [引数とイメージの照合](conditions_check_log.txt)
""")
    on = next(r for r in stamps if r["experiment"] == "082" and r["trial"] == "on")
    last_deltas = Counter(float(r["recorder_last_minus_mapper_s"]) for r in stamps if r["experiment"] == "078")
    print(f"""### 点群の時刻と記録プロセスの負荷

同じ終了時刻で比較すると、記録ありの確認走行では記録側最後の LiDAR が
**{float(on['recorder_last_at_stop_s']):.3f} sim 秒**、地図側最後の LiDAR が
**{float(on['mapper_last_s']):.3f} sim 秒**だった。
078 全回における時刻差（記録側 − 地図側）の内訳は
{'、'.join(f'{v:+g} 秒が {n} 回' for v, n in sorted(last_deltas.items()))}。
確認走行の終了時刻は 14.252 sim 秒で、記録側には 0.052 秒前の LiDAR が届いていた。
その点群は終了時点の地図には採用されていなかった。配信・受信・地図更新のどの段階に
時間がかかったかは、この時刻の差だけから分離できない。
[LiDAR の記録側と地図側の時刻](lidar_stamp_comparison.csv)

078 の §process_4.txt§ は全 24 回で空だった。既存の pose_trace CPU ログは
ホスト全体の使用率と負荷で、記録プロセス単体の数値はそこから取り出せない。
082 は両走行とも低優先度で約 1 秒ごとに §/proc§ をサンプリングした。
""".replace("§", chr(96)))
    recorder, = [r for r in process if r["mode"]=="on" and r["process"]=="recorder"]
    table(("記録プロセス（082 の on）", "測定値"),
          (("観測サンプル数", recorder["samples"]),
           ("CPU 中央値／95%値／最大（1コア=100%）",
            "／".join(number(recorder, f, 2) for f in
                      ("cpu_median_pct_one_core","cpu_p95_pct_one_core","cpu_peak_pct_one_core")) + "%"),
           ("最終観測時の CPU 累積秒", recorder["cpu_total_s_last"]),
           ("観測した RSS 最大", f"{float(recorder['rss_peak_bytes'])/1e6:.2f} MB")))
    print("""確認走行では、計測した約 1 秒間隔の値に記録プロセスによる 1 コアの飽和は現れなかった。
記録を有効にすると LiDAR の購読と圧縮保存が増える。今回の測定では短いスケジューリングの遅れ、
DDS／ブリッジでの配信、Gazebo のセンサー発行のどこで途切れたかは分離できない。
比較は各 1 回で、記録ありと同時に再現した点群の途切れから CPU 負荷単独の原因までは立証できない。
[プロセス別集計](082_process_usage_summary.csv)

## 実行条件・手順と保存

研究 PC §hayashi§ の §~/thesis_Bunker_rtf§、ブランチ §claude/082-frame-check§。
実行時の起点は §cc9b42f477555470dcba7adbb44fd0b46aa0a678§。
11 月 28 日 01:11:12～01:17:10 JST に指定した 2 回を実行した。
テストは同じコミットの独立した作業ツリーで 64/64 モジュール合格。
座標集計・検証は §nice -n 19§、2 スレッド／ジョブ以内。
[テスト一覧](tests/summary.txt) · [比較走行ログ](compare_log.txt) · [生データ保管場所とハッシュ](not_committed.txt)

§§§bash
cd ~/thesis_Bunker_rtf/conference
tmux new-session -s compare-082 'bash results/eval_078/diag/run082.sh > results/eval_078/diag/compare_log.txt 2>&1'
tmux new-session -s analysis-082 'nice -n 19 bash results/eval_078/diag/verify082.sh > results/eval_078/diag/verify_session_log.txt 2>&1'
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. nice -n 19 .venv-localization/bin/python results/eval_078/diag/check_stream082.py
.venv-localization/bin/python results/eval_078/diag/render082.py
§§§

§run082.sh§ の共通環境は §THESIS_RENDER=gpu THESIS_FINE_PROTOCOL=rtf_check
THESIS_ONLY_PATCH=08OB88_-1417 THESIS_ROS_DOMAIN_ID=78 THESIS_STALE_TIMEOUT_S=1.0§。
両方で §run_lidar_checks.sh§ に次の引数を渡し、記録ありだけ末尾に
§--record-sensors --record-sensors-seconds 120§ を付けた。

§§§text
--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
--sensors lidar_real+depth2 --diagnostics --terrain-source prior --obstacle-clearance distance
--save-plan-maps --pose-trace --real-time-factor 1.0 --landmarks 0 --landmark-seed 0
§§§
""".replace("§", chr(96)))


if __name__ == "__main__":
    main()
