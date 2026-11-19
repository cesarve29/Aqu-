#!/usr/bin/env python3
"""
JENGI & NIEVE en ¡LA NOCHE DEL KRAMPUS!
Corto animado estilo cartoon "rubber hose" de los años 30, generado 100% por código
(pycairo + numpy + ffmpeg). Voces, efectos y música: ElevenLabs (carpeta audio/).

Uso:
    python3 krampus.py preview            -> render/previa_1080p.mp4  (apertura ~63 s)
    python3 krampus.py full               -> render/krampus_1080p.mp4 (corto completo)
    python3 krampus.py stills 12.5 40 ... -> stills/*.png (frames sueltos para revisar)
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cairo
import numpy as np

import escenarios as E
from toon import (BLUSH, CREAM, FPS, FUR, GOLD, GREEN, H, INK, LIME, PRESENT_COLORS, RED, SNOW, W, WHITE, G,
                  Post, back_out, blob, circle, clamp, col, ease, ease_in, ease_out, elastic, film_dirt, glow,
                  golden_bell, iris, jengi, krampus, lerp, line, make_paper, mixc, nieve, nz, present,
                  set_time, soften_surface, sparkle, text, twos, u01, window)

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, 'audio')
OUT = os.path.join(HERE, 'render')


# ----------------------------------------------------------------------------
# caché de fondos pintados (por proceso)
# ----------------------------------------------------------------------------
_CACHE = {}
_PAPER = {}


def paper_arr():
    if 'a' not in _PAPER:
        _PAPER['a'] = make_paper(W + 2600, H + 400, seed=5)[1]
    return _PAPER['a']


def painted(key, w, h, draw, blur=1, passes=2, wash=0.0):
    """Dibuja una capa de fondo una vez, la 'pinta' (desenfoque + papel) y la guarda."""
    if key in _CACHE:
        return _CACHE[key]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    saved = (G.t, G.frame, G.boil)
    set_time(0.0, 0)
    G.bg = True
    draw(ctx)
    G.bg = False
    G.t, G.frame, G.boil = saved
    surf.flush()
    out = soften_surface(surf, blur, passes, paper=paper_arr(), wash=wash)
    _CACHE[key] = out
    return out


def blit(ctx, surf, x=0.0, y=0.0, a=1.0):
    ctx.set_source_surface(surf, x, y)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    if a >= 1:
        ctx.paint()
    else:
        ctx.paint_with_alpha(a)


def cam(ctx, cx, cy, z=1.0, shake=0.0):
    sx = shake * nz(G.frame * 1.3, 21) * 14
    sy = shake * nz(G.frame * 1.7, 22) * 14
    ctx.translate(W / 2 + sx, H / 2 + sy)
    ctx.scale(z, z)
    ctx.translate(-cx, -cy)


def silhouette(ctx, draw, color, amt):
    ctx.push_group()
    draw()
    if amt > 0:
        ctx.set_operator(cairo.OPERATOR_ATOP)
        col(ctx, color, amt)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)
    ctx.pop_group_to_source()
    ctx.paint()


def speed_lines(ctx, x, y, n, length, a=1.0, seed=0.0):
    for i in range(n):
        yy = y + (i - n / 2) * 22 + nz(i + G.frame, seed) * 6
        ln = length * (0.6 + 0.4 * u01(i + G.frame, seed + 1))
        line(ctx, [(x - ln, yy), (x, yy)], 5, INK, a * 0.7, smooth=False)


def dust_puff(ctx, x, y, age, s=1.0, seed=0.0):
    """Nube de polvo/nieve en forma de cúpula que se expande y se desvanece."""
    if age < 0 or age > 1.0:
        return
    u = age / 1.0
    for k in range(7):
        a = math.pi + (k + 0.5) / 7 * math.pi
        d = (30 + 90 * ease_out(u)) * s
        r = (26 + 22 * u01(k, seed)) * s * (1.0 - 0.45 * u)
        blob(ctx, x + math.cos(a) * d * 1.3, y - 10 * s + math.sin(a) * d * 0.8, r, r * 0.9,
             (0.96, 0.95, 0.99), 3, seed=seed + k, a=(1 - u) * 0.95)


# ----------------------------------------------------------------------------
# capas pintadas reutilizables
# ----------------------------------------------------------------------------
PAD_X, PAD_Y = 450, 260


def sky_layer(green):
    def d(ctx):
        ctx.translate(PAD_X, PAD_Y)
        E.sky(ctx, 0, green, moon=None, stars=False)
    return painted(('sky', green), W + 2 * PAD_X, H + 2 * PAD_Y, d, blur=3, passes=2)


def far_layer():
    """Colinas lejanas con pinos y la Montaña Negra (panorama ancho)."""
    PW = W + 1400

    def d(ctx):
        E.black_mountain(ctx, PW - 520, 640, 0.9, 0, 0.7)
        ctx.save()
        E.hills(ctx, 0, 690, 120, (0.78, 0.80, 0.92), 7, lw=5, pines=0.5, pine_h=70, pine_c=(0.30, 0.42, 0.50),
                period=1100)
        ctx.restore()
    return painted('far', PW, H, d, blur=3, passes=2, wash=0.2)


def town_layer():
    PW = W + 1800

    def d(ctx):
        ctx.save()
        ctx.translate(0, 0)
        E.hills(ctx, 0, 840, 50, (0.86, 0.88, 0.96), 9, lw=5, pines=0, period=1500)
        E.village(ctx, 0, 840, 0, s=0.8, beat_amp=0, seed=3)
        ctx.restore()
    return painted('town', PW, H, d, blur=2, passes=1)


def near_layer():
    PW = W + 2400

    def d(ctx):
        E.snow_ground(ctx, 960, 0)
        for k in range(14):
            x = k * 330 + 80
            if k % 3 == 0:
                E.lamppost(ctx, x, 990, 1.0, 0, 1.0)
            else:
                E.pine(ctx, x, 1010, 240 + (k % 2) * 60, E.PINE, True, 6, seed=k)
    return painted('near', PW, H + 100, d, blur=1, passes=1)


def plaza_back():
    def d(ctx):
        E.hills(ctx, 300, 760, 60, (0.80, 0.83, 0.94), 4, lw=5, pines=0.4, pine_h=60,
                pine_c=(0.32, 0.45, 0.52), period=900)
        E.village(ctx, 150, 790, 0, s=0.62, beat_amp=0, seed=11)
        E.snow_ground(ctx, 905, 37)
        # adoquines de la plaza
        for r in range(5):
            yy = 930 + r * 32
            for c in range(-1, 24):
                xx = c * 90 + (r % 2) * 45
                line(ctx, [(xx, yy), (xx + 60, yy + 3)], 4, (0.62, 0.70, 0.86), 0.8)
        E.lamppost(ctx, 760, 925, 0.9, 0, 1.0)
        E.lamppost(ctx, 1780, 925, 0.9, 0, 1.0)

    def d2(ctx):
        ctx.translate(PAD_X, PAD_Y)
        d(ctx)
    return painted('plaza', W + 2 * PAD_X, H + 2 * PAD_Y, d2, blur=1, passes=2)


# ----------------------------------------------------------------------------
# ESCENAS
# ----------------------------------------------------------------------------
def sc_leader(ctx, lt, t):
    n = 3 - int(lt)
    E.leader(ctx, lt, max(1, n))
    return {}


def sc_title(ctx, lt, t):
    E.sunburst(ctx, W / 2, H / 2 + 40, lt, (0.55, 0.07, 0.10), (0.68, 0.12, 0.15), 32, 0.08)
    glow(ctx, W / 2, H / 2, 700, (1.0, 0.85, 0.5), 0.35)
    # Krampus asomado de cabeza desde arriba
    peek = ease_out((lt - 3.2) / 0.6) - ease_in((lt - 5.4) / 0.4)
    if peek > 0:
        ctx.save()
        ctx.translate(W / 2 + 40, -330 + 330 * peek - 70)
        ctx.rotate(math.pi)
        krampus(ctx, 0, 0, 0.42, 1, lt, grin=0.5, basket=False, look=(0.2, -0.6),
                lh=(-130, -520), rh=(130, -520))
        ctx.restore()
    E.deco_frame(ctx, 40)
    E.holly(ctx, 95, 95, 1.1, 0.8)
    E.holly(ctx, W - 95, 95, 1.1, 2.4)
    E.holly(ctx, 95, H - 95, 1.1, -0.8)
    E.holly(ctx, W - 95, H - 95, 1.1, -2.4)
    # textos con rebote
    s1 = back_out((lt - 0.25) / 0.55)
    if s1 > 0:
        text(ctx, 'JENGI & NIEVE', W / 2, 330 + math.sin(lt * 3) * 6, 150, 'Luckiest Guy', CREAM, INK, 18,
             shadow=GOLD, sdx=8, sdy=10, scale=s1)
    s2 = back_out((lt - 0.8) / 0.4)
    if s2 > 0:
        text(ctx, 'en', W / 2, 470, 80, 'Lobster', CREAM, INK, 8, scale=s2)
    s3 = elastic((lt - 1.2) / 1.0)
    if s3 > 0:
        text(ctx, '¡LA NOCHE', W / 2, 600, 130, 'Rye', (0.30, 0.66, 0.40), CREAM, 14, shadow=INK, sdx=7, sdy=8,
             scale=s3, rot=math.sin(lt * 2.5) * 0.02)
        text(ctx, 'DEL KRAMPUS!', W / 2, 745, 138, 'Rye', (0.30, 0.66, 0.40), CREAM, 14, shadow=INK, sdx=7,
             sdy=8, scale=s3, rot=-math.sin(lt * 2.5) * 0.02)
    # los héroes asoman y saludan
    pj = ease_out((lt - 1.8) / 0.5)
    if pj > 0:
        jengi(ctx, 250, H + 250 - 200 * pj, 1.2, 1, 'wave', lt, 'happy')
        nieve(ctx, W - 250, H + 240 - 200 * pj, 1.2, -1, 'wave', lt + 0.3, 'happy')
    # iris de cierre
    if lt > 5.9:
        r = lerp(1300, 0, ease_in((lt - 5.9) / 0.6))
        iris(ctx, W / 2, H / 2, r)
    return {}


def sc_village(ctx, lt, t):
    dur = 10.5
    u = lt / dur
    pan = lerp(0, 1150, ease(u * 0.98))
    blit(ctx, sky_layer(0.0), -PAD_X, -PAD_Y)
    E.sky(ctx, t, 0, moon=None, stars=True)  # estrellas titilantes encima
    ctx.save()
    ctx.translate(0, 0)
    E.moon_face(ctx, 1450 - pan * 0.05, 200, 100, t, 'sleepy')
    ctx.restore()
    blit(ctx, far_layer(), -pan * 0.25, 0)
    blit(ctx, town_layer(), -pan * 0.55, 0)
    # humo vivo de chimeneas del pueblo (posiciones del pueblo pintado)
    for k in range(-1, 12):
        sx = k * 270 * 0.8 - pan * 0.55
        if -100 < sx < W + 100:
            hgt = (150 + 90 * u01(k, 3 + 2)) * 0.8
            cxp = (170 + 70 * u01(k, 3 + 1)) * (0.18 if k % 2 else -0.22) * 0.8
            for j in range(4):
                ph = (lt * 0.35 + j / 4 + k * 0.13) % 1
                r = (10 + ph * 26)
                blob(ctx, sx + cxp + math.sin(ph * 6 + k) * 16 + ph * 34,
                     840 + u01(k, 8) * 8 - hgt - 100 - ph * 150, r, r * 0.85, (0.88, 0.86, 0.94), 3,
                     seed=k * 7 + j, a=(1 - ph) * 0.8)
    E.snowfall(ctx, t, 70, 0, 25)
    blit(ctx, near_layer(), -pan * 1.0, -30)
    E.snowfall(ctx, t, 50, 1, 35)
    E.snowfall(ctx, t, 26, 2, 45)
    if lt < 0.6:
        iris(ctx, W / 2, H / 2, lerp(0, 1300, ease_out(lt / 0.6)))
    return {}


def plaza_set(ctx, t, green=0.0, moon_mood='happy', tree_bell=True, bell_sw=0.0, tower_scared=0.0,
              clouds=0.0, bell_shine=0.0, presents=None):
    if green < 1:
        blit(ctx, sky_layer(0.0), -PAD_X, -PAD_Y)
    if green > 0:
        blit(ctx, sky_layer(1.0), -PAD_X, -PAD_Y, a=green)
    E.sky(ctx, t, green, moon=None, stars=True)
    E.moon_face(ctx, 1560, 190, 95, t, moon_mood, green)
    E.storm_clouds(ctx, t, clouds)
    blit(ctx, plaza_back(), -PAD_X, -PAD_Y)
    E.clocktower(ctx, 300, 935, 1.0, t, tower_scared, green)
    top = E.xmas_tree(ctx, 1180, 935, 0.80, t, bell=tree_bell, bell_sw=bell_sw, lights=1.0 - 0.6 * green,
                      bell_shine=bell_shine)
    if presents is not None:
        presents(ctx)
    return top


PILE = [(1010, 925, 90, 70, 0), (1100, 935, 70, 60, 1), (1265, 930, 100, 75, 2), (1360, 935, 70, 55, 3),
        (1180, 945, 80, 50, 4), (1450, 940, 60, 50, 5)]


def draw_pile(ctx, suck=-1.0, basket=(380, 120)):
    for i, (x, y, w, h, c) in enumerate(PILE):
        u = clamp((suck - i * 0.18) / 0.9) if suck >= 0 else 0
        if u >= 1:
            continue
        px = lerp(x, basket[0], ease_in(u))
        py = lerp(y - h / 2, basket[1], ease_in(u)) - math.sin(u * math.pi) * 260
        c1, c2 = PRESENT_COLORS[c]
        sc = 1 - 0.5 * u
        ctx.save()
        ctx.translate(px, py)
        ctx.rotate(u * 9 * (1 if i % 2 else -1))
        ctx.scale(sc, sc)
        present(ctx, 0, 0, w, h, c1, c2)
        ctx.restore()


def sc_plaza(ctx, lt, t):
    # cámara: Jengi -> Nieve -> plano conjunto
    if lt < 3.6:
        cx, cy, z = lerp(940, 900, lt / 3.6), 640, 1.35
    elif lt < 5.0:
        k = ease((lt - 3.6) / 1.0)
        cx, cy, z = lerp(900, 1430, k), 640, 1.35
    else:
        k = ease((lt - 5.0) / 1.2)
        cx, cy, z = lerp(1430, 1130, k), lerp(640, 560, k), lerp(1.35, 1.0, k)
    ctx.save()
    cam(ctx, cx, cy, z)
    plaza_set(ctx, t, presents=lambda c: draw_pile(c))
    if lt < 6.6:
        jengi(ctx, 900, 985, 1.05, 1, 'dance', lt, 'happy')
        nieve(ctx, 1430, 985, 1.05, -1, 'dance', lt + 0.33, 'happy')
    else:
        jengi(ctx, 900, 985, 1.05, 1, 'wave', lt, 'happy')
        nieve(ctx, 1430, 985, 1.05, -1, 'wave', lt + 0.2, 'happy')
    E.snowfall(ctx, t, 40, 1, 20)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 30)
    return {}


KR_TOWER = (300, 278)   # pies del Krampus sobre la torre (coords de plaza)
KR_S = 0.52


def sc_storm(ctx, lt, t):
    green = ease((lt - 1.8) / 2.0)
    clouds = ease((lt - 1.0) / 3.0)
    reveal = 7.2   # "¡KRAMPUS!"
    flash = 0.0
    if 3.75 < lt < 4.1:
        flash = 0.7 * (1 - (lt - 3.75) / 0.35)
    if reveal < lt < reveal + 0.5:
        flash = 0.95 * (1 - (lt - reveal) / 0.5)
    z = lerp(1.0, 0.86, ease((lt - 0.0) / 6.0))
    shake = 0.6 if 3.75 < lt < 4.3 or reveal < lt < reveal + 0.6 else 0.0
    ctx.save()
    cam(ctx, lerp(1130, 900, ease(lt / 6.0)), lerp(560, 410, ease(lt / 6.0)), z, shake)
    plaza_set(ctx, t, green, 'scared' if green > 0.5 else 'happy', tower_scared=1.0 if lt > 4.0 else 0.0,
              clouds=clouds, presents=lambda c: draw_pile(c))
    if 3.75 < lt < 4.15:
        E.lightning(ctx, 1500, -100, 1300, 420, 3.0)
    if reveal < lt < reveal + 0.35:
        E.lightning(ctx, 200, -150, 300, 200, 7.0)
    # Krampus emerge detrás de la torre como silueta
    rise = ease_out((lt - 4.6) / 2.2)
    if rise > 0:
        kx, ky = KR_TOWER
        ky2 = ky + (1 - rise) * 330
        ctx.save()
        ctx.rectangle(-900, -1200, 3000, ky + 1200 - 4)  # oculto tras la torre mientras sube
        ctx.clip()
        sil = 0.0 if lt > reveal else 1.0
        silhouette(ctx, lambda: krampus(ctx, kx, ky2, KR_S, 1, lt, grin=0.3, eyes_glow=1.0, look=(0.6, 0.6)),
                   (0.05, 0.08, 0.05), sil)
        if lt < reveal:
            glow(ctx, kx + 50 * KR_S, ky2 - 670 * KR_S, 60, LIME, 0.8)
            glow(ctx, kx + 10 * KR_S, ky2 - 670 * KR_S, 60, LIME, 0.8)
        ctx.restore()
    # los héroes dejan de bailar y miran al cielo
    if lt < 1.4:
        jengi(ctx, 900, 985, 1.05, 1, 'dance', lt + 10.5, 'happy')
        nieve(ctx, 1430, 985, 1.05, -1, 'dance', lt + 10.83, 'happy')
    elif lt < reveal:
        jengi(ctx, 900, 985, 1.05, 1, 'idle', lt, 'neutral', pose_override={'look': (-0.6, -1.0)})
        nieve(ctx, 1430, 985, 1.05, -1, 'idle', lt, 'neutral', pose_override={'look': (0.6, -1.0)})
    else:
        jengi(ctx, 900, 985, 1.05, -1, 'shock', lt, 'shock')
        nieve(ctx, 1430, 985, 1.05, -1, 'shock', lt, 'shock')
    E.snowfall(ctx, t, 40, 1, 20 + 120 * green)
    ctx.restore()
    E.snowfall(ctx, t, 26, 2, 30 + 200 * green)
    return {'flash': flash}


def sc_kclose(ctx, lt, t):
    # plano contrapicado de Krampus riendo sobre la torre
    laugh = lt < 3.4
    no_t = 3.5
    punch = ease_out((lt - no_t) / 0.25) * (1 - ease((lt - no_t - 0.6) / 0.8)) if lt > no_t else 0
    z = 1.0 + 0.10 * punch + 0.04 * ease((lt - 4.5) / 3.0)
    shake = 0.8 if no_t < lt < no_t + 0.45 else (0.25 if laugh else 0.0)
    blit(ctx, sky_layer(1.0), -PAD_X, -PAD_Y)
    E.sky(ctx, t, 1.0, moon=None, stars=True)
    E.moon_face(ctx, 1600, 230, 140, t, 'scared', 1.0)
    E.storm_clouds(ctx, t + 20, 1.0, 60)
    if 0.2 < lt < 0.45 or no_t < lt < no_t + 0.25:
        E.lightning(ctx, 1750, -100, 1500, 700, 11.0 + (lt > 1))
    ctx.save()
    cam(ctx, 960, 560, z, shake)
    # remate de la torre en primer plano
    ctx.save()
    ctx.translate(960, 1135 + 625 * 2.6)
    ctx.scale(2.6, 2.6)
    E.clocktower(ctx, 0, 0, 1.0, t, 1.0, 1.0)
    ctx.restore()
    # Krampus
    tt = twos(lt)
    if laugh:
        ph = tt * 2 * math.pi * 1.4
        lean = -0.10 - 0.06 * abs(math.sin(ph))
        grin = 0.75 + 0.25 * abs(math.sin(ph))
        lh, rh = (-120, -380), (120, -380)   # manos en la panza
        hop = -abs(math.sin(ph)) * 12
        look = (0.0, -0.6)
    elif lt < 4.4:
        lean, grin, hop, look = 0.10, 0.9, 0, (0.0, 0.3)
        lh, rh = (-260, -560), (260, -560)
    else:
        sp = (lt - 4.4)
        lean = 0.06
        grin = 0.55 + 0.35 * abs(math.sin(tt * 9))
        hop = 0
        look = (0.0, 0.4)
        lh = (-200, -380)
        rh = (lerp(200, 330, ease(sp / 0.4)), lerp(-380, -470, ease(sp / 0.4)))
    krampus(ctx, 960, 1110, 1.12, 1, lt, grin=grin, lh=lh, rh=rh, lean=lean, hop=hop, look=look,
            eyes_glow=0.4 + 0.6 * punch + (0.5 if lt > 4.4 else 0))
    ctx.restore()
    E.snowfall(ctx, t, 40, 2, 260)
    flash = 0.5 * (1 - clamp((lt - no_t) / 0.3)) if lt > no_t else 0.0
    if 0.2 < lt < 0.45:
        flash = 0.5
    return {'flash': flash}


def sc_grab(ctx, lt, t):
    kx, ky = KR_TOWER
    reach0, grab_t, back_t = 0.5, 1.6, 2.4
    suck0 = 2.2
    leap0 = 4.6
    ctx.save()
    cam(ctx, 900, 410, 0.86, 0.3 if grab_t < lt < grab_t + 0.3 else 0.0)
    tree_has_bell = lt < grab_t
    tree_top = (1180, 935 + (-575 - 165 - 40) * 0.80)
    plaza_set(ctx, t, 1.0, 'scared', tree_bell=tree_has_bell, bell_sw=math.sin(lt * 3) * 0.1, tower_scared=1.0,
              clouds=1.0, presents=lambda c: draw_pile(c, lt - suck0 if lt > suck0 else -1,
                                                        (kx - 150 * KR_S, ky - 520 * KR_S)))
    # brazo de manguera que se estira hasta el árbol
    if lt < reach0:
        reach = 0.0
    elif lt < grab_t:
        reach = elastic((lt - reach0) / (grab_t - reach0))
    elif lt < back_t:
        reach = 1 - ease_in((lt - grab_t) / (back_t - grab_t))
    else:
        reach = 0.0
    home = (200, -420)
    tgt = ((tree_top[0] - kx) / KR_S, (tree_top[1] - ky) / KR_S + 20)
    rh = (lerp(home[0], tgt[0], reach), lerp(home[1], tgt[1], reach))
    holding = lt >= grab_t
    # salto final
    lp = clamp((lt - leap0) / 1.0)
    jx = kx + lp * 900
    jy = ky - math.sin(lp * math.pi * 0.8) * 500 - lp * 300
    s = KR_S * (1 - 0.4 * lp)
    if lp < 1:
        krampus(ctx, jx, jy, s, 1, lt, grin=0.9 if holding else 0.5, rh=rh, lh=(-200, -560), look=(0.8, 0.4),
                eyes_glow=0.6, bell_in_hand=(math.sin(lt * 10) * 0.3 if holding else None),
                hop=-abs(math.sin(lt * 6)) * 20 if holding and lt < leap0 else 0)
    if grab_t < lt < grab_t + 0.5:
        for k in range(8):
            a = k * math.pi / 4
            r = 40 + (lt - grab_t) * 300
            sparkle(ctx, tree_top[0] + math.cos(a) * r, tree_top[1] + math.sin(a) * r, 26, GOLD,
                    1 - (lt - grab_t) / 0.5)
    jengi(ctx, 900, 985, 1.05, -1, 'shock', lt, 'shock')
    nieve(ctx, 1430, 985, 1.05, -1, 'shock', lt, 'shock')
    E.snowfall(ctx, t, 40, 1, 140)
    ctx.restore()
    E.snowfall(ctx, t, 26, 2, 230)
    return {'flash': 0.35 * (1 - clamp((lt - grab_t) / 0.25)) if lt > grab_t else 0.0}


def sc_heroes(ctx, lt, t):
    zip_t = 5.1
    z = 1.55 + 0.05 * ease(lt / 5)
    ctx.save()
    cam(ctx, 1160, 700, z)
    plaza_set(ctx, t, 1.0, 'scared', tree_bell=False, tower_scared=1.0, clouds=1.0)
    if lt < 1.6:
        pj, pn, ej, en = 'shock', 'shock', 'shock', 'shock'
        po_j = po_n = None
    elif lt < 3.5:
        pj, ej, pn, en = 'determined', 'angry', 'idle', 'angry'
        po_j = {'rh': (95, -300 + math.sin(lt * 18) * 14)}   # puño al cielo
        po_n = {'look': (-1, -0.3)}
    elif lt < zip_t:
        pj, ej, pn, en = 'point', 'determined', 'determined', 'determined'
        po_j = None
        po_n = None
    else:
        pj = pn = 'run'
        ej = en = 'determined'
        po_j = po_n = None
    if lt < zip_t:
        # anticipación: se agachan antes de salir disparados
        crouch = ease((lt - (zip_t - 0.35)) / 0.35) if lt > zip_t - 0.35 else 0
        sqj = {'squash': 0.18 * crouch} if crouch > 0 else {}
        if po_j:
            sqj.update(po_j)
        jengi(ctx, 980, 985, 1.05, 1, pj, lt, ej, pose_override=sqj or None)
        sqn = {'squash': 0.18 * crouch} if crouch > 0 else {}
        if po_n:
            sqn.update(po_n)
        nieve(ctx, 1330, 985, 1.05, 1, pn, lt, en, pose_override=sqn or None, sling=lt > 3.5)
    else:
        d = (lt - zip_t)
        dx = ease_in(d / 0.45) * 1400
        jengi(ctx, 980 + dx, 985, 1.05, 1, 'run', lt, 'determined',
              pose_override={'squash': -0.18 * clamp(d / 0.1)})
        nieve(ctx, 1330 + dx * 1.1, 985, 1.05, 1, 'run', lt, 'determined',
              pose_override={'squash': -0.18 * clamp(d / 0.1)})
        speed_lines(ctx, 980 + dx - 80, 870, 7, 300, 1 - clamp(d / 0.8))
        dust_puff(ctx, 1000, 985, d, 1.1, 3)
        dust_puff(ctx, 1350, 985, d - 0.05, 1.0, 4)
    E.snowfall(ctx, t, 30, 1, 140)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 230)
    if lt > 5.7:
        r = lerp(1300, 0, ease_in((lt - 5.7) / 1.2))
        iris(ctx, 1100, 760, r)
    return {}


def sc_black(ctx, lt, t):
    ctx.rectangle(-100, -100, W + 200, H + 200)
    col(ctx, (0.02, 0.01, 0.02))
    ctx.fill()
    return {}


# ----------------------------------------------------------------------------
# línea de tiempo
# ----------------------------------------------------------------------------
PREVIEW = [
    (0.0, 3.0, sc_leader),
    (3.0, 9.5, sc_title),
    (9.5, 20.0, sc_village),
    (20.0, 30.5, sc_plaza),
    (30.5, 41.0, sc_storm),
    (41.0, 49.0, sc_kclose),
    (49.0, 55.5, sc_grab),
    (55.5, 62.6, sc_heroes),
    (62.6, 63.5, sc_black),
]

# (archivo, inicio, ganancia, opciones)
PREVIEW_AUDIO = [
    ('mus_intro', 3.0, 0.50, {'fade_out': (29.5, 31.0), 'music': True}),
    ('mus_villain', 30.4, 0.55, {'fade_out': (52.0, 53.0), 'music': True}),
    ('mus_villain', 52.4, 0.50, {'offset': 9.0, 'fade_in': 0.6, 'fade_out': (61.8, 63.4), 'music': True}),
    ('sfx_sleigh', 10.2, 0.45, {}),
    ('n01_erase', 10.0, 1.0, {'voice': True}),
    ('n02_nadie', 20.6, 1.0, {'voice': True}),
    ('sfx_boing', 21.25, 0.30, {}), ('sfx_boing', 21.92, 0.30, {}), ('sfx_boing', 22.58, 0.30, {}),
    ('sfx_boing', 24.6, 0.30, {}), ('sfx_boing', 25.27, 0.30, {}),
    ('j01_feliz', 27.2, 1.0, {'voice': True}),
    ('sfx_wind', 31.0, 0.55, {}),
    ('n03_depronto', 31.0, 1.0, {'voice': True}),
    ('sfx_thunder', 34.2, 0.75, {}),
    ('sfx_chains', 35.4, 0.40, {}),
    ('sfx_thunder', 37.65, 1.0, {}),
    ('sfx_slide', 37.9, 0.45, {}),
    ('k01_esmia', 41.2, 1.05, {'voice': True}),
    ('sfx_thunder', 44.45, 0.6, {}),
    ('sfx_chains', 46.2, 0.5, {}),
    ('sfx_stretch', 49.45, 0.8, {}),
    ('sfx_bell', 50.55, 0.85, {}),
    ('sfx_chains', 51.3, 0.5, {}),
    ('sfx_zip', 51.5, 0.35, {}),
    ('sfx_boing', 53.6, 0.5, {}),
    ('sfx_zip', 53.7, 0.6, {}),
    ('sfx_slide', 55.6, 0.6, {}),
    ('j02_oye', 57.3, 1.0, {'voice': True}),
    ('sfx_zip', 60.5, 0.85, {}),
]

TIMELINES = {'preview': (PREVIEW, PREVIEW_AUDIO)}


# ----------------------------------------------------------------------------
# render
# ----------------------------------------------------------------------------
_POST = {}


def render_frame(args):
    n, tl_name = args
    timeline = TIMELINES[tl_name][0]
    t = n / FPS
    set_time(t, n)
    if 'p' not in _POST:
        _POST['p'] = Post()
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    col(ctx, (0, 0, 0))
    ctx.paint()
    fx = {}
    for (a, b, fn) in timeline:
        if a <= t < b:
            ctx.save()
            # vaivén de la ventanilla del proyector
            ctx.translate(nz(n * 0.7, 31) * 1.6, nz(n * 0.9, 32) * 1.3)
            fx = fn(ctx, t - a, t) or {}
            ctx.restore()
            break
    film_dirt(ctx, n)
    surf.flush()
    rgb = _POST['p'].apply(surf, n, flash=fx.get('flash', 0.0))
    return rgb.tobytes()


def decode(name, sr=48000):
    path = os.path.join(AUD, name + '.mp3')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(sr), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def build_audio(cues, dur, path, sr=48000):
    n = int(dur * sr)
    music = np.zeros((n, 2), np.float32)
    voice = np.zeros((n, 2), np.float32)
    sfx = np.zeros((n, 2), np.float32)
    # proyector de fondo (loop)
    proj = decode('sfx_projector', sr)
    reps = n // len(proj) + 1
    bed = np.tile(proj, (reps, 1))[:n] * 0.10
    bed[:int(3.2 * sr)] *= 3.0
    cache = {}
    for name, start, gain, opt in cues:
        if name not in cache:
            cache[name] = decode(name, sr)
        clip = cache[name]
        off = int(opt.get('offset', 0) * sr)
        clip = clip[off:].copy()
        if 'fade_in' in opt:
            k = int(opt['fade_in'] * sr)
            clip[:k] *= np.linspace(0, 1, k)[:, None]
        i0 = int(start * sr)
        if i0 >= n:
            continue
        seg = clip[:n - i0] * gain
        if 'fade_out' in opt:
            a, b = opt['fade_out']
            ta = np.arange(len(seg)) / sr + start
            env = np.clip((b - ta) / max(b - a, 1e-3), 0, 1)
            seg = seg * env[:, None]
            cut = int((b - start) * sr)
            seg[cut:] = 0
        dest = music if opt.get('music') else voice if opt.get('voice') else sfx
        dest[i0:i0 + len(seg)] += seg
    # ducking: la música baja cuando hablan
    env = np.abs(voice).max(axis=1)
    win = int(0.25 * sr)
    k = np.ones(win, np.float32) / win
    env = np.convolve(env, k, mode='same')
    duck = 1.0 - 0.55 * np.clip(env / 0.08, 0, 1)
    mix = music * duck[:, None] + voice * 1.0 + sfx + bed
    peak = np.abs(mix).max()
    if peak > 0.95:
        mix *= 0.95 / peak
    pcm = (mix * 32767).astype(np.int16)
    import wave
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def render(tl_name, outname):
    timeline, cues = TIMELINES[tl_name]
    dur = timeline[-1][1]
    os.makedirs(OUT, exist_ok=True)
    wav = os.path.join(OUT, outname + '.wav')
    print('audio...', flush=True)
    build_audio(cues, dur, wav)
    nframes = int(round(dur * FPS))
    mp4 = os.path.join(OUT, outname + '.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf',
                           '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                           '-movflags', '+faststart', mp4], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(render_frame, [(n, tl_name) for n in range(nframes)], chunksize=6)):
            ff.stdin.write(buf)
            if i % 120 == 0:
                print(f'frame {i}/{nframes}', flush=True)
    ff.stdin.close()
    ff.wait()
    print('listo:', mp4)


def stills(times, tl_name='preview'):
    d = os.path.join(HERE, 'stills')
    os.makedirs(d, exist_ok=True)
    from PIL import Image
    for tt in times:
        n = int(round(float(tt) * FPS))
        buf = render_frame((n, tl_name))
        Image.frombytes('RGB', (W, H), buf).save(os.path.join(d, f'{tl_name}_{float(tt):07.2f}.png'))
        print('still', tt)


import escenas2  # noqa: E402

TIMELINES['full'] = escenas2.build(sys.modules[__name__])

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'preview'
    if cmd == 'stills':
        args = sys.argv[2:]
        tl = 'preview'
        if args and args[0] in TIMELINES:
            tl, args = args[0], args[1:]
        stills(args, tl)
    elif cmd == 'preview':
        render('preview', 'previa_1080p')
    elif cmd == 'full':
        render('full', 'krampus_1080p')
