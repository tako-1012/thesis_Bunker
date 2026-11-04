"""Official zone-VIII references, cell-centre geometry, immutable sidecars and additive APIs."""

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
from fastapi.testclient import TestClient
from tapp.geo import plane_to_latlon,latlon_to_plane,map_xy_to_latlon,latlon_to_map_xy
from tapp.mapfile import load_map_file
from tapp.mission import render_map_png
from data_prep.export_maps import export_geo_sidecars
from webui.server import app

ROOT=Path(__file__).resolve().parents[1]


def test_projection():
    assert np.max(np.abs(np.asarray(plane_to_latlon(0,0))-[36.,138.5]))<=1e-9
    xy=np.array([[-146639.066,-92848.522],[-146574.980,-92348.545],[-146299.598,-89848.337],[-150000.,-100000.]])
    expected=np.array([[34.673951199,137.486827008],[34.674574079,137.492275071],[34.677278811,137.519524976],[34.642983539,137.409198432]])
    actual=np.array(plane_to_latlon(*xy.T)).T
    difference=actual-expected
    assert np.max(np.abs(difference))<=1e-7
    print("zone VIII reference differences [latitude_deg, longitude_deg]:",flush=True)
    for row in difference:print(" ".join(f'{value:.12g}' for value in row),flush=True)
    points=np.vstack([xy,[0,0],[-180000,-120000],[-130000,-70000]])
    ll=plane_to_latlon(*points.T);restored=np.array(latlon_to_plane(*ll)).T
    error=float(np.max(np.abs(restored-points)))
    assert error<=1e-3
    print("projection round-trip max error [m]:",format(error,".12g"),flush=True)


def test_sidecars_and_geometry():
    paths=sorted((ROOT/"maps").glob("real_las_*.npz"));assert paths
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for path in paths:shutil.copy2(path,tmp/path.name)
        sidecars=export_geo_sidecars(tmp)
        assert {p.name for p in sidecars}=={p.with_suffix(".geo.json").name for p in paths}
        first={p.name:p.read_bytes() for p in sidecars}
        export_geo_sidecars(tmp)
        assert first=={p.name:p.read_bytes() for p in sidecars}
        for path in paths:
            meta=json.loads((tmp/path.with_suffix(".geo.json").name).read_text())
            assert meta["map_sha256"]==before[path.name]==hashlib.sha256((tmp/path.name).read_bytes()).hexdigest()
            with np.load(ROOT/"data/shizuoka_beach_las"/(meta["source_patch"]+".npz"),allow_pickle=False) as src:
                for key in ("origin_xy","tangent","normal"):assert np.array_equal(meta[key],src[key])
            xy=np.array([[0,0],[100,100],[199.5,199.5],[-meta["offset_uv_m"][0],-meta["offset_uv_m"][1]]])
            ll=map_xy_to_latlon(meta,*xy.T)
            restored=np.array(latlon_to_map_xy(meta,*ll)).T
            assert np.max(np.abs(restored-xy))<=1e-3
            origin_ll=plane_to_latlon(*meta["origin_xy"])
            assert np.max(np.abs(np.asarray([ll[0][-1],ll[1][-1]])-origin_ll))<=1e-10
            # Cell (200,200) is (u,v)=(0.25,50.25), not the coastline anchor.
            o,t,n=map(np.asarray,[meta["origin_xy"],meta["tangent"],meta["normal"]])
            X=o[0]-(.25*t[0]+50.25*n[0]);Y=o[1]+.25*t[1]+50.25*n[1]
            expected=plane_to_latlon(X,Y)
            assert np.max(np.abs(np.asarray([ll[0][1],ll[1][1]])-expected))<=1e-10
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    print("geographic sidecars:",len(paths),"maps; source axes, coastline anchor, half-cell offset, round trips and NPZ hashes passed",flush=True)


def test_api():
    real=next(p for p in sorted((ROOT/"maps").glob("real_las_*_200m_0.npz")))
    map_id="file/"+real.name
    with TestClient(app) as client:
        info=client.get("/api/maps/"+map_id).json()
        assert info["geo"]["zone"]==8
        points=[info["start"],[99.75,49.75],[100,100]]
        response=client.post("/api/geo/to-latlon",json=dict(map_id=map_id,points=points))
        assert response.status_code==200,response.text
        ll=response.json()["points"]
        expected=np.array(map_xy_to_latlon(info["geo"],*np.array(points).T)).T
        assert np.array_equal(np.array([[p["lat"],p["lng"]] for p in ll]),expected)
        response=client.post("/api/geo/to-map",json=dict(map_id=map_id,points=ll))
        assert response.status_code==200,response.text
        assert np.max(np.abs(np.asarray(response.json()["points"])-points))<=1e-3
        old=client.get("/api/maps/file/flat_test_100m.npz").json()
        assert set(old)=={"id","side_m","resolution","shape","attribution","source","start","bounds"}
        image=client.get("/api/maps/file/flat_test_100m.npz/image.png")
        assert image.content==render_map_png(load_map_file(ROOT/"maps/flat_test_100m.npz"))
        assert client.post("/api/geo/to-latlon",json=dict(map_id=old["id"],points=[[1,1]])).status_code==422
        assert client.post("/api/geo/to-map",json=dict(map_id=map_id,points=[dict(lat=0,lng=0)])).status_code==422
    print("Web APIs: geographic map conversions, unavailable-map response and unchanged legacy metadata/image passed",flush=True)


if __name__=="__main__":
    test_projection();test_sidecars_and_geometry();test_api()
    print("all geographic conversion tests passed",flush=True)
