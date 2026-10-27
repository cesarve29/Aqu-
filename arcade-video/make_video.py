#!/usr/bin/env python3
"""
INSERT COIN: LA ULTIMA PARTIDA
Video arcade retro de ~2 minutos generado 100% por codigo:
pixel art 16-bit a 320x180, escalado x4 con efecto CRT (curvatura, scanlines,
bloom, aberracion cromatica, glitches VHS) y banda sonora chiptune sintetizada.

Uso:
    python3 make_video.py                  -> last_game.mp4 (video completo)
    python3 make_video.py --stills 5 15 92 -> PNGs de esos segundos (para revisar)
Requiere: numpy, Pillow, ffmpeg.
"""
import colorsys
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, SCALE, FPS = 320, 180, 4, 24
DUR = 120.0
SCENE = 10.0
HERE = os.path.dirname(os.path.abspath(__file__))

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
MAG = (255, 0, 255)
CYAN = (0, 255, 255)
ORANGE = (255, 107, 0)
DEEP = (26, 0, 51)
YELLOW = (255, 230, 0)
RED = (255, 30, 60)
PURPLE = (110, 0, 170)
PINK = (255, 80, 180)
GOLD = (255, 200, 40)
INK = (8, 4, 16)

YY, XX = np.mgrid[0:H, 0:W]


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def mix(c1, c2, t):
    t = clamp(t)
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def rainbow(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def shift(arr, dx, dy):
    """Desplaza la imagen rellenando con negro (screen shake)."""
    dx, dy = int(dx), int(dy)
    if dx == 0 and dy == 0:
        return arr
    out = np.zeros_like(arr)
    sx0, sx1 = max(0, -dx), min(W, W - dx)
    sy0, sy1 = max(0, -dy), min(H, H - dy)
    out[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] = arr[sy0:sy1, sx0:sx1]
    return out


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def dgrad(h, w, stops, levels=10):
    """Degradado vertical con dithering Bayer (look 16-bit)."""
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    bay = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    q = np.clip(np.floor(y * (levels - 1) + bay) / (levels - 1), 0, 1)
    st = np.array(stops, float)
    n = len(st) - 1
    pos = q * n
    i = np.minimum(pos.astype(int), n - 1)
    fr = (pos - i)[..., None]
    return (st[i] * (1 - fr) + st[i + 1] * fr).astype(np.uint8)


# ----------------------------------------------------------------------------
# fuente bitmap 5x7
# ----------------------------------------------------------------------------
_F = {
    'A': ".###.|#...#|#...#|#####|#...#|#...#|#...#",
    'B': "####.|#...#|#...#|####.|#...#|#...#|####.",
    'C': ".###.|#...#|#....|#....|#....|#...#|.###.",
    'D': "####.|#...#|#...#|#...#|#...#|#...#|####.",
    'E': "#####|#....|#....|####.|#....|#....|#####",
    'F': "#####|#....|#....|####.|#....|#....|#....",
    'G': ".###.|#...#|#....|#.###|#...#|#...#|.####",
    'H': "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    'I': ".###.|..#..|..#..|..#..|..#..|..#..|.###.",
    'J': "..###|...#.|...#.|...#.|#..#.|#..#.|.##..",
    'K': "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#",
    'L': "#....|#....|#....|#....|#....|#....|#####",
    'M': "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#",
    'N': "#...#|##..#|#.#.#|#..##|#...#|#...#|#...#",
    'O': ".###.|#...#|#...#|#...#|#...#|#...#|.###.",
    'P': "####.|#...#|#...#|####.|#....|#....|#....",
    'Q': ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#",
    'R': "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    'S': ".####|#....|#....|.###.|....#|....#|####.",
    'T': "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    'U': "#...#|#...#|#...#|#...#|#...#|#...#|.###.",
    'V': "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
    'W': "#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#",
    'X': "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    'Y': "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..",
    'Z': "#####|....#|...#.|..#..|.#...|#....|#####",
    '0': ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.",
    '1': "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    '2': ".###.|#...#|....#|...#.|..#..|.#...|#####",
    '3': "####.|....#|....#|.###.|....#|....#|####.",
    '4': "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.",
    '5': "#####|#....|####.|....#|....#|#...#|.###.",
    '6': ".###.|#....|#....|####.|#...#|#...#|.###.",
    '7': "#####|....#|...#.|..#..|.#...|.#...|.#...",
    '8': ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    '9': ".###.|#...#|#...#|.####|....#|....#|.###.",
    '!': "..#..|..#..|..#..|..#..|..#..|.....|..#..",
    '?': ".###.|#...#|....#|...#.|..#..|.....|..#..",
    ':': ".....|..#..|.....|.....|.....|..#..|.....",
    '.': ".....|.....|.....|.....|.....|.....|..#..",
    ',': ".....|.....|.....|.....|.....|..#..|.#...",
    '+': ".....|..#..|..#..|#####|..#..|..#..|.....",
    '-': ".....|.....|.....|#####|.....|.....|.....",
    ' ': ".....|.....|.....|.....|.....|.....|.....",
}
FONT = {k: np.array([[c == '#' for c in row] for row in v.split('|')]) for k, v in _F.items()}


def text_mask(s):
    if not s:
        return np.zeros((7, 1), bool)
    parts = []
    for i, ch in enumerate(s.upper()):
        parts.append(FONT.get(ch, FONT[' ']))
        if i < len(s) - 1:
            parts.append(np.zeros((7, 1), bool))
    return np.hstack(parts)


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx or dy:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


_TC = {}


def text_rgba(s, scale, color, outline=INK):
    key = (s, scale, color if not callable(color) else color.__name__, outline)
    if key in _TC:
        return _TC[key]
    if len(_TC) > 3000:
        _TC.clear()
    m = np.kron(text_mask(s), np.ones((scale, scale), bool))
    h, w = m.shape
    pad = max(1, scale // 2)
    M = np.zeros((h + 2 * pad, w + 2 * pad), bool)
    M[pad:pad + h, pad:pad + w] = m
    rgba = np.zeros(M.shape + (4,), np.uint8)
    if outline is not None:
        rgba[dilate(M, pad)] = (*outline, 255)
    if callable(color):
        for yy in range(h):
            row = M[pad + yy]
            rgba[pad + yy][row] = (*color(yy / max(1, h - 1)), 255)
    else:
        rgba[M] = (*color, 255)
    img = Image.fromarray(rgba, 'RGBA')
    _TC[key] = img
    return img


def draw_text(im, s, x, y, scale, color, center=True, outline=INK):
    img = text_rgba(s, scale, color, outline)
    if center:
        x = x - img.width // 2
    im.paste(img, (int(x), int(y)), img)
    return img.size


def chrome(yn):
    stops = [(0.0, (255, 255, 255)), (0.42, (120, 220, 255)), (0.5, (20, 20, 90)),
             (0.56, (255, 110, 255)), (1.0, (255, 230, 120))]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if yn <= p1:
            return mix(c0, c1, (yn - p0) / (p1 - p0))
    return stops[-1][1]


def fire_grad(yn):
    return mix(YELLOW, RED, yn)


def ice_grad(yn):
    return mix(WHITE, CYAN, yn)


# ----------------------------------------------------------------------------
# sprites
# ----------------------------------------------------------------------------
SPR = {
    'ninja_a': ["....BBBB....", "...BBBBBB...", "...BBBWWWB..", "RRRBBBBBB...",
                "RR..BBBB....", "...CCCCCC...", "..BBBBBBBB..", "..B.BBBB.B..",
                "....BBBB....", "....BB.BB...", "...BB...BB..", "..BB.....B..",
                "..B......BB.", ".BB........."],
    'ninja_b': ["....BBBB....", "...BBBBBB...", "...BBBWWWB..", ".RRBBBBBB...",
                "RRR.BBBB....", "...CCCCCC...", "..BBBBBBBB..", "...BBBBBB...",
                "....BBBB....", "....BBBB....", "....BBBB....", "....B.BB....",
                "...BB.BB....", "...B...BB..."],
    'robot': ["..MMMMMM..", ".MMMMMMMM.", ".MRRMMRRM.", ".MMMMMMMM.", "..MDDDDM..",
              "MMMMMMMMMM", "M.MMYYMM.M", "M.MMMMMM.M", "..MM..MM..", ".MMM..MMM."],
    'bike': [".....BBBB.....", "....BBBBBB....", "....BCCCCB....", "...BBBBBBBB...",
             "..BBBBBBBBBB..", "..BBBBBBBBBB..", "...BBMMMMBB...", "..MMMMMMMMMM..",
             "..MRRMMMMRRM..", "..MMMMMMMMMM..", ".....KKKK.....", ".....KKKK.....",
             ".....KKKK.....", "......KK......"],
}
PAL = {'B': (60, 70, 210), 'C': CYAN, 'S': (255, 200, 160), 'W': WHITE, 'K': (25, 20, 35),
       'M': (150, 150, 180), 'R': RED, 'Y': YELLOW, 'D': (60, 60, 80)}
PAL_MECHA = {'B': (230, 230, 250), 'C': MAG, 'W': CYAN, 'R': PINK}
PAL_BRUTE = {'B': (170, 85, 30), 'C': GOLD, 'W': WHITE, 'R': (120, 40, 10)}
PAL_GOLD = {'B': GOLD, 'C': WHITE, 'W': RED, 'R': ORANGE}
PAL_MAGENTA = {'B': MAG, 'C': YELLOW, 'W': WHITE, 'R': CYAN}
PAL_CYAN = {'B': CYAN, 'C': MAG, 'W': WHITE, 'R': YELLOW}
PAL_ENEMY_BIKE = {'B': (200, 30, 60), 'C': YELLOW}
PAL_GHOST = {k: (0, 200, 255) for k in "BCSWKMRYD"}
PAL_INK = {k: INK for k in "BCSWKMRYD"}

_SC = {}


def sprite(name, scale=1, pal=None, flip=False):
    key = (name, scale, tuple(sorted(pal.items())) if pal else None, flip)
    if key in _SC:
        return _SC[key]
    rows = SPR[name]
    p = dict(PAL)
    if pal:
        p.update(pal)
    h, w = len(rows), len(rows[0])
    rgba = np.zeros((h + 2, w + 2, 4), np.uint8)
    m = np.zeros((h + 2, w + 2), bool)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != '.':
                m[y + 1, x + 1] = True
    rgba[dilate(m, 1) & ~m] = (*INK, 255)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != '.':
                rgba[y + 1, x + 1] = (*p[c], 255)
    if flip:
        rgba = rgba[:, ::-1]
    img = Image.fromarray(rgba, 'RGBA')
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    _SC[key] = img
    return img


def put(im, spr, x, y):
    """Pega un sprite con los pies en (x, y)."""
    im.paste(spr, (int(x - spr.width // 2), int(y - spr.height)), spr)


def hero(im, x, y, t, scale=2, run=True, pal=None):
    name = 'ninja_a' if (run and int(t * 10) % 2 == 0) else 'ninja_b'
    put(im, sprite(name, scale, pal), x, y)


# ----------------------------------------------------------------------------
# efectos de particulas
# ----------------------------------------------------------------------------
def burst(dr, x, y, age, n=30, speed=80, seed=0, life=1.0, grav=60, colors=None, size=2):
    if age < 0 or age > life:
        return
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0, 2 * np.pi, n)
    spd = rng.uniform(0.3, 1.0, n) * speed
    cols = colors or [WHITE, YELLOW, ORANGE, RED]
    k = age / life
    for a, v in zip(ang, spd):
        px = x + math.cos(a) * v * age
        py = y + math.sin(a) * v * age + grav * age * age
        c = cols[min(len(cols) - 1, int(k * len(cols)))]
        s = size if k < 0.6 else 1
        px, py = int(px), int(py)
        dr.rectangle([px, py, px + s - 1, py + s - 1], fill=c)


def explosion(dr, x, y, age, size=1.0, seed=0):
    if age < 0 or age > 0.9:
        return
    if age < 0.3:
        r = size * (4 + 26 * age)
        c = mix(WHITE, YELLOW, age / 0.3)
        dr.ellipse([x - r, y - r, x + r, y + r], fill=c)
        r2 = r * 0.55
        dr.ellipse([x - r2, y - r2, x + r2, y + r2], fill=WHITE)
    r = size * (6 + 40 * age)
    dr.ellipse([x - r, y - r, x + r, y + r], outline=mix(ORANGE, RED, age / 0.9), width=2)
    burst(dr, x, y, age, n=int(16 * size), speed=90 * size, seed=seed, life=0.9)


def fireworks(dr, x, y, age, seed, hue):
    if age < 0 or age > 1.6:
        return
    rng = np.random.default_rng(seed)
    n = 48
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False) + rng.uniform(0, 0.2, n)
    spd = rng.uniform(55, 75, n)
    for i, (a, v) in enumerate(zip(ang, spd)):
        d = v * (1 - math.exp(-age * 2.5)) / 2.5 * 2
        px = x + math.cos(a) * d
        py = y + math.sin(a) * d + 18 * age * age
        if age > 1.0 and (i + int(age * 20)) % 3 == 0:
            continue
        c = WHITE if age < 0.15 else rainbow(hue + (i % 3) * 0.08, 1.0 - 0.2 * (i % 2))
        dr.rectangle([px, py, px + 1, py + 1], fill=c)


def floater(im, s, x, y, age, color=YELLOW, life=0.9):
    if 0 <= age < life:
        draw_text(im, s, x, y - 22 * age, 1, color)


# ----------------------------------------------------------------------------
# HUD
# ----------------------------------------------------------------------------
def score_at(tg):
    return int(tg * tg * 6.5 + tg * 300) // 10 * 10


def hud(im, tg, lives=3):
    draw_text(im, "1UP", 4, 3, 1, RED, center=False)
    draw_text(im, "%07d" % score_at(tg), 26, 3, 1, WHITE, center=False)
    draw_text(im, "HI 9999990", 236, 3, 1, YELLOW, center=False)
    dr = ImageDraw.Draw(im)
    for i in range(lives):
        x = 4 + i * 8
        dr.rectangle([x, 172, x + 5, 176], fill=CYAN, outline=INK)


def boss_bar(im, v, label="MECHA DRAGON"):
    dr = ImageDraw.Draw(im)
    draw_text(im, label, 160, 13, 1, ORANGE)
    dr.rectangle([60, 23, 260, 29], fill=INK, outline=WHITE)
    w = int(198 * clamp(v))
    if w > 0:
        dr.rectangle([61, 24, 61 + w, 28], fill=mix(RED, YELLOW, v))
        dr.line([61, 24, 61 + w, 24], fill=(255, 220, 200))


# ----------------------------------------------------------------------------
# fondos
# ----------------------------------------------------------------------------
RNG = np.random.default_rng(7)
STARS = np.column_stack([RNG.integers(0, W, 140), RNG.integers(0, H, 140)])
STAR_PH = RNG.uniform(0, 6.28, 140)


def draw_stars(arr, t, ymax=H, drift=0.0):
    xs = ((STARS[:, 0] - drift * t) % W).astype(int)
    ys = STARS[:, 1]
    b = 0.5 + 0.5 * np.sin(t * 3 + STAR_PH)
    m = ys < ymax
    cols = (np.stack([b * 255, b * 220 + 35, np.full_like(b, 255)], -1)).astype(np.uint8)
    arr[ys[m], xs[m]] = cols[m]


SPACE = dgrad(H, W, [(2, 0, 10), DEEP, (60, 0, 90)])


def space_bg(t):
    arr = SPACE.copy()
    draw_stars(arr, t, drift=4)
    return arr


_CACHE = {}


def cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def mountains(seed, hor, amp, base):
    rng = np.random.default_rng(seed)
    x = np.arange(W)
    h = base + amp * (0.5 + 0.5 * np.sin(x * 0.03 + rng.uniform(0, 6)))
    h += amp * 0.6 * np.abs(np.sin(x * 0.071 + rng.uniform(0, 6)))
    h += rng.integers(0, 3, W)
    return h.astype(int)


def synth_bg(t, hor=112, sun_r=44, grid_speed=1.6, sky=None, sun_cy=None):
    sky = sky or [(5, 0, 20), (40, 0, 80), (150, 0, 140), (255, 70, 120)]
    arr = cached(('sky', hor, tuple(sky)), lambda: dgrad(H, W, sky + [sky[-1]] * 0))
    arr = arr.copy()
    # cielo solo hasta el horizonte
    skyp = cached(('skyp', hor, tuple(sky)), lambda: dgrad(hor, W, sky, 12))
    arr[:hor] = skyp
    draw_stars(arr, t, ymax=hor - 30)
    cy = sun_cy if sun_cy is not None else hor - 20
    sun_col = cached(('sun', cy, sun_r), lambda: np.vstack([
        np.zeros((max(0, cy - sun_r), W, 3), np.uint8),
        dgrad(2 * sun_r, W, [(255, 240, 90), (255, 140, 40), (255, 0, 150)], 10),
        np.zeros((max(0, H - (cy + sun_r)), W, 3), np.uint8)])[:H])
    d2 = (XX - 160) ** 2 + (YY - cy) ** 2
    rel = (YY - (cy - sun_r * 0.15)) / sun_r
    band = (YY - t * 5) % 8
    sun = (d2 <= sun_r * sun_r) & (YY < hor) & ~((rel > 0) & (band < rel * 5.5))
    arr[sun] = sun_col[sun]
    # montanas
    hm = cached(('mnt', hor), lambda: mountains(3, hor, 10, 4))
    mm = (YY >= hor - hm[None, :]) & (YY < hor)
    arr[mm] = (30, 0, 60)
    edge = (YY == hor - hm[None, :])
    arr[edge] = (255, 0, 200)
    # suelo con grid
    floor = cached(('floor', hor), lambda: dgrad(H - hor, W, [(15, 0, 35), (55, 0, 85)], 8))
    arr[hor:] = floor
    fy = YY[hor:] - hor
    fx = XX[hor:]
    dpt = (fy + 0.5) / (H - hor)
    rel = (fx - 160) / (dpt * 46)
    vline = np.abs(rel - np.round(rel)) * dpt * 46 < 0.6
    sub = arr[hor:]
    sub[vline] = (255, 0, 220)
    ph = (t * grid_speed) % 1.0
    for k in range(40):
        d = 1.3 + (k - ph) * 0.9
        if d <= 0.9:
            continue
        y = int(hor + (H - hor) * 1.3 / d)
        if hor < y < H:
            c = mix((120, 0, 140), (255, 40, 230), 1.3 / d * 1.2)
            arr[y, :] = c
    arr[hor, :] = (255, 120, 255)
    arr[hor - 1, :] = mix(arr[hor - 1, 0], (255, 120, 255), 0.5)
    return arr


def build_city(width, seed, base_y, hmin, hmax, body, edge, win_prob, signs=False, props=False):
    rng = np.random.default_rng(seed)
    L = np.zeros((H, width, 4), np.uint8)
    wcols = [(0, 220, 255), (255, 0, 220), (255, 220, 80), (120, 120, 255)]
    x = 0
    while x < width:
        bw = int(rng.integers(16, 38))
        top = base_y - int(rng.integers(hmin, hmax + 1)) if hmax > 0 else base_y
        x1 = min(width, x + bw)
        L[top:, x:x1] = (*body, 255)
        if edge:
            L[top, x:x1] = (*edge, 255)
        for wy in range(top + 3, H - 2, 4):
            for wx in range(x + 2, x1 - 2, 3):
                if rng.random() < win_prob:
                    c = wcols[int(rng.integers(0, 4))] if rng.random() < 0.6 else (90, 60, 140)
                    L[wy, wx] = (*c, 255)
        if rng.random() < 0.35 and top > 10:
            ax = x + bw // 2
            L[top - 9:top, ax] = (*body, 255)
            L[top - 10, ax] = (255, 40, 60, 255)
        if signs and rng.random() < 0.45 and bw > 18:
            c = [MAG, CYAN, YELLOW][int(rng.integers(0, 3))]
            sy = top + 6
            L[sy:sy + 18, x + 2:x + 5] = (*c, 255)
        if props:
            if rng.random() < 0.5:
                px = x + int(rng.integers(2, max(3, bw - 10)))
                L[top - 6:top, px:px + 8] = (40, 30, 70, 255)
                L[top - 6, px:px + 8] = (90, 80, 140, 255)
            if rng.random() < 0.3:
                px = x + int(rng.integers(2, max(3, bw - 6)))
                L[top - 14:top, px] = (90, 80, 140, 255)
                L[top - 14, px - 1:px + 2] = (255, 0, 200, 255)
        x = x1 + int(rng.integers(0, 3))
    return L


def city_layers():
    def make():
        far = build_city(960, 1, 120, 30, 70, (45, 12, 85), (90, 40, 150), 0.12)
        mid = build_city(960, 2, 140, 25, 70, (24, 6, 50), (140, 0, 160), 0.3, signs=True)
        near = build_city(960, 4, 142, 0, 0, (12, 4, 24), (255, 0, 200), 0.05, props=True)
        # carteles de neon en la capa media
        for i, (word, col) in enumerate([("NEON", MAG), ("8 BIT", CYAN), ("ARCADE", YELLOW),
                                         ("PIXEL", PINK), ("GAME", CYAN)]):
            t = np.array(text_rgba(word, 2, col))
            x0, y0 = 40 + i * 190, 62 + (i % 2) * 14
            hh, ww = t.shape[:2]
            mid[y0 - 3:y0 + hh + 3, x0 - 3:x0 + ww + 3] = (10, 0, 25, 255)
            mid[y0 - 3, x0 - 3:x0 + ww + 3] = (*col, 255)
            mid[y0 + hh + 2, x0 - 3:x0 + ww + 3] = (*col, 255)
            sub = mid[y0:y0 + hh, x0:x0 + ww]
            mk = t[..., 3] > 0
            sub[mk] = t[mk]
        return far, mid, near
    return cached('city', make)


def comp_layer(arr, layer, offset):
    idx = (np.arange(W) + int(offset)) % layer.shape[1]
    sl = layer[:, idx]
    m = sl[..., 3] > 0
    arr[m] = sl[..., :3][m]


CITY_SKY = dgrad(H, W, [(5, 0, 25), (30, 0, 70), (120, 0, 120), (255, 40, 140)], 12)


def city_bg(t, speed, near=True):
    far, mid, nr = city_layers()
    arr = CITY_SKY.copy()
    draw_stars(arr, t, ymax=60)
    m = (XX - 255) ** 2 + (YY - 30) ** 2 <= 14 ** 2
    arr[m] = (255, 220, 255)
    m2 = ((XX - 250) ** 2 + (YY - 27) ** 2 <= 9) | ((XX - 259) ** 2 + (YY - 34) ** 2 <= 4)
    arr[m & m2] = (220, 170, 230)
    comp_layer(arr, far, t * speed * 0.2)
    comp_layer(arr, mid, t * speed * 0.5)
    if near:
        comp_layer(arr, nr, t * speed)
    return arr


LAVA_SKY = dgrad(H, W, [(5, 0, 5), (40, 0, 20), (120, 10, 20), (255, 70, 0)], 12)


def lava_bg(t, rumble=0.0):
    def ruins():
        L = build_city(W, 9, 160, 20, 75, (30, 5, 15), (120, 20, 20), 0.04)
        rng = np.random.default_rng(5)
        for _ in range(40):  # bordes rotos
            x, y = int(rng.integers(0, W)), int(rng.integers(80, 150))
            L[y:y + 6, x:x + 4, 3] = 0
        return L
    arr = LAVA_SKY.copy()
    comp_layer(arr, cached('ruins', ruins), 0)
    # ascuas
    rng = np.random.default_rng(11)
    ex = rng.uniform(0, W, 70)
    ev = rng.uniform(10, 30, 70)
    ep = rng.uniform(0, 200, 70)
    ys = (170 - (ep + t * ev) % 170).astype(int)
    xs = ((ex + 6 * np.sin(t + ep)) % W).astype(int)
    arr[ys, xs] = (255, 160, 40)
    return arr


def lava_sea(arr, t, top=156):
    wave_y = top + 2.5 * np.sin(XX[0] * 0.08 + t * 2) + 1.5 * np.sin(XX[0] * 0.17 - t * 3.1)
    wave_y = wave_y.astype(int)
    m = YY >= wave_y[None, :]
    depth = YY - wave_y[None, :]
    pat = (np.sin(XX * 0.2 + YY * 0.5 + t * 3) + np.sin(XX * 0.05 - t)) > 0.8
    col = np.where((depth < 2)[..., None], np.array(YELLOW, np.uint8),
                   np.where(pat[..., None], np.array((255, 160, 0), np.uint8),
                            np.array((220, 50, 0), np.uint8)))
    arr[m] = col[m]
    return arr


# ----------------------------------------------------------------------------
# el jefe final: dragon mecanico
# ----------------------------------------------------------------------------
def draw_dragon(dr, hx, hy, t, jaw=0.0, s=1.0, eye=1.0, hit=False):
    body_c, plate_c = ((70, 60, 100), (130, 120, 170)) if not hit else (WHITE, WHITE)
    # alas
    for k, (dx, dy, a0, col) in enumerate([(30, 30, -2.15, (50, 0, 70)), (42, 40, -1.95, (85, 0, 110))]):
        ax, ay = hx + dx * s, hy + dy * s
        flap = math.sin(t * 2.6 + k * 0.4) * 0.22
        angs = [a0 + flap + i * 0.36 for i in range(5)]
        lens = [s * v for v in (100, 118, 110, 90, 62)]
        tips = [(ax + math.cos(a) * l, ay + math.sin(a) * l) for a, l in zip(angs, lens)]
        poly = [(ax, ay)]
        for i, tp in enumerate(tips):
            poly.append(tp)
            if i < len(tips) - 1:
                mx, my = (tp[0] + tips[i + 1][0]) / 2, (tp[1] + tips[i + 1][1]) / 2
                poly.append((lerp(mx, ax, 0.22), lerp(my, ay, 0.22)))
        poly.append((ax + 14 * s, ay + 18 * s))
        dr.polygon(poly, fill=col if not hit else WHITE, outline=INK)
        for tp in tips:
            dr.line([(ax, ay), tp], fill=(170, 160, 215) if not hit else WHITE, width=max(1, int(2 * s)))
            dr.rectangle([tp[0] - 1, tp[1] - 1, tp[0] + 1, tp[1] + 1], fill=MAG if not hit else WHITE)
    # cuerpo serpenteante
    N = 16
    nx, ny = hx + 16 * s, hy + 14 * s
    bx, by = hx + 80 * s, hy + 200 * s
    segs = []
    for k in range(N):
        u = k / (N - 1)
        x = lerp(nx, bx, u) + 22 * s * math.sin(u * 3.2 - t * 2.2) * (0.25 + u)
        y = lerp(ny, by, u)
        segs.append((x, y, (15 - 4 * u) * s))
    for x, y, r in reversed(segs):
        dr.polygon([(x + r * 0.1, y - r * 0.8), (x + r * 1.0, y - r * 1.6), (x + r * 0.8, y - r * 0.2)],
                   fill=MAG if not hit else WHITE, outline=INK)
        dr.ellipse([x - r, y - r, x + r, y + r], fill=body_c, outline=INK)
        dr.ellipse([x - r * 0.7, y - r * 0.8, x + r * 0.4, y + r * 0.1], fill=plate_c)
    x, y, r = segs[2]
    pulse = 0.5 + 0.5 * math.sin(t * 8)
    dr.ellipse([x - r * 0.5, y - r * 0.4, x + r * 0.3, y + r * 0.4], fill=mix((0, 90, 120), CYAN, pulse) if not hit else WHITE)

    def P(pts, oy=None):
        out = []
        for px, py in pts:
            off = (jaw * 9 * clamp((14 - px) / 50)) if oy else 0
            out.append((hx + px * s, hy + py * s + off * s))
        return out
    # mandibula inferior
    dr.polygon(P([(14, 10), (-6, 13), (-36, 15), (-38, 21), (-8, 24), (12, 20)], True),
               fill=body_c, outline=INK)
    for px in (-34, -26, -18):
        dr.polygon(P([(px, 15), (px + 3, 15), (px + 1.5, 11)], True), fill=WHITE)
    if jaw > 0.15 and not hit:
        dr.polygon(P([(-6, 11), (-36, 11), (-36, 15), (-6, 14)], True), fill=ORANGE)
        g = 3 * jaw * s
        cx, cy = hx - 30 * s, hy + 13 * s + jaw * 5 * s
        dr.ellipse([cx - g, cy - g, cx + g, cy + g], fill=YELLOW)
    # craneo
    dr.polygon(P([(-46, 4), (-42, -2), (-20, -8), (-4, -14), (12, -12), (22, -2), (18, 10), (-10, 11), (-46, 10)]),
               fill=body_c, outline=INK)
    dr.line(P([(-32, -2), (8, -10)]), fill=plate_c, width=max(1, int(2 * s)))
    dr.line(P([(-40, 6), (-10, 6)]), fill=(50, 40, 70) if not hit else WHITE)
    for px in (-42, -34, -26, -18):
        dr.polygon(P([(px, 10), (px + 3, 10), (px + 1.5, 14)]), fill=WHITE)
    dr.polygon(P([(6, -10), (36, -32), (18, -4)]), fill=(200, 190, 230) if not hit else WHITE, outline=INK)
    dr.polygon(P([(0, -12), (20, -36), (10, -8)]), fill=(160, 150, 200) if not hit else WHITE, outline=INK)
    dr.rectangle(P([(-44, 1), (-42, 3)]), fill=INK)
    if not hit:
        e = P([(-8, -7), (0, -3)])
        g = 2 * s * eye
        dr.ellipse([e[0][0] - g, e[0][1] - g, e[1][0] + g, e[1][1] + g], fill=(120, 0, 0))
        dr.rectangle(e, fill=mix((120, 0, 0), (255, 40, 40), eye))
        dr.rectangle([e[0][0] + 1, e[0][1] + 1, e[0][0] + 2, e[0][1] + 1], fill=WHITE)
    return (hx - 38 * s, hy + 14 * s + jaw * 4 * s)


# ----------------------------------------------------------------------------
# ESCENAS (cada una dura 10 s). Devuelven (frame, (dx,dy) shake, flash 0..1)
# ----------------------------------------------------------------------------
def scene1(lt, tg):
    """Encendido del CRT + INSERT COIN."""
    arr = space_bg(lt)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    glow = 0.5 + 0.5 * math.sin(lt * 6)
    sc = mix((0, 80, 90), CYAN, glow)
    dr.rectangle([132, 136, 188, 152], fill=(20, 10, 40), outline=sc)
    dr.rectangle([150, 141, 170, 147], fill=mix((60, 0, 60), MAG, glow if lt < 6 else 1))
    draw_text(im, "COIN", 160, 156, 1, sc)
    if lt < 6.0:
        if int(lt * 2.5) % 2 == 0 and lt > 0.8:
            draw_text(im, "INSERT COIN", 160, 48, 3, CYAN)
        draw_text(im, "CREDIT 0", 160, 166, 1, (160, 160, 200))
    else:
        draw_text(im, "1 CREDIT", 160, 40, 3, YELLOW)
        if int(lt * 4) % 2 == 0:
            draw_text(im, "GET READY", 160, 78, 2, MAG)
    if 2.0 <= lt < 6.0:
        p = (lt - 2.0) / 4.0
        y = -12 + 156 * p ** 1.8
        spin = abs(math.cos(lt * 7))
        w = max(1, int(11 * spin))
        dr.ellipse([160 - w - 1, y - 12, 160 + w + 1, y + 12], fill=(150, 90, 0))
        dr.ellipse([160 - w, y - 11, 160 + w, y + 11], fill=GOLD)
        if w > 4:
            dr.rectangle([159, y - 6, 161, y + 6], fill=(255, 250, 180))
            dr.rectangle([160 - w + 2, y - 4, 160 - w + 3, y + 4], fill=(255, 250, 200))
        tw = int(lt * 8) % 4
        sx, sy = 160 + 14, y - 10
        if tw < 2:
            dr.line([sx - 3, sy, sx + 3, sy], fill=WHITE)
            dr.line([sx, sy - 3, sx, sy + 3], fill=WHITE)
    if lt >= 6.0:
        burst(dr, 160, 142, lt - 6.0, n=60, speed=130, seed=3, life=1.5, grav=90)
        burst(dr, 160, 142, lt - 6.1, n=30, speed=70, seed=4, life=1.2, colors=[WHITE, CYAN, MAG])
    if lt > 7.6:
        z = 1 + ((lt - 7.6) / 2.4) ** 2 * 7
        cw, ch = W / z, H / z
        cx, cy = 160, 60
        cy = clamp(cy, ch / 2, H - ch / 2)
        im = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.NEAREST)
    arr = np.array(im)
    if lt < 0.25:
        arr[:] = 0
        w = int(W * lt / 0.25)
        arr[89:91, 160 - w // 2:160 + w // 2] = 255
    elif lt < 0.6:
        h = int(90 * (lt - 0.25) / 0.35)
        arr[np.abs(YY - 90) > h] = 0
    flash = max(0.0, 1 - (lt - 6.0) / 0.25) if lt >= 6.0 else 0.0
    if lt > 9.4:
        flash = max(flash, (lt - 9.4) / 0.6)
    return arr, (0, 0), flash


SLAM = 1.667


def scene2(lt, tg):
    """Titulo epico sobre atardecer synthwave."""
    arr = synth_bg(lt)
    im = Image.fromarray(arr)
    if lt >= SLAM - 0.3:
        p = clamp((lt - (SLAM - 0.3)) / 0.3) ** 2
        s = int(round(lerp(16, 5, p)))
        logo = text_rgba("LAST GAME", s, chrome)
        if lt > SLAM + 0.6:
            a = np.array(logo)
            fill = (a[..., 3] > 0) & (a[..., :3].astype(int).sum(-1) > 60)
            pos = ((lt - SLAM - 0.6) * 240) % (a.shape[1] + 260) - 60
            yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
            band = ((xx + yy * 0.8 - pos) % 1000 < 7) & fill
            a[band] = (255, 255, 255, 255)
            logo = Image.fromarray(a, 'RGBA')
        im.paste(logo, (160 - logo.width // 2, 32 - logo.height // 2), logo)
    if lt > SLAM + 0.9:
        sub = "LA ULTIMA PARTIDA"
        n = int((lt - SLAM - 0.9) * 14)
        draw_text(im, sub[:n], 160, 58, 2, PINK)
    if lt > SLAM + 2.2:
        draw_text(im, "1989  PIXEL ARCADE", 160, 78, 1, CYAN)
    if lt > SLAM + 3.2 and int(lt * 2.5) % 2 == 0:
        draw_text(im, "PRESS START", 160, 150, 2, WHITE)
    shake = (0, 0)
    if 0 <= lt - SLAM < 0.7:
        a = 7 * (1 - (lt - SLAM) / 0.7)
        shake = (a * math.sin(lt * 90), a * math.cos(lt * 77))
    flash = max(0.0, 1 - (lt - SLAM) / 0.35) * 0.9 if lt >= SLAM else 0.0
    return np.array(im), shake, flash


ROSTER = [("NINJA", 'ninja_b', None), ("MECHA", 'ninja_b', PAL_MECHA),
          ("BRUTE", 'ninja_b', PAL_BRUTE), ("ROBO", 'robot', None)]


def scene3(lt, tg):
    """Seleccion de personaje."""
    chk = (((XX + YY + lt * 20) // 16).astype(int) + ((XX - YY) // 16).astype(int)) % 2
    arr = np.where(chk[..., None] == 0, np.array((40, 0, 80), np.uint8), np.array((25, 0, 55), np.uint8))
    arr = arr.astype(np.uint8)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    draw_text(im, "SELECT YOUR HERO", 160, 10, 2, YELLOW)
    sched = [(0, 0.0), (1, 1.8), (2, 3.0), (3, 4.2), (2, 5.2), (1, 5.9), (0, 6.5)]
    cur = 0
    for idx, t0 in sched:
        if lt >= t0:
            cur = idx
    chosen = lt >= 7.0
    bg_cols = [(0, 60, 120), (100, 0, 100), (110, 50, 0), (40, 60, 70)]
    for i, (name, spr, pal) in enumerate(ROSTER):
        x0, y0 = 16 + i * 76, 36
        dim = chosen and i != 0
        bc = mix(bg_cols[i], (10, 5, 20), 0.6 if dim else 0)
        dr.rectangle([x0, y0, x0 + 60, y0 + 80], fill=bc, outline=WHITE if not dim else (80, 80, 100))
        for yy in range(y0 + 2, y0 + 80, 3):
            dr.line([x0 + 1, yy, x0 + 59, yy], fill=mix(bc, BLACK, 0.3))
        bounce = int(abs(math.sin(lt * 8)) * 4) if (chosen and i == 0) else 0
        sp = sprite(spr, 3 if spr != 'robot' else 4, PAL_INK if dim else pal)
        put(im, sp, x0 + 30, y0 + 72 - bounce)
        draw_text(im, name, x0 + 30, y0 + 86, 2, WHITE if not dim else (90, 90, 110))
    x0 = 16 + cur * 76
    if not chosen or int(lt * 10) % 2 == 0:
        c = YELLOW if int(lt * 8) % 2 == 0 else ORANGE
        dr.rectangle([x0 - 3, 33, x0 + 63, 119], outline=c, width=2)
        draw_text(im, "P1", x0 + 6, 26, 1, RED)
    if chosen:
        draw_text(im, "PLAYER 1 READY", 160, 146, 3, rainbow(lt * 0.7) if int(lt * 6) % 2 else WHITE)
        for k, (ft, fx, fy) in enumerate([(7.3, 60, 50), (7.8, 250, 40), (8.4, 160, 30),
                                          (9.0, 90, 60), (9.4, 230, 70)]):
            fireworks(dr, fx, fy, lt - ft, seed=k, hue=k * 0.21)
    flash = max(0.0, 1 - (lt - 7.0) / 0.3) if lt >= 7.0 else 0.0
    return np.array(im), (0, 0), flash


def rain(dr, t, n=80, seed=0):
    rng = np.random.default_rng(int(t * FPS) + seed)
    for _ in range(n):
        x, y = rng.uniform(0, W + 20), rng.uniform(0, H)
        dr.line([x, y, x - 3, y + 7], fill=(110, 140, 255))


def flying_cars(dr, t):
    for i, (y, v, c) in enumerate([(30, 60, CYAN), (48, -45, MAG), (22, 90, YELLOW), (56, 70, PINK)]):
        x = (i * 97 + v * t) % (W + 60) - 30
        if v < 0:
            x = W - ((i * 97 - v * t) % (W + 60)) + 30
        tr = -18 if v > 0 else 18
        dr.line([x, y + 1, x + tr, y + 1], fill=mix(c, BLACK, 0.4))
        dr.rectangle([x - 4, y, x + 4, y + 2], fill=(40, 30, 70), outline=c)


def scene4(lt, tg):
    """Carrera por los tejados de la ciudad neon."""
    arr = city_bg(lt, 140)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    flying_cars(dr, lt)
    ph = lt % 2.5
    jump = 1.5 <= ph < 2.2
    hy = 142
    if jump:
        u = (ph - 1.5) / 0.7
        hy -= 34 * math.sin(math.pi * u)
    if not jump:
        rng = np.random.default_rng(int(lt * FPS))
        for _ in range(6):
            y = rng.uniform(112, 140)
            x = rng.uniform(10, 70)
            dr.line([x, y, x + rng.uniform(10, 30), y], fill=(220, 220, 255))
    for k in range(1, 4):  # estela
        put(im, sprite('ninja_b', 2, PAL_GHOST), 100 - k * 9, hy + (2 if jump else 0))
    hero(im, 100, hy, lt, 2, run=not jump)
    rain(dr, lt)
    hud(im, tg)
    if lt < 2.5:
        draw_text(im, "STAGE 1", 160, 60, 3, YELLOW)
        draw_text(im, "NEON CITY", 160, 86, 2, CYAN)
    return np.array(im), (0, 0), max(0.0, 1 - lt / 0.2)


def scene5(lt, tg):
    """Combate contra oleadas de robots."""
    arr = city_bg(lt, 25, near=False)
    arr[150:] = (18, 6, 34)
    arr[150] = (255, 0, 200)
    lane = ((XX[156:] + lt * 25) % 32 < 14) & (YY[156:] == 165)
    arr[156:][lane] = (90, 60, 140)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    hx, hy = 120, 150
    kills = []
    for i in range(30):
        sp = 0.2 + i * 0.3
        fly = i % 3 == 2
        die = sp + (330 - 150) / 95.0
        kills.append((die, fly, i))
        age = lt - sp
        if age < 0 or lt >= die:
            continue
        x = 330 - 95 * age
        y = (112 + 6 * math.sin(lt * 5 + i)) if fly else 150 - int(abs(math.sin(lt * 12 + i)) * 2)
        put(im, sprite('robot', 2, {'M': (200, 120, 255)} if fly else None), x, y)
        if fly:
            dr.line([x - 6, y - 22, x + 6, y - 22], fill=CYAN)
    done = [(d, f, i) for d, f, i in kills if d <= lt]
    last = max([d for d, _, _ in done], default=-9)
    slashing = lt - last < 0.15
    hero(im, hx, hy, lt, 2, run=not slashing)
    if slashing:
        k = (lt - last) / 0.15
        dr.arc([hx - 4, hy - 46, hx + 44, hy + 2], -90 + 40 * k, 70, fill=WHITE, width=3)
        dr.arc([hx, hy - 40, hx + 38, hy - 2], -80 + 40 * k, 60, fill=CYAN, width=2)
    for d, f, i in done:
        y = 112 if f else 138
        explosion(dr, 152, y, lt - d, size=1.0 if not f else 0.8, seed=i)
        floater(im, "+500" if f else "+100", 160, y - 18, lt - d, YELLOW if not f else CYAN)
    n = len(done)
    if n:
        pulse = 1 if lt - last < 0.12 else 0
        draw_text(im, "X%d COMBO!" % n, 250, 30 - pulse, 2 + pulse, rainbow(n * 0.08))
    rain(dr, lt, 40, 5)
    hud(im, tg)
    shake = (0, 0)
    if lt - last < 0.1:
        shake = (2 * math.sin(lt * 99), 2 * math.cos(lt * 87))
    return np.array(im), shake, max(0.0, 1 - lt / 0.2)


ROAD_HOR = 80
ROAD_SKY = dgrad(ROAD_HOR, W, [(10, 0, 40), (70, 0, 120), (255, 50, 140), (255, 160, 60)], 12)


def palm(dr, x, y, s):
    trunk_h = 80 * s
    tw = max(1, int(5 * s))
    top = (x + 10 * s, y - trunk_h)
    dr.line([x, y, top[0], top[1]], fill=(120, 40, 110), width=tw)
    for a in (-2.8, -2.2, -1.5, -0.9, -0.3, 0.3):
        ex = top[0] + math.cos(a) * 34 * s
        ey = top[1] + math.sin(a) * 18 * s + 14 * s
        mx = (top[0] + ex) / 2
        my = top[1] + math.sin(a) * 22 * s - 2 * s
        dr.line([top[0], top[1], mx, my, ex, ey], fill=(0, 200, 170), width=max(1, int(3 * s)))


def scene6(lt, tg):
    """Persecucion en moto estilo Out Run."""
    arr = np.zeros((H, W, 3), np.uint8)
    arr[:ROAD_HOR] = ROAD_SKY
    draw_stars(arr, lt, ymax=30)
    bolts = [1.8, 5.2, 8.0]
    lit = any(0 <= lt - b < 0.25 for b in bolts)
    if lit:
        arr[:ROAD_HOR] = np.minimum(255, arr[:ROAD_HOR].astype(int) + 70).astype(np.uint8)
    cy, r = ROAD_HOR - 4, 34
    d2 = (XX - 160) ** 2 + (YY - cy) ** 2
    rel = (YY - cy + r * 0.2) / r
    sun = (d2 <= r * r) & (YY < ROAD_HOR) & ~((rel > 0) & ((YY - lt * 4) % 7 < rel * 4.5))
    arr[sun] = np.where((YY[sun] < cy)[:, None], np.array((255, 220, 80)), np.array((255, 60, 160)))
    hm = cached('mnt2', lambda: mountains(8, ROAD_HOR, 8, 3))
    mm = (YY >= ROAD_HOR - hm[None, :]) & (YY < ROAD_HOR)
    arr[mm] = (40, 0, 70)
    arr[(YY == ROAD_HOR - hm[None, :])] = (0, 220, 255)
    # carretera pseudo-3D
    curve = 55 * math.sin(lt * 0.45)
    ys = np.arange(ROAD_HOR, H)
    D = (ys - ROAD_HOR + 0.5) / (H - ROAD_HOR)
    Z = 1.0 / D
    cx = 160 + curve * (1 - D) ** 2 - curve * 0.25
    half = 6 + 150 * D
    seg = (np.floor(Z * 3 - lt * 16) % 2).astype(int)
    X = XX[ROAD_HOR:]
    dx = np.abs(X - cx[:, None])
    hw = half[:, None]
    sg = seg[:, None]
    out = np.where(sg == 0, 1, 0)
    grass = np.where(out[..., None] == 1, np.array((40, 0, 70)), np.array((25, 0, 50)))
    road = np.where(out[..., None] == 1, np.array((60, 50, 90)), np.array((70, 60, 100)))
    rumble = np.where(out[..., None] == 1, np.array((255, 30, 80)), np.array((255, 255, 255)))
    lanec = np.array((255, 255, 255))
    img = np.where((dx < hw)[..., None], road, grass)
    img = np.where(((dx >= hw) & (dx < hw * 1.12))[..., None], rumble, img)
    img = np.where(((dx < hw * 0.03) & (sg == 0))[..., None], lanec, img)
    gl = (np.abs((X - cx[:, None]) / (hw * 0.9) % 1) < 0.04) & (dx > hw * 1.12)
    img = np.where(gl[..., None], np.array((255, 0, 200)), img)
    arr[ROAD_HOR:] = img.astype(np.uint8)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    if lit:
        b = [b for b in bolts if 0 <= lt - b < 0.25][0]
        rng = np.random.default_rng(int(b * 10))
        x, y = rng.uniform(40, 280), 0
        pts = [(x, y)]
        while y < ROAD_HOR - 10:
            x += rng.uniform(-10, 10)
            y += rng.uniform(5, 12)
            pts.append((x, y))
        dr.line(pts, fill=(200, 230, 255), width=3)
        dr.line(pts, fill=WHITE, width=1)
    span = 26.0
    objs = []
    for i in range(10):
        zw = (i * span / 10 - lt * 16 / 3) % span + 0.6
        objs.append((zw, 'palm', i))
    for i in range(2):
        zw = 4.5 + 2.2 * math.sin(lt * 0.8 + i * 2.5)
        objs.append((zw, 'bike', i))
    for zw, kind, i in sorted(objs, reverse=True):
        Dd = 1 / zw
        if Dd > 1:
            continue
        y = ROAD_HOR + Dd * (H - ROAD_HOR)
        c = 160 + curve * (1 - Dd) ** 2 - curve * 0.25
        hh = 6 + 150 * Dd
        if kind == 'palm':
            side = -1 if i % 2 else 1
            palm(dr, c + side * (hh * 1.35 + 10 * Dd), y, Dd * 1.2)
        else:
            sc = max(1, int(round(3 * Dd)))
            put(im, sprite('bike', sc, PAL_ENEMY_BIKE), c + (i * 2 - 1) * hh * 0.45, y)
    sway = 6 * math.sin(lt * 2.0)
    bx = 160 - curve * 0.25 + sway
    put(im, sprite('bike', 3), bx, 178 + int(lt * 20) % 2)
    rng = np.random.default_rng(int(lt * FPS))
    for _ in range(10):
        side = rng.choice([-1, 1])
        x = 160 + side * rng.uniform(90, 160)
        y = rng.uniform(110, 175)
        dr.line([x, y, x + side * rng.uniform(8, 20), y + rng.uniform(4, 10)], fill=(255, 220, 255))
    hud(im, tg)
    draw_text(im, "TIME %02d" % max(0, 60 - int(lt * 3)), 160, 14, 2, YELLOW)
    draw_text(im, "%3d KM/H" % (280 + int(19 * math.sin(lt * 1.7))), 280, 166, 1, CYAN)
    shake = (rng.integers(-1, 2), 0)
    return np.array(im), shake, max(0.0, 1 - lt / 0.2) + (0.5 if lit and int(lt * 24) % 2 == 0 else 0)


ANG = np.arctan2(YY - 105, XX - 160)


def scene7(lt, tg):
    """Power-up."""
    grab = 2.5
    got = lt >= grab
    burstp = ((ANG + lt * (0.4 if not got else 1.4)) * 12 / (2 * np.pi)).astype(int) % 2
    c1, c2 = ((25, 0, 50), (40, 0, 70)) if not got else ((90, 0, 120), (160, 0, 140))
    arr = np.where(burstp[..., None] == 0, np.array(c1), np.array(c2)).astype(np.uint8)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    hx, hy = 160, 150
    if got:
        rng = np.random.default_rng(1)
        ph = rng.uniform(0, 1, 70)
        ox = rng.uniform(-22, 22, 70)
        for k in range(70):
            u = (lt * 1.6 + ph[k]) % 1.0
            y = hy - u * 75
            x = hx + ox[k] * (1 - u * 0.5) + 3 * math.sin(lt * 9 + k)
            c = YELLOW if u < 0.3 else (ORANGE if u < 0.65 else RED)
            s = 3 if u < 0.5 else 2
            dr.rectangle([x, y, x + s - 1, y + s - 1], fill=c)
        ring = lt - grab
        if ring < 1.0:
            rr = 10 + 200 * ring
            dr.ellipse([hx - rr, hy - 30 - rr, hx + rr, hy - 30 + rr], outline=WHITE, width=3)
        pals = [PAL_CYAN, PAL_GOLD, PAL_MAGENTA]
        pal = pals[int(lt * 8) % 3]
    else:
        pal = None
    hero(im, hx, hy, lt, 4, run=False, pal=pal)
    if not got:
        p = lt / grab
        ox = lerp(300, hx, ease(p))
        oy = lerp(50, hy - 30, ease(p)) + 8 * math.sin(lt * 5)
        for rr, c in [(11, (0, 120, 160)), (8, CYAN), (4, WHITE)]:
            dr.ellipse([ox - rr, oy - rr, ox + rr, oy + rr], fill=c)
        for k in range(6):
            a = lt * 4 + k * math.pi / 3
            px, py = ox + math.cos(a) * 15, oy + math.sin(a) * 6
            dr.rectangle([px - 1, py - 1, px + 1, py + 1], fill=MAG)
        draw_text(im, "P", ox, oy - 4, 1, MAG)
    if lt >= 3.0:
        word = "POWER UP!!"
        sc = 4
        total = len(word) * 6 * sc - sc
        x = 160 - total // 2
        for i, ch in enumerate(word):
            t0 = 3.0 + i * 0.07
            if lt >= t0 and ch != ' ':
                drop = max(0.0, 1 - (lt - t0) / 0.25)
                bounce = abs(math.sin((lt - t0) * 6)) * 3 * math.exp(-(lt - t0) * 2)
                y = 16 - 60 * drop - bounce
                draw_text(im, ch, x + i * 6 * sc, y, sc, rainbow(lt * 1.5 + i * 0.1), center=False)
    if lt >= 5.0:
        for i, lab in enumerate(["ATK", "SPD", "DEF"]):
            y = 64 + i * 20
            draw_text(im, lab, 10, y, 2, WHITE, center=False)
            fill = ease_out((lt - 5.0 - i * 0.3) / 0.8)
            dr.rectangle([46, y + 1, 106, y + 12], fill=INK, outline=WHITE)
            if fill > 0:
                dr.rectangle([47, y + 2, 47 + int(58 * fill), y + 11], fill=mix(CYAN, MAG, i / 2))
            if fill >= 1 and int(lt * 6) % 2 == 0:
                draw_text(im, "MAX", 76, y + 3, 1, YELLOW)
    hud(im, tg)
    flash = max(0.0, 1 - (lt - grab) / 0.3) if got else 0.0
    shake = (0, 0)
    if got and lt - grab < 0.5:
        a = 5 * (1 - (lt - grab) / 0.5)
        shake = (a * math.sin(lt * 80), a * math.cos(lt * 70))
    return np.array(im), shake, max(flash, max(0.0, 1 - lt / 0.2))


def scene8(lt, tg):
    """WARNING: se acerca el jefe."""
    arr = lava_bg(lt)
    arr[160:] = (30, 10, 20)
    arr[160] = (120, 40, 40)
    # sombra gigante con borde irregular (las alas del dragon)
    sy = lerp(-10, 150, ease(lt / 9.5))
    edge = sy + 10 * np.sin(XX[0] * 0.05 + 1.0) + 6 * np.abs(np.sin(XX[0] * 0.13))
    sh = YY < edge[None, :]
    arr[sh] = (arr[sh] * 0.3).astype(np.uint8)
    pulse = 0.5 + 0.5 * math.sin(lt * 2 * math.pi * 1.5)
    red = np.array((255, 0, 30), float)
    arr = (arr * (1 - 0.35 * pulse) + red * 0.35 * pulse).astype(np.uint8)
    for y0 in (48, 118):
        band = (YY >= y0) & (YY < y0 + 8)
        stripe = ((XX + YY + lt * 60) // 8).astype(int) % 2 == 0
        arr[band & stripe] = YELLOW
        arr[band & ~stripe] = INK
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    if int(lt * 3) % 2 == 0:
        draw_text(im, "WARNING!!", 160, 66, 6, RED, outline=WHITE)
    else:
        draw_text(im, "WARNING!!", 160, 66, 6, WHITE, outline=RED)
    msg = "A HUGE ENEMY IS APPROACHING FAST . . .  "
    tw = len(msg) * 12
    x = W - (lt * 70) % (tw + W)
    draw_text(im, msg, x, 30, 2, WHITE, center=False)
    rng = np.random.default_rng(42)
    for k in range(int(10 + lt * 6)):
        t0 = rng.uniform(0, 10)
        x0 = rng.uniform(0, W)
        age = (lt - t0) % 1.6
        y = -10 + 120 * age * age
        if y < 160:
            s = int(rng.integers(2, 5))
            dr.rectangle([x0, y, x0 + s, y + s], fill=(110, 90, 100), outline=INK)
    hero(im, 60, 160, lt, 2, run=False)
    if int(lt * 2) % 2 == 0:
        draw_text(im, "!", 60, 120, 2, YELLOW)
    hud(im, tg)
    a = 1 + 3.5 * lt / 10
    rng2 = np.random.default_rng(int(lt * FPS))
    shake = (rng2.uniform(-a, a), rng2.uniform(-a, a))
    return np.array(im), shake, max(0.0, 1 - lt / 0.2)


def scene9(lt, tg):
    """Aparece el jefe."""
    arr = lava_bg(lt)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    hy = lerp(230, 58, ease_out(lt / 5.0))
    roar = 5.5 <= lt < 7.2
    jaw = clamp((lt - 5.3) / 0.3) * (1 - clamp((lt - 7.0) / 0.4))
    eye = clamp((lt - 2.0) / 2)
    draw_dragon(dr, 230, hy, lt, jaw=jaw, eye=eye)
    arr = lava_sea(np.array(im), lt)
    rng = np.random.default_rng(3)
    for k in range(12):  # salpicaduras de lava al emerger
        if lt < 5.0:
            t0 = rng.uniform(0, 5)
            age = lt - t0
            if 0 <= age < 0.8:
                x0 = rng.uniform(180, 300)
                for j in range(6):
                    px = x0 + (j - 3) * 6 * age * 4
                    py = 156 - 60 * age + 90 * age * age - abs(j - 3) * 4
                    arr[int(clamp(py, 0, H - 2)):int(clamp(py, 0, H - 2)) + 2,
                        int(clamp(px, 0, W - 2)):int(clamp(px, 0, W - 2)) + 2] = (255, 200, 0)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    dr.polygon([(10, 160), (20, 146), (60, 144), (72, 160)], fill=(40, 20, 30), outline=INK)
    hero(im, 42, 146, lt, 2, run=False)
    hud(im, tg)
    if lt >= 6.0:
        boss_bar(im, ease_out((lt - 6.0) / 1.5))
    if lt >= 7.5:
        draw_text(im, "MECHA DRAGON", 110, 70, 2, fire_grad)
        draw_text(im, "LORD OF THE LAST LEVEL", 110, 88, 1, ORANGE)
    shake = (0, 0)
    a = 0
    if lt < 5.0:
        a = 2.5
    if roar:
        a = 7 * (1 - (lt - 5.5) / 1.7)
    if a:
        rng2 = np.random.default_rng(int(lt * FPS))
        shake = (rng2.uniform(-a, a), rng2.uniform(-a, a))
    flash = max(0.0, 1 - lt / 0.2)
    if roar and int(lt * 12) % 2 == 0:
        flash = max(flash, 0.25)
    return np.array(im), shake, flash


def dragon_pos(t):
    return 235 + 6 * math.sin(t * 0.9), 58 + 8 * math.sin(t * 1.3)


def hero_bh(t):
    return 60 + 18 * math.sin(t * 1.1), 100 + 40 * math.sin(t * 1.7) + 10 * math.sin(t * 3.1)


def scene10(lt, tg):
    """Batalla final: bullet hell."""
    arr = lava_bg(lt + 30)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    hx_d, hy_d = dragon_pos(lt)
    jaw = 0.7 + 0.3 * math.sin(lt * 6)
    draw_dragon(dr, hx_d, hy_d, lt + 10, jaw=jaw)
    for k in range(int(lt / 0.13) + 1):  # impactos sobre el dragon
        ts = k * 0.13
        age = lt - ts
        if 0 <= age < 0.3 and k % 2 == 0:
            rng = np.random.default_rng(k)
            explosion(dr, hx_d + rng.uniform(-30, 30), hy_d + rng.uniform(-10, 60), age, 0.4, k)
    arr = lava_sea(np.array(im), lt + 30)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    for k in range(5):  # erupciones de lava
        t0 = 1.0 + k * 1.9
        age = lt - t0
        if 0 <= age < 1.2:
            x0 = 40 + k * 57
            for j in range(14):
                v = 90 + j * 6
                py = 160 - v * age + 110 * age * age
                px = x0 + (j - 7) * 3 * age * 5
                if py < 165:
                    dr.rectangle([px, py, px + 2, py + 2], fill=YELLOW if j % 2 else ORANGE)
    # balas
    def mouth(te):
        x, y = dragon_pos(te)
        return x - 38, y + 18
    dt = 0.08
    te0 = max(0.0, lt - 5.0)
    k0 = int(te0 / dt)
    for k in range(k0, int(lt / dt) + 1):
        te = k * dt
        age = lt - te
        if age < 0:
            continue
        mx, my = mouth(te)
        for arm in range(5):
            a = te * 2.3 + arm * 2 * math.pi / 5
            px, py = mx + math.cos(a) * 80 * age, my + math.sin(a) * 80 * age
            if -4 < px < W + 4 and -4 < py < H + 4:
                dr.ellipse([px - 2, py - 2, px + 2, py + 2], fill=MAG)
                dr.point((px, py), fill=WHITE)
    if lt > 4.0:
        for k in range(int((lt - 4.0) / 0.7) + 1):
            te = 4.0 + k * 0.7
            age = lt - te
            if age < 0:
                continue
            mx, my = mouth(te)
            for j in range(14):
                a = j * 2 * math.pi / 14 + k * 0.2
                px, py = mx + math.cos(a) * 55 * age, my + math.sin(a) * 55 * age
                if -6 < px < W + 6 and -6 < py < H + 6:
                    dr.ellipse([px - 4, py - 4, px + 4, py + 4], fill=PINK, outline=WHITE)
    hx, hy = hero_bh(lt)
    for k in range(int(lt / 0.12) + 1):
        ts = k * 0.12
        age = lt - ts
        sx0, sy0 = hero_bh(ts)
        px = sx0 + 12 + 320 * age
        if age >= 0 and px < hx_d - 20:
            dr.rectangle([px, sy0 - 15, px + 9, sy0 - 14], fill=CYAN)
            dr.rectangle([px + 6, sy0 - 15, px + 9, sy0 - 14], fill=WHITE)
    fl = 4 + int(lt * 20) % 3
    dr.polygon([(hx - 3, hy), (hx + 3, hy), (hx, hy + fl + 4)], fill=ORANGE)
    dr.polygon([(hx - 1, hy), (hx + 1, hy), (hx, hy + fl)], fill=YELLOW)
    hero(im, hx, hy, lt, 2, run=False)
    hud(im, tg, lives=2)
    boss_bar(im, lerp(1.0, 0.12, lt / 10))
    rng2 = np.random.default_rng(int(lt * FPS))
    shake = (rng2.uniform(-1.5, 1.5), rng2.uniform(-1.5, 1.5))
    return np.array(im), shake, max(0.0, 1 - lt / 0.2)


IMPACT = 4.0
SHATTER = 4.7
D11 = (235, 58)


def dragon_pixels():
    def make():
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw_dragon(ImageDraw.Draw(layer), D11[0], D11[1], 20.0, jaw=0.5)
        a = np.array(layer)
        ys, xs = np.nonzero(a[..., 3])
        cols = a[ys, xs, :3]
        rng = np.random.default_rng(99)
        cx, cy = 200, 80
        dx, dy = xs - cx, ys - cy
        dist = np.sqrt(dx * dx + dy * dy) + 1
        sp = rng.uniform(30, 170, len(xs))
        vx = dx / dist * sp + rng.normal(0, 20, len(xs))
        vy = dy / dist * sp + rng.normal(0, 20, len(xs)) - 40
        return xs.astype(float), ys.astype(float), cols, vx, vy
    return cached('dpix', make)


def scene11(lt, tg):
    """Golpe final y el dragon estalla en pixeles."""
    if IMPACT <= lt < IMPACT + 0.15:
        return np.full((H, W, 3), 255, np.uint8), (0, 0), 0.0
    if IMPACT + 0.15 <= lt < SHATTER:  # frame congelado en negativo
        im = Image.new('RGB', (W, H), WHITE)
        dr = ImageDraw.Draw(im)
        draw_dragon(dr, D11[0], D11[1], 20.0, jaw=0.5, hit=True)
        a = np.array(im)
        a = 255 - a
        im = Image.fromarray(a)
        dr = ImageDraw.Draw(im)
        dr.line([130, 150, 300, 10], fill=CYAN, width=7)
        dr.line([130, 150, 300, 10], fill=WHITE, width=3)
        put(im, sprite('ninja_b', 2, PAL_INK), 215, 70)
        return np.array(im), (0, 0), 0.0
    arr = lava_bg(lt + 40)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    if lt < IMPACT:
        draw_dragon(dr, D11[0], D11[1], 20.0 + lt * 0.3 if lt < 1.5 else 20.0, jaw=0.5)
    arr = lava_sea(np.array(im), lt + 40)
    if 1.5 <= lt < IMPACT:  # oscurecer + lineas de velocidad
        arr = (arr * 0.45).astype(np.uint8)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    if 1.5 <= lt < IMPACT:
        rng = np.random.default_rng(int(lt * FPS))
        for _ in range(24):
            a = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(60, 120)
            cx, cy = 200, 75
            dr.line([cx + math.cos(a) * r0, cy + math.sin(a) * r0,
                     cx + math.cos(a) * (r0 + 80), cy + math.sin(a) * (r0 + 80)], fill=(255, 255, 255))
    if lt < 1.5:  # carga de energia
        hx, hy = 50, 150
        dr.polygon([(20, 162), (30, 150), (72, 150), (82, 162)], fill=(40, 20, 30), outline=INK)
        rng = np.random.default_rng(7)
        for k in range(50):
            a = rng.uniform(0, 2 * math.pi)
            u = (lt * 1.3 + rng.uniform(0, 1)) % 1
            r = 60 * (1 - u)
            px, py = hx + math.cos(a) * r, hy - 14 + math.sin(a) * r
            dr.rectangle([px, py, px + 1, py + 1], fill=CYAN if k % 2 else WHITE)
        L = 8 + 26 * lt / 1.5
        dr.line([hx + 4, hy - 16, hx + 4, hy - 16 - L], fill=CYAN, width=5)
        dr.line([hx + 4, hy - 16, hx + 4, hy - 16 - L], fill=WHITE, width=2)
        pal = PAL_CYAN if int(lt * 12) % 2 else None
        hero(im, hx, hy, lt, 2, run=False, pal=pal)
        if lt > 0.4:
            draw_text(im, "ULTRA SLASH!", 160, 40, 3, ice_grad)
    elif lt < IMPACT:  # salto en camara lenta
        p = ease((lt - 1.5) / (IMPACT - 1.5))
        def pos(q):
            return lerp(50, 205, q), lerp(150, 78, q) - 40 * math.sin(math.pi * q)
        for k in range(5, 0, -1):
            gx, gy = pos(max(0, p - k * 0.04))
            put(im, sprite('ninja_b', 2, PAL_GHOST), gx, gy)
        hx, hy = pos(p)
        dr.line([hx + 4, hy - 16, hx + 34, hy - 46], fill=CYAN, width=7)
        dr.line([hx + 4, hy - 16, hx + 34, hy - 46], fill=WHITE, width=3)
        hero(im, hx, hy, lt, 2, run=False, pal=PAL_CYAN if int(lt * 12) % 2 else None)
    else:  # estallido
        age = lt - SHATTER
        xs, ys, cols, vx, vy = dragon_pixels()
        px = (xs + vx * age).astype(int)
        py = (ys + vy * age + 45 * age * age).astype(int)
        m = (px >= 0) & (px < W) & (py >= 0) & (py < H)
        a = np.array(im)
        if age < 0.4:
            c = np.full_like(cols, 255)
        else:
            c = cols.copy()
            fl = (np.arange(len(cols)) + int(age * 20)) % 5 == 0
            c[fl] = (255, 220, 120)
        keep = m & ((np.arange(len(xs)) % 7) >= int(clamp(age / 5) * 7))
        a[py[keep], px[keep]] = c[keep]
        im = Image.fromarray(a)
        dr = ImageDraw.Draw(im)
        for k in range(8):
            rng = np.random.default_rng(k + 50)
            explosion(dr, 200 + rng.uniform(-50, 50), 80 + rng.uniform(-40, 60),
                      age - k * 0.25, 1.5, k)
        if age < 1.2:
            rr = 20 + 300 * age
            dr.ellipse([200 - rr, 80 - rr, 200 + rr, 80 + rr], outline=WHITE, width=3)
        hero(im, 100, 160, lt, 2, run=False)
        if age > 0.8:
            sc = 8 if age < 0.95 else 6
            draw_text(im, "K.O.", 160, 40, sc, fire_grad, outline=WHITE)
    hud(im, tg, lives=2)
    v = 0.12 if lt < IMPACT else 0.0
    boss_bar(im, v)
    shake = (0, 0)
    if lt >= SHATTER:
        a = 8 * math.exp(-(lt - SHATTER) * 1.2)
        rng2 = np.random.default_rng(int(lt * FPS))
        shake = (rng2.uniform(-a, a), rng2.uniform(-a, a))
    flash = max(0.0, 1 - lt / 0.2)
    if lt >= SHATTER:
        flash = max(flash, 0.8 * max(0.0, 1 - (lt - SHATTER) / 0.4))
    return np.array(im), shake, flash


CRT_OFF = 6.667
SUNRISE = dgrad(130, W, [(20, 0, 60), (90, 0, 120), (200, 40, 110), (230, 110, 70), (240, 150, 90)], 12)


def scene12(lt, tg):
    """Victoria al amanecer + GAME OVER? CONTINUE?"""
    if lt >= CRT_OFF:
        im = Image.new('RGB', (W, H), BLACK)
        if lt >= CRT_OFF + 0.9:
            draw_text(im, "GAME OVER?", 160, 60, 4, RED)
        if lt >= CRT_OFF + 1.8:
            n = 9 if lt < CRT_OFF + 2.9 else 8
            if int(lt * 3) % 2 == 0:
                draw_text(im, "CONTINUE? %d" % n, 160, 100, 3, YELLOW)
            draw_text(im, "INSERT COIN", 160, 150, 1, CYAN)
        arr = np.array(im)
        u = lt - CRT_OFF
        if u < 0.6:
            arr[:] = 0
            if u < 0.3:
                w = int(W * (1 - u / 0.3)) + 2
                arr[89:91, 160 - w // 2:160 + w // 2] = 255
            elif u < 0.6:
                r = 3 * (1 - (u - 0.3) / 0.3)
                if r > 0.5:
                    arr[(XX - 160) ** 2 + (YY - 90) ** 2 <= r * r] = 255
        return arr, (0, 0), 0.0
    arr = np.zeros((H, W, 3), np.uint8)
    arr[:130] = SUNRISE
    sy = lerp(150, 112, ease_out(lt / 5))
    d2 = (XX - 200) ** 2 + (YY - sy) ** 2
    sun = (d2 <= 26 ** 2) & (YY < 130)
    arr[sun] = (255, 235, 150)
    halo = (d2 <= 34 ** 2) & ~sun & (YY < 130) & ((XX + YY) % 2 == 0)
    arr[halo] = (240, 160, 100)
    for k, (cy, sp) in enumerate([(40, 6), (62, 10), (84, 14)]):  # nubes
        for j in range(3):
            cx = (j * 140 + k * 60 + lt * sp) % (W + 80) - 40
            m = (np.abs(YY - cy) < 3) & (np.abs(XX - cx) < 26 - k * 3 - np.abs(YY - cy) * 4)
            arr[m] = mix((130, 30, 120), (200, 80, 130), k / 2)
    sea = dgrad(50, W, [(200, 90, 100), (60, 0, 90)], 8)
    arr[130:] = sea
    refl = (np.abs(XX[130:] - 200) < 20 - (YY[130:] - 130) * 0.2) & ((YY[130:] + int(lt * 6)) % 3 == 0)
    arr[130:][refl] = (255, 200, 130)
    cliff = (XX < 120 - (YY - 120) * -0.4) & (YY > 118 + 0.15 * XX)
    arr[cliff] = (25, 5, 35)
    edge = cliff & ~np.roll(cliff, 1, 0)
    arr[edge] = (255, 120, 150)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    hx, hy = 70, 129
    wave = [(hx - 2 - i * 5, hy - 22 + i * 2 + 3 * math.sin(lt * 7 - i)) for i in range(7)]
    dr.polygon([(hx - 2, hy - 22), (hx + 2, hy - 22)] + wave[::-1][:1] +
               [(p[0], p[1] + 6) for p in wave[::-1]] + wave[1:], fill=(200, 0, 60), outline=INK)
    hero(im, hx, hy, lt, 2, run=False)
    rng = np.random.default_rng(3)
    for k in range(120):  # confeti de pixeles
        x0 = rng.uniform(0, W)
        ph = rng.uniform(0, 1)
        v = rng.uniform(15, 35)
        y = (ph * 200 + lt * v) % 200 - 10
        x = x0 + 4 * math.sin(lt * 3 + k)
        c = rainbow(k * 0.13 + lt * 0.5)
        dr.rectangle([x, y, x + 1, y + 1], fill=c)
    if lt >= 0.8:
        p = ease_out((lt - 0.8) / 0.6)
        x = lerp(-150, 160, p)
        draw_text(im, "STAGE CLEAR", x, 18, 4, chrome)
    if lt >= 2.6:
        cnt = int(9999999 * clamp((lt - 2.6) / 1.4))
        s = "{:,}".format(cnt)
        draw_text(im, "HIGH SCORE", 160, 62, 2, WHITE)
        col = rainbow(lt * 2) if lt > 4.0 and int(lt * 8) % 2 else YELLOW
        draw_text(im, s, 160, 80, 3, col)
    if lt >= 4.6:
        draw_text(im, "THANK YOU FOR PLAYING", 160, 160, 1, WHITE)
    return np.array(im), (0, 0), max(0.0, 1 - lt / 0.25)


SCENES = [scene1, scene2, scene3, scene4, scene5, scene6,
          scene7, scene8, scene9, scene10, scene11, scene12]


# ----------------------------------------------------------------------------
# post-proceso CRT
# ----------------------------------------------------------------------------
OW, OH = W * SCALE, H * SCALE


def build_crt():
    X, Y = np.meshgrid((np.arange(OW) + 0.5) / OW * 2 - 1, (np.arange(OH) + 0.5) / OH * 2 - 1)
    r2 = X * X + Y * Y
    k = 0.05
    maps = []
    for ca in (1.004, 1.0, 0.996):
        u = X * (1 + k * r2) * ca
        v = Y * (1 + k * r2) * ca
        lx = np.clip(((u + 1) / 2 * W).astype(np.int32), 0, W - 1)
        ly = np.clip(((v + 1) / 2 * H).astype(np.int32), 0, H - 1)
        maps.append((ly * W + lx).ravel())
    u = X * (1 + k * r2)
    v = Y * (1 + k * r2)
    valid = (np.abs(u) < 1) & (np.abs(v) < 1)
    fy = ((v + 1) / 2 * H) % 1.0
    scan = np.where(fy > 0.74, 0.55, 1.0) * (0.92 + 0.08 * np.sin(fy * np.pi))
    vig = np.clip(1 - 0.28 * r2 ** 1.5, 0, 1)
    edge = np.clip(np.minimum(1 - np.abs(u), 1 - np.abs(v)) * 60, 0, 1)
    mask = (scan * vig * valid * edge).astype(np.float32)
    return maps, mask.reshape(OH, OW)


CRT_MAPS, CRT_MASK = None, None


def post(arr, n, lt, scene_idx, shake, flash):
    global CRT_MAPS, CRT_MASK
    if CRT_MAPS is None:
        CRT_MAPS, CRT_MASK = build_crt()
    arr = shift(arr, *shake)
    # glitch VHS
    rng = np.random.default_rng(n * 7 + 1)
    glitch = (lt < 0.15 and scene_idx in (3, 5, 7, 8, 10)) or rng.random() < 0.012
    if glitch:
        arr = arr.copy()
        for _ in range(int(rng.integers(2, 6))):
            y0 = int(rng.integers(0, H - 8))
            h = int(rng.integers(2, 12))
            arr[y0:y0 + h] = np.roll(arr[y0:y0 + h], int(rng.integers(-18, 18)), axis=1)
        y0 = int(rng.integers(0, H - 4))
        arr[y0:y0 + 2] = np.minimum(255, arr[y0:y0 + 2].astype(int) + 90)
        arr[..., 0] = np.roll(arr[..., 0], 2, axis=1)
    a = arr.astype(np.float32)
    if flash > 0:
        a = a + (255 - a) * min(1.0, flash)
    bright = np.clip((a.max(axis=2, keepdims=True) - 150) / 105, 0, 1) * a
    bl = np.asarray(Image.fromarray(bright.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.5)), np.float32)
    a = np.clip(a + bl * 0.8, 0, 255).astype(np.uint8)
    flat = a.reshape(-1, 3)
    out = np.empty((OH * OW, 3), np.uint8)
    for c in range(3):
        out[:, c] = flat[CRT_MAPS[c], c]
    out = out.reshape(OH, OW, 3).astype(np.float32) * CRT_MASK[..., None]
    return out.astype(np.uint8)


def render_frame(n):
    tg = n / FPS
    si = min(len(SCENES) - 1, int(tg // SCENE))
    lt = tg - si * SCENE
    arr, shake, flash = SCENES[si](lt, tg)
    return post(arr, n, lt, si, shake, flash)


# ----------------------------------------------------------------------------
# banda sonora chiptune
# ----------------------------------------------------------------------------
SR = 44100
BPM = 144
BEAT = 60.0 / BPM
BAR = BEAT * 4
E8 = BEAT / 2
NOTE_IDX = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}


def midi(name):
    return 12 * (int(name[-1]) + 1) + NOTE_IDX[name[:-1]]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tone(freq, dur, kind='sq', duty=0.5, att=0.004, dec=0.0, rel=0.02):
    n = max(1, int(dur * SR))
    tt = np.arange(n) / SR
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    ph = np.cumsum(f) / SR
    if kind == 'sq':
        w = np.where(ph % 1 < duty, 1.0, -1.0)
    elif kind == 'tri':
        w = 4 * np.abs(ph % 1 - 0.5) - 1
    elif kind == 'saw':
        w = 2 * (ph % 1) - 1
    else:
        w = np.sin(2 * np.pi * ph)
    env = np.minimum(1, tt / att) * np.exp(-dec * tt)
    r = min(n, int(rel * SR))
    env[n - r:] *= np.linspace(1, 0, r)
    return w * env


NRNG = np.random.default_rng(1234)


def noise(dur, dec=10.0, lp=1):
    n = int(dur * SR)
    x = NRNG.uniform(-1, 1, n)
    if lp > 1:
        x = np.convolve(x, np.ones(lp) / lp, mode='same') * math.sqrt(lp) * 0.7
    return x * np.exp(-dec * np.arange(n) / SR)


def kick():
    n = int(0.3 * SR)
    tt = np.arange(n) / SR
    f = 48 + 110 * np.exp(-tt * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)


def snare():
    x = noise(0.2, 16) * 0.7
    t = tone(185, 0.12, 'tri', dec=25) * 0.5
    x[:len(t)] += t
    return x


def hat():
    x = noise(0.05, 70)
    return np.diff(x, prepend=0) * 0.6


def boom(dur=1.5):
    return noise(dur, 3.0, lp=24) * 1.4 + tone(np.linspace(80, 30, int(dur * SR)), dur, 'sine', dec=2.5)


CHORDS = {
    'Am': (45, [57, 60, 64, 69]), 'F': (41, [53, 57, 60, 65]), 'C': (48, [60, 64, 67, 72]),
    'G': (43, [55, 59, 62, 67]), 'E': (40, [52, 56, 59, 64]), 'Dm': (38, [50, 53, 57, 62]),
}
THEME_A = ["E5:2 A5:2 G5:1 A5:1 C6:2", "A5:3 G5:1 F5:2 E5:2",
           "E5:2 G5:2 C6:2 B5:1 C6:1", "D6:4 B5:2 G5:2"]
THEME_B = ["A5:1 G5:1 E5:1 G5:1 A5:2 C6:2", "C6:1 A5:1 F5:2 A5:2 C6:2",
           "G5:2 E5:1 G5:1 C6:2 E6:2", "D6:2 B5:2 D6:2 G6:2"]
BOSS = ["A4:1 A4:1 C5:1 A4:1 E5:1 A4:1 D5:1 C5:1", "B4:1 G4:1 B4:1 D5:1 G5:2 F5:1 D5:1",
        "C5:1 A4:1 C5:1 F5:1 A5:2 G5:1 F5:1", "E5:2 G#5:2 B5:2 E6:2"]
VICTORY = ["C5:1 E5:1 G5:1 C6:3 G5:1 C6:1", "D6:3 B5:1 G5:2 D6:2",
           "C6:2 E6:2 D6:1 C6:1 B5:2", "A5:2 C6:2 F6:4"]


def build_audio():
    n = int(DUR * SR)
    mix_ = np.zeros(n)
    lead = np.zeros(n)

    def add(sig, t0, g=1.0, buf=None):
        b = mix_ if buf is None else buf
        i = int(t0 * SR)
        if i >= n or i < 0:
            return
        j = min(n, i + len(sig))
        b[i:j] += sig[:j - i] * g

    def phrase(spec, t0, buf, g, duty=0.25, octave=0, dec=1.5):
        t = t0
        for tok in spec.split():
            nm, ln = tok.split(':')
            d = int(ln) * E8
            m = midi(nm) + octave
            add(tone(hz(m), d * 0.95, 'sq', duty, dec=dec), t, g, buf)
            add(tone(hz(m - 12), d * 0.95, 'sq', 0.5, dec=dec), t, g * 0.35, buf)
            t += d

    K, S, HH = kick(), snare(), hat()
    prog = ['Am', 'F', 'C', 'G']
    boss_prog = ['Am', 'G', 'F', 'E']
    vic_prog = ['C', 'G', 'Am', 'F']
    for b in range(72):
        t0 = b * BAR
        if b < 6:  # intro
            if t0 >= 0.6:
                root, ch = CHORDS[prog[b % 4]]
                for s16 in range(16):
                    add(tone(hz(ch[s16 % 4] + 12), E8 / 2 * 0.9, 'sq', 0.125, dec=8), t0 + s16 * E8 / 2, 0.07)
                add(tone(hz(root), BAR, 'tri', dec=0.6), t0, 0.25)
        elif b == 6:  # riser antes del golpe del titulo
            root, ch = CHORDS['Am']
            nn = int(BAR * SR)
            add(noise(BAR, 0) * np.linspace(0, 1, nn) ** 2 * 0.5, t0)
            add(tone(np.linspace(hz(45), hz(81), nn), BAR, 'sq', 0.5), t0, 0.08)
        elif 7 <= b <= 41:  # groove principal
            ch_name = prog[b % 4]
            root, ch = CHORDS[ch_name]
            for beat in range(4):
                add(K, t0 + beat * BEAT, 0.9)
                if beat in (1, 3):
                    add(S, t0 + beat * BEAT, 0.55)
            for e in range(8):
                add(HH, t0 + e * E8, 0.35 if e % 2 else 0.2)
                note = root + (12 if e % 2 else 0)
                add(tone(hz(note), E8 * 0.9, 'tri', dec=5), t0 + e * E8, 0.55)
            for s16 in range(16):
                add(tone(hz(ch[s16 % 4] + 12), E8 / 2 * 0.9, 'sq', 0.125, dec=8), t0 + s16 * E8 / 2, 0.05)
            if b >= 9:
                theme = THEME_A if (b // 4) % 2 == 0 else THEME_B
                phrase(theme[b % 4], t0, lead, 0.16)
        elif 42 <= b <= 47:  # breakdown con alarma
            add(tone(hz(33), BAR, 'saw', dec=0.3), t0, 0.18)
            add(K, t0, 0.8)
            add(K, t0 + BEAT * 0.6, 0.5)
            add(K, t0 + 2 * BEAT, 0.8)
            add(K, t0 + 2 * BEAT + BEAT * 0.6, 0.5)
            for k in range(4):
                f = 880 if k % 2 == 0 else 660
                add(tone(f, BEAT * 0.95, 'sq', 0.5, dec=0.5), t0 + k * BEAT, 0.07)
        elif 48 <= b <= 59:  # musica de jefe
            ch_name = boss_prog[b % 4]
            root, ch = CHORDS[ch_name]
            for beat in range(4):
                add(K, t0 + beat * BEAT, 1.0)
                if beat in (1, 3):
                    add(S, t0 + beat * BEAT, 0.6)
            for s16 in range(16):
                add(HH, t0 + s16 * E8 / 2, 0.25)
                if b >= 49:
                    note = root + (12 if s16 % 4 == 2 else 0)
                    add(tone(hz(note), E8 / 2 * 0.9, 'tri', dec=6), t0 + s16 * E8 / 2, 0.55)
                add(tone(hz(ch[(s16 * 3) % 4] + 12), E8 / 2 * 0.9, 'sq', 0.125, dec=10),
                    t0 + s16 * E8 / 2, 0.045)
            if b >= 51:
                phrase(BOSS[b % 4], t0, lead, 0.17, duty=0.5, dec=3)
        elif 60 <= b <= 65:  # golpe final y caida
            if t0 < 104.0:
                add(tone(hz(33), BAR, 'saw', dec=0.2), t0, 0.15)
                add(K, t0, 0.7)
                add(K, t0 + 2 * BEAT, 0.7)
            elif b >= 63:
                root, ch = CHORDS[['F', 'G', 'G'][b - 63]]
                for k in ch:
                    add(tone(hz(k), BAR * 0.98, 'sq', 0.25, dec=0.8), t0, 0.05)
                add(tone(hz(root), BAR, 'tri', dec=0.5), t0, 0.4)
                if b == 65:
                    for s16 in range(16):
                        add(S, t0 + s16 * E8 / 2, 0.2 + 0.4 * s16 / 16)
        elif 66 <= b <= 69:  # victoria
            ch_name = vic_prog[b - 66]
            root, ch = CHORDS[ch_name]
            for beat in range(4):
                add(K, t0 + beat * BEAT, 0.85)
                if beat in (1, 3):
                    add(S, t0 + beat * BEAT, 0.5)
            for e in range(8):
                add(HH, t0 + e * E8, 0.25)
                add(tone(hz(root + (12 if e % 2 else 0)), E8 * 0.9, 'tri', dec=4), t0 + e * E8, 0.5)
            for s16 in range(16):
                add(tone(hz(ch[s16 % 4] + 12), E8 / 2 * 0.9, 'sq', 0.125, dec=8), t0 + s16 * E8 / 2, 0.05)
            phrase(VICTORY[b - 66], t0, lead, 0.18)
    # eco del lead
    d = int(BEAT * 0.75 * SR)
    echo = np.zeros(n)
    echo[d:] = lead[:-d] * 0.35
    echo[2 * d:] += lead[:-2 * d] * 0.15
    mix_ += lead + echo

    # efectos de sonido
    add(noise(0.15, 20) * 0.6, 0.0)
    add(tone(60, 0.6, 'sine', dec=5), 0.0, 0.5)
    add(tone(hz(83), 0.08, 'sq', 0.5), 6.0, 0.25)
    add(tone(hz(88), 0.5, 'sq', 0.5, dec=5), 6.08, 0.25)
    slam = 10.0 + SLAM
    add(boom(2.0), slam, 0.8)
    add(K, slam, 1.2)
    for t0 in (21.8, 23.0, 24.2, 25.2, 25.9, 26.5):
        add(tone(hz(93), 0.05, 'sq', 0.5), t0, 0.15)
    for i, m in enumerate([72, 76, 79, 84, 88]):
        add(tone(hz(m), 0.08, 'sq', 0.25), 27.0 + i * 0.06, 0.2)
    for ft in (7.3, 7.8, 8.4, 9.0, 9.4):
        add(noise(0.4, 12, lp=3) * 0.5, 20 + ft)
    for i in range(30):  # combate
        die = 40 + 0.2 + i * 0.3 + (330 - 150) / 95.0
        if die < 50:
            add(noise(0.08, 30) * 0.3, die - 0.03)
            add(noise(0.35, 12, lp=6) * 0.45, die)
    for b0 in (1.8, 5.2, 8.0):
        add(boom(1.8), 50 + b0, 0.55)
    nn = int(0.8 * SR)
    add(tone(np.geomspace(200, 2400, nn), 0.8, 'sq', 0.25), 62.5, 0.16)
    for i, m in enumerate(range(60, 96, 3)):
        add(tone(hz(m), 0.05, 'sq', 0.5), 62.5 + i * 0.04, 0.1)
    for k in range(int(10 / 0.24)):  # disparos bullet hell
        add(tone(np.linspace(1600, 500, int(0.05 * SR)), 0.05, 'sq', 0.5), 90 + k * 0.24, 0.05)
    for k in range(0, 76, 2):
        add(noise(0.2, 15, lp=4) * 0.25, 90 + k * 0.13)
    nr = int(1.8 * SR)
    roar = tone(np.linspace(70, 40, nr) * (1 + 0.1 * np.sin(np.arange(nr) / SR * 40)), 1.8, 'saw', dec=1.0)
    add((roar + noise(1.8, 1.2, lp=12)) * 0.6, 85.5)
    nn = int(4.0 * SR)
    add(tone(np.geomspace(80, 1400, nn) * (1 + 0.03 * np.sin(np.arange(nn) / SR * 50)), 4.0, 'sq', 0.5,
             dec=0) * np.linspace(0, 1, nn), 100.0, 0.12)
    add(noise(4.0, 0) * np.linspace(0, 1, nn) ** 2 * 0.3, 100.0)
    add(boom(3.0), 104.0, 1.3)
    add(K, 104.0, 1.5)
    rng = np.random.default_rng(5)
    for k in range(50):
        add(noise(0.1, 30) * 0.3, 104.7 + rng.uniform(0, 3.5))
    for k in range(8):
        add(noise(0.6, 8, lp=8) * 0.5, 104.7 + k * 0.25)
    # corte del CRT
    off = 110 + CRT_OFF
    mix_[int(off * SR):] = 0
    add(tone(np.geomspace(2000, 50, int(0.5 * SR)), 0.5, 'sine', dec=3), off, 0.4)
    for t0 in (off + 1.8, off + 2.9):
        add(tone(hz(76), 0.12, 'sq', 0.5), t0, 0.2)
        add(tone(hz(64), 0.2, 'sq', 0.5), t0 + 0.13, 0.2)
    mix_ = np.tanh(mix_ * 1.1)
    mix_ = mix_ / (np.abs(mix_).max() + 1e-9) * 0.9
    fade = int(0.01 * SR)
    mix_[:fade] *= np.linspace(0, 1, fade)
    return (mix_ * 32767).astype(np.int16)


def write_wav(path, data):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    args = sys.argv[1:]
    if args and args[0] == '--stills':
        os.makedirs(os.path.join(HERE, 'stills'), exist_ok=True)
        for s in args[1:]:
            n = int(float(s) * FPS)
            Image.fromarray(render_frame(n)).save(os.path.join(HERE, 'stills', 'frame_%06.2f.png' % float(s)))
        return
    wav = os.path.join(HERE, 'soundtrack.wav')
    out = os.path.join(HERE, 'last_game.mp4')
    print("Sintetizando banda sonora...")
    write_wav(wav, build_audio())
    total = int(DUR * FPS)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '%dx%d' % (OW, OH), '-r', str(FPS), '-i', '-', '-i', wav,
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        proc.stdin.write(render_frame(n).tobytes())
        if n % (FPS * 5) == 0:
            print("  %5.1fs / %ds" % (n / FPS, DUR), flush=True)
    proc.stdin.close()
    proc.wait()
    print("Listo:", out)


if __name__ == '__main__':
    main()
