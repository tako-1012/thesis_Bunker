"""Optional live Chromium checks/screenshots for geographic display and actual downloads."""

import argparse
import json
import math
from pathlib import Path
import shutil
import sys
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from tapp.mapfile import load_map_file
from tapp.tour import sample_waypoints
from tapp.config import RESOLUTION
import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:8088")
    parser.add_argument("--output",type=Path,default=ROOT/"latlon_checks")
    args=parser.parse_args();base=args.base_url.rstrip("/");output=args.output;output.mkdir(parents=True,exist_ok=True)
    screenshots=ROOT/"screenshots";screenshots.mkdir(exist_ok=True)
    log=[];errors=[];external=[]
    def record(s):log.append(s);print(s,flush=True)
    def ready(page):page.wait_for_function("state.info !== null && !state.busy",timeout=180000)
    def listen(page):
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("request",lambda r:external.append(r.url) if not r.url.startswith(base) and not r.url.startswith("blob:") else None)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which("chromium"),headless=True,args=["--no-sandbox"])
        context=browser.new_context(viewport=dict(width=1440,height=1100),accept_downloads=True)
        page=context.new_page();listen(page);page.goto(base);ready(page)
        assert page.locator("#geo-tools").is_hidden()
        maps=page.request.get(base+"/api/maps").json()
        target=next(r["id"] for r in maps if r["id"].startswith("file/real_las_") and r["id"].endswith("_200m_0.npz"))
        sc=load_map_file(ROOT.parent/"maps"/target.split("/",1)[1])
        points=(np.asarray(sample_waypoints(sc,2,100))*RESOLUTION).tolist()
        page.locator("#map-select").select_option(target);ready(page)
        assert page.locator("#geo-tools").is_visible()
        page.locator("#coordinates").fill("\n".join(",".join(map(str,p)) for p in points));page.locator("#apply-points").click()
        page.wait_for_function("document.getElementById('geo-coordinates').value.split('\\n').length===2 && document.getElementById('geo-coordinates').value.length>0")
        page.locator("#map").scroll_into_view_if_needed()
        pos=page.evaluate("(xy)=>{const p=map.latLngToContainerPoint([xy[1],xy[0]]);return {x:p.x,y:p.y}}",points[0])
        box=page.locator("#map").bounding_box();page.mouse.move(box["x"]+pos["x"],box["y"]+pos["y"])
        page.wait_for_function("document.getElementById('cursor-latlon').textContent.startsWith('緯度 ')")
        with page.expect_download() as pending:page.locator("#save-geo-json").click()
        json_path=output/"waypoints_latlng.json";pending.value.save_as(str(json_path));payload=json.loads(json_path.read_text())
        assert payload["format"]=="latlng" and payload["map_id"]==target and len(payload["points"])==len(points)
        page.wait_for_function("!state.busy")
        page.screenshot(path=str(screenshots/"latlon_desktop.png"),full_page=True)
        with page.expect_download() as pending:page.locator("#save-geo-txt").click()
        text_path=output/"waypoints_latlng.txt";pending.value.save_as(str(text_path));text=text_path.read_text()
        assert len(text.strip().splitlines())==len(points)
        page.wait_for_function("!state.busy")
        page.locator("#clear-points").click();page.locator("#geo-file-input").set_input_files(str(json_path))
        page.wait_for_function("state.points.length===2 && !state.busy")
        assert all(math.dist(a,b)<=1e-3 for a,b in zip(page.evaluate("state.points"),points))
        page.locator("#geo-coordinates").fill(text);page.locator("#apply-geo").click()
        page.wait_for_function("!state.busy")
        assert all(math.dist(a,b)<=1e-3 for a,b in zip(page.evaluate("state.points"),points))
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        record("desktop: geographic cursor, lat/lng list, actual JSON/text downloads and both import round trips passed")
        mobile=browser.new_context(viewport=dict(width=390,height=844),has_touch=True,is_mobile=True)
        phone=mobile.new_page();listen(phone);phone.goto(base);ready(phone)
        phone.locator("#map-select").select_option(target);ready(phone)
        phone.locator("#map").scroll_into_view_if_needed()
        pos=phone.evaluate("(xy)=>{const p=map.latLngToContainerPoint([xy[1],xy[0]]);return {x:p.x,y:p.y}}",points[0])
        box=phone.locator("#map").bounding_box();phone.touchscreen.tap(box["x"]+pos["x"],box["y"]+pos["y"])
        phone.wait_for_function("document.getElementById('cursor-latlon').textContent.startsWith('緯度 ')")
        phone.locator("#geo-file-input").set_input_files(str(text_path))
        phone.wait_for_function("state.points.length===2 && !state.busy")
        phone.wait_for_function("document.getElementById('geo-coordinates').value.trim().split('\\n').length===2")
        assert all(math.dist(a,b)<=1e-3 for a,b in zip(phone.evaluate("state.points"),points))
        assert phone.evaluate("document.documentElement.scrollWidth<=innerWidth")
        phone.screenshot(path=str(screenshots/"latlon_phone.png"),full_page=True)
        record("phone 390x844: touch coordinate display, lat/lng text file import and no horizontal overflow passed (Chromium emulation)")
        phone.locator("#map-select").select_option("file/flat_test_100m.npz");ready(phone)
        assert phone.locator("#geo-tools").is_hidden() and phone.locator("#cursor-latlon").is_hidden()
        assert not errors,errors
        assert not external,external
        record("unreferenced map: geographic tools hidden; no browser errors or external requests")
        browser.close()
    (output/"browser_log.txt").write_text("\n".join(log)+"\n")


if __name__=="__main__":main()
