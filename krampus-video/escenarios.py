"""
escenarios.py - fondos pintados para "Jengi & Nieve en ¡La Noche del Krampus!"
Cielos, luna con cara, pueblito que baila, árbol de Navidad, torre del reloj,
bosque, lago helado, castillo del Krampus, nieve que cae.
"""
import math

import cairo

from toon import (BLUSH, BROWN, CREAM, GINGER, GOLD, GOLD_D, GREEN, GREEN_D, H, INK, LIME, MOUTH, RED, RED_D,
                  SNOW, SNOW_SH, W, WHITE, WINDOW, G, blob, blob_pts, catmull, circle, clamp, col, ease, eye,
                  fill_stroke, glow, golden_bell, line, lerp, mixc, mouth, nz, poly, sparkle, text, twos, u01)

NIGHT_TOP = (0.07, 0.09, 0.26)
NIGHT_BOT = (0.36, 0.30, 0.55)
STORM_TOP = (0.04, 0.10, 0.07)
STORM_BOT = (0.38, 0.56, 0.26)
PINE = (0.10, 0.33, 0.24)
PINE_D = (0.05, 0.20, 0.15)

WALLS = [(0.96, 0.88, 0.70), (0.93, 0.66, 0.60), (0.62, 0.80, 0.76), (0.98, 0.84, 0.48), (0.75, 0.68, 0.86),
         (0.90, 0.76, 0.58)]
ROOFS = [(0.70, 0.16, 0.18), (0.16, 0.42, 0.30), (0.42, 0.28, 0.20), (0.34, 0.40, 0.58), (0.62, 0.22, 0.40)]


# ----------------------------------------------------------------------------
# cielo
# ----------------------------------------------------------------------------
def sky(ctx, t, green=0.0, moon=(1520, 210), moon_mood='sleepy', stars=True, moon_r=105, horizon=H):
    top = mixc(NIGHT_TOP, STORM_TOP, green)
    bot = mixc(NIGHT_BOT, STORM_BOT, green)
    g = cairo.LinearGradient(0, 0, 0, horizon)
    g.add_color_stop_rgb(0, *top)
    g.add_color_stop_rgb(1, *bot)
    ctx.rectangle(-900, -900, W + 1800, H + 1800)
    ctx.set_source(g)
    ctx.fill()
    if stars:
        for i in range(190):
            x = u01(i, 1.1) * (W + 700) - 350
            y = u01(i, 2.2) ** 1.4 * horizon * 0.85 - 150
            tw = 0.55 + 0.45 * math.sin(t * (1.5 + u01(i, 3.3) * 3) + i)
            r = 2 + u01(i, 4.4) * 7
            sparkle(ctx, x, y, r * (0.7 + 0.3 * tw), mixc(CREAM, LIME, green * 0.6), 0.55 + 0.45 * tw,
                    rot=i * 0.3)
    if moon is not None:
        moon_face(ctx, moon[0], moon[1], moon_r, t, moon_mood, green)


def moon_face(ctx, x, y, r, t, mood='sleepy', green=0.0):
    glow(ctx, x, y, r * 2.4, mixc((1.0, 0.95, 0.75), LIME, green), 0.35)
    c = mixc((0.99, 0.93, 0.68), (0.80, 0.95, 0.60), green)
    blob(ctx, x, y, r, r, c, 6, seed=201, n=28)
    ctx.save()
    catmull(ctx, blob_pts(x, y, r, r, 28, seed=201))
    ctx.clip()
    blob(ctx, x - r * 0.4, y + r * 0.5, r * 0.9, r * 0.6, (0.90, 0.80, 0.50), 0, seed=202, a=0.45)
    for k, (dx, dy, cr) in enumerate([(0.45, -0.45, 0.16), (-0.5, 0.15, 0.12), (0.2, 0.55, 0.1)]):
        blob(ctx, x + dx * r, y + dy * r, cr * r, cr * r, (0.86, 0.76, 0.48), 3, seed=203 + k, a=0.7)
    ctx.restore()
    tt = twos(t)
    if mood == 'sleepy':
        for ex in (-0.32, 0.22):
            line(ctx, [(x + ex * r - 16, y - 8), (x + ex * r, y + 2), (x + ex * r + 16, y - 8)], 5)
        mouth(ctx, x - 4, y + r * 0.38, r * 0.45, 0.05, 1.0, 5)
        # Zzz
        for k in range(3):
            ph = (tt * 0.6 + k / 3) % 1
            text(ctx, 'z', x + r * 0.9 + ph * 60, y - r * 0.6 - ph * 90, 34 + k * 6, 'Luckiest Guy', CREAM,
                 INK, 5, a=1 - ph)
    elif mood == 'happy':
        eye(ctx, x - r * 0.32, y - 10, 14, 19, 0, 0, 0, 5)
        eye(ctx, x + r * 0.22, y - 10, 13, 18, 0, 0, 0, 5)
        mouth(ctx, x - 4, y + r * 0.35, r * 0.5, 0.5, 1.0, 5)
    else:  # scared
        j = math.sin(tt * 50) * 2
        eye(ctx, x - r * 0.32 + j, y - 12, 18, 26, 0.3, -0.3, 0, 5)
        eye(ctx, x + r * 0.22 + j, y - 12, 17, 25, 0.3, -0.3, 0, 5)
        blob(ctx, x - 4 + j, y + r * 0.45, 13, 17, MOUTH, 5, seed=205)
        line(ctx, [(x + r * 0.7, y - r * 0.3), (x + r * 0.78, y - r * 0.1)], 4, (0.5, 0.75, 0.95))


def storm_clouds(ctx, t, amt, y=140):
    if amt <= 0:
        return
    for i in range(7):
        x = ((u01(i, 7.7) * (W + 600) + t * (25 + i * 6)) % (W + 600)) - 300
        yy = y + u01(i, 8.8) * 160
        rx = 220 + u01(i, 9.9) * 160
        c = mixc((0.12, 0.20, 0.14), (0.25, 0.32, 0.22), u01(i, 6.6))
        ctx.save()
        ctx.translate(0, -(1 - amt) * 400)
        for k in range(4):
            blob(ctx, x + (k - 1.5) * rx * 0.45, yy + math.sin(k * 2.1) * 25, rx * 0.42, rx * 0.26, c, 5,
                 seed=i * 10 + k, a=amt)
        ctx.restore()


def lightning(ctx, x0, y0, x1, y1, seed, a=1.0):
    pts = [(x0, y0)]
    n = 9
    for k in range(1, n):
        u = k / n
        pts.append((lerp(x0, x1, u) + nz(k, seed) * 70, lerp(y0, y1, u)))
    pts.append((x1, y1))
    for wdt, c, aa in ((26, LIME, 0.35 * a), (12, (0.92, 1.0, 0.75), a), (4, WHITE, a)):
        line(ctx, pts, wdt, c, aa, smooth=False)


# ----------------------------------------------------------------------------
# colinas, pinos, montaña negra
# ----------------------------------------------------------------------------
def pine(ctx, x, y, h, c=PINE, snow=True, lw=5, seed=0.0):
    w = h * 0.55
    for k in range(3):
        ty = y - h * (0.25 + k * 0.27)
        tw = w * (1 - k * 0.25)
        pts = [(x, ty - h * 0.42), (x + tw / 2, ty + h * 0.08), (x + tw * 0.2, ty + h * 0.02), (x, ty + h * 0.1),
               (x - tw * 0.2, ty + h * 0.02), (x - tw / 2, ty + h * 0.08)]
        poly(ctx, pts, c, lw, smooth=False, seed=seed + k, wob=0.6)
        if snow:
            sp = [(x, ty - h * 0.42), (x + tw * 0.18, ty - h * 0.22), (x + tw * 0.06, ty - h * 0.24),
                  (x - tw * 0.05, ty - h * 0.19), (x - tw * 0.16, ty - h * 0.24)]
            poly(ctx, sp, SNOW, lw * 0.6, smooth=True, seed=seed + k + 5, wob=0.4)
    ctx.rectangle(x - h * 0.05, y - h * 0.14, h * 0.10, h * 0.14)
    fill_stroke(ctx, BROWN, lw * 0.8)


def hills(ctx, offx, y0, amp, c, seed, lw=6, pines=0, pine_h=90, pine_c=PINE, period=900.0):
    pts = []
    x = -300
    step = 60
    while x <= W + 300:
        wx = x + offx
        hgt = (math.sin(wx / period * 2 * math.pi + seed) * 0.6 + math.sin(wx / (period * 0.43) + seed * 2) * 0.4)
        pts.append((x, y0 - amp * (hgt * 0.5 + 0.5)))
        x += step
    ctx.move_to(-300, H + 300)
    for p in pts:
        ctx.line_to(*p)
    ctx.line_to(W + 300, H + 300)
    ctx.close_path()
    fill_stroke(ctx, c, lw)
    if pines:
        k0 = int(math.floor((offx - 300) / 140))
        for k in range(k0, k0 + int((W + 600) / 140) + 2):
            if u01(k, seed) < pines:
                wx = k * 140 + u01(k, seed + 1) * 80
                sx = wx - offx
                hgt = (math.sin(wx / period * 2 * math.pi + seed) * 0.6 + math.sin(wx / (period * 0.43) + seed * 2) * 0.4)
                sy = y0 - amp * (hgt * 0.5 + 0.5) + 14
                pine(ctx, sx, sy, pine_h * (0.8 + 0.4 * u01(k, seed + 2)), pine_c, True, 4, seed=k)


def black_mountain(ctx, x, y, s=1.0, t=0.0, glow_amt=0.6):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    pts = [(-420, 0), (-260, -160), (-160, -230), (-60, -380), (0, -430), (70, -360), (180, -250), (300, -150),
           (440, 0)]
    poly(ctx, pts, (0.10, 0.08, 0.13), 6, smooth=True, seed=301, wob=1)
    # castillo torcido
    ctx.save()
    ctx.translate(0, -420)
    for (tx, tw, th, lean) in ((-50, 40, 150, -0.12), (0, 56, 210, 0.05), (52, 38, 130, 0.15)):
        ctx.save()
        ctx.translate(tx, 0)
        ctx.rotate(lean)
        poly(ctx, [(-tw / 2, 10), (tw / 2, 10), (tw / 2 - 4, -th), (-tw / 2 + 4, -th)], (0.08, 0.06, 0.10), 5,
             smooth=False, seed=tx)
        poly(ctx, [(-tw / 2 - 8, -th), (tw / 2 + 8, -th), (0, -th - tw * 1.4)], (0.08, 0.06, 0.10), 5,
             smooth=False, seed=tx + 1)
        for k in range(2):
            wy = -th * (0.35 + k * 0.3)
            glow(ctx, 0, wy, 22, LIME, 0.5 * glow_amt * (0.7 + 0.3 * math.sin(t * 3 + tx)))
            ctx.rectangle(-5, wy - 8, 10, 16)
            col(ctx, mixc((0.3, 0.3, 0.2), LIME, glow_amt))
            ctx.fill()
        ctx.restore()
    ctx.restore()
    ctx.restore()


def snow_ground(ctx, y, offx=0.0, c=SNOW, shadow=SNOW_SH, lw=6):
    pts = []
    for k in range(-2, 26):
        x = k * 100 - (offx % 100)
        pts.append((x, y + 10 * math.sin((x + offx) / 140.0) + 6 * math.sin((x + offx) / 47.0)))
    ctx.move_to(-300, H + 300)
    for p in pts:
        ctx.line_to(*p)
    ctx.line_to(W + 300, H + 300)
    ctx.close_path()
    fill_stroke(ctx, c, lw)
    for k in range(-1, 8):
        x = k * 330 - (offx * 1.0 % 330)
        line(ctx, [(x, y + 70 + (k % 2) * 60), (x + 90, y + 62 + (k % 2) * 60), (x + 200, y + 74 + (k % 2) * 60)],
             5, shadow, 0.9)


# ----------------------------------------------------------------------------
# pueblito
# ----------------------------------------------------------------------------
def house(ctx, x, y, w, h, wall, roof, t, beat=0.0, seed=0, lit=1.0, chimney=True, scared=0.0):
    tt = twos(t)
    ctx.save()
    ctx.translate(x, y)
    sq = 0.05 * math.sin(beat)
    ctx.scale(1 - sq * 0.5, 1 + sq)
    lw = 5
    # chimenea y humo
    if chimney:
        cxp = w * (0.18 if seed % 2 else -0.22)
        poly(ctx, [(cxp - 18, -h - 30), (cxp + 18, -h - 30), (cxp + 18, -h - 105), (cxp - 18, -h - 105)],
             (0.60, 0.25, 0.20), lw, smooth=False, seed=seed + 0.3)
        for k in range(4):
            ph = (tt * 0.35 + k / 4 + seed * 0.13) % 1
            r = 12 + ph * 30
            blob(ctx, cxp + math.sin(ph * 6 + seed) * 20 + ph * 40, -h - 120 - ph * 170, r, r * 0.85,
                 (0.85, 0.82, 0.90), 4, seed=seed + k, a=(1 - ph) * 0.85)
    # paredes
    poly(ctx, [(-w / 2, 0), (w / 2, 0), (w / 2 - 2, -h), (-w / 2 + 2, -h)], wall, lw, smooth=False, seed=seed)
    # techo
    rh = h * 0.75
    poly(ctx, [(-w / 2 - 22, -h + 6), (w / 2 + 22, -h + 6), (w * 0.05, -h - rh)], roof, lw, smooth=False,
         seed=seed + 0.5)
    # nieve en el techo
    sp = [(-w / 2 - 26, -h + 4), (-w / 2 - 6, -h - 14), (w * 0.05 - 16, -h - rh + 8), (w * 0.05, -h - rh - 8),
          (w * 0.05 + 16, -h - rh + 8), (w / 2 + 6, -h - 14), (w / 2 + 26, -h + 4), (w / 2, -h - 2),
          (w * 0.05, -h - rh + 30), (-w / 2, -h - 2)]
    poly(ctx, sp, SNOW, lw, smooth=True, seed=seed + 0.7, wob=0.8)
    for k in range(3):
        ix = -w / 2 + 20 + k * (w - 40) / 2
        line(ctx, [(ix, -h + 6), (ix, -h + 22 + 6 * (k % 2))], 7, SNOW)
    # ventanas encendidas
    nwin = 2 if w < 200 else 3
    for k in range(nwin):
        wx = -w / 2 + (k + 0.5) * w / nwin
        wy = -h * 0.62
        flick = lit * (0.85 + 0.15 * math.sin(t * 5 + seed + k))
        glow(ctx, wx, wy, 60, WINDOW, 0.35 * flick)
        ctx.rectangle(wx - 20, wy - 26, 40, 52)
        fill_stroke(ctx, mixc((0.25, 0.20, 0.30), WINDOW, flick), lw)
        line(ctx, [(wx, wy - 26), (wx, wy + 26)], 4)
        line(ctx, [(wx - 20, wy), (wx + 20, wy)], 4)
        if scared > 0:
            # ojitos asomados en la ventana
            eye(ctx, wx - 8, wy + 6, 6, 9, 0.2, 0, 0, 3)
            eye(ctx, wx + 8, wy + 6, 6, 9, 0.2, 0, 0, 3)
    # puerta con corona
    dx = w * 0.18 if seed % 2 else -w * 0.2
    poly(ctx, [(dx - 24, 0), (dx + 24, 0), (dx + 24, -78), (dx, -94), (dx - 24, -78)], (0.45, 0.22, 0.14), lw,
         smooth=False, seed=seed + 0.9)
    circle(ctx, dx + 13, -40, 4, GOLD, 2)
    ctx.arc(dx, -66, 14, 0, 2 * math.pi)
    col(ctx, GREEN)
    ctx.set_line_width(9)
    ctx.stroke()
    circle(ctx, dx, -52, 5, RED, 2)
    ctx.restore()


def village(ctx, offx, base_y, t, s=1.0, beat_amp=1.0, n=14, seed=0, lit=1.0, scared=0.0, bpm=2.0):
    spacing = 270 * s
    k0 = int(math.floor(offx / spacing)) - 1
    for k in range(k0, k0 + int(W / spacing) + 3):
        sx = k * spacing - offx
        wdt = (170 + 70 * u01(k, seed + 1)) * s
        hgt = (150 + 90 * u01(k, seed + 2)) * s
        wall = WALLS[int(u01(k, seed + 3) * len(WALLS)) % len(WALLS)]
        roof = ROOFS[int(u01(k, seed + 4) * len(ROOFS)) % len(ROOFS)]
        beat = (twos(t) * bpm * 2 * math.pi + k * 1.3) * beat_amp
        ctx.save()
        ctx.translate(sx, base_y + u01(k, seed + 5) * 10 * s)
        ctx.scale(s, s)
        house(ctx, 0, 0, wdt / s, hgt / s, wall, roof, t, beat if beat_amp > 0 else 0, seed=k, lit=lit,
              scared=scared)
        ctx.restore()


def lamppost(ctx, x, y, s=1.0, t=0.0, lit=1.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    glow(ctx, 0, -300, 140, WINDOW, 0.45 * lit)
    poly(ctx, [(-8, 0), (8, 0), (6, -270), (-6, -270)], (0.18, 0.16, 0.20), 4, smooth=False, seed=x)
    poly(ctx, [(-30, -270), (30, -270), (20, -330), (-20, -330)], mixc((0.3, 0.3, 0.3), WINDOW, lit), 5,
         smooth=False, seed=x + 1)
    poly(ctx, [(-38, -330), (38, -330), (0, -360)], (0.18, 0.16, 0.20), 5, smooth=False, seed=x + 2)
    blob(ctx, 0, -360, 34, 9, SNOW, 4, seed=x + 3)
    # lazo navideño
    blob(ctx, -14, -250, 12, 8, RED, 3, rot=0.4, seed=x + 4)
    blob(ctx, 14, -250, 12, 8, RED, 3, rot=-0.4, seed=x + 5)
    ctx.restore()


# ----------------------------------------------------------------------------
# árbol de navidad de la plaza
# ----------------------------------------------------------------------------
ORN = [RED, GOLD, (0.25, 0.45, 0.85), (0.85, 0.35, 0.70), WHITE]


def xmas_tree(ctx, x, y, s=1.0, t=0.0, bell=True, bell_sw=0.0, beat=0.0, lights=1.0, bell_shine=0.0):
    tt = twos(t)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    sq = 0.03 * math.sin(beat)
    ctx.scale(1 - sq * 0.5, 1 + sq)
    lw = 6
    ctx.rectangle(-40, -90, 80, 90)
    fill_stroke(ctx, BROWN, lw)
    # maceta / cubeta
    poly(ctx, [(-90, 0), (90, 0), (70, -95), (-70, -95)], RED, lw, smooth=False, seed=401)
    line(ctx, [(-80, -50), (80, -50)], 8, GOLD)
    tiers = [(-95, 300, 210), (-270, 250, 200), (-430, 195, 185), (-575, 140, 165)]
    for i, (ty, tw, th) in enumerate(tiers):
        pts = [(0, ty - th)]
        nsc = 7
        for k in range(nsc + 1):
            u = k / nsc
            px = lerp(tw, -tw, u)
            pts.append((px, ty + (12 if k % 2 == 0 else -4)))
        poly(ctx, pts, GREEN, lw, smooth=False, seed=410 + i, wob=0.8)
        ctx.save()
        catmull(ctx, pts)
        ctx.clip()
        poly(ctx, [(0, ty - th), (-tw, ty + 20), (-tw * 0.2, ty + 20)], GREEN_D, 0, smooth=False, seed=420 + i)
        ctx.restore()
        # guirnalda dorada
        gp = []
        for k in range(13):
            u = k / 12
            gp.append((lerp(-tw * 0.85, tw * 0.85, u), ty - th * 0.30 + math.sin(u * math.pi) * 34 + u * 22))
        line(ctx, gp, 6, GOLD_D)
        for k in range(1, 12, 2):
            circle(ctx, gp[k][0], gp[k][1], 6, GOLD, 2.5)
        # adornos y luces
        for k in range(5):
            u = (k + 0.5) / 5
            ox = lerp(-tw * 0.75, tw * 0.75, u) * (0.6 + 0.4 * (i % 2))
            oy = ty - 14 - (k % 2) * 30
            if abs(ox) < tw * (1 - (ty - oy) / th) * 0.95 + 20:
                c = ORN[(i * 5 + k) % len(ORN)]
                circle(ctx, ox, oy, 15, c, 4)
                circle(ctx, ox - 5, oy - 5, 4, WHITE, 0, 0.85)
        for k in range(6):
            u = (k + 0.3) / 6
            lx = lerp(-tw * 0.6, tw * 0.6, u)
            ly = ty - th * 0.62 + (k % 3) * 18
            on = lights * (0.5 + 0.5 * math.sin(tt * 6 + k * 2 + i))
            lc = [(1, 0.4, 0.3), (1, 0.9, 0.4), (0.5, 0.8, 1.0)][(k + i) % 3]
            glow(ctx, lx, ly, 26, lc, 0.6 * on)
            circle(ctx, lx, ly, 6, mixc((0.4, 0.4, 0.4), lc, on), 2.5)
    top_y = -575 - 165
    if bell:
        golden_bell(ctx, 0, top_y - 40, 0.95, bell_sw, shine=bell_shine)
    ctx.restore()
    return (x, y + (top_y - 40) * s)


# ----------------------------------------------------------------------------
# torre del reloj (con cara)
# ----------------------------------------------------------------------------
def clocktower(ctx, x, y, s=1.0, t=0.0, scared=0.0, green=0.0):
    tt = twos(t)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    lw = 6
    brick = mixc((0.70, 0.40, 0.32), (0.45, 0.50, 0.32), green * 0.5)
    poly(ctx, [(-110, 0), (110, 0), (95, -620), (-95, -620)], brick, lw, smooth=False, seed=501)
    for r in range(12):
        yy = -40 - r * 48
        for c in range(4):
            bx = -80 + c * 50 + (r % 2) * 25
            line(ctx, [(bx, yy), (bx + 30, yy)], 3, (0.50, 0.26, 0.20), 0.6, smooth=False)
    # puerta
    poly(ctx, [(-40, 0), (40, 0), (40, -110), (0, -140), (-40, -110)], (0.35, 0.18, 0.12), lw, smooth=False,
         seed=502)
    # almenas
    for k in range(5):
        ctx.rectangle(-108 + k * 46, -660, 32, 44)
        fill_stroke(ctx, brick, lw)
    ctx.rectangle(-112, -626, 224, 22)
    fill_stroke(ctx, (0.55, 0.30, 0.24), lw)
    for k in range(5):
        blob(ctx, -92 + k * 46, -662, 20, 7, SNOW, 3, seed=510 + k)
    # reloj con cara
    cy = -440
    circle(ctx, 0, cy, 92, (0.98, 0.94, 0.80), lw)
    circle(ctx, 0, cy, 76, None, 3)
    for k in range(12):
        a = k * math.pi / 6
        line(ctx, [(math.cos(a) * 64, cy + math.sin(a) * 64), (math.cos(a) * 74, cy + math.sin(a) * 74)], 5)
    j = math.sin(tt * 50) * 2 * scared
    ex = 26
    if scared > 0.5:
        eye(ctx, -ex + j, cy - 18, 15, 22, 0.4, -0.2, 0, 4.5)
        eye(ctx, ex + j, cy - 18, 15, 22, 0.4, -0.2, 0, 4.5)
        blob(ctx, 0 + j, cy + 34, 12, 15, MOUTH, 4, seed=520)
    else:
        bl = 1.0 if (tt % 3.1) < 0.15 else 0.0
        eye(ctx, -ex, cy - 16, 13, 18, 0.0, 0.1, bl, 4.5)
        eye(ctx, ex, cy - 16, 13, 18, 0.0, 0.1, bl, 4.5)
        mouth(ctx, 0, cy + 28, 50, 0.35, 1.0, 4.5)
    # manecillas como bigote
    ah = tt * 0.4
    line(ctx, [(0, cy + 8), (math.cos(ah) * 50, cy + 8 + math.sin(ah) * 50)], 6)
    ctx.restore()


# ----------------------------------------------------------------------------
# nieve cayendo
# ----------------------------------------------------------------------------
def snowfall(ctx, t, n=120, layer=0, wind=30.0, a=0.95, seed=0.0, speed=1.0):
    size = (3.0, 5.0, 8.0)[layer]
    vy = (55, 85, 130)[layer] * speed
    for i in range(n):
        x0 = u01(i, 11.1 + layer + seed) * (W + 200)
        y0 = u01(i, 12.2 + layer + seed) * (H + 100)
        x = (x0 + wind * t + math.sin(t * (0.8 + u01(i, 13.3)) + i) * 25) % (W + 200) - 100
        y = (y0 + vy * t) % (H + 100) - 50
        r = size * (0.7 + 0.6 * u01(i, 14.4 + layer))
        circle(ctx, x, y, r, (0.98, 0.98, 1.0), 0, a)


# ----------------------------------------------------------------------------
# tarjetas y transiciones
# ----------------------------------------------------------------------------
def sunburst(ctx, cx, cy, t, c1, c2, n=28, speed=0.05):
    ctx.rectangle(-100, -100, W + 200, H + 200)
    col(ctx, c1)
    ctx.fill()
    R = 2400
    for k in range(n):
        if k % 2:
            continue
        a0 = t * speed + k * 2 * math.pi / n
        a1 = a0 + 2 * math.pi / n
        ctx.move_to(cx, cy)
        ctx.line_to(cx + math.cos(a0) * R, cy + math.sin(a0) * R)
        ctx.line_to(cx + math.cos(a1) * R, cy + math.sin(a1) * R)
        ctx.close_path()
        col(ctx, c2)
        ctx.fill()


def holly(ctx, x, y, s=1.0, rot=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(s, s)
    for a in (-0.6, 0.6, math.pi):
        ctx.save()
        ctx.rotate(a)
        pts = [(0, 0), (20, -14), (34, -8), (48, -20), (62, -8), (78, -14), (92, 0), (78, 14), (62, 8), (48, 20),
               (34, 8), (20, 14)]
        poly(ctx, pts, GREEN, 4.5, smooth=False, seed=a * 10)
        line(ctx, [(4, 0), (86, 0)], 3, GREEN_D)
        ctx.restore()
    for k in range(3):
        circle(ctx, -8 + k * 10, -10 + (k % 2) * 12, 11, RED, 4)
        circle(ctx, -11 + k * 10, -14 + (k % 2) * 12, 3, WHITE, 0, 0.8)
    ctx.restore()


def deco_frame(ctx, inset=40, c=GOLD, lw=10):
    x0, y0, x1, y1 = inset, inset, W - inset, H - inset
    for k, (wdt, cc) in enumerate(((lw + 8, INK), (lw, c))):
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
        col(ctx, cc)
        ctx.set_line_width(wdt)
        ctx.stroke()
    i2 = inset + 26
    ctx.rectangle(i2, i2, W - 2 * i2, H - 2 * i2)
    col(ctx, INK)
    ctx.set_line_width(4)
    ctx.stroke()
    # esquinas art-deco
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        for r in (60, 90, 120):
            ctx.arc(cx, cy, r, 0, 2 * math.pi)
            ctx.save()
            ctx.rectangle(min(cx, cx + sx * 140), min(cy, cy + sy * 140), 140, 140)
            ctx.clip()
            ctx.arc(cx, cy, r, 0, 2 * math.pi)
            col(ctx, INK)
            ctx.set_line_width(14)
            ctx.stroke_preserve()
            col(ctx, c)
            ctx.set_line_width(7)
            ctx.stroke()
            ctx.restore()
            ctx.new_path()


def leader(ctx, t, n):
    """Cuenta regresiva de película antigua."""
    ctx.rectangle(-100, -100, W + 200, H + 200)
    col(ctx, (0.80, 0.78, 0.72))
    ctx.fill()
    cx, cy = W / 2, H / 2
    frac = t % 1.0
    ctx.move_to(cx, cy)
    ctx.arc(cx, cy, 900, -math.pi / 2, -math.pi / 2 + frac * 2 * math.pi)
    ctx.close_path()
    col(ctx, (0.55, 0.53, 0.48))
    ctx.fill()
    for r in (330, 400):
        ctx.arc(cx, cy, r, 0, 2 * math.pi)
        col(ctx, WHITE)
        ctx.set_line_width(10)
        ctx.stroke()
    line(ctx, [(0, cy), (W, cy)], 5, INK, 0.7, smooth=False)
    line(ctx, [(cx, 0), (cx, H)], 5, INK, 0.7, smooth=False)
    text(ctx, str(n), cx, cy + 30, 520, 'Limelight', WHITE, INK, 14)
