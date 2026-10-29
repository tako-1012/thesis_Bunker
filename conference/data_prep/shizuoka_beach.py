#!/usr/bin/env python3
"""Cut 200 m x 200 m real-beach patches from the Shizuoka ALB 0.5 m grid (VIRTUAL SHIZUOKA).

Source: Shizuoka Prefecture, "VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ" (ALB grid data, 0.5 m,
JGD2024 / plane rectangular zone VIII, heights T.P.), CC BY 4.0 / ODbL.

Steps (needs network access to the two S3 hosts below):
  1. download the file list and the grid ZIPs of the Enshu-nada coast (sheets 08OB8*, 08OC*, 08PC*, 08PD0*, 08PD1*);
  2. paste each 3 km x 4 km level-5000 sheet into a 0.5 m array (NaN = no data);
  3. walk along the shoreline (z = 0 m T.P.) every 250 m, fit the local shore direction by PCA over +-100 m,
     and resample a patch with bilinear interpolation: x along the shore (-100..100 m),
     y from the sea to the land (-50..150 m). Cells that touch missing data stay NaN;
  4. keep patches with < 30 % NaN and a median land width >= 60 m, sort them west to east,
     take 60 evenly spaced ones and mark every fifth (index % 5 == 2) as validation.

Usage (from conference/): python3 data_prep/shizuoka_beach.py <work_dir>
Output: data/shizuoka_beach/<sheet>_<offset>.npz (elev float32 [m], origin_xy, tangent, normal, res) + index.json
"""
import glob
import io
import json
import math
import os
import shutil
import sys
import urllib.request
import zipfile
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation, map_coordinates

RES = 0.5
LIST_URL = ("https://gsic-opendata.s3.ap-northeast-1.amazonaws.com/local-gov/shizuoka/point-cloud/2025/"
            "shizuoka-2025-pointcloud-alb/mw/ALB/etc/file_itiran.zip")
GRID_URL = "https://virtual-shizuoka.s3.ap-northeast-1.amazonaws.com/2025/ALB/Grid/08/{a}/{b}/{code}.zip"
PREFIXES = ("08OB8", "08OB9", "08OC", "08PC", "08PD0", "08PD1")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "shizuoka_beach")


def sheet_origin(code):
    """North-west corner (X max, Y min) [m] of a level-500 sheet code such as 08OC9220."""
    r, c = ord(code[2]) - 65, ord(code[3]) - 65
    a, b, d, e = map(int, code[4:8])
    return 300000 - r * 30000 - a * 3000 - d * 300, -160000 + c * 40000 + b * 4000 + e * 400


def download(work):
    os.makedirs(work, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(LIST_URL).read())) as z:
        codes = [c.strip().upper() for c in z.read("file_itiran_grd.txt").decode("utf-8-sig").split()]
    for code in codes:
        path = os.path.join(work, code + ".zip")
        if code.startswith(PREFIXES) and not os.path.exists(path):
            url = GRID_URL.format(a=code[2:4], b=code[4:6], code=code)
            try:
                urllib.request.urlretrieve(url, path)
            except OSError as exc:
                print("skip", code, exc)


def extract(work, tmp):
    os.makedirs(tmp, exist_ok=True)
    groups = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(work, "*.zip"))):
        groups[os.path.basename(f)[:6].upper()].append(f)
    xs = (np.arange(400) + 0.5) * RES - 100
    ys = (np.arange(400) + 0.5) * RES - 50
    XX, YY = np.meshgrid(xs, ys, indexing="ij")
    for grp, files in sorted(groups.items()):
        X0, Y0 = sheet_origin(grp + "00")
        G = np.full((6000, 8000), np.nan, np.float32)
        for f in files:
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    a = pd.read_csv(z.open(n), header=None).to_numpy(float)
                    i = np.rint((X0 - a[:, 2]) / RES - 0.5).astype(int)
                    j = np.rint((a[:, 1] - Y0) / RES - 0.5).astype(int)
                    ok = (i >= 0) & (i < 6000) & (j >= 0) & (j < 8000)
                    G[i[ok], j[ok]] = a[ok, 3]
        valid = np.isfinite(G).astype(np.float32)
        Gz = np.nan_to_num(G, nan=0.0)
        shore = (G > 0) & binary_dilation(G <= 0, iterations=1)
        pi, pj = np.nonzero(shore)
        if len(pi) < 500:
            continue
        P = np.c_[pi, pj].astype(float) * RES
        u = np.linalg.svd(P - P.mean(0), full_matrices=False)[2][0]
        s = (P - P.mean(0)) @ u
        for s0 in np.arange(s.min() + 100, s.max() - 100, 250):
            sel = np.abs(s - s0) < 100
            if sel.sum() < 100:
                continue
            Q = P[sel]
            cq = Q.mean(0)
            t = np.linalg.svd(Q - cq, full_matrices=False)[2][0]
            nrm = np.array([-t[1], t[0]])
            probe = (cq + 30 * nrm) / RES
            if not G[int(np.clip(probe[0], 0, 5999)), int(np.clip(probe[1], 0, 7999))] > 0:
                nrm = -nrm
            if t[1] < 0:
                t = -t
            pts = (cq[None, None, :] + XX[..., None] * t + YY[..., None] * nrm) / RES
            z = map_coordinates(Gz, [pts[..., 0], pts[..., 1]], order=1, mode="constant", cval=0.0)
            v = map_coordinates(valid, [pts[..., 0], pts[..., 1]], order=1, mode="constant", cval=0.0)
            z = np.where(v > 0.999, z, np.nan).astype(np.float32)
            if np.isnan(z).mean() > 0.35 or np.median((z > 0).sum(1)) * RES < 50:
                continue
            np.savez_compressed(os.path.join(tmp, f"{grp}_{int(s0):05d}.npz"), elev=z,
                                origin_xy=np.array([X0 - cq[0], Y0 + cq[1]]), tangent=t, normal=nrm, res=RES)
        print(grp, "done", flush=True)


def select(tmp):
    rows = []
    for f in sorted(glob.glob(os.path.join(tmp, "*.npz"))):
        d = np.load(f)
        z = d["elev"].astype(float)
        land = z > 0
        gx, gy = np.gradient(z, RES)
        sl = np.degrees(np.arctan(np.hypot(gx, gy)))
        X, Y = d["origin_xy"]
        lat = 36 + X / 111000
        lon = 138.5 + Y / (111320 * math.cos(math.radians(lat)))
        rows.append(dict(name=os.path.basename(f)[:-4], X=float(X), Y=float(Y), lat=round(lat, 4), lon=round(lon, 4),
                         nan_frac=round(float(np.isnan(z).mean()), 4),
                         land_width_m=float(np.median(land.sum(1)) * RES), zmax=round(float(np.nanmax(z)), 3),
                         steep_land=round(float((sl[land & np.isfinite(sl)] > 25).mean()), 5)))
    ok = sorted((r for r in rows if r["nan_frac"] < 0.30 and r["land_width_m"] >= 60), key=lambda r: r["Y"])
    sel = [ok[i] for i in np.unique(np.round(np.linspace(0, len(ok) - 1, 60)).astype(int))]
    os.makedirs(OUT, exist_ok=True)
    for i, r in enumerate(sel):
        r["split"] = "validation" if i % 5 == 2 else "test"
        shutil.copy(os.path.join(tmp, r["name"] + ".npz"), os.path.join(OUT, r["name"] + ".npz"))
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(sel, f, indent=1, ensure_ascii=False)
    print(len(rows), "patches,", len(ok), "pass the quality filter,", len(sel), "kept")


if __name__ == "__main__":
    work = sys.argv[1]
    download(os.path.join(work, "zip"))
    extract(os.path.join(work, "zip"), os.path.join(work, "patches"))
    select(os.path.join(work, "patches"))
