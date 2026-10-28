"""
Escenas del video. Cada escena es una funcion f(ctx, lt) que dibuja un cuadro
completo de 1920x1080 para el tiempo local lt (segundos desde el inicio de la escena).
"""
import math
import random

import cairo

from gfx import *  # noqa: F401,F403
from gfx import (W, H, TAU, clamp, lerp, ease, ease_out, window, hexc, mix, shade, src, lin, rad,
                 ell, fell, circ, rrect, frect, poly, fpoly, line, glow, sparkle, text, group_alpha,
                 draw_girl, draw_cat, cat_paw, cloud, ridge, tree, stars, moon, steam, fireflies,
                 rain, pole, wires)

_CACHE = {}


def cached(key, fn, w=W, h=H):
    if key not in _CACHE:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        c = cairo.Context(surf)
        fn(c)
        surf.flush()
        _CACHE[key] = surf
    return _CACHE[key]


def paint_cached(ctx, key, fn, x=0, y=0, a=1.0):
    ctx.set_source_surface(cached(key, fn), x, y)
    ctx.paint_with_alpha(a) if a < 1 else ctx.paint()


def zoom(ctx, z, cx=W / 2, cy=H / 2, dx=0, dy=0):
    ctx.translate(cx + dx, cy + dy)
    ctx.scale(z, z)
    ctx.translate(-cx, -cy)


WALK_HZ = 0.9  # ciclos de paso por segundo


# ----------------------------------------------------------------------------
# elementos compartidos
# ----------------------------------------------------------------------------
def small_house(ctx, x, gy, w, h, wall, roof, lit=1.0, chimney=False, t=0.0, smoke=False):
    frect(ctx, x, gy - h, w, h, wall)
    frect(ctx, x, gy - h, w, h * 0.12, shade(wall, -0.12))
    rh = w * 0.42
    fpoly(ctx, [(x - w * 0.12, gy - h + 4), (x + w * 0.5, gy - h - rh), (x + w * 1.12, gy - h + 4)], roof)
    fpoly(ctx, [(x + w * 0.5, gy - h - rh), (x + w * 1.12, gy - h + 4), (x + w * 0.9, gy - h + 4)],
          shade(roof, -0.18))
    if chimney:
        frect(ctx, x + w * 0.72, gy - h - rh * 0.9, w * 0.11, rh * 0.6, shade(wall, -0.25))
        if smoke:
            steam(ctx, x + w * 0.775, gy - h - rh * 0.95, t, n=7, h=200, w=60, a=0.45, seed=3, size=12)
    ww = w * 0.2
    for k, wx in enumerate((x + w * 0.18, x + w * 0.62)):
        wy = gy - h * 0.62
        if lit > 0:
            glow(ctx, wx + ww / 2, wy + ww * 0.6, ww * 2.2, '#ffcf73', 0.35 * lit)
        frect(ctx, wx, wy, ww, ww * 1.2, mix('#4a5578', '#ffd98a', lit))
        line(ctx, wx + ww / 2, wy, wx + ww / 2, wy + ww * 1.2, shade(wall, -0.3), 2)
        line(ctx, wx, wy + ww * 0.6, wx + ww, wy + ww * 0.6, shade(wall, -0.3), 2)
    frect(ctx, x + w * 0.42, gy - h * 0.42, w * 0.16, h * 0.42, shade(roof, -0.3))


def grass_band(ctx, t, y, c, n=120, seed=7, hgt=40, sway=1.0, a=1.0, x0=-20, x1=W + 20):
    rng = random.Random(seed)
    src(ctx, c, a)
    ctx.set_line_width(5)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(n):
        x = rng.uniform(x0, x1)
        hh = rng.uniform(0.5, 1.0) * hgt
        sw = sway * math.sin(t * 1.3 + x * 0.01) * hh * 0.25
        ctx.move_to(x, y + 6)
        ctx.curve_to(x, y - hh * 0.5, x + sw * 0.5, y - hh * 0.8, x + sw, y - hh)
    ctx.stroke()


def birds(ctx, t, x0, y0, vx, n=3, seed=1, c='#4d4560', s=1.0):
    rng = random.Random(seed)
    for i in range(n):
        bx = x0 + vx * t + rng.uniform(-80, 80) + i * 50
        by = y0 + rng.uniform(-40, 40) + 6 * math.sin(t * 2 + i)
        f = math.sin(t * 9 + i * 1.7) * 8 * s
        ctx.move_to(bx - 14 * s, by - f)
        ctx.curve_to(bx - 7 * s, by - 4 * s, bx - 3 * s, by - 2 * s, bx, by)
        ctx.curve_to(bx + 3 * s, by - 2 * s, bx + 7 * s, by - 4 * s, bx + 14 * s, by - f)
        src(ctx, c)
        ctx.set_line_width(2.6 * s)
        ctx.stroke()


def notes(ctx, t, x, y, n=4, seed=2, c='#6b4a3a', a=0.8):
    rng = random.Random(seed)
    glyphs = ['♪', '♫', '♩']
    for i in range(n):
        per = rng.uniform(3, 4.5)
        p = (t / per + i / n) % 1.0
        px = x + math.sin(p * 5 + i) * 30 + p * 40
        py = y - p * 160
        text(ctx, glyphs[i % 3], px, py, 34 + 10 * (i % 2), c, a * math.sin(math.pi * p), shadow=0,
             font='DejaVu Sans')


def bacon_strip(ctx, x, y, length, width, ang, seed, t=0.0, wob=1.0):
    rng = random.Random(seed)
    k = rng.uniform(2.5, 3.5)
    ph = rng.uniform(0, TAU)
    n = 28
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    top, bot, mid = [], [], []
    for i in range(n + 1):
        u = i / n
        px = (u - 0.5) * length
        amp = width * 0.32 * wob
        py = amp * math.sin(u * k * math.pi + ph + t * 0.6)
        dy = amp * k * math.pi / length * math.cos(u * k * math.pi + ph + t * 0.6)
        nx, ny = -dy, 1.0
        nl = math.hypot(nx, ny)
        nx, ny = nx / nl, ny / nl
        ww = width * 0.5 * (1 + 0.08 * math.sin(u * 17 + ph))
        top.append((px - nx * ww, py - ny * ww))
        bot.append((px + nx * ww, py + ny * ww))
        mid.append((px, py, nx, ny))
    pts = top + bot[::-1]
    poly(ctx, pts)
    src(ctx, '#a63d2b')
    ctx.fill_preserve()
    src(ctx, '#6b2418', 0.7)
    ctx.set_line_width(width * 0.07)
    ctx.stroke()
    for off, wf, c in ((-0.22, 0.16, '#f4d2b2'), (0.18, 0.12, '#efc39e'), (0.0, 0.09, '#c45a3e')):
        ctx.move_to(mid[0][0] + mid[0][2] * off * width, mid[0][1] + mid[0][3] * off * width)
        for px, py, nx, ny in mid[1:]:
            ctx.line_to(px + nx * off * width, py + ny * off * width)
        src(ctx, c)
        ctx.set_line_width(width * wf)
        ctx.stroke()
    # brillo
    for i in range(4):
        u = 0.15 + i * 0.22
        j = int(u * n)
        px, py, nx, ny = mid[j]
        line(ctx, px - 8, py - width * 0.3, px + 10, py - width * 0.32, '#ffffff', width * 0.05, 0.55)
    ctx.restore()


def fried_egg(ctx, x, y, r, seed, t=0.0, jig=0.0, sx=1.0, sy=1.0):
    rng = random.Random(seed)
    ph = [rng.uniform(0, TAU) for _ in range(3)]
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(sx, sy)
    n = 48
    for i in range(n + 1):
        a = i / n * TAU
        rr = r * (1 + 0.11 * math.sin(3 * a + ph[0]) + 0.07 * math.sin(5 * a + ph[1]) + 0.04 * math.sin(9 * a + ph[2]))
        (ctx.move_to if i == 0 else ctx.line_to)(math.cos(a) * rr, math.sin(a) * rr)
    ctx.close_path()
    src(ctx, '#fffdf6')
    ctx.fill_preserve()
    src(ctx, '#e3a956', 0.75)
    ctx.set_line_width(r * 0.07)
    ctx.stroke()
    rad(ctx, -r * 0.2, -r * 0.2, r * 0.2, r * 1.1, [(0, '#ffffff', 0), (1, '#e9dcc8', 0.6)])
    ctx.arc(0, 0, r * 1.15, 0, TAU)
    ctx.fill()
    yr = r * 0.4 * (1 + 0.04 * jig)
    yx, yy = r * 0.08, r * 0.05
    fell(ctx, yx + yr * 0.08, yy + yr * 0.12, yr * 1.08, yr * 1.05, '#e9c98a', 0.6)
    rad(ctx, yx - yr * 0.3, yy - yr * 0.35, yr * 0.1, yr * 1.1, [(0, '#ffd75a'), (0.6, '#ffae1f'), (1, '#f08a12')])
    ctx.arc(yx, yy, yr, 0, TAU)
    ctx.fill()
    fell(ctx, yx - yr * 0.35, yy - yr * 0.4, yr * 0.32, yr * 0.2, '#ffffff', 0.85)
    circ(ctx, yx + yr * 0.35, yy + yr * 0.3, yr * 0.08, '#ffffff', 0.6)
    ctx.restore()


def toast(ctx, x, y, w, ang, butter=1.0, t=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    hw, hh = w / 2, w * 0.52

    def shape(k):
        ctx.move_to(-hw * k, hh * k)
        ctx.line_to(-hw * k, -hh * 0.35 * k)
        ctx.curve_to(-hw * 1.18 * k, -hh * 1.15 * k, -hw * 0.1 * k, -hh * 1.3 * k, 0, -hh * 0.9 * k)
        ctx.curve_to(hw * 0.1 * k, -hh * 1.3 * k, hw * 1.18 * k, -hh * 1.15 * k, hw * k, -hh * 0.35 * k)
        ctx.line_to(hw * k, hh * k)
        ctx.close_path()

    shape(1.0)
    src(ctx, '#a8622a')
    ctx.fill()
    shape(0.86)
    rad(ctx, 0, 0, w * 0.05, w * 0.6, [(0, '#f6d08a'), (0.7, '#e3a456'), (1, '#c97b36')])
    ctx.fill()
    rng = random.Random(int(x))
    for i in range(30):
        circ(ctx, rng.uniform(-hw * 0.7, hw * 0.7), rng.uniform(-hh * 0.6, hh * 0.7), rng.uniform(1, 2.5),
             '#b8743a', 0.5)
    if butter > 0:
        pr = w * 0.33 * (1.25 - 0.5 * butter)
        fell(ctx, 0, hh * 0.05, pr, pr * 0.8, '#ffe58a', 0.55)
        bw = w * 0.26 * (0.55 + 0.45 * butter)
        ctx.save()
        ctx.rotate(0.3)
        frect(ctx, -bw / 2, -bw * 0.38, bw, bw * 0.76, '#fff3b0', r=bw * 0.18)
        frect(ctx, -bw / 2, -bw * 0.38, bw, bw * 0.2, '#ffffff', 0.5, r=bw * 0.1)
        ctx.restore()
    ctx.restore()


def sunset_sky(ctx, x0, y0, x1, y1, k=0.0, t=0.0, clouds=True, night=0.0):
    """Cielo de atardecer (k=0) a noche (night=1)."""
    top = mix(mix('#6d86c2', '#f0a9a0', k * 0.2), '#16204a', night)
    midc = mix('#f4b49c', '#3b4a86', night)
    bot = mix('#ffd99a', '#7a6aa0', night)
    lin(ctx, 0, y0, 0, y1, [(0, top), (0.6, midc), (1, bot)])
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.fill()


# ----------------------------------------------------------------------------
# 1. Establecimiento: atardecer en la colina
# ----------------------------------------------------------------------------
def _est_land(ctx):
    ridge(ctx, 660, 170, '#9a94c6', 11, step=16, freq=0.8)
    ridge(ctx, 720, 120, '#8a9cc0', 12, step=16, freq=1.2)
    ridge(ctx, 770, 70, '#86a58f', 13, step=16, freq=1.7)
    # colina principal
    ctx.move_to(-50, 1200)
    ctx.line_to(-50, 860)
    ctx.curve_to(400, 760, 700, 740, 980, 770)
    ctx.curve_to(1300, 800, 1600, 820, 1980, 800)
    ctx.line_to(1980, 1200)
    ctx.close_path()
    lin(ctx, 0, 740, 0, 1080, [(0, '#8db86a'), (0.5, '#6f9a52'), (1, '#4f7a3f')])
    ctx.fill()
    # camino
    ctx.move_to(930, 790)
    ctx.curve_to(900, 880, 1100, 920, 1000, 1100)
    src(ctx, '#e6cf9e')
    ctx.set_line_width(26)
    ctx.stroke()
    # casitas lejanas
    for (x, gy, w, h, wall, roof, s) in [(180, 830, 90, 60, '#efe0c2', '#5b74a8', 1), (330, 805, 70, 50, '#f3e6cf', '#b8574a', 2),
                                         (1280, 812, 80, 56, '#efe3c8', '#4f7b6a', 3), (1460, 822, 100, 64, '#f1e4cb', '#9b5e8a', 4),
                                         (1680, 815, 70, 48, '#ede0c4', '#c46b46', 5)]:
        small_house(ctx, x, gy, w, h, wall, roof, lit=0.8)
    for (x, y, s, sd) in [(80, 860, 1.2, 1), (480, 800, 1.0, 2), (620, 790, 1.3, 3), (1180, 805, 1.1, 4),
                          (1600, 830, 1.0, 5), (1820, 820, 1.4, 6), (1380, 830, 0.8, 7)]:
        tree(ctx, x, y, s, '#4f7a46', '#7aa65a', sd)


def sc_establish(ctx, lt):
    e = ease(clamp((lt - 1.5) / 10.5))
    ctx.save()
    ctx.translate(0, 520 * (1 - e))
    lin(ctx, 0, -560, 0, 780, [(0, '#5a76b3'), (0.32, '#a7acd6'), (0.6, '#f2b7a5'), (0.82, '#ffd396'), (1, '#ffe9bd')])
    ctx.rectangle(0, -560, W, 1700)
    ctx.fill()
    glow(ctx, 1470, 640, 520, '#ffd28a', 0.55)
    glow(ctx, 1470, 640, 160, '#fff1cf', 0.9)
    circ(ctx, 1470, 640, 62, '#fff6df')
    for (cx, cy, cw, sd, sp) in [(280, -300, 640, 1, 6), (1120, -160, 820, 2, 9), (1700, -380, 520, 3, 5),
                                 (650, 170, 540, 4, 11), (1550, 260, 440, 5, 8), (120, 380, 360, 6, 13)]:
        cloud(ctx, cx + lt * sp, cy, cw, sd, '#fff4e4', '#d797a6', mid='#f6c7b8')
    birds(ctx, lt, -100, 120, 90, n=3, seed=2)
    paint_cached(ctx, 'est_land', _est_land)
    # casa de Hana
    small_house(ctx, 850, 795, 210, 140, '#f6e9cf', '#c9553f', lit=1.0, chimney=True, t=lt, smoke=True)
    tree(ctx, 1110, 800, 1.5, '#4a7542', '#80ad5e', 9)
    frect(ctx, 1072, 700, 10, 98, '#6c4a36')
    # postes
    for px in (400, 700):
        pole(ctx, px, 560, 800 if px == 700 else 812, '#4b4a5e')
    wires(ctx, 100, 400, 560, 40, '#4b4a5e')
    wires(ctx, 400, 700, 560, 40, '#4b4a5e')
    wires(ctx, 700, 1000, 560, 40, '#4b4a5e')
    # primer plano
    ctx.move_to(-20, 1100)
    ctx.line_to(-20, 990)
    ctx.curve_to(500, 960, 1300, 1000, 1940, 970)
    ctx.line_to(1940, 1100)
    ctx.close_path()
    src(ctx, '#3f6a3a')
    ctx.fill()
    grass_band(ctx, lt, 990, '#4e7d42', n=160, seed=3, hgt=60)
    rng = random.Random(4)
    for i in range(40):
        circ(ctx, rng.uniform(0, W), rng.uniform(1000, 1070), rng.uniform(3, 6),
             rng.choice(['#fff6e0', '#ffd2dc', '#ffe68a']), 0.9)
    ctx.restore()
    # luz calida
    rad(ctx, 1470, 500, 0, 1500, [(0, '#ffcf8a', 0.18), (1, '#ffcf8a', 0)])
    ctx.paint()
    a = window(lt, 2.5, 11.5, 1.2)
    text(ctx, "夜のカフェへ", W / 2, 420, 130, '#fffaf0', a)
    text(ctx, "lofi  ·  una noche con Mochi", W / 2, 510, 44, '#fff4e0', a * 0.95)


# ----------------------------------------------------------------------------
# 2. Cocina
# ----------------------------------------------------------------------------
KW0, KW1, KWY0, KWY1 = 960, 1520, 140, 540


def _kitchen_room(ctx):
    # pared con hueco de ventana
    ctx.rectangle(0, 0, W, H)
    ctx.rectangle(KW0, KWY0, KW1 - KW0, KWY1 - KWY0)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    lin(ctx, 0, 0, 0, 760, [(0, '#f2dcb4'), (1, '#e9cc9c')])
    ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    # azulejos
    frect(ctx, 0, 600, W, 160, '#f6efe1')
    for x in range(0, W, 48):
        line(ctx, x, 600, x, 760, '#e3d5bd', 2, cap=cairo.LINE_CAP_BUTT)
    for y in range(600, 760, 40):
        line(ctx, 0, y, W, y, '#e3d5bd', 2, cap=cairo.LINE_CAP_BUTT)
    # marco ventana
    for (x, y, w, h) in [(KW0 - 18, KWY0 - 18, KW1 - KW0 + 36, 18), (KW0 - 18, KWY1, KW1 - KW0 + 36, 26),
                         (KW0 - 18, KWY0, 18, KWY1 - KWY0), (KW1, KWY0, 18, KWY1 - KWY0),
                         ((KW0 + KW1) / 2 - 7, KWY0, 14, KWY1 - KWY0), (KW0, (KWY0 + KWY1) / 2 - 6, KW1 - KW0, 12)]:
        frect(ctx, x, y, w, h, '#9a6a45')
    frect(ctx, KW0 - 40, KWY1 + 18, KW1 - KW0 + 80, 16, '#86593a')
    # cortinas
    for cx, dirn in ((KW0 - 30, 1), (KW1 + 30, -1)):
        ctx.move_to(cx - 60, 110)
        ctx.line_to(cx + 60, 110)
        ctx.curve_to(cx + 40 * dirn + 10, 300, cx + 30, 420, cx + 40, 580)
        ctx.line_to(cx - 40, 580)
        ctx.curve_to(cx - 30, 420, cx - 50, 300, cx - 60, 110)
        ctx.close_path()
        src(ctx, '#f7efe0', 0.95)
        ctx.fill()
        for k in range(-2, 3):
            line(ctx, cx + k * 18, 120, cx + k * 14 + 10 * dirn, 570, '#e4d6bd', 3, 0.8)
        frect(ctx, cx - 44, 360, 88, 14, '#d9706a', r=6)
    frect(ctx, KW0 - 120, 100, KW1 - KW0 + 240, 12, '#7a5236', r=5)
    # plantas en el alfeizar
    for px, c in ((1020, '#c9705a'), (1100, '#d98b62'), (1440, '#b8604f')):
        fpoly(ctx, [(px - 26, KWY1 + 18), (px + 26, KWY1 + 18), (px + 20, KWY1 - 26), (px - 20, KWY1 - 26)], c)
        for k in range(6):
            a = -math.pi / 2 + (k - 2.5) * 0.35
            ell_x, ell_y = px + math.cos(a) * 36, KWY1 - 30 + math.sin(a) * 36
            ctx.save()
            ctx.translate(ell_x, ell_y)
            ctx.rotate(a + math.pi / 2)
            fell(ctx, 0, 0, 10, 24, '#6f9e5a' if k % 2 else '#88b56a')
            ctx.restore()
    # estantes
    for (y, x0, x1) in ((300, 100, 680), (480, 100, 620)):
        frect(ctx, x0, y, x1 - x0, 16, '#94643f')
        for bx in (x0 + 30, x1 - 40):
            fpoly(ctx, [(bx, y + 16), (bx + 12, y + 16), (bx + 12, y + 50)], '#7a5236')
    rng = random.Random(5)
    x = 130
    for i in range(7):
        w = rng.uniform(46, 70)
        h = rng.uniform(60, 110)
        c = rng.choice(['#e8d8b8', '#c9dfd4', '#f0c9a8', '#d8c2e0', '#f3e5b0'])
        frect(ctx, x, 300 - h, w, h, c, 0.9, r=8)
        frect(ctx, x + 4, 300 - h - 12, w - 8, 14, '#9a6a45', r=4)
        frect(ctx, x + 8, 300 - h * 0.6, w - 16, h * 0.3, '#fffaf0', 0.8, r=3)
        x += w + 12
        if x > 480:
            break
    # radio
    frect(ctx, 520, 210, 140, 90, '#d9724f', r=14)
    circ(ctx, 565, 255, 26, '#6b4434')
    for k in range(4):
        line(ctx, 545, 243 + k * 8, 585, 243 + k * 8, '#a0705a', 2)
    frect(ctx, 605, 232, 40, 18, '#fff1d6', r=4)
    circ(ctx, 625, 272, 8, '#fff1d6')
    line(ctx, 640, 210, 700, 140, '#7a7a7a', 3)
    # tazas
    for i, c in enumerate(('#f1e7d6', '#8fb3c9', '#e9a6a0', '#f4d58c')):
        cx = 150 + i * 105
        frect(ctx, cx, 420, 60, 60, c, r=10)
        ctx.arc(cx + 66, 450, 16, -1.4, 1.4)
        src(ctx, c)
        ctx.set_line_width(8)
        ctx.stroke()
    # barra de utensilios
    line(ctx, 160, 620, 640, 620, '#8c8c8c', 6)
    for i, kind in enumerate(('ladle', 'whisk', 'spat', 'ladle', 'pan')):
        ux = 210 + i * 95
        line(ctx, ux, 620, ux, 700, '#6f5a4a', 6)
        if kind == 'ladle':
            fell(ctx, ux, 715, 20, 16, '#b0b0b0')
        elif kind == 'whisk':
            for k in range(-2, 3):
                ell(ctx, ux, 720, 6 + abs(k) * 4, 26)
            src(ctx, '#a8a8a8')
            ctx.set_line_width(2)
            ctx.stroke()
        elif kind == 'spat':
            frect(ctx, ux - 14, 700, 28, 34, '#c49a6c', r=5)
        else:
            circ(ctx, ux, 720, 34, '#5a5560')
            circ(ctx, ux, 720, 26, '#6e6874')


def _kitchen_counter(ctx):
    frect(ctx, 0, 760, W, 30, '#d4a574')
    frect(ctx, 0, 785, W, 6, '#b5865a')
    frect(ctx, 0, 791, W, H - 791, '#b07a4c')
    for x in range(20, W, 300):
        frect(ctx, x, 815, 270, 240, '#a06c42', r=10)
        frect(ctx, x + 14, 829, 242, 212, '#b8845a', r=8)
        frect(ctx, x + 115, 840, 40, 10, '#e8d2a8', r=5)
    # cocina (fogones)
    frect(ctx, 1180, 742, 440, 22, '#4a4650', r=6)
    for kx in (1260, 1330, 1470, 1540):
        circ(ctx, kx, 805, 10, '#3d3a42')
        circ(ctx, kx, 805, 5, '#d9d0c0')


def kitchen_window_view(ctx, lt, night=0.0, sunx=1240):
    sunset_sky(ctx, KW0, KWY0, KW1, KWY1, night=night)
    glow(ctx, sunx, 470, 300, '#ffd088', 0.6 * (1 - night))
    circ(ctx, sunx, 470, 40 * (1 - night) + 0.1, '#fff3d6', 1 - night)
    for (cx, cy, cw, sd, sp) in [(1080, 250, 260, 21, 7), (1380, 200, 300, 22, 5), (1600, 330, 220, 23, 8),
                                 (900, 380, 200, 24, 6)]:
        cloud(ctx, cx + lt * sp, cy, cw, sd, mix('#fff2e2', '#5d6a9a', night), mix('#d995a8', '#2f3a6a', night))
    ridge(ctx, 520, 70, mix('#8f9ccf', '#232c55', night), 31, x0=KW0, x1=KW1, step=12, freq=3)
    for i, hx in enumerate(range(KW0 - 20, KW1, 110)):
        small_house(ctx, hx, 560, 70, 48 + (i % 3) * 10, mix('#f0e1c6', '#3c4468', night),
                    mix('#7d6a9a', '#242a48', night), lit=0.5 + night * 0.5)


def pan_contents(ctx, lt, px, py):
    # aceite brillante
    fell(ctx, px, py, 92, 22, '#3a3438')
    fell(ctx, px, py - 2, 84, 18, '#4f4850')
    bw = 1 + 0.25 * math.sin(lt * 3)
    for k in range(3):
        bacon_strip(ctx, px - 40 + k * 26, py - 6 + k * 4, 110, 22, 0.25 - k * 0.1, 10 + k, lt, wob=0.6 * bw)
    eg1 = ease((lt - 9.6) / 0.8)
    eg2 = ease((lt - 11.2) / 0.8)
    if eg1 > 0:
        fried_egg(ctx, px + 48, py - 4, 34 * eg1, 41, lt, sy=0.35)
    if eg2 > 0:
        fried_egg(ctx, px - 60, py + 2, 30 * eg2, 42, lt, sy=0.35)
    # chisporroteo
    rng = random.Random(int(lt * 12))
    for i in range(10):
        circ(ctx, px + rng.uniform(-80, 80), py - rng.uniform(5, 40), rng.uniform(1.5, 3), '#fff4d0', 0.8)


def sc_kitchen(ctx, lt):
    ctx.save()
    zoom(ctx, 1.12 + 0.06 * ease(lt / 22), 1150, 1080)
    kitchen_window_view(ctx, lt)
    paint_cached(ctx, 'kitchen', _kitchen_room)
    # rayo de sol
    lin(ctx, 1240, 300, 700, 900, [(0, '#ffe2a0', 0.28), (1, '#ffe2a0', 0)])
    poly(ctx, [(KW0, KWY0), (KW1, KWY0), (900, 1000), (200, 1000)])
    ctx.fill()

    def mote(i, p, x, y, rng):
        circ(ctx, x + 30 * math.sin(lt * 0.5 + i), y - p * 120, 2.2, '#fff6d8', 0.6 * math.sin(math.pi * p))
    from gfx import particles
    particles(ctx, lt, 30, 9, 600, 1300, 300, 900, 7.0, mote)
    notes(ctx, lt, 600, 200)

    # Hana cocinando
    gx, gy, s = 1120, 1040, 3.2
    px, py = 1360, 742
    flip = lt > 6.0 and lt < 7.2
    if flip:
        u = (lt - 6.0) / 1.2
        st = (px - 30 + 60 * u, py - 30 - 70 * math.sin(math.pi * u))
    elif 9.0 < lt < 12.6:
        st = (1282, 700)  # rompe huevos: mano lejos
    else:
        st = (px - 20 + 40 * math.sin(lt * 2.2), py - 34 + 6 * math.sin(lt * 4.4))
    egg_hand = None
    for (t0, t1) in ((9.0, 10.2), (10.6, 11.8)):
        if t0 < lt < t1:
            u = (lt - t0) / (t1 - t0)
            egg_hand = (px - 10 + (-20 if t0 > 10 else 40), py - 90 + 40 * ease(u))

    rec = {}

    def spatula(c, hand, ang):
        hx, hy = hand
        rec['hand'] = c.user_to_device(hx, hy)
        rec['tip'] = c.user_to_device(hx + 28, hy + 24)

    def egg_in_hand(c, hand, ang):
        fell(c, hand[0] + 5, hand[1] - 6, 9, 11, '#fbf2e2')

    if egg_hand:
        near = ('ik', egg_hand[0], egg_hand[1])
        hold = egg_in_hand
    else:
        near = ('ik', st[0] - 40, st[1] - 30)
        hold = spatula
    look = -0.05 if lt < 14 else 0.0
    draw_girl(ctx, gx, gy, s, lt, outfit='home', near=near, far=('ik', 1200, py - 2), hold_near=hold,
              head_tilt=0.12 + look, mouth='smile' if lt % 6 < 4 else 'open')
    paint_cached(ctx, 'kitchen_counter', _kitchen_counter)
    # sarten
    frect(ctx, 1170, py - 8, 110, 14, '#2f2b30', r=6)
    fell(ctx, px, py + 6, 100, 26, '#2a262b')
    pan_contents(ctx, lt, px, py)
    if lt < 22:
        steam(ctx, px, py - 20, lt, n=9, h=260, w=50, a=0.35, seed=8, size=20)
    if rec:
        ctx.save()
        ctx.identity_matrix()
        (hx, hy), (tx_, ty_) = rec['hand'], rec['tip']
        line(ctx, hx, hy, tx_, ty_, '#6b4a3a', 16)
        ctx.translate(tx_, ty_)
        ctx.rotate(math.atan2(ty_ - hy, tx_ - hx) - 0.2)
        frect(ctx, -6, -30, 80, 60, '#d6d0c8', r=12)
        frect(ctx, -6, -30, 80, 14, '#ffffff', 0.5, r=8)
        ctx.restore()
    # tostadora + tostadas
    tx, ty = 470, 760
    pop = lt - 15.5
    th = 0
    if pop > 0:
        th = 70 * math.exp(-pop * 1.8) * abs(math.cos(pop * 9)) + 34 * ease(pop / 0.2)
    for k in (-30, 30):
        frect(ctx, tx + k - 26, ty - 120 - th, 52, 70, '#e3a253', r=10)
        frect(ctx, tx + k - 20, ty - 114 - th, 40, 60, '#f3c983', r=8)
    frect(ctx, tx - 85, ty - 110, 170, 110, '#9fc4c0', r=26)
    frect(ctx, tx - 85, ty - 110, 170, 30, '#b8d8d2', r=20)
    frect(ctx, tx + 70, ty - 70, 24, 12, '#5a6c6a', r=4)
    if 0 < pop < 1.6:
        for i in range(6):
            a = -math.pi / 2 + (i - 2.5) * 0.4
            sparkle(ctx, tx + math.cos(a) * (100 + pop * 60), ty - 150 - th + math.sin(a) * 60,
                    14, '#fff1c0', 1 - pop / 1.6)
    # Mochi en la encimera
    turn = 15.5 < lt < 18.0
    draw_cat(ctx, 820, 764, 2.1, lt, facing=-1 if turn else 1, ear=3 * math.sin(lt * 8) if turn else 0,
             eyes='open' if turn else 'auto', head_dy=-3 if turn else 0)
    if turn:
        text(ctx, "!", 790, 610, 56, '#fff6e0', window(lt, 15.6, 17.6, 0.2), shadow=0.6)
    ctx.restore()


# ----------------------------------------------------------------------------
# 3. Primer plano de la comida
# ----------------------------------------------------------------------------
def _table_top(ctx):
    frect(ctx, 0, 0, W, H, '#9b6943')
    rng = random.Random(3)
    for y in range(0, H, 135):
        line(ctx, 0, y, W, y, '#7d5233', 4, cap=cairo.LINE_CAP_BUTT)
        for k in range(6):
            yy = y + rng.uniform(15, 120)
            ctx.move_to(0, yy)
            for x in range(0, W + 80, 80):
                ctx.line_to(x, yy + 5 * math.sin(x * 0.01 + k))
            src(ctx, '#8a5b39', 0.6)
            ctx.set_line_width(2)
            ctx.stroke()
    # mantel de cuadros
    ctx.save()
    ctx.translate(960, 560)
    ctx.rotate(-0.04)
    frect(ctx, -620, -430, 1240, 860, '#fbf3e4', r=14)
    for i in range(-620, 620, 62):
        frect(ctx, i, -430, 31, 860, '#d9655b', 0.35)
    for j in range(-430, 430, 62):
        frect(ctx, -620, j, 1240, 31, '#d9655b', 0.35)
    ctx.restore()
    # servilleta y cubiertos
    ctx.save()
    ctx.translate(1530, 720)
    ctx.rotate(0.12)
    frect(ctx, -90, -180, 180, 360, '#f0e6d2', r=10)
    frect(ctx, -40, -170, 14, 330, '#c9c3bb', r=6)
    for k in range(4):
        frect(ctx, -46 + k * 6, -200, 4, 50, '#c9c3bb', r=2)
    frect(ctx, 20, -170, 18, 330, '#c9c3bb', r=8)
    ctx.restore()
    # jarron con flores
    circ(ctx, 330, 250, 70, '#8fb6c9')
    circ(ctx, 330, 250, 52, '#b6d4e0')
    for k in range(7):
        a = k / 7 * TAU
        circ(ctx, 330 + math.cos(a) * 42, 250 + math.sin(a) * 42, 26, '#fbe3ea')
    circ(ctx, 330, 250, 24, '#ffd56a')
    for (lx, ly, a) in ((250, 330, 2.4), (420, 200, -0.6), (380, 330, 1.0)):
        ctx.save()
        ctx.translate(lx, ly)
        ctx.rotate(a)
        fell(ctx, 0, 0, 40, 16, '#7fae6a')
        ctx.restore()


def sc_food(ctx, lt):
    ctx.save()
    z = 1.0 + 0.10 * ease(lt / 16)
    zoom(ctx, z, 960, 560, 0, -10 * ease(lt / 16))
    ctx.rotate(0.004 * math.sin(lt * 0.3))
    paint_cached(ctx, 'tabletop', _table_top)
    # taza de cafe con leche
    mx, my = 1530, 280
    fell(ctx, mx + 10, my + 14, 118, 112, '#000000', 0.18)
    ctx.arc(mx + 120, my, 30, -1.2, 1.2)
    src(ctx, '#f2e4cf')
    ctx.set_line_width(20)
    ctx.stroke()
    circ(ctx, mx, my, 112, '#f2e4cf')
    circ(ctx, mx, my, 92, '#7a4a2a')
    rad(ctx, mx, my, 10, 92, [(0, '#c99a6b'), (1, '#7a4a2a')])
    ctx.arc(mx, my, 92, 0, TAU)
    ctx.fill()
    # corazon de espuma
    ctx.save()
    ctx.translate(mx, my + 6)
    ctx.rotate(0.2 * math.sin(lt * 0.4))
    ctx.move_to(0, 30)
    ctx.curve_to(-60, -10, -30, -55, 0, -22)
    ctx.curve_to(30, -55, 60, -10, 0, 30)
    src(ctx, '#f4e2c4')
    ctx.fill()
    ctx.restore()
    steam(ctx, mx, my - 30, lt, n=6, h=240, w=40, a=0.28, seed=12, size=22)
    # plato
    pxc, pyc = 940, 560
    fell(ctx, pxc + 18, pyc + 26, 400, 352, '#3a2414', 0.25)
    fell(ctx, pxc, pyc, 400, 352, '#f8f3e8')
    fell(ctx, pxc, pyc, 318, 278, '#efe7d6')
    fell(ctx, pxc, pyc + 4, 312, 272, '#fffdf7')
    ell(ctx, pxc, pyc, 380, 334)
    src(ctx, '#9ec3d6', 0.6)
    ctx.set_line_width(5)
    ctx.stroke()
    # tostadas
    bt = 1 - ease((lt - 1) / 14) * 0.85
    toast(ctx, 690, 480, 250, -0.35, butter=bt, t=lt)
    toast(ctx, 720, 690, 250, 0.2, butter=bt * 0.9, t=lt)
    # bacon
    for k in range(3):
        bacon_strip(ctx, 1010 + k * 10, 650 + k * 62, 420, 64, -0.12 + k * 0.05, 20 + k, lt * 0.5, wob=0.8)
    # huevos
    jig = math.sin(lt * 9) * math.exp(-lt * 0.8)
    fried_egg(ctx, 940, 410, 135, 7, lt, jig)
    fried_egg(ctx, 1150, 470, 120, 8, lt, -jig)
    # brillos
    for i, (sx_, sy_) in enumerate(((905, 375), (1120, 440), (980, 640), (1100, 760), (700, 470))):
        a = max(0, math.sin(lt * 1.6 + i * 1.3)) ** 3
        sparkle(ctx, sx_, sy_, 22, '#ffffff', a)
    for (sx_, sy_) in ((940, 400), (1150, 460), (1050, 680), (700, 560)):
        steam(ctx, sx_, sy_, lt + sx_, n=4, h=220, w=40, a=0.22, seed=int(sx_), size=26)
    # patita de Mochi
    pk = window(lt, 8.5, 12.8, 1.0)
    if pk > 0:
        reach = ease(clamp((lt - 8.5) / 1.6)) - ease(clamp((lt - 11.4) / 1.2))
        cat_paw(ctx, 1500 - 250 * reach, 1160 - 330 * reach, 2.6, 0.9)
    ctx.restore()
    text(ctx, "いただきます", 1660, 980, 64, '#fffaf0', window(lt, 2.0, 7.0, 1.0))
    text(ctx, "¡Mochi, eso es mío!", 380, 990, 46, '#fffaf0', window(lt, 9.8, 13.2, 0.5))


# ----------------------------------------------------------------------------
# 4. Cenando junto a la ventana
# ----------------------------------------------------------------------------
DW0, DW1, DWY0, DWY1 = 640, 1300, 110, 520
FLOOR4 = 1060


def _dining_room(ctx):
    ctx.rectangle(0, 0, W, H)
    ctx.rectangle(DW0, DWY0, DW1 - DW0, DWY1 - DWY0)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    lin(ctx, 0, 0, 0, 900, [(0, '#efd9b0'), (1, '#e3c695')])
    ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    frect(ctx, 0, 820, W, 240, '#c79a6a')
    for x in range(0, W, 60):
        line(ctx, x, 820, x, FLOOR4, '#b48654', 2, cap=cairo.LINE_CAP_BUTT)
    frect(ctx, 0, 810, W, 14, '#9a6a45')
    frect(ctx, 0, FLOOR4, W, 30, '#7d5233')
    for (x, y, w, h) in [(DW0 - 16, DWY0 - 16, DW1 - DW0 + 32, 16), (DW0 - 16, DWY1, DW1 - DW0 + 32, 22),
                         (DW0 - 16, DWY0, 16, DWY1 - DWY0), (DW1, DWY0, 16, DWY1 - DWY0),
                         ((DW0 + DW1) / 2 - 6, DWY0, 12, DWY1 - DWY0)]:
        frect(ctx, x, y, w, h, '#9a6a45')
    # cuadro y estanteria
    frect(ctx, 240, 220, 220, 160, '#8a5d3c', r=6)
    frect(ctx, 256, 236, 188, 128, '#cfe2e8')
    ridge(ctx, 340, 50, '#8fb27a', 3, x0=256, x1=444, bottom=364, step=8, freq=6)
    frect(ctx, 1480, 360, 300, 14, '#94643f')
    for i, c in enumerate(('#c9705a', '#6f8fb3', '#e8c070', '#8fb08f')):
        frect(ctx, 1500 + i * 40, 280 + (i % 2) * 10, 32, 80 - (i % 2) * 10, c, r=3)
    circ(ctx, 1700, 330, 30, '#f2e4cf')
    fpoly(ctx, [(1675, 360), (1725, 360), (1715, 330), (1685, 330)], '#c9705a')
    for k in range(5):
        a = -math.pi / 2 + (k - 2) * 0.45
        ctx.save()
        ctx.translate(1700 + math.cos(a) * 30, 318 + math.sin(a) * 30)
        ctx.rotate(a + math.pi / 2)
        fell(ctx, 0, 0, 9, 22, '#7aa65a')
        ctx.restore()


def chair(ctx, x, seat_y, floor, facing=1, c='#8a5a38'):
    frect(ctx, x - 60, seat_y, 120, 16, c, r=4)
    frect(ctx, x - 55, seat_y + 16, 12, floor - seat_y - 16, shade(c, -0.15))
    frect(ctx, x + 43, seat_y + 16, 12, floor - seat_y - 16, shade(c, -0.15))
    bx = x - 60 * facing
    frect(ctx, bx - 8, seat_y - 200, 16, 216, c, r=4)
    frect(ctx, bx - 8 + (0 if facing > 0 else -0), seat_y - 200, 16, 20, shade(c, 0.1), r=4)


def clock(ctx, x, y, r, hours):
    circ(ctx, x, y, r + 8, '#8a5d3c')
    circ(ctx, x, y, r, '#fbf4e4')
    for k in range(12):
        a = k / 12 * TAU
        circ(ctx, x + math.cos(a) * r * 0.8, y + math.sin(a) * r * 0.8, 3, '#6b4a3a')
    ah = hours / 12 * TAU - math.pi / 2
    am = (hours % 1) * TAU - math.pi / 2
    line(ctx, x, y, x + math.cos(ah) * r * 0.5, y + math.sin(ah) * r * 0.5, '#4a3328', 6)
    line(ctx, x, y, x + math.cos(am) * r * 0.75, y + math.sin(am) * r * 0.75, '#4a3328', 4)
    circ(ctx, x, y, 5, '#d9534f')


def sc_dinner(ctx, lt):
    night = ease((lt - 1) / 12)
    lamp = ease((lt - 5) / 1.2)
    ctx.save()
    zoom(ctx, 1.34 - 0.04 * ease(lt / 16), 1000, 1080)
    # ventana: del atardecer a la noche
    sunset_sky(ctx, DW0, DWY0, DW1, DWY1, night=night)
    stars(ctx, lt, 40, 5, DWY0, DWY1 - 80, a=night, x0=DW0, x1=DW1)
    moon(ctx, 1180, lerp(470, 230, ease(lt / 16)), 34, a=night)
    for (cx, cy, cw, sd, sp) in [(760, 220, 240, 51, 6), (1100, 300, 280, 52, 4)]:
        cloud(ctx, cx + lt * sp, cy, cw, sd, mix('#fff2e2', '#55608e', night), mix('#d995a8', '#2a3360', night))
    ridge(ctx, 500, 60, mix('#8f9ccf', '#1d2448', night), 61, x0=DW0, x1=DW1, step=12, freq=3)
    rng = random.Random(9)
    for i in range(18):
        circ(ctx, rng.uniform(DW0, DW1), rng.uniform(470, 515), 3, '#ffd27a', night * rng.uniform(0.5, 1))
    paint_cached(ctx, 'dining', _dining_room)
    clock(ctx, 1500, 200, 60, 6.5 + lt / 16 * 0.9)
    # oscurece la habitacion y luego la lampara la calienta
    ctx.rectangle(0, 0, W, H)
    src(ctx, '#1b2240', 0.38 * night * (1 - 0.65 * lamp))
    ctx.fill()
    # lampara colgante
    line(ctx, 960, 0, 960, 210, '#3a3030', 3)
    fpoly(ctx, [(900, 260), (1020, 260), (990, 205), (930, 205)], '#e7b04c')
    if lamp > 0:
        glow(ctx, 960, 280, 700, '#ffcf7a', 0.35 * lamp)
        glow(ctx, 960, 268, 70, '#fff6d8', lamp)
        lin(ctx, 960, 260, 960, 900, [(0, '#ffe2a0', 0.22 * lamp), (1, '#ffe2a0', 0)])
        poly(ctx, [(905, 260), (1015, 260), (1300, 900), (620, 900)])
        ctx.fill()
    seat = FLOOR4 - 46 * 2.95
    chair(ctx, 720, seat, FLOOR4, 1)
    chair(ctx, 1270, seat, FLOOR4, -1)
    # Hana comiendo
    s = 2.95
    gx = 720
    cyc = (lt % 3.4) / 3.4
    plate = (850, 846)
    mouth = (gx + (3 + 16.5) * s + 4, FLOOR4 - 46 * s + (-74 + 11) * s + 6)
    if cyc < 0.35:
        tgt = plate
    elif cyc < 0.6:
        u = ease((cyc - 0.35) / 0.25)
        tgt = (lerp(plate[0], mouth[0], u), lerp(plate[1], mouth[1] + 12, u))
    elif cyc < 0.75:
        tgt = (mouth[0], mouth[1] + 12)
    else:
        u = ease((cyc - 0.75) / 0.25)
        tgt = (lerp(mouth[0], plate[0], u), lerp(mouth[1] + 12, plate[1], u))

    def fork(c, hand, ang):
        hx, hy = hand
        line(c, hx, hy, hx + 22, hy - 10, '#c9c3bb', 3.5)
        fell(c, hx + 24, hy - 11, 4, 3, '#e3a956' if cyc > 0.3 and cyc < 0.7 else '#c9c3bb')

    chewing = 0.6 < cyc < 1.0
    happy = 9.5 < lt < 12.5
    draw_girl(ctx, gx, FLOOR4, s, lt, outfit='home', sit=True, near=('ik', tgt[0] - 26, tgt[1] + 6),
              hold_near=fork, far=('ik', 860, 860), mouth='chew' if chewing else 'smile',
              eyes='happy' if happy else 'auto', head_tilt=0.1 if cyc < 0.35 else -0.02)
    # Mochi en su silla, comiendo de su platito
    looking = 9.0 < lt < 12.5
    fell(ctx, 1275, seat - 18, 75, 26, '#d9705a')
    fell(ctx, 1275, seat - 26, 64, 16, '#e88a6e')
    draw_cat(ctx, 1285, seat - 36, 2.25, lt, pose='sit' if looking else 'eat', facing=-1,
             eyes='happy' if looking else 'auto')
    if looking:
        text(ctx, "♡", 1200, seat - 210, 50, '#ff9fb0', window(lt, 9.3, 12.3, 0.4), shadow=0,
             font='DejaVu Sans')
    # mesa
    ty = FLOOR4 - 70 * s
    frect(ctx, 600, ty, 760, 22, '#fbf3e4')
    frect(ctx, 600, ty + 18, 760, 70, '#fbf3e4')
    for i in range(600, 1360, 40):
        frect(ctx, i, ty + 66, 20, 22, '#d9655b', 0.7)
    frect(ctx, 650, ty + 88, 20, FLOOR4 - ty - 88, '#7d5233')
    frect(ctx, 1290, ty + 88, 20, FLOOR4 - ty - 88, '#7d5233')
    # vajilla
    fell(ctx, 860, ty - 2, 92, 13, '#f8f3e8')
    fell(ctx, 860, ty - 5, 66, 7, '#fffdf7')
    eaten = clamp(lt / 16)
    for k in range(int(3 * (1 - eaten * 0.7)) + 1):
        fell(ctx, 830 + k * 22, ty - 9, 14, 5, '#b8452f' if k % 2 else '#ffcc40')
    fell(ctx, 1190, ty - 2, 44, 9, '#9fc4d6')
    fell(ctx, 1190, ty - 6, 30, 5, '#c45a3e')
    frect(ctx, 975, ty - 66, 52, 64, '#f2e4cf', r=10)
    ctx.arc(1032, ty - 36, 16, -1.4, 1.4)
    src(ctx, '#f2e4cf')
    ctx.set_line_width(8)
    ctx.stroke()
    steam(ctx, 1000, ty - 70, lt, n=5, h=160, w=26, a=0.3, seed=4, size=12)
    ctx.restore()


# ----------------------------------------------------------------------------
# 5. Se arregla para salir (transformacion) y abre la puerta
# ----------------------------------------------------------------------------
FLOOR5 = 940
DOOR0, DOOR1, DOORY = 1420, 1660, 330


def _ready_room(ctx):
    ctx.rectangle(0, 0, W, H)
    ctx.rectangle(DOOR0, DOORY, DOOR1 - DOOR0, FLOOR5 - DOORY)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    lin(ctx, 0, 0, 0, FLOOR5, [(0, '#e2cfb0'), (1, '#d6bf98')])
    ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    # papel pintado: florecitas
    rng = random.Random(4)
    for i in range(140):
        x, y = rng.uniform(0, W), rng.uniform(0, 640)
        if DOOR0 - 40 < x < DOOR1 + 40 and y > DOORY - 40:
            continue
        circ(ctx, x, y, 4, '#c9a982', 0.6)
    frect(ctx, 0, 640, W, 12, '#9a6a45')
    ctx.rectangle(0, 652, W, FLOOR5 - 652)
    ctx.rectangle(DOOR0, DOORY, DOOR1 - DOOR0, FLOOR5 - DOORY)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    src(ctx, '#b58a5e')
    ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    for x in range(0, W, 90):
        if DOOR0 - 10 < x < DOOR1 + 10:
            continue
        line(ctx, x, 660, x, FLOOR5, '#a07a50', 3, cap=cairo.LINE_CAP_BUTT)
    frect(ctx, 0, FLOOR5, W, H - FLOOR5, '#8a5d3c')
    for y in range(FLOOR5 + 30, H, 40):
        line(ctx, 0, y, W, y, '#7a5034', 2, cap=cairo.LINE_CAP_BUTT)
    # marco de la puerta
    frect(ctx, DOOR0 - 22, DOORY - 22, 22, FLOOR5 - DOORY + 22, '#7d5233')
    frect(ctx, DOOR1, DOORY - 22, 22, FLOOR5 - DOORY + 22, '#7d5233')
    frect(ctx, DOOR0 - 22, DOORY - 22, DOOR1 - DOOR0 + 44, 22, '#7d5233')
    # perchero con sombrero y paraguas
    frect(ctx, 1200, 360, 140, 12, '#7d5233', r=4)
    for hx in (1225, 1315):
        circ(ctx, hx, 380, 7, '#c9a24a')
    fell(ctx, 1225, 410, 40, 14, '#d6b27a')
    fell(ctx, 1225, 398, 24, 20, '#d6b27a')
    frect(ctx, 1201, 400, 48, 7, '#d9534f')
    line(ctx, 1315, 385, 1315, 560, '#3a6a8a', 10)
    fpoly(ctx, [(1300, 420), (1330, 420), (1340, 560), (1290, 560)], '#4f86a8')
    # zapatero
    frect(ctx, 1150, 860, 220, 80, '#8a5d3c', r=6)
    for i in range(3):
        fell(ctx, 1190 + i * 70, 855, 24, 9, ['#e7a3a0', '#6b6b8a', '#c9a24a'][i])
    # espejo de pie
    frect(ctx, 300, 300, 320, 620, '#7d5233', r=150)
    frect(ctx, 330, 330, 260, 560, '#9fb5c9', r=125)
    frect(ctx, 440, 900, 40, 40, '#7d5233')
    frect(ctx, 380, 930, 160, 14, '#7d5233', r=6)
    # alfombra
    fell(ctx, 760, FLOOR5 + 60, 300, 40, '#c9705a', 0.8)
    fell(ctx, 760, FLOOR5 + 60, 250, 30, '#e6a07a', 0.8)
    # lampara de pie
    line(ctx, 160, FLOOR5, 160, 420, '#3a3030', 6)
    fpoly(ctx, [(110, 420), (210, 420), (190, 340), (130, 340)], '#f0d9a0')


def sc_ready(ctx, lt):
    ctx.save()
    zoom(ctx, 1.08, 960, 1080)
    door = ease((lt - 11.0) / 1.4)
    # exterior tras la puerta
    sunset_sky(ctx, DOOR0, DOORY, DOOR1, FLOOR5, night=1.0)
    stars(ctx, lt, 20, 8, DOORY, 700, x0=DOOR0, x1=DOOR1)
    moon(ctx, 1560, 430, 26)
    ridge(ctx, 820, 60, '#1d2448', 6, x0=DOOR0, x1=DOOR1, bottom=FLOOR5, step=10, freq=5)
    frect(ctx, DOOR0, 860, DOOR1 - DOOR0, 80, '#2c3350')
    fireflies(ctx, lt, 5, 3, DOOR0, DOOR1, 700, 860)
    paint_cached(ctx, 'ready', _ready_room)
    glow(ctx, 170, 380, 400, '#ffd98a', 0.35)
    glow(ctx, 160, 380, 60, '#fff6d8', 0.9)
    # la hoja de la puerta (gira hacia la bisagra derecha)
    dw = (DOOR1 - DOOR0) * (1 - 0.82 * door)
    frect(ctx, DOOR1 - dw, DOORY, dw, FLOOR5 - DOORY, '#a8744c')
    if dw > 30:
        frect(ctx, DOOR1 - dw + dw * 0.18, DOORY + 60, dw * 0.64, 180, '#8fa6c9', 0.85)
        circ(ctx, DOOR1 - dw + dw * 0.12, 650, 9, '#e8c070')
    if door > 0:
        # luz de luna entrando
        poly(ctx, [(DOOR0, FLOOR5), (DOOR1 - dw, FLOOR5), (DOOR1 - dw - 300 * door, H), (DOOR0 - 380 * door, H)])
        src(ctx, '#a9b8ff', 0.18 * door)
        ctx.fill()

    s, gy = 3.0, FLOOR5
    # Hana: espejo -> transformacion -> camina a la puerta
    m = ease((lt - 4.2) / 0.9)
    if lt < 7.8:
        gx, facing, walk = 760, -1, None
        hop = 18 * max(0.0, math.sin(clamp((lt - 6.0) / 0.6) * math.pi)) if 6 < lt < 6.6 else 0
        gy2 = gy - hop
    else:
        u = clamp((lt - 7.8) / 5.6)
        gx = lerp(760, 1560, u)
        facing, walk = 1, lt * TAU * WALK_HZ
        gy2 = gy
    ga = 1 - ease((gx - 1480) / 80)
    # reflejo
    ctx.save()
    rrect(ctx, 330, 330, 260, 560, 125)
    ctx.clip()
    rx = 2 * 600 - gx
    if lt < 7.8:
        draw_girl(ctx, rx, gy2, s * 0.96, lt, facing=1, outfit_mix=('home', 'night', m),
                  eyes='happy' if 6 < lt < 7.5 else 'auto', alpha=0.85)
    lin(ctx, 330, 330, 590, 890, [(0, '#ffffff', 0.35), (0.5, '#ffffff', 0.0), (1, '#9fb5c9', 0.3)])
    ctx.paint()
    ctx.restore()
    # gato junto a la puerta
    if lt < 9.5:
        draw_cat(ctx, 1300, gy, 2.4, lt, pose='sit', facing=-1, look=-1)
    else:
        cu = clamp((lt - 9.5) / 4.5)
        draw_cat(ctx, lerp(1300, 1600, cu), gy, 2.4, lt, pose='walk', facing=1,
                 phase=lt * TAU * 1.5, alpha=1 - ease((lerp(1300, 1600, cu) - 1480) / 90))
    # chispas de la transformacion
    sp = window(lt, 3.2, 5.8, 0.6)
    if sp > 0:
        for i in range(36):
            a = i * 2.39996 + lt * 3.2
            rr = 120 + 30 * math.sin(i)
            yy = gy - ((i * 37 + lt * 260) % 560)
            sparkle(ctx, gx + math.cos(a) * rr, yy, 10 + (i % 4) * 4,
                    ['#fff6c8', '#ffd1e8', '#cfe8ff'][i % 3], sp * (0.4 + 0.6 * abs(math.sin(a))))
        glow(ctx, gx, gy - 300, 360, '#fff2d0', 0.5 * window(lt, 4.2, 5.2, 0.5))
    draw_girl(ctx, gx, gy2, s, lt, facing=facing, walk=walk, outfit_mix=('home', 'night', m),
              eyes='happy' if 6 < lt < 7.5 else 'auto', alpha=ga, head_tilt=0.05 if lt < 3 else 0)
    ctx.restore()
    text(ctx, "いってきます！", W / 2, 160, 70, '#fffaf0', window(lt, 9.0, 13.5, 0.8))


# ----------------------------------------------------------------------------
# 6. Paseo nocturno por el barrio (scroll lateral con parallax)
# ----------------------------------------------------------------------------
GROUND6 = 900
SPEED6 = 250.0


def jhouse(ctx, x, gy, w, h, seed, t):
    rng = random.Random(seed)
    wall = rng.choice(['#3f4670', '#4a4a72', '#3a4b6a', '#504a6e'])
    roof = rng.choice(['#222844', '#2a2440', '#1e2a40'])
    frect(ctx, x, gy - h, w, h, wall)
    for yy in range(int(gy - h + 20), int(gy), 22):
        line(ctx, x, yy, x + w, yy, shade(wall, -0.12), 2, 0.6, cap=cairo.LINE_CAP_BUTT)
    fpoly(ctx, [(x - 24, gy - h + 6), (x + w + 24, gy - h + 6), (x + w - 20, gy - h - 60), (x + 20, gy - h - 60)], roof)
    for k in range(int(w / 26)):
        line(ctx, x - 14 + k * 26, gy - h + 2, x + 22 + k * 22, gy - h - 56, shade(roof, 0.1), 2, 0.5)
    frect(ctx, x - 16, gy - h * 0.5, w + 32, 12, roof)
    for fl in (0, 1):
        wy = gy - h + 30 if fl == 0 else gy - h * 0.5 + 34
        n = max(1, int(w / 120))
        for k in range(n):
            wx = x + 30 + k * (w - 60) / max(1, n) + 10
            ww = min(90, (w - 60) / n - 20)
            lit = rng.random() < 0.7
            if fl == 1 and k == 0:
                # puerta corredera
                c = '#ffd58a' if lit else '#2a3150'
                if lit:
                    glow(ctx, wx + ww / 2, gy - 60, 160, '#ffc86a', 0.35)
                frect(ctx, wx, gy - 120, ww, 120, c)
                for j in range(1, 4):
                    line(ctx, wx + ww * j / 4, gy - 120, wx + ww * j / 4, gy, shade(wall, -0.3), 2)
                continue
            if lit:
                fl_ = 0.85 + 0.15 * math.sin(t * 0.7 + seed + k)
                glow(ctx, wx + ww / 2, wy + 35, 150, '#ffc86a', 0.35 * fl_)
                frect(ctx, wx, wy, ww, 70, mix('#ffcf7a', '#ffe7b0', 0.5 * fl_))
                if rng.random() < 0.3:
                    fell(ctx, wx + ww * 0.6, wy + 50, 12, 18, '#d79a50', 0.6)
            else:
                frect(ctx, wx, wy, ww, 70, '#26304f')
            line(ctx, wx + ww / 2, wy, wx + ww / 2, wy + 70, shade(wall, -0.35), 2.5)
            line(ctx, wx, wy + 35, wx + ww, wy + 35, shade(wall, -0.35), 2.5)
    if rng.random() < 0.6:
        for k in range(3):
            fpoly(ctx, [(x + w - 40 - k * 30, gy), (x + w - 20 - k * 30, gy), (x + w - 24 - k * 30, gy - 22),
                        (x + w - 36 - k * 30, gy - 22)], '#6b4a3a')
            circ(ctx, x + w - 30 - k * 30, gy - 34, 14, '#2f4a3a')


def vending(ctx, x, gy, t):
    glow(ctx, x + 50, gy - 100, 260, '#cfe8ff', 0.4)
    frect(ctx, x, gy - 200, 100, 200, '#e9eef5', r=6)
    frect(ctx, x + 8, gy - 190, 84, 110, '#f8fbff')
    cols = ['#e05a5a', '#5aa0e0', '#f0c040', '#60c090', '#f08a50', '#a070d0']
    for r in range(3):
        for c in range(4):
            frect(ctx, x + 14 + c * 19, gy - 182 + r * 34, 12, 24, cols[(r * 4 + c) % 6], r=3)
    frect(ctx, x + 14, gy - 60, 72, 26, '#2a2f45', r=4)
    frect(ctx, x + 70, gy - 120, 14, 22, '#ffdd55', r=3)


def lamp_post(ctx, x, gy, t, h=330):
    frect(ctx, x - 6, gy - h, 12, h, '#2b3048')
    line(ctx, x, gy - h, x + 60, gy - h - 6, '#2b3048', 8)
    fpoly(ctx, [(x + 40, gy - h), (x + 90, gy - h), (x + 80, gy - h - 16), (x + 50, gy - h - 16)], '#3a3f58')
    flick = 0.92 + 0.08 * math.sin(t * 13 + x)
    lin(ctx, x + 65, gy - h, x + 65, gy, [(0, '#fff0b0', 0.22 * flick), (1, '#fff0b0', 0.02)])
    poly(ctx, [(x + 45, gy - h), (x + 85, gy - h), (x + 220, gy + 20), (x - 90, gy + 20)])
    ctx.fill()
    glow(ctx, x + 65, gy - h + 4, 120, '#fff0b0', 0.8 * flick)
    fell(ctx, x + 65, gy + 10, 170, 22, '#fff0b0', 0.18 * flick)


def night_sky(ctx, t, y1=900):
    lin(ctx, 0, 0, 0, y1, [(0, '#0f1736'), (0.45, '#24346a'), (0.8, '#4b4f88'), (1, '#6a5f94')])
    ctx.rectangle(0, 0, W, y1)
    ctx.fill()


def _sky6(ctx):
    night_sky(ctx, 0)


def sc_street(ctx, lt):
    off = lt * SPEED6
    paint_cached(ctx, 'sky6', _sky6)
    stars(ctx, lt, 160, 61, 0, 520)
    moon(ctx, 1500, 200, 70)
    for (cx, cy, cw, sd, sp) in [(300, 260, 520, 71, 0.02), (1000, 160, 420, 72, 0.03), (1750, 330, 480, 73, 0.025)]:
        x = (cx - off * sp) % (W + 800) - 400
        cloud(ctx, x, cy, cw, sd, '#9fb0dc', '#3a4778', a=0.9, mid='#6a7aae')
    # montanas con luces
    ctx.save()
    ctx.translate(-(off * 0.06) % 400, 0)
    ridge(ctx, 640, 150, '#2a3462', 81, x0=-400, x1=W + 400, step=20, freq=1.0)
    ctx.restore()
    rng = random.Random(4)
    for i in range(70):
        x = (rng.uniform(0, W + 400) - off * 0.15) % (W + 400) - 200
        y = rng.uniform(600, 690)
        circ(ctx, x, y, 2.5, '#ffd27a', 0.5 + 0.5 * math.sin(lt + i))
    # colina media con casitas
    ctx.save()
    ctx.translate(-((off * 0.3) % 600), 0)
    ridge(ctx, 720, 60, '#252d55', 82, x0=-100, x1=W + 700, step=20, freq=2.0)
    ctx.restore()
    base3 = off * 0.3
    k0 = int((base3 - 300) // 260)
    for k in range(k0, k0 + 11):
        x = k * 260 - base3
        rng = random.Random(k * 7 + 1)
        hh = rng.uniform(60, 110)
        frect(ctx, x, 760 - hh, 150, hh + 60, '#2c3460')
        fpoly(ctx, [(x - 14, 760 - hh), (x + 164, 760 - hh), (x + 120, 760 - hh - 34), (x + 30, 760 - hh - 34)], '#1f2648')
        for j in range(2):
            if rng.random() < 0.7:
                frect(ctx, x + 22 + j * 66, 760 - hh + 20, 36, 26, '#ffcf7a', 0.85)
    # calle principal (velocidad 1.0)
    spacing = 520
    k0 = int((off - 600) // spacing)
    for k in range(k0, k0 + 7):
        x = k * spacing - off
        rng = random.Random(k * 13 + 5)
        w = rng.uniform(340, 440)
        h = rng.uniform(300, 380)
        jhouse(ctx, x, GROUND6 - 40, w, h, k * 13 + 5, lt)
        if k % 3 == 1:
            vending(ctx, x + w + 20, GROUND6 - 40, lt)
    # muro bajo y acera
    frect(ctx, 0, GROUND6 - 40, W, 40, '#3b4466')
    for k in range(int((off - 100) // 80), int((off + W) // 80) + 2):
        line(ctx, k * 80 - off, GROUND6 - 40, k * 80 - off, GROUND6, '#2e3656', 3)
    frect(ctx, 0, GROUND6, W, 30, '#565c80')
    frect(ctx, 0, GROUND6 + 30, W, H - GROUND6 - 30, '#353a58')
    for k in range(int((off - 200) // 300), int((off + W) // 300) + 2):
        frect(ctx, k * 300 - off, GROUND6 + 110, 140, 8, '#c9c3a8', 0.6)
    # postes y cables
    ps = 700
    k0 = int((off - 800) // ps)
    poles_x = [k * ps - off + 200 for k in range(k0, k0 + 5)]
    for i in range(len(poles_x) - 1):
        wires(ctx, poles_x[i], poles_x[i + 1], 260, 60)
    for px in poles_x:
        pole(ctx, px, 260, GROUND6 + 4)
    lp = 900
    k0 = int((off - 1000) // lp)
    for k in range(k0, k0 + 4):
        lamp_post(ctx, k * lp - off + 640, GROUND6 + 4, lt)
    fireflies(ctx, lt, 10, 66, 0, W, 560, 860)
    # Hana y Mochi
    ph = lt * TAU * WALK_HZ
    draw_cat(ctx, 1110 + 30 * math.sin(lt * 0.4), GROUND6 + 22, 1.75, lt, pose='walk', phase=lt * TAU * 1.6,
             look=1 if (lt % 9) > 6 else 0, head_dx=-4 if (lt % 9) > 6 else 0)
    draw_girl(ctx, 860, GROUND6 + 14, 2.3, lt, facing=1, outfit='night', walk=ph,
              eyes='happy' if 12 < lt < 14.5 else 'auto', head_tilt=-0.08 if 12 < lt < 14.5 else 0.0, wind=0.3)
    # primer plano: arbustos de hortensias
    fs = 1.5
    k0 = int((off * fs - 900) // 900)
    for k in range(k0, k0 + 5):
        x = k * 900 - off * fs
        rng = random.Random(k * 31)
        if rng.random() < 0.5:
            continue
        for j in range(7):
            bx, by, r = x + rng.uniform(-150, 150), H + rng.uniform(-60, 20), rng.uniform(60, 110)
            circ(ctx, bx, by, r, '#141a30')
        for j in range(8):
            circ(ctx, x + rng.uniform(-150, 150), H - rng.uniform(20, 100), rng.uniform(16, 26),
                 rng.choice(['#5a6fb8', '#8a6ab8', '#6a8ad0']), 0.8)
    text(ctx, "♪  夜散歩  —  paseo nocturno", 70, 1010, 40, '#fff4e0', window(lt, 2.0, 9.0, 1.0), align='left')


# ----------------------------------------------------------------------------
# 7. El rio y el tren
# ----------------------------------------------------------------------------
WL7 = 600  # nivel del agua
BANK7 = 840


def _river_upper(ctx, lt):
    night_sky(ctx, lt, WL7 + 10)
    stars(ctx, lt, 140, 91, 0, 450)
    moon(ctx, 420, 170, 60)
    for (cx, cy, cw, sd, sp) in [(900, 230, 500, 92, 5), (1600, 140, 420, 93, 4)]:
        cloud(ctx, cx + lt * sp, cy, cw, sd, '#9fb0dc', '#3a4778', a=0.85, mid='#6a7aae')
    ridge(ctx, WL7 - 10, 160, '#28325f', 94, step=20, freq=1.1, bottom=WL7 + 5)
    rng = random.Random(95)
    for i in range(50):
        circ(ctx, rng.uniform(0, W), rng.uniform(WL7 - 70, WL7 - 10), 2.5, '#ffd27a', 0.7)
    # viaducto
    deck = 400
    frect(ctx, 0, deck, W, 26, '#1d2446')
    for k in range(-1, 10):
        x = k * 230 + 40
        ctx.rectangle(x, deck + 20, 230, WL7 + 5 - deck - 20)
        ctx.move_to(x + 20, WL7 + 6)
        ctx.line_to(x + 20, deck + 120)
        ctx.curve_to(x + 20, deck + 50, x + 210, deck + 50, x + 210, deck + 120)
        ctx.line_to(x + 210, WL7 + 6)
        ctx.close_path()
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        src(ctx, '#1d2446')
        ctx.fill()
        ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    for k in range(0, W, 30):
        line(ctx, k, deck - 18, k, deck, '#1d2446', 3)
    line(ctx, 0, deck - 18, W, deck - 18, '#1d2446', 3)
    # tren
    tx = W + 200 - (lt - 2.0) * 420
    if -2200 < tx < W + 100:
        for car in range(4):
            cx = tx + car * 420
            frect(ctx, cx, deck - 92, 400, 82, '#3e5a8a', r=12)
            frect(ctx, cx, deck - 30, 400, 10, '#e8c070')
            for wdw in range(6):
                wx = cx + 22 + wdw * 62
                glow(ctx, wx + 22, deck - 62, 70, '#ffd98a', 0.4)
                frect(ctx, wx, deck - 80, 44, 36, '#ffe3a0', r=4)
                if (car + wdw) % 3 == 0:
                    fell(ctx, wx + 22, deck - 52, 10, 14, '#4a3a4a', 0.6)
            frect(ctx, cx + 30, deck - 12, 60, 12, '#151a30', r=5)
            frect(ctx, cx + 310, deck - 12, 60, 12, '#151a30', r=5)
        glow(ctx, tx - 10, deck - 50, 160, '#fff3c0', 0.6)
        line(ctx, tx + 160, deck - 92, tx + 230, deck - 130, '#2a3050', 3)
        if int(lt * 3) % 4 == 0:
            sparkle(ctx, tx + 230, deck - 130, 16, '#d0e8ff', 0.9)


def sc_river(ctx, lt):
    ctx.push_group()
    _river_upper(ctx, lt)
    pat = ctx.pop_group()
    ctx.set_source(pat)
    ctx.paint()
    # agua con reflejo
    lin(ctx, 0, WL7, 0, BANK7, [(0, '#2d3b70'), (1, '#18203f')])
    ctx.rectangle(0, WL7, W, BANK7 - WL7 + 40)
    ctx.fill()
    ctx.save()
    ctx.rectangle(0, WL7, W, BANK7 - WL7 + 40)
    ctx.clip()
    m = cairo.Matrix(1, 0, 0, -1, 0, 2 * WL7)
    pat.set_matrix(m)
    ctx.set_source(pat)
    ctx.paint_with_alpha(0.4)
    rng = random.Random(7)
    for i in range(90):
        y = rng.uniform(WL7 + 4, BANK7 + 30)
        x = (rng.uniform(0, W) + lt * rng.uniform(10, 30)) % W
        w = rng.uniform(30, 140) * (0.5 + (y - WL7) / 300)
        line(ctx, x, y, x + w, y, '#cfd8ff', 2, 0.18 + 0.12 * math.sin(lt * 2 + i))
    # luna reflejada
    for k in range(10):
        y = 2 * WL7 - 170 + k * 6
        if y > WL7:
            line(ctx, 420 - 50 + 6 * math.sin(lt * 2 + k), y, 420 + 50 + 6 * math.sin(lt * 2.4 + k), y,
                 '#fff9e0', 3, 0.5)
    ctx.restore()
    # orilla
    ctx.move_to(-20, H + 10)
    ctx.line_to(-20, BANK7 + 10)
    ctx.curve_to(500, BANK7 - 20, 1200, BANK7 + 10, 1940, BANK7 - 10)
    ctx.line_to(1940, H + 10)
    ctx.close_path()
    src(ctx, '#1f2a3a')
    ctx.fill()
    frect(ctx, 0, BANK7 + 40, W, 60, '#4a4f6a')
    frect(ctx, 0, BANK7 + 100, W, H - BANK7 - 100, '#1c2436')
    grass_band(ctx, lt, BANK7 + 34, '#2a3a4a', n=140, seed=12, hgt=46)
    # juncos
    rng = random.Random(13)
    for i in range(26):
        x = rng.uniform(0, W)
        hh = rng.uniform(90, 170)
        sw = 8 * math.sin(lt * 1.2 + i)
        ctx.move_to(x, BANK7 + 30)
        ctx.curve_to(x, BANK7 - hh * 0.5, x + sw, BANK7 - hh * 0.8, x + sw * 1.5, BANK7 - hh)
        src(ctx, '#1a2434')
        ctx.set_line_width(4)
        ctx.stroke()
        fell(ctx, x + sw * 1.5, BANK7 - hh, 5, 16, '#3a2e2a')
    fireflies(ctx, lt, 16, 77, 0, W, 560, 840)
    # Hana y Mochi en la orilla
    gy = BANK7 + 72
    if lt < 4.0:
        u = ease_out(lt / 4.0) if lt > 0 else 0
        gx, walk = lerp(260, 860, lt / 4.0), lt * TAU * WALK_HZ
    elif lt < 11.5:
        gx, walk = 860, None
    else:
        gx, walk = lerp(860, 1500, (lt - 11.5) / 4.5), lt * TAU * WALK_HZ
    watching = 4.0 < lt < 11.5
    train_near = window(lt, 4.5, 10, 1.0)
    if lt < 4.3:
        draw_cat(ctx, gx + 170, gy + 6, 1.9, lt, pose='walk', phase=lt * TAU * 1.6)
    elif lt < 11.8:
        draw_cat(ctx, 1030, gy + 6, 1.9, lt, pose='sit', look=0, head_dy=-4, ear=2 * train_near)
    else:
        draw_cat(ctx, lerp(1030, 1680, (lt - 11.8) / 4.2), gy + 6, 1.9, lt, pose='walk', phase=lt * TAU * 1.6)
    draw_girl(ctx, gx, gy, 2.45, lt, outfit='night', walk=walk, wind=0.4 + 0.8 * train_near,
              head_tilt=-0.22 * ease((lt - 4.0) / 0.8) * (1 - ease((lt - 11) / 0.5)),
              eyes='auto', near=('ik', gx + 40, gy - 260) if 6 < lt < 9 and watching else None)
    if 6.2 < lt < 9.2:
        text(ctx, "またね〜", gx + 230, gy - 330, 52, '#fffaf0', window(lt, 6.2, 9.2, 0.4))


# ----------------------------------------------------------------------------
# 8. La cafeteria por fuera
# ----------------------------------------------------------------------------
GROUND8 = 930
CDX0, CDX1, CDY = 1180, 1360, 520


def _cafe_front(ctx):
    night_sky(ctx, 0, GROUND8)
    stars(ctx, 0, 90, 41, 0, 300)
    # edificios vecinos
    frect(ctx, 0, 300, 380, GROUND8 - 300, '#2e3560')
    frect(ctx, 1680, 260, 300, GROUND8 - 260, '#2a3158')
    for (x, y) in ((60, 360), (220, 360), (60, 520), (1740, 330), (1840, 470)):
        frect(ctx, x, y, 90, 80, '#ffcf7a', 0.8)
    # fachada
    frect(ctx, 420, 220, 1220, GROUND8 - 220, '#8a5a3c')
    for y in range(240, GROUND8, 36):
        off = 0 if (y // 36) % 2 else 40
        for x in range(420 + off, 1640, 80):
            frect(ctx, x + 2, y + 2, 76, 32, '#9a6646', 0.7, r=3)
    frect(ctx, 400, 200, 1260, 34, '#5a3a28')
    # cartel
    frect(ctx, 680, 250, 700, 100, '#2f3d32', r=16)
    frect(ctx, 690, 260, 680, 80, '#3d5040', r=12)
    # toldo
    for i in range(14):
        x = 440 + i * 85
        frect(ctx, x, 370, 85, 90, '#2f6a52' if i % 2 == 0 else '#f4ead8')
        ctx.arc(x + 42.5, 460, 42.5, 0, math.pi)
        src(ctx, '#2f6a52' if i % 2 == 0 else '#f4ead8')
        ctx.fill()
    # ventanal (hueco)
    ctx.set_operator(cairo.OPERATOR_CLEAR)
    frect(ctx, 520, 540, 580, 300, '#000000', r=8)
    frect(ctx, CDX0, CDY, CDX1 - CDX0, GROUND8 - CDY, '#000000', r=6)
    ctx.set_operator(cairo.OPERATOR_OVER)
    for (x, y, w, h) in ((505, 525, 610, 15), (505, 840, 610, 22), (505, 525, 15, 337), (1100, 525, 15, 337),
                         (805, 525, 10, 320)):
        frect(ctx, x, y, w, h, '#4a3022')
    frect(ctx, CDX0 - 14, CDY - 14, CDX1 - CDX0 + 28, 14, '#4a3022')
    frect(ctx, CDX0 - 14, CDY, 14, GROUND8 - CDY, '#4a3022')
    frect(ctx, CDX1, CDY, 14, GROUND8 - CDY, '#4a3022')
    # acera
    frect(ctx, 0, GROUND8, W, H - GROUND8, '#41466a')
    frect(ctx, 0, GROUND8, W, 14, '#5a6088')
    # macetas
    for px in (470, 1140, 1420):
        fpoly(ctx, [(px - 30, GROUND8), (px + 30, GROUND8), (px + 38, GROUND8 - 60), (px - 38, GROUND8 - 60)], '#b8604f')
        for k in range(7):
            circ(ctx, px + (k - 3) * 14, GROUND8 - 80 - (k % 3) * 18, 26, '#3f6a4a' if k % 2 else '#4f7d55')
    # pizarra
    fpoly(ctx, [(1480, GROUND8), (1530, 720), (1600, 720), (1650, GROUND8)], '#6b4a34')
    frect(ctx, 1500, 740, 130, 150, '#2c3330', r=6)


def cafe_interior_glimpse(ctx, lt, x0, y0, w, h):
    lin(ctx, 0, y0, 0, y0 + h, [(0, '#ffcf86'), (1, '#e89a5a')])
    ctx.rectangle(x0, y0, w, h)
    ctx.fill()
    for k in range(3):
        lx = x0 + 90 + k * 200
        line(ctx, lx, y0, lx, y0 + 60, '#5a3a28', 2)
        glow(ctx, lx, y0 + 80, 140, '#fff3c0', 0.6)
        fpoly(ctx, [(lx - 30, y0 + 80), (lx + 30, y0 + 80), (lx + 16, y0 + 58), (lx - 16, y0 + 58)], '#3d5040')
    frect(ctx, x0, y0 + h - 90, w, 90, '#8a5a3c')
    for k in range(4):
        # siluetas de clientes
        cx = x0 + 70 + k * 150 + 10 * math.sin(lt * 0.5 + k)
        if k % 2 == 0:
            fell(ctx, cx, y0 + h - 140, 24, 26, '#7a4a3a', 0.55)
            frect(ctx, cx - 30, y0 + h - 118, 60, 40, '#7a4a3a', 0.55, r=14)
    for k in range(5):
        frect(ctx, x0 + 30 + k * 110, y0 + h - 116, 30, 26, '#f4ead8', 0.8, r=4)


def sc_cafe_out(ctx, lt):
    ctx.save()
    zoom(ctx, 1.0 + 0.05 * ease(lt / 14), 1200, 650)
    night_sky(ctx, lt, GROUND8)
    cafe_interior_glimpse(ctx, lt, 520, 540, 580, 300)
    door = ease((lt - 8.0) / 0.8) * (1 - ease((lt - 11.6) / 0.8))
    lin(ctx, 0, CDY, 0, GROUND8, [(0, '#ffd28a'), (1, '#f0a868')])
    ctx.rectangle(CDX0, CDY, CDX1 - CDX0, GROUND8 - CDY)
    ctx.fill()
    paint_cached(ctx, 'cafe_front', _cafe_front)
    glow(ctx, 810, 690, 600, '#ffb860', 0.35)
    # puerta (se abre)
    dw = (CDX1 - CDX0) * (1 - 0.85 * door)
    frect(ctx, CDX0, CDY, dw, GROUND8 - CDY, '#5a3a28')
    if dw > 40:
        frect(ctx, CDX0 + dw * 0.15, CDY + 30, dw * 0.7, 200, '#ffd28a', 0.85)
    if door > 0:
        poly(ctx, [(CDX0 + dw, GROUND8), (CDX1, GROUND8), (CDX1 + 160 * door, H), (CDX0 - 100 * door, H)])
        src(ctx, '#ffcf86', 0.3 * door)
        ctx.fill()
    # campanita
    sw = math.sin((lt - 8) * 14) * math.exp(-(lt - 8) * 2) if lt > 8 else 0
    ctx.save()
    ctx.translate(CDX0 + 20, CDY + 8)
    ctx.rotate(sw * 0.6)
    line(ctx, 0, 0, 0, 20, '#c9a24a', 2)
    fpoly(ctx, [(-10, 34), (10, 34), (6, 18), (-6, 18)], '#e8c070')
    ctx.restore()
    # letrero luminoso
    text(ctx, "喫茶  つきあかり", 1030, 318, 54, '#ffe9b0', 1.0, shadow=0.2)
    glow(ctx, 1030, 300, 380, '#ffe9b0', 0.12)
    text(ctx, "COFFEE", 1565, 790, 26, '#f4ead8', 1.0, shadow=0)
    text(ctx, "珈琲・ケーキ", 1565, 836, 19, '#ffd0d8', 1.0, shadow=0)
    ctx.arc(1565, 862, 14, 0, math.pi)
    src(ctx, '#f4ead8')
    ctx.set_line_width(2.5)
    ctx.stroke()
    # guirnalda de bombillas
    for i in range(24):
        x = 420 + i * 53
        y = 200 + 36 * math.sin(math.pi * ((i % 8) / 8))
        if i > 0:
            px_ = 420 + (i - 1) * 53
            py_ = 200 + 36 * math.sin(math.pi * (((i - 1) % 8) / 8))
            line(ctx, px_, py_, x, y, '#2a2020', 1.5)
        fl = 0.8 + 0.2 * math.sin(lt * 3 + i)
        glow(ctx, x, y + 8, 40, '#ffd98a', 0.6 * fl)
        circ(ctx, x, y + 8, 6, '#fff3c0', fl)
    # farola
    lamp_post(ctx, 240, GROUND8, lt, h=420)
    steam(ctx, 470, 220, lt, n=6, h=200, w=40, a=0.25, seed=18, size=20)
    # personajes
    if lt < 8.6:
        gx = lerp(-120, 1200, ease_out(clamp(lt / 8.6)) * 0.4 + clamp(lt / 8.6) * 0.6)
        walk = lt * TAU * WALK_HZ
    else:
        gx = lerp(1200, 1290, clamp((lt - 8.6) / 2.4))
        walk = (lt * TAU * WALK_HZ) if lt > 9.2 else None
    ga = 1 - ease((lt - 10.0) / 1.2)
    cx = lerp(80, 1260, clamp(lt / 8.0)) if lt < 9.6 else 1260
    ca = 1 - ease((lt - 9.4) / 1.0)
    if lt < 8.0:
        draw_cat(ctx, cx, GROUND8 + 30, 1.9, lt, pose='walk', phase=lt * TAU * 1.6, alpha=ca)
    else:
        draw_cat(ctx, cx, GROUND8 + 30, 1.9, lt, pose='sit', facing=-1, eyes='happy', alpha=ca)
    draw_girl(ctx, gx, GROUND8 + 30, 2.35, lt, outfit='night', walk=walk, alpha=ga,
              near=('ik', CDX0 + 30, 700) if 7.8 < lt < 9.5 else None)
    ctx.restore()


# ----------------------------------------------------------------------------
# 9. Dentro de la cafeteria, junto a la ventana con lluvia
# ----------------------------------------------------------------------------
FLOOR9 = 1060
CW0, CW1, CWY0, CWY1 = 1020, 1860, 90, 690


def _cafe_room(ctx):
    ctx.rectangle(0, 0, W, H)
    ctx.rectangle(CW0, CWY0, CW1 - CW0, CWY1 - CWY0)
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    lin(ctx, 0, 0, 0, H, [(0, '#6e4a36'), (0.6, '#8a5d40'), (1, '#6a4430')])
    ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    for x in range(0, CW0 - 20, 70):
        line(ctx, x, 0, x, H, '#5e3e2c', 3, 0.6, cap=cairo.LINE_CAP_BUTT)
    for (x, y, w, h) in [(CW0 - 20, CWY0 - 20, CW1 - CW0 + 40, 20), (CW0 - 20, CWY1, CW1 - CW0 + 40, 34),
                         (CW0 - 20, CWY0, 20, CWY1 - CWY0), (CW1, CWY0, 20, CWY1 - CWY0),
                         ((CW0 + CW1) / 2 - 8, CWY0, 16, CWY1 - CWY0), (CW0, 300, CW1 - CW0, 12)]:
        frect(ctx, x, y, w, h, '#3e2a1e')
    # estanterias con libros y plantas
    for y in (260, 470):
        frect(ctx, 60, y, 520, 16, '#4a3022')
        rng = random.Random(y)
        x = 80
        while x < 540:
            bw = rng.uniform(18, 34)
            bh = rng.uniform(70, 120)
            frect(ctx, x, y - bh, bw, bh, rng.choice(['#c9705a', '#6f8fb3', '#e8c070', '#8fb08f', '#d8c2e0', '#f0e1c4']), r=3)
            x += bw + 4
            if rng.random() < 0.15:
                fpoly(ctx, [(x + 10, y), (x + 50, y), (x + 44, y - 40), (x + 16, y - 40)], '#b8604f')
                for k in range(5):
                    circ(ctx, x + 30 + (k - 2) * 10, y - 50 - (k % 2) * 14, 16, '#5f8f55')
                x += 64
    # monstera
    fpoly(ctx, [(140, FLOOR9), (260, FLOOR9), (280, 880), (120, 880)], '#c9b8a0')
    rng = random.Random(3)
    for k in range(9):
        a = -math.pi / 2 + (k - 4) * 0.33
        lx, ly = 200 + math.cos(a) * 170, 860 + math.sin(a) * 200
        line(ctx, 200, 880, lx, ly, '#3f6a3a', 5)
        ctx.save()
        ctx.translate(lx, ly)
        ctx.rotate(a + math.pi / 2)
        fell(ctx, 0, 0, 52, 66, '#4f8a4a' if k % 2 else '#5f9a52')
        for j in range(3):
            line(ctx, 0, -40 + j * 30, (40 if j % 2 else -40), -30 + j * 30, '#3f6a3a', 5)
        ctx.restore()
    # suelo
    frect(ctx, 0, FLOOR9, W, H - FLOOR9, '#4a3022')
    # banco junto a la ventana
    frect(ctx, CW0 - 30, CWY1 + 34, CW1 - CW0 + 60, 40, '#4a3022')


def city_bokeh(ctx, lt, x0, y0, x1, y1):
    lin(ctx, 0, y0, 0, y1, [(0, '#121a38'), (0.7, '#2a3060'), (1, '#4a3a5a')])
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.fill()
    for i, (bx, bw, bh) in enumerate(((1040, 160, 330), (1210, 120, 420), (1340, 200, 280), (1550, 140, 380),
                                      (1700, 180, 300))):
        frect(ctx, bx, y1 - bh, bw, bh, '#1c2446')
        rng = random.Random(i)
        for r in range(int(bh / 40)):
            for c in range(int(bw / 34)):
                if rng.random() < 0.45:
                    frect(ctx, bx + 10 + c * 34, y1 - bh + 16 + r * 40, 18, 22, '#ffd27a', 0.6)
    rng = random.Random(77)
    for i in range(34):
        x = rng.uniform(x0, x1)
        y = rng.uniform(y0 + 200, y1)
        r = rng.uniform(18, 46)
        c = rng.choice(['#ffcf7a', '#ff9f8a', '#9fd0ff', '#ffe6a0', '#d9a0ff'])
        a = 0.25 + 0.15 * math.sin(lt * rng.uniform(0.5, 1.5) + i)
        rad(ctx, x, y, r * 0.6, r, [(0, c, a), (1, c, 0)])
        ctx.arc(x, y, r, 0, TAU)
        ctx.fill()


def window_drops(ctx, lt, x0, y0, x1, y1, intensity):
    rng = random.Random(5)
    n = int(70 * intensity)
    for i in range(n):
        x = rng.uniform(x0, x1)
        sp = rng.uniform(40, 140)
        y = y0 + (rng.uniform(0, y1 - y0) + lt * sp * (1 if i % 4 == 0 else 0.05)) % (y1 - y0)
        r = rng.uniform(3, 7)
        if i % 4 == 0:
            line(ctx, x, y - r * 8, x, y, '#cfe0ff', r * 0.5, 0.25)
        fell(ctx, x, y, r * 0.8, r, '#dbe8ff', 0.35)
        circ(ctx, x - r * 0.25, y - r * 0.3, r * 0.25, '#ffffff', 0.6)


def sc_cafe_in(ctx, lt):
    rain_k = ease((lt - 1.0) / 6.0)
    ctx.save()
    zoom(ctx, 1.36 + 0.08 * ease(lt / 24), 1200, 1080)
    city_bokeh(ctx, lt, CW0, CWY0, CW1, CWY1)
    rain(ctx, lt, int(260 * rain_k) + 1, 9, CW0 - 100, CW1, CWY0, CWY1, a=0.4 * rain_k + 0.05)
    window_drops(ctx, lt, CW0, CWY0, CW1, CWY1, 0.2 + 0.8 * rain_k)
    paint_cached(ctx, 'cafe_room', _cafe_room)
    # lamparas colgantes
    for lx in (760, 1300):
        line(ctx, lx, 0, lx, 230, '#2a1e18', 3)
        fpoly(ctx, [(lx - 60, 290), (lx + 60, 290), (lx + 30, 230), (lx - 30, 230)], '#3d5040')
        glow(ctx, lx, 300, 620, '#ffc870', 0.32)
        glow(ctx, lx, 296, 60, '#fff3d0', 1.0)
    # Hana sentada escribiendo
    s = 2.7
    gx = 760
    seat = FLOOR9 - 46 * s
    frect(ctx, gx - 120, seat, 220, 18, '#5a3a28', r=6)
    frect(ctx, gx - 120, seat - 220, 24, 240, '#5a3a28', r=6)
    frect(ctx, gx - 110, seat + 18, 14, FLOOR9 - seat - 18, '#4a3022')
    frect(ctx, gx + 80, seat + 18, 14, FLOOR9 - seat - 18, '#4a3022')
    ty = FLOOR9 - 70 * s
    sip = window(lt, 10.0, 13.5, 0.9)
    head_bob = 0.035 * math.sin(lt * TAU * 78 / 60 / 2)
    mug = (1060, ty - 4)
    mouth = (gx + (3 + 16.5) * s + 6, seat + (-74 + 11) * s + 10)

    def pen(c, hand, ang):
        hx, hy = hand
        line(c, hx - 4, hy + 4, hx + 20, hy - 18, '#4a5a8a', 3.5)

    def cup(c, hand, ang):
        hx, hy = hand
        frect(c, hx - 2, hy - 13, 15, 17, '#f4ead8', r=3)
        frect(c, hx - 2, hy - 13, 15, 3, '#8a5a3c', r=1.5)

    if sip > 0.05:
        u = sip
        tgt = (lerp(mug[0] - 30, mouth[0] + 10, u), lerp(mug[1] - 20, mouth[1] + 20, u))
        near = ('ik', tgt[0], tgt[1])
        hold = cup
    else:
        wx = 900 + 30 * math.sin(lt * 2.3) + 10 * math.sin(lt * 7)
        near = ('ik', wx, ty - 10)
        hold = pen
    draw_girl(ctx, gx, FLOOR9, s, lt, outfit='night', sit=True, near=near, hold_near=hold,
              far=('ik', 900, ty - 4), headphones=True, head_tilt=(0.16 if sip < 0.5 else -0.1) + head_bob,
              eyes='closed' if sip > 0.5 else 'auto', mouth='sip' if sip > 0.6 else 'smile')
    # mesa
    frect(ctx, 640, ty, 560, 22, '#6b4430', r=4)
    frect(ctx, 900, ty + 22, 30, FLOOR9 - ty - 22, '#4a3022')
    frect(ctx, 820, FLOOR9 - 14, 190, 14, '#4a3022', r=6)
    # cuaderno
    fpoly(ctx, [(800, ty), (980, ty), (990, ty - 10), (790, ty - 10)], '#fbf6ea')
    line(ctx, 890, ty - 10, 890, ty, '#d9cdb8', 2)
    # taza (si no esta en la mano)
    if sip <= 0.05:
        frect(ctx, mug[0] - 22, mug[1] - 44, 44, 48, '#f4ead8', r=8)
        ctx.arc(mug[0] + 26, mug[1] - 22, 12, -1.4, 1.4)
        src(ctx, '#f4ead8')
        ctx.set_line_width(6)
        ctx.stroke()
        steam(ctx, mug[0], mug[1] - 50, lt, n=5, h=150, w=24, a=0.35, seed=3, size=12)
    # pastel de fresa
    frect(ctx, 1110, ty - 8, 80, 8, '#e8e2d6', r=3)
    fpoly(ctx, [(1120, ty - 8), (1180, ty - 8), (1180, ty - 52), (1120, ty - 40)], '#fff6ea')
    line(ctx, 1120, ty - 26, 1180, ty - 30, '#f2a0a8', 4)
    circ(ctx, 1160, ty - 58, 9, '#e0404a')
    # Mochi dormido en el banco de la ventana
    draw_cat(ctx, 1450, CWY1 + 34, 2.4, lt, pose='curl')
    for i in range(3):
        p = (lt / 3.0 + i / 3) % 1.0
        text(ctx, "z", 1510 + p * 50 + i * 4, CWY1 - 40 - p * 110, 30 + i * 6, '#fff4e0',
             math.sin(math.pi * p) * 0.9, shadow=0)
    # reflejo calido sobre la mesa
    glow(ctx, 900, ty, 300, '#ffc870', 0.15)
    notes(ctx, lt, 700, 300, n=3, seed=5, c='#ffe7c0', a=0.7)
    ctx.restore()
    a = window(lt, 15.0, 30.0, 1.5)
    text(ctx, "おやすみ、モチ。", W / 2, 150, 84, '#fffaf0', a)
    text(ctx, "buenas noches, Mochi", W / 2, 220, 40, '#fff1d8', a)
