"""Sample CPU and memory for the recorder and planner from host procfs."""

import csv
import os
from pathlib import Path
import sys
import time


def role(argv):
    names = {Path(a).name for a in argv}
    if "sensor_recorder.py" in names:
        return "recorder"
    if "lidar_planner.py" in names:
        return "planner"
    if "parameter_bridge" in names:
        return "bridge"
    if any(name.startswith("gz-sim") for name in names) or ("gz" in names and "sim" in names):
        return "gazebo"
    return None


def main():
    out, stop = map(Path, sys.argv[1:])
    tick_hz = os.sysconf("SC_CLK_TCK")
    page_size = os.sysconf("SC_PAGE_SIZE")
    previous = {}
    started = time.monotonic()
    with out.open("x", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("wall_s", "role", "pid", "cpu_total_s", "cpu_percent_one_core", "rss_bytes"))
        while not stop.exists():
            now = time.monotonic()
            for folder in Path("/proc").iterdir():
                if not folder.name.isdigit():
                    continue
                try:
                    name = role((folder/"cmdline").read_bytes().decode(errors="replace").strip("\0").split("\0"))
                    if name is None:
                        continue
                    fields = (folder/"stat").read_text().rsplit(") ", 1)[1].split()
                    cpu = (int(fields[11])+int(fields[12]))/tick_hz
                    rss = int(fields[21])*page_size
                except (OSError, ValueError, IndexError):
                    continue
                pid = int(folder.name)
                last = previous.get((pid, fields[19]))
                usage = 100*(cpu-last[1])/(now-last[0]) if last else None
                writer.writerow((round(now-started, 3), name, pid, cpu, usage, rss))
                previous[(pid, fields[19])] = now, cpu
            stream.flush()
            time.sleep(1)


if __name__ == "__main__":
    main()
