#!/usr/bin/env python3
"""
EL ORIGEN DE LA NAVIDAD
Short vertical 9:16 (1080x1920) a 60 fps, generado 100% por codigo (skia + numpy + ffmpeg).
Reutiliza las utilidades de dibujo de ../viaje-tiempo/make_video.py.
Voz: ElevenLabs "Ludovico" (narrador latino, 1 toma). Efectos: 3 nuevos (1 variacion) + reutilizados.

Uso:
    python3 make_video.py                 -> navidad_9x16_60fps.mp4
    python3 make_video.py --stills 5 20   -> stills/*.png
    python3 make_video.py --times         -> tiempos de anclaje
"""
import importlib.util
import json
import math
import os
import random
import re
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("vt_make_video",
                                               os.path.join(HERE, "..", "viaje-tiempo", "make_video.py"))
mv = importlib.util.module_from_spec(_spec)
sys.modules["vt_make_video"] = mv
_spec.loader.exec_module(mv)
from vt_make_video import (P, W, H, FPS, back, clamp, col, cross_icon, check_icon, ease, eout, fin,  # noqa: E402
                           font, fwin, lerp, mix, rrect, text, vignette, draw_earth, person)

AUD = os.path.join(HERE, "audio")
OUT = os.path.join(HERE, "navidad_9x16_60fps.mp4")

GOLD = (255, 205, 90)
WARM = (255, 230, 170)
RED = (220, 45, 60)
GREEN = (40, 170, 95)
PINE = (20, 95, 60)
WHITE = (255, 255, 255)
MUTED = (175, 170, 190)
STONE = (205, 190, 165)
SKY = (120, 170, 255)

# ---------------------------------------------------------------- tiempos
WORDS = [w for w in json.load(open(os.path.join(AUD, "words.json")))["words"]
         if w["type"] == "word" and not w["text"].startswith("[")]


def _norm(s):
    return re.sub(r"[¿?¡!.,:;…\"]", "", s.lower())


def _find(phrase, after=0.0):
    toks = _norm(phrase).split()
    for i in range(len(WORDS) - len(toks) + 1):
        if WORDS[i]["start"] >= after and all(_norm(WORDS[i + k]["text"]) == toks[k] for k in range(len(toks))):
            return i, len(toks)
    raise KeyError(phrase)


def at(phrase, after=0.0):
    i, _ = _find(phrase, after)
    return WORDS[i]["start"]


def end_of(phrase, after=0.0):
    i, n = _find(phrase, after)
    return WORDS[i + n - 1]["end"]


VOICE_END = WORDS[-1]["end"]
END = round(VOICE_END + 2.8, 2)

T = dict(
    sabias=at("sabías que"), fecha=at("en qué fecha"), biblia=at("la biblia"), entonces=at("entonces"),
    dic25=at("veinticinco de diciembre"),
    roma=at("viajemos a la antigua roma"), saturnales=at("las saturnales"), banquetes=at("banquetes"),
    regalos=at("regalos y fiestas"), y25=at("y el veinticinco"), sol=at("sol invicto"),
    solsticio=at("solsticio de invierno"), alargarse=at("empiezan a alargarse"),
    siglo4=at("en el siglo cuarto"), misma=at("esa misma fecha"), historiadores=at("muchos historiadores"),
    otros=at("otros"), calculo=at("cálculo teológico"), debate=at("el debate"),
    resto=at("y el resto"), arbol=at("el árbol"), alemania=at("alemania"), s16=at("siglo dieciséis"),
    nacimiento=at("el primer nacimiento"), francisco=at("san francisco"), y1223=at("mil doscientos"),
    santa=at("y santa claus"), nicolas=at("san nicolás"), obispo=at("un obispo"), secreto=at("en secreto"),
    turquia=at("turquía"),
    yno=at("y no"), rojo=at("vistió de rojo"), antes=at("mucho antes"),
    asi=at("así que la navidad"), origen=at("un solo origen"), culturas=at("muchas culturas"),
    noche=at("una misma noche"),
)

SCENES = [
    ("hook", 0.0, T["roma"] - 0.25),
    ("rome", T["roma"] - 0.25, T["siglo4"] - 0.25),
    ("church", T["siglo4"] - 0.25, T["resto"] - 0.25),
    ("tree", T["resto"] - 0.25, T["nacimiento"] - 0.2),
    ("nativity", T["nacimiento"] - 0.2, T["santa"] - 0.2),
    ("santa", T["santa"] - 0.2, T["asi"] - 0.25),
    ("ending", T["asi"] - 0.25, END),
]
XF = 0.3

mv.AUD = AUD
mv.CAP_Y = 1680
mv.KEY_MOMENTS = [
    (T["biblia"] - 0.1, end_of("no lo dice") + 0.05),
    (T["historiadores"] - 0.1, end_of("cálculo teológico") + 0.05),
    (at("que hacía regalos") - 0.1, end_of("en secreto") + 0.05),
    (at("ya lo era") - 0.1, end_of("mucho antes") + 0.05),
]
mv.EMPH = {"SECRETO": GOLD, "TEOLÓGICO": GOLD, "SENTIDO": GOLD, "ANTES": RED, "BIBLIA": GOLD}

# ---------------------------------------------------------------- fondo
rng = np.random.default_rng(12)
NSN = 260
SNX, SNY = rng.random(NSN) * W, rng.random(NSN) * H
SNZ = rng.random(NSN) ** 1.5 * 0.9 + 0.1
SNP = rng.random(NSN) * 6.28
NST = 160
STX, STY = rng.random(NST) * W, rng.random(NST) * H * 0.6
STZ = rng.random(NST)


def background(c, t, warm=0.0):
    top = mix((10, 14, 38), (40, 16, 20), warm)
    mid = mix((28, 26, 70), (90, 40, 30), warm)
    bot = mix((8, 10, 26), (30, 12, 10), warm)
    sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)], [col(top), col(mid), col(bot)],
                                        [0, 0.55, 1])
    c.drawPaint(P(WHITE, 1, shader=sh))
    g = skia.GradientShader.MakeRadial(skia.Point(W / 2, 700), 900, [col(GOLD, 0.10 + 0.08 * warm), col(GOLD, 0)])
    c.drawCircle(W / 2, 700, 900, P(WHITE, 1, shader=g))
    for i in range(NST):
        tw = 0.5 + 0.5 * math.sin(t * (1.2 + STZ[i] * 2) + i)
        c.drawCircle(STX[i], STY[i], 0.8 + 1.6 * STZ[i], P(WHITE, (0.15 + 0.5 * STZ[i]) * tw * (1 - warm * 0.7)))
    # nieve
    for i in range(NSN):
        z = SNZ[i]
        y = (SNY[i] + t * (40 + 90 * z)) % (H + 40) - 20
        x = (SNX[i] + math.sin(t * 0.8 + SNP[i]) * 30 * z) % W
        r = 1.2 + 4.0 * z
        c.drawCircle(x, y, r, P(WHITE, 0.25 + 0.55 * z))
        if z > 0.8:
            c.drawCircle(x, y, r * 2.4, P(WHITE, 0.12, blur=r))


def star(c, x, y, r, color, a, rot=0.0, glow=True):
    pth = skia.Path()
    for i in range(10):
        ang = rot - math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        px, py = x + math.cos(ang) * rr, y + math.sin(ang) * rr
        (pth.moveTo if i == 0 else pth.lineTo)(px, py)
    pth.close()
    if glow:
        c.drawPath(pth, P(color, a * 0.7, blur=r * 0.35))
        c.drawCircle(x, y, r * 1.6, P(color, a * 0.18, blur=r * 0.6))
    c.drawPath(pth, P(color, a))


def gift(c, x, y, s, body, ribbon, a):
    rrect(c, x - s / 2, y - s * 0.8, s, s * 0.8, s * 0.06, P(body, a))
    rrect(c, x - s * 0.56, y - s * 0.98, s * 1.12, s * 0.22, s * 0.05, P(mix(body, WHITE, 0.15), a))
    c.drawRect(skia.Rect.MakeXYWH(x - s * 0.08, y - s * 0.98, s * 0.16, s * 0.98), P(ribbon, a))
    c.drawOval(skia.Rect.MakeXYWH(x - s * 0.36, y - s * 1.2, s * 0.34, s * 0.24), P(ribbon, a, stroke=s * 0.06))
    c.drawOval(skia.Rect.MakeXYWH(x + s * 0.02, y - s * 1.2, s * 0.34, s * 0.24), P(ribbon, a, stroke=s * 0.06))


# ---------------------------------------------------------------- escenas
def sc_hook(c, t):
    # pagina de calendario
    k = back((t - T["sabias"]) / 0.6)
    a = clamp(k)
    cx, cy = W / 2, 820
    s = clamp(k, 0, 1.08)
    c.save()
    c.translate(cx, cy)
    c.rotate(math.sin(t * 1.3) * 3)
    c.scale(s, s)
    rrect(c, -230, -260, 460, 500, 40, P((250, 246, 238), a))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-230, -260, 460, 140), 40, 40), P(RED, a))
    c.drawRect(skia.Rect.MakeXYWH(-230, -170, 460, 50), P(RED, a))
    for x in (-120, 120):
        c.drawCircle(x, -262, 18, P((60, 60, 70), a))
    text(c, "DICIEMBRE", 0, -165, 52, WHITE, a, "black", spacing=4)
    show25 = fin(t, T["dic25"], 0.3)
    q = 1 - show25
    text(c, "?", 0, 120, 280, (50, 50, 60), a * q, "black")
    text(c, "25", 0, 130, int(280 * lerp(0.8, 1.0, back((t - T["dic25"]) / 0.4))), RED, a * show25, "black")
    c.restore()
    text(c, "¿CUÁNDO NACIÓ JESÚS?", W / 2, 400, 70, WHITE, fin(t, T["fecha"] - 0.3, 0.5) * (1 - fin(t, T["entonces"], 0.4)),
         "black", glow=10)
    kb = fin(t, T["biblia"], 0.4) * (1 - fin(t, T["entonces"], 0.4))
    if kb > 0:
        # libro abierto
        bx, by = W / 2, 1310
        for sgn in (-1, 1):
            pg = skia.Path()
            pg.moveTo(bx, by - 70)
            pg.quadTo(bx + sgn * 90, by - 100, bx + sgn * 180, by - 80)
            pg.lineTo(bx + sgn * 180, by + 50)
            pg.quadTo(bx + sgn * 90, by + 30, bx, by + 60)
            pg.close()
            c.drawPath(pg, P(WARM, kb))
            for j in range(4):
                c.drawLine(bx + sgn * 30, by - 40 + j * 22, bx + sgn * 150, by - 50 + j * 22, P(MUTED, kb, stroke=3))
        text(c, "NO LO DICE", W / 2, 1460, 54, GOLD, kb, "black", spacing=4, glow=8)
    if t > T["entonces"]:
        ke = back((t - T["dic25"] - 0.5) / 0.5) if t > T["dic25"] else 0
        text(c, "¿POR QUÉ EL 25?", W / 2, 400, int(96 * clamp(ke, 0, 1.12)), GOLD, clamp(ke), "black", glow=16)


def temple(c, cx, base, w, h, a):
    col_n = 6
    rrect(c, cx - w / 2 - 20, base - 30, w + 40, 30, 4, P(STONE, a))
    rrect(c, cx - w / 2 - 40, base, w + 80, 26, 4, P(mix(STONE, (0, 0, 0), 0.2), a))
    for i in range(col_n):
        x = cx - w / 2 + 25 + i * (w - 50) / (col_n - 1)
        rrect(c, x - 18, base - 30 - h, 36, h, 6, P(STONE, a))
        c.drawRect(skia.Rect.MakeXYWH(x - 24, base - 40 - h, 48, 14), P(STONE, a))
    c.drawRect(skia.Rect.MakeXYWH(cx - w / 2 - 20, base - 60 - h, w + 40, 26), P(STONE, a))
    roof = skia.Path()
    roof.moveTo(cx - w / 2 - 40, base - 60 - h)
    roof.lineTo(cx, base - 60 - h - 110)
    roof.lineTo(cx + w / 2 + 40, base - 60 - h)
    roof.close()
    c.drawPath(roof, P(STONE, a))


def sc_rome(c, t):
    k = fin(t, T["roma"], 0.6)
    text(c, "ANTIGUA ROMA", W / 2, 360, 90, GOLD, k, "black", glow=12, spacing=4)
    sol = fin(t, T["y25"] - 0.2, 0.5)
    # templo + saturnales
    ta = k * (1 - sol)
    if ta > 0:
        temple(c, W / 2, 1050, 620, 330, ta)
        ks = back((t - T["saturnales"]) / 0.5)
        text(c, "SATURNALES", W / 2, 520, int(80 * clamp(ks, 0, 1.12)), RED, clamp(ks) * ta, "black", glow=12)
        items = [("BANQUETES", T["banquetes"]), ("REGALOS", T["regalos"]), ("FIESTAS", T["regalos"] + 0.7)]
        for i, (lab, t0) in enumerate(items):
            kk = back((t - t0) / 0.45)
            x = 200 + i * 340
            y = 1290
            a = clamp(kk) * ta
            if a <= 0:
                continue
            rrect(c, x - 150, y - 120, 300, 230, 30, P((40, 20, 30), a * 0.85))
            rrect(c, x - 150, y - 120, 300, 230, 30, P(GOLD, a, stroke=3))
            if i == 0:  # copa
                cp = skia.Path()
                cp.moveTo(x - 40, y - 80)
                cp.quadTo(x, y + 10, x + 40, y - 80)
                cp.close()
                c.drawPath(cp, P(RED, a))
                c.drawLine(x, y - 40, x, y + 10, P(GOLD, a, stroke=6))
                c.drawLine(x - 25, y + 12, x + 25, y + 12, P(GOLD, a, stroke=6))
            elif i == 1:
                gift(c, x, y + 15, 90, RED, GOLD, a)
            else:
                for j in range(5):
                    ang = j / 5 * 6.28 + t * 2
                    c.drawCircle(x + math.cos(ang) * 40, y - 30 + math.sin(ang) * 40, 9,
                                 P((GOLD, RED, GREEN, SKY, WHITE)[j], a))
            text(c, lab, x, y + 85, 32, WHITE, a, "black", spacing=2)
    # Sol Invicto + solsticio
    if sol > 0:
        sy = lerp(1150, 900, ease((t - T["y25"]) / 2.0))
        rays = 16
        for i in range(rays):
            ang = i / rays * 6.28 + t * 0.3
            c.drawLine(W / 2 + math.cos(ang) * 190, sy + math.sin(ang) * 190, W / 2 + math.cos(ang) * 270,
                       sy + math.sin(ang) * 270, P(GOLD, sol * 0.8, stroke=10))
        c.drawCircle(W / 2, sy, 230, P(GOLD, sol * 0.4, blur=60))
        c.drawCircle(W / 2, sy, 160, P((255, 220, 120), sol))
        kv = back((t - T["sol"]) / 0.5)
        text(c, "SOL INVICTO", W / 2, 520, int(86 * clamp(kv, 0, 1.12)), GOLD, clamp(kv), "black", glow=14)
        text(c, "25 de diciembre", W / 2, 590, 42, WARM, clamp(kv), "semi")
        # grafica de duracion del dia
        kg = fin(t, T["solsticio"], 0.5)
        if kg > 0:
            y0, x0, x1 = 1420, 130, 950
            rrect(c, x0 - 30, y0 - 160, x1 - x0 + 60, 250, 26, P((20, 16, 30), kg * 0.85))
            pth = skia.Path()
            prog = clamp((t - T["solsticio"]) / 1.5)
            for i in range(0, int(120 * prog) + 1):
                u = i / 120
                x = lerp(x0, x1, u)
                y = y0 - 20 - 90 * (1 - math.cos((u - 0.5) * math.pi * 1.4)) / 2
                (pth.moveTo if i == 0 else pth.lineTo)(x, y)
            c.drawPath(pth, P(GOLD, kg, stroke=6))
            mx = (x0 + x1) / 2
            c.drawLine(mx, y0 - 140, mx, y0 + 10, P(SKY, kg * 0.8, stroke=3))
            text(c, "SOLSTICIO", mx, y0 + 60, 32, SKY, kg, "black", spacing=3)
            text(c, "duración del día", x0 + 10, y0 - 120, 28, MUTED, kg, "semi", align="l")
            ka = fin(t, T["alargarse"], 0.4)
            text(c, "los días crecen →", x1 - 10, y0 - 120, 32, GOLD, ka, "black", align="r")


def church(c, cx, base, s, a):
    rrect(c, cx - s * 0.5, base - s * 0.7, s, s * 0.7, 6, P(STONE, a))
    roof = skia.Path()
    roof.moveTo(cx - s * 0.6, base - s * 0.7)
    roof.lineTo(cx, base - s * 1.05)
    roof.lineTo(cx + s * 0.6, base - s * 0.7)
    roof.close()
    c.drawPath(roof, P(mix(STONE, RED, 0.4), a))
    rrect(c, cx - s * 0.13, base - s * 1.45, s * 0.26, s * 0.5, 4, P(STONE, a))
    c.drawLine(cx, base - s * 1.62, cx, base - s * 1.42, P(GOLD, a, stroke=8))
    c.drawLine(cx - s * 0.07, base - s * 1.55, cx + s * 0.07, base - s * 1.55, P(GOLD, a, stroke=8))
    c.drawOval(skia.Rect.MakeXYWH(cx - s * 0.1, base - s * 0.32, s * 0.2, s * 0.32), P((60, 40, 30), a))
    c.drawCircle(cx, base - s * 0.52, s * 0.08, P(GOLD, a))


def sc_church(c, t):
    k = fin(t, T["siglo4"], 0.5)
    text(c, "SIGLO IV", W / 2, 380, 120, GOLD, k, "black", glow=14)
    church(c, W / 2, 1080, 320, k)
    km = back((t - T["misma"]) / 0.5)
    text(c, "NAVIDAD = 25 DIC", W / 2, 500, int(64 * clamp(km, 0, 1.12)), WHITE, clamp(km), "black", spacing=2)
    # dos teorias
    for i, (lab, sub, t0) in enumerate((("TEORÍA 1", "dar nuevo sentido\na las fiestas", T["historiadores"]),
                                         ("TEORÍA 2", "cálculo\nteológico", T["calculo"] - 0.6))):
        kk = back((t - t0) / 0.5)
        a = clamp(kk)
        if a <= 0:
            continue
        x = 280 + i * 520
        y = 1230
        rrect(c, x - 230, y - 90, 460, 260, 30, P((28, 20, 40), a * 0.9))
        rrect(c, x - 230, y - 90, 460, 260, 30, P(GOLD if i == 0 else SKY, a, stroke=4))
        text(c, lab, x, y - 25, 40, GOLD if i == 0 else SKY, a, "black", spacing=3)
        for j, line in enumerate(sub.split("\n")):
            text(c, line, x, y + 40 + j * 50, 38, WHITE, a, "semi")
    kd = back((t - T["debate"]) / 0.5)
    text(c, "DEBATE ABIERTO", W / 2, 1560, int(56 * clamp(kd, 0, 1.12)), GOLD, clamp(kd), "black", glow=10,
         spacing=3)


def xmas_tree(c, cx, base, s, a, t, lights):
    c.drawRect(skia.Rect.MakeXYWH(cx - s * 0.08, base - s * 0.15, s * 0.16, s * 0.18), P((100, 60, 30), a))
    for i, (w, y0, y1) in enumerate(((0.55, 0.15, 0.55), (0.45, 0.42, 0.8), (0.33, 0.68, 1.05))):
        p = skia.Path()
        p.moveTo(cx - s * w, base - s * y0)
        p.lineTo(cx, base - s * y1 - s * 0.12)
        p.lineTo(cx + s * w, base - s * y0)
        p.close()
        c.drawPath(p, P(mix(PINE, GREEN, i * 0.25), a))
    rnd = random.Random(3)
    cols = (RED, GOLD, SKY, WHITE, (255, 120, 200))
    for i in range(26):
        u = rnd.random()
        yy = base - s * (0.2 + u * 0.8)
        hw = s * 0.5 * (1 - u * 0.85)
        x = cx + (rnd.random() - 0.5) * 2 * hw * 0.8
        on = clamp(lights * 26 - i)
        blink = 0.6 + 0.4 * math.sin(t * 4 + i)
        cc = cols[i % 5]
        c.drawCircle(x, yy, s * 0.03, P(cc, a * on))
        c.drawCircle(x, yy, s * 0.07, P(cc, a * on * 0.45 * blink, blur=s * 0.03))
    star(c, cx, base - s * 1.2, s * 0.12, GOLD, a * clamp(lights * 1.5), rot=t * 0.3)


def sc_tree(c, t):
    k = fin(t, T["resto"], 0.4)
    text(c, "¿Y EL RESTO?", W / 2, 400, 90, WHITE, k * (1 - fin(t, T["arbol"] + 0.2, 0.3)), "black", glow=10)
    ka = fin(t, T["arbol"], 0.5)
    xmas_tree(c, W / 2, 1380, 640, ka, t, clamp((t - T["arbol"]) / 2.0))
    text(c, "EL ÁRBOL", W / 2, 360, 100, GREEN, fin(t, T["arbol"] + 0.2, 0.4), "black", glow=12)
    text(c, "ALEMANIA · SIGLO XVI", W / 2, 450, 46, GOLD, fin(t, T["alemania"], 0.4), "black", spacing=3)


def sc_nativity(c, t):
    k = fin(t, T["nacimiento"], 0.5)
    text(c, "EL PRIMER", W / 2, 340, 64, WHITE, k, "black", spacing=4)
    text(c, "NACIMIENTO", W / 2, 450, 104, GOLD, k, "black", glow=14)
    # establo
    cx, base = W / 2, 1280
    p = skia.Path()
    p.moveTo(cx - 330, base)
    p.lineTo(cx - 330, base - 260)
    p.lineTo(cx, base - 450)
    p.lineTo(cx + 330, base - 260)
    p.lineTo(cx + 330, base)
    c.drawPath(p, P((120, 80, 50), k, stroke=18, cap=False))
    c.drawLine(cx - 380, base, cx + 380, base, P((120, 80, 50), k, stroke=14))
    g = skia.GradientShader.MakeRadial(skia.Point(cx, base - 120), 320, [col(GOLD, 0.45 * k), col(GOLD, 0)])
    c.drawCircle(cx, base - 120, 320, P(WHITE, 1, shader=g))
    # pesebre
    rrect(c, cx - 70, base - 80, 140, 60, 12, P((150, 100, 60), k))
    c.drawCircle(cx, base - 92, 26, P(WARM, k))
    person(c, cx - 190, base - 6, 230, (60, 70, 140), k)
    person(c, cx + 190, base - 6, 250, (110, 70, 50), k)
    star(c, cx, base - 640, 60, GOLD, k * (0.85 + 0.15 * math.sin(t * 3)), rot=t * 0.2)
    kf = back((t - T["francisco"]) / 0.5)
    text(c, "SAN FRANCISCO DE ASÍS", W / 2, 1420, int(56 * clamp(kf, 0, 1.12)), WHITE, clamp(kf), "black")
    ky = back((t - T["y1223"]) / 0.5)
    text(c, "1223", W / 2, 1550, int(110 * clamp(ky, 0, 1.12)), GOLD, clamp(ky), "black", glow=14)


def mitre(c, x, y, s, a):
    p = skia.Path()
    p.moveTo(x - s * 0.45, y)
    p.lineTo(x - s * 0.45, y - s * 0.6)
    p.quadTo(x - s * 0.3, y - s * 1.1, x, y - s * 1.25)
    p.quadTo(x + s * 0.3, y - s * 1.1, x + s * 0.45, y - s * 0.6)
    p.lineTo(x + s * 0.45, y)
    p.close()
    c.drawPath(p, P(WARM, a))
    c.drawLine(x, y - s * 1.15, x, y, P(GOLD, a, stroke=s * 0.1))
    c.drawLine(x - s * 0.45, y - s * 0.35, x + s * 0.45, y - s * 0.35, P(GOLD, a, stroke=s * 0.08))


def santa_hat(c, x, y, s, a, t):
    p = skia.Path()
    p.moveTo(x - s * 0.55, y)
    p.cubicTo(x - s * 0.4, y - s * 0.9, x + s * 0.2, y - s * 1.2, x + s * 0.75, y - s * 0.55)
    p.lineTo(x + s * 0.55, y)
    p.close()
    c.drawPath(p, P(RED, a))
    rrect(c, x - s * 0.65, y - s * 0.12, s * 1.3, s * 0.3, s * 0.15, P(WHITE, a))
    c.drawCircle(x + s * 0.78, y - s * 0.5 + math.sin(t * 3) * 4, s * 0.16, P(WHITE, a))


def sc_santa(c, t):
    k = fin(t, T["santa"], 0.5)
    myth = fin(t, T["yno"] - 0.1, 0.4)
    text(c, "SANTA CLAUS", W / 2, 380, 100, RED, k * (1 - myth), "black", glow=14)
    # mitra -> gorro
    morph = ease((t - T["obispo"] - 0.3) / 0.8) if t < T["yno"] else 1.0
    cx, cy = W / 2, 1000
    a = k * (1 - myth * 0.85)
    if morph < 1:
        mitre(c, cx, cy, 360, a * (1 - morph))
    if morph > 0:
        santa_hat(c, cx, cy, 340, a * morph, t)
    kn = back((t - T["nicolas"]) / 0.5)
    text(c, "SAN NICOLÁS DE MIRA", W / 2, 470, int(58 * clamp(kn, 0, 1.12)), GOLD, clamp(kn) * (1 - myth), "black")
    text(c, "obispo · siglo IV", W / 2, 540, 40, WARM, clamp(kn) * (1 - myth), "semi")
    kt = fin(t, T["turquia"], 0.4) * (1 - myth)
    text(c, "hoy: TURQUÍA", W / 2, 1180, 50, WHITE, kt, "black", spacing=3)
    # regalos secretos
    if t > T["secreto"] - 0.3:
        for i in range(3):
            kk = back((t - T["secreto"] - i * 0.15) / 0.4) * (1 - myth)
            gift(c, 300 + i * 240, 1420, 120, (RED, GREEN, SKY)[i], GOLD, clamp(kk))
    # mito Coca-Cola
    if myth > 0:
        km = back((t - T["yno"] - 0.3) / 0.5)
        y = 520
        text(c, "¿COCA-COLA?", W / 2, y, int(90 * clamp(km, 0, 1.12)), WHITE, clamp(km), "black", glow=8)
        # sello MITO
        kr = back((t - T["rojo"]) / 0.4)
        if kr > 0:
            c.save()
            c.translate(W / 2, 1320)
            c.rotate(-12)
            sc = lerp(2.2, 1.0, clamp(kr))
            c.scale(sc, sc)
            ar = clamp(kr)
            rrect(c, -230, -90, 460, 180, 24, P(RED, ar, stroke=12))
            text(c, "MITO", 0, 45, 130, RED, ar, "black")
            c.restore()
        ka = fin(t, T["antes"], 0.4)
        text(c, "ya vestía de rojo mucho antes de 1931", W / 2, 1520, 38, WARM, ka, "semi")


def sc_ending(c, t):
    k = fin(t, T["asi"], 0.6)
    ex, ey, er = W / 2, 980, 300
    draw_earth(c, ex, ey, er, k, t * 2)
    # luces conectando culturas
    kc = fin(t, T["culturas"], 0.6)
    rnd = random.Random(21)
    pts = []
    for i in range(14):
        ang = rnd.random() * 6.28
        rr = er * (0.3 + rnd.random() * 0.65)
        pts.append((ex + math.cos(ang) * rr, ey + math.sin(ang) * rr))
    for i in range(len(pts) - 1):
        kk = clamp(kc * 14 - i)
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        c.drawLine(x0, y0, lerp(x0, x1, kk), lerp(y0, y1, kk), P(GOLD, k * 0.7, stroke=3))
    for i, (x, y) in enumerate(pts):
        kk = clamp(kc * 14 - i + 1)
        c.drawCircle(x, y, 9, P((GOLD, RED, GREEN, WHITE)[i % 4], k * kk))
        c.drawCircle(x, y, 22, P(GOLD, k * kk * 0.35, blur=10))
    ko = back((t - T["origen"]) / 0.5)
    text(c, "NO TIENE UN SOLO ORIGEN", W / 2, 420, int(62 * clamp(ko, 0, 1.12)), WHITE, clamp(ko), "black", glow=8)
    kn = back((t - T["noche"]) / 0.6)
    text(c, "MUCHAS CULTURAS", W / 2, 1420, int(76 * clamp(kn, 0, 1.12)), GOLD, clamp(kn), "black", glow=12)
    text(c, "UNA MISMA NOCHE", W / 2, 1520, int(76 * clamp(kn, 0, 1.12)), WHITE, clamp(kn), "black", glow=12)
    star(c, W / 2, 610, 50, GOLD, clamp(kn), rot=t * 0.4)


SCENE_FN = {"hook": sc_hook, "rome": sc_rome, "church": sc_church, "tree": sc_tree, "nativity": sc_nativity,
            "santa": sc_santa, "ending": sc_ending}


# ---------------------------------------------------------------- hud
def hud(c, t):
    k = clamp(t / VOICE_END)
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W, 8), P(WHITE, 0.12))
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W * k, 8), P(RED, 0.95))


SHAKES = [(T["dic25"], 0.3, 6), (T["rojo"], 0.35, 10)]


def render(surface, t):
    c = surface.getCanvas()
    warm = fwin(t, T["roma"], T["siglo4"] - 0.25, 0.6)
    c.save()
    background(c, t, warm)
    s = 0.0
    for t0, d, m in SHAKES:
        if t0 <= t < t0 + d:
            s = max(s, m * (1 - (t - t0) / d))
    c.translate(math.sin(t * 87) * s, math.cos(t * 71) * s)
    n = len(SCENES)
    for i, (name, s0, s1) in enumerate(SCENES):
        if s0 - XF <= t < s1 + XF:
            a = 1.0
            if i > 0:
                a = min(a, clamp((t - s0 + XF / 2) / XF))
            if i < n - 1:
                a = min(a, clamp((s1 + XF / 2 - t) / XF))
            if a <= 0.001:
                continue
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
    mv.captions(c, t)
    if t > END - 1.6:
        c.drawPaint(P((0, 0, 0), clamp((t - (END - 1.6)) / 1.4)))
    if t < 0.3:
        c.drawPaint(P((0, 0, 0), 1 - t / 0.3))
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)


# ---------------------------------------------------------------- audio
def loudness(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


def build_audio():
    out = os.path.join(HERE, "build", "mix.wav")
    voice = os.path.join(AUD, "voz.mp3")
    vI = loudness(voice)
    ev = [  # (archivo, inicio, LU relativo a la voz)
        ("sfx_bells.mp3", 0.0, -12), ("sfx_sparkle.mp3", T["dic25"] - 0.1, -11),
        ("sfx_whoosh.mp3", T["roma"] - 0.5, -13), ("sfx_boom.mp3", T["saturnales"] - 0.05, -15),
        ("sfx_sparkle.mp3", T["sol"] - 0.1, -12), ("sfx_whoosh.mp3", T["siglo4"] - 0.5, -13),
        ("sfx_boom.mp3", T["siglo4"], -15), ("sfx_whoosh.mp3", T["resto"] - 0.5, -13),
        ("sfx_sparkle.mp3", T["arbol"] + 0.3, -11), ("sfx_whoosh.mp3", T["nacimiento"] - 0.5, -13),
        ("sfx_sparkle.mp3", T["y1223"] - 0.1, -12), ("sfx_bells.mp3", T["santa"] - 0.2, -12),
        ("sfx_rewind.mp3", T["yno"] - 0.2, -16), ("sfx_boom.mp3", T["rojo"] - 0.05, -12),
        ("sfx_whoosh.mp3", T["asi"] - 0.5, -13), ("sfx_riser.mp3", T["noche"] - 3.6, -16),
        ("sfx_bells.mp3", T["noche"] + 0.2, -11),
    ]
    files = sorted({f for f, _, _ in ev} | {"sfx_winter.mp3"})
    LI = {f: loudness(os.path.join(AUD, f)) for f in files}
    inputs = ["-i", voice, "-stream_loop", "-1", "-i", os.path.join(AUD, "sfx_winter.mp3")]
    for f, _, _ in ev:
        inputs += ["-i", os.path.join(AUD, f)]
    fl = [f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
          f"acompressor=threshold=-20dB:ratio=3:attack=5:release=120,apad=whole_dur={END}[v]",
          f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:{END},"
          f"volume={vI - 16 - LI['sfx_winter.mp3']:.1f}dB,afade=t=in:d=1.0,afade=t=out:st={END - 3}:d=3[amb]"]
    labels = ["[v]", "[amb]"]
    for i, (f, st, rel) in enumerate(ev):
        ms = max(0, int(st * 1000))
        fl.append(f"[{i + 2}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,volume={vI + rel - LI[f]:.1f}dB,"
                  f"adelay={ms}|{ms}[s{i}]")
        labels.append(f"[s{i}]")
    fl.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,"
              f"atrim=0:{END},loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(fl), "-map", "[out]",
                                                                "-ar", "48000", out], check=True)
    return out


# ---------------------------------------------------------------- render
def render_chunk(args):
    idx, f0, f1 = args
    surface = skia.Surface(W, H)
    path = os.path.join(HERE, "build", f"chunk_{idx:02d}.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2", "-g", "120", "-threads", "2", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        pr.stdin.write(render(surface, f / FPS).tobytes())
    pr.stdin.close()
    pr.wait()
    return path


def main():
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    if "--times" in sys.argv:
        for k, v in T.items():
            print(f"{k:14s} {v:7.2f}")
        print("END", END)
        return
    if "--stills" in sys.argv:
        os.makedirs(os.path.join(HERE, "stills"), exist_ok=True)
        surface = skia.Surface(W, H)
        for s in sys.argv[sys.argv.index("--stills") + 1:]:
            t = float(s)
            skia.Image.fromarray(render(surface, t), colorType=skia.kRGBA_8888_ColorType).save(
                os.path.join(HERE, "stills", f"still_{t:05.1f}.png"))
        return
    if "--audio" in sys.argv:
        print(build_audio())
        return
    total = int(END * FPS)
    n = int(os.environ.get("WORKERS", "4"))
    step = math.ceil(total / n)
    with Pool(n) as pool:
        parts = pool.map(render_chunk, [(i, i * step, min(total, (i + 1) * step)) for i in range(n)])
    lst = os.path.join(HERE, "build", "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    mixwav = build_audio()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", mixwav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-movflags", "+faststart", "-shortest", OUT], check=True)
    print("OK ->", OUT)


if __name__ == "__main__":
    main()
