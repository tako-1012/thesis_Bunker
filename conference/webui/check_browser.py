"""Optional Playwright checks/screenshots against a live server, using real plans.

Run from conference: python3 -m webui.check_browser (install playwright separately).
WEBUI_BASE_URL overrides the local port 8080 default. Chromium must be available.
"""

import csv, json, math, os, shutil, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT.parent / "results" / "web_ui"
RESULTS.mkdir(parents=True, exist_ok=True)
(ROOT / "screenshots").mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT.parent))
from tapp.mission import load_map
from tapp.tour import sample_waypoints
from tapp.config import RESOLUTION

sc = load_map("synthetic/beach_gentle/200/100")
fixture = dict(
    start=[float(v) * RESOLUTION for v in sc["start"]],
    points=[[float(v) * RESOLUTION for v in p] for p in sample_waypoints(sc, 5, 100)],
)
BASE_URL = os.environ.get("WEBUI_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
TEMP = tempfile.TemporaryDirectory(prefix="web-ui-browser-")
SAVED = Path(TEMP.name) / "points.json"
checks = []
plans = []
errors = []
external = []


def record(message):
    checks.append(message)
    print(message, flush=True)


def click_xy(page, point, touch=False):
    pos = page.evaluate(
        "(xy) => { const p=map.latLngToContainerPoint([xy[1],xy[0]]); return {x:p.x,y:p.y}; }",
        point,
    )
    box = page.locator("#map").bounding_box()
    if touch:
        page.touchscreen.tap(box["x"] + pos["x"], box["y"] + pos["y"])
    else:
        page.mouse.click(box["x"] + pos["x"], box["y"] + pos["y"])


def ready(page):
    page.wait_for_function("state.info !== null && !state.busy", timeout=180000)


def done(page):
    page.wait_for_function("!state.busy", timeout=240000)
    assert not page.locator("#status").evaluate(
        '(e)=>e.classList.contains("error")'
    ), page.locator("#status-text").inner_text()


def listen(page):
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "request",
        lambda r: (
            external.append(r.url)
            if not r.url.startswith(BASE_URL) and not r.url.startswith("blob:")
            else None
        ),
    )

    def response(r):
        if r.url.endswith("/api/plan") and r.status == 200:
            plans.append(r.json())

    page.on("response", response)


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=shutil.which("chromium"), headless=True, args=["--no-sandbox"]
    )
    desktop = browser.new_context(
        viewport={"width": 1440, "height": 1100}, device_scale_factor=1
    )
    page = desktop.new_page()
    listen(page)
    page.goto(BASE_URL)
    ready(page)
    assert page.locator("#map-select option").count() == 17
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    record("desktop 1440px: initial map, 17 choices and no horizontal overflow passed")
    click_xy(page, fixture["points"][0])
    assert page.locator("#point-count").inner_text() == "1 / 12"
    box = page.locator(".waypoint-icon").bounding_box()
    old = page.locator("#coordinates").input_value()
    page.mouse.move(box["x"] + 16, box["y"] + 16)
    page.mouse.down()
    page.mouse.move(box["x"] + 35, box["y"] + 26, steps=8)
    page.mouse.up()
    assert page.locator("#coordinates").input_value() != old
    page.locator(".waypoint-icon").click()
    page.get_by_role("button", name="この地点を削除").click()
    assert page.locator("#point-count").inner_text() == "0 / 12"
    record("desktop: map click, numbered marker, drag and popup deletion passed")
    base = page.locator(".base-icon").bounding_box()
    old = page.locator("#start-x").input_value()
    page.mouse.move(base["x"] + 15, base["y"] + 15)
    page.mouse.down()
    page.mouse.move(base["x"] + 28, base["y"] + 25, steps=8)
    page.mouse.up()
    assert page.locator("#start-x").input_value() != old
    page.locator("#start-x").fill(str(fixture["start"][0]))
    page.locator("#start-y").fill(str(fixture["start"][1]))
    page.locator("#apply-start").click()
    page.locator("#coordinates").fill(
        "\n".join(", ".join(map(str, point)) for point in fixture["points"])
    )
    page.locator("#apply-points").click()
    assert page.locator("#point-count").inner_text() == "5 / 12"
    record("desktop: base drag/direct input and pasted five-point coordinates passed")
    with page.expect_download() as download_info:
        page.locator("#save-points").click()
    download = download_info.value
    download.save_as(str(SAVED))
    saved = json.loads(Path(str(SAVED)).read_text())
    assert saved["points"] == fixture["points"]
    page.locator("#clear-points").click()
    assert page.locator("#point-count").inner_text() == "0 / 12"
    page.locator("#file-input").set_input_files(str(SAVED))
    page.wait_for_function("state.points.length === 5 && !state.busy")
    assert page.locator("#point-count").inner_text() == "5 / 12"
    record("desktop: JSON browser download, clear and file import round-trip passed")
    page.locator("#plan").click()
    page.wait_for_function("state.busy")
    assert page.locator("#map-select").is_disabled()
    assert page.request.get(BASE_URL + "/api/maps").status == 200
    done(page)
    assert page.locator("#results-table tbody tr").count() == 10
    assert page.evaluate("state.results[0].path_lethal_cells") == 0
    record(
        "desktop: live terrain plan, responsive API while busy and results table passed"
    )
    page.locator("#compare").click()
    done(page)
    assert page.locator(".tour-order").count() == 2
    assert page.evaluate("state.routes.length") == 2
    assert page.locator("#results-table thead th").count() == 3
    record(
        "desktop: sequential comparison, two overlaid routes and side-by-side metrics passed"
    )
    page.locator("#play").click()
    page.wait_for_function("state.robot !== null")
    start = page.evaluate(
        "({p:[state.robot.getLatLng().lng,state.robot.getLatLng().lat],t:performance.now()})"
    )
    page.wait_for_timeout(800)
    end = page.evaluate(
        "({p:[state.robot.getLatLng().lng,state.robot.getLatLng().lat],t:performance.now()})"
    )
    distance = math.dist(start["p"], end["p"])
    expected = (end["t"] - start["t"]) / 1000 * 1.388
    assert abs(distance - expected) < 0.15, (distance, expected)
    record(
        f'desktop: playback observed {distance:.6f}m in {(end["t"]-start["t"])/1000:.6f}s, consistent with 1.388m/s'
    )
    page.locator("#map").scroll_into_view_if_needed()
    page.screenshot(path=str(ROOT / "screenshots/desktop.png"), full_page=True)
    page.locator("#play").click()
    assert page.evaluate("state.robot === null")
    # Reuse only the actual downloaded inputs; compute a fresh result in the tablet context.
    tablet = browser.new_context(
        viewport={"width": 834, "height": 1112},
        device_scale_factor=1,
        has_touch=True,
        is_mobile=True,
        user_agent="Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1",
    )
    ipad = tablet.new_page()
    listen(ipad)
    ipad.goto(BASE_URL)
    ready(ipad)
    click_xy(ipad, fixture["points"][0], touch=True)
    assert ipad.locator("#point-count").inner_text() == "1 / 12"
    ipad.locator("#file-input").set_input_files(str(SAVED))
    ipad.wait_for_function("state.points.length === 5 && !state.busy")
    ipad.locator("#compare").tap()
    done(ipad)
    assert ipad.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert ipad.locator(".tour-order").count() == 2
    sizes = ipad.locator("button").evaluate_all(
        "(els)=>els.filter(e=>e.getClientRects().length).map(e=>({id:e.id,height:e.getBoundingClientRect().height}))"
    )
    assert all(x["height"] >= 44 for x in sizes), sizes
    ipad.locator("#play").tap()
    ipad.wait_for_function("state.robot !== null")
    ipad.locator("#map").scroll_into_view_if_needed()
    ipad.screenshot(path=str(ROOT / "screenshots/ipad.png"), full_page=True)
    ipad.locator("#play").tap()
    record(
        "tablet 834x1112: touch addition, JSON import, real comparison/playback, >=44px buttons and no horizontal overflow passed (Chromium touch emulation)"
    )
    ipad.set_viewport_size({"width": 1112, "height": 834})
    ipad.wait_for_timeout(300)
    assert ipad.evaluate("document.documentElement.scrollWidth <= innerWidth")
    ipad.locator("#fit-map").tap()
    record(
        "tablet 1112x834: landscape reflow and fit map passed (Chromium touch emulation)"
    )
    # The source must be visible on a real map, not just on synthetic ones.
    real_id = next(
        o["id"]
        for o in page.request.get(BASE_URL + "/api/maps").json()
        if o["id"].startswith("real/")
    )
    ipad.locator("#map-select").select_option(real_id)
    ready(ipad)
    assert ipad.locator("#map-name").inner_text().startswith("静岡県")
    assert "静岡県" in ipad.locator(".source").inner_text()
    assert ipad.evaluate("state.image.getElement().naturalWidth") == 400
    record(
        "real validation map: image/selection, reset points and Shizuoka attribution passed"
    )
    assert not errors, errors
    assert not external, external
    record(
        "browser console: no page errors; runtime network: no external asset requests"
    )
    browser.close()

(RESULTS / "browser_checks_log.txt").write_text("\n".join(checks) + "\n")
(RESULTS / "browser_plan_results.json").write_text(
    json.dumps(plans, ensure_ascii=False, indent=2) + "\n"
)
TEMP.cleanup()
(RESULTS / "browser_input.json").write_text(
    json.dumps(fixture, ensure_ascii=False, indent=2) + "\n"
)
with (RESULTS / "browser_summary.csv").open("w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "method",
            "points",
            "length_xy_m",
            "climb_m",
            "mean_cost",
            "energy_kj",
            "matrix_s",
            "solve_s",
            "lethal_cells",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for r in plans:
        m = r["metrics"]
        t = r["timing"]
        writer.writerow(
            dict(
                method=r["method"],
                points=len(r["order"]) - 1,
                length_xy_m=m["length_xy"],
                climb_m=m["climb"],
                mean_cost=m["mean_cost"],
                energy_kj=m["energy_kj"],
                matrix_s=t["matrix_s"],
                solve_s=t["solve_s"],
                lethal_cells=r["path_lethal_cells"],
            )
        )
# Only timings and scalar summaries, never constructed experimental values.
print(
    "method points length_xy_m climb_m mean_cost energy_kj matrix_s solve_s lethal_cells",
    flush=True,
)
for result in plans:
    m = result["metrics"]
    t = result["timing"]
    print(
        result["method"],
        len(result["order"]) - 1,
        m["length_xy"],
        m["climb"],
        m["mean_cost"],
        m["energy_kj"],
        t["matrix_s"],
        t["solve_s"],
        result["path_lethal_cells"],
        flush=True,
    )
