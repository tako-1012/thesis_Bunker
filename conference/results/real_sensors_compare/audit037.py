"""Reproduce the task 037 report using only retained run records."""
import json
import re
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation, label

from experiments import eval_035_report as audit
from tapp.collision import segment_cells
from tapp.config import RESOLUTION

ROOT = Path(__file__).resolve().parent
D = RESOLUTION
RUNS = ROOT / "runs"


def raw(folder):
    return next((folder / "physical_1/raw").iterdir())


def sensor_cells(folder):
    records = json.loads((raw(folder) / "pointcloud_map.npz.sensors.json").read_text())
    return {tuple(r["fine_cell"]): r for r in records["first_detections"]}


def camera_comparison():
    rows = []
    for beach in sorted(RUNS.iterdir()):
        lidar = [set(sensor_cells(beach / f"L_r{rep}")) for rep in (1, 2, 3)]
        for rep in (1, 2, 3):
            records = sensor_cells(beach / f"LC_r{rep}")
            candidates = {c for c, r in records.items()
                          if r["triggering_sensor"].startswith("camera")
                          and r["supporting_returns"].get("lidar", 0) == 0}
            hits = [len(candidates & cells) for cells in lidar]
            rows.append([beach.name, rep, len(candidates), *hits,
                         len(candidates & set.union(*lidar)), len(candidates & set.intersection(*lidar)),
                         len(candidates - set.union(*lidar)), "不明"])
    return pd.DataFrame(rows, columns=["砂浜", "LC回", "(i) マス数", "L1で登録", "L2で登録", "L3で登録",
                                        "Lいずれか", "L全回", "L全回なし", "(ii) マス数"])


def segment_point(a, b, points):
    direction = b - a
    fraction = np.clip(np.sum((points - a) * direction, axis=-1)
                       / max(direction @ direction, 1e-15), 0, 1)
    return np.linalg.norm(points - a - fraction[..., None] * direction, axis=-1)


def clearance(path, mask):
    centres = np.argwhere(mask) * D
    corners = centres[:, None, :] + D / 2 * np.array(list(product((-1, 1), repeat=2)))
    best = (float("inf"), "", False)
    for a, b in zip(path[:-1], path[1:]):
        cells = segment_cells(a / D, b / D, mask.shape)
        hits = cells[mask[tuple(cells.T)]]
        if len(hits):
            value = 0.
        else:
            value = min(float(segment_point(a, b, corners).min()),
                        *(float(np.linalg.norm(np.maximum(np.abs(centres - p) - D / 2, 0),
                                               axis=1).min()) for p in (a, b)))
        if value < best[0]:
            best = value, f"{a.round(3).tolist()} → {b.round(3).tolist()}", bool(np.all(abs(b-a) > 1e-8))
    return best


def diagonal_intersections(path, mask):
    """Separate diagonal segments touching closed cells from those entering interiors."""
    touches, crosses = set(), set()
    for a, b in zip(path[:-1] / D, path[1:] / D):
        delta = b - a
        if np.any(np.abs(delta) < 1e-9):
            continue
        cells = segment_cells(a, b, mask.shape)
        cells = cells[mask[tuple(cells.T)]]
        for cell in cells:
            touches.add(tuple(map(int, cell)))
            bounds = (np.array([cell - .5, cell + .5]) - a) / delta
            lo = max(0., bounds.min(axis=0).max())
            hi = min(1., bounds.max(axis=0).min())
            if hi - lo > 1e-8:
                crosses.add(tuple(map(int, cell)))
    return sorted(touches), sorted(crosses)


def movement(poses, start, end):
    xy = np.column_stack([np.interp([start, end], poses[:, 0], poses[:, i]) for i in (1, 2)])
    mid = poses[(poses[:, 0] > start) & (poses[:, 0] < end), 1:]
    return np.linalg.norm(np.diff(np.vstack([xy[0], mid, xy[1]]), axis=0), axis=1).sum()


def contact_rows(folder, name, contact):
    record = raw(folder)
    with np.load(record / "evaluation_reference.npz") as z:
        truth = z["truth_rock"] & ~z["prior_rock"]
    poses = np.array([[float(r[k]) for k in ("t", "x", "y")]
                      for r in audit.read_csv_parts(record / "trajectory.csv")])
    revs = [(float(r["t"]), np.array(json.loads(r["path"])))
            for r in audit.read_csv_parts(record / "path_revisions.csv") if len(json.loads(r["path"])) > 1]
    events = audit.safety_events(record)
    snapshots = []
    for f in sorted((folder / "diag_all").glob("periodic_*.npz")):
        with np.load(f) as z:
            snapshots.append((float(z["sim_time"]), f))
    first, last = contact.episode_start, contact.episode_end
    cell = tuple(int(x) for x in re.findall(r"int64\((\d+)\)", contact.cell))
    one = np.zeros_like(truth)
    one[cell] = True
    labels, _ = label(truth, structure=np.ones((3, 3)))
    component = labels == labels[cell]
    nearby = [e for e in events if e["event"] == "off_path" and first - 1 <= e["t"] <= last + 1]
    stop = nearby[-1]["t"] if nearby else None
    active = max((r for r in revs if r[0] <= first), key=lambda r: r[0])
    checks = [("進入時", active)]
    if stop is not None:
        prev = max((r for r in revs if r[0] <= stop), key=lambda r: r[0])
        if prev[0] != active[0]:
            checks.insert(0, ("停止時（旧経路）", prev))
    rows = []
    for context, (stamp, path) in checks:
        distance, edge, diagonal = clearance(path, one)
        all_distance, _, _ = clearance(path, truth)
        touch, cross = diagonal_intersections(path, truth)
        diagonal_hits = f"接触 {len(touch)}、内部 {len(cross)}"
        if touch:
            diagonal_hits += "、" + str(touch)
        coverage = []
        for kind, candidates in (("前", [s for s in snapshots if s[0] <= stamp]),
                                  ("後", [s for s in snapshots if s[0] > stamp])):
            if not candidates:
                continue
            t, f = (max if kind == "前" else min)(candidates)
            with np.load(f) as z:
                fine = audit.bits(z, "fine_obstacle")
                radius = int(round(.5 / float(z["fine_resolution_m"])))
                u, v = np.mgrid[-radius:radius+1, -radius:radius+1]
                disk = np.maximum(2*abs(u)-1, 0)**2 + np.maximum(2*abs(v)-1, 0)**2 <= (2*radius)**2
                padded = binary_dilation(fine, structure=disk)
                covered = padded.reshape(truth.shape[0], 5, truth.shape[1], 5).sum(axis=(1, 3))
                coverage.append(f"{kind} {t:.2f}s: 禁={int(audit.bits(z,'lethal')[cell])}, "
                                f"進入マス {covered[cell]}/25, 同一漂着物 {covered[component].sum()}/{component.sum()*25}")
        pose_t = poses[(poses[:, 0] >= first) & (poses[:, 0] <= last)]
        dx = [min(float(segment_point(a, b, p[1:])) for a, b in zip(path[:-1], path[1:]))
              for p in pose_t]
        stop_distance = "—"
        if stop is not None:
            resumed = next((e["t"] for e in events if e["t"] >= stop and e["event"] == "safety_replanned"), None)
            stop_distance = (f"{stop:.2f}s、再計画まで {movement(poses, stop, resumed):.3f}m、"
                             f"進入まで {movement(poses, stop, first):.3f}m、退出直前まで {movement(poses, stop, last):.3f}m")
        rows.append([name, str(cell), f"{first:.2f}–{last:.2f}", context, stamp, f"{distance:.4f}",
                     f"{all_distance:.4f}", edge, "斜め" if diagonal else "軸方向",
                     diagonal_hits, " / ".join(coverage), f"{max(dx, default=float('nan')):.3f}", stop_distance])
    return rows


def md(frame):
    cells = [[str(v).replace("|", "&#124;") for v in row] for row in frame.itertuples(index=False, name=None)]
    return "\n".join(["| " + " | ".join(map(str, frame.columns)) + " |",
                      "| " + " | ".join(["---"] * len(frame.columns)) + " |",
                      *["| " + " | ".join(row) + " |" for row in cells]])


def triple(values, digits=0):
    a = values.dropna()
    return "—" if a.empty else "/".join(f"{x:.{digits}f}" for x in (a.min(), a.median(), a.max()))


def grouped(runs, fields, keys=("patch", "condition")):
    return pd.DataFrame([list(key) + [len(part)] + [triple(part[col], digits) for col, _, digits in fields]
                         for key, part in runs.groupby(list(keys))],
                        columns=[*keys, "n", *[name for _, name, _ in fields]])


def main():
    runs = pd.read_csv(ROOT / "runs.csv")
    assert len(runs) == 30 and (runs.groupby(["patch", "condition"]).size() == 3).all()
    assert (runs.exit_code == 0).all()
    first = pd.read_csv(ROOT / "first_detections.csv")
    sensor = pd.read_csv(ROOT / "sensor_updates.csv")
    contacts = pd.read_csv(ROOT / "contact_evidence.csv")
    old = pd.read_csv(ROOT / "s1_035_contact_evidence.csv")
    contact_data = []
    for table, base, prefix in ((contacts, RUNS, "037"), (old, ROOT.parent / "eval_035/runs", "035")):
        for c in table[table["mask"] == "debris"].itertuples(index=False):
            condition = c.condition if prefix == "037" else "S1"
            contact_data.extend(contact_rows(base / c.patch / f"{condition}_r{c.rep}",
                                             f"{prefix} {c.patch} {condition} r{c.rep}", c))
    contact_frame = pd.DataFrame(contact_data, columns=["走行", "進入マス", "進入区間 s", "経路", "経路時刻 s",
        "進入マスまで m", "全漂着物への最小 m", "進入マス最近傍の線分端点 m", "方向", "全漂着物と斜め線分の交差",
        "保存地図の通行不可と膨張の重なり", "進入中最大偏差 m", "off_path 後の軌跡長"])
    camera = camera_comparison()
    contact_frame.to_csv(ROOT / "contact_clearance.csv", index=False)
    camera.to_csv(ROOT / "camera_vs_lidar.csv", index=False)
    stops = []
    for r in runs.itertuples(index=False):
        for ev in json.loads(r.stops_detail):
            stops.append(dict(patch=r.patch, condition=r.condition, rep=r.rep, outcome=r.outcome, **ev))
    stop_frame = pd.DataFrame(stops)
    stop_frame.to_csv(ROOT / "stop_followup.csv", index=False)
    print("# 037 実機配置センサーの比較")
    print()
    print("走行は研究 PC の `claude/037-real-sensors`、基点 `e7f86d52c320c055be92e3b98770574feb8e8e07`。"
          "11月18日18:54〜19日03:08（JST）。30回とも実行スクリプトは終了コード0。事前テストは31本すべて合格。"
          "条件・ログ・走行別CSVは本フォルダに保存。成果物は Mac 経由で origin の同名ブランチに送る。集計のコミットIDは持ち帰り報告に記載する。")
    print("\n## 安全性\n")
    print(md(grouped(runs, [("truth_lethal_len_m","通行不可 m",3),("truth_lethal_entries","通行不可進入",0),
      ("debris_len_m","漂着物 m",3),("debris_entries","漂着物進入",0),("ev_off_path","off_path",0),
      ("ev_unsafe_tilt","unsafe_tilt",0),("stops_then_moved","停止後1m超移動",0),
      ("stops_then_stationary","停止後1m以下",0)])))
    hit = runs[runs.debris_entries > 0].iloc[0]
    print(f"\n037では転倒なし。{hit.patch} {hit.condition}{hit.rep} で漂着物マスに{hit.debris_len_m:.3f} m進入。"
          "これは中心軌跡と評価用マスクの重なりであり、物理的な接触は未確認。")
    print("\n### 漂着物マスへの進入（035 S1 を含む）\n")
    print(md(contact_frame))
    print("\n距離は 0.5 m 四方の閉じたマスと経路線分の最短距離。全漂着物への最小距離は経路全体を対象とし、進入マスの距離とは区別する。"
          "地図は経路時刻の前後で保存されたスナップショット。計画時点の地図そのものは取得できない。膨張の重なりは、0.1 m の検出マスを既存規則で 0.5 m 膨らませ、"
          "進入マスと真値上の8近傍連結成分を覆った細格子数。進入時のサンプル最大偏差は各行の経路に対する距離。")
    print("\n偏差は記録された中心位置と経路全体の最近点から再計算した値。停止通知を発した追従器の内部偏差と、ログ上の経路に対する偏差は測定時刻と定義が異なる。")
    print("\n- **037 0847 L2 — 主因は追う側のずれ。** 旧経路から外れて 134.55 s に off_path が記録され、再計画まで 0.042 m 動いた。新経路は進入マスの角から約 9 mm の位置を斜めに通り、余裕の小ささも寄与した。新経路全体では別の真値漂着物3マスの内部を斜めに通る。一方、進入マスそのものを横切る角削りは確認されなかった。")
    print("- **035 S1 — 主因は経路が近すぎたこと。** 進入マスを横切らず、約 5 cm の余裕で斜めに通る経路だった。進入中の最大偏差は約 0.15 m で、近接する経路と追従ずれが重なった。進入の前後1秒に off_path は記録されなかった。中心軌跡の進入長は 0.381 m。")
    print("- 両場面とも保存地図では進入マスを含む漂着物を膨張で覆っており、位置のずれや見落としを主因とする証拠はない。斜めの線分と閉じたマスの交差を基準に、角削りの有無を判定した。")
    print("\n### 停止後の経過\n")
    tilt = stop_frame[stop_frame.kind == "unsafe_tilt"]
    if tilt.empty:
        print(md(pd.DataFrame([["037 L", 0, "該当なし"], ["037 LC", 0, "該当なし"]],
                              columns=["条件", "unsafe_tilt", "停止後の経過"])))
        print("\n035 S1 にも unsafe_tilt の記録はない。037 では傾き停止の反復や上限時間到達は観測されなかった。")
    else:
        print(md(tilt))
    off = stop_frame[stop_frame.kind == "off_path"]
    print(f"\noff_path は {len(off)} 件。30秒以内の再計画は {off.replanned_30s.sum()} 件、"
          f"30秒以内に停止位置から1 m超移動したのは {(off.moved_30s_m > 1).sum()} 件。"
          "各停止の時刻、移動距離と終了状態は `stop_followup.csv`。")
    print("\n## 1. 結果と経路なしの型\n")
    outcomes = runs.assign(completed_n=runs.outcome.eq("completed").astype(int),
                           no_path_n=runs.outcome.eq("no_path").astype(int))
    print(md(grouped(outcomes, [("completed_n","完走",0),("no_path_n","経路なし",0),
                 ("goals_reached","到達地点数",0),("fail_goal_cell","goal_cell計画失敗",0),
                 ("fail_start_cell","start_cell計画失敗",0),("fail_start_steep","start_steep計画失敗",0),
                 ("fail_corridor","corridor計画失敗",0),("fail_other","その他の計画失敗",0)])))
    print("\n完走・経路なしの実数は次表。一部・止まったまま・転倒は、いずれも0回。\n")
    print(md(pd.read_csv(ROOT / "outcome_counts.csv")))
    print("\n## 3. センサー別の初回登録距離\n")
    print(md(grouped(first[first.sensor != "camera_union"], [("detections","登録数",0),
                 ("distance_min_m","走行内最小 m",2),("distance_median_m","走行内中央値 m",2)],
                ("patch","condition","sensor"))))
    print("\n### カメラのみの2つの定義\n")
    print(md(camera))
    print()
    print(md(grouped(camera, [(c, c, 0) for c in camera.columns[2:-1]], ("砂浜",))))
    print("\n(i) カメラが登録を発火させ、登録時にそのマスの保存された支持点履歴に LiDAR が0点の細格子。"
          "Lの列は同じ砂浜の各L走行の初回登録と同じ座標で照合した数。"
          "(ii) LCの走行終了まで LiDAR の点が一度もなかったマス数は判定不能。"
          "保存されたセンサー別情報は初回登録時の支持点と走行全体の集計で、マスごとの全時刻・全センサーの点履歴はない。"
          "L全回で未登録のマスも、LC内でその後 LiDAR が当たったかは分からない。再走行はしていない。")
    print("\n## 4. 地図の誤り（023 と同じ定義）\n")
    print(md(grouped(runs, [("map_fp_cells","誤って通れない",0),("map_fn_cells","見落とし",0),
                             ("map_seen_cells","観測済み",0)])))
    print("\n## 5. 更新時間と捨てた走査\n")
    print(md(grouped(sensor, [("update_s_median","更新中央値 s",3),("update_s_p95","95%値 s",3),
                              ("update_s_max","最大 s",3),("queue_drops_last","捨てた走査",0)],
                     ("patch","condition","sensor"))))
    print("\n各表のスラッシュ区切りは3回の最小/中央値/最大。走行単位の値は `runs.csv`、"
          "`first_detections.csv`、`sensor_updates.csv`。")
    print("\n## 失敗時の地図\n")
    print("経路なしは8回。0167のL・LC各3回は5地点目 (137,294) が急斜面の膨張で塞がった。"
          "1417のL2では (203,229) が急斜面の膨張で塞がった。0847のLC1では (281,117) が通行不可で、"
          "急斜面膨張と周辺の障害物検出が同時に記録された。どの目標マスも真値の評価地図では通行可能。"
          "失敗時刻・現在地・目標とマスクの内訳は `failure_evidence.csv`。実行エラー・中断・再走行は0。")
    print("\n## 判断と限界\n")
    print("完走はL・LCとも11/15。1417はL 2/3対LC 3/3、0847はL 3/3対LC 2/3。"
          "完走数がはっきり分かれた砂浜はなく、カメラ増設による完走や安全性の差は結論づけられない。"
          "カメラが先に登録したマスはあった。箱は実物の漂着物より0.5 m高いため、LiDARで見えやすくなり、"
          "カメラの効果を小さく見積もる可能性がある。検定やエネルギー集計は行っていない。")


if __name__ == "__main__":
    main()
