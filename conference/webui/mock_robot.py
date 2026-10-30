"""Post explicitly labelled display-test telemetry; this is not a physical robot."""

import argparse
import json
from urllib.request import Request, urlopen


def post_state(url, map_id, pose, mission_id=0, status="running"):
    payload = dict(
        map_id=map_id,
        pose=pose,
        mission_id=mission_id,
        status=status,
        message="表示確認用の模擬状態（Gazeboではありません）",
    )
    request = Request(
        url.rstrip("/") + "/api/robot/state",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=3) as response:
        return json.load(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Web位置表示の確認用。実測値ではない模擬状態を1件送信"
    )
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--map-id", default="file/flat_test_100m.npz")
    parser.add_argument(
        "--pose", default="10,10,0,0,0,0", help="x,y,z,roll,pitch,yaw（m,rad）"
    )
    parser.add_argument("--mission-id", type=int, default=0)
    parser.add_argument("--status", default="running")
    args = parser.parse_args()
    pose = [float(v) for v in args.pose.split(",")]
    if len(pose) != 6:
        parser.error("poseには6個の数値が必要です")
    print(post_state(args.url, args.map_id, pose, args.mission_id, args.status))
