"""Browser-only online-path telemetry fixture; never claim mock data is a robot run."""

import json
import os
from pathlib import Path
import shutil
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright


def main():
    url = os.environ.get("WEBUI_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
    output = Path(__file__).resolve().parent.parent / "results/online_mission"
    errors = []

    def post(path, pose, count):
        payload = dict(
            map_id="file/flat_test_100m.npz",
            mission_id=914,
            status="running",
            pose=[*pose, 0, 0, 0, 0],
            sim_time=0,
            current_path=path,
            n_replans=count,
            message="画面確認用の模擬状態（Gazebo未実測）",
        )
        with urlopen(
            Request(
                url + "/api/robot/state",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
        ) as response:
            assert response.status == 200

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        page.wait_for_function("state.info !== null && !state.busy", timeout=120000)
        page.locator("#map-select").select_option("file/flat_test_100m.npz")
        page.wait_for_function(
            "state.info?.id === 'file/flat_test_100m.npz' && !state.busy",
            timeout=120000,
        )
        page.locator("#coordinates").fill("20, 10\n20, 20")
        page.locator("#apply-points").click()
        page.locator("#plan").click()
        page.wait_for_function(
            "!state.busy && state.results.length === 1", timeout=120000
        )
        post([[10, 10], [20, 10], [20, 20]], [12, 10], 1)
        page.wait_for_function(
            "state.livePath !== null && state.livePath.getLatLngs().length === 3"
        )
        post([[13, 10], [18, 13], [20, 20]], [13, 10], 2)
        page.wait_for_function(
            "state.livePoints.length >= 2 && document.getElementById('robot-status').textContent.includes('計画し直した回数 2')"
        )
        assert page.evaluate("state.livePath.getLatLngs()[1].lng") == 18
        assert "模擬状態" in page.locator("#robot-status").inner_text()
        assert page.locator("#robot-status").is_visible()
        for name, width, height in [("desktop", 1440, 1100), ("tablet", 834, 1112)]:
            page.set_viewport_size({"width": width, "height": height})
            post([[13, 10], [18, 13], [20, 20]], [13, 10], 2)
            page.wait_for_timeout(400)
            page.locator("#map").scroll_into_view_if_needed()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"ui_{name}.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print(
        "browser: current green path replacement, continuous purple trail, replanning count and desktop/tablet layout passed"
    )
    print("telemetry_source: labelled browser fixture only; not Gazebo measurements")


if __name__ == "__main__":
    main()
