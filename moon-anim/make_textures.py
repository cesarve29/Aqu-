"""Texturas 2D procedurales: destello de 4 puntas y halo radial (para efectos de brillo)."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def save_rgba(rgb, a, name):
    img = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])
    Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(OUT, name))


# ------------------------------------------------------------------ destello (4 puntas)
S = 512
yy, xx = (np.mgrid[0:S, 0:S] - S / 2 + 0.5) / (S / 2)
r = np.hypot(xx, yy)
star = np.exp(-np.abs(xx) / 0.5) * np.exp(-(yy / 0.025) ** 2) + np.exp(-np.abs(yy) / 0.5) * np.exp(-(xx / 0.025) ** 2)
rx, ry = (xx + yy) / np.sqrt(2), (xx - yy) / np.sqrt(2)
star += 0.35 * (np.exp(-np.abs(rx) / 0.22) * np.exp(-(ry / 0.02) ** 2) + np.exp(-np.abs(ry) / 0.22) * np.exp(-(rx / 0.02) ** 2))
star += np.exp(-(r / 0.06) ** 2) * 1.5 + np.exp(-(r / 0.25) ** 2) * 0.25
star *= smoothstep(1.0, 0.8, r)
a = np.clip(star, 0, 1)
save_rgba(np.ones((S, S, 3)), a, "sparkle.png")

# ------------------------------------------------------------------ halo radial
S = 1024
yy, xx = (np.mgrid[0:S, 0:S] - S / 2 + 0.5) / (S / 2)
r = np.hypot(xx, yy)
a = np.exp(-((r) / 0.45) ** 2) * smoothstep(1.0, 0.85, r)
save_rgba(np.ones((S, S, 3)), a, "halo.png")
print("ok")
