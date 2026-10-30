#!/usr/bin/env python3
"""Rebuild the 60 real-beach patches from the Shizuoka ALB ground point cloud (no 0.1 m height steps).

The published ALB 0.5 m grid (used by shizuoka_beach.py) stores heights rounded to 0.1 m, so flat beach
areas become terraces with 0.1 m steps. The same survey is also published as ground-classified LAS points
with 1 mm resolution. This script keeps every patch of data/shizuoka_beach/ at exactly the same place and
orientation (origin_xy, tangent, normal) and recomputes only the elevation:
  1. find the level-500 sheets (300 m x 400 m) the patch touches and download their ground LAS ZIPs;
  2. rotate the ground points into the patch frame (x along the shore -100..100 m, y sea->land -50..150 m)
     and average them per 0.5 m cell;
  3. a cell without points takes the mean of the points in its 3 x 3 neighbourhood (1.5 m square);
     if that is empty too, it stays NaN (no data).
Source: Shizuoka Prefecture, "VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ" (ALB ground points, JGD2024 /
plane rectangular zone VIII, heights T.P.), CC BY 4.0 / ODbL.

Usage (from conference/): python3 data_prep/shizuoka_beach_las.py <work_dir>
Output: data/shizuoka_beach_las/<name>.npz (elev float32 [m], npts uint16, origin_xy, tangent, normal, res)
        + index.json
"""
import json
import os
import struct
import sys
import urllib.error
import urllib.request
import zipfile

import numpy as np

RES = 0.5
N = 400
GROUND_URL = "https://virtual-shizuoka.s3.ap-northeast-1.amazonaws.com/2025/ALB/Ground/08/{a}/{b}/{code}.zip"
SRC = os.path.join(os.path.dirname(__file__), "..", "data", "shizuoka_beach")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "shizuoka_beach_las")


def sheet_code(X, Y):
    """Level-500 sheet code (e.g. 08OC9382) that contains the plane point X (north) / Y (east) [m]."""
    s = 300000 - X
    r = int(s // 30000)
    s -= r * 30000
    a = int(s // 3000)
    s -= a * 3000
    d = int(s // 300)
    t = Y + 160000
    c = int(t // 40000)
    t -= c * 40000
    b = int(t // 4000)
    t -= b * 4000
    e = int(t // 400)
    return f"08{chr(65 + r)}{chr(65 + c)}{a}{b}{d}{e}"


def patch_to_plane(origin_xy, tangent, normal, u, v):
    """Plane coordinates (X north, Y east) of patch coordinates u (along shore), v (sea -> land) [m]."""
    X = origin_xy[0] - (u * tangent[0] + v * normal[0])
    Y = origin_xy[1] + (u * tangent[1] + v * normal[1])
    return X, Y


def plane_to_patch(origin_xy, tangent, normal, X, Y):
    di, dj = origin_xy[0] - X, Y - origin_xy[1]
    return di * tangent[0] + dj * tangent[1], di * normal[0] + dj * normal[1]


def patch_sheets(origin_xy, tangent, normal):
    g = np.linspace(-1, 1, 41)
    u, v = np.meshgrid(g * 101, 50 + g * 101)
    X, Y = patch_to_plane(origin_xy, tangent, normal, u.ravel(), v.ravel())
    return sorted({sheet_code(x, y) for x, y in zip(X, Y)})


def read_las(data):
    """Points of a LAS 1.x file as (X north, Y east, z) [m]; LAS x is easting, LAS y is northing."""
    off = struct.unpack("<I", data[96:100])[0]
    reclen = struct.unpack("<H", data[105:107])[0]
    n = struct.unpack("<I", data[107:111])[0]
    if data[25] >= 4 and n == 0:
        n = struct.unpack("<Q", data[247:255])[0]
    scale = struct.unpack("<3d", data[131:155])
    shift = struct.unpack("<3d", data[155:179])
    dt = np.dtype([("x", "<i4"), ("y", "<i4"), ("z", "<i4"), ("rest", f"V{reclen - 12}")])
    p = np.frombuffer(data, dtype=dt, count=n, offset=off)
    east = p["x"] * scale[0] + shift[0]
    north = p["y"] * scale[1] + shift[1]
    return north, east, p["z"] * scale[2] + shift[2]


def download(codes, work):
    os.makedirs(work, exist_ok=True)
    for code in codes:
        path = os.path.join(work, code + ".zip")
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(GROUND_URL.format(a=code[2:4], b=code[4:6], code=code), path)
            except urllib.error.HTTPError as exc:   # sheets outside the survey area have no file
                if exc.code != 404:
                    raise
                print("no ground file", code)


def load_sheet(work, code):
    path = os.path.join(work, code + ".zip")
    if not os.path.exists(path):
        return None
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".las")][0]
        return read_las(z.read(name))


def grid_patch(points, origin_xy, tangent, normal):
    """Mean ground height per 0.5 m patch cell, with the 3 x 3 fallback for empty cells."""
    s = np.zeros((N + 2, N + 2))
    c = np.zeros((N + 2, N + 2))
    for X, Y, z in points:
        u, v = plane_to_patch(origin_xy, tangent, normal, X, Y)
        a = np.floor((u + 100) / RES).astype(int) + 1
        b = np.floor((v + 50) / RES).astype(int) + 1
        ok = (a >= 0) & (a < N + 2) & (b >= 0) & (b < N + 2)
        k = a[ok] * (N + 2) + b[ok]
        s += np.bincount(k, z[ok], minlength=(N + 2) ** 2).reshape(N + 2, N + 2)
        c += np.bincount(k, minlength=(N + 2) ** 2).reshape(N + 2, N + 2)
    s3 = sum(s[1 + i:N + 1 + i, 1 + j:N + 1 + j] for i in (-1, 0, 1) for j in (-1, 0, 1))
    c3 = sum(c[1 + i:N + 1 + i, 1 + j:N + 1 + j] for i in (-1, 0, 1) for j in (-1, 0, 1))
    s, c = s[1:-1, 1:-1], c[1:-1, 1:-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        elev = np.where(c > 0, s / c, np.where(c3 > 0, s3 / c3, np.nan))
    return elev.astype(np.float32), np.minimum(c, 65535).astype(np.uint16)


def stats(z, old):
    land = z > 0
    gx, gy = np.gradient(z.astype(float), RES)
    sl = np.degrees(np.arctan(np.hypot(gx, gy)))
    both = np.isfinite(z) & np.isfinite(old)
    fin = z[np.isfinite(z)]
    return dict(nan_frac=round(float(np.isnan(z).mean()), 4),
                land_width_m=float(np.median(land.sum(1)) * RES), zmax=round(float(np.nanmax(z)), 3),
                steep_land=round(float((sl[land & np.isfinite(sl)] > 25).mean()), 5),
                on_0p1_grid=round(float(np.mean(np.abs(fin * 10 - np.round(fin * 10)) < 1e-4)), 4),
                diff_to_grid_mean=round(float(np.mean(z[both] - old[both])), 4),
                diff_to_grid_std=round(float(np.std(z[both] - old[both])), 4))


def main(work):
    rows = json.load(open(os.path.join(SRC, "index.json")))
    geo = {r["name"]: np.load(os.path.join(SRC, r["name"] + ".npz")) for r in rows}
    need = sorted({c for r in rows for c in patch_sheets(geo[r["name"]]["origin_xy"], geo[r["name"]]["tangent"],
                                                          geo[r["name"]]["normal"])})
    download(need, work)
    os.makedirs(OUT, exist_ok=True)
    out = []
    for r in rows:
        d = geo[r["name"]]
        codes = patch_sheets(d["origin_xy"], d["tangent"], d["normal"])
        points = [p for p in (load_sheet(work, c) for c in codes) if p is not None]
        elev, npts = grid_patch(points, d["origin_xy"], d["tangent"], d["normal"])
        np.savez_compressed(os.path.join(OUT, r["name"] + ".npz"), elev=elev, npts=npts, origin_xy=d["origin_xy"],
                            tangent=d["tangent"], normal=d["normal"], res=RES)
        row = dict(name=r["name"], X=r["X"], Y=r["Y"], lat=r["lat"], lon=r["lon"], split=r["split"], sheets=codes)
        row.update(stats(elev, d["elev"]))
        out.append(row)
        print(r["name"], row["nan_frac"], row["on_0p1_grid"], row["diff_to_grid_mean"], row["diff_to_grid_std"],
              flush=True)
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1])
