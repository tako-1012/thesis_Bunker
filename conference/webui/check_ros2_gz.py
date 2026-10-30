"""Live browser check with explicitly labelled mock robot telemetry, never Gazebo data."""

import json
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright
import numpy as np
from tapp.mapfile import load_map_file
from tapp.tour import sample_waypoints
from .mock_robot import post_state


def main():
    root = Path(__file__).resolve().parent.parent
    url = os.environ.get("WEBUI_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    sc = load_map_file(root / "maps/flat_test_100m.npz")
    points = (np.asarray(sample_waypoints(sc, 5, 100)) * 0.5).tolist()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 1100}, device_scale_factor=1
        )
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_function("state.info !== null && !state.busy", timeout=120000)
        page.locator("#map-select").select_option("file/flat_test_100m.npz")
        page.wait_for_function(
            "state.info?.id === 'file/flat_test_100m.npz' && !state.busy",
            timeout=120000,
        )
        page.locator("#coordinates").fill(
            "\n".join(", ".join(map(str, row)) for row in points + [[-1, 0]])
        )
        page.locator("#apply-points").click()
        page.locator("#plan").click()
        page.wait_for_function(
            "!state.busy && state.results.length === 1", timeout=120000
        )
        with page.expect_response(
            lambda r: r.url.endswith("/api/robot/mission")
            and r.request.method == "POST"
        ) as sent:
            page.locator("#send-robot").click()
        mission = sent.value.json()
        assert mission["path"]
        assert len(mission["points"]) == len(points)
        # Use the documented mock sender. These positions are display inputs,
        # not measurements from a Gazebo model or an experiment.
        for point in mission["path"][:3]:
            post_state(
                url, mission["map_id"], [point[0], point[1], 0, 0, 0, 0], mission["id"]
            )
            page.wait_for_timeout(400)
        page.wait_for_function(
            "state.liveRobot !== null && state.livePoints.length >= 2"
        )
        assert "模擬状態" in page.locator("#robot-status").inner_text()
        assert page.evaluate("state.liveTrail.getLatLngs().length") >= 2
        for name, width, height in [("desktop", 1440, 1100), ("ipad", 834, 1112)]:
            page.set_viewport_size({"width": width, "height": height})
            post_state(
                url,
                mission["map_id"],
                [mission["path"][2][0], mission["path"][2][1], 0, 0, 0, 0],
                mission["id"],
            )
            page.wait_for_timeout(350)
            page.locator("#map").scroll_into_view_if_needed()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(
                path=str(root / "webui/screenshots" / f"ros2_robot_{name}.png"),
                full_page=True,
            )
        page.wait_for_function(
            "document.getElementById('robot-status').textContent.includes('つながっていません')",
            timeout=6000,
        )
        assert not errors, errors
        browser.close()
    print(
        "live UI: real five-point planner, rejected point excluded from send, send/id, labelled mock telemetry, purple marker/trail, desktop/tablet layouts, stale disconnect passed"
    )
    print("telemetry_source: mock_robot display test; not a Gazebo physical run")


if __name__ == "__main__":
    main()
