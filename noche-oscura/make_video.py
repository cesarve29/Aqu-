#!/usr/bin/env python3
"""
¿POR QUÉ LA NOCHE ES OSCURA? (la paradoja de Olbers)
Short vertical 9:16 (1080x1920) a 60 fps, generado 100% por codigo (skia + numpy + ffmpeg).
Reutiliza las utilidades de dibujo de ../viaje-tiempo/make_video.py.
Voz: ElevenLabs (1 toma). Efectos: reutilizados del video anterior (0 creditos).
Tiempos de cada escena anclados a frases de audio/words.json (ElevenLabs Scribe).

Uso:
    python3 make_video.py                 -> noche_oscura_9x16_60fps.mp4
    python3 make_video.py --stills 5 20   -> stills/*.png
    python3 make_video.py --audio         -> build/mix.wav
"""
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
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("vt_make_video", os.path.join(HERE, "..", "viaje-tiempo",
                                                                             "make_video.py"))
mv = importlib.util.module_from_spec(_spec)
sys.modules["vt_make_video"] = mv
_spec.loader.exec_module(mv)
from vt_make_video import (P, W, H, FPS, back, clamp, col, cross_icon, check_icon, ease, eout, ein,  # noqa: E402
                        fin, font, fwin, lerp, mix, rrect, text, vignette, person)

AUD = os.path.join(HERE, "audio")
OUT = os.path.join(HERE, "noche_oscura_9x16_60fps.mp4")

CYAN = (56, 225, 255)
BLUE = (70, 120, 255)
RED = (255, 59, 92)
ORANGE = (255, 140, 60)
GOLD = (255, 210, 63)
SUN = (255, 236, 170)
WHITE = (255, 255, 255)
MUTED = (150, 165, 200)
VIOLET = (160, 90, 255)
GREEN = (60, 230, 150)
SAND = (230, 196, 140)

# ---------------------------------------------------------------- tiempos desde la transcripcion
WORDS = [w for w in json.load(open(os.path.join(AUD, "words.json")))["words"] if w["type"] == "word"]


def _norm(s):
    return re.sub(r"[¿?¡!.,:;…\"]", "", s.lower())


def at(phrase, after=0.0):
    """inicio (s) de la primera aparicion de 'phrase' despues de 'after'."""
    toks = _norm(phrase).split()
    ws = [w for w in WORDS if not w["text"].startswith("[")]
    for i in range(len(ws) - len(toks) + 1):
        if ws[i]["start"] < after:
            continue
        if all(_norm(ws[i + k]["text"]) == toks[k] for k in range(len(toks))):
            return ws[i]["start"]
    raise KeyError(phrase)


def end_of(phrase, after=0.0):
    toks = _norm(phrase).split()
    t0 = at(phrase, after)
    ws = [w for w in WORDS if not w["text"].startswith("[")]
    i = next(k for k, w in enumerate(ws) if w["start"] == t0)
    return ws[i + len(toks) - 1]["end"]


VOICE_END = WORDS[-1]["end"]
END = round(VOICE_END + 2.8, 2)

T = dict(
    mira=at("mira al cielo"),
    estrellas=at("hay más estrellas"),
    arena=at("granos de arena"),
    playas=at("todas las playas"),
    porque=at("por qué la noche"),
    oscura=at("es oscura"),
    parece=at("parece una pregunta"),
    atormentado=at("ha atormentado"),
    siglos=at("durante siglos"),
    olbers=at("paradoja de olbers"),
    piensalo=at("piénsalo así"),
    infinito=at("fuera infinito"),
    eterno=at("eterno y estuviera"),
    lleno=at("lleno de estrellas"),
    mirases=at("mirases donde mirases"),
    chocando=at("acabaría chocando"),
    bosque=at("como en un bosque"),
    tronco=at("siempre ves un tronco"),
    cielo=at("el cielo entero debería"),
    sol=at("superficie del sol"),
    dia=at("de día y de noche"),
    punto=at("sin un solo punto"),
    perono=at("pero no es así"),
    falla=at("algo falla"),
    respuesta=at("y la respuesta"),
    alucinante=at("es alucinante"),
    pista1=at("primera pista"),
    noeterno=at("no es eterno"),
    trece=at("tiene unos trece"),
    lejanas=at("estrellas más lejanas"),
    tiempo=at("no ha tenido tiempo"),
    curiosamente=at("y curiosamente"),
    escritor=at("sino un escritor"),
    poe=at("edgar allan poe"),
    pista2=at("segunda pista"),
    expande=at("se expande"),
    estira=at("estira la luz"),
    colores=at("hacia colores"),
    nopueden=at("no pueden ver"),
    aqui=at("y aquí viene"),
    sibrilla=at("el cielo sí brilla"),
    direcciones=at("en todas direcciones"),
    noverlo=at("solo que no podemos"),
    fondo=at("es el fondo cósmico"),
    resplandor=at("el resplandor del big bang"),
    llena=at("todavía llena"),
    ojos=at("si tus ojos"),
    encendido=at("estaría encendido"),
    asique=at("así que esta noche"),
    recuerda=at("recuerda"),
    nada=at("no estás viendo la nada"),
    prueba=at("estás viendo la prueba"),
    principio=at("tuvo un principio"),
)

SCENES = [
    ("hook", 0.0, T["parece"] - 0.25),
    ("olbers", T["parece"] - 0.25, T["piensalo"] - 0.3),
    ("rays", T["piensalo"] - 0.3, T["cielo"] - 0.2),
    ("bright", T["cielo"] - 0.2, T["perono"] - 0.05),
    ("fail", T["perono"] - 0.05, T["pista1"] - 0.3),
    ("age", T["pista1"] - 0.3, T["pista2"] - 0.3),
    ("expand", T["pista2"] - 0.3, T["aqui"] - 0.3),
    ("cmb", T["aqui"] - 0.3, T["asique"] - 0.3),
    ("ending", T["asique"] - 0.3, END),
]
XF = 0.3

CHAPTERS = [
    (T["parece"], T["perono"], "LA PARADOJA", GOLD),
    (T["pista1"], T["pista2"], "PISTA 1", CYAN),
    (T["pista2"], T["aqui"], "PISTA 2", RED),
    (T["aqui"], T["asique"], "EL GIRO FINAL", ORANGE),
]

# subtitulos solo en momentos clave (rangos por frase)
mv.AUD = AUD
mv.CAP_Y = 1660
mv.KEY_MOMENTS = [
    (at("pero ha atormentado") - 0.1, end_of("durante siglos") + 0.05),
    (T["mirases"] - 0.1, end_of("chocando con una estrella") + 0.05),
    (at("la luz de las estrellas") - 0.1, end_of("llegar hasta nosotros") + 0.05),
    (at("uno de los primeros") - 0.1, end_of("en intuirlo") + 0.05),
    (T["estira"] - 0.1, end_of("galaxias más lejanas") + 0.05),
    (T["noverlo"] - 0.1, end_of("no podemos verlo") + 0.05),
]
mv.EMPH = {"SIGLOS": GOLD, "INTUIRLO": GOLD, "ESTIRA": RED, "OSCURA": VIOLET, "ESTRELLA": GOLD, "FALLA": RED, "NOSOTROS": CYAN, "VERLO": ORANGE,
           "MICROONDAS": ORANGE, "ENCENDIDO": ORANGE, "LLEGAR": CYAN}

# ---------------------------------------------------------------- fondo
rng = np.random.default_rng(23)
NST = 520
STX = rng.random(NST) * W
STY = rng.random(NST) * H
STZ = rng.random(NST) ** 2.2 * 0.9 + 0.1
STP = rng.random(NST) * 6.28
STC = rng.random(NST)


def background(c, t, star_a=1.0, tint=(14, 22, 60)):
    sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)],
                                        [col((4, 6, 18)), col(mix((4, 6, 18), tint, 0.6)), col((2, 3, 10))],
                                        [0, 0.55, 1])
    c.drawPaint(P(WHITE, 1, shader=sh))
    # via lactea difusa
    for i, (nx, ny, nr, nc, na) in enumerate(((260, 520, 650, VIOLET, 0.13), (820, 1180, 720, BLUE, 0.12),
                                               (520, 1650, 520, CYAN, 0.07))):
        ox, oy = math.sin(t * 0.06 + i * 2) * 50, math.cos(t * 0.05 + i) * 40
        g = skia.GradientShader.MakeRadial(skia.Point(nx + ox, ny + oy), nr, [col(nc, na), col(nc, 0)])
        c.drawCircle(nx + ox, ny + oy, nr, P(WHITE, 1, shader=g))
    if star_a <= 0.01:
        return
    for i in range(NST):
        z = STZ[i]
        y = (STY[i] + t * 6 * z) % H
        x = (STX[i] - t * 3 * z) % W
        tw = 0.55 + 0.45 * math.sin(t * (1.3 + STC[i] * 2.5) + STP[i])
        r = 0.7 + 2.3 * z
        cc = mix(WHITE, mix(CYAN, GOLD, STC[i]), STC[i] * 0.45)
        c.drawCircle(x, y, r, P(cc, star_a * (0.2 + 0.8 * z) * tw))
        if z > 0.75:
            c.drawCircle(x, y, r * 3.5, P(cc, star_a * 0.18 * tw, blur=r * 2))


# ---------------------------------------------------------------- textura CMB (precalculada)
def _cmb_texture(seed=4, w=512, h=256):
    r = np.random.default_rng(seed)
    noise = r.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    k = np.sqrt(fx ** 2 + fy ** 2) + 1e-4
    spec = np.fft.fft2(noise) * (k ** -1.35) * np.exp(-(k / 0.09) ** 2)
    f = np.real(np.fft.ifft2(spec))
    f = (f - f.mean()) / f.std()
    f = np.clip(f / 2.6, -1, 1)
    # mapa de color tipo Planck: azul -> blanco/amarillo -> rojo
    stops = np.array([[-1, 20, 30, 140], [-0.45, 40, 110, 230], [0, 235, 240, 225], [0.45, 255, 150, 40],
                      [1, 200, 20, 20]], float)
    out = np.zeros((h, w, 4), np.uint8)
    for ch in range(3):
        out[:, :, ch] = np.interp(f, stops[:, 0], stops[:, ch + 1]).astype(np.uint8)
    out[:, :, 3] = 255
    return out


CMB_ARR = _cmb_texture()
_CMB_IMG = None


def cmb_image():
    global _CMB_IMG
    if _CMB_IMG is None:
        _CMB_IMG = skia.Image.fromarray(CMB_ARR, colorType=skia.kRGBA_8888_ColorType)
    return _CMB_IMG


def draw_cmb(c, rect, a, shift=0.0, oval=True):
    img = cmb_image()
    c.save()
    if oval:
        pth = skia.Path()
        pth.addOval(rect)
        c.clipPath(pth, skia.ClipOp.kIntersect, True)
    p = skia.Paint(AntiAlias=True)
    p.setAlphaf(clamp(a))
    sw = img.width()
    off = (shift * sw) % sw
    src1 = skia.Rect.MakeXYWH(off, 0, sw - off, img.height())
    frac = (sw - off) / sw
    dst1 = skia.Rect.MakeLTRB(rect.left(), rect.top(), rect.left() + rect.width() * frac, rect.bottom())
    c.drawImageRect(img, src1, dst1, skia.SamplingOptions(skia.FilterMode.kLinear), p)
    if off > 0:
        src2 = skia.Rect.MakeXYWH(0, 0, off, img.height())
        dst2 = skia.Rect.MakeLTRB(dst1.right(), rect.top(), rect.right(), rect.bottom())
        c.drawImageRect(img, src2, dst2, skia.SamplingOptions(skia.FilterMode.kLinear), p)
    c.restore()
    if oval:
        c.drawOval(rect, P(WHITE, a * 0.6, stroke=3))


# ---------------------------------------------------------------- escenas
def sc_hook(c, t):
    # titulo
    k = fin(t, 0.1, 0.7)
    text(c, "MIRA AL CIELO", W / 2, 360, 60, MUTED, k * (1 - fin(t, T["estrellas"], 0.4)), "bold", spacing=12)
    # granos de arena -> estrellas
    if t > T["estrellas"] - 0.2:
        ks = fin(t, T["estrellas"], 0.5)
        text(c, "MÁS ESTRELLAS", W / 2, 360, 92, WHITE, ks, "black", glow=14)
        text(c, "QUE GRANOS DE ARENA", W / 2, 460, 62, SAND, fin(t, T["arena"], 0.5), "black", spacing=2)
        text(c, "en todas las playas de la Tierra", W / 2, 530, 40, MUTED, fin(t, T["playas"], 0.5), "med")
        # arena cayendo que se convierte en estrellas al subir
        rnd = random.Random(9)
        kq = 1 - fin(t, T["porque"] - 0.3, 0.5)
        for i in range(260):
            x0 = W / 2 + (rnd.random() - 0.5) * 900
            sp = 0.35 + rnd.random() * 0.8
            ph = (rnd.random() + (t - T["estrellas"]) * sp * 0.22) % 1.0
            y = 1450 - ph * 820
            x = x0 + math.sin(ph * 6 + i) * 30
            sand_k = clamp((y - 900) / 500)
            cc = mix(GOLD, SAND, sand_k)
            r = lerp(3.4, 2.2, sand_k)
            a = ks * kq * clamp(ph * 5) * clamp((1 - ph) * 4)
            c.drawCircle(x, y, r, P(cc, a))
            if sand_k < 0.4:
                c.drawCircle(x, y, r * 4, P(GOLD, a * 0.25, blur=6))
        # duna
        dune = skia.Path()
        dune.moveTo(0, 1480)
        dune.cubicTo(300, 1420, 700, 1520, W, 1450)
        dune.lineTo(W, H)
        dune.lineTo(0, H)
        dune.close()
        sh = skia.GradientShader.MakeLinear([skia.Point(0, 1420), skia.Point(0, 1700)],
                                            [col(SAND, 0.55 * ks * kq), col((40, 30, 20), 0)])
        c.drawPath(dune, P(WHITE, 1, shader=sh))
    # pregunta
    if t > T["porque"] - 0.2:
        kq = back((t - T["porque"]) / 0.55)
        a = clamp(kq)
        sz = clamp(kq, 0, 1.12)
        text(c, "¿POR QUÉ", W / 2, 860, int(130 * sz), WHITE, a, "black", glow=16)
        text(c, "LA NOCHE", W / 2, 1000, int(130 * sz), WHITE, a, "black", glow=16)
        ko = back((t - T["oscura"]) / 0.5)
        text(c, "ES OSCURA?", W / 2, 1140, int(130 * clamp(ko, 0, 1.12)), VIOLET, clamp(ko), "black", glow=22)


def sc_olbers(c, t):
    k = back((t - T["olbers"]) / 0.6)
    text(c, "parece una pregunta de niño...", W / 2, 520, 46, MUTED,
         fin(t, T["parece"], 0.5) * (1 - fin(t, T["olbers"] - 0.2, 0.4)), "med")
    kq = back((t - T["parece"]) / 0.6) * (1 - fin(t, T["siglos"] - 0.4, 0.4))
    if kq > 0:
        bob = math.sin(t * 2.5) * 12
        text(c, "?", W / 2, 1000 + bob, int(380 * clamp(kq, 0, 1.1)), GOLD, clamp(kq), "black", glow=30)
    # siglos: linea de tiempo 1610 -> 1823
    kl = fin(t, T["siglos"] - 0.2, 0.6) * (1 - fin(t, T["olbers"] - 0.2, 0.4))
    if kl > 0:
        y = 900
        c.drawLine(160, y, lerp(160, 920, eout((t - T["siglos"]) / 1.0)), y, P(GOLD, kl * 0.8, stroke=6))
        for x, yr, who in ((200, "1610", "Kepler"), (540, "1720", "Halley"), (880, "1823", "Olbers")):
            kk = kl * fin(t, T["siglos"] + (x - 200) / 1400, 0.3)
            c.drawCircle(x, y, 14, P(GOLD, kk))
            text(c, yr, x, y - 50, 48, WHITE, kk, "black")
            text(c, who, x, y + 70, 34, MUTED, kk, "semi")
    if t > T["olbers"] - 0.1:
        a = clamp(k)
        sz = clamp(k, 0, 1.12)
        text(c, "LA PARADOJA", W / 2, 800, int(86 * sz), WHITE, a, "black", spacing=6)
        text(c, "DE OLBERS", W / 2, 940, int(150 * sz), GOLD, a, "black", glow=24)
        text(c, "Heinrich Olbers · 1823", W / 2, 1030, 40, MUTED, fin(t, T["olbers"] + 0.5, 0.5), "med")


def sc_rays(c, t):
    forest = fin(t, T["bosque"] - 0.1, 0.6)
    title = "SI EL UNIVERSO FUERA..."
    text(c, title, W / 2, 330, 54, WHITE, fin(t, T["piensalo"], 0.5) * (1 - forest), "black", spacing=2)
    # chips: infinito / eterno / lleno de estrellas
    for i, (lab, key) in enumerate((("INFINITO", "infinito"), ("ETERNO", "eterno"), ("LLENO DE ESTRELLAS", "lleno"))):
        kk = back((t - T[key]) / 0.45) if t > T[key] - 0.1 else 0
        a = clamp(kk) * (1 - forest)
        if a <= 0:
            continue
        widths = [260, 230, 420]
        xs = [190, 470, 800]
        y = 430 if i < 2 else 430
        if i == 2:
            xs[2], y = W / 2, 530
        bw = widths[i]
        rrect(c, xs[i] - bw / 2, y - 45, bw, 80, 40, P(GOLD, a * 0.15))
        rrect(c, xs[i] - bw / 2, y - 45, bw, 80, 40, P(GOLD, a, stroke=3))
        text(c, lab, xs[i], y + 10, 34, GOLD, a, "black", spacing=2)
    if forest > 0:
        text(c, "UN BOSQUE INFINITO", W / 2, 360, 66, GREEN, forest, "black", glow=10)
        text(c, "mires donde mires... siempre ves un tronco", W / 2, 440, 36, MUTED, fin(t, T["tronco"] - 0.6, 0.5),
             "med")
    # observador y rayos
    ox, oy = W / 2, 1350
    rnd = random.Random(42)
    objs = []
    for i in range(170):
        ang = rnd.random() * math.pi * 1.0 + math.pi
        d = 140 + (rnd.random() ** 0.6) * 900
        objs.append((ox + math.cos(ang) * d, oy + math.sin(ang) * d * 1.05, d, rnd.random()))
    kobj = 0.35 * fin(t, T["infinito"], 0.8) + 0.65 * fin(t, T["lleno"], 0.8)
    for x, y, d, s in objs:
        if y < 560 or y > oy - 40:
            continue
        a = kobj * clamp(1.3 - d / 1100)
        if forest > 0:
            # troncos (vista cenital)
            r = lerp(9, 22, s)
            c.drawCircle(x, y, r, P((90, 60, 35), a * forest))
            c.drawCircle(x, y, r, P(GREEN, a * forest * 0.7, stroke=3))
        if forest < 1:
            r = 2.5 + 4 * s
            c.drawCircle(x, y, r * 3, P(GOLD, a * (1 - forest) * 0.3, blur=6))
            c.drawCircle(x, y, r, P(SUN, a * (1 - forest)))
    # rayos de mirada: cada rayo termina en el objeto mas cercano que intersecta
    kr = fin(t, T["mirases"], 0.6)
    if kr > 0:
        n = 28
        for j in range(n):
            ang = math.pi + (j + 0.5) / n * math.pi
            dx, dy = math.cos(ang), math.sin(ang)
            hit = None
            for x, y, d, s in objs:
                if y < 560 or y > oy - 40:
                    continue
                vx, vy = x - ox, y - oy
                proj = vx * dx + vy * dy
                if proj <= 0:
                    continue
                perp = abs(vx * dy - vy * dx)
                rad = lerp(9, 22, s) if forest > 0.5 else 18
                if perp < rad and (hit is None or proj < hit):
                    hit = proj
            L = (hit if hit else 1000) * eout((t - T["mirases"] - j * 0.02) / 0.8)
            ex, ey = ox + dx * L, oy + dy * L
            colr = mix(CYAN, GREEN, forest)
            c.drawLine(ox, oy, ex, ey, P(colr, kr * 0.35, stroke=2.5))
            if hit and L >= hit * 0.98:
                c.drawCircle(ex, ey, 9, P(colr, kr * 0.8, blur=5))
        # ojo del observador
        c.drawCircle(ox, oy, 40, P((8, 12, 30), kr))
        c.drawCircle(ox, oy, 40, P(CYAN, kr, stroke=4))
        eye = skia.Path()
        eye.moveTo(ox - 26, oy)
        eye.quadTo(ox, oy - 22, ox + 26, oy)
        eye.quadTo(ox, oy + 22, ox - 26, oy)
        c.drawPath(eye, P(WHITE, kr, stroke=3))
        c.drawCircle(ox, oy, 8, P(CYAN, kr))
        text(c, "TÚ", ox, oy + 90, 36, CYAN, kr, "black", spacing=3)
    if t > T["chocando"]:
        kc = back((t - T["chocando"]) / 0.5) * (1 - forest)
        text(c, "¡SIEMPRE UNA ESTRELLA!", W / 2, 1545, int(56 * clamp(kc, 0, 1.1)), GOLD, clamp(kc), "black",
             glow=10)


def sc_bright(c, t):
    k = ein((t - T["cielo"]) / 2.2)
    # cielo blanco cegador
    sh = skia.GradientShader.MakeRadial(skia.Point(W / 2, H * 0.4), H * 0.9,
                                        [col(WHITE, k), col(SUN, k), col((255, 190, 90), k * 0.95)],
                                        [0, 0.5, 1])
    c.drawPaint(P(WHITE, 1, shader=sh))
    # estrellas que se funden en un solo brillo
    rnd = random.Random(5)
    for i in range(300):
        x, y = rnd.random() * W, rnd.random() * H
        r = 2 + rnd.random() * 4 + 30 * k * rnd.random()
        c.drawCircle(x, y, r, P(SUN, (1 - k) * 0.9 + 0.1, blur=r * 0.6))
    dark = mix(WHITE, (40, 20, 0), k)
    ks = back((t - T["sol"]) / 0.5)
    text(c, "BRILLANTE COMO", W / 2, 820, int(70 * clamp(ks, 0, 1.12)), dark, clamp(ks), "black", spacing=3)
    text(c, "EL SOL", W / 2, 990, int(190 * clamp(ks, 0, 1.12)), (200, 90, 0) if k > 0.5 else GOLD, clamp(ks),
         "black")
    text(c, "DE DÍA Y DE NOCHE", W / 2, 1110, 54, dark, fin(t, T["dia"], 0.4), "black", spacing=3)
    text(c, "sin un solo punto negro", W / 2, 1180, 42, mix(MUTED, (90, 50, 10), k), fin(t, T["punto"], 0.4),
         "semi")


def sc_fail(c, t):
    # vuelve la oscuridad de golpe
    k = back((t - T["perono"]) / 0.45)
    a = clamp(k)
    amt = max(0.0, 1 - (t - T["falla"]) / 0.7) if t > T["falla"] else 0
    text(c, "PERO NO", W / 2, 760, int(120 * clamp(k, 0, 1.12)), WHITE, a, "black", glow=14)
    if t > T["falla"] - 0.1:
        kf = back((t - T["falla"]) / 0.45)
        sz = int(130 * clamp(kf, 0, 1.15))
        if amt > 0:
            ox = math.sin(t * 91) * 16 * amt
            text(c, "ALGO FALLA", W / 2 - ox, 920, sz, (255, 0, 60), clamp(kf) * 0.7, "black")
            text(c, "ALGO FALLA", W / 2 + ox, 922, sz, (0, 220, 255), clamp(kf) * 0.7, "black")
        text(c, "ALGO FALLA", W / 2, 920, sz, RED, clamp(kf), "black", glow=20)
    if t > T["respuesta"] - 0.1:
        kr = fin(t, T["respuesta"], 0.5)
        text(c, "y la respuesta...", W / 2, 1100, 48, MUTED, kr, "med")
        ka = back((t - T["alucinante"]) / 0.5)
        text(c, "ES ALUCINANTE", W / 2, 1210, int(78 * clamp(ka, 0, 1.12)), GOLD, clamp(ka), "black", glow=14)


def sc_age(c, t):
    k = fin(t, T["pista1"], 0.5)
    text(c, "EL UNIVERSO", W / 2, 330, 58, WHITE, k, "black", spacing=4)
    text(c, "NO ES ETERNO", W / 2, 430, 86, CYAN, fin(t, T["noeterno"], 0.5), "black", glow=14)
    poe = fin(t, T["curiosamente"] - 0.1, 0.5)
    # horizonte de luz alrededor del observador
    ox, oy = W / 2, 1000
    R = 360 * eout((t - T["trece"]) / 1.8)
    kh = fin(t, T["trece"], 0.5) * (1 - poe * 0.75)
    rnd = random.Random(31)
    for i in range(260):
        ang = rnd.random() * 2 * math.pi
        d = 40 + rnd.random() ** 0.7 * 560
        x, y = ox + math.cos(ang) * d, oy + math.sin(ang) * d
        inside = d < R
        a = (0.95 if inside else 0.12) * fin(t, T["pista1"], 0.6) * (1 - poe * 0.75)
        cc = SUN if inside else MUTED
        c.drawCircle(x, y, 3.2 if inside else 2.2, P(cc, a))
        if inside:
            c.drawCircle(x, y, 9, P(GOLD, a * 0.3, blur=5))
    if kh > 0:
        g = skia.GradientShader.MakeRadial(skia.Point(ox, oy), max(R, 1), [col(CYAN, 0.0), col(CYAN, 0.10 * kh)])
        c.drawCircle(ox, oy, R, P(WHITE, 1, shader=g))
        c.drawCircle(ox, oy, R, P(CYAN, kh * 0.7, stroke=8, blur=8))
        c.drawCircle(ox, oy, R, P(CYAN, kh, stroke=3))
        c.drawCircle(ox, oy, 12, P(WHITE, kh))
        # pulsos de luz viajando hacia el centro desde fuera (no llegan)
        if t > T["lejanas"]:
            for j in range(10):
                ang = j / 10 * 2 * math.pi + 0.3
                ph = ((t - T["lejanas"]) * 0.35 + j * 0.13) % 1.0
                d = lerp(600, R + 20, ph)
                x, y = ox + math.cos(ang) * d, oy + math.sin(ang) * d
                c.drawCircle(x, y, 7, P(RED, kh * (1 - ph) * fin(t, T["lejanas"], 0.5)))
                c.drawLine(x, y, x + math.cos(ang) * 40, y + math.sin(ang) * 40,
                           P(RED, kh * (1 - ph) * 0.5, stroke=3))
    kn = back((t - T["trece"]) / 0.6)
    if t > T["trece"] - 0.1:
        a = clamp(kn) * (1 - poe)
        text(c, "13.800 MILLONES", W / 2, 1490, int(76 * clamp(kn, 0, 1.12)), WHITE, a, "black", glow=10)
        text(c, "DE AÑOS", W / 2, 1565, 50, CYAN, a, "black", spacing=6)
    # Edgar Allan Poe
    if poe > 0:
        y = 1010
        kp = back((t - T["poe"]) / 0.6) if t > T["poe"] - 0.1 else 0
        text(c, "NO FUE UN CIENTÍFICO...", W / 2, 760, 50, MUTED, poe, "black", spacing=2)
        text(c, "...SINO UN ESCRITOR", W / 2, 840, 58, GOLD, fin(t, T["escritor"], 0.4), "black", glow=8)
        a = clamp(kp)
        if a > 0:
            bw = 820
            rrect(c, W / 2 - bw / 2, y, bw, 300, 36, P((14, 12, 30), a * 0.92))
            rrect(c, W / 2 - bw / 2, y, bw, 300, 36, P(GOLD, a, stroke=4))
            # pluma
            px, py = W / 2 - 280, y + 150
            q = skia.Path()
            q.moveTo(px - 40, py + 70)
            q.cubicTo(px - 20, py - 10, px + 30, py - 70, px + 60, py - 90)
            q.cubicTo(px + 40, py - 30, px, py + 30, px - 40, py + 70)
            q.close()
            c.drawPath(q, P(GOLD, a))
            c.drawLine(px - 40, py + 70, px - 60, py + 95, P(GOLD, a, stroke=5))
            text(c, "EDGAR", W / 2 + 60, y + 105, 62, WHITE, a, "black")
            text(c, "ALLAN POE", W / 2 + 60, y + 180, 62, WHITE, a, "black")
            text(c, "«Eureka», 1848", W / 2 + 60, y + 245, 38, GOLD, a, "semi")


def wave_path(x0, x1, y, amp, wl, phase):
    p = skia.Path()
    n = 220
    for i in range(n + 1):
        x = lerp(x0, x1, i / n)
        yy = y + amp * math.sin((x - x0) / wl * 2 * math.pi + phase)
        if i == 0:
            p.moveTo(x, yy)
        else:
            p.lineTo(x, yy)
    return p


def sc_expand(c, t):
    k = fin(t, T["pista2"], 0.5)
    text(c, "EL UNIVERSO", W / 2, 330, 58, WHITE, k, "black", spacing=4)
    text(c, "SE EXPANDE", W / 2, 430, 92, RED, fin(t, T["expande"], 0.5), "black", glow=14)
    # galaxias alejandose
    rnd = random.Random(12)
    ke = fin(t, T["expande"], 0.6)
    s = 1 + 0.18 * (t - T["expande"]) if t > T["expande"] else 1
    for i in range(16):
        ang = rnd.random() * 2 * math.pi
        d = 80 + rnd.random() * 280
        x = W / 2 + math.cos(ang) * d * s
        y = 760 + math.sin(ang) * d * s * 0.55
        rr = 10 + rnd.random() * 14
        cc = mix(mix(BLUE, WHITE, 0.4), RED, clamp((s - 1) * 0.9))
        c.save()
        c.translate(x, y)
        c.rotate(rnd.random() * 180)
        c.drawOval(skia.Rect.MakeXYWH(-rr * 1.6, -rr * 0.6, rr * 3.2, rr * 1.2), P(cc, ke * 0.35, blur=rr * 0.5))
        c.drawOval(skia.Rect.MakeXYWH(-rr * 0.5, -rr * 0.25, rr, rr * 0.5), P(WHITE, ke * 0.9, blur=2))
        c.restore()
    # onda que se estira
    kw = fin(t, T["estira"], 0.5)
    stretch = ease((t - T["estira"]) / 3.2)
    wl = lerp(70, 300, stretch)
    wcol = mix(mix(BLUE, CYAN, 0.3), RED, clamp(stretch * 1.4))
    vis = 1 - clamp((stretch - 0.75) / 0.25) * 0.75
    if kw > 0:
        pth = wave_path(90, 990, 1120, 70, wl, -t * 6)
        c.drawPath(pth, P(wcol, kw * vis * 0.6, stroke=14, blur=10))
        c.drawPath(pth, P(wcol, kw * vis, stroke=6))
        text(c, "LUZ ESTIRADA", W / 2, 1000, 44, wcol, kw, "black", spacing=4)
    # espectro con rango visible del ojo
    kspec = fin(t, T["colores"], 0.5)
    if kspec > 0:
        y = 1330
        x0, x1 = 120, 960
        cols = [col((120, 0, 255), kspec), col((0, 90, 255), kspec), col((0, 220, 120), kspec),
                col((255, 230, 0), kspec), col((255, 60, 0), kspec), col((110, 0, 0), kspec),
                col((40, 0, 0), kspec)]
        pos = [0, 0.14, 0.3, 0.42, 0.56, 0.66, 1.0]
        sh = skia.GradientShader.MakeLinear([skia.Point(x0, y), skia.Point(x1, y)], cols, pos)
        rrect(c, x0, y, x1 - x0, 46, 23, P(WHITE, 1, shader=sh))
        vx0, vx1 = x0, x0 + (x1 - x0) * 0.62
        rrect(c, vx0 - 6, y - 12, vx1 - vx0 + 12, 70, 30, P(WHITE, kspec * 0.9, stroke=3))
        text(c, "LO QUE VEN TUS OJOS", (vx0 + vx1) / 2, y + 110, 32, WHITE, kspec, "black", spacing=2)
        text(c, "INFRARROJO", (vx1 + x1) / 2 + 10, y + 110, 32, RED, kspec, "black", spacing=2)
        # marcador que se desplaza a la derecha (corrimiento al rojo)
        mxp = lerp(x0 + 140, x1 - 40, ease((t - T["colores"]) / 2.2))
        c.drawCircle(mxp, y + 23, 18, P(WHITE, kspec))
        c.drawCircle(mxp, y + 23, 30, P(WHITE, kspec * 0.4, blur=10))
        if t > T["nopueden"]:
            kk = fin(t, T["nopueden"], 0.4)
            cross_icon(c, (vx1 + x1) / 2 + 10, y - 60, 70, RED, kk, eout((t - T["nopueden"]) / 0.4))


def sc_cmb(c, t):
    ks = back((t - T["sibrilla"]) / 0.5)
    text(c, "Y AQUÍ VIENE LO MÁS INCREÍBLE", W / 2, 330, 40, MUTED,
         fin(t, T["aqui"], 0.4) * (1 - fin(t, T["sibrilla"] - 0.1, 0.3)), "black", spacing=2)
    if t > T["sibrilla"] - 0.1:
        text(c, "EL CIELO SÍ BRILLA", W / 2, 360, int(84 * clamp(ks, 0, 1.12)), ORANGE, clamp(ks), "black", glow=16)
    # mapa CMB en elipse (proyeccion tipo Mollweide)
    reveal = fin(t, T["noverlo"] + 0.3, 1.0)
    full = ease((t - T["ojos"]) / 1.6)
    rw = lerp(940, W * 2.4, full)
    rh = lerp(470, H * 1.25, full)
    cy = lerp(900, H / 2, full)
    rect = skia.Rect.MakeXYWH(W / 2 - rw / 2, cy - rh / 2, rw, rh)
    # pulso de "señal invisible" antes de revelar
    if t > T["aqui"] and reveal < 1:
        for j in range(5):
            ph = ((t - T["aqui"]) * 0.6 + j / 5) % 1.0
            rr = 60 + ph * 520
            c.drawCircle(W / 2, 900, rr, P(ORANGE, (1 - ph) * 0.35 * (1 - reveal) * fin(t, T["aqui"], 0.6), stroke=4))
        text(c, "en todas direcciones", W / 2, 460, 42, WHITE, fin(t, T["direcciones"], 0.4) * (1 - reveal), "med")
    if reveal > 0:
        draw_cmb(c, rect, reveal, shift=t * 0.01, oval=full < 0.98)
        if full > 0:
            c.drawPaint(P((40, 10, 0), full * 0.25))
    kf = fin(t, T["fondo"], 0.5) * (1 - fin(t, T["ojos"] - 0.2, 0.4))
    if kf > 0:
        y = 1300
        bw = 900
        rrect(c, W / 2 - bw / 2, y - 80, bw, 230, 34, P((24, 10, 4), kf * 0.92))
        rrect(c, W / 2 - bw / 2, y - 80, bw, 230, 34, P(ORANGE, kf, stroke=4))
        text(c, "FONDO CÓSMICO", W / 2, y + 2, 64, WHITE, kf, "black")
        text(c, "DE MICROONDAS", W / 2, y + 72, 64, ORANGE, kf, "black", glow=8)
        text(c, "el resplandor del Big Bang · 2,7 K", W / 2, y + 128, 34, MUTED, fin(t, T["resplandor"], 0.4) * kf,
             "semi")
    if t > T["ojos"]:
        ke = back((t - T["encendido"]) / 0.5) if t > T["encendido"] - 0.1 else 0
        text(c, "SI TUS OJOS VIERAN", W / 2, 760, 60, WHITE, fin(t, T["ojos"], 0.4), "black", glow=10,
             outline=10)
        text(c, "MICROONDAS...", W / 2, 850, 76, ORANGE, fin(t, T["ojos"] + 0.8, 0.4), "black", glow=10, outline=10)
        text(c, "¡CIELO ENCENDIDO!", W / 2, 1120, int(88 * clamp(ke, 0, 1.12)), WHITE, clamp(ke), "black", glow=20,
             outline=12)


def sc_ending(c, t):
    k = fin(t, T["asique"], 0.6)
    # horizonte: silueta de colinas con una persona mirando el cielo
    hill = skia.Path()
    hill.moveTo(0, 1500)
    hill.cubicTo(300, 1430, 650, 1540, W, 1460)
    hill.lineTo(W, H)
    hill.lineTo(0, H)
    hill.close()
    c.drawPath(hill, P((2, 3, 8), k))
    person(c, W / 2 + 160, 1478, 120, (2, 3, 8), k)
    text(c, "cuando mires al cielo oscuro...", W / 2, 520, 44, MUTED,
         k * (1 - fin(t, T["nada"] - 0.2, 0.4)), "med")
    if t > T["nada"] - 0.1:
        kn = back((t - T["nada"]) / 0.5) * (1 - fin(t, T["prueba"] - 0.2, 0.4))
        text(c, "NO ESTÁS VIENDO", W / 2, 720, int(70 * clamp(kn, 0, 1.12)), WHITE, clamp(kn), "black")
        text(c, "LA NADA", W / 2, 860, int(120 * clamp(kn, 0, 1.12)), MUTED, clamp(kn), "black", glow=10)
    if t > T["prueba"] - 0.1:
        kp = back((t - T["prueba"]) / 0.5)
        a = clamp(kp)
        sz = clamp(kp, 0, 1.12)
        text(c, "ESTÁS VIENDO LA PRUEBA", W / 2, 660, int(62 * sz), WHITE, a, "black", glow=10)
        text(c, "DE QUE EL UNIVERSO", W / 2, 750, int(62 * sz), WHITE, fin(t, T["prueba"] + 0.6, 0.4), "black")
        kq = back((t - T["principio"]) / 0.6)
        text(c, "TUVO UN", W / 2, 900, int(90 * clamp(kq, 0, 1.12)), GOLD, clamp(kq), "black", glow=14)
        text(c, "PRINCIPIO", W / 2, 1040, int(140 * clamp(kq, 0, 1.12)), GOLD, clamp(kq), "black", glow=26)


SCENE_FN = {"hook": sc_hook, "olbers": sc_olbers, "rays": sc_rays, "bright": sc_bright, "fail": sc_fail,
            "age": sc_age, "expand": sc_expand, "cmb": sc_cmb, "ending": sc_ending}


# ---------------------------------------------------------------- hud / post
def hud(c, t):
    k = clamp(t / VOICE_END)
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W, 8), P(WHITE, 0.12))
    c.drawRect(skia.Rect.MakeXYWH(0, 0, W * k, 8), P(GOLD, 0.95))
    for t0, t1, lab, colr in CHAPTERS:
        if t0 - 0.2 <= t < t1:
            a = fwin(t, t0 + 0.05, t1, 0.35)
            f = font(30, "black")
            sp = 5
            wtxt = sum(f.measureText(ch) for ch in lab) + sp * (len(lab) - 1)
            bw = wtxt + 90
            x, y = W / 2 - bw / 2, 130
            rrect(c, x, y, bw, 62, 31, P(colr, a * 0.15))
            rrect(c, x, y, bw, 62, 31, P(colr, a * 0.9, stroke=2.5))
            c.drawCircle(x + 32, y + 31, 7, P(colr, a * (0.6 + 0.4 * math.sin(t * 5))))
            text(c, lab, W / 2 + 12, y + 42, 30, colr, a, "black", spacing=sp)


GLITCHES = [(T["perono"], 0.6, 1.0), (T["falla"], 0.6, 0.9), (T["sibrilla"], 0.35, 0.45)]
SHAKES = [(T["porque"], 0.35, 8), (T["oscura"], 0.4, 10), (T["olbers"], 0.4, 9), (T["perono"], 0.5, 16),
          (T["falla"], 0.5, 14), (T["sibrilla"], 0.4, 9), (T["encendido"], 0.4, 10), (T["principio"], 0.4, 8)]


def post(arr, t):
    g = 0.0
    for t0, d, m in GLITCHES:
        if t0 <= t < t0 + d:
            g = max(g, m * (1 - (t - t0) / d))
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
        out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], int(rnd.integers(-60, 60) * g), axis=1)
    return out


def shake(t):
    s = 0.0
    for t0, d, m in SHAKES:
        if t0 <= t < t0 + d:
            s = max(s, m * (1 - (t - t0) / d))
    return math.sin(t * 87) * s, math.cos(t * 71) * s


def render(surface, t):
    c = surface.getCanvas()
    c.save()
    in_bright = fwin(t, T["cielo"], T["perono"] - 0.05, 0.3)
    background(c, t, star_a=1.0 - in_bright)
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
    for t0 in (T["oscura"], T["perono"], T["encendido"]):
        if t0 <= t < t0 + 0.22:
            c.drawPaint(P(WHITE, 0.3 * (1 - (t - t0) / 0.22)))
    if t > END - 1.6:
        c.drawPaint(P((0, 0, 0), clamp((t - (END - 1.6)) / 1.4)))
    if t < 0.4:
        c.drawPaint(P((0, 0, 0), 1 - t / 0.4))
    arr = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return post(arr, t)


# ---------------------------------------------------------------- audio
SFX_I = {"sfx_boom.mp3": -10.1, "sfx_rewind.mp3": -7.4, "sfx_riser.mp3": -5.8, "sfx_warp.mp3": -10.0,
         "sfx_whoosh.mp3": -12.8, "sfx_beeps.mp3": -15.2, "sfx_clock.mp3": -19.9, "sfx_ambience.mp3": -9.8}
VOICE_I = -20.0


def g(f, rel):
    """ganancia (dB) para que el efecto quede 'rel' LU respecto a la voz."""
    return round(VOICE_I + rel - SFX_I[f], 1)


def build_audio():
    out = os.path.join(HERE, "build", "mix.wav")
    ev = [
        ("sfx_riser.mp3", T["porque"] - 3.6, -15), ("sfx_boom.mp3", T["oscura"] - 0.05, -10),
        ("sfx_whoosh.mp3", T["parece"] - 0.6, -12), ("sfx_boom.mp3", T["olbers"] - 0.05, -12),
        ("sfx_whoosh.mp3", T["piensalo"] - 0.6, -12), ("sfx_beeps.mp3", T["mirases"], -16),
        ("sfx_whoosh.mp3", T["bosque"] - 0.4, -14), ("sfx_riser.mp3", T["cielo"] - 0.3, -13),
        ("sfx_rewind.mp3", T["perono"] - 0.25, -12), ("sfx_boom.mp3", T["falla"] - 0.05, -10),
        ("sfx_whoosh.mp3", T["pista1"] - 0.6, -12), ("sfx_clock.mp3", T["trece"], -14),
        ("sfx_whoosh.mp3", T["curiosamente"] - 0.4, -14), ("sfx_whoosh.mp3", T["pista2"] - 0.6, -12),
        ("sfx_warp.mp3", T["expande"] - 0.2, -14), ("sfx_riser.mp3", T["sibrilla"] - 4.0, -14),
        ("sfx_boom.mp3", T["sibrilla"] - 0.05, -11), ("sfx_beeps.mp3", T["fondo"], -17),
        ("sfx_boom.mp3", T["encendido"] - 0.05, -10), ("sfx_whoosh.mp3", T["asique"] - 0.6, -13),
        ("sfx_boom.mp3", T["principio"] - 0.05, -12),
    ]
    voice = os.path.join(AUD, "voz.mp3")
    inputs = ["-i", voice, "-stream_loop", "-1", "-i", os.path.join(AUD, "sfx_ambience.mp3")]
    for f, _, _ in ev:
        inputs += ["-i", os.path.join(AUD, f)]
    fl = [f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
          f"acompressor=threshold=-20dB:ratio=3:attack=5:release=120,apad=whole_dur={END}[v]",
          f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,atrim=0:{END},volume={g('sfx_ambience.mp3', -16)}dB,"
          f"afade=t=in:d=1.5,afade=t=out:st={END - 3}:d=3[amb]"]
    labels = ["[v]", "[amb]"]
    for i, (f, st, rel) in enumerate(ev):
        ms = max(0, int(st * 1000))
        fl.append(f"[{i + 2}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,volume={g(f, rel)}dB,adelay={ms}|{ms}[s{i}]")
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
