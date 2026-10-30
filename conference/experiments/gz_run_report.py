"""Compare a recorded physical run with map predictions and the fixed kinematic model."""

import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapp.config import RESOLUTION
from tapp.mission import load_map
from tapp.mapfile import load_map_file
from tapp.collision import path_lethal_cells
from tapp.metrics import evaluate, resample
from tapp.pure_pursuit import prepare_path, path_distance
from tapp.robot_sim import simulate
from scipy.ndimage import map_coordinates


def analyze_run(folder, output=None):
    folder = Path(folder)
    output = Path(output) if output else folder / "report"
    output.mkdir(parents=True, exist_ok=True)
    mission = json.loads((folder / "mission.json").read_text())
    sc = (
        load_map_file(mission["map_file"])
        if mission.get("map_file")
        else load_map(mission["map_id"])
    )
    with (folder / "trajectory.csv").open() as stream:
        records = list(csv.DictReader(stream))
    if not records:
        raise ValueError("trajectory.csv is empty")
    data = {
        k: np.array([float(row[k]) for row in records])
        for k in ("t", "x", "y", "z", "roll", "pitch", "yaw", "v", "w")
    }
    if (
        not all(np.isfinite(v).all() for v in data.values())
        or (np.diff(data["t"]) < 0).any()
    ):
        raise ValueError("invalid trajectory values/time")
    xy = np.column_stack((data["x"], data["y"]))
    path = prepare_path(mission["path"])
    tm = sc["tmap"]
    deviation = np.array([path_distance(p, path) for p in xy])
    cells = xy / RESOLUTION
    predicted = evaluate(cells if len(cells) > 1 else np.repeat(cells, 2, axis=0), tm)
    rx, ry = resample(cells if len(cells) > 1 else np.repeat(cells, 2, axis=0))
    xi = np.clip(np.rint(rx[:-1]).astype(int), 0, tm.shape[0] - 1)
    yi = np.clip(np.rint(ry[:-1]).astype(int), 0, tm.shape[1] - 1)
    dx, dy = np.diff(rx), np.diff(ry)
    norm = np.maximum(np.hypot(dx, dy), 1e-12)
    pitch = np.degrees(
        np.arctan(np.abs(tm.gx[xi, yi] * dx / norm + tm.gy[xi, yi] * dy / norm))
    )
    settings = {
        k: v
        for k, v in mission.get("controller", {}).items()
        if k in ("lookahead_m", "v_max", "w_max", "goal_tol_m")
    }
    settings.setdefault("lookahead_m", mission.get("lookahead_m", 1.0))
    simple = simulate(
        sc,
        path,
        [data["x"][0], data["y"][0], data["yaw"][0]],
        controller_kwargs=settings,
    )
    ground = map_coordinates(tm.elev, cells.T, order=1, mode="nearest")
    result = dict(
        data_source=mission.get("data_source", "robot_recording"),
        map_id=mission["map_id"],
        status=mission.get("status", "unknown"),
        completed=mission.get("status") == "completed",
        elapsed_s=float(data["t"][-1] - data["t"][0]),
        deviation_mean_m=float(deviation.mean()),
        deviation_max_m=float(deviation.max()),
        path_lethal_cells=len(path_lethal_cells(cells, tm.lethal)),
        out_of_bounds_samples=int(
            np.any((cells < 0) | (cells > np.array(tm.shape) - 1), axis=1).sum()
        ),
        fallen_samples=int((data["z"] < ground - 1.0).sum()),
        roll_p95_actual_deg=float(np.percentile(np.abs(np.degrees(data["roll"])), 95)),
        pitch_p95_actual_deg=float(
            np.percentile(np.abs(np.degrees(data["pitch"])), 95)
        ),
        roll_p95_map_deg=predicted["p95_roll"],
        pitch_p95_map_deg=float(np.percentile(pitch, 95)),
        kinematic={
            k: simple[k]
            for k in (
                "elapsed_s",
                "deviation_mean_m",
                "deviation_max_m",
                "path_lethal_cells",
                "completed",
            )
        },
    )
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    with (output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[k for k in result if k != "kinematic"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow({k: v for k, v in result.items() if k != "kinematic"})
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(
        tm.elev.T,
        origin="lower",
        extent=[-0.25, tm.shape[0] * 0.5 - 0.25, -0.25, tm.shape[1] * 0.5 - 0.25],
        cmap="terrain",
    )
    ax.plot(path[:, 0], path[:, 1], label="planned")
    ax.plot(xy[:, 0], xy[:, 1], label="recorded")
    traj = np.asarray(simple["trajectory"])
    ax.plot(traj[:, 1], traj[:, 2], ls="--", label="kinematic")
    ax.set(xlabel="x [m]", ylabel="y [m]", aspect="equal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "paths.png", dpi=130)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    for ax, key in zip(axes, ("roll", "pitch")):
        ax.plot(data["t"] - data["t"][0], np.degrees(data[key]))
        ax.set_ylabel(key + " [deg]")
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("time [s]")
    fig.tight_layout()
    fig.savefig(output / "attitude.png", dpi=130)
    plt.close(fig)
    lines = [
        "data_source " + result["data_source"],
        "source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells",
        "recorded "
        + " ".join(
            str(result[k])
            for k in (
                "completed",
                "elapsed_s",
                "deviation_mean_m",
                "deviation_max_m",
                "path_lethal_cells",
            )
        ),
        "kinematic "
        + " ".join(
            str(simple[k])
            for k in (
                "completed",
                "elapsed_s",
                "deviation_mean_m",
                "deviation_max_m",
                "path_lethal_cells",
            )
        ),
        "attitude actual_p95_deg map_p95_deg",
        f"roll {result['roll_p95_actual_deg']} {result['roll_p95_map_deg']}",
        f"pitch {result['pitch_p95_actual_deg']} {result['pitch_p95_map_deg']}",
    ]
    log = "\n".join(lines) + "\n"
    (output / "report_log.txt").write_text(log)
    print(log, end="")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gazebo走行記録と地図・運動学模型を比較"
    )
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    analyze_run(args.folder, args.output)
