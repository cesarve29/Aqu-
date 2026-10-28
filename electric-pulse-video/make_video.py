#!/usr/bin/env python3
"""
ELECTRIC PULSE - lyric video 3D
Video musical con letras generado 100% por codigo: motor 3D en software (proyeccion
en perspectiva) con suelo de rejilla neon, ciudad wireframe, tunel de anillos,
poliedros, rayos y campo de estrellas, todo reactivo al audio (bombo/graves/espectro).
Las letras son tipografia extruida en 3D, con brillo neon, que entra palabra a palabra
sincronizada con los tiempos incrustados en el .m4a y gira en el espacio.

Uso:
    python3 make_video.py                  -> electric_pulse_1080p.mp4 (1920x1080, 30 fps)
    python3 make_video.py --stills 5 25 60 -> PNGs de esos segundos en stills/ (para revisar)
Requiere: numpy, Pillow, ffmpeg.
"""
import colorsys
import math
import os
import re
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
RW, RH = 960, 540  # el mundo 3D se dibuja a media resolucion y se escala; el texto va a 1080p
HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "electric_pulse.m4a")
OUT = os.path.join(HERE, "electric_pulse_1080p.mp4")
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-BlackItalic.otf"
FONT_UI = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
SR = 22050

KEYWORDS = {
    "night", "neon", "dreams", "electric", "tides", "lights", "sky", "fly", "pulse",
    "shake", "jolt", "veins", "revolt", "strobe-lit", "digital", "bassline", "circuit",
    "sparks", "ignite", "right",
}


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t ** 3


def back_out(t, k=2.2):
    t = clamp(t) - 1
    return 1 + (k + 1) * t ** 3 + k * t ** 2


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def hsv(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def scale_col(c, k):
    return tuple(int(clamp(v * k, 0, 255)) for v in c)


def mixc(a, b, t):
    t = clamp(t)
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


# ----------------------------------------------------------------------------
# letras (pista de subtitulos / metadato incrustado en el m4a)
# ----------------------------------------------------------------------------
def load_lyrics():
    srt = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", AUDIO, "-map", "0:s:0", "-f", "srt", "-"],
        capture_output=True, text=True, check=True).stdout
    items = []
    for block in srt.strip().split("\n\n"):
        rows = block.strip().splitlines()
        if len(rows) < 3:
            continue
        a, b = re.findall(r"(\d+):(\d+):(\d+),(\d+)", rows[1])
        t0 = int(a[0]) * 3600 + int(a[1]) * 60 + int(a[2]) + int(a[3]) / 1000
        t1 = int(b[0]) * 3600 + int(b[1]) * 60 + int(b[2]) + int(b[3]) / 1000
        text = " ".join(rows[2:]).strip()
        items.append((t0, t1, text))
    lines, section = [], "verse"
    for t0, t1, text in items:
        if text.startswith("["):
            section = text.strip("[]").lower()
            continue
        lines.append({"t0": t0, "t1": t1, "text": text, "section": section})
    return lines


# ----------------------------------------------------------------------------
# analisis de audio
# ----------------------------------------------------------------------------
def analyze_audio(dur):
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", AUDIO, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    n = int(dur * FPS) + 2
    win = 2048
    pad = np.concatenate([np.zeros(win), a, np.zeros(win)])
    hann = np.hanning(win)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    edges = np.geomspace(40, 9000, 33)
    band_idx = [(np.searchsorted(freqs, edges[i]), max(np.searchsorted(freqs, edges[i + 1]), np.searchsorted(freqs, edges[i]) + 1)) for i in range(32)]
    bass, rms, spec = np.zeros(n), np.zeros(n), np.zeros((n, 32))
    for i in range(n):
        c = int(i / FPS * SR) + win
        seg = pad[c - win // 2:c + win // 2]
        if len(seg) < win:
            continue
        mag = np.abs(np.fft.rfft(seg * hann))
        bass[i] = mag[(freqs > 30) & (freqs < 150)].sum()
        rms[i] = math.sqrt(float(np.mean(seg ** 2)))
        spec[i] = [mag[x:y].mean() for x, y in band_idx]

    def norm(v):
        return np.clip(v / (np.percentile(v, 97) + 1e-9), 0, 1.3)

    bass, rms = norm(bass), norm(rms)
    spec = np.log1p(spec * 4)
    spec = np.clip(spec / (np.percentile(spec, 98, axis=0) + 1e-9), 0, 1.2)
    # bombo: subida brusca de graves con caida exponencial
    flux = np.maximum(0, np.diff(bass, prepend=bass[0]))
    flux = np.clip(flux / (np.percentile(flux, 98) + 1e-9), 0, 1.5)
    kick = np.zeros(n)
    for i in range(n):
        kick[i] = max(flux[i] if flux[i] > 0.25 else 0, (kick[i - 1] if i else 0) * 0.80)
    # suavizados
    bass_s = np.convolve(bass, np.ones(5) / 5, mode="same")
    energy = np.convolve(rms, np.ones(45) / 45, mode="same")
    beats = np.cumsum(flux > 0.45)  # contador de golpes (semillas para rayos, etc.)
    return {"bass": bass_s, "rms": rms, "kick": np.clip(kick, 0, 1.2), "spec": spec,
            "energy": energy, "beats": beats}


# ----------------------------------------------------------------------------
# guion visual por secciones
# ----------------------------------------------------------------------------
PALETTES = {
    # neon principal, neon secundario, extrusion, cielo arriba, cielo horizonte
    "verse":     ((0, 240, 255), (255, 40, 200), (40, 0, 90), (6, 0, 22), (70, 0, 110)),
    "prechorus": ((255, 230, 60), (255, 40, 120), (80, 0, 60), (12, 0, 20), (130, 10, 80)),
    "chorus":    ((255, 40, 200), (0, 255, 230), (60, 0, 110), (10, 0, 30), (90, 0, 140)),
    "verse 2":   ((255, 120, 20), (255, 30, 90), (90, 10, 30), (16, 0, 10), (120, 20, 40)),
    "outro":     ((120, 80, 255), (0, 240, 255), (30, 0, 90), (4, 0, 16), (50, 0, 100)),
}


def build_timeline(lines, dur):
    """Lista de (inicio, seccion). La ultima frase termina a ~106 s: despues, outro."""
    sec = []
    for ln in lines:
        if not sec or sec[-1][1] != ln["section"]:
            sec.append((ln["t0"], ln["section"]))
    last = lines[-1]
    sec.append((last["t1"] + 0.8, "outro"))
    sec[0] = (0.0, sec[0][1])
    return sec


def section_weights(t, timeline, fade=0.9):
    """Pesos suaves por seccion (crossfade alrededor de cada cambio)."""
    w = {}
    for i, (st, name) in enumerate(timeline):
        en = timeline[i + 1][0] if i + 1 < len(timeline) else 1e9
        a = smooth((t - st + fade / 2) / fade) if i else 1.0
        b = 1 - smooth((t - en + fade / 2) / fade)
        v = a * b
        if v > 0:
            w[name] = w.get(name, 0) + v
    return w


def blend_palette(w):
    tot = sum(w.values()) or 1
    out = []
    for k in range(5):
        out.append(tuple(int(sum(PALETTES[n][k][c] * v for n, v in w.items()) / tot) for c in range(3)))
    return out


def chorus_w(w):
    return w.get("chorus", 0)


# ----------------------------------------------------------------------------
# camara y proyeccion
# ----------------------------------------------------------------------------
class Cam:
    def __init__(self, x, y, roll, pitch, yaw, f=560.0):
        self.x, self.y, self.f = x, y, f
        cr, sr_ = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        ry = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
        rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        rz = np.array([[cr, -sr_, 0], [sr_, cr, 0], [0, 0, 1]])
        self.R = rz @ rx @ ry

    def to_cam(self, P):
        P = np.asarray(P, float).reshape(-1, 3) - np.array([self.x, self.y, 0.0])
        return P @ self.R.T

    def proj(self, C):
        z = np.maximum(C[:, 2], 1e-3)
        return np.stack([RW / 2 + self.f * C[:, 0] / z, RH * 0.5 - self.f * C[:, 1] / z], 1)

    def segments(self, A, B, near=0.25):
        """Proyecta segmentos 3D (Nx3, Nx3) recortando contra el plano cercano.
        Devuelve (pts_a, pts_b, z_medio, ok)."""
        CA, CB = self.to_cam(A), self.to_cam(B)
        za, zb = CA[:, 2], CB[:, 2]
        ok = (za > near) | (zb > near)
        t = np.where(za < near, (near - za) / (zb - za + 1e-9), 0)[:, None]
        CA = np.where((za < near)[:, None], CA + (CB - CA) * t, CA)
        t = np.where(zb < near, (near - zb) / (za - zb + 1e-9), 0)[:, None]
        CB = np.where((zb < near)[:, None], CB + (CA - CB) * t, CB)
        return self.proj(CA), self.proj(CB), (CA[:, 2] + CB[:, 2]) / 2, ok


def draw_segs(dr, cam, A, B, color, width=2, zfade=60.0, minw=1):
    pa, pb, zm, ok = cam.segments(A, B)
    for i in np.nonzero(ok)[0]:
        k = clamp(1.0 - zm[i] / zfade, 0.0, 1.0) ** 1.3
        if k < 0.02:
            continue
        w = max(minw, int(round(width * clamp(6.0 / max(zm[i], 0.5), 0.4, 1.6))))
        dr.line([tuple(pa[i]), tuple(pb[i])], fill=scale_col(color, k), width=w)


# ----------------------------------------------------------------------------
# elementos del mundo
# ----------------------------------------------------------------------------
@lru_cache(maxsize=None)
def vignette():
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return np.clip(1.15 - 0.45 * d ** 2, 0.35, 1.0).astype(np.float32)[..., None]


def sky(pal, horizon):
    top, bot = np.array(pal[3], float), np.array(pal[4], float)
    y = np.arange(RH, dtype=float)[:, None]
    t = np.clip(y / max(horizon, 1), 0, 1) ** 1.6
    col = top * (1 - t) + bot * t
    below = y >= horizon
    col = np.where(below, np.array([4, 0, 10], float), col)
    return np.repeat(col[:, None, :], RW, 1).reshape(RH, RW, 3)


@lru_cache(maxsize=8)
def sun_sprite(r, c1, c2):
    s = 2 * r + 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    arr = np.zeros((s, s, 4), np.float32)
    yy, xx = np.mgrid[0:s, 0:s]
    d = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2)
    inside = d < r
    t = (yy / s)[..., None]
    col = np.array(c1) * (1 - t) + np.array(c2) * t
    # franjas horizontales en la mitad inferior (sol synthwave)
    yn = (yy - s / 2) / r
    gap = (yn > 0.05) & (np.mod(yn * 10 + yn ** 2 * 8, 1.6) < 0.35 + yn * 0.5)
    a = inside & ~gap
    arr[..., :3] = col
    arr[..., 3] = a * 255
    im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return im


def make_city(seed=3):
    rng = np.random.default_rng(seed)
    boxes = []
    for side in (-1, 1):
        z = 0.0
        while z < 140:
            w = rng.uniform(2.0, 5.0)
            d = rng.uniform(2.0, 5.0)
            h = rng.uniform(3, 20) * (1.4 if rng.random() < 0.15 else 1)
            x = side * rng.uniform(7, 16)
            boxes.append((x, z, w, d, h))
            z += d + rng.uniform(1.0, 4.0)
    return boxes


CITY = make_city()
CITY_LEN = 140.0


def box_edges(x, y0, z, w, d, h):
    xs, zs = (x - w / 2, x + w / 2), (z, z + d)
    v = [(xs[i], y0 + h * k, zs[j]) for k in (0, 1) for j in (0, 1) for i in (0, 1)]
    e = [(0, 1), (2, 3), (0, 2), (1, 3), (4, 5), (6, 7), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    return np.array(v), e


def hull(pts):
    pts = sorted(set(map(tuple, np.round(pts, 1))))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def draw_city(dr, cam, travel, floor_y, pal, amount, bass):
    if amount <= 0.02:
        return
    items = []
    for (x, z0, w, d, h) in CITY:
        z = (z0 - travel) % CITY_LEN - 4
        items.append((z, x, w, d, h * (1 + 0.25 * bass * (abs(x) < 12))))
    items.sort(key=lambda b: -b[0])
    for z, x, w, d, h in items:
        V, E = box_edges(x, floor_y, z, w, d, h)
        C = cam.to_cam(V)
        if (C[:, 2] < 0.5).any():
            continue
        P = cam.proj(C)
        zf = clamp(1 - z / 120, 0, 1) * amount
        if zf < 0.03:
            continue
        hp = hull(P)
        if len(hp) >= 3:
            dr.polygon(hp, fill=scale_col((10, 0, 24), 1.0))
        edge = mixc(pal[1], pal[0], (math.sin(x * 3.1 + z0) + 1) / 2)
        for a, b in E:
            dr.line([tuple(P[a]), tuple(P[b])], fill=scale_col(edge, zf), width=1)
        # ventanas: puntos de luz en la cara que mira a la carretera
        fx = x - np.sign(x) * w / 2
        rng = np.random.default_rng(int(z0 * 10))
        nwin = int(h * 1.2)
        wy = floor_y + rng.uniform(0.5, h - 0.3, nwin)
        wz = z + rng.uniform(0.2, d - 0.2, nwin)
        Wp = cam.proj(cam.to_cam(np.stack([np.full(nwin, fx), wy, wz], 1)))
        wc = scale_col(pal[0] if rng.random() < 0.5 else (255, 220, 140), zf * 0.9)
        for p in Wp:
            dr.rectangle([p[0], p[1], p[0] + 1, p[1] + 1], fill=wc)


def draw_grid(dr, cam, travel, floor_y, pal, amount, kick):
    if amount <= 0.02:
        return
    zmax, step = 70.0, 2.0
    col = scale_col(pal[1], amount * (0.8 + 0.5 * kick))
    xs = np.arange(-30, 31) * step
    A = np.stack([xs, np.full_like(xs, floor_y), np.full_like(xs, 0.3)], 1)
    B = np.stack([xs, np.full_like(xs, floor_y), np.full_like(xs, zmax)], 1)
    draw_segs(dr, cam, A, B, col, width=2, zfade=zmax)
    zs = np.arange(0, 36) * step + (-travel % step)
    A = np.stack([np.full_like(zs, -60), np.full_like(zs, floor_y), zs], 1)
    B = np.stack([np.full_like(zs, 60), np.full_like(zs, floor_y), zs], 1)
    draw_segs(dr, cam, A, B, col, width=2, zfade=zmax)


def draw_tunnel(dr, cam, travel, t, pal, amount, kick, bass):
    if amount <= 0.02:
        return
    spacing, n = 3.0, 22
    off = travel % spacing
    sides = 6
    for k in range(n, 0, -1):
        z = k * spacing - off
        if z < 0.6:
            continue
        r = 4.2 * (1 + 0.18 * kick * math.exp(-z / 25))
        rot = z * 0.07 + t * 0.4
        ang = rot + np.arange(sides + 1) * 2 * math.pi / sides
        P = np.stack([r * np.cos(ang), r * np.sin(ang) + 0.6, np.full(sides + 1, z + travel * 0)], 1)
        P[:, 0] += cam.x
        P[:, 1] += cam.y - 0.3
        hue = (t * 0.05 + k * 0.035) % 1.0
        c = mixc(hsv(hue, 0.85, 1.0), pal[0], 0.35)
        fade = clamp(1 - z / (n * spacing), 0, 1) ** 1.2 * amount
        draw_segs(dr, cam, P[:-1], P[1:], scale_col(c, fade * 1.3), width=3, zfade=200)


ICO_V = None
ICO_E = None


def icosa():
    global ICO_V, ICO_E
    if ICO_V is None:
        p = (1 + 5 ** 0.5) / 2
        v = []
        for a in (-1, 1):
            for b in (-p, p):
                v += [(0, a, b), (a, b, 0), (b, 0, a)]
        V = np.array(v, float)
        V /= np.linalg.norm(V[0])
        E = [(i, j) for i in range(12) for j in range(i + 1, 12)
             if abs(np.linalg.norm(V[i] - V[j]) - 1.0515) < 0.05]
        ICO_V, ICO_E = V, E
    return ICO_V, ICO_E


def rot_mat(ax, ay, az):
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    return (np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]) @
            np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @
            np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]))


def draw_poly(dr, cam, t, pal, amount, bass, center, size):
    if amount <= 0.02:
        return
    V, E = icosa()
    R = rot_mat(t * 0.5, t * 0.73, t * 0.21)
    for shell, sc in ((0, 1.0), (1, 0.55)):
        Vr = (V @ R.T if shell == 0 else V @ R) * size * sc * (1 + 0.25 * bass) + np.array(center)
        A = np.array([Vr[a] for a, b in E])
        B = np.array([Vr[b] for a, b in E])
        c = pal[0] if shell == 0 else pal[1]
        draw_segs(dr, cam, A, B, scale_col(c, amount), width=3, zfade=80)


def draw_stars(dr, cam, travel, t, amount, speed):
    if amount <= 0.02:
        return
    rng = np.random.default_rng(11)
    n = 260
    X = rng.uniform(-40, 40, n) + cam.x
    Y = rng.uniform(-8, 30, n)
    Z0 = rng.uniform(0, 90, n)
    Z = (Z0 - travel * 1.5) % 90 + 1
    A = np.stack([X, Y, Z], 1)
    B = np.stack([X, Y, Z + 0.15 + speed * 0.06], 1)
    pa, pb, zm, ok = cam.segments(A, B)
    for i in np.nonzero(ok)[0]:
        k = clamp(1 - zm[i] / 90, 0, 1) * amount
        dr.line([tuple(pa[i]), tuple(pb[i])], fill=scale_col((220, 230, 255), k), width=2 if zm[i] < 15 else 1)


def draw_lightning(dr, seed, age, pal):
    if age > 0.22:
        return
    rng = np.random.default_rng(seed)
    x = rng.uniform(RW * 0.15, RW * 0.85)
    y = 0.0
    pts = [(x, y)]
    while y < RH * 0.55:
        y += rng.uniform(12, 30)
        x += rng.uniform(-28, 28)
        pts.append((x, y))
    k = 1 - age / 0.22
    dr.line(pts, fill=scale_col((255, 255, 255), k), width=4)
    dr.line(pts, fill=scale_col(pal[0], k), width=2)
    for j in range(2, len(pts) - 2, 3):
        bx, by = pts[j]
        br = [(bx, by)]
        for _ in range(4):
            bx += rng.uniform(-26, 26)
            by += rng.uniform(8, 20)
            br.append((bx, by))
        dr.line(br, fill=scale_col(pal[0], k * 0.8), width=2)


def draw_spectrum(dr, spec, pal, amount):
    """Ecualizador espejado en la parte baja del encuadre."""
    if amount <= 0.02:
        return
    n = len(spec)
    bw = RW / (2 * n + 6)
    base = RH - 14
    for i in range(n):
        v = float(spec[i])
        h = 3 + v * 48
        c = mixc(pal[0], pal[1], i / n)
        c = scale_col(c, amount * 0.85)
        for sgn in (-1, 1):
            cx = RW / 2 + sgn * (i + 0.5) * bw * 1.05
            dr.rectangle([cx - bw * 0.38, base - h, cx + bw * 0.38, base], fill=c)


# ----------------------------------------------------------------------------
# texto 3D extruido
# ----------------------------------------------------------------------------
@lru_cache(maxsize=16)
def font(size, ui=False):
    return ImageFont.truetype(FONT_UI if ui else FONT, size)


def _shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    if dx >= 0 and dy >= 0:
        out[dy:, dx:] = m[:h - dy, :w - dx]
    return out


@lru_cache(maxsize=512)
def word_sprite(word, size, face_a, face_b, side, glow, accent):
    """Palabra con extrusion 3D, contorno, degradado frontal, brillo y halo neon (RGBA)."""
    f = font(size)
    l, t, r, b = f.getbbox(word, anchor="ls")
    depth = int(size * 0.13)
    stroke = max(3, size // 26)
    gr = int(size * 0.16)
    pad = stroke + gr + 4
    w = r - l + 2 * pad + depth
    h = b - t + 2 * pad + depth
    ox, oy = pad - l, pad - t

    def mask(sw):
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((ox, oy), word, font=f, anchor="ls", fill=255, stroke_width=sw, stroke_fill=255)
        return np.asarray(im, np.float32) / 255.0

    m_face = mask(0)
    m_out = mask(stroke)
    rgb = np.zeros((h, w, 3), np.float32)
    al = np.zeros((h, w), np.float32)

    def over(c, a):
        nonlocal rgb, al
        a = a[..., None]
        rgb = rgb * (1 - a) + np.array(c, np.float32) * a
        al = np.maximum(al, a[..., 0])

    # halo neon (debajo de todo)
    g = Image.fromarray((m_out * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(gr * 0.55))
    ga = np.asarray(g, np.float32) / 255.0
    halo_a = np.clip(ga * 1.25, 0, 0.9)
    rgb = np.array(glow, np.float32) * np.ones((h, w, 1), np.float32)
    al = halo_a.copy()
    # extrusion: capas desde el fondo hacia la cara frontal
    sideA = np.array(side, np.float32)
    sideB = np.array(glow, np.float32) * 0.55 + sideA * 0.45
    for k in range(depth, 0, -1):
        dx, dy = int(round(k * 0.45)), int(round(k * 0.9))
        u = k / depth
        c = sideB * (1 - u) + sideA * u
        lit = 0.55 + 0.45 * (1 - u)
        over(tuple(c * lit), _shift(m_out, dx, dy))
    # contorno oscuro + cara con degradado vertical
    over((8, 0, 20), m_out)
    yy = np.linspace(0, 1, h)[:, None, None]
    ys = (yy - (oy - size * 0.75) / h) / (size * 0.85 / h)
    ys = np.clip(ys, 0, 1)
    fa, fb = np.array(face_a, np.float32), np.array(face_b, np.float32)
    face = fa * (1 - ys) + fb * ys
    if accent:
        # franja brillante diagonal tipo cromo
        xx = np.linspace(0, 1, w)[None, :, None]
        band = np.exp(-((ys - 0.48 + (xx - 0.5) * 0.25) ** 2) / 0.004)
        face = face * (1 - 0.6 * band) + 255 * 0.6 * band
    a = m_face[..., None]
    rgb = rgb * (1 - a) + face * a
    al = np.maximum(al, m_face)
    # brillo superior (bisel)
    rim = np.clip(m_face - _shift(m_face, 0, max(2, size // 40)), 0, 1)[..., None] * 0.8
    rgb = rgb * (1 - rim) + 255 * rim
    out = np.dstack([np.clip(rgb, 0, 255), al * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA"), ox, oy


def layout(text, chorus):
    words = text.split()
    size = 230 if chorus else 200
    maxw = 1500
    while True:
        f = font(size)
        sp = f.getlength(" ") * 1.1
        rows, cur, cw = [], [], 0
        for wd in words:
            wl = f.getlength(wd)
            if cur and cw + sp + wl > maxw:
                rows.append(cur)
                cur, cw = [], 0
            cw += (sp if cur else 0) + wl
            cur.append(wd)
        rows.append(cur)
        widest = max(sum(f.getlength(x) for x in r) + sp * (len(r) - 1) for r in rows)
        if (len(rows) <= 2 and widest <= maxw) or size <= 90:
            break
        size -= 10
    lh = size * 1.12
    placed = []
    for ri, r in enumerate(rows):
        rw = sum(f.getlength(x) for x in r) + sp * (len(r) - 1)
        x = -rw / 2
        y = (ri - (len(rows) - 1) / 2) * lh + size * 0.35  # linea base
        for wd in r:
            placed.append((wd, x, y))
            x += f.getlength(wd) + sp
    return size, placed, len(rows) * lh


def homography(src, dst):
    """Coeficientes PIL PERSPECTIVE que mapean puntos de dst (salida) a src (entrada)."""
    A, bvec = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        bvec += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(bvec, float)).tolist()


def place_3d(cw, ch, cx, cy, z, yaw, pitch, roll, f=1700.0):
    pts = []
    R = rot_mat(pitch, yaw, roll)
    for (x, y) in ((0, 0), (cw, 0), (cw, ch), (0, ch)):
        P = R @ np.array([x - cw / 2, y - ch / 2, 0.0])
        zz = max(P[2] + z + f, 50)
        pts.append((cx + f * P[0] / zz, cy + f * P[1] / zz))
    return pts


def render_line(frame, ln, t, pal, kick, chorus, shake):
    t0, t1 = ln["t0"], ln["t1"]
    if t < t0 - 0.35 or t > t1 + 0.35:
        return
    size, placed, block_h = layout(ln["text"], chorus > 0.5)
    words = [p[0] for p in placed]
    # tiempos por palabra: se reparten en el primer 55% de la frase segun su longitud
    dur = max(0.4, t1 - t0)
    span = min(dur * 0.55, 0.42 * len(words))
    lens = np.array([len(w) + 2 for w in words], float)
    starts = t0 - 0.12 + np.concatenate([[0], np.cumsum(lens)[:-1]]) / lens.sum() * span
    # lienzo de la frase
    margin = int(size * 0.6)
    xs = [p[1] for p in placed]
    cw = int(max(abs(min(xs)), abs(max(xs) + font(size).getlength(placed[-1][0]))) * 2 + 2 * margin + size * 0.5)
    ch = int(block_h + 2 * margin + size * 0.5)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    face_a, face_b = (255, 255, 255), mixc(pal[0], (255, 255, 255), 0.15)
    acc_a, acc_b = mixc(pal[1], (255, 255, 255), 0.55), pal[1]
    for (wd, x, y), st in zip(placed, starts):
        age = t - st
        if age < 0:
            continue
        accent = re.sub(r"[^a-z\-]", "", wd.lower()) in KEYWORDS
        spr, ox, oy = word_sprite(
            wd, size, face_a if not accent else acc_a, face_b if not accent else acc_b,
            pal[2], pal[1] if not accent else pal[0], accent)
        p = clamp(age / 0.32)
        sc = 1.9 - 0.9 * back_out(p) if p < 1 else 1.0
        if accent:
            sc *= 1 + 0.06 * kick
        a = ease_out(age / 0.18)
        sw, sh = max(1, int(spr.width * sc)), max(1, int(spr.height * sc))
        s2 = spr.resize((sw, sh), Image.BILINEAR) if sc != 1.0 else spr
        if a < 1:
            s2 = s2.copy()
            s2.putalpha(s2.getchannel("A").point(lambda v, a=a: int(v * a)))
        px = cw / 2 + x - ox * sc - (sc - 1) * (spr.width - 2 * ox) * 0.5 * 0.3
        py = ch / 2 + y - oy * sc + (1 - sc) * size * 0.3
        canvas.alpha_composite(s2, (int(px), int(py)))
    # entrada desde el fondo y salida hacia la camara
    enter = ease_out((t - (t0 - 0.35)) / 0.45)
    leave = ease_in((t - (t1 - 0.22)) / 0.5)
    z = (1 - enter) * 1400 - leave * 1300 - 90 * kick * chorus
    alpha = clamp(enter * 1.5) * (1 - clamp(leave * 1.4))
    if alpha <= 0.01:
        return
    if alpha < 1:
        canvas.putalpha(canvas.getchannel("A").point(lambda v: int(v * alpha)))
    seed = (sum(map(ord, ln["text"])) * 37 % 1000) / 1000 * 6.28
    yaw = 0.30 * math.sin(t * 0.55 + seed) + (1 - enter) * 0.6 * (1 if seed > 3 else -1)
    pitch = 0.14 * math.sin(t * 0.43 + seed * 0.7) - 0.04 + (1 - enter) * 0.4
    roll = 0.04 * math.sin(t * 0.31 + seed) + leave * 0.25
    cx = W / 2 + shake[0]
    cy = H * 0.47 + shake[1]
    dst = place_3d(cw, ch, cx, cy, z, yaw, pitch, roll)
    coeffs = homography([(0, 0), (cw, 0), (cw, ch), (0, ch)], dst)
    layer = canvas.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    frame.alpha_composite(layer)


def render_title(frame, t, start, end, pal, kick):
    """Titulo final: ELECTRIC / PULSE girando en 3D."""
    if t < start:
        return
    k = ease_out((t - start) / 1.4)
    out = 1 - smooth((t - (end - 2.5)) / 2.0)
    canvas = Image.new("RGBA", (1900, 760), (0, 0, 0, 0))
    for i, (wd, size) in enumerate((("ELECTRIC", 250), ("PULSE", 330))):
        spr, ox, oy = word_sprite(wd, size, mixc(pal[1], (255, 255, 255), 0.6), pal[1], pal[2], pal[0], True)
        canvas.alpha_composite(spr, (int(950 - (spr.width - 2 * ox + size * 0.13) / 2 - ox + ox * 0),
                                     int(40 + i * 300 - (oy - size)) ))
    a = k * out
    if a <= 0.01:
        return
    canvas.putalpha(canvas.getchannel("A").point(lambda v: int(v * a)))
    yaw = 0.45 * math.sin((t - start) * 0.5) * (1 - k * 0.3)
    pitch = 0.18 * math.sin((t - start) * 0.37) + (1 - k) * 0.9
    z = (1 - k) * 2500 - 120 * kick
    dst = place_3d(1900, 760, W / 2, H * 0.46, z, yaw, pitch, 0.03 * math.sin(t))
    coeffs = homography([(0, 0), (1900, 0), (1900, 760), (0, 760)], dst)
    frame.alpha_composite(canvas.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BILINEAR))


# ----------------------------------------------------------------------------
# fotograma completo
# ----------------------------------------------------------------------------
G = {}


def init_worker(lines, timeline, audio, dur):
    G.update(lines=lines, timeline=timeline, audio=audio, dur=dur)
    # recorrido acumulado de la camara (velocidad depende de la seccion y de los graves)
    n = len(audio["bass"])
    travel = np.zeros(n)
    for i in range(1, n):
        t = i / FPS
        w = section_weights(t, timeline)
        sp = 6 + 10 * w.get("chorus", 0) + 5 * w.get("prechorus", 0) + 3 * w.get("verse 2", 0)
        sp *= 0.75 + 0.6 * audio["bass"][i]
        travel[i] = travel[i - 1] + sp / FPS
    G["travel"] = travel


def render_frame(i):
    t = i / FPS
    A, lines, timeline, dur = G["audio"], G["lines"], G["timeline"], G["dur"]
    j = min(i, len(A["bass"]) - 1)
    bass, kick, energy, spec = A["bass"][j], A["kick"][j], A["energy"][j], A["spec"][j]
    w = section_weights(t, timeline)
    pal = blend_palette(w)
    ch = w.get("chorus", 0)
    pre = w.get("prechorus", 0)
    v2 = w.get("verse 2", 0)
    v1 = w.get("verse", 0)
    outro = w.get("outro", 0)
    travel = G["travel"][j]
    fade_in = smooth(t / 1.2)
    fade_out = 1 - smooth((t - (dur - 2.2)) / 2.0)

    # camara
    sway = math.sin(t * 0.35)
    cam_y = 1.4 + 0.35 * math.sin(t * 0.5) + pre * 1.2 + outro * 1.5
    roll = 0.06 * math.sin(t * 0.42) + ch * 0.05 * math.sin(t * 1.1)
    pitch = -0.02 + 0.03 * math.sin(t * 0.3) - pre * 0.06
    cam = Cam(1.2 * sway, cam_y, roll, pitch, 0.04 * math.sin(t * 0.27))
    horizon = int(cam.proj(cam.to_cam([[cam.x, cam.y, 1e4]]))[0, 1])

    # mundo 3D a media resolucion
    bg = sky(pal, horizon)
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), "RGB")
    dr = ImageDraw.Draw(img)
    sun_r = int(120 + 18 * bass)
    sun_amt = clamp(1 - ch * 0.6)
    if sun_amt > 0.05:
        sun = sun_sprite(sun_r, (255, 240, 120), pal[1])
        sp = cam.proj(cam.to_cam([[cam.x, cam.y + 900, 6000]]))[0]
        if sun_amt < 1:
            sun = sun.copy()
            sun.putalpha(sun.getchannel("A").point(lambda v: int(v * sun_amt)))
        img.paste(sun, (int(sp[0] - sun.width / 2), int(min(sp[1], horizon - sun_r * 0.35) - sun.height / 2)), sun)
        # cortar el sol por debajo del horizonte
        dr.rectangle([0, horizon, RW, RH], fill=(4, 0, 10))
    floor_y = 0.0
    draw_stars(dr, cam, travel, t, 0.6 + 0.4 * ch + outro, 6 + 10 * ch)
    draw_grid(dr, cam, travel, floor_y, pal, 1.0, kick)
    draw_city(dr, cam, travel, floor_y, pal, clamp(v1 + pre + v2 * 0.8 + outro * 0.6), bass)
    draw_tunnel(dr, cam, travel, t, pal, ch, kick, bass)
    draw_poly(dr, cam, t, pal, v2 + outro * 0.0, bass, (cam.x, cam.y + 2.2, 16), 3.2)
    if pre > 0.3 or ch > 0.3:
        bi = int(A["beats"][j])
        # buscar el inicio del golpe actual
        k0 = j
        while k0 > 0 and A["beats"][k0 - 1] == bi and j - k0 < 10:
            k0 -= 1
        if bi % (1 if pre > 0.3 else 4) == 0:
            draw_lightning(dr, bi * 7 + 1, (j - k0) / FPS, pal)
    draw_spectrum(dr, spec, pal, 0.6)

    # bloom barato + escalado a 1080p
    small = img.resize((RW // 4, RH // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    glow = np.asarray(small.resize((RW, RH), Image.BILINEAR), np.float32)
    base = np.asarray(img, np.float32)
    base = base + glow * (1.1 + 0.8 * kick)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.BILINEAR)

    # temblor en los golpes del estribillo
    sh = (kick * (6 + 18 * ch)) if kick > 0.3 else 0
    rng = np.random.default_rng(i)
    shake = (rng.uniform(-sh, sh), rng.uniform(-sh, sh))

    frame = img.convert("RGBA")
    for ln in lines:
        render_line(frame, ln, t, pal, kick, ch, shake)
    if outro > 0:
        render_title(frame, t, timeline[-1][0] + 0.2, dur, pal, kick)
    # etiqueta discreta
    if t < dur - 3:
        tag = Image.new("RGBA", (420, 60), (0, 0, 0, 0))
        tdr = ImageDraw.Draw(tag)
        tdr.text((0, 10), "ELECTRIC PULSE", font=font(34, True), fill=(*pal[0], 170))
        frame.alpha_composite(tag, (60, 44))

    out = np.asarray(frame.convert("RGB"), np.float32)
    # aberracion cromatica en los golpes
    ca = int(kick * (3 + 7 * ch))
    if ca > 0:
        out[..., 0] = np.roll(out[..., 0], ca, 1)
        out[..., 2] = np.roll(out[..., 2], -ca, 1)
    out += 38 * kick * (0.4 + ch) * (kick > 0.5)
    out *= vignette()
    out *= fade_in * fade_out
    return np.clip(out, 0, 255).astype(np.uint8).tobytes()


# ----------------------------------------------------------------------------
def main():
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", AUDIO],
        capture_output=True, text=True, check=True).stdout)
    lines = load_lyrics()
    timeline = build_timeline(lines, dur)
    print("secciones:", timeline)
    audio = analyze_audio(dur)

    if "--stills" in sys.argv:
        secs = [float(x) for x in sys.argv[sys.argv.index("--stills") + 1:]]
        os.makedirs(os.path.join(HERE, "stills"), exist_ok=True)
        init_worker(lines, timeline, audio, dur)
        for s in secs:
            buf = render_frame(int(s * FPS))
            Image.frombytes("RGB", (W, H), buf).save(os.path.join(HERE, "stills", f"t{s:06.2f}.png"))
            print("still", s)
        return

    nframes = int(dur * FPS)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", AUDIO,
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
         "-tune", "animation", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
         "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init_worker, initargs=(lines, timeline, audio, dur)) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nframes), chunksize=4)):
            ff.stdin.write(buf)
            if k % 150 == 0:
                print(f"frame {k}/{nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("listo:", OUT)


if __name__ == "__main__":
    main()
