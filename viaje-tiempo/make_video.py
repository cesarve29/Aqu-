#!/usr/bin/env python3
"""
VIAJAR EN EL TIEMPO: por que al futuro si y al pasado no
Short vertical 9:16 (1080x1920) a 60 fps, generado 100% por codigo (skia + numpy + ffmpeg).
Voz en off y efectos de sonido: ElevenLabs (carpeta audio/).
Subtitulos sincronizados palabra a palabra con audio/words.json (ElevenLabs Scribe).

Uso:
    python3 make_video.py                 -> viaje_en_el_tiempo_9x16_60fps.mp4
    python3 make_video.py --stills 5 20   -> stills/still_005.0.png ... (para revisar)
"""
import json
import math
import os
import random
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
import skia

W, H, FPS = 1080, 1920, 60
END = 140.0
HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "audio")
FONT_DIR = "/usr/share/fonts/opentype/inter"
OUT = os.path.join(HERE, "viaje_en_el_tiempo_9x16_60fps.mp4")

# ---------------------------------------------------------------- paleta
CYAN = (56, 225, 255)
BLUE = (70, 120, 255)
RED = (255, 59, 92)
ORANGE = (255, 140, 60)
GOLD = (255, 210, 63)
WHITE = (255, 255, 255)
MUTED = (150, 165, 200)
VIOLET = (160, 90, 255)
GREEN = (60, 230, 150)

# ---------------------------------------------------------------- escenas (s)
SCENES = [
    ("hook", 0.0, 13.3),
    ("einstein", 13.3, 29.8),
    ("iss", 29.8, 41.0),
    ("gps", 41.0, 50.2),
    ("ship", 50.2, 66.3),
    ("past", 66.3, 69.9),
    ("paradox", 69.9, 82.6),
    ("wormhole", 82.6, 99.5),
    ("hawking", 99.5, 115.6),
    ("summary", 115.6, 127.3),
    ("ending", 127.3, END),
]
XF = 0.35  # crossfade

CHAPTERS = [
    (0.0, 13.3, "", None),
    (13.3, 66.3, "AL FUTURO", CYAN),
    (66.3, 69.9, "AL PASADO", RED),
    (69.9, 82.6, "01 · PARADOJAS", RED),
    (82.6, 99.5, "02 · LA FÍSICA", RED),
    (99.5, 115.6, "03 · HAWKING", RED),
    (115.6, 127.3, "EN RESUMEN", GOLD),
    (127.3, END, "", None),
]

# ---------------------------------------------------------------- utilidades
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def eout(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ein(t):
    t = clamp(t)
    return t * t * t


def back(t, s=1.7):
    t = clamp(t)
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def fin(t, t0, d=0.45):
    """0->1 a partir de t0."""
    return eout((t - t0) / d)


def fwin(t, t0, t1, d=0.35):
    """ventana: entra en t0, sale en t1."""
    return min(eout((t - t0) / d), eout((t1 - t) / d))


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(int(lerp(a, b, k)) for a, b in zip(c1, c2))


def col(rgb, a=1.0):
    return skia.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(255 * clamp(a)))


_TF = {}


def tf(w):
    if w not in _TF:
        name = {
            "black": "InterDisplay-Black.otf",
            "xbold": "InterDisplay-ExtraBold.otf",
            "bold": "InterDisplay-Bold.otf",
            "semi": "InterDisplay-SemiBold.otf",
            "med": "InterDisplay-Medium.otf",
            "reg": "InterDisplay-Regular.otf",
            "mono": None,
        }[w]
        if name is None:
            _TF[w] = skia.Typeface.MakeFromFile("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
        else:
            _TF[w] = skia.Typeface.MakeFromFile(os.path.join(FONT_DIR, name))
    return _TF[w]


def font(size, w="black"):
    f = skia.Font(tf(w), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def P(color, a=1.0, stroke=None, blur=None, cap=True, shader=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor(col(color, a))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        if cap:
            p.setStrokeCap(skia.Paint.kRound_Cap)
            p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if shader is not None:
        p.setShader(shader)
    return p


def text(c, s, x, y, size, color=WHITE, a=1.0, w="black", align="c", glow=0, outline=0,
         spacing=0.0, ocolor=(0, 0, 0)):
    if a <= 0.003 or not s:
        return 0
    f = font(size, w)
    if spacing:
        # tracking manual
        widths = [f.measureText(ch) for ch in s]
        tw = sum(widths) + spacing * (len(s) - 1)
        x0 = x - tw / 2 if align == "c" else (x - tw if align == "r" else x)
        cx = x0
        for ch, cw in zip(s, widths):
            if glow:
                c.drawString(ch, cx, y, f, P(color, a * 0.8, blur=glow))
            c.drawString(ch, cx, y, f, P(color, a))
            cx += cw + spacing
        return tw
    tw = f.measureText(s)
    x0 = x - tw / 2 if align == "c" else (x - tw if align == "r" else x)
    if outline:
        c.drawString(s, x0, y, f, P(ocolor, a * 0.9, stroke=outline))
    if glow:
        c.drawString(s, x0, y, f, P(color, a * 0.85, blur=glow))
    c.drawString(s, x0, y, f, P(color, a))
    return tw


def tw_of(s, size, w="black"):
    return font(size, w).measureText(s)


def rrect(c, x, y, w, h, r, paint):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r), paint)


def check_icon(c, x, y, s, color, a, k=1.0):
    """palomita dibujada con trazo (k = progreso de dibujo)."""
    path = skia.Path()
    pts = [(x - 0.45 * s, y + 0.02 * s), (x - 0.12 * s, y + 0.33 * s), (x + 0.5 * s, y - 0.35 * s)]
    l1 = math.dist(pts[0], pts[1])
    l2 = math.dist(pts[1], pts[2])
    L = (l1 + l2) * clamp(k)
    path.moveTo(*pts[0])
    if L <= l1:
        q = L / l1
        path.lineTo(lerp(pts[0][0], pts[1][0], q), lerp(pts[0][1], pts[1][1], q))
    else:
        path.lineTo(*pts[1])
        q = (L - l1) / l2
        path.lineTo(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q))
    c.drawPath(path, P(color, a * 0.7, stroke=s * 0.16, blur=s * 0.12))
    c.drawPath(path, P(color, a, stroke=s * 0.14))


def cross_icon(c, x, y, s, color, a, k=1.0):
    k1 = clamp(k * 2)
    k2 = clamp(k * 2 - 1)
    d = s * 0.4
    for kk, (sx, sy, ex, ey) in ((k1, (x - d, y - d, x + d, y + d)), (k2, (x + d, y - d, x - d, y + d))):
        if kk <= 0:
            continue
        sx_, sy_, ex_, ey_ = sx, sy, lerp(sx, ex, kk), lerp(sy, ey, kk)
        c.drawLine(sx_, sy_, ex_, ey_, P(color, a * 0.7, stroke=s * 0.16, blur=s * 0.12))
        c.drawLine(sx_, sy_, ex_, ey_, P(color, a, stroke=s * 0.14))


def person(c, x, y, s, color, a, stroke=None, dash=False):
    """silueta simple (cabeza + torso). y = base de los pies."""
    head_r = s * 0.17
    body = skia.Path()
    bw = s * 0.36
    top = y - s * 0.62
    body.moveTo(x - bw, y)
    body.lineTo(x - bw, top + bw * 0.9)
    body.quadTo(x - bw, top, x, top)
    body.quadTo(x + bw, top, x + bw, top + bw * 0.9)
    body.lineTo(x + bw, y)
    body.close()
    if stroke:
        p = P(color, a, stroke=stroke)
        if dash:
            p.setPathEffect(skia.DashPathEffect.Make([stroke * 2.2, stroke * 1.8], 0))
        c.drawPath(body, p)
        c.drawCircle(x, top - head_r * 1.25, head_r, p)
    else:
        c.drawPath(body, P(color, a))
        c.drawCircle(x, top - head_r * 1.25, head_r, P(color, a))


def draw_clock(c, x, y, r, minute, second, color, a, glow=True, face=True, sec_color=None):
    """minute/second en revoluciones (1.0 = vuelta completa)."""
    if a <= 0:
        return
    if face:
        sh = skia.GradientShader.MakeRadial(skia.Point(x, y - r * 0.3), r * 1.3,
                                            [col((30, 40, 80), a * 0.85), col((8, 10, 25), a * 0.9)])
        c.drawCircle(x, y, r, P(WHITE, 1, shader=sh))
    if glow:
        c.drawCircle(x, y, r, P(color, a * 0.6, stroke=r * 0.05, blur=r * 0.08))
    c.drawCircle(x, y, r, P(color, a, stroke=r * 0.035))
    for i in range(60):
        ang = i / 60 * 2 * math.pi
        major = i % 5 == 0
        r0 = r * (0.80 if major else 0.87)
        r1 = r * 0.93
        c.drawLine(x + math.sin(ang) * r0, y - math.cos(ang) * r0, x + math.sin(ang) * r1,
                   y - math.cos(ang) * r1,
                   P(WHITE if major else MUTED, a * (0.95 if major else 0.45),
                     stroke=r * (0.025 if major else 0.01)))
    # aguja larga
    ang = minute * 2 * math.pi
    c.drawLine(x, y, x + math.sin(ang) * r * 0.62, y - math.cos(ang) * r * 0.62,
               P(WHITE, a, stroke=r * 0.045))
    ang = second * 2 * math.pi
    sc = sec_color or color
    c.drawLine(x - math.sin(ang) * r * 0.15, y + math.cos(ang) * r * 0.15,
               x + math.sin(ang) * r * 0.82, y - math.cos(ang) * r * 0.82,
               P(sc, a * 0.7, stroke=r * 0.03, blur=r * 0.02))
    c.drawLine(x - math.sin(ang) * r * 0.15, y + math.cos(ang) * r * 0.15,
               x + math.sin(ang) * r * 0.82, y - math.cos(ang) * r * 0.82,
               P(sc, a, stroke=r * 0.018))
    c.drawCircle(x, y, r * 0.05, P(sc, a))
    c.drawCircle(x, y, r * 0.022, P(WHITE, a))


def draw_earth(c, x, y, r, a, t, night=0.0):
    if a <= 0:
        return
    # atmosfera
    c.drawCircle(x, y, r * 1.05, P(CYAN, a * 0.45, blur=r * 0.08))
    sh = skia.GradientShader.MakeRadial(skia.Point(x - r * 0.35, y - r * 0.4), r * 1.5,
                                        [col((90, 170, 255), a), col((20, 80, 190), a),
                                         col((6, 20, 70), a)], [0.0, 0.45, 1.0])
    c.drawCircle(x, y, r, P(WHITE, 1, shader=sh))
    # continentes estilizados (manchas) recortados al circulo
    c.save()
    clip = skia.Path()
    clip.addCircle(x, y, r)
    c.clipPath(clip, skia.ClipOp.kIntersect, True)
    rnd = random.Random(7)
    for i in range(14):
        lon = rnd.random() * 2 * math.pi
        lat = (rnd.random() - 0.5) * 1.8
        size = r * (0.12 + rnd.random() * 0.22)
        ang = lon + t * 0.08
        px = x + math.sin(ang) * r * math.cos(lat * 0.8)
        py = y + math.sin(lat * 0.8) * r
        vis = math.cos(ang)
        if vis <= 0:
            continue
        c.drawOval(skia.Rect.MakeXYWH(px - size * vis, py - size * 0.6, 2 * size * vis, size * 1.2),
                   P((60, 180, 120), a * 0.55 * vis, blur=size * 0.15))
    # rejilla de latitudes
    for k in range(-3, 4):
        yy = y + k * r / 4
        hw = math.sqrt(max(r * r - (yy - y) ** 2, 0))
        c.drawOval(skia.Rect.MakeLTRB(x - hw, yy - hw * 0.06, x + hw, yy + hw * 0.06),
                   P(WHITE, a * 0.08, stroke=1.5))
    # terminador (sombra)
    sh2 = skia.GradientShader.MakeLinear([skia.Point(x - r * 0.2, y), skia.Point(x + r, y)],
                                         [col((0, 0, 0), 0), col((0, 0, 10), a * (0.75 + night * 0.2))])
    c.drawCircle(x, y, r, P(WHITE, 1, shader=sh2))
    c.restore()
    c.drawCircle(x, y, r, P((150, 220, 255), a * 0.6, stroke=3))


def draw_iss(c, x, y, s, ang, a):
    c.save()
    c.translate(x, y)
    c.rotate(math.degrees(ang))
    c.drawCircle(0, 0, s * 1.4, P(CYAN, a * 0.35, blur=s * 0.8))
    rrect(c, -s * 0.18, -s * 0.5, s * 0.36, s, s * 0.08, P(WHITE, a))
    for sx in (-1, 1):
        for oy in (-0.32, 0.18):
            c.drawRect(skia.Rect.MakeXYWH(sx * s * 0.25 if sx > 0 else -s * 1.25, oy * s, s * 1.0,
                                          s * 0.14), P((90, 150, 255), a))
    c.drawLine(-s * 1.25, 0, s * 1.25, 0, P(WHITE, a, stroke=s * 0.06))
    c.restore()


def draw_sat(c, x, y, s, a, color=GOLD):
    c.drawCircle(x, y, s * 1.6, P(color, a * 0.3, blur=s))
    rrect(c, x - s * 0.3, y - s * 0.3, s * 0.6, s * 0.6, s * 0.1, P(WHITE, a))
    c.drawRect(skia.Rect.MakeXYWH(x - s * 1.3, y - s * 0.18, s * 0.9, s * 0.36), P(BLUE, a))
    c.drawRect(skia.Rect.MakeXYWH(x + s * 0.4, y - s * 0.18, s * 0.9, s * 0.36), P(BLUE, a))


def draw_ship(c, x, y, s, a, flame):
    c.save()
    c.translate(x, y)
    # llama
    fl = s * (0.9 + 0.25 * flame)
    sh = skia.GradientShader.MakeLinear([skia.Point(0, s * 0.55), skia.Point(0, s * 0.55 + fl)],
                                        [col(WHITE, a), col(CYAN, a * 0.8), col(BLUE, 0)],
                                        [0, 0.35, 1])
    flame_p = skia.Path()
    flame_p.moveTo(-s * 0.2, s * 0.5)
    flame_p.quadTo(0, s * 0.55 + fl * 1.1, s * 0.2, s * 0.5)
    flame_p.close()
    c.drawPath(flame_p, P(WHITE, 1, shader=sh, blur=s * 0.04))
    c.drawCircle(0, s * 0.6, s * 0.35, P(CYAN, a * 0.5, blur=s * 0.3))
    # casco
    body = skia.Path()
    body.moveTo(0, -s * 1.0)
    body.cubicTo(s * 0.22, -s * 0.7, s * 0.28, -s * 0.1, s * 0.24, s * 0.55)
    body.lineTo(-s * 0.24, s * 0.55)
    body.cubicTo(-s * 0.28, -s * 0.1, -s * 0.22, -s * 0.7, 0, -s * 1.0)
    body.close()
    sh2 = skia.GradientShader.MakeLinear([skia.Point(-s * 0.3, 0), skia.Point(s * 0.3, 0)],
                                         [col((120, 135, 170), a), col((240, 245, 255), a),
                                          col((90, 100, 130), a)], [0, 0.45, 1])
    # alas
    wing = skia.Path()
    wing.moveTo(-s * 0.22, s * 0.0)
    wing.lineTo(-s * 0.62, s * 0.55)
    wing.lineTo(-s * 0.2, s * 0.45)
    wing.close()
    wing2 = skia.Path()
    wing2.moveTo(s * 0.22, s * 0.0)
    wing2.lineTo(s * 0.62, s * 0.55)
    wing2.lineTo(s * 0.2, s * 0.45)
    wing2.close()
    c.drawPath(wing, P((70, 90, 150), a))
    c.drawPath(wing2, P((70, 90, 150), a))
    c.drawPath(body, P(WHITE, 1, shader=sh2))
    c.drawOval(skia.Rect.MakeXYWH(-s * 0.08, -s * 0.62, s * 0.16, s * 0.28), P(CYAN, a))
    c.drawOval(skia.Rect.MakeXYWH(-s * 0.08, -s * 0.62, s * 0.16, s * 0.28), P(CYAN, a * 0.8, blur=s * 0.06))
    c.restore()


# ---------------------------------------------------------------- fondo
rng = np.random.default_rng(11)
NST = 420
STX = rng.random(NST) * W
STY = rng.random(NST) * H
STZ = rng.random(NST) ** 2 * 0.9 + 0.1
STP = rng.random(NST) * 6.28
STC = rng.random(NST)


def past_amount(t):
    """0 = futuro (cian), 1 = pasado (rojo)."""
    return clamp((t - 66.2) / 0.6) * (1 - clamp((t - 115.4) / 1.2)) + 0.0


def warp_amount(t):
    return clamp((t - 50.3) / 2.4) * (1 - clamp((t - 65.8) / 0.6)) * (0.55 + 0.45 * clamp((t - 52.9) / 1.0))


def background(c, t):
    pa = past_amount(t)
    top = mix((6, 8, 22), (18, 4, 12), pa)
    bot = mix((3, 4, 12), (8, 2, 6), pa)
    sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)],
                                        [col(top), col(mix(top, (14, 22, 60), 0.6 * (1 - pa))), col(bot)],
                                        [0, 0.5, 1])
    c.drawPaint(P(WHITE, 1, shader=sh))
    # nebulosas
    neb = [((300, 500), 600, mix(BLUE, RED, pa), 0.20), ((850, 1250), 700, mix(VIOLET, ORANGE, pa), 0.13),
           ((540, 1700), 520, mix(CYAN, RED, pa), 0.10)]
    for i, ((nx, ny), nr, nc, na) in enumerate(neb):
        ox = math.sin(t * 0.07 + i * 2) * 60
        oy = math.cos(t * 0.05 + i) * 50
        g = skia.GradientShader.MakeRadial(skia.Point(nx + ox, ny + oy), nr, [col(nc, na), col(nc, 0)])
        c.drawCircle(nx + ox, ny + oy, nr, P(WHITE, 1, shader=g))
    # estrellas
    wa = warp_amount(t)
    direction = -1.0 if 66.3 <= t < 69.9 else 1.0  # en "al pasado" las estrellas van hacia atras
    speed = 14 + 2600 * wa ** 2
    if 66.3 <= t < 69.9:
        speed = 14 + 900 * fwin(t, 66.3, 69.9, 0.5)
    for i in range(NST):
        z = STZ[i]
        if wa > 0.01:
            # estrellas cayendo verticalmente (la nave sube)
            y = (STY[i] + (t - 50.3) * speed * z * 0.35 + 9e3) % (H + 400) - 200
            x = STX[i]
            L = max(2.0, wa ** 1.5 * 260 * z)
            ccol = mix(WHITE, CYAN, STC[i] * 0.7)
            c.drawLine(x, y - L, x, y, P(ccol, (0.35 + 0.65 * z), stroke=1.2 + 2.2 * z))
        else:
            # deriva lenta
            y = (STY[i] + direction * t * 14 * z + 9e3) % H
            x = (STX[i] - t * 4 * z + 9e3) % W
            tw = 0.55 + 0.45 * math.sin(t * (1.5 + STC[i] * 2) + STP[i])
            r = 0.8 + 2.4 * z
            ccol = mix(WHITE, mix(CYAN, RED, pa), STC[i] * 0.5)
            if 66.3 <= t < 69.9:
                L = speed * z * 0.06
                c.drawLine(x, y, x, y + L, P(ccol, 0.8 * z + 0.2, stroke=r))
            else:
                c.drawCircle(x, y, r, P(ccol, (0.25 + 0.75 * z) * tw))


def vignette(c):
    g = skia.GradientShader.MakeRadial(skia.Point(W / 2, H * 0.46), H * 0.75,
                                       [col((0, 0, 0), 0), col((0, 0, 0), 0), col((0, 0, 0), 0.75)],
                                       [0, 0.55, 1])
    c.drawPaint(P(WHITE, 1, shader=g))


# ---------------------------------------------------------------- escenas
def sc_hook(c, t):
    # titulo
    k = fin(t, 0.05, 0.7)
    text(c, "VIAJAR EN EL", W / 2, 330 - 30 * (1 - k), 64, MUTED, k, "bold", spacing=10)
    text(c, "TIEMPO", W / 2, 470 - 30 * (1 - k), 170, WHITE, k, "black", glow=18)
    # reloj central
    cx, cy, r = W / 2, 930, 270
    rev = 0.0
    if t > 9.66:
        rev = -ein((t - 9.66) / 2.0) * 3.0  # gira hacia atras
    sec = t / 6.0 + rev
    pa = clamp((t - 9.7) / 0.8)
    ccol = mix(CYAN, RED, pa)
    kk = back((t - 0.3) / 0.8)
    draw_clock(c, cx, cy, r * kk, t / 60 + rev / 4, sec, ccol, clamp(kk), sec_color=mix(GOLD, RED, pa))
    # flecha futuro
    if 1.6 < t:
        kf = fin(t, 1.7, 0.6) * (1 - 0.65 * clamp((t - 9.6) / 0.6))
        y = 1290
        x0 = W / 2 + 40
        x1 = x0 + 330 * eout((t - 1.7) / 0.7)
        c.drawLine(x0, y, x1, y, P(CYAN, kf, stroke=10))
        c.drawLine(x0, y, x1, y, P(CYAN, kf * 0.6, stroke=14, blur=8))
        path = skia.Path()
        path.moveTo(x1 + 26, y)
        path.lineTo(x1 - 8, y - 26)
        path.lineTo(x1 - 8, y + 26)
        path.close()
        c.drawPath(path, P(CYAN, kf))
        text(c, "FUTURO", x0 + 165, y - 40, 54, CYAN, kf, "black", glow=10)
        if t > 4.3:
            kc = fin(t, 4.32, 0.5) * (1 - 0.65 * clamp((t - 9.6) / 0.6))
            check_icon(c, x0 + 165, y + 92, 70, GREEN, kc, eout((t - 4.32) / 0.5))
            text(c, "REAL · MEDIDO", x0 + 165, y + 185, 34, GREEN, kc, "bold", spacing=3)
    if t > 9.7:
        kp = fin(t, 10.5, 0.6)
        y = 1290
        x0 = W / 2 - 40
        x1 = x0 - 330 * eout((t - 10.5) / 0.7)
        c.drawLine(x0, y, x1, y, P(RED, kp, stroke=10))
        c.drawLine(x0, y, x1, y, P(RED, kp * 0.6, stroke=14, blur=8))
        path = skia.Path()
        path.moveTo(x1 - 26, y)
        path.lineTo(x1 + 8, y - 26)
        path.lineTo(x1 + 8, y + 26)
        path.close()
        c.drawPath(path, P(RED, kp))
        text(c, "PASADO", x0 - 165, y - 40, 54, RED, kp, "black", glow=10)
        kq = back((t - 11.75) / 0.5)
        if t > 11.75:
            text(c, "?", x0 - 165, y + 150, int(130 * clamp(kq, 0, 1.3)), RED, clamp(kq), "black", glow=14)


def sc_einstein(c, t):
    # 1905
    k = fin(t, 13.6, 0.5)
    up = eout((t - 17.9) / 0.8)
    y = lerp(760, 380, up)
    size = lerp(300, 150, up)
    yr = int(lerp(1800, 1905, eout((t - 13.6) / 1.4)))
    text(c, str(yr), W / 2, y, int(size), GOLD, k, "black", glow=22)
    ka = fin(t, 15.28, 0.5) * (1 - up)
    text(c, "ALBERT EINSTEIN", W / 2, y + 120, 52, WHITE, ka, "xbold", spacing=6)
    text(c, "Relatividad especial", W / 2, y + 185, 42, MUTED, fin(t, 16.56, 0.5) * (1 - up), "med")
    # dos relojes
    if t > 18.0:
        kc = fin(t, 18.1, 0.6)
        lx, rx, cy, r = 290, 790, 830, 185
        # quieto
        draw_clock(c, lx, cy, r, (t - 18) / 30, (t - 18) / 2.5, CYAN, kc, sec_color=GOLD)
        text(c, "QUIETO", lx, cy + r + 80, 42, WHITE, kc, "xbold", spacing=4)
        # en movimiento: aguja mas lenta + lineas de velocidad
        km = fin(t, 21.1, 0.5)
        slow = lerp(1.0, 0.45, clamp((t - 22.9) / 1.0))
        ph = (t - 18) / 2.5 * slow if t < 22.9 else (22.9 - 18) / 2.5 + (t - 22.9) / 2.5 * 0.45
        jitter = math.sin(t * 40) * 3 * km
        for i in range(6):
            yy = cy - r * 0.8 + i * r * 0.32
            L = 90 + 60 * math.sin(t * 9 + i * 1.7)
            xx = rx - r - 30 - ((t * 900 + i * 137) % 160)
            c.drawLine(xx - L, yy, xx, yy, P(CYAN, km * 0.55, stroke=5))
        draw_clock(c, rx + jitter, cy, r, (t - 18) / 30 * slow, ph, mix(CYAN, ORANGE, km), kc, sec_color=ORANGE)
        text(c, "EN MOVIMIENTO", rx, cy + r + 80, 42, ORANGE if km > 0.5 else WHITE, kc, "xbold", spacing=4)
        kl = fin(t, 22.96, 0.4)
        text(c, "más lento", rx, cy + r + 140, 38, ORANGE, kl, "semi")
        text(c, "normal", lx, cy + r + 140, 38, MUTED, kl, "semi")
    # dilatacion temporal
    if t > 27.3:
        kd = back((t - 27.5) / 0.6)
        a = clamp(kd)
        y = 1260
        bw = 860
        rrect(c, W / 2 - bw / 2, y - 80, bw, 150, 30, P(GOLD, a * 0.14))
        rrect(c, W / 2 - bw / 2, y - 80, bw, 150, 30, P(GOLD, a * 0.9, stroke=4))
        text(c, "DILATACIÓN TEMPORAL", W / 2, y + 18, int(66 * clamp(kd, 0, 1.15)), GOLD, a, "black", glow=12)
        text(c, "Δt' = γ · Δt", W / 2, y + 150, 46, WHITE, fin(t, 28.4, 0.5) * 0.9, "semi")


def sc_iss(c, t):
    text(c, "NO ES SOLO TEORÍA", W / 2, 330, 56, WHITE, fin(t, 30.0, 0.5), "black", spacing=4)
    ex, ey, er = W / 2, 1020, 300
    ke = fin(t, 29.9, 0.8)
    draw_earth(c, ex, ey + 60 * (1 - ke), er, ke, t)
    # orbita ISS
    ko = fin(t, 31.6, 0.6)
    orx, ory = 430, 120
    tilt = -0.25
    c.save()
    c.translate(ex, ey)
    c.rotate(math.degrees(tilt))
    p = P(CYAN, ko * 0.5, stroke=3)
    p.setPathEffect(skia.DashPathEffect.Make([14, 12], -t * 30))
    c.drawOval(skia.Rect.MakeLTRB(-orx, -ory, orx, ory), p)
    ang = t * 0.9
    ix, iy = math.cos(ang) * orx, math.sin(ang) * ory
    behind = math.sin(ang) < 0
    c.restore()
    gx = ex + ix * math.cos(tilt) - iy * math.sin(tilt)
    gy = ey + ix * math.sin(tilt) + iy * math.cos(tilt)
    if behind:  # tapada por la Tierra
        if math.hypot(gx - ex, gy - ey) < er:
            ko *= 0.0
    draw_iss(c, gx, gy, 34, ang * 0.3, ko)
    if ko > 0:
        text(c, "ISS", gx, gy - 60, 34, CYAN, ko, "xbold", spacing=3)
    # dato
    if t > 33.0:
        kb = fin(t, 33.0, 0.5)
        text(c, "6 MESES EN ÓRBITA", W / 2, 520, 44, CYAN, kb, "xbold", spacing=3)
    if t > 36.6:
        kd = back((t - 36.72) / 0.6)
        a = clamp(kd)
        y = 1490 - 40
        rrect(c, W / 2 - 400, y - 95, 800, 170, 34, P((10, 20, 45), a * 0.85))
        rrect(c, W / 2 - 400, y - 95, 800, 170, 34, P(CYAN, a, stroke=4))
        val = 0.005 * eout((t - 36.72) / 1.2)
        text(c, f"≈ {val:.3f} s".replace(".", ","), W / 2, y + 22, int(84 * clamp(kd, 0, 1.12)), WHITE, a, "black",
             glow=10)
        text(c, "MÁS JÓVENES", W / 2, y + 125, 38, GOLD, fin(t, 38.0, 0.4), "black", spacing=6)


def sc_gps(c, t):
    ex, ey, er = W / 2, 900, 230
    text(c, "SATÉLITES GPS", W / 2, 330, 64, WHITE, fin(t, 41.2, 0.5), "black", spacing=4)
    draw_earth(c, ex, ey, er, fin(t, 41.0, 0.5), t)
    # satelites en 2 orbitas
    ks = fin(t, 41.3, 0.6)
    for j, (rx, ry, tl, sp, n) in enumerate(((410, 200, 0.5, 0.55, 3), (430, 170, -0.6, -0.45, 3))):
        c.save()
        c.translate(ex, ey)
        c.rotate(math.degrees(tl))
        p = P(GOLD, ks * 0.35, stroke=2.5)
        p.setPathEffect(skia.DashPathEffect.Make([10, 12], t * 20))
        c.drawOval(skia.Rect.MakeLTRB(-rx, -ry, rx, ry), p)
        c.restore()
        for i in range(n):
            ang = t * sp + i * 2 * math.pi / n + j
            ix, iy = math.cos(ang) * rx, math.sin(ang) * ry
            gx = ex + ix * math.cos(tl) - iy * math.sin(tl)
            gy = ey + ix * math.sin(tl) + iy * math.cos(tl)
            if math.sin(ang) < 0 and math.hypot(gx - ex, gy - ey) < er:
                continue
            draw_sat(c, gx, gy, 20, ks)
            # pulso de senal
            ph = (t * 1.2 + i * 0.33 + j * 0.5) % 1.0
            c.drawCircle(gx, gy, 20 + ph * 60, P(GOLD, ks * (1 - ph) * 0.6, stroke=3))
    # correccion de reloj
    if t > 43.3:
        kc = back((t - 43.44) / 0.6)
        a = clamp(kc) * (1 - fin(t, 45.5, 0.3))
        y = 1300
        rrect(c, W / 2 - 390, y - 85, 780, 150, 30, P((30, 24, 8), a * 0.85))
        rrect(c, W / 2 - 390, y - 85, 780, 150, 30, P(GOLD, a, stroke=4))
        text(c, "+38 μs / día", W / 2, y + 22, int(76 * clamp(kc, 0, 1.12)), GOLD, a, "black", glow=10)
        text(c, "corrección diaria de sus relojes", W / 2, y + 125, 36, MUTED, fin(t, 44.0, 0.5) * (1 - fin(t, 45.5, 0.3)), "med")
    # error de posicion
    if t > 45.6:
        ke = fin(t, 45.7, 0.4)
        # dimmer de la escena anterior
        c.drawRect(skia.Rect.MakeXYWH(0, 1200, W, 300), P((4, 5, 14), ke * 0.92))
        km = 10.0 * eout((t - 47.3) / 2.2)
        y = 1300
        rrect(c, W / 2 - 400, y - 95, 800, 170, 34, P((40, 8, 16), ke * 0.85))
        rrect(c, W / 2 - 400, y - 95, 800, 170, 34, P(RED, ke, stroke=4))
        text(c, f"ERROR: {km:4.1f} km/día".replace(".", ","), W / 2, y + 26, 70, RED, ke, "black", glow=10)
        text(c, "sin corrección", W / 2, y + 128, 36, MUTED, ke, "med")
        # marcador de posicion que se desplaza sobre la Tierra
        mx = ex - 40 + km * 14
        my = ey - 60 + km * 6
        c.drawCircle(ex - 40, ey - 60, 14, P(GREEN, ke, stroke=4))
        pin = skia.Path()
        pin.moveTo(mx, my)
        pin.lineTo(mx - 22, my - 40)
        pin.arcTo(skia.Rect.MakeXYWH(mx - 25, my - 78, 50, 50), 150, 240, False)
        pin.close()
        c.drawPath(pin, P(RED, ke))
        c.drawCircle(mx, my - 52, 9, P(WHITE, ke))
        c.drawLine(ex - 40, ey - 60, mx, my - 10, P(RED, ke * 0.8, stroke=3))


def sc_ship(c, t):
    wa = warp_amount(t)
    sx = W / 2 + math.sin(t * 3.1) * 6 * wa
    sy = 960 + math.sin(t * 2.3) * 10 + 80 * (1 - fin(t, 50.3, 1.0))
    s = 230
    draw_ship(c, sx, sy, s, fin(t, 50.4, 0.6), wa + 0.15 * math.sin(t * 30))
    text(c, "CASI A LA VELOCIDAD", W / 2, 300, 50, WHITE, fin(t, 52.4, 0.5) * (1 - fin(t, 54.4, 0.4)),
         "black", spacing=3)
    text(c, "DE LA LUZ", W / 2, 370, 50, CYAN, fin(t, 53.4, 0.5) * (1 - fin(t, 54.4, 0.4)), "black", spacing=3)
    # velocimetro
    kv = fin(t, 52.9, 0.5)
    v = 0.9995 * eout((t - 52.9) / 1.6)
    if kv > 0:
        y = 470
        text(c, f"v = {v:.4f} c".replace(".", ","), W / 2, y, 52, CYAN, kv, "xbold", glow=8)
        bw = 640
        rrect(c, W / 2 - bw / 2, y + 30, bw, 14, 7, P(WHITE, kv * 0.15))
        rrect(c, W / 2 - bw / 2, y + 30, bw * v, 14, 7, P(CYAN, kv))
    # contadores
    if t > 54.4:
        k1 = fin(t, 54.56, 0.5)
        k2 = fin(t, 56.4, 0.5)
        yrs_ship = eout((t - 54.56) / 1.6)
        yrs_earth = 31.6 * clamp((t - 56.6) / 2.4) ** 0.8
        y = 1290
        for i, (lab, val, colr, kk) in enumerate((("NAVE", f"{yrs_ship:.1f} año", CYAN, k1),
                                                    ("TIERRA", f"{yrs_earth:.1f} años", GOLD, k2))):
            x = 280 + i * 520
            rrect(c, x - 230, y - 110, 460, 210, 30, P((8, 14, 34), kk * 0.85))
            rrect(c, x - 230, y - 110, 460, 210, 30, P(colr, kk, stroke=4))
            text(c, lab, x, y - 45, 38, colr, kk, "xbold", spacing=6)
            text(c, val.replace(".", ","), x, y + 50, 70, WHITE, kk, "black", glow=6)
    if t > 60.0:
        kf = back((t - 60.08) / 0.6)
        a = clamp(kf) * (1 - fin(t, 65.9, 0.3))
        text(c, "→ VIAJE AL FUTURO", W / 2, 1475, int(72 * clamp(kf, 0, 1.12)), CYAN, a, "black", glow=16)
    if t > 62.4:
        kt = fin(t, 62.5, 0.5)
        text(c, "solo nos falta la tecnología", W / 2, 1535, 40, MUTED, kt, "med")


def glitch_text(c, s, x, y, size, color, a, t, amt):
    if amt > 0:
        ox = math.sin(t * 91) * 14 * amt
        text(c, s, x - ox, y, size, (255, 0, 60), a * 0.7, "black")
        text(c, s, x + ox, y + 2, size, (0, 220, 255), a * 0.7, "black")
    text(c, s, x, y, size, color, a, "black", glow=18)


def sc_past(c, t):
    # reloj girando hacia atras grande
    k = fin(t, 66.4, 0.5)
    rev = -(t - 66.3) * 1.6
    draw_clock(c, W / 2, 1050, 300, rev / 6, rev, RED, k * 0.9, sec_color=RED)
    kk = back((t - 66.7) / 0.5)
    amt = max(0.0, 1 - (t - 66.7) / 0.8)
    glitch_text(c, "¿AL PASADO?", W / 2, 520, int(118 * clamp(kk, 0, 1.15)), WHITE, clamp(kk), t, amt)
    text(c, "aquí todo se complica", W / 2, 620, 46, RED, fin(t, 68.1, 0.5), "semi")


def sc_paradox(c, t):
    text(c, "PARADOJAS", W / 2, 360, 92, WHITE, fin(t, 70.08, 0.5), "black", glow=10, spacing=4)
    # linea temporal
    y = 900
    x0, x1 = 150, 930
    kl = fin(t, 70.2, 0.8)
    if kl > 0:
        c.drawLine(x0, y, lerp(x0, x1, kl), y, P(MUTED, 0.7 * kl, stroke=6))
        for xx, lab in ((x0 + 70, "PASADO"), (x1 - 70, "HOY")):
            c.drawCircle(xx, y, 12, P(WHITE, kl))
            text(c, lab, xx, y + 70, 34, MUTED, kl, "xbold", spacing=4)
    # viaje de vuelta (arco)
    phase1 = 1 - fin(t, 77.2, 0.4)
    if t > 72.2:
        kv = eout((t - 72.4) / 1.3)
        cx = (x0 + x1) / 2
        rx = (x1 - x0 - 140) / 2
        path = skia.Path()
        oval = skia.Rect.MakeLTRB(cx - rx, y - 280, cx + rx, y + 280)
        path.arcTo(oval, 0, -180 * kv, True)
        c.drawPath(path, P(RED, phase1 * 0.6, stroke=10, blur=8))
        c.drawPath(path, P(RED, phase1, stroke=6))
        ang = math.radians(-180 * kv)
        tx, ty = cx + rx * math.cos(ang), y + 280 * math.sin(ang)
        # viajero
        flick = 1.0
        if t > 75.6:
            flick = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(t * 38)) * (1 - clamp((t - 75.6) / 1.2))
        person(c, tx, ty - 20, 110, CYAN, phase1 * flick)
        text(c, "TÚ", tx, ty - 165, 36, CYAN, phase1 * flick, "black")
    # nacimiento
    if t > 73.3:
        kb = fin(t, 73.4, 0.4) * phase1
        bx, by = x0 + 70, y - 60
        rrect(c, bx - 120, by - 300, 240, 210, 26, P((40, 10, 20), kb * 0.8))
        rrect(c, bx - 120, by - 300, 240, 210, 26, P(RED, kb, stroke=3))
        c.drawCircle(bx, by - 220, 42, P(GOLD, kb))  # bebe estilizado
        rrect(c, bx - 55, by - 172, 110, 60, 28, P(GOLD, kb))
        text(c, "tu nacimiento", bx + 0, by - 40, 30, MUTED, kb, "semi", align="c")
        if t > 74.3:
            cross_icon(c, bx, by - 195, 190, RED, kb, eout((t - 74.32) / 0.5))
    if t > 75.5:
        kq = back((t - 75.63) / 0.5)
        a = clamp(kq) * phase1
        text(c, "¿QUIÉN HIZO", W / 2, 1270, int(84 * clamp(kq, 0, 1.12)), WHITE, a, "black", glow=12)
        text(c, "EL VIAJE?", W / 2, 1370, int(84 * clamp(kq, 0, 1.12)), RED, a, "black", glow=12)
    # causa / efecto
    if t > 77.2:
        ka = fin(t, 77.44, 0.5) * (1 - fin(t, 82.3, 0.3))
        swap = ease((t - 78.6) / 1.2)
        y2 = 1060
        xa = lerp(270, 810, swap)
        xb = lerp(810, 270, swap)
        bad = clamp((t - 79.3) / 0.4)
        for x, lab, colr in ((xa, "CAUSA", CYAN), (xb, "EFECTO", GOLD)):
            yy = y2 + math.sin(swap * math.pi) * (-90 if lab == "CAUSA" else 90)
            rrect(c, x - 200, yy - 75, 400, 150, 30, P((10, 14, 30), ka * 0.9))
            rrect(c, x - 200, yy - 75, 400, 150, 30, P(colr, ka, stroke=4))
            text(c, lab, x, yy + 22, 58, colr, ka, "black")
        ac = mix(WHITE, RED, bad)
        ay = y2 + 200
        c.drawLine(330, ay, 750, ay, P(ac, ka, stroke=8))
        hx = 770 if swap < 0.5 else 310
        d = 1 if swap < 0.5 else -1
        path = skia.Path()
        path.moveTo(hx, ay)
        path.lineTo(hx - d * 34, ay - 26)
        path.lineTo(hx - d * 34, ay + 26)
        path.close()
        c.drawPath(path, P(ac, ka))
        text(c, "tiempo →", W / 2, ay + 70, 32, MUTED, ka, "med")
        if t > 80.2:
            kr = back((t - 81.5) / 0.4)
            # grietas
            if t > 81.4:
                rnd = random.Random(3)
                kc = eout((t - 81.5) / 0.35) * (1 - fin(t, 82.3, 0.3))
                for i in range(9):
                    pth = skia.Path()
                    x, yv = W / 2, 1450
                    pth.moveTo(x, yv)
                    ang = i / 9 * 2 * math.pi + rnd.random() * 0.4
                    L = (180 + rnd.random() * 280) * kc
                    for j in range(5):
                        ang += (rnd.random() - 0.5) * 0.9
                        x += math.cos(ang) * L / 5
                        yv += math.sin(ang) * L / 5
                        pth.lineTo(x, yv)
                    c.drawPath(pth, P(RED, kc * 0.5, stroke=6, blur=5))
                    c.drawPath(pth, P(WHITE, kc, stroke=2.5))
            text(c, "LÓGICA ROTA", W / 2, 1480, int(92 * clamp(kr, 0, 1.15)), RED,
                 clamp(kr) * (1 - fin(t, 82.3, 0.3)), "black", glow=16)


def sc_wormhole(c, t):
    text(c, "LA FÍSICA", W / 2, 360, 92, WHITE, fin(t, 82.9, 0.5), "black", glow=10, spacing=4)
    k = fin(t, 84.9, 1.0)
    cx, cy = W / 2, 930
    rot = t * 0.6
    # embudo doble: perfil r(y) = r0*cosh(y/a)
    N = 26
    for side in (-1, 1):
        for i in range(N):
            u = i / (N - 1)
            yy = side * (u * 380)
            r = 60 * math.cosh(abs(yy) / 120)
            r = min(r, 480)
            ph = (u + t * 0.25) % 1.0
            colr = mix(VIOLET, CYAN, u) if side < 0 else mix(VIOLET, RED, u)
            a = k * (0.25 + 0.6 * (1 - u)) * (0.6 + 0.4 * math.sin(ph * 6.28))
            c.drawOval(skia.Rect.MakeLTRB(cx - r, cy + yy - r * 0.18, cx + r, cy + yy + r * 0.18),
                       P(colr, a, stroke=2.4))
        # meridianos
        for m in range(14):
            ang = m / 14 * 2 * math.pi + rot
            pth = skia.Path()
            first = True
            for i in range(N):
                u = i / (N - 1)
                yy = side * (u * 380)
                r = min(60 * math.cosh(abs(yy) / 120), 480)
                x = cx + math.cos(ang) * r
                y = cy + yy + math.sin(ang) * r * 0.18
                if first:
                    pth.moveTo(x, y)
                    first = False
                else:
                    pth.lineTo(x, y)
            front = math.sin(ang) > 0
            c.drawPath(pth, P(VIOLET if not front else (200, 160, 255), k * (0.55 if front else 0.2), stroke=2))
    c.drawCircle(cx, cy, 70, P((210, 170, 255), k * 0.7, blur=40))
    c.drawCircle(cx, cy, 26, P(WHITE, k * 0.9, blur=10))
    # partícula que atraviesa
    if t > 89.5:
        u = ((t - 89.5) / 2.0) % 1.0
        yy = lerp(-380, 380, u)
        r = min(60 * math.cosh(abs(yy) / 120), 480) * 0.0
        c.drawCircle(cx + r, cy + yy, 14, P(GOLD, k * fwin(t, 89.5, 92.0), blur=6))
        c.drawCircle(cx + r, cy + yy, 8, P(WHITE, k * fwin(t, 89.5, 92.0)))
    text(c, "AGUJERO DE GUSANO", W / 2, 1420, 56, mix(VIOLET, WHITE, 0.4), fin(t, 88.0, 0.5) * (1 - fin(t, 91.8, 0.3)),
         "black", spacing=3)
    text(c, "solución teórica de la relatividad general", W / 2, 1485, 34, MUTED,
         fin(t, 88.3, 0.5) * (1 - fin(t, 91.8, 0.3)), "med")
    # requisitos
    if t > 92.7:
        y = 1330
        for i, (lab, t0) in enumerate((("MATERIA EXÓTICA", 92.88), ("ENERGÍA NEGATIVA", 94.08))):
            kk = back((t - t0) / 0.5)
            a = clamp(kk)
            yy = y + i * 150
            bw = 700
            rrect(c, W / 2 - bw / 2, yy - 62, bw, 118, 59, P((24, 10, 40), a * 0.9))
            rrect(c, W / 2 - bw / 2, yy - 62, bw, 118, 59, P(VIOLET, a, stroke=4))
            text(c, lab, W / 2 + 30, yy + 18, int(52 * clamp(kk, 0, 1.12)), WHITE, a, "black")
            c.drawCircle(W / 2 - bw / 2 + 62, yy - 3, 30, P(VIOLET, a))
            text(c, "E<0" if i else "?", W / 2 - bw / 2 + 62, yy + 9, 26 if i else 40, WHITE, a, "black")
        if t > 95.6:
            kn = back((t - 95.72) / 0.5)
            a = clamp(kn)
            cross_icon(c, W / 2 + 395, y + 45, 150, RED, a, eout((t - 95.72) / 0.6))
            text(c, "NUNCA ENCONTRADA EN ESAS CANTIDADES", W / 2, y + 240, 34, RED, fin(t, 96.2, 0.5), "black",
                 spacing=1)


def shield(c, x, y, s, color, a, k):
    pth = skia.Path()
    pth.moveTo(x, y - s)
    pth.cubicTo(x + s * 0.5, y - s * 0.78, x + s * 0.82, y - s * 0.8, x + s * 0.86, y - s * 0.8)
    pth.cubicTo(x + s * 0.9, y + s * 0.1, x + s * 0.6, y + s * 0.75, x, y + s * 1.05)
    pth.cubicTo(x - s * 0.6, y + s * 0.75, x - s * 0.9, y + s * 0.1, x - s * 0.86, y - s * 0.8)
    pth.cubicTo(x - s * 0.82, y - s * 0.8, x - s * 0.5, y - s * 0.78, x, y - s)
    pth.close()
    c.save()
    c.translate(x, y)
    sc = lerp(0.6, 1.0, back(k))
    c.scale(sc, sc)
    c.translate(-x, -y)
    c.drawPath(pth, P(color, a * 0.15))
    c.drawPath(pth, P(color, a * 0.6, stroke=14, blur=14))
    c.drawPath(pth, P(color, a, stroke=8))
    c.restore()


def sc_hawking(c, t):
    text(c, "STEPHEN HAWKING", W / 2, 360, 78, WHITE, fin(t, 100.88, 0.5), "black", glow=8, spacing=3)
    part2 = fin(t, 109.4, 0.5)
    a1 = fin(t, 101.9, 0.6) * (1 - part2)
    if a1 > 0:
        cx, cy = W / 2, 860
        shield(c, cx, cy, 300, GOLD, a1, (t - 101.9) / 0.7)
        rev = -(t - 102) / 3
        # reloj que intenta ir atrás y rebota
        bounce = 0.04 * math.sin(t * 7) * clamp((t - 107.5) / 0.3)
        draw_clock(c, cx, cy - 20, 150, 0.0, 0.0 + bounce + 0.02 * math.sin(t * 2), GOLD, a1, glow=False,
                   sec_color=RED)
        text(c, "CONJETURA DE", W / 2, 1300, 46, GOLD, fin(t, 102.32, 0.5) * (1 - part2), "xbold", spacing=5)
        text(c, "PROTECCIÓN CRONOLÓGICA", W / 2, 1385, 64, WHITE, fin(t, 103.0, 0.5) * (1 - part2), "black",
             glow=8)
        kk = fin(t, 106.24, 0.5) * (1 - part2)
        text(c, "las leyes de la naturaleza", W / 2, 1470, 38, MUTED, kk, "med")
        text(c, "IMPIDEN VOLVER ATRÁS", W / 2, 1535, 44, RED, fin(t, 107.52, 0.4) * (1 - part2), "black",
             spacing=2)
    if part2 > 0:
        # fiesta sin invitados
        y = 1000
        text(c, "TURISTAS DEL FUTURO", W / 2, 600, 58, GOLD, part2, "black", spacing=3)
        n = 5
        for i in range(n):
            x = 160 + i * 190
            kk = fin(t, 110.0 + i * 0.12, 0.4)
            person(c, x, y + 120, 200, MUTED, kk * 0.8, stroke=5, dash=True)
        cnt = back((t - 113.04) / 0.5)
        if t > 112.9:
            text(c, "0", W / 2, 1380, int(240 * clamp(cnt, 0, 1.15)), RED, clamp(cnt), "black", glow=24)
        text(c, "¿DÓNDE ESTÁN?", W / 2, 1480, 58, WHITE, fin(t, 113.3, 0.5), "black", glow=10)
        # confeti
        rnd = random.Random(5)
        for i in range(40):
            x = rnd.random() * W
            spd = 120 + rnd.random() * 220
            yy = (rnd.random() * 400 + (t - 109.5) * spd) % 1300 + 450
            colr = (GOLD, CYAN, RED, VIOLET)[i % 4]
            c.save()
            c.translate(x + math.sin(t * 2 + i) * 20, yy)
            c.rotate((t * 180 + i * 40) % 360)
            c.drawRect(skia.Rect.MakeXYWH(-7, -3, 14, 6), P(colr, part2 * 0.5))
            c.restore()


def sc_summary(c, t):
    text(c, "EN RESUMEN", W / 2, 360, 84, WHITE, fin(t, 115.9, 0.5), "black", glow=10, spacing=5)
    cards = [
        (116.96, 640, "FUTURO", CYAN, GREEN, True, "hecho comprobado", "(milésimas de segundo)", 118.5),
        (121.76, 1080, "PASADO", RED, RED, False, "choca con la lógica", "y con la física", 124.9),
    ]
    for t0, y, title, colr, icol, ok, l1, l2, t1 in cards:
        kk = back((t - t0) / 0.6)
        a = clamp(kk)
        if a <= 0:
            continue
        xoff = (1 - eout((t - t0) / 0.6)) * (-400 if ok else 400)
        x = W / 2 + xoff
        bw, bh = 900, 360
        rrect(c, x - bw / 2, y - bh / 2, bw, bh, 40, P((8, 12, 30), a * 0.88))
        rrect(c, x - bw / 2, y - bh / 2, bw, bh, 40, P(colr, a * 0.5, stroke=10, blur=10))
        rrect(c, x - bw / 2, y - bh / 2, bw, bh, 40, P(colr, a, stroke=5))
        c.drawCircle(x - bw / 2 + 140, y, 90, P(icol, a * 0.18))
        if ok:
            check_icon(c, x - bw / 2 + 140, y, 120, icol, a, eout((t - t0 - 0.2) / 0.5))
        else:
            cross_icon(c, x - bw / 2 + 140, y, 120, icol, a, eout((t - t0 - 0.2) / 0.5))
        text(c, title, x - bw / 2 + 270, y - 40, 92, colr, a, "black", align="l", glow=10)
        text(c, l1, x - bw / 2 + 272, y + 40, 42, WHITE, fin(t, t1 - 1.2, 0.5), "semi", align="l")
        text(c, l2, x - bw / 2 + 272, y + 95, 36, MUTED, fin(t, t1 - 0.6, 0.5), "med", align="l")
    text(c, "según todo lo que sabemos hoy", W / 2, 1380, 36, MUTED, fin(t, 123.08, 0.5), "med")


def sc_ending(c, t):
    k = fin(t, 127.5, 0.8)
    q = fin(t, 133.7, 0.6)
    y = lerp(900, 760, ease((t - 133.2) / 1.2))
    r = lerp(300, 230, ease((t - 133.2) / 1.2))
    draw_clock(c, W / 2, y, r, (t - 127) / 60, (t - 127.3), CYAN, k, sec_color=GOLD)
    text(c, "1 s / s", W / 2, y + r + 110, 76, CYAN, fin(t, 131.2, 0.5) * (1 - q), "black", glow=12)
    text(c, "todos viajamos al futuro", W / 2, y + r + 180, 40, MUTED, fin(t, 129.0, 0.5) * (1 - q), "med")
    if t > 135.0:
        kk = back((t - 135.2) / 0.6)
        a = clamp(kk)
        sz = int(80 * clamp(kk, 0, 1.12))
        text(c, "¿QUÉ VAS A HACER", W / 2, 1270, sz, WHITE, a, "black", glow=14)
        text(c, "CUANDO LLEGUES?", W / 2, 1370, sz, GOLD, a, "black", glow=14)


SCENE_FN = {
    "hook": sc_hook, "einstein": sc_einstein, "iss": sc_iss, "gps": sc_gps, "ship": sc_ship,
    "past": sc_past, "paradox": sc_paradox, "wormhole": sc_wormhole, "hawking": sc_hawking,
    "summary": sc_summary, "ending": sc_ending,
}

# ---------------------------------------------------------------- subtitulos
KEY_FUT = ("FUTURO", "FUTURO?", "FUTURO.", "FUTURO,", "FUTURO...")
EMPH = {"FUTURO": CYAN, "PASADO": RED, "EINSTEIN": GOLD, "DILATACIÓN": GOLD, "TEMPORAL": GOLD,
        "GPS": GOLD, "LUZ": CYAN, "DÉCADAS": GOLD, "PARADOJAS": RED, "GUSANO": VIOLET,
        "HAWKING": GOLD, "NEGATIVA": VIOLET, "EXÓTICA": VIOLET, "CRONOLÓGICA": GOLD, "ROMPE": RED,
        "LLEGUES": GOLD, "MILÉSIMAS": CYAN}
CAP_Y = 1650
CAP_SIZE = 64


# Subtitulos SOLO en los momentos clave (frases que no repite el grafico en pantalla)
KEY_MOMENTS = [
    (0.0, 3.8),      # ¿Y si te dijera que viajar al futuro no es ciencia ficción?
    (9.6, 12.7),     # Pero viajar al pasado... es otra historia.
    (18.0, 20.6),    # el tiempo no corre igual para todos.
    (46.7, 49.8),    # tu móvil se equivocaría en varios kilómetros diarios.
    (57.7, 59.7),    # podrían haber pasado décadas.
    (72.2, 75.6),    # Si viajas atrás e impides tu propio nacimiento...
    (80.0, 82.5),    # la lógica del universo se rompe.
    (95.7, 97.4),    # algo que nunca hemos encontrado
    (111.6, 112.9),  # si fuera posible...
    (128.9, 132.9),  # todos ya viajamos al futuro... a un segundo por segundo.
]


def moment_of(w):
    for i, (a, b) in enumerate(KEY_MOMENTS):
        if a <= w["start"] < b:
            return i
    return None


def build_groups():
    words = json.load(open(os.path.join(AUD, "words.json")))["words"]
    ws = [w for w in words if w["type"] == "word" and not w["text"].startswith("[")
          and moment_of(w) is not None]
    groups = []
    cur = []
    for i, w in enumerate(ws):
        cur.append(w)
        txt = " ".join(x["text"] for x in cur).upper()
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        brk = (
            nxt is None
            or len(cur) >= 4
            or w["text"][-1] in ".,:?!…"
            or (nxt and nxt["start"] - w["end"] > 0.3)
            or moment_of(nxt) != moment_of(w)
            or tw_of(txt + " " + nxt["text"].upper(), CAP_SIZE) > 900
        )
        if brk:
            groups.append(cur)
            cur = []
    out = []
    for gi, g in enumerate(groups):
        s = g[0]["start"] - 0.06
        e = g[-1]["end"] + 0.35
        if gi + 1 < len(groups):
            e = min(e, groups[gi + 1][0]["start"] - 0.06)
        out.append((s, e, g))
    return out


GROUPS = None


def captions(c, t):
    global GROUPS
    if GROUPS is None:
        GROUPS = build_groups()
    for s, e, g in GROUPS:
        if not (s <= t < e):
            continue
        a = clamp((t - s) / 0.08) * clamp((e - t) / 0.08)
        pop = back((t - s) / 0.22, 2.2)
        ws = [w["text"].upper() for w in g]
        f = font(CAP_SIZE, "black")
        space = f.measureText(" ") + CAP_SIZE * 0.22
        widths = [f.measureText(x) for x in ws]
        total = sum(widths) + space * (len(ws) - 1)
        x = W / 2 - total / 2
        yb = CAP_Y + (1 - clamp(pop)) * 18
        # placa de fondo sutil
        rrect(c, W / 2 - total / 2 - 34, yb - 70, total + 68, 100, 26, P((0, 0, 0), a * 0.38))
        prev_txt = ""
        for w, txt, wd in zip(g, ws, widths):
            active = w["start"] - 0.03 <= t < w["end"] + 0.05
            said = t >= w["start"] - 0.03
            key = txt.strip("¿?.,:…!")
            base = EMPH.get(key, WHITE)
            if key == "PASADO" and (prev_txt not in ("AL", "¿Y AL")):
                base = WHITE
            prev_txt = txt
            colr = GOLD if (active and base == WHITE) else base
            aa = a * (1.0 if said else 0.55)
            sc = 1.0
            if active:
                sc = 1.0 + 0.10 * (1 - clamp((t - w["start"]) / 0.18))
            c.save()
            cx = x + wd / 2
            c.translate(cx, yb - 22)
            c.scale(sc, sc)
            c.translate(-cx, -(yb - 22))
            c.drawString(txt, x, yb, f, P((0, 0, 0), aa * 0.95, stroke=12))
            if active or base != WHITE:
                c.drawString(txt, x, yb, f, P(colr, aa * 0.55, blur=10))
            c.drawString(txt, x, yb, f, P(colr, aa))
            c.restore()
            x += wd + space


# ---------------------------------------------------------------- hud
def hud(c, t):
    # barra de progreso
    k = clamp(t / 137.0)
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W, 8), P(WHITE, 0.12))
    pa = past_amount(t)
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W * k, 8), P(mix(CYAN, RED, pa), 0.95))
    # capitulo
    for t0, t1, lab, colr in CHAPTERS:
        if lab and t0 - 0.2 <= t < t1:
            a = fwin(t, t0 + 0.1, t1, 0.4)
            f = font(30, "black")
            spacing = 5
            wtxt = sum(f.measureText(ch) for ch in lab) + spacing * (len(lab) - 1)
            bw = wtxt + 90
            x = W / 2 - bw / 2
            y = 130
            rrect(c, x, y, bw, 62, 31, P(colr, a * 0.15))
            rrect(c, x, y, bw, 62, 31, P(colr, a * 0.9, stroke=2.5))
            c.drawCircle(x + 32, y + 31, 7, P(colr, a * (0.6 + 0.4 * math.sin(t * 5))))
            text(c, lab, W / 2 + 12, y + 42, 30, colr, a, "black", spacing=spacing)


# ---------------------------------------------------------------- post (glitch)
def glitch_amount(t):
    g = 0.0
    for t0, d, m in ((9.66, 0.9, 0.8), (66.3, 1.1, 1.0), (81.5, 0.6, 0.9), (75.6, 0.5, 0.35)):
        if t0 <= t < t0 + d:
            g = max(g, m * (1 - (t - t0) / d))
    return g


def post(arr, t):
    g = glitch_amount(t)
    if g <= 0.02:
        return arr
    rnd = np.random.default_rng(int(t * 60))
    out = arr.copy()
    sh = int(18 * g)
    out[:, :, 0] = np.roll(arr[:, :, 0], sh, axis=1)
    out[:, :, 2] = np.roll(arr[:, :, 2], -sh, axis=1)
    for _ in range(int(10 * g)):
        y0 = rnd.integers(0, H - 80)
        hh = rnd.integers(8, 90)
        dx = int(rnd.integers(-60, 60) * g)
        out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], dx, axis=1)
    return out


# ---------------------------------------------------------------- frame
def scene_alpha(t, s0, s1, first, last):
    a = 1.0
    if not first:
        a = min(a, clamp((t - s0 + XF / 2) / XF))
    if not last:
        a = min(a, clamp((s1 + XF / 2 - t) / XF))
    return a


def shake(t):
    s = 0.0
    for t0, d, m in ((0.05, 0.5, 10), (13.6, 0.45, 9), (66.7, 0.6, 16), (81.5, 0.6, 18), (113.04, 0.3, 8),
                     (60.08, 0.3, 6)):
        if t0 <= t < t0 + d:
            s = max(s, m * (1 - (t - t0) / d))
    return math.sin(t * 87) * s, math.cos(t * 71) * s


def render(surface, t):
    c = surface.getCanvas()
    c.save()
    background(c, t)
    sx, sy = shake(t)
    c.translate(sx, sy)
    n = len(SCENES)
    for i, (name, s0, s1) in enumerate(SCENES):
        if s0 - XF <= t < s1 + XF:
            a = scene_alpha(t, s0, s1, i == 0, i == n - 1)
            if a <= 0.001:
                continue
            # leve zoom de entrada
            z = 1.0 + 0.035 * (1 - eout((t - s0) / 0.8))
            c.save()
            c.translate(W / 2, H / 2)
            c.scale(z, z)
            c.translate(-W / 2, -H / 2)
            if a < 0.999:
                c.saveLayerAlpha(None, int(255 * a))
            SCENE_FN[name](c, t)
            if a < 0.999:
                c.restore()
            c.restore()
    c.restore()
    vignette(c)
    hud(c, t)
    captions(c, t)
    # flash blanco en golpes
    for t0 in (13.6, 66.7):
        if t0 <= t < t0 + 0.25:
            c.drawPaint(P(WHITE, 0.35 * (1 - (t - t0) / 0.25)))
    # fundido final
    if t > END - 1.6:
        c.drawPaint(P((0, 0, 0), clamp((t - (END - 1.6)) / 1.4)))
    if t < 0.4:
        c.drawPaint(P((0, 0, 0), 1 - t / 0.4))
    arr = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return post(arr, t)


# ---------------------------------------------------------------- render
def render_chunk(args):
    idx, f0, f1 = args
    surface = skia.Surface(W, H)
    path = os.path.join(HERE, "build", f"chunk_{idx:02d}.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2", "-g", "120",
           "-threads", "2", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        arr = render(surface, f / FPS)
        pr.stdin.write(arr.tobytes())
        if (f - f0) % 300 == 0:
            print(f"[chunk {idx}] {f - f0}/{f1 - f0}", flush=True)
    pr.stdin.close()
    pr.wait()
    return path


def build_audio():
    out = os.path.join(HERE, "build", "mix.wav")
    voice = os.path.join(AUD, "voz_take1.mp3")
    sfx = [  # (archivo, inicio s, volumen dB)
        ("sfx_boom.mp3", 0.0, -6), ("sfx_clock.mp3", 0.2, -14), ("sfx_rewind.mp3", 9.55, -8),
        ("sfx_boom.mp3", 13.5, -7), ("sfx_clock.mp3", 18.1, -16), ("sfx_whoosh.mp3", 29.5, -8),
        ("sfx_whoosh.mp3", 40.7, -9), ("sfx_beeps.mp3", 41.3, -15), ("sfx_beeps.mp3", 43.4, -16),
        ("sfx_whoosh.mp3", 49.9, -9), ("sfx_warp.mp3", 50.4, -8), ("sfx_riser.mp3", 62.3, -12),
        ("sfx_rewind.mp3", 66.2, -5), ("sfx_boom.mp3", 66.65, -5), ("sfx_whoosh.mp3", 69.6, -9),
        ("sfx_rewind.mp3", 72.4, -14), ("sfx_boom.mp3", 81.45, -6), ("sfx_whoosh.mp3", 82.3, -9),
        ("sfx_warp.mp3", 84.9, -18), ("sfx_boom.mp3", 95.7, -10), ("sfx_whoosh.mp3", 99.2, -9),
        ("sfx_riser.mp3", 109.0, -13), ("sfx_boom.mp3", 113.0, -9), ("sfx_whoosh.mp3", 115.3, -9),
        ("sfx_whoosh.mp3", 116.8, -12), ("sfx_whoosh.mp3", 121.6, -12), ("sfx_whoosh.mp3", 127.0, -10),
        ("sfx_clock.mp3", 127.5, -14), ("sfx_boom.mp3", 135.15, -9),
    ]
    inputs = ["-i", voice, "-stream_loop", "-1", "-i", os.path.join(AUD, "sfx_ambience.mp3")]
    for f, _, _ in sfx:
        inputs += ["-i", os.path.join(AUD, f)]
    fl = [f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,adelay=0|0,volume=0dB,"
          f"acompressor=threshold=-20dB:ratio=3:attack=5:release=120,apad=whole_dur={END}[v]",
          f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:{END},volume=-19dB,"
          f"afade=t=in:d=1.5,afade=t=out:st={END - 3}:d=3[amb]"]
    labels = ["[v]", "[amb]"]
    for i, (f, st, db) in enumerate(sfx):
        ms = int(st * 1000)
        fl.append(f"[{i + 2}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,volume={db}dB,adelay={ms}|{ms}[s{i}]")
        labels.append(f"[s{i}]")
    fl.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,"
              f"atrim=0:{END},loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(fl), "-map", "[out]",
                                                      "-ar", "48000", out]
    subprocess.run(cmd, check=True)
    return out


def main():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    if "--stills" in sys.argv:
        os.makedirs(os.path.join(HERE, "stills"), exist_ok=True)
        surface = skia.Surface(W, H)
        for s in sys.argv[sys.argv.index("--stills") + 1:]:
            t = float(s)
            arr = render(surface, t)
            skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType).save(
                os.path.join(HERE, "stills", f"still_{t:05.1f}.png"))
            print("still", t)
        return
    if "--audio" in sys.argv:
        print(build_audio())
        return
    total = int(END * FPS)
    n = int(os.environ.get("WORKERS", "4"))
    step = math.ceil(total / n)
    jobs = [(i, i * step, min(total, (i + 1) * step)) for i in range(n)]
    with Pool(n) as pool:
        parts = pool.map(render_chunk, jobs)
    lst = os.path.join(HERE, "build", "list.txt")
    with open(lst, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    mixwav = build_audio()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", mixwav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-movflags", "+faststart", "-shortest", OUT], check=True)
    print("OK ->", OUT)


if __name__ == "__main__":
    main()
