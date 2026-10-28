"""
Utilidades de dibujo (cairo) y personajes del video:
  - Hana: la chica (perfil, poses de pie / caminando / sentada, dos atuendos)
  - Mochi: su gato atigrado naranja (sentado, caminando, comiendo, dormido)
  - Elementos de escenario estilo anime: nubes cumulo, arboles, casas, postes...
Todas las coordenadas de diseno estan en pixeles de 1920x1080.
"""
import math
import random

import cairo

W, H = 1920, 1080
TAU = 2 * math.pi
FONT = "Klee One"


# ----------------------------------------------------------------------------
# utilidades basicas
# ----------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def window(t, a, b, fade=0.6):
    """1 dentro de [a,b] con rampas suaves de entrada/salida."""
    return ease((t - a) / fade) * ease((b - t) / fade)


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def col(c):
    return hexc(c) if isinstance(c, str) else c


def mix(a, b, t):
    a, b = col(a), col(b)
    return tuple(lerp(a[i], b[i], t) for i in range(3))


def shade(c, k):
    """k<0 oscurece, k>0 aclara."""
    c = col(c)
    return mix(c, (0, 0, 0), -k) if k < 0 else mix(c, (1, 1, 1), k)


def src(ctx, c, a=1.0):
    c = col(c)
    ctx.set_source_rgba(c[0], c[1], c[2], a)


def lin(ctx, x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for st in stops:
        o, c = st[0], col(st[1])
        a = st[2] if len(st) > 2 else 1.0
        g.add_color_stop_rgba(o, c[0], c[1], c[2], a)
    ctx.set_source(g)


def rad(ctx, cx, cy, r0, r1, stops):
    g = cairo.RadialGradient(cx, cy, r0, cx, cy, r1)
    for st in stops:
        o, c = st[0], col(st[1])
        a = st[2] if len(st) > 2 else 1.0
        g.add_color_stop_rgba(o, c[0], c[1], c[2], a)
    ctx.set_source(g)


def ell(ctx, x, y, rx, ry):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(max(rx, 1e-3), max(ry, 1e-3))
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()


def fell(ctx, x, y, rx, ry, c, a=1.0):
    ell(ctx, x, y, rx, ry)
    src(ctx, c, a)
    ctx.fill()


def circ(ctx, x, y, r, c, a=1.0):
    ctx.arc(x, y, max(r, 0.01), 0, TAU)
    src(ctx, c, a)
    ctx.fill()


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def frect(ctx, x, y, w, h, c, a=1.0, r=0):
    if r:
        rrect(ctx, x, y, w, h, r)
    else:
        ctx.rectangle(x, y, w, h)
    src(ctx, c, a)
    ctx.fill()


def poly(ctx, pts, close=True):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    if close:
        ctx.close_path()


def fpoly(ctx, pts, c, a=1.0):
    poly(ctx, pts)
    src(ctx, c, a)
    ctx.fill()


def line(ctx, x0, y0, x1, y1, c, w, a=1.0, cap=cairo.LINE_CAP_ROUND):
    ctx.set_line_cap(cap)
    ctx.move_to(x0, y0)
    ctx.line_to(x1, y1)
    src(ctx, c, a)
    ctx.set_line_width(w)
    ctx.stroke()


def glow(ctx, x, y, r, c, a=1.0):
    rad(ctx, x, y, 0, r, [(0, c, a), (0.35, c, a * 0.45), (1, c, 0)])
    ctx.arc(x, y, r, 0, TAU)
    ctx.fill()


def sparkle(ctx, x, y, r, c='#fffbe8', a=1.0):
    if a <= 0.01 or r <= 0.2:
        return
    glow(ctx, x, y, r * 2.2, c, 0.35 * a)
    ctx.move_to(x, y - r)
    for k in range(4):
        ang = -math.pi / 2 + (k + 0.5) * math.pi / 2
        ctx.line_to(x + math.cos(ang) * r * 0.22, y + math.sin(ang) * r * 0.22)
        ang2 = -math.pi / 2 + (k + 1) * math.pi / 2
        ctx.line_to(x + math.cos(ang2) * r, y + math.sin(ang2) * r)
    ctx.close_path()
    src(ctx, c, a)
    ctx.fill()


def text(ctx, s, x, y, size, c='#fffaf0', a=1.0, align='center', shadow=0.35, weight=cairo.FONT_WEIGHT_NORMAL,
         font=FONT):
    if a <= 0.01:
        return
    ctx.select_font_face(font, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    if align == 'center':
        tx = x - ext.x_advance / 2
    elif align == 'right':
        tx = x - ext.x_advance
    else:
        tx = x
    if shadow:
        for dx, dy, al in ((0, size * 0.05, shadow), (0, 0, shadow * 0.5)):
            ctx.move_to(tx + dx, y + dy)
            ctx.text_path(s)
            src(ctx, '#2a1e2e', a * al)
            ctx.set_line_width(size * 0.09)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke()
    ctx.move_to(tx, y)
    src(ctx, c, a)
    ctx.show_text(s)


def group_alpha(ctx, a, fn):
    if a <= 0.005:
        return
    if a >= 0.995:
        fn()
        return
    ctx.push_group()
    fn()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(a)


def ik(sx, sy, tx, ty, l1, l2, bend=-1):
    """IK de dos segmentos. Angulos medidos desde 'abajo', positivos hacia +x."""
    dx, dy = tx - sx, ty - sy
    d = math.hypot(dx, dy)
    d = min(max(d, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    base = math.atan2(dx, dy)
    alpha = math.acos(clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1))
    beta = math.acos(clamp((l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2), -1, 1))
    return base + bend * alpha, -bend * (math.pi - beta)


def seg_end(x, y, a, l):
    return x + l * math.sin(a), y + l * math.cos(a)


def limb(ctx, x0, y0, a1, l1, a2, l2, w1, w2, c):
    x1, y1 = seg_end(x0, y0, a1, l1)
    x2, y2 = seg_end(x1, y1, a1 + a2, l2)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    src(ctx, c)
    ctx.set_line_width(w1)
    ctx.move_to(x0, y0)
    ctx.line_to(x1, y1)
    ctx.stroke()
    ctx.set_line_width(w2)
    ctx.move_to(x1, y1)
    ctx.line_to(x2, y2)
    ctx.stroke()
    return (x1, y1), (x2, y2)


# ----------------------------------------------------------------------------
# Hana
# ----------------------------------------------------------------------------
SKIN = hexc('#f8dcc8')
SKIN_SH = hexc('#e8b9a2')
HAIR = hexc('#4b302b')
HAIR_HI = hexc('#7a5143')
EYE = hexc('#3b2421')
BLUSH = hexc('#f2979a')
RIBBON = hexc('#d9534f')

OUTFIT = {
    'home': dict(top=hexc('#f3e6cb'), skirt=hexc('#c99a6b'), apron=hexc('#8fb08f'),
                 legs=SKIN, sock=hexc('#fdfaf3'), shoe=hexc('#e7a3a0'), collar=None, bag=None),
    'night': dict(top=hexc('#2a3d72'), skirt=hexc('#2a3d72'), apron=None,
                  legs=hexc('#2d2735'), sock=None, shoe=hexc('#7a4630'),
                  collar=hexc('#f6f1e7'), bag=hexc('#a06a44')),
}


def _blink(t, seed=0.0):
    p = (t * 0.31 + seed) % 1.0
    if p < 0.035:
        return abs(p / 0.0175 - 1.0)
    return 1.0


def draw_girl(ctx, x, y, s, t, facing=1, outfit='home', walk=None, sit=False,
              near=None, far=None, lean=0.0, head_tilt=0.0, eyes='auto',
              mouth='smile', wind=0.0, headphones=False, hold_near=None,
              hold_far=None, alpha=1.0, outfit_mix=None):
    """Dibuja a Hana. (x,y)=punto entre los pies (o el suelo bajo la silla si sit).
    near/far: None | ('ik', wx, wy) en coords de mundo | ('ang', a1, a2)."""
    if outfit_mix is not None:
        # transformacion magica: mezcla de dos atuendos
        a0, a1_, m = outfit_mix
        kw = dict(facing=facing, walk=walk, sit=sit, near=near, far=far, lean=lean,
                  head_tilt=head_tilt, eyes=eyes, mouth=mouth, wind=wind,
                  headphones=headphones, hold_near=hold_near, hold_far=hold_far)
        group_alpha(ctx, alpha * (1 - m), lambda: draw_girl(ctx, x, y, s, t, outfit=a0, **kw))
        group_alpha(ctx, alpha * m, lambda: draw_girl(ctx, x, y, s, t, outfit=a1_, **kw))
        return
    if alpha < 0.995:
        group_alpha(ctx, alpha, lambda: draw_girl(
            ctx, x, y, s, t, facing, outfit, walk, sit, near, far, lean, head_tilt, eyes,
            mouth, wind, headphones, hold_near, hold_far, 1.0))
        return
    o = OUTFIT[outfit]
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * facing, s)

    # --- piernas / cadera
    if sit:
        hx, hy = 0.0, -46.0
        legs = [(math.pi / 2 - 0.05, -(math.pi / 2 - 0.05)), (math.pi / 2 - 0.13, -(math.pi / 2 - 0.13))]
        dnear, dfar = (0.35, 0.95), (0.2, 0.9)
        hem = 0
    elif walk is not None:
        ph = walk
        an, af = 0.40 * math.sin(ph), 0.40 * math.sin(ph + math.pi)
        kn = -0.85 * max(0.0, math.cos(ph))
        kf = -0.85 * max(0.0, math.cos(ph + math.pi))
        hx, hy = 0.0, -90.0 + 90 * (1 - math.cos(an)) - 1.5
        legs = [(af, kf), (an, kn)]
        dnear, dfar = (-0.36 * math.sin(ph), 0.28), (0.36 * math.sin(ph), 0.28)
        hem = 2.5 * math.sin(ph)
    else:
        hx, hy = 0.0, -90.0
        legs = [(-0.05, 0.03), (0.05, 0.0)]
        dnear, dfar = (0.06, 0.12), (-0.06, 0.1)
        hem = 0

    cl, sl = math.cos(lean), math.sin(lean)

    def to_hip(wx, wy):
        lx = (wx - x) / (s * facing) - hx
        ly = (wy - y) / s - hy
        return lx * cl + ly * sl, -lx * sl + ly * cl

    SHX, SHY, L1, L2 = 1.0, -44.0, 27.0, 25.0

    def arm_angles(spec, dflt):
        if spec is None:
            return dflt
        if spec[0] == 'ang':
            return spec[1], spec[2]
        tx, ty = to_hip(spec[1], spec[2])
        return ik(SHX, SHY, tx, ty, L1, L2, bend=-1)

    na = arm_angles(near, dnear)
    fa = arm_angles(far, dfar)

    def hip_frame():
        ctx.translate(hx, hy)
        ctx.rotate(lean)

    def head_frame():
        hip_frame()
        ctx.translate(3, -74)
        ctx.rotate(head_tilt)

    # 1. pelo trasero
    ctx.save()
    head_frame()
    wv = wind * (5 + 3 * math.sin(t * 7.0))
    ctx.move_to(-6, -22)
    ctx.curve_to(-30, -18, -30, 6, -26 - wv, 26)
    ctx.curve_to(-24 - wv, 33, -14 - wv * 0.6, 33, -9, 29)
    ctx.curve_to(-4, 27, 0, 24, 2, 18)
    ctx.line_to(4, -10)
    ctx.close_path()
    src(ctx, HAIR)
    ctx.fill()
    ctx.restore()

    # 2. brazo lejano
    def draw_arm(a, c, hold):
        e, hnd = limb(ctx, SHX, SHY, a[0], L1, a[1], L2, 8.5, 7.5, c)
        circ(ctx, hnd[0], hnd[1], 4.6, SKIN if c == o['top'] else shade(SKIN, -0.08))
        if hold:
            hold(ctx, hnd, a[0] + a[1])

    ctx.save()
    hip_frame()
    draw_arm(fa, shade(o['top'], -0.18), hold_far)
    ctx.restore()

    # 3. piernas
    for i, (a1, a2) in enumerate(legs):
        lc = o['legs'] if i == 1 else shade(o['legs'], -0.12)
        (kx, ky), (fx, fy) = limb(ctx, hx + (0 if i else -2), hy, a1, 46, a2, 44, 12.5, 10, lc)
        if o['sock']:
            sx_, sy_ = lerp(kx, fx, 0.6), lerp(ky, fy, 0.6)
            line(ctx, sx_, sy_, fx, fy, o['sock'] if i else shade(o['sock'], -0.1), 10.5)
        ctx.save()
        ctx.translate(fx, fy)
        ctx.rotate(-(a1 + a2))
        fell(ctx, 4, 1.5, 8.5, 4.6, o['shoe'] if i else shade(o['shoe'], -0.15))
        ctx.restore()

    # 4. falda + torso
    ctx.save()
    hip_frame()
    sk = o['skirt']
    if sit:
        ctx.move_to(-13, -6)
        ctx.line_to(10, -6)
        ctx.curve_to(28, -8, 42, -7, 47, 0)
        ctx.line_to(48, 9)
        ctx.curve_to(30, 12, 2, 13, -15, 9)
        ctx.close_path()
    else:
        ctx.move_to(-12, -6)
        ctx.line_to(12, -6)
        ctx.curve_to(16, 8, 20, 22, 23 + hem, 37)
        ctx.curve_to(16 + hem, 40, 9 + hem, 36, 2 + hem, 39)
        ctx.curve_to(-6 + hem, 41, -12 + hem, 37, -19 + hem, 38)
        ctx.curve_to(-18, 22, -16, 8, -12, -6)
        ctx.close_path()
    src(ctx, sk)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    if not sit:
        line(ctx, 3, 2, 4 + hem, 38, shade(sk, -0.15), 2.2, 0.8)
        line(ctx, -8, 4, -11 + hem, 38, shade(sk, -0.15), 2.0, 0.6)
    lin(ctx, 0, -6, 0, 40, [(0, '#000000', 0.12), (0.5, '#000000', 0.0)])
    ctx.paint()
    ctx.restore()
    ctx.new_path()

    # cuello
    frect(ctx, -2.5, -54, 8, 12, SKIN_SH)
    # torso
    ctx.move_to(-11, -2)
    ctx.curve_to(-13, -20, -12, -38, -8, -48)
    ctx.line_to(7, -48)
    ctx.curve_to(12, -41, 14, -30, 12, -18)
    ctx.curve_to(11, -10, 11, -5, 11, -2)
    ctx.close_path()
    src(ctx, o['top'])
    ctx.fill()
    line(ctx, -12, -3, 11.5, -3, shade(o['top'], -0.2), 2.4)  # cintura
    if o['apron']:
        ap = o['apron']
        fpoly(ctx, [(3, -35), (12.5, -33), (12, -3), (2, -3)], ap)
        line(ctx, 5, -35, -4, -47, ap, 2.2)
        if not sit:
            ctx.move_to(0, -4)
            ctx.line_to(14, -4)
            ctx.curve_to(17, 10, 20, 22, 22 + hem, 33)
            ctx.line_to(4 + hem, 35)
            ctx.close_path()
            src(ctx, ap)
            ctx.fill()
            line(ctx, 8, 2, 11 + hem, 32, shade(ap, -0.15), 1.6, 0.7)
        # lazo a la espalda
        fell(ctx, -14, -6, 4, 3, ap)
        fell(ctx, -16, -1, 3, 4.5, shade(ap, -0.1))
    if o['collar']:
        ctx.move_to(-6, -48)
        ctx.curve_to(-2, -41, 6, -40, 12, -44)
        ctx.line_to(7, -49)
        ctx.close_path()
        src(ctx, o['collar'])
        ctx.fill()
        fell(ctx, 10, -44, 2.6, 2, RIBBON)
        fell(ctx, 13, -45.5, 2.4, 1.7, RIBBON)
        fell(ctx, 13, -42.5, 2.4, 1.7, RIBBON)
        # botones
        for k in range(3):
            circ(ctx, 10.5, -34 + k * 9, 1.1, '#e7dccb')
    if o['bag']:
        line(ctx, 6, -47, -13, -4, shade(o['bag'], -0.2), 1.8)
        frect(ctx, -22, -6, 15, 13, o['bag'], r=3)
        frect(ctx, -22, -6, 15, 5, shade(o['bag'], -0.18), r=2)
        circ(ctx, -14.5, -1, 1.3, '#f1d38a')
    ctx.restore()

    # 5. brazo cercano
    ctx.save()
    hip_frame()
    draw_arm(na, o['top'], hold_near)
    ctx.restore()

    # 6. cabeza
    ctx.save()
    head_frame()
    # cara
    fell(ctx, 1, 0, 20, 21, SKIN)
    ctx.move_to(-8, 8)
    ctx.curve_to(0, 22, 12, 23, 19.5, 11)
    ctx.line_to(20.5, 0)
    ctx.line_to(-6, 0)
    ctx.close_path()
    src(ctx, SKIN)
    ctx.fill()
    fell(ctx, -3, 3, 4.2, 5.2, SKIN_SH)
    # mejillas
    fell(ctx, 12.5, 7, 5, 2.4, BLUSH, 0.5)
    # nariz y boca
    line(ctx, 20.6, 1.5, 21.4, 3.6, SKIN_SH, 1.3)
    mc = hexc('#a5524a')
    if mouth == 'open' or (mouth == 'chew' and math.sin(t * 9) > 0.3):
        fell(ctx, 16.5, 11.2, 1.9, 1.7, mc)
    elif mouth == 'sip':
        fell(ctx, 17.5, 11, 1.2, 1.0, mc)
    else:
        ctx.move_to(14, 10.4)
        ctx.curve_to(15.5, 12.2, 17, 12.2, 18.3, 10.2)
        src(ctx, mc)
        ctx.set_line_width(1.25)
        ctx.stroke()
    # ojos
    b = _blink(t) if eyes == 'auto' else 1.0
    ex, ey = 11.0, -2.0
    if eyes == 'happy':
        ctx.move_to(ex - 4, ey + 1.5)
        ctx.curve_to(ex - 2, ey - 3.5, ex + 2, ey - 3.5, ex + 4, ey + 1.5)
        src(ctx, EYE)
        ctx.set_line_width(1.8)
        ctx.stroke()
    elif eyes == 'closed' or b < 0.25:
        ctx.move_to(ex - 4, ey)
        ctx.curve_to(ex - 2, ey + 2.5, ex + 2, ey + 2.5, ex + 4, ey)
        src(ctx, EYE)
        ctx.set_line_width(1.7)
        ctx.stroke()
    else:
        fell(ctx, ex, ey, 3.7, 5.5 * b, EYE)
        fell(ctx, ex + 0.3, ey + 1.8 * b, 2.6, 3.0 * b, '#7a4b3a')
        fell(ctx, ex + 0.2, ey + 0.4 * b, 1.6, 2.4 * b, EYE)
        circ(ctx, ex + 1.2, ey - 2.2 * b, 1.5, '#ffffff')
        circ(ctx, ex - 1.2, ey + 2.6 * b, 0.7, '#ffffff', 0.8)
        ctx.move_to(ex - 4.3, ey - 5.2 * b)
        ctx.curve_to(ex - 1.5, ey - 7 * b, ex + 2.5, ey - 7 * b, ex + 4.6, ey - 4.8 * b)
        ctx.line_to(ex + 6.2, ey - 6.2 * b)
        src(ctx, EYE)
        ctx.set_line_width(1.8)
        ctx.stroke()
    line(ctx, ex - 3, -13, ex + 4, -13.6, HAIR, 1.4)
    # pelo frontal / flequillo
    ctx.move_to(-23, 6)
    ctx.curve_to(-27, -18, -6, -31, 8, -26.5)
    ctx.curve_to(18, -23, 24.5, -14, 23, -4)
    ctx.line_to(20.5, -3)
    ctx.line_to(18, -9.5)
    ctx.line_to(15, -2.5)
    ctx.line_to(11.5, -10)
    ctx.line_to(8, -4)
    ctx.line_to(4.5, -11)
    ctx.line_to(0.5, -6)
    ctx.curve_to(-5, -2, -7.5, 4, -9.5, 12)
    ctx.line_to(-15, 17 + wv * 0.2)
    ctx.curve_to(-20, 14, -22, 10, -23, 6)
    ctx.close_path()
    src(ctx, HAIR)
    ctx.fill()
    # mechon lateral
    ctx.move_to(-1, -6)
    ctx.curve_to(0, 4, -1, 12, -3 - wv * 0.3, 19)
    ctx.curve_to(-5, 12, -5, 2, -4, -6)
    ctx.close_path()
    src(ctx, HAIR)
    ctx.fill()
    ctx.arc(-2, -5, 18, -2.55, -1.35)
    src(ctx, HAIR_HI, 0.75)
    ctx.set_line_width(2.6)
    ctx.stroke()
    ctx.arc(-2, -5, 18, -1.15, -0.85)
    ctx.stroke()
    # lazo
    fpoly(ctx, [(-16, -18), (-26, -27), (-24, -13)], RIBBON)
    fpoly(ctx, [(-16, -18), (-7, -29), (-10, -15)], RIBBON)
    circ(ctx, -16, -18, 2.4, shade(RIBBON, -0.2))
    if headphones:
        ctx.arc(-1, -4, 24.5, -2.9, -0.95)
        src(ctx, '#ead9c6')
        ctx.set_line_width(4.2)
        ctx.stroke()
        fell(ctx, -3, 3, 7.5, 9.5, '#e08a86')
        fell(ctx, -2, 3, 4.5, 6.5, '#f3b7a8')
    ctx.restore()

    ctx.restore()


# ----------------------------------------------------------------------------
# Mochi (gato)
# ----------------------------------------------------------------------------
CAT = hexc('#eba45e')
CAT_SH = hexc('#cf8545')
CAT_ST = hexc('#c26f34')
CAT_W = hexc('#fdf5e8')
CAT_EYE = hexc('#9ad27a')
CAT_PINK = hexc('#f2a3a3')


def cat_head(ctx, hx, hy, t, eyes='auto', look=0.0, ear=0.0):
    # orejas
    fpoly(ctx, [(hx - 13, hy - 3), (hx - 11, hy - 21), (hx - 2, hy - 10)], CAT_SH)
    fpoly(ctx, [(hx - 10.5, hy - 7), (hx - 10, hy - 16), (hx - 5, hy - 10)], CAT_PINK, 0.7)
    fell(ctx, hx, hy, 15.5, 12.8, CAT)
    fpoly(ctx, [(hx + 1, hy - 10), (hx + 9 + ear, hy - 23 + abs(ear) * 0.5), (hx + 14, hy - 5)], CAT)
    fpoly(ctx, [(hx + 4, hy - 9), (hx + 9 + ear * 0.8, hy - 18.5), (hx + 11.5, hy - 6.5)], CAT_PINK)
    # mofletes
    fpoly(ctx, [(hx - 14, hy + 3), (hx - 19, hy + 7), (hx - 12, hy + 8)], CAT)
    # rayas frente
    for i in range(3):
        line(ctx, hx - 5 + i * 4, hy - 12, hx - 4.2 + i * 4, hy - 7, CAT_ST, 1.8)
    fell(ctx, hx + 6, hy + 5, 8.5, 5.8, CAT_W)
    # ojos
    b = _blink(t, 0.5) if eyes == 'auto' else 1.0
    for k, (ex, ey) in enumerate(((hx - 1.5 + look, hy - 1), (hx + 8.5 + look, hy - 1.5))):
        r = 0.85 if k == 0 else 1.0
        if eyes == 'closed' or (eyes == 'auto' and b < 0.3):
            ctx.move_to(ex - 3 * r, ey)
            ctx.curve_to(ex - 1, ey + 2, ex + 1, ey + 2, ex + 3 * r, ey)
            src(ctx, '#3a2a1e')
            ctx.set_line_width(1.5)
            ctx.stroke()
        elif eyes == 'happy':
            ctx.move_to(ex - 3 * r, ey + 1)
            ctx.curve_to(ex - 1, ey - 2.5, ex + 1, ey - 2.5, ex + 3 * r, ey + 1)
            src(ctx, '#3a2a1e')
            ctx.set_line_width(1.5)
            ctx.stroke()
        else:
            fell(ctx, ex, ey, 2.9 * r, 3.9 * b, CAT_EYE)
            fell(ctx, ex + 0.3, ey, 1.15 * r, 3.1 * b, '#1d261b')
            circ(ctx, ex + 0.9, ey - 1.4 * b, 0.9, '#ffffff')
            line(ctx, ex - 3.2 * r, ey - 3.6 * b, ex + 3.2 * r, ey - 3.9 * b, '#3a2a1e', 1.1, 0.8)
    fpoly(ctx, [(hx + 11, hy + 2.6), (hx + 14.4, hy + 2.6), (hx + 12.7, hy + 4.8)], '#e58c8c')
    ctx.move_to(hx + 10.3, hy + 6.4)
    ctx.curve_to(hx + 11.3, hy + 7.6, hx + 12.5, hy + 7.2, hx + 12.7, hy + 5)
    ctx.curve_to(hx + 13, hy + 7.2, hx + 14.3, hy + 7.6, hx + 15, hy + 6.2)
    src(ctx, '#7a4a3a')
    ctx.set_line_width(0.9)
    ctx.stroke()
    for dy, dy2 in ((4.5, 2.0), (6.5, 7.0)):
        line(ctx, hx + 15, hy + dy, hx + 30, hy + dy2, '#fff7ea', 0.8, 0.8)
        line(ctx, hx - 2, hy + dy, hx - 15, hy + dy2 - 1, '#fff7ea', 0.7, 0.5)


def draw_cat(ctx, x, y, s, t, pose='sit', facing=1, phase=0.0, eyes='auto', look=0.0,
             alpha=1.0, head_dy=0.0, head_dx=0.0, ear=0.0, tail_speed=1.7):
    if alpha < 0.995:
        group_alpha(ctx, alpha, lambda: draw_cat(ctx, x, y, s, t, pose, facing, phase, eyes,
                                                 look, 1.0, head_dy, head_dx, ear, tail_speed))
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * facing, s)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    if pose in ('sit', 'eat'):
        sw = math.sin(t * tail_speed)
        ctx.move_to(-16, -5)
        ctx.curve_to(-32, -1, -44, -4, -46 + 4 * sw, -14 + 3 * math.cos(t * tail_speed))
        src(ctx, CAT)
        ctx.set_line_width(7.5)
        ctx.stroke()
        circ(ctx, -46 + 4 * sw, -14 + 3 * math.cos(t * tail_speed), 4, CAT_ST)
        fell(ctx, -8, -17, 18, 17, CAT)
        for r in (8, 12.5):
            ctx.arc(-8, -17, r, -2.6, -1.2)
            src(ctx, CAT_ST, 0.85)
            ctx.set_line_width(2.6)
            ctx.stroke()
        fell(ctx, -1, -3, 9, 4, CAT_W)
        fell(ctx, 5, -28, 12.5, 20, CAT)
        fell(ctx, 10, -27, 7, 15, CAT_W)
        line(ctx, 7, -18, 7, -3, CAT_SH, 6)
        circ(ctx, 8, -2.5, 3.8, shade(CAT_W, -0.08))
        line(ctx, 13.5, -18, 13.5, -3, CAT, 6.5)
        fell(ctx, 14.5, -2.5, 4.8, 3.2, CAT_W)
        if pose == 'eat':
            bob = 2.0 * max(0, math.sin(t * 6))
            cat_head(ctx, 17 + head_dx, -33 + bob + head_dy, t, 'happy', look, ear)
        else:
            cat_head(ctx, 9 + head_dx, -50 + head_dy, t, eyes, look, ear)
    elif pose == 'walk':
        ph = phase
        sw = math.sin(t * 2.2)
        ctx.move_to(-24, -28)
        ctx.curve_to(-36, -34, -40, -52, -33 + 4 * sw, -63)
        src(ctx, CAT)
        ctx.set_line_width(7.5)
        ctx.stroke()
        ctx.arc(-29 + 4 * sw, -63, 4.5, math.pi, TAU)
        src(ctx, CAT_ST)
        ctx.set_line_width(7.0)
        ctx.stroke()

        def leg(lx, off, c, pc):
            a = 0.5 * math.sin(ph + off)
            lift = 4 * max(0.0, math.cos(ph + off))
            fx, fy = lx + 18 * math.sin(a), -2 - lift
            line(ctx, lx, -20, fx, fy, c, 6.2)
            fell(ctx, fx + 1.5, fy, 4.3, 3, pc)

        leg(15, math.pi, CAT_SH, shade(CAT_W, -0.1))
        leg(-15, 0, CAT_SH, shade(CAT_W, -0.1))
        fell(ctx, 0, -26, 27, 12.5, CAT)
        fell(ctx, 3, -18, 17, 5, CAT_W, 0.75)
        for k in range(3):
            ctx.arc(-12 + k * 9, -24, 9, -2.2, -1.2)
            src(ctx, CAT_ST, 0.85)
            ctx.set_line_width(2.6)
            ctx.stroke()
        leg(19, 0, CAT, CAT_W)
        leg(-11, math.pi, CAT, CAT_W)
        fell(ctx, 22, -30, 9, 9, CAT)
        cat_head(ctx, 28 + head_dx, -39 + 1.2 * math.sin(2 * ph) + head_dy, t, eyes, look, ear)
    elif pose == 'curl':
        br = 1 + 0.04 * math.sin(t * 2.0)
        fell(ctx, 0, -14 * br, 30, 14 * br, CAT)
        for k in range(3):
            ctx.arc(-14 + k * 9, -12, 10, -2.3, -1.3)
            src(ctx, CAT_ST, 0.85)
            ctx.set_line_width(2.6)
            ctx.stroke()
        ctx.move_to(-27, -6)
        ctx.curve_to(-22, 5, 14, 5, 27, -2)
        src(ctx, CAT)
        ctx.set_line_width(8)
        ctx.stroke()
        circ(ctx, 27, -2, 4.2, CAT_ST)
        fell(ctx, 24, -5, 6, 3.6, CAT_W)
        ctx.save()
        ctx.translate(19, -15 * br)
        ctx.rotate(0.35)
        ctx.scale(0.92, 0.92)
        cat_head(ctx, 0, 0, t, 'closed', 0, 0)
        ctx.restore()
    ctx.restore()


def cat_paw(ctx, x, y, s, ang):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    ctx.scale(s, s)
    frect(ctx, -16, 0, 32, 110, CAT, r=15)
    for k in range(4):
        line(ctx, -16, 26 + k * 20, -2, 31 + k * 20, CAT_ST, 4)
    fell(ctx, 0, 0, 19, 16, CAT_W)
    for dx, dy in ((-11, -8), (-4, -12), (4, -12), (11, -8)):
        fell(ctx, dx, dy, 3.6, 3, CAT_PINK)
    fell(ctx, 0, 3, 7, 5.5, CAT_PINK)
    ctx.restore()


# ----------------------------------------------------------------------------
# escenario
# ----------------------------------------------------------------------------
def cloud(ctx, x, y, w, seed, light, shadow, a=1.0, mid=None):
    rng = random.Random(seed)
    n = max(5, int(w / 60))
    puffs = []
    for i in range(n):
        u = (i + 0.5) / n * 2 - 1
        r = w * (0.09 + 0.06 * rng.random()) * (1 - 0.4 * abs(u))
        px = x + u * w * 0.43
        py = y - r * 0.55 - (1 - u * u) * w * 0.09 * rng.uniform(0.6, 1.3)
        puffs.append((px, py, r))
    for i in range(max(2, n // 2)):
        u = rng.uniform(-0.45, 0.45)
        r = w * rng.uniform(0.08, 0.13)
        puffs.append((x + u * w * 0.6, y - w * 0.15 - r * 0.6 * rng.random(), r))
    mid = mid or mix(light, shadow, 0.45)
    ctx.save()
    ctx.rectangle(x - w, y - w * 2, w * 2, w * 2)
    ctx.clip()
    ctx.push_group()
    src(ctx, shadow)
    for px, py, r in puffs:
        ctx.arc(px, py, r, 0, TAU)
        ctx.new_sub_path()
    ctx.fill()
    src(ctx, mid)
    for px, py, r in puffs:
        ctx.arc(px - r * 0.06, py - r * 0.12, r * 0.92, 0, TAU)
        ctx.new_sub_path()
    ctx.fill()
    src(ctx, light)
    for px, py, r in puffs:
        ctx.arc(px - r * 0.14, py - r * 0.24, r * 0.8, 0, TAU)
        ctx.new_sub_path()
    ctx.fill()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(a)
    ctx.restore()


def ridge(ctx, y, amp, c, seed, a=1.0, bottom=H + 600, x0=-50, x1=W + 50, step=20, freq=1.0):
    rng = random.Random(seed)
    ph = [rng.uniform(0, TAU) for _ in range(4)]
    ctx.move_to(x0, bottom)
    x = x0
    while x <= x1 + step:
        u = x / W * freq
        h = (math.sin(u * 3.1 + ph[0]) * 0.5 + math.sin(u * 7.3 + ph[1]) * 0.28 +
             math.sin(u * 13.7 + ph[2]) * 0.12 + math.sin(u * 1.3 + ph[3]) * 0.6)
        ctx.line_to(x, y - amp * (0.5 + 0.5 * h / 1.5))
        x += step
    ctx.line_to(x1 + step, bottom)
    ctx.close_path()
    src(ctx, c, a)
    ctx.fill()


def tree(ctx, x, y, s, dark, light, seed, trunk='#5a4030'):
    rng = random.Random(seed)
    frect(ctx, x - 6 * s, y - 60 * s, 12 * s, 60 * s, trunk)
    blobs = []
    for i in range(9):
        a = rng.uniform(0, TAU)
        d = rng.uniform(0, 34) * s
        blobs.append((x + math.cos(a) * d * 1.2, y - 95 * s + math.sin(a) * d, rng.uniform(26, 40) * s))
    src(ctx, dark)
    for bx, by, r in blobs:
        ctx.arc(bx, by, r, 0, TAU)
        ctx.new_sub_path()
    ctx.fill()
    src(ctx, light)
    for bx, by, r in blobs:
        ctx.arc(bx - r * 0.2, by - r * 0.28, r * 0.68, 0, TAU)
        ctx.new_sub_path()
    ctx.fill()


def stars(ctx, t, n, seed, y0=0, y1=600, a=1.0, x0=0, x1=W):
    rng = random.Random(seed)
    for i in range(n):
        x = rng.uniform(x0, x1)
        y = rng.uniform(y0, y1) ** 1.0
        r = rng.uniform(0.8, 2.4)
        tw = 0.55 + 0.45 * math.sin(t * rng.uniform(1, 3) + rng.uniform(0, TAU))
        al = a * tw * (1 - (y - y0) / max(1, (y1 - y0)) * 0.6)
        circ(ctx, x, y, r, '#fff8e6', al)
        if r > 2.1:
            sparkle(ctx, x, y, r * 2.6, '#fff8e6', al * 0.7)


def moon(ctx, x, y, r, a=1.0):
    glow(ctx, x, y, r * 6, '#cfd8ff', 0.25 * a)
    glow(ctx, x, y, r * 2.4, '#eef0ff', 0.35 * a)
    circ(ctx, x, y, r, '#fff9e8', a)
    for dx, dy, rr in ((-0.3, -0.2, 0.18), (0.25, 0.3, 0.14), (0.1, -0.4, 0.1), (-0.15, 0.4, 0.09)):
        circ(ctx, x + dx * r, y + dy * r, rr * r, '#efe5cc', 0.6 * a)


def particles(ctx, t, n, seed, x0, x1, y0, y1, period, fn):
    rng = random.Random(seed)
    for i in range(n):
        off = rng.random()
        p = (t / period + off) % 1.0
        fn(i, p, rng.uniform(x0, x1), rng.uniform(y0, y1), rng)


def steam(ctx, x, y, t, n=6, h=170, w=26, a=0.32, seed=0, size=14):
    rng = random.Random(seed)
    for i in range(n):
        per = rng.uniform(2.6, 3.6)
        p = (t / per + i / n) % 1.0
        px = x + rng.uniform(-w, w) * 0.5 + math.sin(p * 6 + i) * w * p
        py = y - p * h
        al = a * math.sin(math.pi * p) ** 1.5
        rr = size * (0.6 + 1.6 * p)
        rad(ctx, px, py, 0, rr, [(0, '#ffffff', al), (1, '#ffffff', 0)])
        ctx.arc(px, py, rr, 0, TAU)
        ctx.fill()


def fireflies(ctx, t, n, seed, x0, x1, y0, y1, a=1.0):
    rng = random.Random(seed)
    for i in range(n):
        bx, by = rng.uniform(x0, x1), rng.uniform(y0, y1)
        f1, f2, ph = rng.uniform(0.2, 0.5), rng.uniform(0.2, 0.5), rng.uniform(0, TAU)
        px = bx + 40 * math.sin(t * f1 + ph)
        py = by + 25 * math.sin(t * f2 * 1.3 + ph * 2)
        bl = 0.5 + 0.5 * math.sin(t * rng.uniform(1.5, 3.0) + ph)
        glow(ctx, px, py, 22, '#e9ff8a', 0.35 * bl * a)
        circ(ctx, px, py, 2.6, '#fbffd0', (0.5 + 0.5 * bl) * a)


def rain(ctx, t, n, seed, x0, x1, y0, y1, a=0.5, length=40, speed=1400, slant=0.18):
    rng = random.Random(seed)
    span = y1 - y0
    src(ctx, '#cfe0ff', a)
    ctx.set_line_width(1.6)
    for i in range(n):
        x = rng.uniform(x0, x1)
        off = rng.uniform(0, span)
        y = y0 + (off + t * speed * rng.uniform(0.8, 1.2)) % span
        ctx.move_to(x + (y - y0) * slant, y)
        ctx.line_to(x + (y - y0) * slant - length * slant, y - length)
    ctx.stroke()


def pole(ctx, x, top, ground, c='#2a2f45'):
    frect(ctx, x - 7, top, 14, ground - top, c)
    frect(ctx, x - 38, top + 24, 76, 7, c)
    frect(ctx, x - 26, top + 50, 52, 6, c)
    for dx in (-30, -12, 12, 30):
        frect(ctx, dx + x - 3, top + 16, 6, 9, '#c9c3b8')


def wires(ctx, xa, xb, ya, sag, c='#20263a', a=0.9):
    for k, dy in enumerate((24, 24, 50)):
        dx = (-30, 30, -20)[k]
        ctx.move_to(xa + dx, ya + dy)
        ctx.curve_to(xa + dx + (xb - xa) * 0.3, ya + dy + sag, xb + dx - (xb - xa) * 0.3, ya + dy + sag,
                     xb + dx, ya + dy)
    src(ctx, c, a)
    ctx.set_line_width(2.2)
    ctx.stroke()
