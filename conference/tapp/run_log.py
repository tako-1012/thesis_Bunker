"""One durable mission JSON and streaming trajectory CSV per robot run."""

import csv
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

FIELDS = ["t", "x", "y", "z", "roll", "pitch", "yaw", "v", "w"]


class RunLog:
    def __init__(self, mission, root=None):
        root = Path(root).expanduser() if root else Path.home() / "thesis_runs"
        stamp = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%dT%H%M%S_%f")
        name = re.sub(r"[^A-Za-z0-9_-]", "_", mission["map_id"])
        self.folder = root / (stamp + "_" + name)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.mission = dict(mission, status="running")
        self._save()
        self.stream = (self.folder / "trajectory.csv").open("w", newline="")
        self.writer = csv.DictWriter(
            self.stream, fieldnames=FIELDS, lineterminator="\n"
        )
        self.writer.writeheader()

    def _save(self):
        (self.folder / "mission.json").write_text(
            json.dumps(self.mission, ensure_ascii=False, indent=2) + "\n"
        )

    def write(self, row):
        self.writer.writerow(row)
        self.stream.flush()

    def close(self, status):
        self.mission["status"] = status
        self._save()
        self.stream.close()
