"""Standard-library HTTP polling and coordinate helpers shared with offline tests."""

import json
import math
from urllib.request import Request, urlopen


class RobotHTTP:
    def __init__(self, url, map_id, timeout=1.0):
        self.url, self.map_id, self.timeout = url.rstrip("/"), map_id, timeout
        self.after = 0

    def _request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(
            self.url + path, data=data, headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=self.timeout) as response:
            return None if response.status == 204 else json.load(response)

    def poll(self):
        result = self._request("/api/robot/mission?after=" + str(self.after))
        if result is None:
            return None, None
        self.after = int(result["id"])
        if result["map_id"] != self.map_id:
            return None, dict(
                map_id=self.map_id,
                mission_id=self.after,
                status="map_mismatch",
                message="Gazeboと送信された地図が異なります",
            )
        return result, None

    def state(self, payload):
        return self._request("/api/robot/state", payload)


def rpy(q):
    x, y, z, w = q.x, q.y, q.z, q.w
    return (
        math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)),
        math.asin(max(-1, min(1, 2 * (w * y - z * x)))),
        math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)),
    )


def pose3d(pose):
    return (pose.position.x, pose.position.y, pose.position.z, *rpy(pose.orientation))
