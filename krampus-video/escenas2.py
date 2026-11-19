"""
escenas2.py - del primer asalto al FIN.
Se registra en krampus.py mediante build(K), que recibe el módulo principal
(para reutilizar la caché de fondos pintados, cámara, plaza, etc.).
"""
import math

import cairo

import escenarios as E
from toon import (BROWN, CREAM, FUR, GOLD, GOLD_D, GREEN, GREEN_D, H, INK, LIME, MOUTH, ORANGE, PRESENT_COLORS,
                  RED, RED_D, SNOW, SNOW_SH, W, WHITE, G, back_out, blob, candy_cane, circle, clamp, col, ease,
                  ease_in, ease_out, elastic, fill_stroke, frost_man, glow, golden_bell, iris, jengi, krampus, lerp,
                  line, mixc, nieve, nutcracker, nz, peppermint, poly, present, sparkle, text, twos, u01)

K = None  # módulo principal (se fija en build)


# ----------------------------------------------------------------------------
# utilidades de acción
# ----------------------------------------------------------------------------
def arc_pos(p0, p1, u, h):
    """Trayectoria parabólica de p0 a p1 con altura h."""
    x = lerp(p0[0], p1[0], u)
    y = lerp(p0[1], p1[1], u) - math.sin(math.pi * clamp(u)) * h
    return x, y


def walnut(ctx, x, y, r=26, rot=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    blob(ctx, 0, 0, r, r * 0.85, (0.66, 0.45, 0.24), 5, seed=601)
    line(ctx, [(0, -r * 0.85), (2, 0), (0, r * 0.85)], 4, (0.35, 0.20, 0.10))
    for k in (-1, 1):
        line(ctx, [(k * r * 0.5, -r * 0.5), (k * r * 0.62, 0), (k * r * 0.5, r * 0.5)], 3, (0.45, 0.28, 0.14))
    ctx.restore()


def impact(ctx, x, y, age, s=1.0, c=GOLD):
    if age < 0 or age > 0.45:
        return
    u = age / 0.45
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * (0.6 + u), s * (0.6 + u))
    pts = []
    for k in range(16):
        a = k * math.pi / 8
        r = 70 if k % 2 == 0 else 32
        pts.append((math.cos(a) * r, math.sin(a) * r))
    poly(ctx, pts, c, 5, smooth=False, seed=age, a=1 - u)
    ctx.restore()


def pop_word(ctx, word, x, y, age, c1=GOLD, c2=RED, size=150, dur=2.6):
    if age < 0 or age > dur:
        return
    sc = back_out(age / 0.35) * (1 - ease_in((age - dur + 0.3) / 0.3))
    if sc <= 0.01:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(-0.06 + math.sin(age * 6) * 0.03)
    ctx.scale(sc, sc)
    pts = []
    for k in range(28):
        a = k * math.pi / 14 + age * 0.4
        r = (360 if k % 2 == 0 else 250) * (1 + 0.04 * math.sin(age * 20 + k))
        pts.append((math.cos(a) * r, math.sin(a) * r * 0.55))
    poly(ctx, pts, c2, 8, smooth=False, seed=7)
    text(ctx, word, 0, 0, size, 'Luckiest Guy', c1, INK, 16, shadow=INK, sdx=7, sdy=8)
    ctx.restore()


def dizzy_stars(ctx, x, y, t, r=70, n=4):
    for k in range(n):
        a = t * 5 + k * 2 * math.pi / n
        sparkle(ctx, x + math.cos(a) * r, y + math.sin(a) * r * 0.35, 20, GOLD, 1.0, rot=t * 4)


def puff_cloud(ctx, x, y, age, s=1.0, c=(0.92, 0.90, 0.95), dur=1.0, seed=0.0):
    if age < 0 or age > dur:
        return
    u = age / dur
    for k in range(7):
        a = k * 2 * math.pi / 7 + seed
        d = (40 + 110 * ease_out(u)) * s
        r = (55 + 30 * u01(k, seed)) * s * (1 - 0.5 * u)
        blob(ctx, x + math.cos(a) * d, y + math.sin(a) * d * 0.7, r, r * 0.85, c, 5, seed=seed + k, a=1 - u * 0.9)


def bell_bomb(ctx, x, y, t, s=0.45):
    golden_bell(ctx, x, y, s, math.sin(t * 20) * 0.4)
    # mecha encendida
    line(ctx, [(x, y - 70 * s), (x + 10, y - 95 * s), (x + 4, y - 115 * s)], 4, INK)
    sparkle(ctx, x + 4, y - 120 * s, 16 + 6 * math.sin(t * 40), (1, 0.8, 0.3), 1.0, rot=t * 9)


def talkw(lt, a, b):
    """Intensidad de habla (para mover la boca) entre a y b."""
    return 1.0 if a <= lt <= b else 0.0


def idea_bulb(ctx, x, y, age):
    if age < 0 or age > 1.6:
        return
    s = back_out(age / 0.3) * (1 - ease_in((age - 1.3) / 0.3))
    if s <= 0.01:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    glow(ctx, 0, 0, 110, (1, 0.95, 0.5), 0.7)
    blob(ctx, 0, 0, 40, 44, (1.0, 0.95, 0.55), 5, seed=611)
    ctx.rectangle(-18, 38, 36, 26)
    fill_stroke(ctx, (0.6, 0.6, 0.65), 5)
    for k in range(8):
        a = k * math.pi / 4
        line(ctx, [(math.cos(a) * 58, math.sin(a) * 58), (math.cos(a) * 80, math.sin(a) * 80)], 5, INK)
    ctx.restore()


# ----------------------------------------------------------------------------
# tarjetas de asalto
# ----------------------------------------------------------------------------
def make_card(l1, l2, c1, c2, dur, tc=(0.98, 0.84, 0.30)):
    def sc(ctx, lt, t):
        E.sunburst(ctx, W / 2, H / 2, lt, c1, c2, 30, 0.10)
        glow(ctx, W / 2, H / 2, 650, (1, 0.9, 0.6), 0.3)
        E.deco_frame(ctx, 40)
        E.holly(ctx, 95, 95, 1.0, 0.8)
        E.holly(ctx, W - 95, H - 95, 1.0, -2.4)
        s1 = back_out((lt - 0.2) / 0.4)
        if s1 > 0:
            text(ctx, l1, W / 2, 380, 110, 'Luckiest Guy', CREAM, INK, 14, shadow=GOLD, sdx=6, sdy=8, scale=s1)
        s2 = elastic((lt - 0.6) / 0.9)
        if s2 > 0:
            size = 140 if len(l2) < 16 else 110
            text(ctx, l2, W / 2, 610, size, 'Rye', tc, INK, 14, shadow=INK, sdx=7, sdy=8, scale=s2,
                 rot=math.sin(lt * 3) * 0.02)
        if lt < 0.5:
            iris(ctx, W / 2, H / 2, lerp(0, 1300, ease_out(lt / 0.5)))
        if lt > dur - 0.55:
            iris(ctx, W / 2, H / 2, lerp(1300, 0, ease_in((lt - dur + 0.55) / 0.5)))
        return {}
    return sc


# ----------------------------------------------------------------------------
# BOSQUE DE LOS JUGUETES
# ----------------------------------------------------------------------------
def toy_block(ctx, x, y, s, c, letter, rot=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(s, s)
    poly(ctx, [(-60, -120), (60, -120), (60, 0), (-60, 0)], c, 6, smooth=False, seed=x)
    ctx.rectangle(-46, -106, 92, 92)
    col(ctx, CREAM)
    ctx.set_line_width(5)
    ctx.stroke()
    text(ctx, letter, 0, -62, 80, 'Rye', CREAM, INK, 6)
    ctx.restore()


def forest_back():
    PX, PY = K.PAD_X, K.PAD_Y

    def d(ctx):
        ctx.translate(PX, PY)
        E.hills(ctx, 0, 700, 140, (0.76, 0.80, 0.92), 13, lw=5, pines=0.95, pine_h=110,
                pine_c=(0.22, 0.38, 0.40), period=800)
        E.hills(ctx, 400, 820, 70, (0.86, 0.88, 0.96), 17, lw=5, pines=0.8, pine_h=170, pine_c=E.PINE,
                period=1100)
        E.snow_ground(ctx, 905, 91)
        for (x, h) in ((-120, 420), (170, 330), (1790, 380), (2050, 460)):
            E.pine(ctx, x, 930, h, E.PINE, True, 6, seed=x)
        toy_block(ctx, 300, 925, 0.9, RED, 'A', -0.05)
        toy_block(ctx, 405, 925, 0.75, (0.25, 0.42, 0.75), 'B', 0.04)
        toy_block(ctx, 350, 830, 0.7, GREEN, 'C', -0.1)
        toy_block(ctx, 1640, 925, 0.85, GOLD_D, 'K', 0.06)
        for x in (520, 1530, 1880):
            candy_cane(ctx, x, 940, -math.pi / 2 + 0.12 * (1 if x % 2 else -1), 210, 18, 5)
        # tambor de juguete
        ctx.save()
        ctx.translate(1760, 930)
        ctx.rectangle(-70, -110, 140, 110)
        fill_stroke(ctx, RED, 6)
        for k in range(5):
            line(ctx, [(-70 + k * 35, -110), (-52 + k * 35, 0)], 5, GOLD)
        blob(ctx, 0, -110, 72, 18, CREAM, 6, seed=88)
        ctx.restore()
    return K.painted('forest', W + 2 * PX, H + 2 * PY, d, blur=1, passes=2)


def forest_set(ctx, t):
    K.blit(ctx, K.sky_layer(0.0), -K.PAD_X, -K.PAD_Y)
    E.sky(ctx, t, 0, moon=None, stars=True)
    E.moon_face(ctx, 1640, 170, 90, t, 'happy')
    K.blit(ctx, forest_back(), -K.PAD_X, -K.PAD_Y)


NUT_X, NUT_S = 1450, 0.86


def nut_mouth(x=NUT_X, s=NUT_S, jaw=0.0):
    return (x, 985 - 560 * s + (40 + jaw * 120) * s)


def sc_forest_arrive(ctx, lt, t):
    ctx.save()
    K.cam(ctx, lerp(820, 960, ease(lt / 10)), 520, 0.92)
    forest_set(ctx, t)
    # el cascanueces entra marchando
    if lt > 5.5:
        nx = lerp(2350, NUT_X, ease_out((lt - 5.5) / 4.5))
        nutcracker(ctx, nx, 985, NUT_S, -1, lt, jaw=0.1, march=lt < 10.0, look=(-0.6, 0.1))
    # los héroes llegan corriendo
    run = clamp(lt / 3.0)
    jx = lerp(-250, 640, ease_out(run))
    nx_ = lerp(-450, 420, ease_out(run))
    if lt < 3.0:
        jengi(ctx, jx, 985, 1.0, 1, 'run', lt, 'determined')
        nieve(ctx, nx_, 985, 1.0, 1, 'run', lt, 'determined')
    elif lt < 7.0:
        jengi(ctx, jx, 985, 1.0, 1, 'idle', lt, 'neutral', pose_override={'look': (math.sin(lt * 1.5), -0.2)})
        nieve(ctx, nx_, 985, 1.0, 1, 'idle', lt, 'neutral', pose_override={'look': (-math.sin(lt * 1.5), -0.2)})
    else:
        jengi(ctx, jx, 985, 1.0, 1, 'shock', lt, 'shock')
        nieve(ctx, nx_, 985, 1.0, 1, 'shock', lt, 'shock')
    if lt < 3.2:
        K.dust_puff(ctx, jx - 60, 985, (lt % 0.5) * 2, 0.6, 5)
    E.snowfall(ctx, t, 40, 1, 20)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 30)
    return {}


def sc_nut_talk(ctx, lt, t):
    # plano del cascanueces gritando, luego contraplano de Jengi
    if lt < 6.5:
        cx, cy, z = NUT_X - 60, 560, 1.45
    else:
        k = ease((lt - 6.5) / 0.6)
        cx, cy, z = lerp(NUT_X - 60, 560, k), lerp(560, 690, k), lerp(1.45, 1.5, k)
    ctx.save()
    K.cam(ctx, cx, cy, z)
    forest_set(ctx, t)
    tk = talkw(lt, 0.2, 6.4)
    jaw = 0.12 + 0.55 * tk * abs(math.sin(twos(lt) * 13))
    stomp = lt > 4.7 and lt < 6.4
    nutcracker(ctx, NUT_X, 985, NUT_S, -1, lt, jaw=jaw, march=stomp, look=(-0.6, 0.0))
    jt = talkw(lt, 6.75, 8.9)
    jengi(ctx, 640, 985, 1.0, 1, 'determined', lt, 'determined', cane=True, talk=jt)
    nieve(ctx, 420, 985, 1.0, 1, 'determined', lt, 'determined', sling=True)
    E.snowfall(ctx, t, 40, 1, 20)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 30)
    return {}


# nueces: (disparo, destino_x, altura)
NUTS = [(0.0, 640, 260), (1.6, 420, 220), (4.0, 760, 300), (4.5, 560, 260), (5.0, 360, 230)]
MINTS = [1.9, 7.0, 7.4, 7.8]
MINT_FLY = 0.4


def sc_nut_fight(ctx, lt, t):
    shake = 0.0
    flash = 0.0
    ctx.save()
    hit_t = 11.0
    fall0, crash = 15.8, 16.6
    if abs(lt - hit_t) < 0.3 or abs(lt - crash) < 0.4:
        shake = 0.7
    K.cam(ctx, 960, 520, 0.92, shake)
    forest_set(ctx, t)

    # ---- cascanueces
    dizzy = 8.2 < lt < 9.6
    talk = talkw(lt, 11.6, 15.1)
    if lt < 9.5:
        jaw = 0.15
        for (ft, _, _) in NUTS:
            if ft - 0.35 < lt < ft + 0.15:
                jaw = 0.8
    elif lt < 10.05:
        jaw = 0.25 + 0.75 * ease((lt - 9.5) / 0.4)
    elif lt < hit_t:
        jaw = 0.9
    else:
        jaw = 0.2 + 0.4 * talk * abs(math.sin(twos(lt) * 12))
    hurt = 1.0 if (dizzy or hit_t < lt < 15.5) else 0.0
    for m in MINTS:
        if m + MINT_FLY < lt < m + MINT_FLY + 0.3:
            hurt = 1.0
    if lt < fall0:
        ox = math.sin(lt * 40) * 6 * hurt
        nutcracker(ctx, NUT_X + ox, 985, NUT_S, -1, lt, jaw=jaw, march=4.0 < lt < 6.0, hurt=hurt,
                   look=(-0.7, 0.1) if not dizzy else (math.sin(lt * 9), math.cos(lt * 9)))
        if dizzy:
            dizzy_stars(ctx, NUT_X, 985 - 900 * NUT_S, lt)
    elif lt < crash:
        u = ease_in((lt - fall0) / (crash - fall0))
        ctx.save()
        ctx.translate(NUT_X + 40, 985)
        ctx.rotate(u * 1.45)
        ctx.translate(-(NUT_X + 40), -985)
        nutcracker(ctx, NUT_X, 985, NUT_S, -1, lt, jaw=0.6, march=False, hurt=1.0)
        ctx.restore()
    else:
        # piezas de madera desparramadas
        age = lt - crash
        for k in range(10):
            vx = nz(k, 1.1) * 420
            vy = -260 - u01(k, 2.2) * 380
            tt_ = min(age, 1.2)
            px = NUT_X + 200 + vx * tt_
            py = min(985 - 20, 900 + vy * tt_ + 900 * tt_ * tt_)
            c = [RED, (0.22, 0.32, 0.62), (0.98, 0.84, 0.70), INK, GOLD][k % 5]
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(age * 6 * nz(k, 3) if age < 1.2 else nz(k, 3) * 2)
            poly(ctx, [(-34, -16), (34, -16), (34, 16), (-34, 16)], c, 5, smooth=False, seed=k)
            ctx.restore()
        # el gorro rueda
        hx = NUT_X + 380 + min(age, 2.0) * 120
        ctx.save()
        ctx.translate(hx, 950)
        ctx.rotate(min(age, 2.0) * 3)
        poly(ctx, [(-60, 40), (60, 40), (52, -90), (-52, -90)], INK, 6, seed=91)
        ctx.restore()
        K.dust_puff(ctx, NUT_X + 250, 985, age, 2.2, 9)

    # ---- nueces disparadas
    for i, (ft, tx, hh) in enumerate(NUTS):
        u = (lt - ft) / 0.9
        if 0 <= u <= 1:
            x, y = arc_pos(nut_mouth(jaw=0.8), (tx, 960), u, hh)
            walnut(ctx, x, y, 36, lt * 10)
        elif 1 < u < 1.5:
            K.dust_puff(ctx, tx, 985, (u - 1) * 0.9 * 1.3, 0.7, i)
    # nuez gigante y su regreso
    gw0, bat_t = 10.0, 10.6
    if gw0 <= lt < bat_t:
        u = (lt - gw0) / (bat_t - gw0)
        x, y = arc_pos(nut_mouth(jaw=1.0), (700, 840), u, 120)
        walnut(ctx, x, y, 46, lt * 8)
    elif bat_t <= lt < hit_t:
        u = (lt - bat_t) / (hit_t - bat_t)
        x, y = arc_pos((700, 840), nut_mouth(jaw=0.9), u, 140)
        walnut(ctx, x, y, 46, -lt * 14)
        K.speed_lines(ctx, x - 40, y, 5, 160, 1.0, 4)
    impact(ctx, *nut_mouth(jaw=0.9), lt - hit_t, 1.3)
    impact(ctx, 700, 840, lt - bat_t, 0.8, CREAM)
    # dientes volando
    if lt > hit_t:
        age = lt - hit_t
        for k in range(6):
            vx = 150 + 260 * u01(k, 7.7)
            vy = -320 - 200 * u01(k, 8.8)
            tt_ = min(age, 1.0)
            mx, my = nut_mouth(jaw=0.9)
            px = mx - vx * tt_
            py = min(980, my + vy * tt_ + 980 * tt_ * tt_)
            ctx.save()
            ctx.translate(px, py)
            ctx.rotate(age * 12 * (1 if k % 2 else -1) if age < 1 else k)
            ctx.rectangle(-11, -11, 22, 22)
            fill_stroke(ctx, WHITE, 4)
            ctx.restore()
    # caramelos de Nieve
    for i, m in enumerate(MINTS):
        u = (lt - m) / MINT_FLY
        tgt = (NUT_X - 10, 985 - 760 * NUT_S) if i == 0 else (NUT_X, 985 - 560 * NUT_S + 20)
        if 0 <= u <= 1:
            x, y = arc_pos((470, 860), tgt, u, 60)
            peppermint(ctx, x, y, 17, lt * 20)
        impact(ctx, *tgt, lt - m - MINT_FLY, 0.6, CREAM)

    # ---- héroes
    jx = 640
    jpose, jexpr, jo, cane = 'idle', 'determined', None, True
    if 0.3 < lt < 1.0:
        jpose = 'jump'
        jo = {'hop': -math.sin(math.pi * (lt - 0.3) / 0.7) * 230}
    elif 4.0 < lt < 6.2:
        jpose = 'run'
        jx = 640 + math.sin((lt - 4.0) / 2.2 * math.pi * 2) * 160
    elif 9.6 < lt < bat_t + 0.4:
        jpose = 'swing'
        ph = clamp((lt - 10.35) / 0.3)
        jo = None
        jengi(ctx, jx, 985, 1.0, 1, 'swing', lt, 'angry', phase=ph, cane=True,
              pose_override={'cane_ang': lerp(-2.6, 0.6, ease_out(ph))})
        jpose = None
    elif 15.0 < lt < 16.0:
        jpose = 'run'
        jx = lerp(640, 1150, ease((lt - 15.0) / 0.6))
        if lt > 15.6:
            jpose = None
            jengi(ctx, jx, 985, 1.0, 1, 'swing', lt, 'angry', phase=clamp((lt - 15.6) / 0.25), cane=True,
                  pose_override={'cane_ang': lerp(-2.6, 0.6, ease_out(clamp((lt - 15.6) / 0.25)))})
    elif lt >= 16.0:
        jx = lerp(1150, 900, ease((lt - 16.0) / 1.0))
        jpose = 'cheer' if lt > 17.0 else 'idle'
        jexpr = 'happy'
    if jpose:
        jengi(ctx, jx, 985, 1.0, 1, jpose, lt, jexpr, cane=cane and jpose != 'cheer', pose_override=jo)
    nx = 420
    npose, nexpr, no = 'determined', 'determined', None
    if 1.5 < lt < 2.4 or 6.6 < lt < 8.3:
        npose = 'throw'
        last = max(m for m in MINTS if m <= lt + 0.4) if any(m <= lt + 0.4 for m in MINTS) else 0
        no = None
        nieve(ctx, nx, 985, 1.0, 1, 'throw', lt, 'determined', phase=clamp((lt - last + 0.4) / 0.4), sling=True)
        npose = None
    elif 4.0 < lt < 6.2:
        npose = 'run'
        nx = 420 - math.sin((lt - 4.0) / 2.2 * math.pi * 2) * 140
    elif lt >= 16.5:
        npose, nexpr = ('cheer', 'happy') if lt > 17.0 else ('idle', 'happy')
        nx = lerp(420, 640, ease((lt - 16.5) / 1.0))
    if npose:
        nieve(ctx, nx, 985, 1.0, 1, npose, lt, nexpr, sling=npose != 'cheer', pose_override=no)
    pop_word(ctx, '¡CATAPLÚN!', 1180, 380, lt - 17.0, size=140, dur=3.0)
    E.snowfall(ctx, t, 40, 1, 20)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 30)
    if lt > 23.4:
        iris(ctx, 800, 700, lerp(1300, 0, ease_in((lt - 23.4) / 1.0)))
    return {'flash': 0.3 * (1 - clamp((lt - hit_t) / 0.2)) if lt > hit_t else 0.0}


# ----------------------------------------------------------------------------
# LAGO HELADO
# ----------------------------------------------------------------------------
ICE = (0.74, 0.86, 0.96)


def bare_tree(ctx, x, y, h, seed):
    def branch(x0, y0, ang, L, w, depth):
        x1 = x0 + math.cos(ang) * L
        y1 = y0 + math.sin(ang) * L
        line(ctx, [(x0, y0), ((x0 + x1) / 2 + nz(depth, seed) * 8, (y0 + y1) / 2), (x1, y1)], w, BROWN)
        if depth > 0:
            branch(x1, y1, ang - 0.45 + nz(depth * 3, seed) * 0.2, L * 0.7, w * 0.65, depth - 1)
            branch(x1, y1, ang + 0.40 + nz(depth * 5, seed) * 0.2, L * 0.65, w * 0.65, depth - 1)
    branch(x, y, -math.pi / 2, h * 0.45, 16, 4)


def lake_back():
    PX, PY = K.PAD_X, K.PAD_Y

    def d(ctx):
        ctx.translate(PX, PY)
        E.black_mountain(ctx, 1500, 700, 0.75, 0, 0.8)
        E.hills(ctx, 0, 720, 110, (0.78, 0.82, 0.94), 21, lw=5, pines=0.7, pine_h=90,
                pine_c=(0.25, 0.38, 0.45), period=900)
        # lago
        ctx.move_to(-600, 790)
        ctx.curve_to(300, 740, 1500, 740, W + 600, 790)
        ctx.line_to(W + 600, H + 600)
        ctx.line_to(-600, H + 600)
        ctx.close_path()
        fill_stroke(ctx, ICE, 6)
        for k in range(14):
            x = u01(k, 31) * W
            y = 820 + u01(k, 32) * 220
            line(ctx, [(x, y), (x + 120, y - 6), (x + 260, y + 2)], 5, WHITE, 0.8)
        for k in range(6):
            x = u01(k, 41) * W
            line(ctx, [(x, 860), (x + 30, 900), (x + 10, 950), (x + 50, 1000)], 3, (0.45, 0.60, 0.80), 0.8)
        # orillas nevadas
        for (x0, flip) in ((-200, 1), (W + 200, -1)):
            ctx.move_to(x0, 700)
            ctx.curve_to(x0 + flip * 260, 720, x0 + flip * 380, 820, x0 + flip * 330, H + 300)
            ctx.line_to(x0 - flip * 400, H + 300)
            ctx.line_to(x0 - flip * 400, 700)
            ctx.close_path()
            fill_stroke(ctx, SNOW, 6)
        bare_tree(ctx, 60, 860, 420, 1.0)
        bare_tree(ctx, 1880, 880, 460, 2.0)
    return K.painted('lake', W + 2 * PX, H + 2 * PY, d, blur=1, passes=2)


def lake_set(ctx, t):
    K.blit(ctx, K.sky_layer(0.0), -K.PAD_X, -K.PAD_Y)
    E.sky(ctx, t, 0, moon=None, stars=True)
    E.moon_face(ctx, 380, 170, 85, t, 'scared' if t > 118.5 else 'happy')
    K.blit(ctx, lake_back(), -K.PAD_X, -K.PAD_Y)


def cocoa_cart(ctx, x, y, t, tip=0.0):
    ctx.save()
    ctx.translate(x, y)
    # carrito
    poly(ctx, [(-120, -40), (120, -40), (110, -170), (-110, -170)], (0.55, 0.30, 0.18), 6, smooth=False, seed=701)
    for wx in (-80, 80):
        circle(ctx, wx, -30, 32, INK, 5)
        circle(ctx, wx, -30, 12, GOLD, 4)
    # toldo a rayas
    for k in range(6):
        c = RED if k % 2 == 0 else WHITE
        poly(ctx, [(-140 + k * 47, -330), (-93 + k * 47, -330), (-93 + k * 47, -290), (-140 + k * 47, -280)],
             c, 4, smooth=False, seed=702 + k, wob=0.3)
    line(ctx, [(-125, -170), (-125, -330)], 8, BROWN)
    line(ctx, [(125, -170), (125, -330)], 8, BROWN)
    text(ctx, 'CHOCOLATE', 0, -230, 40, 'Rye', CREAM, INK, 6)
    text(ctx, 'CALIENTE', 0, -192, 34, 'Rye', CREAM, INK, 6)
    # taza gigante
    ctx.save()
    ctx.translate(40, -330)
    ctx.rotate(tip * 1.6)
    poly(ctx, [(-80, 0), (80, 0), (90, -170), (-90, -170)], (0.98, 0.95, 0.88), 6, smooth=False, seed=710)
    ctx.arc(95, -85, 40, -math.pi / 2, math.pi / 2)
    col(ctx, INK)
    ctx.set_line_width(20)
    ctx.stroke()
    ctx.arc(95, -85, 40, -math.pi / 2, math.pi / 2)
    col(ctx, (0.98, 0.95, 0.88))
    ctx.set_line_width(10)
    ctx.stroke()
    blob(ctx, 0, -170, 90, 18, (0.42, 0.22, 0.12), 5, seed=711)
    for k in range(3):
        ph = (t * 0.6 + k / 3) % 1
        line(ctx, [(-30 + k * 30, -200 - ph * 80), (-20 + k * 30 + math.sin(ph * 8) * 10, -240 - ph * 80)], 6,
             WHITE, 1 - ph)
    ctx.restore()
    ctx.restore()


def cocoa_wave(ctx, x0, front, y, h):
    if front <= x0:
        return
    pts = [(x0, y)]
    n = 14
    for k in range(n + 1):
        u = k / n
        x = lerp(x0, front, u)
        pts.append((x, y - h * (0.4 + 0.6 * u ** 0.6) - 14 * math.sin(u * 9 + G.t * 8)))
    pts.append((front + h * 0.5, y - h * 0.4))
    pts.append((front + h * 0.2, y))
    poly(ctx, pts, (0.45, 0.24, 0.12), 6, smooth=True, seed=720)
    for k in range(5):
        mx = lerp(x0, front, (k + 0.5) / 5)
        blob(ctx, mx, y - h * 0.8 + 10 * math.sin(k + G.t * 6), 18, 14, WHITE, 4, seed=730 + k)


FROST_X, FROST_S = 1420, 0.72


def sc_lake_arrive(ctx, lt, t):
    ctx.save()
    K.cam(ctx, 960, 540, 0.95, 0.4 if 3.0 < lt < 5.0 else 0.0)
    lake_set(ctx, t)
    cocoa_cart(ctx, 200, 1000, t)
    rise = ease_out((lt - 3.0) / 1.8)
    if rise > 0:
        ctx.save()
        ctx.rectangle(-1000, -1000, 4000, 1000 + 975)
        ctx.clip()
        tk = talkw(lt, 4.5, 10.4)
        frost_man(ctx, FROST_X, 985 + (1 - rise) * 700, FROST_S, -1, lt,
                  blow=0.4 * tk * abs(math.sin(twos(lt) * 12)))
        ctx.restore()
    # montículo que tiembla
    if lt < 3.2:
        j = math.sin(lt * 50) * 6 * clamp((lt - 2.0) / 0.5)
        blob(ctx, FROST_X + j, 985, 200, 60, SNOW, 6, seed=740)
    elif lt < 4.0:
        for k in range(10):
            a = k * math.pi / 5
            age = lt - 3.2
            blob(ctx, FROST_X + math.cos(a) * 300 * age, 985 - 200 * age + 500 * age * age * math.sin(a) ** 2,
                 30, 24, SNOW, 4, seed=741 + k, a=1 - age)
    # héroes patinando
    sl = clamp(lt / 2.5)
    jx = lerp(-200, 720, ease_out(sl))
    nx = lerp(-400, 520, ease_out(sl))
    pose = 'idle' if lt < 3.0 else 'shock'
    expr = 'happy' if lt < 3.0 else 'shock'
    jengi(ctx, jx, 985, 1.0, 1, pose, lt, expr, pose_override={'lean': -0.25 * (1 - sl)} if lt < 2.5 else None)
    nieve(ctx, nx, 985, 1.0, 1, pose, lt, expr, pose_override={'lean': -0.25 * (1 - sl)} if lt < 2.5 else None)
    E.snowfall(ctx, t, 40, 1, 40)
    ctx.restore()
    E.snowfall(ctx, t, 22, 2, 60)
    return {}


def blizzard(ctx, x, y, t, amt, length=1200):
    if amt <= 0:
        return
    for i in range(70):
        ph = (t * 1.8 + u01(i, 51)) % 1
        px = x - ph * length
        py = y + (u01(i, 52) - 0.5) * 120 * (0.3 + ph * 2.2) + math.sin(t * 9 + i) * 10
        ln = 30 + 60 * u01(i, 53)
        line(ctx, [(px, py), (px + ln, py - 4)], 4 + 3 * u01(i, 54), WHITE, amt * (1 - ph * 0.6), smooth=False)


def sc_lake_fight(ctx, lt, t):
    blow_on = (0.5 < lt < 3.2) or (3.3 < lt < 9.3)
    amt = 1.0 if 0.5 < lt < 3.2 else (0.55 if blow_on else 0.0)
    wave0 = 16.9
    melt = clamp((lt - 17.9) / 4.0)
    ctx.save()
    zcam = 0.95
    cx, cy = 960, 540
    if lt > 24.5:
        k = ease((lt - 24.5) / 3.0)
        cx, cy, zcam = lerp(960, 1500, k), lerp(540, 300, k), lerp(0.95, 1.6, k)
    K.cam(ctx, cx, cy, zcam, 0.4 if 0.5 < lt < 3.0 else 0.0)
    lake_set(ctx, t)
    tip = ease_out(clamp((lt - wave0) / 0.4)) if lt > wave0 else 0.0
    cocoa_cart(ctx, 200, 1000, t, tip)
    # Escarcha
    if melt < 1:
        arm = ease(clamp((lt - 9.5) / 0.4)) * (1 - ease(clamp((lt - 11.5) / 0.4)))
        tk = talkw(lt, 17.9, 21.6)
        hurt = 1.0 if 17.4 < lt < 22 else 0.0
        frost_man(ctx, FROST_X + math.sin(lt * 30) * 6 * hurt, 985, FROST_S, -1, lt,
                  blow=amt if blow_on else 0.3 * tk * abs(math.sin(twos(lt) * 10)), melt=melt, arm_up=arm)
        if blow_on:
            mx, my = FROST_X - 10 * FROST_S, 985 - 560 * FROST_S
            blizzard(ctx, mx - 40, my, lt, amt, 1300)
    else:
        frost_man(ctx, FROST_X, 985, FROST_S, -1, lt, melt=1.0)
        # zanahoria y sombrero flotando en el charco
        ctx.save()
        ctx.translate(FROST_X - 40, 975 + math.sin(lt * 3) * 4)
        poly(ctx, [(0, 0), (-80, 10), (0, 18)], ORANGE, 5, smooth=False, seed=750)
        ctx.restore()
        for k in range(7):
            u = k / 6
            poly(ctx, [(FROST_X + 40 + k * 22 - 10, 985), (FROST_X + 40 + k * 22 + 10, 985),
                       (FROST_X + 40 + k * 22, 985 - 30 - 10 * math.sin(u * math.pi))], (0.75, 0.9, 1.0), 4,
                 smooth=False, seed=760 + k)
    # vapor al derretirse
    if 17.4 < lt < 22.5:
        for k in range(6):
            ph = (lt * 0.8 + k / 6) % 1
            blob(ctx, FROST_X + nz(k, 3) * 160, 985 - 300 * FROST_S - ph * 400 * (1 - melt * 0.5),
                 30 + ph * 40, 26 + ph * 30, (0.95, 0.95, 0.98), 4, seed=770 + k, a=(1 - ph) * 0.8)
    # carámbanos que caen
    for i, (ft, x) in enumerate(((9.9, 1050), (10.3, 900), (10.7, 1150), (11.0, 820))):
        u = (lt - ft) / 0.5
        if 0 <= u <= 1:
            y = lerp(-100, 960, ease_in(u))
            poly(ctx, [(x - 18, y - 120), (x + 18, y - 120), (x, y)], (0.75, 0.9, 1.0), 5, smooth=False, seed=i)
        elif 1 < u < 2:
            for k in range(5):
                a = -math.pi * (0.15 + 0.7 * k / 4)
                age = (u - 1) * 0.5
                d = 140 * age
                poly(ctx, [(x + math.cos(a) * d - 8, 960 + math.sin(a) * d),
                           (x + math.cos(a) * d + 8, 960 + math.sin(a) * d),
                           (x + math.cos(a) * d, 960 + math.sin(a) * d - 22)], (0.8, 0.92, 1.0), 3,
                     smooth=False, seed=i * 10 + k, a=1 - age * 2)
    # ola de chocolate
    if lt > wave0 + 0.2:
        front = lerp(300, 1750, ease_out(clamp((lt - wave0 - 0.2) / 1.0)))
        h = 130 * (1 - clamp((lt - wave0 - 2.0) / 2.0))
        if h > 2:
            cocoa_wave(ctx, 230, front, 990, h)

    # ---- Jengi
    if lt < 0.5:
        jengi(ctx, 720, 985, 1.0, 1, 'determined', lt, 'determined')
    elif lt < 3.2:
        u = ease_out(clamp((lt - 0.5) / 1.5))
        jx = lerp(720, 330, u)
        jengi(ctx, jx, 985, 1.0, 1, 'shock', lt, 'shock', pose_override={'lean': -0.3})
    elif lt < 11.5:
        sh = math.sin(lt * 45) * 4
        jengi(ctx, 330 + sh, 985, 1.0, 1, 'idle', lt, 'shock', pose_override={'squash': 0.08, 'lh': (-30, -120),
                                                                                  'rh': (30, -120)})
        for k in range(4):
            poly(ctx, [(270 + k * 35, 760), (290 + k * 35, 760), (280 + k * 35, 800)], (0.8, 0.92, 1.0), 3,
                 smooth=False, seed=780 + k)
    elif lt < 13.0:
        jt = talkw(lt, 11.9, 16.6)
        jengi(ctx, 330, 985, 1.0, 1, 'point', lt, 'happy', talk=jt)
        idea_bulb(ctx, 400, 600, lt - 11.5)
    elif lt < wave0:
        jt = talkw(lt, 11.9, 16.6)
        u = ease(clamp((lt - 13.0) / 1.2))
        jx = lerp(330, 330, u)
        jengi(ctx, lerp(330, 380, u), 985, 1.0, -1, 'run' if lt < 14.2 else 'determined', lt, 'determined', talk=jt)
    elif lt < wave0 + 1.2:
        jengi(ctx, 380, 985, 1.0, -1, 'throw', lt, 'angry', phase=clamp((lt - wave0) / 0.3))
    else:
        pose = 'cheer' if lt > 22.4 else 'idle'
        if lt > 26.0:
            pose = 'point'
        jengi(ctx, lerp(380, 820, ease(clamp((lt - 19.0) / 1.5))), 985, 1.0, 1, pose, lt, 'happy')
    # ---- Nieve
    if lt < 3.3:
        nieve(ctx, 900, 985, 1.0, 1, 'determined', lt, 'determined')
    elif lt < 9.3:
        vt = talkw(lt, 3.3, 9.2)
        nx = lerp(900, 1080, ease(clamp((lt - 3.3) / 5.5)))
        nieve(ctx, nx, 985, 1.0, 1, 'idle', lt, 'happy', talk=vt, pose_override={'lean': 0.15})
    elif lt < 12.0:
        nx = lerp(1080, 820, ease_out(clamp((lt - 9.9) / 0.8)))
        nieve(ctx, nx, 985, 1.0, 1, 'jump' if 9.9 < lt < 10.7 else 'shock', lt, 'shock',
              pose_override={'hop': -math.sin(math.pi * clamp((lt - 9.9) / 0.8)) * 160})
    elif lt < 22.4:
        nieve(ctx, 820, 985, 1.0, -1 if lt < wave0 else 1, 'idle', lt, 'happy')
    else:
        nieve(ctx, 1040, 985, 1.0, 1, 'cheer' if lt < 26 else 'point', lt + 0.4, 'happy')
    pop_word(ctx, '¡DERRETIDO!', 1250, 380, lt - 22.5, (0.75, 0.92, 1.0), (0.25, 0.42, 0.75), 120, 2.6)
    E.snowfall(ctx, t, 40, 1, 40 + 400 * amt)
    ctx.restore()
    E.snowfall(ctx, t, 22, 2, 60 + 600 * amt)
    if lt > 28.0:
        iris(ctx, W / 2, H / 2, lerp(1300, 0, ease_in((lt - 28.0) / 1.0)))
    return {}


# ----------------------------------------------------------------------------
# CASTILLO DEL KRAMPUS
# ----------------------------------------------------------------------------
CPX, CPY = 1500, 900


def castle_back():
    PX, PY = CPX, CPY

    def d(ctx):
        ctx.translate(PX, PY)
        stone = (0.30, 0.26, 0.36)
        for (tx, tw, th, lean) in ((180, 200, 720, -0.06), (520, 150, 560, 0.05), (1450, 180, 680, 0.07),
                                   (1780, 220, 820, -0.05)):
            ctx.save()
            ctx.translate(tx, 905)
            ctx.rotate(lean)
            poly(ctx, [(-tw / 2, 0), (tw / 2, 0), (tw / 2 - 10, -th), (-tw / 2 + 10, -th)], stone, 6,
                 smooth=False, seed=tx)
            poly(ctx, [(-tw / 2 - 30, -th), (tw / 2 + 30, -th), (8, -th - tw * 1.3)], (0.20, 0.16, 0.26), 6,
                 smooth=False, seed=tx + 1)
            for k in range(3):
                wy = -th * (0.25 + 0.25 * k)
                glow(ctx, 0, wy, 50, LIME, 0.4)
                poly(ctx, [(-16, wy + 26), (16, wy + 26), (16, wy - 10), (0, wy - 30), (-16, wy - 10)],
                     (0.70, 0.95, 0.45), 4, smooth=False, seed=tx + k)
            for r in range(8):
                yy = -60 - r * 80
                line(ctx, [(-tw / 2 + 12, yy), (tw / 2 - 12, yy + 4)], 3, (0.20, 0.16, 0.25), 0.6)
            ctx.restore()
        # suelo de piedra
        ctx.rectangle(-1500, 900, W + 3000, 900)
        fill_stroke(ctx, (0.42, 0.38, 0.46), 6)
        for r in range(12):
            for c in range(-14, 36):
                x = c * 120 + (r % 2) * 60
                y = 930 + r * 48
                line(ctx, [(x, y), (x + 100, y + 2)], 4, (0.28, 0.24, 0.32), 0.8)
        for k in range(4):
            blob(ctx, 300 + k * 480, 905, 120, 16, SNOW, 5, seed=800 + k)
    return K.painted('castle', W + 2 * PX, H + 2 * PY, d, blur=1, passes=2)


def castle_set(ctx, t, green=1.0):
    E.sky(ctx, t, green, moon=None, stars=True)
    E.moon_face(ctx, 960, 180, 80, t, 'scared', 1.0)
    E.storm_clouds(ctx, t + 40, 1.0, 40)
    K.blit(ctx, castle_back(), -CPX, -CPY)


def present_throne(ctx, x, y, s=1.0):
    k = 0
    for row, n in enumerate((5, 4, 3)):
        for i in range(n):
            c1, c2 = PRESENT_COLORS[(k * 2 + row) % len(PRESENT_COLORS)]
            present(ctx, x + (i - (n - 1) / 2) * 100 * s, y - 45 * s - row * 85 * s, 92 * s, 80 * s, c1, c2,
                    rot=nz(k, 4) * 0.08)
            k += 1


KR_X, KR_Y, KR_S0 = 1330, 905, 0.62


def sc_castle_intro(ctx, lt, t):
    ctx.save()
    K.cam(ctx, 960, 520, 0.92)
    castle_set(ctx, t)
    present_throne(ctx, KR_X + 60, 905, 1.0)
    tk = talkw(lt, 1.0, 6.3)
    on_top = lt < 6.6
    ky = 905 - 255 if on_top else 905
    kx = KR_X
    if 6.6 <= lt < 7.4:
        u = (lt - 6.6) / 0.8
        kx = lerp(KR_X + 60, KR_X - 80, u)
        ky = lerp(650, 905, u) - math.sin(u * math.pi) * 120
    elif lt >= 7.4:
        kx = KR_X - 80
    laugh = 2.0 < lt < 3.2
    krampus(ctx, kx, ky, KR_S0, -1, lt, grin=0.45 + 0.45 * tk * abs(math.sin(twos(lt) * 11)),
            lean=-0.12 if laugh else (0.08 if lt > 3.5 else 0.0),
            eyes_glow=0.3 + (0.7 if 3.6 < lt < 6.4 else 0.0), look=(0.6, 0.4), bell_on_horn=math.sin(lt * 4) * 0.2,
            hop=-abs(math.sin(lt * 9)) * 14 if laugh else 0.0)
    run = clamp(lt / 2.5)
    jengi(ctx, lerp(-200, 520, ease_out(run)), 985, 1.0, 1, 'run' if lt < 2.5 else 'determined', lt, 'determined',
          cane=lt > 2.5)
    nieve(ctx, lerp(-420, 300, ease_out(run)), 985, 1.0, 1, 'run' if lt < 2.5 else 'determined', lt,
          'determined', sling=lt > 2.5)
    E.snowfall(ctx, t, 30, 1, 160)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 260)
    if lt < 0.5:
        iris(ctx, W / 2, H / 2, lerp(0, 1300, ease_out(lt / 0.5)))
    return {}


BOMBS = [(0.6, 1.3, 520), (1.9, 2.6, 330), (6.5, 7.2, 560)]
KMINTS = [3.6, 4.0, 4.4]
BAT_BOMB = (7.9, 8.8, 9.2)   # lanzamiento, bateo, impacto


def sc_castle_fight(ctx, lt, t):
    kx, ky = KR_X - 80, 905
    shake = 0.0
    flash = 0.0
    for (_, land, _) in BOMBS:
        if 0 <= lt - land < 0.3:
            shake = 0.5
    if 0 <= lt - BAT_BOMB[2] < 0.4:
        shake, flash = 0.8, 0.4
    if lt > 10.0:
        shake = max(shake, 0.25 + 0.4 * clamp((lt - 10) / 5))
    ctx.save()
    K.cam(ctx, 960, 520, 0.92, shake)
    castle_set(ctx, t)
    present_throne(ctx, KR_X + 60, 905, 1.0)
    # brazo del látigo
    whips = [0.3, 1.6, 6.2, 7.6]
    rh = None
    for w in whips:
        u = (lt - w) / 0.5
        if 0 <= u <= 1:
            a = lerp(-2.4, 0.4, ease_out(u))
            rh = (math.cos(a) * 320, -560 + math.sin(a) * 260)
    hurt = any(0 <= lt - (m + 0.4) < 0.4 for m in KMINTS)
    soot = lt > BAT_BOMB[2]
    expr = 'dizzy' if 4.9 < lt < 6.0 else 'evil'
    glow_e = 0.3 + (1.0 if lt > 9.4 else 0.0)
    if lt > 10:
        glow(ctx, kx, ky - 400 * KR_S0, 500 * (1 + 0.1 * math.sin(lt * 10)), LIME, 0.35 * clamp((lt - 10) / 3))
    krampus(ctx, kx + (math.sin(lt * 40) * 8 if hurt or lt > 10 else 0), ky, KR_S0, -1, lt,
            grin=0.9 if lt > 9.4 else 0.6, rh=rh, eyes_glow=glow_e, look=(0.7, 0.4), expr=expr,
            bell_on_horn=math.sin(lt * 5) * 0.25, lean=0.08 if lt > 10 else 0.0)
    if soot:
        # cara tiznada por la explosión
        hx, hy = kx - 10 * KR_S0, ky - 640 * KR_S0
        for k in range(5):
            blob(ctx, hx + nz(k, 9) * 50, hy + nz(k, 8) * 40, 30, 22, (0.08, 0.07, 0.08), 0, seed=850 + k, a=0.6)
    # bombas-campana
    for i, (t0, t1, tx) in enumerate(BOMBS):
        u = (lt - t0) / (t1 - t0)
        if 0 <= u <= 1:
            x, y = K_arc((kx - 150, ky - 520 * KR_S0), (tx, 960), u, 300)
            bell_bomb(ctx, x, y, lt)
        puff_cloud(ctx, tx, 930, lt - t1, 1.0, (0.95, 0.85, 0.5), 0.9, i)
        if 0 <= lt - t1 < 0.6:
            for k in range(6):
                a = k * math.pi / 3
                r = (lt - t1) * 400
                sparkle(ctx, tx + math.cos(a) * r, 930 + math.sin(a) * r * 0.6, 22, GOLD, 1 - (lt - t1) / 0.6)
    t0, tb, ti = BAT_BOMB
    if t0 <= lt < tb:
        x, y = K_arc((kx - 150, ky - 520 * KR_S0), (700, 830), (lt - t0) / (tb - t0), 260)
        bell_bomb(ctx, x, y, lt)
    elif tb <= lt < ti:
        x, y = K_arc((700, 830), (kx - 10 * KR_S0, ky - 640 * KR_S0), (lt - tb) / (ti - tb), 120)
        bell_bomb(ctx, x, y, lt)
        K.speed_lines(ctx, x - 40, y, 5, 150, 1.0, 5)
    puff_cloud(ctx, kx - 10 * KR_S0, ky - 640 * KR_S0, lt - ti, 1.3, (0.30, 0.28, 0.30), 1.2, 9)
    # caramelos de Nieve a la nariz del Krampus
    for m in KMINTS:
        u = (lt - m) / 0.4
        tgt = (kx - 40 * KR_S0, ky - 620 * KR_S0)
        if 0 <= u <= 1:
            x, y = K_arc((420, 860), tgt, u, 80)
            peppermint(ctx, x, y, 17, lt * 20)
        impact(ctx, *tgt, lt - m - 0.4, 0.6, CREAM)
    # Jengi
    j_hop = 0.0
    jp, je = 'determined', 'determined'
    for (b0, b1) in ((0.9, 1.5), (6.8, 7.4)):
        if b0 < lt < b1:
            jp = 'jump'
            j_hop = -math.sin(math.pi * (lt - b0) / (b1 - b0)) * 220
    if tb - 0.3 < lt < tb + 0.4:
        ph = clamp((lt - tb + 0.2) / 0.3)
        jengi(ctx, 640, 985, 1.0, 1, 'swing', lt, 'angry', phase=ph, cane=True,
              pose_override={'cane_ang': lerp(-2.6, 0.6, ease_out(ph))})
    else:
        if lt > 10:
            jp, je = 'shock', 'shock'
        jengi(ctx, 640, 985, 1.0, 1, jp, lt, je, cane=jp != 'shock', pose_override={'hop': j_hop} if j_hop else None)
    # Nieve
    if 3.3 < lt < 5.0:
        last = max([m for m in KMINTS if m <= lt + 0.4] or [3.6])
        nieve(ctx, 420, 985, 1.0, 1, 'throw', lt, 'determined', phase=clamp((lt - last + 0.4) / 0.4), sling=True)
    elif 1.7 < lt < 3.0:
        nx = lerp(420, 220, ease(clamp((lt - 1.7) / 0.6)))
        nx = lerp(nx, 420, ease(clamp((lt - 2.6) / 0.4)))
        nieve(ctx, nx, 985, 1.0, 1, 'run', lt, 'determined')
    else:
        nieve(ctx, 420, 985, 1.0, 1, 'shock' if lt > 10 else 'determined', lt,
              'shock' if lt > 10 else 'determined', sling=lt <= 10)
    E.snowfall(ctx, t, 30, 1, 160)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 260)
    return {'flash': flash}


def K_arc(p0, p1, u, h):
    return arc_pos(p0, p1, u, h)


GIANT_S = 1.75


def giant_scale(lt):
    return lerp(KR_S0, GIANT_S, elastic(clamp((lt - 0.2) / 1.8)))


def sc_giant(ctx, lt, t):
    s = giant_scale(lt)
    stomps = [1.5, 3.0, 6.0, 7.5]
    shake = 0.2
    for st in stomps:
        if 0 <= lt - st < 0.35:
            shake = 1.0
    z = lerp(0.92, 0.55, ease(clamp((lt - 0.2) / 2.0)))
    ctx.save()
    K.cam(ctx, 960, lerp(520, 260, ease(clamp((lt - 0.2) / 2.0))), z, shake)
    castle_set(ctx, t)
    present_throne(ctx, KR_X + 60, 905, 1.0)
    kx = KR_X - 80 - (s - KR_S0) * 120
    glow(ctx, kx, 905 - 400 * s, 520 * s, LIME, 0.35)
    st_side = 0.0
    for i, st in enumerate(stomps):
        if st - 0.4 < lt < st:
            st_side = (1 if i % 2 else -1) * math.sin(math.pi * (lt - st + 0.4) / 0.4)
    # manotazo barriendo el suelo
    rh = None
    if 8.3 < lt < 9.1:
        u = (lt - 8.3) / 0.8
        rh = (lerp(-100, 650, u), -40)
    krampus(ctx, kx, 905, s, -1, lt, grin=0.9, eyes_glow=1.0, stomp=st_side, rh=rh, look=(0.5, 0.8),
            bell_on_horn=math.sin(lt * 4) * 0.3)
    for st in stomps:
        K.dust_puff(ctx, kx + 80 * s, 905, (lt - st) * 1.2, 2.0, st)
    # héroes chiquitos
    jump = -math.sin(math.pi * clamp((lt - 8.5) / 0.6)) * 200 if 8.5 < lt < 9.1 else 0.0
    vt = talkw(lt, 9.0, 12.4)
    jengi(ctx, 560, 985, 0.9, 1, 'jump' if jump else 'shock', lt, 'shock', pose_override={'hop': jump} if jump else None)
    nieve(ctx, 330, 985, 0.9, 1, 'point' if lt > 9.0 else ('jump' if jump else 'shock'), lt,
          'determined' if lt > 9.0 else 'shock', talk=vt,
          pose_override={'rh': (110, -260)} if lt > 9.0 else ({'hop': jump} if jump else None))
    E.snowfall(ctx, t, 30, 1, 180)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 280)
    return {}


def arm_point(s, kx, ky, rh, u, face=-1):
    """Punto a lo largo del brazo de manguera del Krampus (u=0 mano, u=1 hombro), en coords de mundo."""
    a = (112.0, -505.0)
    b = rh
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    c = ((a[0] + b[0]) / 2 + nx * -60, (a[1] + b[1]) / 2 + ny * -60)
    v = 1 - u
    lx = (1 - v) ** 2 * a[0] + 2 * v * (1 - v) * c[0] + v * v * b[0]
    ly = (1 - v) ** 2 * a[1] + 2 * v * (1 - v) * c[1] + v * v * b[1]
    return kx + face * s * lx, ky + s * ly


def sc_climb(ctx, lt, t):
    s = GIANT_S
    kx, ky = KR_X - 80 - (s - KR_S0) * 120, 905
    dong = 5.5
    slam = clamp((lt - 0.0) / 0.3)
    rh = (lerp(200, 520, ease_in(slam)), lerp(-420, 0, ease_in(slam)) - 20)
    # Jengi corre por el brazo
    run0, run1 = 0.8, 4.3
    if lt < run0:
        jx, jy = 560, 985
    elif lt < run1:
        u = ease((lt - run0) / (run1 - run0)) * 0.95
        jx, jy = arm_point(s, kx, ky, rh, u)
        jy -= 20 * s
    else:
        hx, hy = kx - 10 * s, ky - 640 * s
        u = ease(clamp((lt - run1) / 0.7))
        sx, sy = arm_point(s, kx, ky, rh, 0.95)
        bx, by = kx - 192 * s, ky - 650 * s - 40
        jx = lerp(sx, bx + 120, u)
        jy = lerp(sy - 20 * s, by + 40, u) - math.sin(u * math.pi) * 200
    if lt > 6.3:
        u = clamp((lt - 6.3) / 1.2)
        bx, by = kx - 192 * s, ky - 650 * s - 40
        jx = lerp(bx + 120, 700, u)
        jy = lerp(by + 40, 985, ease_in(u)) - math.sin(u * math.pi) * 250
    # cámara que sigue a Jengi
    ccx = lerp(960, jx, 0.6)
    ccy = lerp(400, jy - 150, 0.7)
    z = 0.62 if lt < 0.6 else lerp(0.62, 0.95, ease(clamp((lt - 0.6) / 1.0)))
    if lt > 6.0:
        z = lerp(0.95, 0.6, ease(clamp((lt - 6.0) / 1.2)))
        ccx, ccy = lerp(ccx, 960, ease(clamp((lt - 6.0) / 1.2))), lerp(ccy, 300, ease(clamp((lt - 6.0) / 1.2)))
    shake = 1.0 if 0.25 < lt < 0.6 else (1.2 if 0 <= lt - dong < 0.6 else 0.0)
    ctx.save()
    K.cam(ctx, ccx, ccy, z, shake)
    castle_set(ctx, t)
    present_throne(ctx, KR_X + 60, 905, 1.0)
    dizzy = lt > dong + 0.1
    has_bell = lt < dong + 0.4
    krampus(ctx, kx, ky, s, -1, lt, grin=0.7, eyes_glow=0.0 if dizzy else 1.0, rh=rh, look=(0.4, 0.2),
            expr='dizzy' if dizzy else 'evil', bell_on_horn=(math.sin(lt * 30) * 0.6 if lt > dong else 0.0)
            if has_bell else None, lean=math.sin(lt * 3) * 0.06 if dizzy else 0.0)
    if dizzy:
        dizzy_stars(ctx, kx - 10 * s, ky - 900 * s, lt, 160, 5)
    K.dust_puff(ctx, kx - 520 * s, 905, (lt - 0.3) * 1.2, 2.0, 77)
    # ondas expansivas del DONG
    bx, by = kx - 192 * s, ky - 650 * s
    if lt > dong:
        for k in range(4):
            r = (lt - dong - k * 0.15) * 1400
            if r > 0:
                ctx.arc(bx, by, r, 0, 2 * math.pi)
                col(ctx, (1, 0.95, 0.7), max(0, 0.8 - r / 1800))
                ctx.set_line_width(18)
                ctx.stroke()
    # Jengi (en el aire con el bastón)
    if lt < run0:
        jengi(ctx, jx, jy, 0.9, 1, 'determined', lt, 'determined', cane=True)
    elif lt < run1:
        jengi(ctx, jx, jy, 0.9, -1, 'run', lt, 'determined', cane=True)
    elif lt < dong + 0.2:
        ph = clamp((lt - (dong - 0.3)) / 0.3)
        jengi(ctx, jx, jy, 0.9, -1, 'swing', lt, 'angry', phase=ph, cane=True,
              pose_override={'cane_ang': lerp(-2.6, 0.6, ease_out(ph))})
    else:
        jengi(ctx, jx, jy, 0.9, -1, 'jump', lt, 'happy', cane=not (lt > dong + 0.4))
        if lt > dong + 0.4:
            golden_bell(ctx, jx - 10, jy - 260, 0.45, math.sin(lt * 8) * 0.3)
    nieve(ctx, 330, 985, 0.9, 1, 'cheer' if lt > dong else 'point', lt, 'happy' if lt > dong else 'determined',
          pose_override=None if lt > dong else {'rh': (110, -260)})
    pop_word(ctx, '¡DONG!', bx + 300, by - 200, lt - dong, GOLD, RED, 170, 2.2)
    E.snowfall(ctx, t, 30, 1, 180)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 280)
    flash = 0.9 * (1 - clamp((lt - dong) / 0.4)) if lt > dong else 0.0
    return {'flash': flash}


def sc_shrink(ctx, lt, t):
    s = lerp(GIANT_S, 0.24, ease_in(clamp((lt - 0.2) / 0.9)))
    if lt > 1.1:
        s = 0.24 * (1 + 0.25 * math.sin((lt - 1.1) * 18) * math.exp(-(lt - 1.1) * 4))
    kx = KR_X - 80 - (max(s, KR_S0) - KR_S0) * 120
    kx = lerp(kx, 1020, ease(clamp((lt - 0.6) / 0.8)))
    z = lerp(0.6, 1.0, ease(clamp((lt - 0.4) / 1.4)))
    ctx.save()
    K.cam(ctx, lerp(960, 1000, ease(lt / 3)), lerp(300, 620, ease(clamp((lt - 0.4) / 1.4))), z)
    castle_set(ctx, t)
    present_throne(ctx, KR_X + 60, 905, 1.0)
    # regalos que salen volando de la canasta
    if lt > 2.6:
        for k in range(10):
            u = clamp((lt - 2.6 - k * 0.08) / 1.6)
            if 0 < u < 1:
                x = kx + nz(k, 2) * 300 * u
                y = 905 - 60 - u * 900 - 200 * math.sin(u * math.pi)
                c1, c2 = PRESENT_COLORS[k % len(PRESENT_COLORS)]
                ctx.save()
                ctx.translate(x, y)
                ctx.rotate(u * 6 * nz(k, 5))
                present(ctx, 0, 0, 60, 50, c1, c2)
                ctx.restore()
                sparkle(ctx, x + 30, y + 30, 18, GOLD, 1 - u, rot=lt * 5)
    expr = 'dizzy' if lt < 1.6 else 'scared'
    krampus(ctx, kx, 905, s, -1, lt, grin=0.3, eyes_glow=0.0, expr=expr, look=(0.6, 0.0), basket=lt < 2.6)
    if 1.6 < lt < 4.0:
        circle(ctx, kx - 30, 905 - 600 * s, 7, (0.95, 0.5, 0.5), 0, 0.8)
    if 1.8 < lt < 3.0:
        text(ctx, '¿beee?', kx - 60, 905 - 210, 46, 'Lobster', CREAM, INK, 6, a=1 - clamp((lt - 2.6) / 0.4))
    jengi(ctx, 700, 985, 1.0, 1, 'cheer' if lt > 3.4 else 'idle', lt, 'happy')
    golden_bell(ctx, 700 + 80, 985 - 300, 0.4, math.sin(lt * 6) * 0.3)
    nieve(ctx, 470, 985, 1.0, 1, 'cheer' if lt > 3.4 else 'idle', lt + 0.3, 'happy')
    E.snowfall(ctx, t, 30, 1, 60)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 80)
    if lt > 6.9:
        iris(ctx, W / 2, H / 2, lerp(1300, 0, ease_in((lt - 6.9) / 0.9)))
    return {'flash': 0.4 * (1 - clamp((lt - 0.2) / 0.3)) if lt > 0.2 else 0.0}


# ----------------------------------------------------------------------------
# REGRESO Y FIN
# ----------------------------------------------------------------------------
def sc_return(ctx, lt, t):
    bell_land = 1.5
    ctx.save()
    K.cam(ctx, lerp(1130, 1100, ease(lt / 14)), 560, lerp(0.95, 1.05, ease(lt / 14)))
    has_bell = lt >= bell_land

    def pile(c):
        for i, (x, y, w, h, ci) in enumerate(K.PILE):
            u = clamp((lt - 0.2 - i * 0.35) / 1.0)
            if u <= 0:
                continue
            py = lerp(-300, y - h / 2, ease_in(u))
            c1, c2 = PRESENT_COLORS[ci]
            ctx.save()
            ctx.translate(x, py)
            ctx.rotate((1 - u) * 4 * (1 if i % 2 else -1))
            present(ctx, 0, 0, w, h, c1, c2)
            ctx.restore()
    K.plaza_set(ctx, t, 0.0, 'happy', tree_bell=has_bell, bell_sw=math.sin(lt * 3) * 0.15 if has_bell else 0,
                bell_shine=clamp(1 - (lt - bell_land) / 2.0) if has_bell else 0, presents=pile)
    if not has_bell and lt > 0.6:
        u = (lt - 0.6) / (bell_land - 0.6)
        x, y = arc_pos((880, 760), (1180, 935 + (-575 - 165 - 40) * 0.8), u, 260)
        golden_bell(ctx, x, y, 0.75, lt * 8)
    if has_bell and lt - bell_land < 0.8:
        for k in range(10):
            a = k * math.pi / 5
            r = 60 + (lt - bell_land) * 500
            sparkle(ctx, 1180 + math.cos(a) * r, 315 + math.sin(a) * r, 26, GOLD, 1 - (lt - bell_land) / 0.8)
    # mini Krampus barriendo con gorro de Santa
    mk_x = 1600 + math.sin(lt * 1.2) * 60
    krampus(ctx, mk_x, 985, 0.25, -1 if math.cos(lt * 1.2) > 0 else 1, lt, grin=0.35, expr='scared' if lt < 9 else 'evil',
            look=(0.4, 0.3), basket=False, santa_hat=True, tongue=0.0 if lt < 9 else 1.0,
            lh=(-60, -300), rh=(lerp(80, 160, abs(math.sin(lt * 5))), -150))
    # escoba
    bxs = mk_x - 40
    line(ctx, [(bxs, 985 - 60), (bxs - 50, 985 - 5)], 6, BROWN)
    poly(ctx, [(bxs - 70, 985), (bxs - 30, 985), (bxs - 45, 985 - 25)], GOLD_D, 4, smooth=False, seed=990)
    if 9.0 < lt < 11.5:
        blob(ctx, mk_x - 50, 985 - 100, 20, 20, (0.80, 0.55, 0.30), 4, seed=991)  # galleta
    if lt < 0.9:
        jengi(ctx, 880, 985, 1.05, 1, 'throw', lt, 'happy', phase=clamp((lt - 0.3) / 0.3))
    else:
        jengi(ctx, 880, 985, 1.05, 1, 'dance', lt, 'happy')
    nx = 1380 if lt < 8.5 else lerp(1380, 1460, ease(clamp((lt - 8.5) / 0.6)))
    nieve(ctx, nx, 985, 1.05, -1 if lt < 8.5 else 1, 'dance' if lt < 8.5 else 'point', lt + 0.33, 'happy',
          pose_override={'rh': (100, -120)} if lt >= 8.5 else None)
    E.snowfall(ctx, t, 40, 1, 20)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 30)
    if lt < 0.5:
        iris(ctx, W / 2, H / 2, lerp(0, 1300, ease_out(lt / 0.5)))
    return {}


def sc_goodbye(ctx, lt, t):
    ctx.save()
    K.cam(ctx, 1160, 700, 1.5)
    K.plaza_set(ctx, t, 0.0, 'happy', tree_bell=True, bell_sw=math.sin(lt * 3) * 0.15)
    jengi(ctx, 1000, 985, 1.05, 1, 'wave', lt, 'happy', talk=talkw(lt, 0.3, 1.6))
    nieve(ctx, 1320, 985, 1.05, -1, 'wave', lt + 0.2, 'happy', talk=talkw(lt, 1.8, 4.2))
    E.snowfall(ctx, t, 30, 1, 20)
    ctx.restore()
    E.snowfall(ctx, t, 20, 2, 30)
    return {}


def sc_fin(ctx, lt, t):
    E.sunburst(ctx, W / 2, H / 2 + 40, lt, (0.55, 0.07, 0.10), (0.68, 0.12, 0.15), 32, 0.08)
    glow(ctx, W / 2, H / 2, 700, (1.0, 0.85, 0.5), 0.35)
    E.deco_frame(ctx, 40)
    for (x, y, r) in ((95, 95, 0.8), (W - 95, 95, 2.4), (95, H - 95, -0.8), (W - 95, H - 95, -2.4)):
        E.holly(ctx, x, y, 1.1, r)
    s1 = elastic((lt - 0.2) / 1.0)
    if s1 > 0:
        text(ctx, 'FIN', W / 2, 400, 300, 'Limelight', CREAM, INK, 18, shadow=GOLD, sdx=10, sdy=12, scale=s1)
    s2 = back_out((lt - 1.0) / 0.5)
    if s2 > 0:
        text(ctx, '¡Feliz Navidad!', W / 2, 640, 120, 'Lobster', (0.40, 0.75, 0.45), CREAM, 10, shadow=INK,
             scale=s2)
    pj = ease_out((lt - 1.4) / 0.5)
    if pj > 0:
        jengi(ctx, 330, H + 230 - 200 * pj, 1.2, 1, 'wave', lt, 'happy')
        nieve(ctx, W - 330, H + 220 - 200 * pj, 1.2, -1, 'wave', lt + 0.3, 'happy')
        krampus(ctx, W / 2 + 20, H + 190 - 240 * pj, 0.32, 1, lt, grin=0.5, basket=False, santa_hat=True,
                look=(0.0, 0.3), tongue=1.0, rh=(150, -700 + 40 * math.sin(lt * 10)))
    if lt > 6.6:
        iris(ctx, W / 2, H / 2, lerp(1300, 0, ease_in((lt - 6.6) / 1.0)))
    return {}


# ----------------------------------------------------------------------------
# registro de la línea de tiempo completa
# ----------------------------------------------------------------------------
def build(mod):
    global K
    K = mod
    base = [s for s in mod.PREVIEW if s[2] is not mod.sc_black]
    full = base + [
        (62.6, 67.0, make_card('PRIMER ASALTO', '¡EL CORONEL CASCANUECES!', (0.10, 0.25, 0.45),
                               (0.16, 0.33, 0.56), 4.4)),
        (67.0, 77.5, sc_forest_arrive),
        (77.5, 87.0, sc_nut_talk),
        (87.0, 111.5, sc_nut_fight),
        (111.5, 116.0, make_card('SEGUNDO ASALTO', '¡ESCARCHA, EL MALVADO!', (0.12, 0.35, 0.50),
                                 (0.20, 0.45, 0.62), 4.5, (0.80, 0.93, 1.0))),
        (116.0, 126.5, sc_lake_arrive),
        (126.5, 155.5, sc_lake_fight),
        (155.5, 160.0, make_card('ASALTO FINAL', '¡EL KRAMPUS!', (0.06, 0.18, 0.08), (0.10, 0.28, 0.12), 4.5,
                                 (0.70, 0.95, 0.40))),
        (160.0, 169.0, sc_castle_intro),
        (169.0, 184.0, sc_castle_fight),
        (184.0, 196.5, sc_giant),
        (196.5, 206.2, sc_climb),
        (206.2, 214.0, sc_shrink),
        (214.0, 228.0, sc_return),
        (228.0, 233.0, sc_goodbye),
        (233.0, 241.5, sc_fin),
    ]
    # audio: la apertura sin el remate final de la previa
    aud = []
    for c in mod.PREVIEW_AUDIO:
        if c[0] == 'mus_villain' and c[3].get('offset'):
            c = (c[0], c[1], c[2], dict(c[3], fade_out=(61.6, 62.8)))
        aud.append(c)
    V, M, S = {'voice': True}, {'music': True}, {}
    aud += [
        ('mus_card', 62.6, 0.6, M),
        ('mus_forest', 70.0, 0.42, dict(M, fade_in=2.0, fade_out=(110.3, 111.5))),
        ('n04_bosque', 67.4, 1.0, V),
        ('sfx_march', 72.4, 0.55, S), ('sfx_march', 76.2, 0.45, S),
        ('c01_alto', 77.7, 1.0, V),
        ('sfx_march', 82.2, 0.4, S),
        ('j03_yaveremos', 84.25, 1.0, V),
        # pelea del cascanueces (lt = t - 87)
        ('sfx_walnut', 86.8, 0.6, S), ('sfx_boing', 87.3, 0.4, S),
        ('sfx_walnut', 88.4, 0.6, S), ('sfx_ping', 88.9, 0.6, S), ('sfx_bonk', 89.3, 0.6, S),
        ('sfx_walnut', 90.8, 0.55, S), ('sfx_walnut', 91.3, 0.55, S), ('sfx_walnut', 91.8, 0.55, S),
        ('sfx_ping', 94.0, 0.55, S), ('sfx_ping', 94.4, 0.55, S), ('sfx_ping', 94.8, 0.55, S),
        ('sfx_bonk', 95.2, 0.7, S),
        ('sfx_walnut', 97.0, 0.8, S), ('sfx_bat', 97.55, 0.9, S), ('sfx_bonk', 98.0, 0.8, S),
        ('sfx_teeth', 98.05, 0.7, S),
        ('c02_dientes', 98.6, 1.0, V),
        ('sfx_bat', 102.6, 0.8, S), ('sfx_woodcrash', 103.5, 0.9, S),
        ('mus_victory', 104.0, 0.6, M),
        ('n05_menos', 105.2, 1.0, V),
        # lago
        ('mus_card', 111.6, 0.6, M),
        ('mus_ice', 116.2, 0.42, dict(M, fade_out=(154.5, 155.6))),
        ('sfx_icecrack', 117.6, 0.6, S), ('sfx_icecrack', 119.0, 0.8, S), ('sfx_wind', 119.0, 0.5, S),
        ('e01_lago', 120.5, 1.05, V),
        ('sfx_blizzard', 127.0, 0.85, S), ('sfx_blizzard', 130.5, 0.4, S),
        ('v01_frio', 129.8, 1.0, V),
        ('sfx_icicles', 136.4, 0.7, S), ('sfx_icicles', 137.2, 0.6, S),
        ('sfx_twinkle', 138.0, 0.5, S),
        ('j04_chocolate', 138.4, 1.0, V),
        ('sfx_splash', 143.5, 0.9, S), ('sfx_sizzle', 144.0, 0.8, S),
        ('e02_derrito', 144.4, 1.0, V),
        ('mus_victory', 149.0, 0.6, M),
        ('n06_dos', 150.0, 1.0, V),
        # castillo
        ('mus_card', 155.6, 0.6, M),
        ('mus_final', 160.0, 0.45, dict(M, fade_out=(212.4, 214.2))),
        ('sfx_thunder', 160.2, 0.5, S),
        ('k02_otravez', 161.0, 1.05, V),
        ('sfx_chains', 166.5, 0.6, S), ('sfx_stomp', 167.4, 0.5, S),
        ('sfx_whip', 169.3, 0.7, S), ('sfx_boomjingle', 170.3, 0.8, S),
        ('sfx_whip', 170.6, 0.6, S), ('sfx_boomjingle', 171.6, 0.8, S),
        ('sfx_ping', 173.0, 0.6, S), ('sfx_ping', 173.4, 0.6, S), ('sfx_ping', 173.8, 0.6, S),
        ('sfx_bonk', 174.0, 0.5, S),
        ('sfx_whip', 175.2, 0.7, S), ('sfx_boomjingle', 176.2, 0.8, S),
        ('sfx_whip', 176.6, 0.6, S), ('sfx_bat', 177.75, 0.9, S), ('sfx_boomjingle', 178.2, 1.0, S),
        ('sfx_thunder', 179.5, 0.6, S), ('sfx_stomp', 181.0, 0.5, S),
        # gigante
        ('sfx_stretch', 184.2, 0.9, S), ('sfx_stomp', 185.5, 0.9, S), ('sfx_stomp', 187.0, 0.9, S),
        ('n07_crecio', 185.0, 1.0, V),
        ('sfx_stomp', 190.0, 0.9, S), ('sfx_stomp', 191.5, 0.9, S), ('sfx_whip', 192.3, 0.8, S),
        ('v02_campana', 193.0, 1.0, V),
        ('sfx_stomp', 196.8, 1.0, S),
        ('n08_trepo', 197.0, 1.0, V),
        ('sfx_zip', 197.4, 0.4, S),
        ('sfx_dong', 202.0, 1.0, S), ('sfx_bell', 202.05, 0.6, S),
        ('sfx_boing', 203.4, 0.4, S),
        # se encoge
        ('sfx_shrink', 206.3, 0.8, S), ('sfx_bleat', 208.0, 0.8, S), ('sfx_twinkle', 208.8, 0.6, S),
        ('mus_victory', 207.5, 0.5, M),
        # regreso
        ('mus_finale', 213.6, 0.5, dict(M, fade_out=(239.8, 241.5))),
        ('sfx_bell', 215.5, 0.8, S), ('sfx_cheer', 215.8, 0.6, S), ('sfx_sleigh', 214.5, 0.4, S),
        ('n09_asi', 217.0, 1.0, V),
        ('sfx_bleat', 224.5, 0.6, S),
        ('j05_feliz', 228.3, 1.0, V),
        ('v03_feliz', 230.0, 1.0, V),
        ('sfx_cheer', 231.0, 0.4, S),
        ('n10_colorin', 233.6, 1.0, V),
    ]
    return full, aud
