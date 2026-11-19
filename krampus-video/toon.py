"""
toon.py - motor de dibujo "rubber hose" estilo años 30 con pycairo.

Todo se dibuja con vectores: contornos de tinta gruesos, ojos "pie-cut",
guantes blancos, brazos de manguera, y un leve "line boil" (temblor del trazo
que cambia en dos) como en la animación dibujada a mano.
"""
import math

import cairo
import numpy as np

W, H, FPS = 1920, 1080, 24


class G:
    """Estado global por frame."""
    t = 0.0       # tiempo global (s)
    boil = 0      # índice de dibujo (cambia 8 veces por segundo)
    frame = 0
    bg = False        # modo fondo pintado: líneas marrones finas, sin sombreado de cel
    shade = True      # sombreado de cel en personajes


def set_time(t, frame):
    G.t = t
    G.frame = frame
    G.boil = int(t * 8)


# ----------------------------------------------------------------------------
# paleta (Technicolor de los 30)
# ----------------------------------------------------------------------------
INK = (0.09, 0.06, 0.07)
CREAM = (0.97, 0.93, 0.82)
WHITE = (0.99, 0.98, 0.95)
GINGER = (0.74, 0.43, 0.20)
GINGER_D = (0.56, 0.30, 0.13)
GINGER_L = (0.86, 0.58, 0.32)
RED = (0.80, 0.13, 0.16)
RED_D = (0.55, 0.06, 0.09)
GREEN = (0.15, 0.45, 0.29)
GREEN_D = (0.08, 0.28, 0.18)
GOLD = (0.97, 0.77, 0.24)
GOLD_D = (0.78, 0.53, 0.10)
SNOW = (0.97, 0.97, 0.95)
SNOW_SH = (0.70, 0.79, 0.91)
ORANGE = (0.95, 0.52, 0.15)
BROWN = (0.36, 0.22, 0.12)
FUR = (0.20, 0.16, 0.22)
FUR_L = (0.33, 0.28, 0.36)
HORN = (0.88, 0.82, 0.68)
HORN_D = (0.62, 0.55, 0.42)
LIME = (0.62, 0.92, 0.30)
MOUTH = (0.38, 0.05, 0.08)
TONGUE = (0.90, 0.30, 0.35)
BLUSH = (0.96, 0.52, 0.50)
WINDOW = (1.0, 0.86, 0.42)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def back_out(t, s=1.9):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def elastic(t):
    t = clamp(t)
    if t in (0, 1):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


def mixc(c1, c2, t):
    t = clamp(t)
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def twos(t):
    """Tiempo de animación de personajes: 24 dibujos por segundo ('en unos'), fluido."""
    return math.floor(t * 24 + 1e-6) / 24.0


def nz(i, seed=0.0):
    """Ruido determinista en [-1, 1]."""
    v = math.sin(i * 12.9898 + seed * 78.233 + 0.5) * 43758.5453
    return (v - math.floor(v)) * 2 - 1


def u01(i, seed=0.0):
    return nz(i, seed) * 0.5 + 0.5


def window(t, a, b, fade=0.3):
    """1 dentro de [a,b] con rampas suaves."""
    return ease((t - a) / fade) * (1 - ease((t - b + fade) / fade))


# ----------------------------------------------------------------------------
# primitivas
# ----------------------------------------------------------------------------
def col(ctx, c, a=1.0):
    ctx.set_source_rgba(c[0], c[1], c[2], a)


def catmull(ctx, pts, closed=True):
    n = len(pts)
    if n < 2:
        return
    if closed:
        ctx.move_to(*pts[0])
        for i in range(n):
            p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
            ctx.curve_to(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                         p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6,
                         p2[0], p2[1])
        ctx.close_path()
    else:
        ext = [pts[0]] + list(pts) + [pts[-1]]
        ctx.move_to(*pts[0])
        for i in range(1, n):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            ctx.curve_to(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                         p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6,
                         p2[0], p2[1])


def blob_pts(cx, cy, rx, ry, n=22, rot=0.0, wob=None, seed=0.0, rfun=None):
    if wob is None:
        wob = 0.010 * min(rx, ry) + 0.5
    pts = []
    cr, sr = math.cos(rot), math.sin(rot)
    for k in range(n):
        a = 2 * math.pi * k / n
        r = 1.0 if rfun is None else rfun(a, k)
        d = wob * nz(k * 3.1 + G.boil * 17.3, seed)
        x = (rx * r + d) * math.cos(a)
        y = (ry * r + d) * math.sin(a)
        pts.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return pts


def _cel_shade(ctx, a):
    """Sombra suave abajo-derecha y brillo arriba-izquierda dentro de la forma actual."""
    x0, y0, x1, y1 = ctx.fill_extents()
    w, h = x1 - x0, y1 - y0
    if w < 6 or h < 6:
        return
    ctx.save()
    ctx.clip_preserve()
    g = cairo.LinearGradient(x0 + w * 0.25, y0 + h * 0.15, x0 + w * 0.95, y0 + h * 1.0)
    g.add_color_stop_rgba(0.0, 1, 0.97, 0.88, 0.16 * a)
    g.add_color_stop_rgba(0.42, 1, 1, 1, 0.0)
    g.add_color_stop_rgba(0.62, 0.15, 0.05, 0.12, 0.0)
    g.add_color_stop_rgba(1.0, 0.15, 0.05, 0.12, 0.30 * a)
    ctx.set_source(g)
    ctx.paint()
    ctx.restore()


def ink_stroke(ctx, lw, a=1.0, ink=INK, preserve=False):
    """Trazo de pincel: fino arriba-izquierda, grueso abajo-derecha (peso de tinta)."""
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    if G.bg:
        col(ctx, (0.30, 0.20, 0.16), a * 0.75)
        ctx.set_line_width(lw * 0.5)
        if preserve:
            ctx.stroke_preserve()
        else:
            ctx.stroke()
        return
    path = ctx.copy_path()
    col(ctx, ink, a)
    ctx.set_line_width(lw * 0.62)
    ctx.stroke()
    ctx.save()
    ctx.translate(lw * 0.22, lw * 0.30)
    ctx.append_path(path)
    ctx.set_line_width(lw * 0.78)
    ctx.stroke()
    ctx.restore()
    if preserve:
        ctx.append_path(path)


def fill_stroke(ctx, fill, lw=6.0, a=1.0, ink=INK, shade=None):
    if fill is not None:
        col(ctx, fill, a)
        ctx.fill_preserve()
        if (G.shade and not G.bg) if shade is None else shade:
            _cel_shade(ctx, a)
    if lw > 0:
        ink_stroke(ctx, lw, a, ink)
    else:
        ctx.new_path()


def blob(ctx, cx, cy, rx, ry, fill, lw=6.0, rot=0.0, seed=0.0, n=22, wob=None, a=1.0, rfun=None):
    catmull(ctx, blob_pts(cx, cy, rx, ry, n, rot, wob, seed, rfun))
    fill_stroke(ctx, fill, lw, a)


def poly(ctx, pts, fill, lw=6.0, a=1.0, smooth=True, seed=0.0, wob=0.8):
    if wob:
        pts = [(x + wob * nz(i * 5.7 + G.boil * 13.1, seed), y + wob * nz(i * 3.3 + G.boil * 7.7, seed + 1))
               for i, (x, y) in enumerate(pts)]
    if smooth:
        catmull(ctx, pts, True)
    else:
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
    fill_stroke(ctx, fill, lw, a)


def line(ctx, pts, lw=5.0, c=INK, a=1.0, smooth=True):
    if G.bg and c == INK:
        c, lw, a = (0.30, 0.20, 0.16), lw * 0.55, a * 0.75
    if smooth:
        catmull(ctx, pts, False)
    else:
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
    col(ctx, c, a)
    ctx.set_line_width(lw)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()


def circle(ctx, x, y, r, fill, lw=0.0, a=1.0):
    ctx.arc(x, y, r, 0, 2 * math.pi)
    fill_stroke(ctx, fill, lw, a)


def glow(ctx, x, y, r, c, a=0.6):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, c[0], c[1], c[2], a)
    g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
    ctx.set_source(g)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill()


def hose(ctx, a, b, bend, w, c, lw=5.0, mid=None):
    """Brazo/pierna de manguera: curva suave a->b con una comba perpendicular."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    if mid is None:
        cx, cy = (ax + bx) / 2 + nx * bend, (ay + by) / 2 + ny * bend
    else:
        cx, cy = mid
    c1 = (ax + (cx - ax) * 0.66, ay + (cy - ay) * 0.66)
    c2 = (bx + (cx - bx) * 0.66, by + (cy - by) * 0.66)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for width, cc in ((w + 2 * lw, INK), (w, c)):
        ctx.move_to(ax, ay)
        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], bx, by)
        col(ctx, cc)
        ctx.set_line_width(width)
        ctx.stroke()
    # ángulo final (para orientar el guante)
    return math.atan2(by - c2[1], bx - c2[0])


def glove(ctx, x, y, ang, r, lw=5.0, fist=False, spread=1.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    # puño (cuff) enrollado
    blob(ctx, -r * 0.62, 0, r * 0.38, r * 0.70, WHITE, lw, seed=31)
    line(ctx, [(-r * 0.80, -r * 0.45), (-r * 0.78, 0), (-r * 0.80, r * 0.45)], lw * 0.6)
    if not fist:
        for k in (-1, 0, 1):
            blob(ctx, r * 0.78, k * r * 0.44 * spread, r * 0.52, r * 0.26, WHITE, lw,
                 rot=k * 0.32 * spread, seed=40 + k, n=14)
    blob(ctx, 0, 0, r * 0.80 if not fist else r * 0.85, r * 0.74, WHITE, lw, seed=33)
    blob(ctx, r * 0.15, -r * 0.70, r * 0.24, r * 0.36, WHITE, lw, rot=-0.5, seed=35, n=12)
    if fist:
        for k in (-1, 0, 1):
            line(ctx, [(r * 0.35, k * r * 0.30), (r * 0.70, k * r * 0.26)], lw * 0.6)
    # las tres costuras clásicas
    for k in (-1, 0, 1):
        line(ctx, [(-r * 0.30, k * r * 0.25), (r * 0.05, k * r * 0.22)], lw * 0.45)
    ctx.restore()


def eye(ctx, x, y, rx, ry, lx=0.0, ly=0.0, blink=0.0, lw=5.0, pupil=0.62, white=WHITE,
        iris=None, lashes=False, face=1):
    if blink > 0.85:
        line(ctx, [(x - rx, y), (x, y + ry * 0.25), (x + rx, y)], lw)
        return
    ry2 = ry * (1 - blink)
    catmull(ctx, blob_pts(x, y, rx, ry2, 18, seed=x * 0.01))
    col(ctx, white)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip_preserve()
    col(ctx, INK)
    ctx.set_line_width(lw)
    ctx.stroke()
    px, py = x + lx * rx * 0.38, y + ly * ry2 * 0.32 + ry2 * 0.08
    if iris is not None:
        ctx.save()
        ctx.translate(px, py)
        ctx.scale(rx * pupil * 1.25, ry2 * 0.72)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        col(ctx, iris)
        ctx.fill()
    ctx.save()
    ctx.translate(px, py)
    ctx.scale(rx * pupil, ry2 * 0.60)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    col(ctx, INK)
    ctx.fill()
    # el corte de "pastel"
    rr = max(rx * pupil, ry2 * 0.6) * 1.3
    ctx.move_to(px + rx * pupil * 0.05, py - ry2 * 0.05)
    ctx.line_to(px + math.cos(-1.15) * rr, py + math.sin(-1.15) * rr)
    ctx.line_to(px + math.cos(-0.45) * rr, py + math.sin(-0.45) * rr)
    ctx.close_path()
    col(ctx, white if iris is None else iris)
    ctx.fill()
    ctx.restore()
    ctx.new_path()
    if lashes:
        for k in range(3):
            a = -math.pi / 2 + (k - 1) * 0.45 + face * 0.25
            sx, sy = x + math.cos(a) * rx, y + math.sin(a) * ry2
            line(ctx, [(sx, sy), (sx + math.cos(a) * rx * 0.45, sy + math.sin(a) * ry2 * 0.45)], lw * 0.8)


def mouth(ctx, x, y, w, open_=0.6, smile=1.0, lw=5.0, teeth=False, tongue=True, square_teeth=0):
    """Boca abierta clásica. smile>0 sonrisa, <0 mueca."""
    h = w * 0.55 * open_
    up = -w * 0.10 * smile
    if open_ < 0.08:
        line(ctx, [(x - w / 2, y + up), (x, y + w * 0.18 * smile), (x + w / 2, y + up)], lw)
        return
    pts = []
    for k in range(9):
        u = k / 8.0
        pts.append((x - w / 2 + w * u, y + up + (w * 0.06 * smile) * math.sin(math.pi * u)))
    for k in range(9):
        u = 1 - k / 8.0
        pts.append((x - w / 2 + w * u, y + up + h * math.sin(math.pi * u) * (1 if smile >= 0 else 0.8)
                    + w * 0.12 * smile * math.sin(math.pi * u)))
    catmull(ctx, pts)
    col(ctx, MOUTH)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip_preserve()
    ctx.new_path()
    if tongue:
        blob(ctx, x + w * 0.08, y + up + h * 1.0, w * 0.30, h * 0.55, TONGUE, 0, seed=7)
    if teeth:
        ctx.rectangle(x - w / 2, y + up - 2, w, h * 0.28)
        col(ctx, WHITE)
        ctx.fill()
    if square_teeth:
        n = square_teeth
        tw = w * 0.8 / n
        for i in range(n):
            tx = x - w * 0.4 + i * tw
            ctx.rectangle(tx + 1, y + up - 4, tw - 3, h * 0.30 + 4)
            col(ctx, WHITE)
            ctx.fill_preserve()
            col(ctx, INK)
            ctx.set_line_width(lw * 0.5)
            ctx.stroke()
    ctx.restore()
    catmull(ctx, pts)
    col(ctx, INK)
    ctx.set_line_width(lw)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()


def sparkle(ctx, x, y, r, c=CREAM, a=1.0, rot=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.move_to(0, -r)
    for k in range(4):
        a1 = -math.pi / 2 + k * math.pi / 2
        a2 = a1 + math.pi / 4
        a3 = a1 + math.pi / 2
        ctx.line_to(math.cos(a2) * r * 0.22, math.sin(a2) * r * 0.22)
        ctx.line_to(math.cos(a3) * r, math.sin(a3) * r)
    ctx.close_path()
    col(ctx, c, a)
    ctx.fill()
    ctx.restore()


def text(ctx, s, x, y, size, font, fill, outline=INK, lw=8.0, shadow=None, sdx=6, sdy=6,
         align=0.5, rot=0.0, scale=1.0, a=1.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(scale, scale)
    ctx.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    ox = -ext.x_advance * align
    oy = size * 0.35
    if shadow is not None:
        ctx.move_to(ox + sdx, oy + sdy)
        ctx.text_path(s)
        col(ctx, shadow, a)
        ctx.fill()
    ctx.move_to(ox, oy)
    ctx.text_path(s)
    if outline is not None:
        col(ctx, outline, a)
        ctx.set_line_width(lw)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke_preserve()
    col(ctx, fill, a)
    ctx.fill()
    ctx.restore()


def boot(ctx, x, y, face, s=1.0, c=INK, lw=5.0):
    blob(ctx, x + face * 10 * s, y - 13 * s, 30 * s, 17 * s, c, lw, seed=x * 0.1, n=16)
    line(ctx, [(x + face * 2 * s, y - 22 * s), (x + face * 18 * s, y - 25 * s), (x + face * 30 * s, y - 19 * s)],
         4 * s, c=(0.55, 0.55, 0.6), a=0.8)


# ----------------------------------------------------------------------------
# poses compartidas para los héroes
# ----------------------------------------------------------------------------
def hero_pose(pose, t, phase=0.0):
    """Devuelve dict con hop, squash, lean, pies y manos (coords locales)."""
    t = twos(t)
    p = dict(hop=0.0, squash=0.0, lean=0.0, lf=(-22, 0), rf=(22, 0),
             lh=(-78, -66), rh=(78, -66), blink=0.0, look=(0.3, 0.0))
    bl = (t * 0.7 + phase) % 3.3
    p['blink'] = 1.0 if bl < 0.12 else 0.0
    if pose == 'idle':
        s = math.sin(2 * math.pi * 1.3 * t + phase)
        p['squash'] = 0.03 * s
        p['lh'] = (-80, -64 + 5 * s)
        p['rh'] = (80, -64 - 5 * s)
    elif pose == 'dance':
        b = t * 1.5 + phase
        s = math.sin(math.pi * 2 * b)
        hopv = abs(math.sin(math.pi * 2 * b))
        p['hop'] = -26 * hopv
        p['squash'] = 0.10 * (0.5 - hopv) * 2 * 0.5
        p['lean'] = 0.12 * s
        k = 1 if s > 0 else -1
        p['lh'] = (-80 - 10 * s, -170 + 70 * max(0, -s) - 40 * max(0, s))
        p['rh'] = (80 - 10 * s, -170 + 70 * max(0, s) - 40 * max(0, -s))
        p['lf'] = (-26 - 30 * max(0, -s), -30 * max(0, -s))
        p['rf'] = (26 + 30 * max(0, s), -30 * max(0, s))
        p['look'] = (0.6 * k, -0.2)
    elif pose == 'run':
        ph = 2 * math.pi * 3.0 * t + phase
        c, s = math.cos(ph), math.sin(ph)
        p['lean'] = 0.20
        p['hop'] = -10 * abs(s)
        p['lf'] = (42 * c, -32 * max(0, s))
        p['rf'] = (-42 * c, -32 * max(0, -s))
        p['lh'] = (-48 * c + 6, -96 + 10 * s)
        p['rh'] = (48 * c + 6, -96 - 10 * s)
        p['look'] = (1, 0)
    elif pose == 'shock':
        j = math.sin(t * 60) * 3
        p['squash'] = -0.14
        p['hop'] = -18
        p['lh'] = (-95 + j, -235)
        p['rh'] = (95 - j, -235)
        p['lf'] = (-38, 0)
        p['rf'] = (38, 0)
        p['look'] = (0.0, -0.3)
    elif pose == 'wave':
        s = math.sin(2 * math.pi * 3 * t)
        p['rh'] = (88 + 18 * s, -240)
        p['lh'] = (-58, -82)
        p['squash'] = 0.03 * s
        p['look'] = (0.0, 0.1)
    elif pose == 'point':
        p['rh'] = (130, -150)
        p['lh'] = (-55, -70)
        p['lean'] = 0.08
        p['look'] = (1, 0)
    elif pose == 'jump':
        p['hop'] = 0
        p['lh'] = (-80, -230)
        p['rh'] = (80, -230)
        p['lf'] = (-30, -28)
        p['rf'] = (26, -40)
        p['squash'] = -0.08
    elif pose == 'determined':
        s = math.sin(2 * math.pi * 2 * t)
        p['lh'] = (-48, -110)
        p['rh'] = (70, -150 + 6 * s)
        p['lf'] = (-34, 0)
        p['rf'] = (34, 0)
        p['look'] = (1, 0)
    elif pose == 'swing':
        # golpe de bate: phase 0..1 dentro de t
        u = clamp(phase)
        a = lerp(-2.4, 0.8, ease_out(u))
        p['rh'] = (math.cos(a) * 110, -120 + math.sin(a) * 80)
        p['lh'] = (math.cos(a) * 90 - 10, -115 + math.sin(a) * 70)
        p['lean'] = lerp(-0.15, 0.25, u)
        p['lf'] = (-36, 0)
        p['rf'] = (36, 0)
        p['look'] = (1, 0)
    elif pose == 'throw':
        u = clamp(phase)
        a = lerp(-2.6, 0.4, ease_out(u))
        p['rh'] = (math.cos(a) * 100, -150 + math.sin(a) * 70)
        p['lh'] = (70, -120)
        p['lean'] = lerp(-0.12, 0.18, u)
        p['lf'] = (-34, 0)
        p['rf'] = (34, 0)
        p['look'] = (1, 0)
    elif pose == 'cheer':
        s = math.sin(2 * math.pi * 2 * t + phase)
        p['hop'] = -30 * abs(s)
        p['lh'] = (-90, -240 + 15 * s)
        p['rh'] = (90, -240 - 15 * s)
        p['squash'] = -0.06 * abs(s)
        p['look'] = (0, -0.2)
    return p


# ----------------------------------------------------------------------------
# JENGI - el niño de jengibre
# ----------------------------------------------------------------------------
def candy_cane(ctx, x, y, ang, L=150, w=16, lw=5):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    pts = [(0, 0), (L * 0.75, 0)]
    for k in range(9):
        a = math.pi / 2 - k * math.pi / 8
        pts.append((L * 0.75 + math.cos(a + math.pi / 2) * -w * 1.6 * -1 + 0, 0))
    # tallo recto + gancho
    ctx.move_to(-L * 0.25, 0)
    ctx.line_to(L * 0.70, 0)
    ctx.arc_negative(L * 0.70, -w * 1.7, w * 1.7, math.pi / 2, -math.pi * 0.9)
    path = ctx.copy_path()
    ctx.new_path()
    for width, c in ((w + 2 * lw, INK), (w, WHITE)):
        ctx.append_path(path)
        col(ctx, c)
        ctx.set_line_width(width)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()
    # rayas rojas
    ctx.save()
    ctx.append_path(path)
    ctx.set_line_width(w)
    ctx.set_dash([w * 0.7, w * 0.9], G.boil * 0.0)
    col(ctx, RED)
    ctx.stroke()
    ctx.restore()
    ctx.restore()


def jengi(ctx, x, y, s=1.0, face=1, pose='idle', t=0.0, expr='happy', phase=0.0, cane=False,
          pose_override=None, alpha=1.0):
    p = hero_pose(pose, t, phase)
    if pose_override:
        p.update(pose_override)
    lw = 5.5
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * face, s)
    ctx.translate(0, p['hop'])
    sq = p['squash']
    ctx.scale(1 + sq * 0.6, 1 - sq)
    lean = p['lean']

    def rot(pt, pivot=(0, -78)):
        dx, dy = pt[0] - pivot[0], pt[1] - pivot[1]
        c, sn = math.cos(lean), math.sin(lean)
        return (pivot[0] + dx * c - dy * sn, pivot[1] + dx * sn + dy * c)

    hipL, hipR = (-16, -74), (16, -74)
    shL, shR = rot((-36, -138)), rot((36, -138))
    head = rot((0, -215))
    bodyc = rot((0, -112))

    # pierna trasera + brazo trasero
    hose(ctx, hipL, (p['lf'][0], p['lf'][1] - 18), 10, 17, GINGER, lw)
    line(ctx, [(p['lf'][0] - 12, p['lf'][1] - 28), (p['lf'][0] - 4, p['lf'][1] - 33),
               (p['lf'][0] + 4, p['lf'][1] - 28), (p['lf'][0] + 12, p['lf'][1] - 33)], 3.5, WHITE)
    boot(ctx, p['lf'][0], p['lf'][1], 1, 1.0, INK, lw)
    ang = hose(ctx, shL, p['lh'], -18, 15, GINGER, lw)
    glove(ctx, p['lh'][0], p['lh'][1], ang, 26, lw)

    hose(ctx, hipR, (p['rf'][0], p['rf'][1] - 18), -10, 17, GINGER, lw)
    line(ctx, [(p['rf'][0] - 12, p['rf'][1] - 28), (p['rf'][0] - 4, p['rf'][1] - 33),
               (p['rf'][0] + 4, p['rf'][1] - 28), (p['rf'][0] + 12, p['rf'][1] - 33)], 3.5, WHITE)
    boot(ctx, p['rf'][0], p['rf'][1], 1, 1.0, INK, lw)

    # cuerpo
    blob(ctx, bodyc[0], bodyc[1], 46, 52, GINGER, lw, rot=lean, seed=2)
    # icing en el borde del cuerpo
    ctx.save()
    pts = blob_pts(bodyc[0], bodyc[1], 38, 44, 40, rot=lean, wob=0.4, seed=3,
                   rfun=lambda a, k: 1 + 0.05 * math.sin(a * 14))
    catmull(ctx, pts)
    col(ctx, WHITE, 0.9)
    ctx.set_line_width(3.0)
    ctx.set_dash([10, 8])
    ctx.stroke()
    ctx.restore()
    for k in range(3):
        bx, by = rot((4, -132 + k * 22))
        blob(ctx, bx, by, 8.5, 8, RED, 4, seed=10 + k, n=10)
        circle(ctx, bx - 2.5, by - 3, 2.4, WHITE, 0, 0.8)

    # cabeza
    hx, hy = head
    blob(ctx, hx, hy, 66, 62, GINGER, lw, seed=5, n=26)
    # luz y sombra
    ctx.save()
    catmull(ctx, blob_pts(hx, hy, 66, 62, 26, seed=5))
    ctx.clip()
    blob(ctx, hx - 26, hy + 34, 70, 40, GINGER_D, 0, seed=6, a=0.35)
    blob(ctx, hx + 22, hy - 30, 26, 14, GINGER_L, 0, seed=7, rot=-0.4, a=0.8)
    ctx.restore()
    # glaseado ondulado en el borde de la cabeza
    pts = blob_pts(hx, hy, 55, 51, 64, wob=0.3, seed=8,
                   rfun=lambda a, k: 1 + 0.045 * math.sin(a * 16))
    catmull(ctx, pts)
    col(ctx, WHITE)
    ctx.set_line_width(4.0)
    ctx.stroke()

    # cara
    lx, ly = p['look']
    bl = p['blink']
    if expr == 'shock':
        eye(ctx, hx + 2, hy - 14, 17, 26, 0, -0.2, 0, lw)
        eye(ctx, hx + 38, hy - 14, 15, 24, 0, -0.2, 0, lw)
        blob(ctx, hx + 20, hy + 28, 13, 17, MOUTH, lw, seed=9)
    elif expr == 'angry' or expr == 'determined':
        eye(ctx, hx + 2, hy - 10, 15, 21, lx, ly, bl, lw)
        eye(ctx, hx + 38, hy - 10, 13, 20, lx, ly, bl, lw)
        line(ctx, [(hx - 16, hy - 40), (hx + 16, hy - 30)], 6)
        line(ctx, [(hx + 26, hy - 30), (hx + 52, hy - 38)], 6)
        mouth(ctx, hx + 22, hy + 22, 40, 0.35 if expr == 'angry' else 0.15, -0.3 if expr == 'angry' else 0.6,
              lw, teeth=True, tongue=False)
    else:
        eye(ctx, hx + 2, hy - 12, 15, 22, lx, ly, bl, lw)
        eye(ctx, hx + 38, hy - 12, 13, 21, lx, ly, bl, lw)
        op = 0.75 if expr == 'happy' else 0.4
        mouth(ctx, hx + 20, hy + 18, 62, op, 1.0, lw, teeth=True)
    circle(ctx, hx - 22, hy + 14, 9, BLUSH, 0, 0.75)
    circle(ctx, hx + 56, hy + 12, 8, BLUSH, 0, 0.75)
    # pajarita
    nx, ny = rot((2, -158))
    poly(ctx, [(nx, ny), (nx - 22, ny - 12), (nx - 22, ny + 12)], RED, 4.5, smooth=False, seed=12)
    poly(ctx, [(nx, ny), (nx + 22, ny - 12), (nx + 22, ny + 12)], RED, 4.5, smooth=False, seed=13)
    blob(ctx, nx, ny, 6, 6, RED_D, 4, seed=14, n=8)

    # brazo delantero
    ang = hose(ctx, shR, p['rh'], 18, 15, GINGER, lw)
    if cane:
        candy_cane(ctx, p['rh'][0], p['rh'][1], p.get('cane_ang', -1.75), 150, 14, 4.5)
    glove(ctx, p['rh'][0], p['rh'][1], ang, 26, lw, fist=cane)
    ctx.restore()


# ----------------------------------------------------------------------------
# NIEVE - la niña de nieve
# ----------------------------------------------------------------------------
def scarf_tail(ctx, x, y, t, length=120, wind=1.0, lw=4.5, dirx=-1):
    pts_c = []
    for k in range(9):
        u = k / 8
        px = x + dirx * u * length
        py = y + u * 20 + math.sin(t * 9 + u * 5) * 14 * u * wind
        pts_c.append((px, py))
    wdt = 13
    left, right = [], []
    for i, (px, py) in enumerate(pts_c):
        j = min(i, len(pts_c) - 2)
        dx = pts_c[j + 1][0] - pts_c[j][0]
        dy = pts_c[j + 1][1] - pts_c[j][1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        left.append((px + nx * wdt, py + ny * wdt))
        right.append((px - nx * wdt, py - ny * wdt))
    # rayas
    for i in range(len(pts_c) - 1):
        quad = [left[i], left[i + 1], right[i + 1], right[i]]
        ctx.move_to(*quad[0])
        for q in quad[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        col(ctx, RED if i % 2 == 0 else WHITE)
        ctx.fill()
    outline = left + right[::-1]
    ctx.move_to(*outline[0])
    for q in outline[1:]:
        ctx.line_to(*q)
    ctx.close_path()
    col(ctx, INK)
    ctx.set_line_width(lw)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()
    # flecos
    ex, ey = pts_c[-1]
    for k in range(4):
        line(ctx, [(ex + dirx * 2, ey - 10 + k * 7), (ex + dirx * 16, ey - 12 + k * 8)], 3)


def nieve(ctx, x, y, s=1.0, face=1, pose='idle', t=0.0, expr='happy', phase=0.0, sling=False,
          pose_override=None):
    p = hero_pose(pose, t, phase + 0.7)
    if pose_override:
        p.update(pose_override)
    lw = 5.5
    tt = twos(t)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * face, s)
    ctx.translate(0, p['hop'])
    sq = p['squash']
    ctx.scale(1 + sq * 0.6, 1 - sq)
    lean = p['lean']

    def rot(pt, pivot=(0, -60)):
        dx, dy = pt[0] - pivot[0], pt[1] - pivot[1]
        c, sn = math.cos(lean), math.sin(lean)
        return (pivot[0] + dx * c - dy * sn, pivot[1] + dx * sn + dy * c)

    lf = (p['lf'][0] * 0.8, p['lf'][1] * 0.8)
    rf = (p['rf'][0] * 0.8, p['rf'][1] * 0.8)
    lh = (p['lh'][0], p['lh'][1] * 0.95)
    rh = (p['rh'][0], p['rh'][1] * 0.95)

    # bufanda (detrás)
    nk = rot((0, -142))
    wind = 1.6 if pose == 'run' else 0.8
    scarf_tail(ctx, nk[0] - 10, nk[1] + 4, tt * 1.0 + phase, 125 if pose == 'run' else 95, wind, lw)

    # brazo trasero (ramita)
    shL, shR = rot((-46, -112)), rot((46, -112))
    ang = hose(ctx, shL, lh, -14, 9, BROWN, lw)
    glove(ctx, lh[0], lh[1], ang, 22, lw)
    # piernas cortitas con botitas rojas
    for f, hip, bend in ((lf, (-18, -45), 8), (rf, (18, -45), -8)):
        hose(ctx, hip, (f[0], f[1] - 14), bend, 15, SNOW, lw)
        blob(ctx, f[0] + 8, f[1] - 11, 22, 14, RED, lw, seed=f[0] * 0.3, n=14)
        line(ctx, [(f[0] - 8, f[1] - 22), (f[0] + 12, f[1] - 24)], 3.0, WHITE, 0.9)

    # cuerpo bola de nieve
    bc = rot((0, -92))
    blob(ctx, bc[0], bc[1], 58, 56, SNOW, lw, seed=21, n=24)
    ctx.save()
    catmull(ctx, blob_pts(bc[0], bc[1], 58, 56, 24, seed=21))
    ctx.clip()
    blob(ctx, bc[0] - 34, bc[1] + 30, 60, 42, SNOW_SH, 0, seed=22, a=0.75)
    ctx.restore()
    for k in range(2):
        cx, cy = rot((10, -108 + k * 28))
        blob(ctx, cx, cy, 7, 7, INK, 0, seed=23 + k, n=8)

    # cabeza
    hx, hy = rot((0, -186))
    blob(ctx, hx, hy, 50, 47, SNOW, lw, seed=25, n=22)
    ctx.save()
    catmull(ctx, blob_pts(hx, hy, 50, 47, 22, seed=25))
    ctx.clip()
    blob(ctx, hx - 28, hy + 26, 46, 30, SNOW_SH, 0, seed=26, a=0.6)
    ctx.restore()
    # vuelta de la bufanda al cuello
    blob(ctx, nk[0], nk[1], 52, 15, RED, lw, seed=27, n=16)
    for k in range(-2, 3):
        line(ctx, [(nk[0] + k * 18 - 4, nk[1] - 12), (nk[0] + k * 18 + 4, nk[1] + 12)], 6, WHITE, 0.95)
    blob(ctx, nk[0], nk[1], 52, 15, None, lw, seed=27, n=16)

    # gorro verde con pompón
    ctx.save()
    ctx.move_to(hx - 48, hy - 30)
    ctx.curve_to(hx - 44, hy - 92, hx + 44, hy - 92, hx + 48, hy - 30)
    ctx.close_path()
    fill_stroke(ctx, GREEN, lw)
    ctx.restore()
    blob(ctx, hx, hy - 32, 52, 11, CREAM, lw, seed=29, n=16)
    for k in range(-4, 5):
        line(ctx, [(hx + k * 11, hy - 40), (hx + k * 11, hy - 24)], 2.5, (0.75, 0.70, 0.60))
    blob(ctx, hx + 6, hy - 88, 15, 14, RED, lw, seed=30, n=12)

    # cara
    lx, ly = p['look']
    bl = p['blink']
    if expr == 'shock':
        eye(ctx, hx - 2, hy, 14, 20, 0, -0.2, 0, lw, lashes=True)
        eye(ctx, hx + 30, hy, 12, 19, 0, -0.2, 0, lw, lashes=True)
        blob(ctx, hx + 14, hy + 34, 9, 12, MOUTH, lw - 1, seed=31)
    elif expr in ('angry', 'determined'):
        eye(ctx, hx - 2, hy + 2, 13, 17, lx, ly, bl, lw, lashes=True)
        eye(ctx, hx + 30, hy + 2, 11, 16, lx, ly, bl, lw, lashes=True)
        line(ctx, [(hx - 16, hy - 20), (hx + 10, hy - 12)], 5)
        line(ctx, [(hx + 22, hy - 12), (hx + 42, hy - 18)], 5)
        mouth(ctx, hx + 14, hy + 32, 26, 0.12, 0.5, lw - 1, tongue=False)
    else:
        eye(ctx, hx - 2, hy, 13, 18, lx, ly, bl, lw, lashes=True)
        eye(ctx, hx + 30, hy, 11, 17, lx, ly, bl, lw, lashes=True)
        mouth(ctx, hx + 14, hy + 30, 34, 0.55 if expr == 'happy' else 0.2, 1.0, lw - 1)
    # nariz de zanahoria
    poly(ctx, [(hx + 10, hy + 8), (hx + 62, hy + 16), (hx + 10, hy + 22)], ORANGE, lw - 1, smooth=False,
         seed=33, wob=0.6)
    line(ctx, [(hx + 26, hy + 10), (hx + 28, hy + 19)], 2.5)
    line(ctx, [(hx + 40, hy + 12), (hx + 41, hy + 18)], 2.5)
    circle(ctx, hx - 20, hy + 20, 7, BLUSH, 0, 0.8)
    circle(ctx, hx + 44, hy + 26, 6, BLUSH, 0, 0.8)

    # brazo delantero
    ang = hose(ctx, shR, rh, 14, 9, BROWN, lw)
    if sling:
        slingshot(ctx, rh[0], rh[1], ang)
    glove(ctx, rh[0], rh[1], ang, 22, lw, fist=sling)
    ctx.restore()


def slingshot(ctx, x, y, ang, lw=4.5):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    # horquilla de bastón de caramelo
    for sgn in (-1, 1):
        line(ctx, [(0, 0), (30, sgn * 6), (52, sgn * 22)], 13, INK)
        line(ctx, [(0, 0), (30, sgn * 6), (52, sgn * 22)], 8, WHITE)
        for k in range(3):
            u = 0.25 + k * 0.28
            line(ctx, [(u * 52 - 3, sgn * (u * 22) - 2), (u * 52 + 3, sgn * (u * 22) + 2)], 5, RED)
    line(ctx, [(52, -22), (40, 0), (52, 22)], 2.5, BROWN)
    ctx.restore()


def peppermint(ctx, x, y, r=16, rot=0.0, lw=4):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    circle(ctx, 0, 0, r, WHITE, lw)
    for k in range(4):
        a = k * math.pi / 2
        ctx.move_to(0, 0)
        ctx.arc(0, 0, r - lw * 0.4, a, a + math.pi / 4)
        ctx.close_path()
        col(ctx, RED)
        ctx.fill()
    ctx.restore()


# ----------------------------------------------------------------------------
# KRAMPUS
# ----------------------------------------------------------------------------
def horn(ctx, x, y, side, s=1.0, lw=6.0, curl=1.0):
    """Cuerno de carnero en espiral: polígono afinado a lo largo de una espiral."""
    R = 105 * s
    cx, cy = x + side * 74 * s, y - 74 * s
    phi0 = math.atan2(y - cy, (x - cx) * side)
    n = 30
    cen = []
    for k in range(n):
        u = k / (n - 1)
        phi = phi0 + u * 5.6 * curl
        r = R * (1 - 0.62 * u)
        cen.append((cx + side * r * math.cos(phi), cy + r * math.sin(phi)))
    left, right = [], []
    for i, (px, py) in enumerate(cen):
        j = min(i, n - 2)
        dx, dy = cen[j + 1][0] - cen[j][0], cen[j + 1][1] - cen[j][1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        w = 30 * s * (1 - i / n) ** 0.8 + 3
        left.append((px + nx * w, py + ny * w))
        right.append((px - nx * w, py - ny * w))
    pts = left + right[::-1]
    ctx.move_to(*pts[0])
    for q in pts[1:]:
        ctx.line_to(*q)
    ctx.close_path()
    fill_stroke(ctx, HORN, lw)
    for i in range(2, n - 3, 3):
        line(ctx, [left[i], right[i]], lw * 0.55, HORN_D)


def chain(ctx, pts_fn, n, lw=4.0, bells=(), t=0.0):
    """Cadena a lo largo de una curva paramétrica pts_fn(u)->(x,y)."""
    for i in range(n):
        u = (i + 0.5) / n
        x, y = pts_fn(u)
        x2, y2 = pts_fn(min(1, u + 0.01))
        a = math.atan2(y2 - y, x2 - x)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(a)
        if i % 2 == 0:
            ctx.scale(1, 0.55)
        else:
            ctx.scale(1, 0.25)
        ctx.arc(0, 0, 13, 0, 2 * math.pi)
        ctx.restore()
        col(ctx, (0.55, 0.55, 0.60))
        ctx.fill_preserve()
        col(ctx, INK)
        ctx.set_line_width(lw)
        ctx.stroke()
    for b in bells:
        x, y = pts_fn(b)
        sw = math.sin(t * 8 + b * 20) * 0.35
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(sw)
        poly(ctx, [(-14, 26), (-10, 6), (0, 0), (10, 6), (14, 26)], GOLD, lw, seed=b * 9)
        circle(ctx, 0, 28, 5, GOLD_D, lw * 0.7)
        ctx.restore()


def present(ctx, x, y, w, h, c, ribbon, rot=0.0, lw=5.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    poly(ctx, [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)], c, lw, smooth=False,
         seed=x * 0.1)
    ctx.rectangle(-w * 0.09, -h / 2, w * 0.18, h)
    col(ctx, ribbon)
    ctx.fill()
    ctx.rectangle(-w / 2, -h * 0.09, w, h * 0.18)
    ctx.fill()
    blob(ctx, -w * 0.16, -h / 2 - 8, w * 0.16, 9, ribbon, lw * 0.7, rot=0.4, seed=x)
    blob(ctx, w * 0.16, -h / 2 - 8, w * 0.16, 9, ribbon, lw * 0.7, rot=-0.4, seed=x + 1)
    ctx.restore()


PRESENT_COLORS = [(RED, GOLD), (GREEN, RED), ((0.25, 0.42, 0.75), WHITE), (GOLD, GREEN),
                  ((0.62, 0.30, 0.62), GOLD), (CREAM, RED)]


def krampus(ctx, x, y, s=1.0, face=1, t=0.0, grin=0.6, lh=None, rh=None, tongue=1.0,
            eyes_glow=0.0, basket=True, stomp=0.0, look=(0.0, 0.3), lean=0.0, mouth_open=None,
            hop=0.0, expr='evil', bell_in_hand=None):
    tt = twos(t)
    lw = 7.0
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * face, s)
    ctx.translate(0, hop)
    breathe = math.sin(tt * 2.2) * 6

    def rot(pt, pivot=(0, -300)):
        dx, dy = pt[0] - pivot[0], pt[1] - pivot[1]
        c, sn = math.cos(lean), math.sin(lean)
        return (pivot[0] + dx * c - dy * sn, pivot[1] + dx * sn + dy * c)

    shL, shR = rot((-112, -505 + breathe)), rot((112, -505 + breathe))
    if lh is None:
        lh = (-190 + math.sin(tt * 2) * 10, -330)
    if rh is None:
        rh = (190 - math.sin(tt * 2) * 10, -330)

    # piernas largas: pezuña y bota
    st = stomp
    lfoot = (-75, 0 - 40 * max(0, st))
    rfoot = (75, 0 - 40 * max(0, -st))
    hose(ctx, rot((-45, -300)), (lfoot[0], lfoot[1] - 30), 30, 26, FUR, lw)
    hose(ctx, rot((45, -300)), (rfoot[0], rfoot[1] - 30), -30, 26, FUR, lw)
    # pezuña hendida
    poly(ctx, [(lfoot[0] - 34, lfoot[1]), (lfoot[0] - 26, lfoot[1] - 40), (lfoot[0] + 20, lfoot[1] - 40),
               (lfoot[0] + 30, lfoot[1])], (0.12, 0.10, 0.12), lw, seed=51)
    line(ctx, [(lfoot[0] - 2, lfoot[1] - 2), (lfoot[0] - 4, lfoot[1] - 26)], lw * 0.7, (0.5, 0.5, 0.55))
    boot(ctx, rfoot[0], rfoot[1], 1, 1.9, INK, lw)

    # canasta de mimbre con regalos (detrás)
    if basket:
        bx, by = rot((-150, -470))
        for i, (c1, c2) in enumerate(PRESENT_COLORS[:4]):
            present(ctx, bx - 50 + i * 34, by - 130 + (i % 2) * 18, 54, 46, c1, c2, rot=(i - 1.5) * 0.25)
        if bell_in_hand is None and False:
            pass
        poly(ctx, [(bx - 85, by - 110), (bx + 85, by - 110), (bx + 70, by + 120), (bx - 70, by + 120)],
             (0.62, 0.42, 0.20), lw, smooth=False, seed=52)
        for k in range(6):
            yy = by - 85 + k * 38
            line(ctx, [(bx - 80 + k * 2, yy), (bx - 30, yy + 8), (bx + 20, yy - 4), (bx + 78 - k * 2, yy + 6)],
                 3.5, (0.40, 0.25, 0.10))
        for k in range(5):
            xx = bx - 60 + k * 30
            line(ctx, [(xx, by - 105), (xx + 2, by + 115)], 3, (0.40, 0.25, 0.10))

    # brazo trasero
    ang = hose(ctx, shL, lh, 60, 30, FUR, lw)
    glove(ctx, lh[0], lh[1], ang, 40, lw)

    # torso peludo
    tc = rot((0, -420 + breathe * 0.5))
    fur = lambda a, k: 1.0 + (0.09 if k % 2 == 0 else -0.02) + 0.03 * math.sin(a * 3)
    blob(ctx, tc[0], tc[1], 128, 165, FUR, lw, rot=lean, seed=53, n=44, rfun=fur)
    blob(ctx, tc[0] + 30, tc[1] + 40, 62, 90, FUR_L, 0, rot=lean, seed=54, n=30, rfun=fur, a=0.85)
    # cadena cruzada con campanillas
    p0 = rot((-120, -560))
    p1 = rot((110, -300))
    chain(ctx, lambda u: (lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u) + math.sin(u * math.pi) * 40),
          13, 4.0, bells=(0.25, 0.55, 0.85), t=tt)

    # cabeza de cabra
    hx, hy = rot((10, -640 + breathe))
    # orejas caídas
    blob(ctx, hx - 95, hy - 20, 48, 18, FUR, lw, rot=0.5, seed=55)
    blob(ctx, hx + 105, hy - 20, 48, 18, FUR, lw, rot=-0.5, seed=56)
    # cuernos
    horn(ctx, hx - 60, hy - 50, -1, 1.0, lw)
    horn(ctx, hx + 70, hy - 50, 1, 1.0, lw)
    # cabeza alargada con barba
    head_r = lambda a, k: 1.0 + (0.06 if k % 2 == 0 else 0) + (0.38 if math.sin(a) > 0.55 else 0) * math.sin(a)
    blob(ctx, hx, hy, 92, 100, FUR, lw, seed=57, n=36, rfun=head_r)
    # hocico claro
    blob(ctx, hx + 18, hy + 45, 70, 50, FUR_L, lw, seed=58)
    # ojos amarillos
    eg = eyes_glow
    if eg > 0:
        glow(ctx, hx - 15, hy - 30, 90, LIME, 0.5 * eg)
        glow(ctx, hx + 55, hy - 30, 90, LIME, 0.5 * eg)
    yel = mixc((0.98, 0.85, 0.22), LIME, eg)
    lx, ly = look
    if expr == 'dizzy':
        for ex in (hx - 15, hx + 55):
            circle(ctx, ex, hy - 30, 26, yel, lw)
            ctx.save()
            ctx.translate(ex, hy - 30)
            ctx.rotate(tt * 8)
            for k in range(3):
                ctx.arc(0, 0, 6 + k * 6, k, k + 3.5)
                col(ctx, INK)
                ctx.set_line_width(4)
                ctx.stroke()
            ctx.restore()
    else:
        eye(ctx, hx - 15, hy - 30, 26, 32, lx, ly, 0, lw, pupil=0.42, white=yel)
        eye(ctx, hx + 55, hy - 30, 24, 30, lx, ly, 0, lw, pupil=0.42, white=yel)
        if expr == 'evil':
            line(ctx, [(hx - 50, hy - 78), (hx - 5, hy - 55)], 12)
            line(ctx, [(hx + 30, hy - 55), (hx + 85, hy - 80)], 12)
        elif expr == 'scared':
            line(ctx, [(hx - 45, hy - 62), (hx - 5, hy - 80)], 10)
            line(ctx, [(hx + 30, hy - 80), (hx + 80, hy - 62)], 10)
    # nariz
    blob(ctx, hx + 40, hy + 20, 18, 11, INK, 0, seed=59)
    # boca enorme con dientes cuadrados
    mo = grin if mouth_open is None else mouth_open
    mouth(ctx, hx + 22, hy + 58, 130, mo, 1.0 if expr != 'scared' else -0.6, lw, tongue=False, square_teeth=6)
    # lengua larguísima
    if tongue > 0 and expr != 'scared':
        tpts = []
        for k in range(10):
            u = k / 9
            tpts.append((hx + 50 + u * 30 + math.sin(tt * 6 + u * 4) * 16 * u,
                         hy + 70 + u * 140 * tongue))
        for width, c in ((30 + 2 * lw, INK), (30, TONGUE)):
            catmull(ctx, tpts, False)
            col(ctx, c)
            ctx.set_line_width(width)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
        line(ctx, tpts[2:8], 3, RED_D, 0.8)
    # barba de chivo
    poly(ctx, [(hx - 10, hy + 108), (hx + 40, hy + 108), (hx + 18, hy + 170)], FUR, lw, seed=60)

    # brazo delantero
    ang = hose(ctx, shR, rh, -60, 30, FUR, lw)
    if bell_in_hand is not None:
        golden_bell(ctx, rh[0] + 20, rh[1] + 50, 0.9, bell_in_hand)
    glove(ctx, rh[0], rh[1], ang, 40, lw, fist=bell_in_hand is not None)
    ctx.restore()


def golden_bell(ctx, x, y, s=1.0, sw=0.0, lw=6.0, shine=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(sw)
    ctx.scale(s, s)
    if shine > 0:
        glow(ctx, 0, 10, 140, GOLD, 0.5 * shine)
    pts = [(-62, 60), (-48, 10), (-38, -36), (-20, -58), (0, -62), (20, -58), (38, -36), (48, 10), (62, 60),
           (40, 70), (0, 74), (-40, 70)]
    poly(ctx, pts, GOLD, lw, seed=71)
    blob(ctx, -18, -20, 10, 28, (1.0, 0.95, 0.70), 0, rot=0.3, seed=72, a=0.85)
    line(ctx, [(-52, 42), (0, 50), (52, 42)], lw * 0.6, GOLD_D)
    circle(ctx, 4 * math.sin(sw * 3), 80, 14, GOLD_D, lw)
    # moño rojo
    blob(ctx, -26, -66, 24, 13, RED, lw * 0.8, rot=0.3, seed=73)
    blob(ctx, 26, -66, 24, 13, RED, lw * 0.8, rot=-0.3, seed=74)
    blob(ctx, 0, -66, 10, 10, RED_D, lw * 0.8, seed=75)
    ctx.restore()


# ----------------------------------------------------------------------------
# CORONEL CASCANUECES (jefe 1)
# ----------------------------------------------------------------------------
def nutcracker(ctx, x, y, s=1.0, face=-1, t=0.0, jaw=0.0, march=True, hurt=0.0, broken=0.0, look=(-0.5, 0)):
    tt = twos(t)
    lw = 7.0
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * face, s)
    ph = tt * 2 * math.pi * 1.2
    step = math.sin(ph) if march else 0
    bob = -abs(step) * 14
    ctx.translate(0, bob)
    blue = (0.22, 0.32, 0.62)
    # piernas rígidas
    for side, sgn in ((-1, 1), (1, -1)):
        lift = max(0, sgn * step) * 50
        lx = side * 45
        poly(ctx, [(lx - 26, -260), (lx + 26, -260), (lx + 24, -60 - lift), (lx - 24, -60 - lift)], blue, lw,
             smooth=False, seed=80 + side)
        poly(ctx, [(lx - 30, -70 - lift), (lx + 30, -70 - lift), (lx + 44, 0 - lift), (lx - 32, 0 - lift)], INK, lw,
             smooth=False, seed=82 + side)
    # casaca roja
    poly(ctx, [(-95, -470), (95, -470), (110, -240), (-110, -240)], RED, lw, smooth=False, seed=84)
    for k in range(4):
        circle(ctx, 0, -440 + k * 55, 10, GOLD, lw * 0.6)
    poly(ctx, [(-95, -470), (-60, -470), (110, -270), (75, -255)], WHITE, lw * 0.8, smooth=False, seed=85)
    # cinturón
    ctx.rectangle(-110, -270, 220, 30)
    fill_stroke(ctx, INK, lw)
    ctx.rectangle(-16, -272, 32, 34)
    fill_stroke(ctx, GOLD, lw * 0.6)
    # charreteras
    for side in (-1, 1):
        blob(ctx, side * 105, -465, 34, 16, GOLD, lw, seed=86 + side)
        for k in range(5):
            line(ctx, [(side * 105 - 24 + k * 12, -452), (side * 105 - 24 + k * 12, -425)], 4, GOLD_D)
    # brazos rígidos (madera)
    sw = math.sin(ph) * 0.35
    for side in (-1, 1):
        ctx.save()
        ctx.translate(side * 112, -455)
        ctx.rotate(side * sw)
        poly(ctx, [(-18, 0), (18, 0), (16, 170), (-16, 170)], RED, lw, smooth=False, seed=88 + side)
        glove(ctx, 0, 190, math.pi / 2, 30, lw, fist=True)
        ctx.restore()
    # cabeza cuadrada
    hy = -560
    ctx.save()
    ctx.translate(0, hy)
    ctx.rotate(math.sin(tt * 30) * 0.05 * hurt)
    poly(ctx, [(-80, -95), (80, -95), (82, 60), (-82, 60)], (0.98, 0.84, 0.70), lw, smooth=False, seed=90)
    # ojos
    eye(ctx, -32, -45, 22, 25, look[0], look[1], 0, lw, pupil=0.5)
    eye(ctx, 32, -45, 22, 25, look[0], look[1], 0, lw, pupil=0.5)
    line(ctx, [(-62, -85), (-10, -68)], 12)
    line(ctx, [(10, -68), (62, -85)], 12)
    blob(ctx, -55, -5, 14, 9, BLUSH, 0, seed=91, a=0.8)
    blob(ctx, 55, -5, 14, 9, BLUSH, 0, seed=92, a=0.8)
    # bigote
    poly(ctx, [(-70, 0), (-10, -18), (0, -6), (10, -18), (70, 0), (40, 14), (0, 4), (-40, 14)], WHITE, lw,
         seed=93)
    # mandíbula articulada
    jy = 20 + jaw * 120
    ctx.rectangle(-60, 20, 120, jy - 20 + 10)
    col(ctx, MOUTH)
    ctx.fill()
    for k in range(5):
        ctx.rectangle(-55 + k * 22, 18, 18, 18)
        fill_stroke(ctx, WHITE, 3)
        ctx.rectangle(-55 + k * 22, jy - 14, 18, 18)
        fill_stroke(ctx, WHITE, 3)
    poly(ctx, [(-70, jy), (70, jy), (66, jy + 60), (-66, jy + 60)], (0.98, 0.84, 0.70), lw, smooth=False, seed=94)
    poly(ctx, [(-66, jy + 10), (66, jy + 10), (40, jy + 110), (-40, jy + 110)], WHITE, lw, seed=95)
    ctx.restore()
    # gorro alto (busby)
    if broken < 0.5:
        poly(ctx, [(-90, -650), (90, -650), (80, -860), (-80, -860)], INK, lw, seed=96)
        ctx.rectangle(-92, -668, 184, 26)
        fill_stroke(ctx, GOLD, lw * 0.7)
        blob(ctx, 60, -880, 20, 48, WHITE, lw, rot=0.3, seed=97)
        circle(ctx, 0, -760, 22, GOLD, lw * 0.7)
    ctx.restore()


# ----------------------------------------------------------------------------
# ESCARCHA - el muñeco de nieve malvado (jefe 2)
# ----------------------------------------------------------------------------
def frost_man(ctx, x, y, s=1.0, face=-1, t=0.0, blow=0.0, melt=0.0, hurt=0.0, arm_up=0.0):
    tt = twos(t)
    lw = 7.0
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * face, s * (1 - melt * 0.75))
    ctx.scale(1 + melt * 0.6, 1)
    wob = math.sin(tt * 3) * 8
    icy = (0.86, 0.93, 1.0)
    shade = (0.55, 0.70, 0.88)
    # brazos de rama
    for side in (-1, 1):
        ax0, ay0 = side * 140, -420
        up = arm_up if side == 1 else arm_up * 0.3
        ax1, ay1 = side * 300, -420 - 200 * up + math.sin(tt * 4 + side) * 20
        line(ctx, [(ax0, ay0), ((ax0 + ax1) / 2, (ay0 + ay1) / 2 - 20), (ax1, ay1)], 18, INK)
        line(ctx, [(ax0, ay0), ((ax0 + ax1) / 2, (ay0 + ay1) / 2 - 20), (ax1, ay1)], 10, BROWN)
        for k in (-1, 1):
            line(ctx, [(ax1, ay1), (ax1 + side * 40, ay1 + k * 34)], 14, INK)
            line(ctx, [(ax1, ay1), (ax1 + side * 40, ay1 + k * 34)], 7, BROWN)
    # tres bolas
    for (cy, r, sd) in ((-150, 170, 101), (-410, 135, 102), (-620 + wob * 0.5, 110, 103)):
        blob(ctx, 0, cy, r * 1.05, r, icy, lw, seed=sd, n=28)
        ctx.save()
        catmull(ctx, blob_pts(0, cy, r * 1.05, r, 28, seed=sd))
        ctx.clip()
        blob(ctx, -r * 0.55, cy + r * 0.55, r * 0.95, r * 0.6, shade, 0, seed=sd + 10, a=0.7)
        ctx.restore()
    # botones de carbón
    for k in range(3):
        blob(ctx, 0, -470 + k * 60, 14, 13, INK, 0, seed=110 + k)
    hy = -620 + wob * 0.5
    # ojos enojados
    eye(ctx, -40, hy - 25, 24, 28, -0.5, 0.2, 0, lw, pupil=0.5, white=(1, 1, 1), iris=None)
    eye(ctx, 40, hy - 25, 24, 28, -0.5, 0.2, 0, lw, pupil=0.5)
    line(ctx, [(-75, hy - 68), (-15, hy - 45)], 13)
    line(ctx, [(15, hy - 45), (75, hy - 68)], 13)
    # nariz de zanahoria torcida
    poly(ctx, [(-10, hy + 2), (-95, hy + 22), (-6, hy + 26)], ORANGE, lw, smooth=False, seed=112)
    # boca de carbón
    if blow > 0.1:
        blob(ctx, 10, hy + 62, 24 * blow + 10, 20 * blow + 8, MOUTH, lw, seed=113)
    else:
        for k in range(7):
            u = k / 6
            blob(ctx, -55 + u * 110, hy + 52 + math.sin(u * math.pi) * 18, 9, 8, INK, 0, seed=114 + k, n=8)
    # corona de carámbanos
    for k in range(7):
        u = k / 6
        bx = -85 + u * 170
        by = hy - 92 - math.sin(u * math.pi) * 18
        hgt = 60 + 30 * math.sin(u * math.pi)
        poly(ctx, [(bx - 16, by + 6), (bx + 16, by + 6), (bx, by - hgt)], (0.75, 0.90, 1.0), lw * 0.7,
             smooth=False, seed=120 + k)
    ctx.restore()
    if melt > 0:
        # charco
        blob(ctx, x, y - 6, 220 * s * (0.4 + melt), 30 * s * (0.3 + melt * 0.7), (0.75, 0.86, 0.98), lw,
             seed=130, a=min(1, melt * 2))


# ----------------------------------------------------------------------------
# texturas / postproceso
# ----------------------------------------------------------------------------
def smooth_noise(h, w, scale, seed):
    rng = np.random.default_rng(seed)
    gh, gw = h // scale + 2, w // scale + 2
    g = rng.random((gh, gw)).astype(np.float32)
    ys = np.linspace(0, gh - 1.001, h)
    xs = np.linspace(0, gw - 1.001, w)
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def make_paper(w=W + 200, h=H + 200, seed=3):
    """Textura de papel/acuarela para multiplicar sobre los fondos."""
    n = (smooth_noise(h, w, 180, seed) * 0.5 + smooth_noise(h, w, 60, seed + 1) * 0.3 +
         smooth_noise(h, w, 14, seed + 2) * 0.2)
    rng = np.random.default_rng(seed + 9)
    fine = rng.random((h, w)).astype(np.float32)
    v = 0.86 + 0.14 * n - 0.03 * fine
    v = np.clip(v, 0, 1)
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0] = (v * 0.97 * 255).astype(np.uint8)   # B
    arr[..., 1] = (v * 0.995 * 255).astype(np.uint8)  # G
    arr[..., 2] = (v * 255).astype(np.uint8)          # R
    arr[..., 3] = 255
    surf = cairo.ImageSurface.create_for_data(memoryview(arr), cairo.FORMAT_ARGB32, w, h)
    return surf, arr


class Post:
    def __init__(self, seed=7):
        rng = np.random.default_rng(seed)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dx = (xx - W / 2) / (W / 2)
        dy = (yy - H / 2) / (H / 2)
        r = np.sqrt(dx * dx * 0.85 + dy * dy)
        self.vig = np.clip(1.0 - 0.42 * np.clip(r - 0.45, 0, None) ** 1.6, 0, 1)[..., None].astype(np.float32)
        self.grain = [(rng.standard_normal((H // 2, W // 2)).astype(np.float32)) for _ in range(6)]
        self.tint = np.array([1.035, 1.0, 0.90], np.float32)

    def apply(self, surf, frame, flash=0.0, dark=0.0):
        buf = surf.get_data()
        a = np.ndarray((H, W, 4), np.uint8, buf)
        rgb = a[..., 2::-1].astype(np.float32) * (1.0 / 255.0)
        # gradación cálida tipo Technicolor + negros levantados
        rgb = rgb * self.tint * 0.93 + np.array([0.035, 0.025, 0.02], np.float32)
        lum = rgb.mean(axis=2, keepdims=True)
        rgb = lum + (rgb - lum) * 0.92
        g = self.grain[frame % 6]
        oy, ox = (frame * 7) % 2, (frame * 3) % 2
        g = np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)
        if oy or ox:
            g = np.roll(g, (oy * 31, ox * 57), axis=(0, 1))
        rgb += g[..., None] * 0.035
        flick = 1.0 + 0.022 * nz(frame * 1.7, 4.0)
        rgb *= self.vig * flick * (1 - dark)
        if flash > 0:
            rgb = rgb + (1.0 - rgb) * flash
        np.clip(rgb, 0, 1, out=rgb)
        return (rgb * 255).astype(np.uint8)


def film_dirt(ctx, frame):
    """Polvo, pelos y rayas del celuloide (dibujados encima de todo)."""
    rnd = lambda k: u01(frame * 13.7 + k, 9.1)
    nspecks = int(rnd(1) * 7)
    for i in range(nspecks):
        x, y = rnd(10 + i) * W, rnd(30 + i) * H
        r = 1.5 + rnd(50 + i) * 4
        c = INK if rnd(70 + i) > 0.35 else CREAM
        blob(ctx, x, y, r, r * (0.6 + rnd(90 + i)), c, 0, seed=frame + i, a=0.55, wob=0.6, n=8)
    if rnd(2) > 0.86:
        x, y = rnd(3) * W, rnd(4) * H
        line(ctx, [(x, y), (x + 12, y + 8), (x + 6, y + 22), (x + 18, y + 30)], 1.6, INK, 0.5)
    # raya vertical que persiste unos frames
    blk = frame // 20
    if u01(blk, 3.3) > 0.55:
        x = u01(blk, 5.5) * W + math.sin(frame * 0.4) * 6
        line(ctx, [(x, 0), (x + 3, H)], 1.3, CREAM, 0.35, smooth=False)


def iris(ctx, cx, cy, r):
    ctx.save()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.rectangle(-50, -50, W + 100, H + 100)
    ctx.arc(cx, cy, max(r, 0.01), 0, 2 * math.pi)
    col(ctx, (0.02, 0.01, 0.02))
    ctx.fill()
    ctx.restore()


def box_blur(a, r):
    """Desenfoque de caja separable (r en px) sobre array HxWxC float32."""
    if r < 1:
        return a
    k = 2 * r + 1
    out = a
    for axis in (0, 1):
        c = np.cumsum(out, axis=axis, dtype=np.float32)
        pad = [(0, 0)] * out.ndim
        pad[axis] = (r + 1, r)
        c = np.pad(c, pad, mode='edge')
        if axis == 0:
            c[:r + 1] = 0
            out = (c[k:] - c[:-k]) / k
        else:
            c[:, :r + 1] = 0
            out = (c[:, k:] - c[:, :-k]) / k
    return out.astype(np.float32)


def soften_surface(surf, r=2, passes=2, paper=None, paper_off=(0, 0), wash=0.0):
    """Pinta-acuarela: desenfoque suave + papel multiplicado. Devuelve nueva superficie."""
    w, h = surf.get_width(), surf.get_height()
    a = np.ndarray((h, w, 4), np.uint8, surf.get_data()).astype(np.float32)
    for _ in range(passes):
        a = box_blur(a, r)
    if paper is not None:
        py, px = paper_off
        p = paper[py:py + h, px:px + w, :3].astype(np.float32) / 255.0
        if p.shape[0] < h or p.shape[1] < w:
            p = np.pad(p, ((0, h - p.shape[0]), (0, w - p.shape[1]), (0, 0)), mode='reflect')
        a[..., :3] *= p
    if wash > 0:
        lum = a[..., :3].mean(axis=2, keepdims=True)
        a[..., :3] = lum + (a[..., :3] - lum) * (1 - wash)
    out = np.clip(a, 0, 255).astype(np.uint8)
    ns = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    np.ndarray((h, w, 4), np.uint8, ns.get_data())[...] = out
    ns.mark_dirty()
    return ns
