"""Optional geographic sidecars and additive waypoint conversion endpoints."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import numpy as np
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from tapp import mission
from tapp.geo import map_xy_to_latlon,latlon_to_map_xy

router=APIRouter()


@lru_cache(maxsize=64)
def _read_geo(path,sidecar_mtime,map_mtime,map_bytes):
    path=Path(path)
    meta=json.loads(path.with_suffix(".geo.json").read_text())
    if meta["map_file"]!=path.name or meta["map_sha256"]!=hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("地図と位置情報ファイルが一致しません")
    map_xy_to_latlon(meta,0,0)
    return meta


def geo_for_map(map_id):
    parts=map_id.split("/")
    if len(parts)!=2 or parts[0]!="file" or Path(parts[1]).name!=parts[1]:
        return None
    path=mission.MAPS_DIR/parts[1]
    sidecar=path.with_suffix(".geo.json")
    if not sidecar.is_file():return None
    try:
        return _read_geo(str(path),sidecar.stat().st_mtime_ns,path.stat().st_mtime_ns,path.stat().st_size)
    except (ValueError,KeyError,OSError) as exc:
        raise ValueError("位置情報を読み込めません: "+str(exc)) from exc


class XYRequest(BaseModel):
    map_id:str
    points:list[tuple[float,float]]=Field(min_length=1,max_length=13)


class LatLng(BaseModel):
    lat:float=Field(ge=-90,le=90,allow_inf_nan=False)
    lng:float=Field(ge=-180,le=180,allow_inf_nan=False)


class LatLngRequest(BaseModel):
    map_id:str
    points:list[LatLng]=Field(min_length=1,max_length=13)


def _map_geo(map_id):
    try:
        sc=mission.load_map(map_id)
    except ValueError as exc:
        raise HTTPException(404,str(exc)) from exc
    try:
        meta=geo_for_map(map_id)
        if meta is None:raise ValueError("この地図には緯度・経度の位置情報がありません")
        return sc,meta
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post("/api/geo/to-latlon")
def to_latlon(request:XYRequest):
    _,meta=_map_geo(request.map_id)
    try:
        xy=np.asarray(request.points,float)
        lat,lng=map_xy_to_latlon(meta,*xy.T)
        if not np.isfinite([lat,lng]).all():raise ValueError("変換できる範囲の座標を指定してください")
        return dict(map_id=request.map_id,points=[dict(lat=float(a),lng=float(b)) for a,b in zip(lat,lng)])
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post("/api/geo/to-map")
def to_map(request:LatLngRequest):
    sc,meta=_map_geo(request.map_id)
    try:
        ll=np.asarray([(p.lat,p.lng) for p in request.points],float)
        xy=np.array(latlon_to_map_xy(meta,*ll.T)).T
        limit=(np.asarray(sc["tmap"].shape)-1)*meta["resolution"]
        # One micrometre only for projection roundoff at the first/last centres.
        if (xy < -1e-6).any() or (xy > limit+1e-6).any():
            raise ValueError("地図の範囲内にある緯度・経度を指定してください")
        return dict(map_id=request.map_id,points=np.clip(xy,0,limit).tolist())
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
