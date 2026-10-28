#!/usr/bin/env python3
"""
IN THE POOL - video musical generado 100% por codigo.

Un piano en perspectiva 3D en primer plano (en foco) cuyas teclas se hunden y brillan
con las notas detectadas en el audio, y fondos nostalgicos desenfocados (bokeh) que
cambian, laten y destellan siguiendo el ritmo. Profundidad de campo real por capas:
fondo lejano muy desenfocado, siluetas medias, piano con enfoque que sigue la musica,
y particulas de luz / polvo en primer plano fuera de foco.

Uso:
    python3 make_video.py                    -> in_the_pool_1080p.mp4 (1920x1080, 24 fps)
    python3 make_video.py --stills 20 75 140 -> PNGs de esos segundos (para revisar)
Requiere: numpy, Pillow, ffmpeg.
"""
import math
import multiprocessing as mp
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import analysis

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, 'in_the_pool.mp3')
OUT = os.path.join(HERE, 'in_the_pool_1080p.mp4')
FPS = 24
OW, OH = 1920, 1080          # salida
LW, LH = 480, 270            # fondo a baja resolucion (el escalado ya desenfoca)
BW, BH = 540, 304            # lienzo del fondo con margen para el paralaje
HW, HH = 960, 540            # capa aditiva de particulas
SS = 2                       # supermuestreo del piano
N_SCENES = 5
FONT = '/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf'

ANA = None
CACHE = {}


# ---------------------------------------------------------------- utilidades

def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoothstep(a, b, x):
    t = clamp((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def vgrad(stops, h=BH, w=BW):
    y = np.linspace(0, 1, h)
    pos = [p for p, _ in stops]
    col = np.stack([np.interp(y, pos, [c[i] for _, c in stops]) for i in range(3)], -1)
    return np.repeat(col[:, None, :], w, axis=1).astype(np.float32)


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def to_arr(im):
    return np.asarray(im, dtype=np.float32) / 255.0


def blur(a, r):
    return to_arr(to_img(a).filter(ImageFilter.GaussianBlur(r)))


def radial(cx, cy, sigma, h=BH, w=BW):
    yy, xx = np.mgrid[0:h, 0:w]
    return np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2)).astype(np.float32)


def cached(key, fn):
    if key not in CACHE:
        CACHE[key] = fn()
    return CACHE[key]


def bokeh_sprite(r, soft):
    """Disco de bokeh: borde suave y aro ligeramente mas brillante, como una lente real."""
    def make():
        R = int(math.ceil(r + 2))
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
        d = np.sqrt(xx ** 2 + yy ** 2) / max(r, 0.5)
        edge = np.clip((1 - d) / max(soft, 0.05) + 0.5, 0, 1)
        rim = 0.85 + 0.2 * np.clip(d, 0, 1) ** 4
        return (edge * rim).astype(np.float32)
    return cached(('bk', round(r * 2) / 2, soft), make)


def glow_sprite(r):
    def make():
        R = int(math.ceil(r * 3 + 1))
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
        g = np.exp(-(xx ** 2 + yy ** 2) / (2 * r * r))
        return g.astype(np.float32)
    return cached(('gl', round(r * 4) / 4), make)


def stamp(arr, spr, x, y, color):
    h, w = arr.shape[:2]
    R = spr.shape[0] // 2
    xi, yi = int(round(x)), int(round(y))
    x0, y0, x1, y1 = xi - R, yi - R, xi + R + 1, yi + R + 1
    if x1 <= 0 or y1 <= 0 or x0 >= w or y0 >= h:
        return
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = spr.shape[1] - max(0, x1 - w), spr.shape[0] - max(0, y1 - h)
    arr[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] += spr[sy0:sy1, sx0:sx1, None] * color


def rng(seed):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------- escenas de fondo
# Cada escena: capa lejana (RGB), capa media de siluetas (RGBA), lista de bokeh,
# color de acento para el piano y una funcion de animacion opcional.

def scene_pool():
    hor = 0.55
    far = vgrad([(0, (0.10, 0.09, 0.25)), (0.25, (0.33, 0.17, 0.40)), (0.45, (0.92, 0.50, 0.45)),
                 (hor - 0.005, (1.0, 0.80, 0.58)), (hor + 0.005, (0.30, 0.55, 0.62)), (0.75, (0.08, 0.32, 0.42)),
                 (1, (0.03, 0.14, 0.22))])
    yy = np.arange(BH)[:, None] / BH
    sun = radial(BW * 0.60, BH * (hor - 0.04), 38)[..., None] * np.array([1.0, 0.62, 0.35]) * 0.55
    disc = (radial(BW * 0.60, BH * (hor - 0.04), 9) > 0.35)[..., None] * (yy < hor)[..., None]
    far = far + sun + disc * np.array([1.0, 0.85, 0.6]) * 0.8
    far = blur(far, 2.5)

    mid = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(mid)
    sil = (22, 12, 30, 255)

    def palm(x, base, h, lean, s):
        pts = [(x + lean * (i / 10) ** 1.6 * h, base - i / 10 * h) for i in range(11)]
        d.line(pts, fill=sil, width=max(2, int(5 * s)))
        tx, ty = pts[-1]
        for a in np.linspace(0, 2 * math.pi, 9, endpoint=False):
            L = 55 * s
            ex, ey = tx + math.cos(a) * L, ty + math.sin(a) * L * 0.45 + 18 * s
            mx, my = tx + math.cos(a) * L * 0.5, ty + math.sin(a) * L * 0.25 - 6 * s
            d.polygon([(tx, ty), (mx, my - 5 * s), (ex, ey), (mx, my + 4 * s)], fill=sil)
    palm(70, BH * 0.95, 190, 40, 1.0)
    palm(30, BH * 0.95, 150, -25, 0.8)
    palm(470, BH * 0.95, 205, -45, 1.05)
    d.rectangle([0, int(BH * 0.86), BW, BH], fill=(18, 14, 26, 255))
    mid = mid.filter(ImageFilter.GaussianBlur(2.2))

    bok = []
    cols = [(1.0, 0.70, 0.35), (1.0, 0.45, 0.55), (0.55, 1.0, 0.75), (1.0, 0.88, 0.55)]
    for strand, (y0, sag) in enumerate([(18, 55), (40, 38)]):
        for i in range(17):
            u = (i + 0.5 * strand) / 16
            x = -10 + u * (BW + 20)
            y = y0 + sag * 4 * u * (1 - u)
            bok.append((x, y, 7.5 - strand * 1.5, cols[(i + strand) % 4], i * 1.7, i % 4, 0.55 - 0.2 * strand))

    def anim(arr, t, e, dx):
        h = int(LH * (hor - 0.012) + 0)
        yy, xx = np.mgrid[h:LH, 0:LW].astype(np.float32)
        xs = xx + dx * 0.5
        k = (yy - h + 4) / (LH - h)
        c = np.sin(xs * 0.11 / (0.3 + k) + t * 1.1 + np.sin(yy * 0.4 + t * 0.7) * 1.5)
        c += np.sin(xs * 0.05 / (0.3 + k) - t * 0.8 + yy * 0.23)
        c = np.clip(c - 0.9, 0, 1) ** 1.5 * (0.10 + 0.25 * e)
        streak = np.exp(-((xs - LW * 0.585) / (6 + 40 * k)) ** 2) * (0.5 + 0.5 * np.sin(yy * 1.7 - t * 3))
        arr[h:LH] += c[..., None] * np.array([0.6, 1.0, 1.0]) + streak[..., None] * np.array([1, 0.7, 0.4]) * 0.35
    return dict(far=far, mid=mid, bokeh=bok, accent=(1.0, 0.72, 0.42), anim=anim, name='piscina al atardecer')


def scene_rain():
    far = vgrad([(0, (0.03, 0.04, 0.11)), (0.5, (0.09, 0.08, 0.20)), (1, (0.28, 0.13, 0.22))])
    far = far + radial(BW * 0.3, BH * 1.0, 120)[..., None] * np.array([0.5, 0.25, 0.15]) * 0.4
    far = blur(far, 3)
    r = rng(11)
    cols = [(1.0, 0.68, 0.32), (0.30, 0.80, 0.95), (1.0, 0.30, 0.30), (0.92, 0.92, 1.0), (0.95, 0.40, 0.85)]
    bok = []
    for i in range(75):
        y = BH * (0.30 + 0.70 * r.random() ** 0.7)
        bok.append((r.random() * BW, y, 3 + 10 * r.random() ** 2, cols[r.integers(5)], r.random() * 6,
                    int(r.integers(4)), 0.25 + 0.35 * r.random()))
    mid = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(mid)
    fr = (6, 6, 12, 245)
    d.rectangle([0, 0, BW, 14], fill=fr)
    d.rectangle([0, 0, 18, BH], fill=fr)
    d.rectangle([BW - 18, 0, BW, BH], fill=fr)
    d.rectangle([int(BW * 0.62), 0, int(BW * 0.62) + 11, BH], fill=fr)
    d.rectangle([0, int(BH * 0.36), BW, int(BH * 0.36) + 9], fill=fr)
    d.line([(int(BW * 0.62) + 11, 14), (int(BW * 0.62) + 11, BH)], fill=(120, 80, 50, 160), width=1)
    mid = mid.filter(ImageFilter.GaussianBlur(2.4))
    drops = r.random((160, 4))

    def anim(arr, t, e, dx):
        for x0, y0, sp, b in drops:
            x = int((x0 * LW + dx * 0.9) % LW)
            y = int((y0 * LH + t * (180 + 140 * sp)) % (LH + 30)) - 30
            y0c, y1c = max(0, y), min(LH, y + 10 + int(12 * sp))
            if y1c > y0c:
                arr[y0c:y1c, x] += (0.05 + 0.08 * b) * (0.6 + 0.6 * e)
        # gotas en el vidrio que resbalan despacio
        for i in range(25):
            x = (drops[i, 0] * LW * 1.3 + dx) % LW
            y = (drops[i, 1] * LH + t * (3 + 6 * drops[i, 2])) % LH
            stamp(arr, glow_sprite(1.0 + drops[i, 3]), x, y, np.array([0.5, 0.55, 0.65]) * 0.25)
    return dict(far=far, mid=mid, bokeh=bok, accent=(0.70, 0.86, 1.0), anim=anim, name='lluvia en la ventana')


def scene_room():
    far = vgrad([(0, (0.30, 0.18, 0.10)), (0.6, (0.50, 0.32, 0.18)), (1, (0.40, 0.24, 0.13))])
    win = np.zeros((BH, BW), np.float32)
    win[int(BH * 0.08):int(BH * 0.62), int(BW * 0.14):int(BW * 0.46)] = 1
    win[:, int(BW * 0.295):int(BW * 0.305)] *= 0.3
    win[int(BH * 0.34):int(BH * 0.35), :] *= 0.3
    win_b = blur(np.repeat(win[..., None], 3, -1), 6)
    far = far * (1 - win_b * 0.9) + win_b * np.array([1.0, 0.90, 0.68])
    far = far + blur(np.repeat(win[..., None], 3, -1), 30) * np.array([1.0, 0.7, 0.4]) * 0.45
    far = far + radial(BW * 0.82, BH * 0.33, 40)[..., None] * np.array([1.0, 0.6, 0.25]) * 0.45
    for (x0, y0, x1, y1) in [(330, 60, 390, 135), (400, 85, 440, 140)]:
        far[y0:y1, x0:x1] *= 0.55
        far[y0 + 6:y1 - 6, x0 + 6:x1 - 6] = far[y0 + 6:y1 - 6, x0 + 6:x1 - 6] * 0.7 + np.array([0.35, 0.28, 0.2]) * 0.3
    far = blur(far, 2)
    mid = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(mid)
    cur = [(0, 0), (60, 0)] + [(48 + 10 * math.sin(y * 0.06), y) for y in range(0, BH + 1, 8)] + [(0, BH)]
    d.polygon(cur, fill=(40, 20, 12, 235))
    d.polygon([(420, 75), (470, 75), (488, 112), (402, 112)], fill=(120, 60, 25, 255))   # pantalla de lampara
    d.rectangle([443, 112, 447, 260], fill=(25, 14, 10, 255))
    for a in np.linspace(-1.2, 1.2, 9):                                                 # planta
        L = 70
        d.line([(110, 280), (110 + math.sin(a) * L * 0.8, 280 - math.cos(a) * L)], fill=(28, 18, 10, 255), width=5)
        d.ellipse([110 + math.sin(a) * L * 0.8 - 12, 280 - math.cos(a) * L - 6,
                   110 + math.sin(a) * L * 0.8 + 12, 280 - math.cos(a) * L + 6], fill=(28, 18, 10, 255))
    mid = mid.filter(ImageFilter.GaussianBlur(2.3))
    r = rng(5)
    dust = r.random((70, 5))
    bok = [(445, 95, 9, (1.0, 0.72, 0.4), 0, 0, 0.4)]
    for i in range(10):
        bok.append((r.random() * BW, BH * (0.1 + 0.5 * r.random()), 4 + 6 * r.random(), (1.0, 0.85, 0.6), i, i % 4, 0.18))
    yy, xx = np.mgrid[0:LH, 0:LW].astype(np.float32)

    def anim(arr, t, e, dx):
        # rayos de luz diagonales desde la ventana
        u = (xx + dx * 0.4 - LW * 0.15) - (yy - LH * 0.1) * 0.85
        beams = sum(np.exp(-((u - c) / w) ** 2) for c, w in [(40, 18), (95, 10), (150, 22)])
        fade = np.clip(yy / LH * 1.4, 0, 1) * np.clip(1 - (xx - LW * 0.15) / (LW * 0.9), 0, 1)
        arr += (beams * fade * (0.05 + 0.12 * e))[..., None] * np.array([1.0, 0.8, 0.5])
        for x0, y0, sx, sy, b in dust:
            x = (x0 * LW + 12 * math.sin(t * 0.2 * sx + b * 9) + t * 3 + dx) % LW
            y = (y0 * LH + 10 * math.sin(t * 0.3 * sy + b * 5) - t * 2) % LH
            stamp(arr, glow_sprite(0.7 + b * 0.6), x, y, np.array([1, 0.85, 0.6]) * (0.15 + 0.25 * e))
    return dict(far=far, mid=mid, bokeh=bok, accent=(1.0, 0.82, 0.50), anim=anim, name='habitacion dorada')


def scene_fireflies():
    hor = 0.62
    far = vgrad([(0, (0.05, 0.05, 0.17)), (0.35, (0.22, 0.11, 0.33)), (hor, (0.80, 0.42, 0.42)), (1, (0.3, 0.12, 0.2))])
    far = far + radial(BW * 0.80, BH * 0.18, 14)[..., None] * np.array([0.9, 0.9, 1.0]) * 0.5
    far = far + radial(BW * 0.80, BH * 0.18, 4)[..., None] * 0.7
    far = blur(far, 2)
    mid = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(mid)
    hill1 = [(x, BH * hor + 18 * math.sin(x * 0.012 + 1) + 8 * math.sin(x * 0.04)) for x in range(0, BW + 10, 10)]
    d.polygon(hill1 + [(BW, BH), (0, BH)], fill=(45, 22, 50, 255))
    hill2 = [(x, BH * (hor + 0.08) + 22 * math.sin(x * 0.009 + 3)) for x in range(0, BW + 10, 10)]
    d.polygon(hill2 + [(BW, BH), (0, BH)], fill=(22, 10, 28, 255))
    for cx, cy, rr in [(90, 150, 34), (60, 165, 26), (120, 170, 24), (100, 120, 22)]:
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(14, 7, 20, 255))
    d.rectangle([86, 170, 96, 240], fill=(14, 7, 20, 255))
    d.rectangle([360, 168, 400, 196], fill=(30, 14, 34, 255))
    d.polygon([(355, 168), (380, 150), (405, 168)], fill=(30, 14, 34, 255))
    d.rectangle([368, 176, 378, 186], fill=(255, 190, 110, 255))
    mid = mid.filter(ImageFilter.GaussianBlur(2.2))
    r = rng(3)
    stars = r.random((90, 3))
    flies = r.random((45, 6))

    def anim(arr, t, e, dx):
        for x0, y0, ph in stars:
            x, y = (x0 * LW + dx * 0.3) % LW, y0 * LH * 0.5
            tw = 0.5 + 0.5 * math.sin(t * (1 + 2 * ph) + ph * 20)
            stamp(arr, glow_sprite(0.6), x, y, np.array([0.9, 0.9, 1.0]) * (0.15 + 0.35 * tw))
    bok = []
    for i, (x0, y0, a, b, ph, s) in enumerate(flies):
        bok.append(('fly', x0, y0, a, b, ph, s, i % 4))
    return dict(far=far, mid=mid, bokeh=bok, accent=(0.85, 1.0, 0.55), anim=anim, name='luciernagas')


def scene_fair():
    hor = 0.66
    far = vgrad([(0, (0.10, 0.17, 0.36)), (0.4, (0.50, 0.38, 0.55)), (hor, (1.0, 0.62, 0.42)), (1, (0.25, 0.12, 0.15))])
    far = blur(far, 2)
    mid = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(mid)
    sil = (26, 14, 30, 255)
    d.rectangle([0, int(BH * hor) + 10, BW, BH], fill=sil)
    for x0, w, h in [(20, 70, 50), (110, 60, 38), (420, 90, 46)]:
        y = BH * hor + 12
        d.polygon([(x0, y), (x0 + w / 2, y - h), (x0 + w, y)], fill=sil)
    cx, cy = BW * 0.64, BH * 0.40
    d.polygon([(cx - 6, cy), (cx + 6, cy), (cx + 60, BH * hor + 12), (cx + 48, BH * hor + 12)], fill=sil)
    d.polygon([(cx - 6, cy), (cx + 6, cy), (cx - 48, BH * hor + 12), (cx - 60, BH * hor + 12)], fill=sil)
    mid = mid.filter(ImageFilter.GaussianBlur(2.0))
    R = BH * 0.32
    bok = []
    cols = [(1.0, 0.85, 0.6), (1.0, 0.45, 0.65), (0.45, 0.9, 1.0)]
    for i in range(24):
        bok.append(('wheel', i, cx, cy, R, cols[i % 3]))
    r = rng(8)
    for i in range(20):
        u = i / 19
        bok.append((20 + u * 140, BH * hor - 30 + 25 * 4 * u * (1 - u) * 0.5, 4.5, cols[i % 3], i, i % 4, 0.45))
        bok.append((410 + u * 110, BH * hor - 20 + 14 * 4 * u * (1 - u), 4.0, cols[(i + 1) % 3], i, (i + 2) % 4, 0.45))

    def anim(arr, t, e, dx):
        pass
    return dict(far=far, mid=mid, bokeh=bok, accent=(1.0, 0.62, 0.72), anim=anim, name='feria lejana',
                wheel=(cx, cy, R))


SCENES = [scene_pool, scene_rain, scene_room, scene_fireflies, scene_fair]


def get_scene(i):
    def make():
        s = SCENES[i]()
        s['far_img'] = to_img(s['far'])
        return s
    return cached(('scene', i), make)


def affine(img, zoom, dx, dy):
    k = 1.0 / zoom
    data = (k, 0, BW / 2 + dx - LW / 2 * k, 0, k, BH / 2 + dy - LH / 2 * k)
    return img.transform((LW, LH), Image.AFFINE, data, Image.BILINEAR)


def render_scene(i, t, f, cam_dx):
    """Fondo de la escena i a baja resolucion (float RGB)."""
    S = get_scene(i)
    A = ANA
    e, hit, bp, bi = A['energy'][f], A['hit'][f], A['beat_pulse'][f], A['beat_idx'][f]
    zoom = 1.0 + 0.012 * bp * (0.3 + e) + 0.02 * math.sin(t * 0.05)
    dxf, dxm = cam_dx * 5, cam_dx * 11
    arr = to_arr(affine(S['far_img'], zoom, dxf, 0))
    S['anim'](arr, t, e, dxf)
    if 'wheel' in S:  # la noria gira y se dibuja cada cuadro
        cx, cy, R = S['wheel']
        im = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        rot = t * 0.08
        for j in range(12):
            a = rot + j * math.pi / 6
            d.line([(cx, cy), (cx + R * math.cos(a), cy + R * math.sin(a))], fill=(30, 16, 34, 230), width=2)
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(30, 16, 34, 240), width=3)
        d.ellipse([cx - R * 0.6, cy - R * 0.6, cx + R * 0.6, cy + R * 0.6], outline=(30, 16, 34, 200), width=2)
        mid = Image.alpha_composite(S['mid'], im.filter(ImageFilter.GaussianBlur(2.0)))
    else:
        mid = S['mid']
    m = np.asarray(affine(mid, zoom, dxm, 0), dtype=np.float32) / 255.0
    arr = arr * (1 - m[..., 3:]) + m[..., :3] * m[..., 3:]

    def to_out(x, y, par):
        return (x - BW / 2 - cam_dx * par) * zoom + LW / 2, (y - BH / 2) * zoom + LH / 2

    gain = 0.55 + 0.7 * e
    for b in S['bokeh']:
        if b[0] == 'fly':
            _, x0, y0, a, bb, ph, s, g = b
            x = x0 * BW + 30 * math.sin(t * (0.2 + 0.3 * a) + ph * 6)
            y = BH * (0.35 + 0.55 * y0) + 18 * math.sin(t * (0.25 + 0.3 * bb) + ph * 4)
            blink = smoothstep(0.2, 1.0, math.sin(t * (0.9 + s) + ph * 13))
            flare = bp * (1.0 if (bi % 4) == g else 0.25)
            br = (0.15 + 0.6 * blink + 0.8 * flare) * gain
            ox, oy = to_out(x, y, 8)
            stamp(arr, bokeh_sprite(2 + 5 * s, 0.6), ox, oy, np.array([0.85, 1.0, 0.45]) * br * 0.5)
        elif b[0] == 'wheel':
            _, j, cx, cy, R, col = b
            a = t * 0.08 + j * math.pi / 12
            ox, oy = to_out(cx + R * math.cos(a), cy + R * math.sin(a), 11)
            chase = 1.0 if (j + bi) % 3 == 0 else 0.35
            br = (0.25 + 0.55 * chase * (0.5 + 0.5 * bp)) * gain
            stamp(arr, bokeh_sprite(6.0, 0.5), ox, oy, np.array(col) * br)
        else:
            x, y, r, col, ph, g, base = b
            tw = 0.75 + 0.25 * math.sin(t * 0.8 + ph)
            flare = bp * (1.0 if (bi % 4) == g else 0.15) * (0.4 + e)
            br = (base * tw + 0.5 * flare + 0.3 * hit * e) * gain
            ox, oy = to_out(x, y, 7)
            stamp(arr, bokeh_sprite(r, 0.5), ox, oy, np.array(col) * br)
    return arr


def background(t, f, cam_dx):
    A = ANA
    ch, sc = A['changes'], A['scenes']
    k = int(np.searchsorted(ch, t, side='right') - 1)
    cur = int(sc[k])
    arr = render_scene(cur, t, f, cam_dx)
    e_at = A['energy'][min(len(A['energy']) - 1, int(ch[k] * FPS))]
    trans = 2.2 - 1.4 * e_at
    p = (t - ch[k]) / trans
    if k > 0 and p < 1:
        prev = render_scene(int(sc[k - 1]), t, f, cam_dx)
        w = smoothstep(0, 1, p)
        arr = prev * (1 - w) + arr * w
    # gradacion: temperatura y brillo con la energia
    e = A['energy'][f]
    arr = arr * (0.80 + 0.30 * e)
    lum = arr.mean(-1, keepdims=True)
    arr = lum + (arr - lum) * 0.88
    arr = arr * 0.92 + np.array([0.035, 0.022, 0.03])
    return arr, cur, k


# ---------------------------------------------------------------- piano 3D

WHITE_W, WHITE_L, WHITE_H = 1.0, 6.2, 0.85
BLACK_W, BLACK_L, BLACK_H = 0.56, 3.9, 0.62
N_KEYS = analysis.HIGH_MIDI - analysis.LOW_MIDI + 1
WHITE_SEMIS = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}
BLACK_SEMIS = {1: (0, -0.09), 3: (1, 0.09), 6: (3, -0.11), 8: (4, 0.0), 10: (5, 0.11)}


def key_layout():
    keys = []
    for k in range(N_KEYS):
        o, s = divmod(k, 12)
        if s in WHITE_SEMIS:
            x0 = (o * 7 + WHITE_SEMIS[s]) * WHITE_W
            keys.append(dict(k=k, white=True, x0=x0 + 0.03, x1=x0 + WHITE_W - 0.03))
        else:
            left, off = BLACK_SEMIS[s]
            cx = (o * 7 + left + 1 + off) * WHITE_W
            keys.append(dict(k=k, white=False, x0=cx - BLACK_W / 2, x1=cx + BLACK_W / 2))
    return keys


KEYS = key_layout()
KB_LEN = 36 * WHITE_W


class Camera:
    def __init__(self, pos, target, f):
        self.p = np.array(pos, float)
        fw = np.array(target, float) - self.p
        self.fw = fw / np.linalg.norm(fw)
        up = np.array([0.0, 1.0, 0.0])
        rt = np.cross(up, self.fw)
        self.rt = rt / np.linalg.norm(rt)
        self.up = np.cross(self.fw, self.rt)
        self.f = f

    def depth(self, P):
        return (np.asarray(P) - self.p) @ self.fw

    def project(self, P, scale=1.0):
        v = np.asarray(P, float) - self.p
        z = v @ self.fw
        x = v @ self.rt
        y = v @ self.up
        z = np.maximum(z, 1e-3)
        return np.stack([OW / 2 + self.f * x / z, OH / 2 - self.f * y / z], -1) * scale, z


def camera_at(t, f):
    A = ANA
    bp, e = A['beat_pulse'][f], A['energy'][f]
    cx = 7.5 + 2.6 * math.sin(2 * math.pi * t / 75) + 1.2 * math.sin(2 * math.pi * t / 31)
    cy = 6.6 + 0.6 * math.sin(2 * math.pi * t / 47)
    cz = -8.8 + 0.7 * math.sin(2 * math.pi * t / 59) + 0.10 * bp * e
    tx = cx + 11.5 + 1.5 * math.sin(2 * math.pi * t / 90)
    return Camera((cx, cy, cz), (tx, 2.4, 6.0), 1050), cx - 7.5


def box_faces(x0, x1, ytf, ytb, ybot, z0, z1):
    """Caras de una tecla (prisma inclinado si esta pulsada): nombre -> vertices."""
    return {
        'top': [(x0, ytf, z0), (x1, ytf, z0), (x1, ytb, z1), (x0, ytb, z1)],
        'front': [(x0, ytf, z0), (x1, ytf, z0), (x1, ybot, z0), (x0, ybot, z0)],
        'left': [(x0, ytf, z0), (x0, ytb, z1), (x0, ybot, z1), (x0, ybot, z0)],
        'right': [(x1, ytf, z0), (x1, ytb, z1), (x1, ybot, z1), (x1, ybot, z0)],
    }


def shade(col, k):
    return tuple(c * k for c in col)


def rgb255(c, a=255):
    return tuple(int(clamp(v) * 255) for v in c) + (a,)


def render_piano(cam, press, accent, focus_d, bg_mean):
    """Devuelve (capa RGBA del piano 1080p, mascara de desenfoque, capa de brillo 480x270)."""
    img = Image.new('RGBA', (OW * SS, OH * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    mask = Image.new('L', (LW, LH), 255)
    dm = ImageDraw.Draw(mask)
    glow = Image.new('RGB', (LW, LH), (0, 0, 0))
    dg = ImageDraw.Draw(glow)
    acc = np.array(accent)

    def coc(depth):
        return int(clamp(abs(1.0 / depth - 1.0 / focus_d) * 21) * 255)

    def poly(verts, col, glow_col=None, mask_on=True):
        V = np.array(verts, float)
        pts, z = cam.project(V, SS)
        if z.min() < 0.6:
            return
        flat = [tuple(p) for p in pts]
        d.polygon(flat, fill=col)
        if mask_on:
            dm.polygon([(x / (SS * 4), y / (SS * 4)) for x, y in flat], fill=coc(z.mean()))
        if glow_col is not None:
            dg.polygon([(x / (SS * 4), y / (SS * 4)) for x, y in flat], fill=glow_col)

    lac = (0.035, 0.03, 0.035)
    refl = tuple(0.05 + 0.35 * c for c in bg_mean)
    # tapa (fallboard) laqueada al fondo, con un reflejo del ambiente
    poly([(-1.2, 0.3, 6.5), (KB_LEN + 1.2, 0.3, 6.5), (KB_LEN + 1.2, 2.3, 6.9), (-1.2, 2.3, 6.9)], rgb255(lac))
    poly([(-1.2, 1.55, 6.75), (KB_LEN + 1.2, 1.55, 6.75), (KB_LEN + 1.2, 1.85, 6.81), (-1.2, 1.85, 6.81)],
         rgb255(refl))
    poly([(-1.2, 2.3, 6.9), (KB_LEN + 1.2, 2.3, 6.9), (KB_LEN + 1.2, 2.45, 8.5), (-1.2, 2.45, 8.5)],
         rgb255(shade(lac, 1.6)))
    # lecho oscuro bajo las teclas (se ve entre las rendijas)
    poly([(-0.2, -0.3, -0.05), (KB_LEN + 0.2, -0.3, -0.05), (KB_LEN + 0.2, -0.3, 6.5), (-0.2, -0.3, 6.5)],
         rgb255((0.02, 0.015, 0.02)))
    # mejilla lejana
    poly([(KB_LEN + 0.1, 1.1, -0.3), (KB_LEN + 1.2, 1.1, -0.3), (KB_LEN + 1.2, 1.1, 6.6), (KB_LEN + 0.1, 1.1, 6.6)],
         rgb255(shade(lac, 2.2)))
    poly([(KB_LEN + 0.1, 1.1, -0.3), (KB_LEN + 0.1, 1.1, 6.6), (KB_LEN + 0.1, -0.9, 6.6), (KB_LEN + 0.1, -0.9, -0.3)],
         rgb255(shade(lac, 1.4)))

    ivory = np.array([0.93, 0.88, 0.78])
    order = sorted(KEYS, key=lambda K: -abs((K['x0'] + K['x1']) / 2 - cam.p[0]))
    for white in (True, False):
        for K in order:
            if K['white'] != white:
                continue
            p = float(press[K['k']])
            x0, x1 = K['x0'], K['x1']
            if white:
                z0, z1, top, h = 0.0, WHITE_L, 0.0, WHITE_H
                base = ivory
            else:
                z0, z1, top, h = WHITE_L - BLACK_L, WHITE_L, BLACK_H, BLACK_H + 0.25
                base = np.array([0.055, 0.05, 0.055])
            drop = (0.36 if white else 0.40) * p
            ytf, ytb = top - drop, top - drop * 0.15
            faces = box_faces(x0, x1, ytf, ytb, top - h, z0, z1)
            dist = cam.depth(((x0 + x1) / 2, top, (z0 + z1) / 2))
            fog = clamp((dist - 14) / 70, 0, 0.3)
            lit = base * (1 - 0.55 * p) + acc * (0.9 if white else 0.65) * p
            if white:
                lit = lit + acc * 0.25 * p
            lit = lit * (1 - fog) + np.array(bg_mean) * fog
            vis = {'top': cam.p[1] > ytf, 'front': True,
                   'left': cam.p[0] < x0, 'right': cam.p[0] > x1}
            for name in ('left', 'right', 'front', 'top'):
                if not vis[name]:
                    continue
                kf = {'top': 1.0, 'front': 0.70, 'left': 0.55, 'right': 0.55}[name]
                if not white and name == 'top':
                    kf = 1.6
                gcol = None
                if name == 'top' and p > 0.02:
                    gcol = rgb255(acc * p * (0.9 if white else 0.7))[:3]
                poly(faces[name], rgb255(lit * kf), gcol)
            # brillo especular en el borde frontal
            a, _ = cam.project([(x0 + 0.05, ytf + 0.005, z0 + 0.03), (x1 - 0.05, ytf + 0.005, z0 + 0.03)], SS)
            spec = (1.0, 0.97, 0.9) if white else (0.45, 0.42, 0.45)
            d.line([tuple(a[0]), tuple(a[1])], fill=rgb255(np.array(spec) * (1 - fog)), width=SS * 2)
    # riel frontal (madera laqueada bajo el teclado) y mejilla cercana
    poly([(-1.2, -0.85, -0.12), (KB_LEN + 1.2, -0.85, -0.12), (KB_LEN + 1.2, -3.2, -0.25), (-1.2, -3.2, -0.25)],
         rgb255(shade(lac, 1.2)))
    poly([(-1.2, -0.85, -0.12), (KB_LEN + 1.2, -0.85, -0.12), (KB_LEN + 1.2, -0.95, -0.35), (-1.2, -0.95, -0.35)],
         rgb255(tuple(0.08 + 0.3 * c for c in bg_mean)))
    poly([(-1.2, 1.1, -0.3), (-0.1, 1.1, -0.3), (-0.1, 1.1, 6.6), (-1.2, 1.1, 6.6)], rgb255(shade(lac, 2.2)))
    poly([(-0.1, 1.1, -0.3), (-0.1, 1.1, 6.6), (-0.1, -0.9, 6.6), (-0.1, -0.9, -0.3)], rgb255(shade(lac, 1.4)))
    # reflejos de las teclas encendidas en la tapa laqueada
    for K in KEYS:
        p = float(press[K['k']])
        if p > 0.05:
            cx = (K['x0'] + K['x1']) / 2
            q, _ = cam.project([(cx, 0.35, 6.52), (cx, 2.2, 6.88)], 0.25)
            dg.line([tuple(q[0]), tuple(q[1])], fill=rgb255(acc * p * 0.5)[:3], width=2)

    img = img.reduce(SS)
    return img, mask, glow


# ---------------------------------------------------------------- particulas de luz

def key_top_center(k):
    K = KEYS[k]
    cx = (K['x0'] + K['x1']) / 2
    return (cx, 0.1, 2.2) if K['white'] else (cx, BLACK_H + 0.05, 4.4)


def draw_motes(layer, cam, t, accent):
    """Particulas que nacen de cada tecla pulsada y flotan hacia el fondo."""
    ev = ANA['events']
    LIFE = 4.0
    i0 = int(np.searchsorted(ev[:, 0], t - LIFE))
    i1 = int(np.searchsorted(ev[:, 0], t))
    acc = np.array(accent)
    focus = ANA['focus_d']
    for i in range(i0, i1):
        t0, k, v = ev[i]
        age = t - t0
        r = rng(i)
        n = 2 + int(v * 4)
        bx, by, bz = key_top_center(int(k))
        for j in range(n):
            a, b, c, s, ph, life = r.random(6)
            life = 2.0 + 2.0 * life
            if age > life:
                continue
            u = age / life
            x = bx + (a - 0.5) * 0.8 + 0.5 * math.sin(age * (1 + b) + ph * 6)
            y = by + 0.2 + age * (0.9 + 1.4 * c) + 0.3 * age * age * 0.2
            z = bz + age * (0.6 + 1.6 * b)
            P, depth = cam.project([(x, y, z)], HW / OW)
            if depth[0] < 1:
                continue
            fade = smoothstep(0, 0.08, u) * (1 - smoothstep(0.55, 1.0, u))
            cc = abs(1 / depth[0] - 1 / focus) * 26
            rad = (0.6 + 1.2 * s) * 9 / depth[0] * 1.8 + cc * 5
            br = v * fade * (0.9 + 0.6 * math.sin(age * 7 + ph * 9) ** 2) / (1 + cc * 3)
            col = acc * 0.7 + np.array([1, 1, 1]) * 0.3
            if cc > 0.3:
                stamp(layer, bokeh_sprite(min(rad, 22), 0.6), P[0, 0], P[0, 1], col * br * 0.35)
            else:
                stamp(layer, glow_sprite(max(0.6, rad * 0.5)), P[0, 0], P[0, 1], col * br * 1.1)


def foreground_dust(layer, t, e):
    """Motas grandes muy cerca de la camara: fuera de foco, refuerzan la profundidad."""
    r = rng(99)
    P = r.random((10, 5))
    for x0, y0, s, sp, ph in P:
        x = (x0 * LW + t * (2 + 6 * sp)) % (LW + 80) - 40
        y = y0 * LH + 18 * math.sin(t * 0.13 + ph * 6)
        br = (0.035 + 0.05 * e) * (0.6 + 0.4 * math.sin(t * 0.4 + ph * 10))
        stamp(layer, bokeh_sprite(14 + 26 * s, 0.4), x, y, np.array([1.0, 0.85, 0.65]) * br)


# ---------------------------------------------------------------- post y cuadro final

def precompute_post():
    def make():
        yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
        d = np.sqrt(((xx - OW / 2) / (OW * 0.62)) ** 2 + ((yy - OH / 2) / (OH * 0.62)) ** 2)
        vig = (1 - 0.55 * np.clip(d - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)
        r = rng(7)
        grains = [r.normal(0, 5.0, (OH // 2, OW // 2)).astype(np.float32) for _ in range(6)]
        grains = [np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None] for g in grains]
        yl, xl = np.mgrid[0:LH, 0:LW].astype(np.float32)
        leak = np.exp(-(((xl - LW * 1.05) / (LW * 0.35)) ** 2 + ((yl + LH * 0.1) / (LH * 0.6)) ** 2))
        return vig, grains, leak[..., None].astype(np.float32)
    return cached('post', make)


def title_layer():
    def make():
        im = Image.new('L', (OW, OH), 0)
        d = ImageDraw.Draw(im)
        f = ImageFont.truetype(FONT, 96)
        txt = 'in the pool'
        w = d.textlength(txt, font=f)
        d.text(((OW - w) / 2, OH * 0.22), txt, font=f, fill=255)
        soft = im.filter(ImageFilter.GaussianBlur(12))
        return np.maximum(np.asarray(im, np.float32), np.asarray(soft, np.float32) * 0.9)[..., None] / 255.0
    return cached('title', make)


def render_frame(f):
    A = ANA
    t = f / FPS
    e, hit = A['energy'][f], A['hit'][f]
    cam, cam_dx = camera_at(t, f)
    bg, cur, k = background(t, f, cam_dx)
    S = get_scene(cur)
    accent = np.array(S['accent'])
    ch = A['changes']
    if k > 0 and t - ch[k] < 1.0:
        accent = np.array(get_scene(int(A['scenes'][k - 1]))['accent']) * (1 - (t - ch[k])) + accent * (t - ch[k])
    bg_mean = tuple(bg.mean((0, 1)))

    focus_x = A['focus_x'][f]
    focus_d = float(cam.depth((focus_x, 0.0, 3.0)))
    A['focus_d'] = focus_d
    piano, mask, glow = render_piano(cam, A['press'][f], accent, focus_d, bg_mean)

    # profundidad de campo del piano: mezcla nitida/desenfocada segun la mascara de CoC
    pb = piano.reduce(4).filter(ImageFilter.GaussianBlur(3)).resize((OW, OH), Image.BILINEAR)
    m = mask.filter(ImageFilter.GaussianBlur(2)).resize((OW, OH), Image.BILINEAR)
    piano = Image.composite(pb, piano, m)

    frame = to_img(bg).resize((OW, OH), Image.BICUBIC).convert('RGBA')
    frame = Image.alpha_composite(frame, piano).convert('RGB')

    # capa aditiva: brillo de teclas + polvo cercano + destellos (480x270), particulas (960x540)
    low = to_arr(glow.filter(ImageFilter.GaussianBlur(5))) * 1.3
    low += to_arr(glow.filter(ImageFilter.GaussianBlur(1.5))) * 0.5
    foreground_dust(low, t, e)
    vig, grains, leak = precompute_post()
    low += leak * np.array([1.0, 0.55, 0.3]) * (0.35 * hit * (0.3 + e) + 0.08)
    if k > 0:
        dt = t - ch[k]
        if 0 <= dt < 0.6:
            low += (1 - dt / 0.6) ** 2 * 0.22 * np.array([1.0, 0.85, 0.7])
    half = to_arr(to_img(low).resize((HW, HH), Image.BILINEAR))
    draw_motes(half, cam, t, accent)
    add = to_img(half).resize((OW, OH), Image.BILINEAR)
    frame = ImageChops.screen(frame, add)

    out = np.asarray(frame, np.float32) * vig
    if t < 9:
        a = smoothstep(1.5, 3.0, t) * (1 - smoothstep(6.5, 8.5, t))
        if a > 0:
            out = out + title_layer() * (255 - out) * 0.85 * a
    out += grains[f % len(grains)]
    fade = smoothstep(0, 2.5, t) * (1 - smoothstep(A['dur'] - 4.0, A['dur'] - 0.3, t))
    out *= fade
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- main

def load_analysis():
    a = analysis.analyze(AUDIO, FPS, N_SCENES)
    P = a['press']
    xs = np.array([(K['x0'] + K['x1']) / 2 for K in KEYS])
    w = P.sum(1)
    fx = np.where(w > 0.05, (P * xs).sum(1) / np.maximum(w, 1e-6), np.nan)
    # el foco sigue a la zona del teclado donde suena la musica, con suavidad
    out = np.zeros(len(P))
    cur = 15.0
    for i, v in enumerate(fx):
        if not np.isnan(v):
            cur += (v - cur) * 0.035
        out[i] = cur
    a['focus_x'] = np.clip(out, 13, 24)
    a['focus_d'] = 14.0
    return a


def worker_init():
    np.seterr(all='ignore')


def main():
    global ANA
    print('Analizando audio...')
    ANA = load_analysis()
    print('  %.1fs, %.0f BPM, %d notas, %d escenas' % (ANA['dur'], ANA['bpm'], len(ANA['events']),
                                                      len(ANA['changes'])))
    args = sys.argv[1:]
    if args and args[0] == '--stills':
        os.makedirs(os.path.join(HERE, 'stills'), exist_ok=True)
        for s in args[1:]:
            n = int(float(s) * FPS)
            Image.fromarray(render_frame(n)).save(os.path.join(HERE, 'stills', 'frame_%06.2f.png' % float(s)))
        return
    total = int(ANA['dur'] * FPS)
    master = os.path.join(HERE, 'master_tmp.mp4')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '%dx%d' % (OW, OH), '-r', str(FPS), '-i', '-', '-i', AUDIO,
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', master]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with mp.get_context('fork').Pool(os.cpu_count(), initializer=worker_init) as pool:
        for n, fr in enumerate(pool.imap(render_frame, range(total), chunksize=4)):
            proc.stdin.write(fr.tobytes())
            if n % (FPS * 10) == 0:
                print('  %5.1fs / %.0fs' % (n / FPS, ANA['dur']), flush=True)
    proc.stdin.close()
    proc.wait()
    compress(master)
    print('Listo:', OUT)


def compress(master):
    """El grano de pelicula dispara el peso: se suaviza y se codifica a 2 pasadas (<100 MB para GitHub)."""
    print('Comprimiendo (2 pasadas)...')
    base = ['ffmpeg', '-loglevel', 'error', '-y', '-i', master, '-vf', 'hqdn3d=3:3:6:6', '-c:v', 'libx264',
            '-preset', 'slow', '-tune', 'film', '-b:v', '2900k', '-passlogfile', os.path.join(HERE, 'x264pass')]
    subprocess.run(base + ['-pass', '1', '-an', '-f', 'null', os.devnull], check=True)
    subprocess.run(base + ['-pass', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
                           '-movflags', '+faststart', OUT], check=True)
    for f in os.listdir(HERE):
        if f.startswith('x264pass'):
            os.remove(os.path.join(HERE, f))
    os.remove(master)


if __name__ == '__main__':
    main()
