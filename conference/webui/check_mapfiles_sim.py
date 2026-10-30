"""Optional live Chromium check of file-map planning, simulation and timed playback."""

import csv
import json
import math
import os
from pathlib import Path
import shutil

import numpy as np
from playwright.sync_api import sync_playwright
from tapp.mapfile import load_map_file
from tapp.tour import sample_waypoints

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("WEBUI_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
RESULTS = ROOT / "results" / "mapfiles_sim"


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    sc = load_map_file(ROOT / "maps" / "flat_test_100m.npz")
    points = (np.asarray(sample_waypoints(sc, 5, 100)) * 0.5).tolist()
    rows, errors, external = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        for name, width, height, touch in (
            ("desktop", 1440, 1100, False),
            ("ipad", 834, 1112, True),
        ):
            context = browser.new_context(
                viewport=dict(width=width, height=height),
                device_scale_factor=1,
                has_touch=touch,
                is_mobile=touch,
            )
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "request",
                lambda r: (
                    external.append(r.url) if not r.url.startswith(BASE) else None
                ),
            )
            page.goto(BASE)
            page.wait_for_function("state.info !== null && !state.busy", timeout=120000)
            assert page.locator("#map-select option").count() == 40
            page.locator("#map-select").select_option("file/flat_test_100m.npz")
            page.wait_for_function(
                "state.info?.id === 'file/flat_test_100m.npz' && !state.busy",
                timeout=120000,
            )
            assert page.locator("#map-size").inner_text() == "100 × 100 m"
            page.locator("#coordinates").fill(
                "\n".join(", ".join(map(str, point)) for point in points)
            )
            page.locator("#apply-points").click()
            page.locator("#plan").click()
            page.wait_for_function(
                "!state.busy && state.results.length === 1", timeout=120000
            )
            assert page.evaluate("state.results[0].path_lethal_cells") == 0
            for value in ("0.5", "3", "1"):
                page.locator("#lookahead").fill(value)
                assert (
                    page.locator("#lookahead-value").inner_text()
                    == f"{float(value):.1f} m"
                )
            page.locator("#simulate").click()
            page.wait_for_function(
                "!state.busy && state.simulation !== null", timeout=120000
            )
            result = page.evaluate("state.simulation")
            assert result["completed"]
            assert page.locator("#simulation-result").is_visible()
            assert page.evaluate("state.simulatedRoute.getLatLngs().length") == len(
                result["trajectory"]
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#play").click()
            page.wait_for_function("state.robot !== null")
            page.wait_for_timeout(800)
            observed = page.evaluate(
                "({t:(performance.now()-state.playback.start)/1000,x:state.robot.getLatLng().lng,y:state.robot.getLatLng().lat})"
            )
            trace = np.asarray(result["trajectory"])
            expected = [
                np.interp(observed["t"], trace[:, 0], trace[:, i]) for i in (1, 2)
            ]
            error = math.dist(expected, [observed["x"], observed["y"]])
            assert error < 0.15
            page.locator("#map").scroll_into_view_if_needed()
            page.screenshot(
                path=str(ROOT / "webui" / "screenshots" / f"mapfiles_sim_{name}.png"),
                full_page=True,
            )
            page.locator("#play").click()
            assert page.evaluate("state.robot === null")
            rows.append(
                dict(
                    view=name,
                    completed=result["completed"],
                    elapsed_s=result["elapsed_s"],
                    deviation_mean_m=result["deviation_mean_m"],
                    deviation_max_m=result["deviation_max_m"],
                    path_lethal_cells=result["path_lethal_cells"],
                    playback_error_m=error,
                )
            )
            # Changing the controller invalidates only the simulated trajectory.
            page.locator("#lookahead").fill("1.5")
            assert page.evaluate(
                "state.simulation === null && state.simulatedRoute === null && state.results.length === 1"
            )
            if touch:
                page.set_viewport_size(dict(width=1112, height=834))
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
            context.close()
        assert not errors, errors
        assert not external, external
        browser.close()
    print(
        "view completed elapsed_s deviation_mean_m deviation_max_m path_lethal_cells playback_error_m"
    )
    for row in rows:
        print(*row.values())
    with (RESULTS / "browser_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (RESULTS / "browser_input.json").write_text(
        json.dumps(
            dict(
                map_id="file/flat_test_100m.npz",
                points=points,
                start=(np.asarray(sc["start"]) * 0.5).tolist(),
                lookahead_m=1.0,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        "file map, five-point plan, lookahead range, simulation, orange trace, timed playback, desktop/tablet reflow passed"
    )
    print(
        "no page errors or external asset requests; Chromium touch emulation, Safari not verified"
    )


if __name__ == "__main__":
    main()
