"""Terrain around downtown Bogotá from the public AWS Terrain Tiles (terrarium PNG, SRTM-based).
Writes a height grid in local metres (origin Torre Colpatria, z relative to its base).
    python3 fetch_dem.py OUT.npz"""
import io, math, os, sys, subprocess
import numpy as np
from PIL import Image

LAT0, LON0 = 4.6109936, -74.0702477
KX = 111320.0 * math.cos(math.radians(LAT0)); KY = 110574.0
Z = 14
X0, X1, Y0, Y1, RES = -6000, 7000, -6000, 7000, 10.0


def tile_xy(lat, lon):
    n = 2 ** Z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


cache = {}


def tile(tx, ty):
    if (tx, ty) not in cache:
        raw = subprocess.run(["curl", "-sS", "-m", "60", "--retry", "3",
                              f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png"],
                             check=True, capture_output=True).stdout
        a = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(np.float64)
        cache[(tx, ty)] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    return cache[(tx, ty)]


xs = np.arange(X0, X1 + 1, RES); ys = np.arange(Y0, Y1 + 1, RES)
H = np.zeros((len(ys), len(xs)))
for j, y in enumerate(ys):
    lat = LAT0 + y / KY
    for i, x in enumerate(xs):
        lon = LON0 + x / KX
        fx, fy = tile_xy(lat, lon)
        tx, ty = int(fx), int(fy)
        px, py = (fx - tx) * 256 - 0.5, (fy - ty) * 256 - 0.5
        ix, iy = int(np.clip(math.floor(px), 0, 254)), int(np.clip(math.floor(py), 0, 254))
        u, v = np.clip(px - ix, 0, 1), np.clip(py - iy, 0, 1)
        t = tile(tx, ty)
        H[j, i] = (t[iy, ix] * (1 - u) * (1 - v) + t[iy, ix + 1] * u * (1 - v) +
                   t[iy + 1, ix] * (1 - u) * v + t[iy + 1, ix + 1] * u * v)
base = H[np.argmin(np.abs(ys)), np.argmin(np.abs(xs))]
np.savez_compressed(sys.argv[1], H=(H - base).astype(np.float32), xs=xs, ys=ys, base=base)
print("tiles", len(cache), "base", round(base, 1), "range", round(H.min() - base, 1), round(H.max() - base, 1))
