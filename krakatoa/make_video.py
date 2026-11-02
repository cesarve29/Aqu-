#!/usr/bin/env python3
"""
EL SONIDO MÁS FUERTE DE LA HISTORIA (Krakatoa, 1883)
Short vertical 9:16 (1080x1920) a 60 fps, generado 100% por codigo (skia + numpy + ffmpeg).
Reutiliza las utilidades de dibujo de ../viaje-tiempo/make_video.py.
Voz: ElevenLabs "Ludovico" (narrador latino, 1 toma). Efectos: 2 nuevos (1 variacion) + reutilizados.

Uso:
    python3 make_video.py                 -> krakatoa_9x16_60fps.mp4
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
from vt_make_video import (P, W, H, FPS, back, clamp, col, cross_icon, ease, eout, ein, fin,  # noqa: E402
                           font, fwin, lerp, mix, rrect, text, vignette, draw_earth)

AUD = os.path.join(HERE, "audio")
OUT = os.path.join(HERE, "krakatoa_9x16_60fps.mp4")

CYAN = (56, 225, 255)
RED = (255, 59, 92)
ORANGE = (255, 120, 40)
LAVA = (255, 80, 20)
GOLD = (255, 210, 63)
WHITE = (255, 255, 255)
MUTED = (165, 160, 170)
ASH = (90, 82, 80)
GREEN = (60, 230, 150)

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
END = round(VOICE_END + 2.6, 2)

T = dict(
    cual=at("cuál fue"), sonido=at("el sonido más fuerte"), bomba=at("no fue una bomba"),
    volcan=at("fue un volcán"), fecha=at("veintisiete de agosto"), indonesia=at("indonesia"),
    explota=at("explota"), estruendo=at("y el estruendo"), cinco=at("casi cinco mil"),
    mexico=at("más lejos que"), lima=at("a lima"), isla=at("en una isla"),
    canon=at("cañonazos"), barco=at("de un barco en apuros"), ciento=at("a ciento sesenta"),
    medidores=at("los medidores"), decibeles=at("ciento setenta decibeles"), rock=at("un concierto de rock"),
    ciento20=at("los ciento veinte"), barco2=at("y en un barco cercano"), mitad=at("más de la mitad"),
    timpanos=at("se le reventaron"), pero=at("pero lo más increíble"), onda=at("la onda de presión"),
    vuelta=at("dio la vuelta"), novez=at("no una vez"), varias=at("sino varias"),
    cinco_dias=at("durante cinco días"), barometros=at("los barómetros"), cenizas=at("las cenizas"),
    rojo=at("de rojo"), meses=at("durante meses"), asi=at("así que recuérdalo"),
    hubo=at("hubo un día"), planeta=at("todo el planeta"), solo=at("un solo sonido"),
)

SCENES = [
    ("hook", 0.0, T["fecha"] - 0.25),
    ("eruption", T["fecha"] - 0.25, T["estruendo"] - 0.2),
    ("distance", T["estruendo"] - 0.2, T["isla"] - 0.25),
    ("island", T["isla"] - 0.25, T["ciento"] - 0.25),
    ("meter", T["ciento"] - 0.25, T["pero"] - 0.25),
    ("globe", T["pero"] - 0.25, T["cenizas"] - 0.25),
    ("sunset", T["cenizas"] - 0.25, T["asi"] - 0.25),
    ("ending", T["asi"] - 0.25, END),
]
XF = 0.3

mv.AUD = AUD
mv.CAP_Y = 1660
mv.KEY_MOMENTS = [
    (at("la gente pensó") - 0.1, end_of("barco en apuros") + 0.05),
    (T["mitad"] - 0.1, end_of("se le reventaron los tímpanos") + 0.05),
    (T["novez"] - 0.1, end_of("sino varias") + 0.05),
    (at("tiñeron de rojo") - 0.1, end_of("del mundo entero") + 0.05),
]
mv.EMPH = {"CAÑONAZOS": GOLD, "TÍMPANOS": RED, "REVENTARON": RED, "VARIAS": ORANGE, "ROJO": RED}


# ---------------------------------------------------------------- fondo
rng = np.random.default_rng(5)
NST = 300
STX, STY = rng.random(NST) * W, rng.random(NST) * H * 0.7
STZ = rng.random(NST) ** 2 * 0.9 + 0.1
STP = rng.random(NST) * 6.28


def background(c, t, heat=0.0, sunset=0.0):
    top = mix(mix((8, 6, 14), (40, 8, 6), heat), (60, 12, 40), sunset)
    midc = mix(mix((22, 14, 26), (90, 20, 8), heat), (230, 70, 30), sunset)
    bot = mix(mix((10, 8, 12), (30, 6, 4), heat), (255, 160, 60), sunset)
    sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)],
                                        [col(top), col(midc), col(bot)], [0, 0.6, 1])
    c.drawPaint(P(WHITE, 1, shader=sh))
    sa = (1 - heat * 0.7) * (1 - sunset)
    if sa > 0.02:
        for i in range(NST):
            tw = 0.55 + 0.45 * math.sin(t * (1.4 + STZ[i] * 2) + STP[i])
            c.drawCircle((STX[i] - t * 3 * STZ[i]) % W, STY[i], 0.7 + 2 * STZ[i],
                         P(WHITE, sa * (0.2 + 0.7 * STZ[i]) * tw))
    # brasas / ceniza flotando
    rnd = random.Random(2)
    for i in range(70):
        x = (rnd.random() * W + math.sin(t * 0.6 + i) * 30) % W
        y = (rnd.random() * H - t * (20 + rnd.random() * 50)) % H
        cc = mix(ASH, ORANGE, heat)
        c.drawCircle(x, y, 1.5 + rnd.random() * 2.5, P(cc, 0.15 + 0.35 * heat))


def volcano(c, cx, base_y, s, a, erupt, t):
    """silueta de volcan con erupcion (erupt 0..1)."""
    if a <= 0:
        return
    # columna de ceniza
    if erupt > 0:
        rnd = random.Random(11)
        for i in range(70):
            ph = (rnd.random() + t * (0.15 + rnd.random() * 0.15)) % 1.0
            h = ph * 1200 * erupt
            x = cx + (rnd.random() - 0.5) * (80 + h * 0.9) + math.sin(t + i) * 20
            y = base_y - s * 0.95 - h
            r = 40 + h * 0.22 + rnd.random() * 40
            cc = mix(mix(LAVA, ASH, clamp(ph * 2.5)), (40, 36, 36), clamp(ph))
            c.drawCircle(x, y, r, P(cc, a * erupt * (0.55 - 0.45 * ph), blur=r * 0.35))
        # lava proyectada
        for i in range(40):
            ph = ((t * 0.9 + i * 0.137) % 1.0)
            ang = -math.pi / 2 + (rnd.random() - 0.5) * 1.4
            v = 900 + rnd.random() * 500
            x = cx + math.cos(ang) * v * ph
            y = base_y - s * 0.95 + math.sin(ang) * v * ph + 900 * ph * ph
            c.drawCircle(x, y, 7, P(GOLD, a * erupt * (1 - ph)))
            c.drawCircle(x, y, 18, P(LAVA, a * erupt * (1 - ph) * 0.5, blur=10))
        c.drawCircle(cx, base_y - s * 0.95, s * 0.5, P(LAVA, a * erupt * 0.6, blur=s * 0.3))
    pth = skia.Path()
    pth.moveTo(cx - s * 1.6, base_y)
    pth.cubicTo(cx - s * 0.9, base_y - s * 0.3, cx - s * 0.35, base_y - s * 0.8, cx - s * 0.18, base_y - s * 0.95)
    pth.lineTo(cx + s * 0.18, base_y - s * 0.95)
    pth.cubicTo(cx + s * 0.35, base_y - s * 0.8, cx + s * 0.9, base_y - s * 0.3, cx + s * 1.6, base_y)
    pth.close()
    sh = skia.GradientShader.MakeLinear([skia.Point(cx, base_y - s), skia.Point(cx, base_y)],
                                        [col((70, 40, 36), a), col((18, 12, 12), a)])
    c.drawPath(pth, P(WHITE, 1, shader=sh))
    if erupt > 0:
        # rios de lava
        for k in (-1, 1):
            lp = skia.Path()
            lp.moveTo(cx + k * s * 0.1, base_y - s * 0.93)
            lp.cubicTo(cx + k * s * 0.3, base_y - s * 0.6, cx + k * s * 0.25, base_y - s * 0.4,
                       cx + k * s * 0.55, base_y - s * 0.1 * erupt)
            c.drawPath(lp, P(LAVA, a * erupt * 0.6, stroke=14, blur=8))
            c.drawPath(lp, P(GOLD, a * erupt, stroke=5))
    # mar
    c.drawRect(skia.Rect.MakeLTRB(0, base_y, W, H), P((6, 14, 26), a))
    for i in range(8):
        y = base_y + 20 + i * 26
        p = P(mix(CYAN, LAVA, erupt * 0.6), a * 0.12, stroke=2)
        p.setPathEffect(skia.DashPathEffect.Make([40 + i * 8, 30], -t * 30 * (1 + i * 0.2)))
        c.drawLine(0, y, W, y, p)


def sound_rings(c, cx, cy, t, t0, color, a, n=6, maxr=900, speed=0.5):
    if t < t0:
        return
    for j in range(n):
        ph = ((t - t0) * speed + j / n) % 1.0
        c.drawCircle(cx, cy, 30 + ph * maxr, P(color, a * (1 - ph) * 0.7, stroke=6 * (1 - ph) + 1))


# ---------------------------------------------------------------- escenas
def sc_hook(c, t):
    k = back((t - T["cual"]) / 0.6)
    a = clamp(k)
    sz = clamp(k, 0, 1.1)
    text(c, "¿EL SONIDO", W / 2, 420, int(96 * sz), WHITE, a, "black", glow=12)
    text(c, "MÁS FUERTE", W / 2, 540, int(110 * sz), GOLD, a, "black", glow=18)
    text(c, "DE LA HISTORIA?", W / 2, 650, int(80 * sz), WHITE, a, "black", glow=12)
    # ecualizador/forma de onda
    cy = 1000
    amp = 0.25 + 0.75 * fwin(t, T["sonido"], T["bomba"], 0.4)
    for i in range(40):
        x = 120 + i * 21.5
        h = (30 + 220 * abs(math.sin(t * 7 + i * 0.6) * math.sin(i * 0.31 + t * 2.1))) * amp * a
        rrect(c, x - 6, cy - h / 2, 12, h, 6, P(mix(CYAN, GOLD, i / 40), a * 0.9))
    # no fue una bomba
    if t > T["bomba"] - 0.1:
        kb = fin(t, T["bomba"], 0.35)
        bx, by = W / 2 - 220, 1330
        c.drawCircle(bx, by, 80, P((40, 40, 50), kb))
        c.drawCircle(bx, by, 80, P(MUTED, kb, stroke=4))
        c.drawLine(bx + 50, by - 60, bx + 80, by - 100, P(MUTED, kb, stroke=8))
        c.drawCircle(bx + 86, by - 108, 10, P(GOLD, kb * (0.6 + 0.4 * math.sin(t * 30))))
        cross_icon(c, bx, by, 190, RED, kb, eout((t - T["bomba"] - 0.4) / 0.4))
        text(c, "BOMBA", bx, by + 150, 44, MUTED, kb, "black", spacing=3)
    if t > T["volcan"] - 0.1:
        kv = back((t - T["volcan"]) / 0.5)
        a2 = clamp(kv)
        c.save()
        c.translate(W / 2 + 220, 1420)
        sc = clamp(kv, 0, 1.15)
        c.scale(sc, sc)
        pth = skia.Path()
        pth.moveTo(-140, 0)
        pth.lineTo(-30, -160)
        pth.lineTo(30, -160)
        pth.lineTo(140, 0)
        pth.close()
        c.drawPath(pth, P((90, 50, 40), a2))
        c.drawCircle(0, -175, 40, P(LAVA, a2, blur=18))
        c.drawCircle(-10, -230, 34, P(ASH, a2 * 0.8, blur=10))
        c.drawCircle(20, -270, 44, P(ASH, a2 * 0.6, blur=12))
        c.restore()
        text(c, "VOLCÁN", W / 2 + 220, 1480, 52, ORANGE, a2, "black", spacing=3, glow=8)


def sc_eruption(c, t):
    erupt = ein((t - T["explota"] + 0.1) / 0.5)
    volcano(c, W / 2, 1450, 330, fin(t, T["fecha"], 0.6), clamp(erupt), t)
    kd = fin(t, T["fecha"], 0.5) * (1 - 0.5 * clamp(erupt))
    text(c, "27 AGOSTO", W / 2, 360, 80, WHITE, kd, "black", spacing=4)
    text(c, "1883", W / 2, 520, 170, GOLD, kd, "black", glow=20)
    text(c, "INDONESIA", W / 2, 600, 44, MUTED, fin(t, T["indonesia"], 0.4) * kd, "black", spacing=10)
    if t > T["explota"] - 0.1:
        ke = back((t - T["explota"]) / 0.45)
        text(c, "KRAKATOA", W / 2, 760, int(130 * clamp(ke, 0, 1.15)), LAVA, clamp(ke), "black", glow=26,
             outline=10)


def sc_distance(c, t):
    # mapa abstracto: punto Krakatoa y anillos de sonido
    cx, cy = 300, 820
    c.drawCircle(cx, cy, 16, P(LAVA, 1))
    c.drawCircle(cx, cy, 40, P(LAVA, 0.5, blur=20))
    text(c, "KRAKATOA", cx, cy + 70, 34, LAVA, 1, "black", spacing=3)
    R = 640 * eout((t - T["estruendo"]) / 2.4)
    c.drawCircle(cx, cy, R, P(GOLD, 0.08))
    c.drawCircle(cx, cy, R, P(GOLD, 0.8, stroke=5))
    sound_rings(c, cx, cy, t, T["estruendo"], ORANGE, 0.8, n=5, maxr=R, speed=0.7)
    kc = back((t - T["cinco"]) / 0.5)
    text(c, "4.800 km", W / 2, 360, int(140 * clamp(kc, 0, 1.12)), GOLD, clamp(kc), "black", glow=18)
    text(c, "y aún se escuchaba", W / 2, 440, 44, WHITE, fin(t, T["cinco"] + 0.5, 0.4), "semi")
    # comparacion CDMX -> Lima
    if t > T["mexico"] - 0.1:
        km = fin(t, T["mexico"], 0.4)
        y = 1340
        x0, x1 = 120, 960
        rrect(c, x0 - 20, y - 130, x1 - x0 + 40, 300, 30, P((20, 12, 14), km * 0.88))
        # barra Krakatoa 4800
        c.drawLine(x0 + 20, y - 40, lerp(x0 + 20, x1 - 20, eout((t - T["mexico"]) / 0.8)), y - 40,
                   P(GOLD, km, stroke=16))
        text(c, "Krakatoa  4.800 km", x0 + 20, y - 70, 34, GOLD, km, "black", align="l")
        # barra CDMX-Lima 4230
        kl = fin(t, T["lima"] - 0.6, 0.4)
        L = (x1 - x0 - 40) * 4230 / 4800
        c.drawLine(x0 + 20, y + 80, lerp(x0 + 20, x0 + 20 + L, eout((t - T["lima"] + 0.6) / 0.8)), y + 80,
                   P(CYAN, kl, stroke=16))
        text(c, "Ciudad de México → Lima  4.230 km", x0 + 20, y + 50, 32, CYAN, kl, "black", align="l")


def boat(c, x, y, s, a, t):
    rock = math.sin(t * 2) * 4
    c.save()
    c.translate(x, y)
    c.rotate(rock)
    hull = skia.Path()
    hull.moveTo(-s, 0)
    hull.lineTo(s, 0)
    hull.lineTo(s * 0.75, s * 0.32)
    hull.lineTo(-s * 0.8, s * 0.32)
    hull.close()
    c.drawPath(hull, P((60, 40, 30), a))
    c.drawLine(0, 0, 0, -s * 1.2, P((70, 50, 40), a, stroke=6))
    sail = skia.Path()
    sail.moveTo(6, -s * 1.15)
    sail.lineTo(s * 0.65, -s * 0.15)
    sail.lineTo(6, -s * 0.15)
    sail.close()
    c.drawPath(sail, P((220, 210, 190), a))
    c.restore()


def sc_island(c, t):
    k = fin(t, T["isla"], 0.5)
    text(c, "OCÉANO ÍNDICO", W / 2, 360, 70, CYAN, k, "black", spacing=4, glow=8)
    text(c, "una isla a 4.800 km", W / 2, 440, 42, MUTED, k, "semi")
    # isla + palmera
    iy = 1150
    c.drawOval(skia.Rect.MakeXYWH(150, iy - 40, 420, 90), P((200, 170, 110), k))
    c.drawRect(skia.Rect.MakeLTRB(0, iy + 10, W, H), P((8, 24, 44), k))
    tr = skia.Path()
    tr.moveTo(330, iy - 20)
    tr.quadTo(320, iy - 160, 360, iy - 250)
    c.drawPath(tr, P((80, 55, 30), k, stroke=12))
    for ang in (-150, -110, -60, -20, 20):
        r = math.radians(ang)
        c.drawLine(360, iy - 250, 360 + math.cos(r) * 110, iy - 250 + math.sin(r) * 60 + 40,
                   P((40, 140, 70), k, stroke=10))
    # personas
    for i, x in enumerate((240, 420, 480)):
        c.drawCircle(x, iy - 85, 14, P((20, 18, 22), k))
        rrect(c, x - 14, iy - 70, 28, 60, 10, P((20, 18, 22), k))
    # barco a lo lejos + destellos de cañón
    bx = 820
    boat(c, bx, iy - 30, 90, k, t)
    if t > T["canon"] - 0.2:
        for j, t0 in enumerate((T["canon"], T["canon"] + 0.7, T["barco"] + 0.3)):
            if t0 <= t < t0 + 0.5:
                fl = 1 - (t - t0) / 0.5
                c.drawCircle(bx - 120, iy - 50, 60 * fl + 10, P(GOLD, fl, blur=20))
        kq = back((t - T["canon"]) / 0.45)
        text(c, "¿CAÑONAZOS?", W / 2, 760, int(100 * clamp(kq, 0, 1.12)), GOLD, clamp(kq), "black", glow=16)
    sound_rings(c, W + 400, 300, t, T["isla"], ORANGE, 0.5 * k, n=4, maxr=1300, speed=0.35)


def ear(c, x, y, s, a, broken):
    pth = skia.Path()
    pth.moveTo(x - s * 0.1, y + s * 0.6)
    pth.cubicTo(x - s * 0.6, y + s * 0.5, x - s * 0.7, y - s * 0.6, x, y - s * 0.7)
    pth.cubicTo(x + s * 0.65, y - s * 0.75, x + s * 0.7, y + s * 0.1, x + s * 0.2, y + s * 0.3)
    pth.cubicTo(x, y + s * 0.4, x + s * 0.1, y + s * 0.65, x - s * 0.1, y + s * 0.6)
    colr = mix((240, 190, 170), RED, broken)
    c.drawPath(pth, P(colr, a * 0.25))
    c.drawPath(pth, P(colr, a, stroke=10))
    inner = skia.Path()
    inner.moveTo(x - s * 0.1, y + s * 0.25)
    inner.cubicTo(x - s * 0.35, y, x - s * 0.2, y - s * 0.4, x + s * 0.1, y - s * 0.35)
    inner.cubicTo(x + s * 0.35, y - s * 0.3, x + s * 0.3, y, x + s * 0.05, y + s * 0.05)
    c.drawPath(inner, P(colr, a, stroke=7))
    if broken > 0:
        rnd = random.Random(4)
        for i in range(6):
            ang = rnd.random() * 6.28
            L = s * (0.4 + rnd.random() * 0.5) * broken
            c.drawLine(x, y, x + math.cos(ang) * L, y + math.sin(ang) * L, P(WHITE, a * broken, stroke=3))


def sc_meter(c, t):
    k = fin(t, T["ciento"], 0.5)
    text(c, "A 160 km DEL VOLCÁN", W / 2, 360, 60, WHITE, k, "black", spacing=2)
    # medidor vertical de decibeles
    x, y0, y1 = 230, 1450, 520
    rrect(c, x - 45, y1 - 20, 90, y0 - y1 + 40, 45, P((20, 16, 20), k * 0.9))
    sh = skia.GradientShader.MakeLinear([skia.Point(0, y0), skia.Point(0, y1)],
                                        [col(GREEN, k), col(GOLD, k), col(RED, k)], [0, 0.55, 1])
    db = 0.0
    if t > T["medidores"]:
        db = 172 * eout((t - T["medidores"]) / 1.6)

    def ypos(v):
        return y0 - (y0 - y1) * v / 200

    rrect(c, x - 30, ypos(db), 60, y0 - ypos(db), 30, P(WHITE, 1, shader=sh))
    for v in (0, 50, 100, 150, 200):
        c.drawLine(x + 55, ypos(v), x + 80, ypos(v), P(MUTED, k * 0.7, stroke=3))
        text(c, str(v), x + 95, ypos(v) + 12, 30, MUTED, k * 0.7, "semi", align="l")
    text(c, "dB", x, y0 + 70, 40, MUTED, k, "black")
    # marcas
    kr = fin(t, T["rock"], 0.4)
    if kr > 0:
        yy = ypos(120)
        c.drawLine(x + 40, yy, 620, yy, P(CYAN, kr * 0.8, stroke=3))
        text(c, "120 dB", 640, yy + 14, 44, CYAN, kr, "black", align="l")
        text(c, "concierto de rock", 640, yy + 62, 34, MUTED, kr, "semi", align="l")
    kk = back((t - T["decibeles"]) / 0.5)
    if t > T["decibeles"] - 0.1:
        yy = ypos(172)
        c.drawLine(x + 40, yy, 620, yy, P(RED, clamp(kk), stroke=4))
        text(c, "+170 dB", 640, yy + 26, int(78 * clamp(kk, 0, 1.12)), RED, clamp(kk), "black", glow=14,
             align="l")
        text(c, "Krakatoa", 640, yy + 78, 36, ORANGE, clamp(kk), "black", align="l")
    # oido / timpanos
    if t > T["barco2"] - 0.2:
        ko = fin(t, T["barco2"], 0.4)
        broken = eout((t - T["timpanos"]) / 0.5) if t > T["timpanos"] else 0
        jit = math.sin(t * 60) * 6 * broken * (1 - clamp((t - T["timpanos"]) / 1.5))
        ear(c, 760 + jit, 1260, 190, ko, broken)
        text(c, "TÍMPANOS ROTOS", 760, 1540, 46, RED, broken, "black", glow=10)


def sc_globe(c, t):
    k = fin(t, T["pero"], 0.5)
    text(c, "LA ONDA DE PRESIÓN", W / 2, 360, 64, WHITE, fin(t, T["onda"], 0.4), "black", spacing=2)
    text(c, "DIO LA VUELTA AL PLANETA", W / 2, 440, 50, ORANGE, fin(t, T["vuelta"], 0.4), "black", glow=8)
    ex, ey, er = W / 2, 960, 320
    draw_earth(c, ex, ey, er, k, t * 3)
    # frente de onda que recorre el globo (circulo que crece y decrece = vuelta)
    if t > T["onda"]:
        laps = (t - T["onda"]) / 2.8
        ph = laps % 1.0
        # proyeccion: anillo que se abre desde el punto y se cierra en el antipoda
        rr = er * math.sin(ph * math.pi)
        oy = ey - er * math.cos(ph * math.pi) * 0.0
        c.save()
        clip = skia.Path()
        clip.addCircle(ex, ey, er)
        c.clipPath(clip, skia.ClipOp.kIntersect, True)
        c.drawOval(skia.Rect.MakeLTRB(ex - rr, oy - rr * 0.35 - er * math.cos(ph * math.pi) * 0.9,
                                      ex + rr, oy + rr * 0.35 - er * math.cos(ph * math.pi) * 0.9),
                   P(ORANGE, 0.9, stroke=8))
        c.restore()
        n = int(laps) + 1
        kv = fin(t, T["novez"], 0.3)
        text(c, f"VUELTA {min(n, 4)}", W / 2, 560, 62, GOLD, kv, "black", glow=10)
    # barometro: grafica con picos
    if t > T["cinco_dias"] - 0.2:
        kb = fin(t, T["cinco_dias"], 0.4)
        y = 1440
        x0, x1 = 110, 970
        rrect(c, x0 - 20, y - 110, x1 - x0 + 40, 190, 26, P((14, 10, 14), kb * 0.9))
        prog = clamp((t - T["cinco_dias"]) / 3.0)
        pth = skia.Path()
        pth.moveTo(x0, y)
        n = 260
        for i in range(1, int(n * prog) + 1):
            u = i / n
            x = lerp(x0, x1, u)
            v = 0
            for p in range(7):
                pc = 0.06 + p * 0.135
                v += math.exp(-((u - pc) / 0.01) ** 2) * (1 - p * 0.11) * (1 if p % 2 == 0 else -0.8)
            pth.lineTo(x, y - v * 70 + math.sin(u * 90) * 2)
        c.drawPath(pth, P(ORANGE, kb, stroke=4))
        for d in range(6):
            xx = lerp(x0, x1, d / 5)
            text(c, f"día {d}" if d else "", xx, y + 60, 26, MUTED, kb, "semi")
        text(c, "BARÓMETROS DE TODO EL MUNDO", W / 2, y - 70, 32, WHITE, kb, "black", spacing=2)


def sc_sunset(c, t):
    k = fin(t, T["cenizas"], 0.8)
    # sol poniente
    sy = lerp(900, 1180, ease((t - T["cenizas"]) / 6))
    g = skia.GradientShader.MakeRadial(skia.Point(W / 2, sy), 520, [col((255, 200, 120), 0.9 * k),
                                                                     col((255, 80, 40), 0)])
    c.drawCircle(W / 2, sy, 520, P(WHITE, 1, shader=g))
    c.drawCircle(W / 2, sy, 150, P((255, 220, 160), k))
    # horizonte y mar
    c.drawRect(skia.Rect.MakeLTRB(0, 1250, W, H), P((30, 8, 20), k))
    for i in range(10):
        y = 1270 + i * 30
        w = 300 - i * 20
        c.drawLine(W / 2 - w, y, W / 2 + w, y, P((255, 140, 80), k * (0.5 - i * 0.04), stroke=5))
    # capas de ceniza
    rnd = random.Random(8)
    for i in range(14):
        y = 500 + i * 50
        x = (rnd.random() * W + t * (10 + i * 3)) % (W + 600) - 300
        c.drawOval(skia.Rect.MakeXYWH(x, y, 600, 40), P((80, 30, 40), k * 0.35, blur=18))
    kt = back((t - T["rojo"]) / 0.5)
    text(c, "CIELOS ROJOS", W / 2, 400, int(110 * clamp(kt, 0, 1.12)), (255, 90, 70), clamp(kt), "black", glow=18)
    text(c, "en todo el mundo · durante meses", W / 2, 480, 42, WHITE, fin(t, T["meses"], 0.4), "semi")


def sc_ending(c, t):
    k = fin(t, T["asi"], 0.6)
    ex, ey, er = W / 2, 980, 250
    draw_earth(c, ex, ey, er, k, t * 2)
    sound_rings(c, ex, ey, t, T["hubo"], ORANGE, k, n=6, maxr=900, speed=0.45)
    kp = back((t - T["planeta"]) / 0.5)
    text(c, "TODO EL PLANETA", W / 2, 470, int(84 * clamp(kp, 0, 1.12)), WHITE, clamp(kp), "black", glow=10)
    text(c, "SINTIÓ", W / 2, 570, int(70 * clamp(kp, 0, 1.12)), MUTED, clamp(kp), "black")
    ks = back((t - T["solo"]) / 0.55)
    text(c, "UN SOLO", W / 2, 1400, int(100 * clamp(ks, 0, 1.12)), GOLD, clamp(ks), "black", glow=14)
    text(c, "SONIDO", W / 2, 1530, int(150 * clamp(ks, 0, 1.12)), GOLD, clamp(ks), "black", glow=26)


SCENE_FN = {"hook": sc_hook, "eruption": sc_eruption, "distance": sc_distance, "island": sc_island,
            "meter": sc_meter, "globe": sc_globe, "sunset": sc_sunset, "ending": sc_ending}


# ---------------------------------------------------------------- hud / post
def hud(c, t):
    k = clamp(t / VOICE_END)
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W, 8), P(WHITE, 0.12))
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W * k, 8), P(ORANGE, 0.95))


SHAKES = [(T["explota"], 1.6, 26), (T["estruendo"], 0.5, 10), (T["decibeles"], 0.5, 12), (T["timpanos"], 0.7, 14),
          (T["solo"], 0.4, 8), (T["canon"], 0.25, 6)]
GLITCHES = [(T["explota"], 0.5, 0.9), (T["timpanos"], 0.5, 0.6)]


def shake(t):
    s = 0.0
    for t0, d, m in SHAKES:
        if t0 <= t < t0 + d:
            s = max(s, m * (1 - (t - t0) / d))
    return math.sin(t * 87) * s, math.cos(t * 71) * s


def post(arr, t):
    g = 0.0
    for t0, d, m in GLITCHES:
        if t0 <= t < t0 + d:
            g = max(g, m * (1 - (t - t0) / d))
    if g <= 0.02:
        return arr
    rnd = np.random.default_rng(int(t * 60))
    out = arr.copy()
    sh = int(16 * g)
    out[:, :, 0] = np.roll(arr[:, :, 0], sh, axis=1)
    out[:, :, 2] = np.roll(arr[:, :, 2], -sh, axis=1)
    for _ in range(int(8 * g)):
        y0 = rnd.integers(0, H - 80)
        hh = rnd.integers(8, 90)
        out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], int(rnd.integers(-50, 50) * g), axis=1)
    return out


def render(surface, t):
    c = surface.getCanvas()
    heat = fwin(t, T["explota"] - 0.1, T["isla"] - 0.25, 0.4)
    sunset = fwin(t, T["cenizas"], T["asi"] - 0.25, 0.8)
    c.save()
    background(c, t, heat, sunset)
    sx, sy = shake(t)
    c.translate(sx, sy)
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
    if T["explota"] <= t < T["explota"] + 0.35:
        c.drawPaint(P((255, 230, 200), 0.85 * (1 - (t - T["explota"]) / 0.35)))
    if t > END - 1.6:
        c.drawPaint(P((0, 0, 0), clamp((t - (END - 1.6)) / 1.4)))
    if t < 0.3:
        c.drawPaint(P((0, 0, 0), 1 - t / 0.3))
    arr = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return post(arr, t)


# ---------------------------------------------------------------- audio
def loudness(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    return float(m[-1])


def build_audio():
    out = os.path.join(HERE, "build", "mix.wav")
    voice = os.path.join(AUD, "voz.mp3")
    vI = loudness(voice)
    ev = [  # (archivo, inicio, LU relativo a la voz)
        ("sfx_riser.mp3", T["explota"] - 3.8, -14), ("sfx_volcano.mp3", T["explota"] - 0.05, -4),
        ("sfx_whoosh.mp3", T["estruendo"] - 0.5, -13), ("sfx_whoosh.mp3", T["isla"] - 0.5, -13),
        ("sfx_boom.mp3", T["canon"], -14), ("sfx_boom.mp3", T["canon"] + 0.7, -16),
        ("sfx_whoosh.mp3", T["ciento"] - 0.5, -13), ("sfx_beeps.mp3", T["medidores"], -16),
        ("sfx_boom.mp3", T["decibeles"], -11), ("sfx_ringing.mp3", T["timpanos"] + 0.1, -9),
        ("sfx_whoosh.mp3", T["pero"] - 0.5, -12), ("sfx_warp.mp3", T["onda"], -15),
        ("sfx_beeps.mp3", T["cinco_dias"], -17), ("sfx_whoosh.mp3", T["cenizas"] - 0.5, -13),
        ("sfx_whoosh.mp3", T["asi"] - 0.5, -13), ("sfx_boom.mp3", T["solo"] - 0.05, -10),
    ]
    files = sorted({f for f, _, _ in ev} | {"sfx_ambience.mp3"})
    LI = {f: loudness(os.path.join(AUD, f)) for f in files}
    inputs = ["-i", voice, "-stream_loop", "-1", "-i", os.path.join(AUD, "sfx_ambience.mp3")]
    for f, _, _ in ev:
        inputs += ["-i", os.path.join(AUD, f)]
    fl = [f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
          f"acompressor=threshold=-20dB:ratio=3:attack=5:release=120,apad=whole_dur={END}[v]",
          f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:{END},"
          f"volume={vI - 17 - LI['sfx_ambience.mp3']:.1f}dB,afade=t=in:d=1.0,afade=t=out:st={END - 3}:d=3[amb]"]
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
            print(f"{k:12s} {v:7.2f}")
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
