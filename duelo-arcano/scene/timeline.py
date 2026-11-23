"""Shared timeline for the single-take duel. Pure Python/numpy (no bpy).

Every animated element (keyframes, procedural FX, audio cues) reads its timing
from here so picture and sound stay locked together.
"""
import math
import numpy as np

FPS = 24
F_START = 1
F_END = 1440            # 60 s

WIZ = np.array([0.0, 7.0, 0.0])    # wizard root, faces -Y
DEF = np.array([0.0, -7.0, 0.0])   # defender root, faces +Y

E = dict(
    lightning1=52, lightning2=214, lightning3=1150,
    eyes_on=150,
    runes_start=168, runes_end=264,
    arms_up_start=268, arms_up_end=336,
    gather_start=292,
    orb_birth=336,
    lift_start=560, lift_end=640,
    rocks_rise_start=420, rocks_rise_end=540,
    arcs_start=470,
    charge_peak=800,
    windup_start=800, windup_end=862,
    release=870,
    def_raise_start=880, def_raise_end=904,
    shield_start=900, shield_full=938,
    impact=950,
    push_back_end=1030,
    push_fwd_start=1040,
    burst=1092,
    rocks_fall=872,
    shield_fade_start=1185, shield_fade_end=1275,
    wiz_recover=1150,
    eyes_flare=1330,
    fade_start=1414,
)

LAUNCH_POS = np.array([-0.10, 6.05, 1.70])
IMPACT_POS = np.array([0.02, -6.04, 1.42])   # on the shield surface (before push)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def smoother(t):
    t = clamp(t)
    return t * t * t * (t * (t * 6 - 15) + 10)


def ramp(f, f0, f1, fn=smooth):
    if f1 == f0:
        return 1.0 if f >= f1 else 0.0
    return fn((f - f0) / (f1 - f0))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t ** 3


# ----------------------------------------------------------------------------
# Wizard charge / orb
# ----------------------------------------------------------------------------
def charge(f):
    """0..1 power level of the wizard's spell (drives glow, arcs, wind...)."""
    if f < E['gather_start']:
        return 0.0
    if f < E['release']:
        c = 0.12 * ramp(f, E['gather_start'], E['orb_birth'])
        c += 0.88 * ramp(f, E['orb_birth'], E['charge_peak'], smoother)
        c += 0.05 * math.sin(f * 0.45) * ramp(f, E['orb_birth'], E['charge_peak'])
        return clamp(c, 0, 1.05)
    # after release the wizard's own aura decays
    return clamp(1.0 - ramp(f, E['release'], E['release'] + 60), 0, 1)


def orb_radius(f):
    if f < E['orb_birth']:
        return 0.0
    if f < E['windup_start']:
        r = 0.05 * ramp(f, E['orb_birth'], E['orb_birth'] + 14, ease_out)
        r += 0.25 * ramp(f, E['orb_birth'] + 10, E['charge_peak'], smooth)
        r *= 1 + 0.04 * math.sin(f * 0.9)
        return r
    if f < E['release']:
        # compress during wind-up (anticipation)
        k = ramp(f, E['windup_start'], E['windup_end'])
        r = lerp(0.30, 0.24, k) * (1 + 0.06 * math.sin(f * 2.3) * k)
        if f >= E['windup_end']:
            r = lerp(0.24, 0.34, ramp(f, E['windup_end'], E['release'], ease_out))
        return r
    if f < E['impact']:
        return 0.34 * (1 + 0.03 * math.sin(f * 1.7))
    if f < E['burst']:
        k = ramp(f, E['impact'], E['burst'])
        wob = 0.05 * math.sin(f * 2.9) + 0.03 * math.sin(f * 5.3)
        return lerp(0.36, 0.27, k) * (1 + wob * (0.4 + k))
    return 0.0


def _wiz_hold(f):
    """Orb position while held by the wizard (world)."""
    chest = WIZ + np.array([0.0, -0.58, 1.38])
    over = WIZ + np.array([0.0, -0.36, 2.28])
    back = WIZ + np.array([-0.40, 0.08, 1.95])
    k = ramp(f, E['lift_start'], E['lift_end'], smoother)
    p = chest + (over - chest) * k
    # slow hover drift
    p = p + np.array([0.02 * math.sin(f * 0.07), 0.0, 0.025 * math.sin(f * 0.11)])
    if f >= E['windup_start']:
        kw = ramp(f, E['windup_start'], E['windup_end'], smoother)
        p = p + (back - p) * kw
        if f >= E['windup_end']:
            kt = ramp(f, E['windup_end'], E['release'], ease_in)
            p = back + (LAUNCH_POS - back) * kt
    return p


def flight_progress(f):
    """Speed-ramped 0..1 progress of the projectile (fast-slow-fast)."""
    t = clamp((f - E['release']) / (E['impact'] - E['release']))
    # piecewise speed profile integrated numerically -> monotone
    # fast start, slow-mo middle, fast finish
    def speed(x):
        return 1.0 - 0.78 * math.exp(-((x - 0.5) / 0.2) ** 2)
    n = 64
    xs = np.linspace(0, 1, n * 4 + 1)
    sp = np.array([speed(x) for x in xs])
    cum = np.concatenate([[0], np.cumsum((sp[1:] + sp[:-1]) * 0.5 * (xs[1] - xs[0]))])
    cum /= cum[-1]
    return float(np.interp(t, xs, cum))


def shield_push(f):
    """How far (m) the defender/shield is pushed back along -Y."""
    if f < E['impact']:
        return 0.0
    a = 0.30 * ramp(f, E['impact'], E['push_back_end'], ease_out)
    b = 0.22 * ramp(f, E['push_fwd_start'], E['burst'], smooth)
    return a - b


def orb_pos(f):
    if f < E['release']:
        return _wiz_hold(f)
    if f < E['impact']:
        p = flight_progress(f)
        base = LAUNCH_POS + (IMPACT_POS - LAUNCH_POS) * p
        arc = 0.55 * math.sin(math.pi * p)                     # slight lob
        spiral = 0.10 * math.sin(p * 14.0) * math.sin(math.pi * p)
        return base + np.array([spiral + 0.25 * math.sin(math.pi * p), 0.0, arc])
    if f < E['burst']:
        k = ramp(f, E['impact'], E['burst'])
        jitter = np.array([0.03 * math.sin(f * 3.1), 0.02 * math.sin(f * 4.7),
                           0.03 * math.sin(f * 2.3 + 1)]) * (0.5 + k)
        r = orb_radius(f)
        return IMPACT_POS + np.array([0, -shield_push(f) + r * 0.55, 0]) + jitter
    return IMPACT_POS + np.array([0, -shield_push(E['burst']) + 0.15, 0])


def orb_visible(f):
    return E['orb_birth'] <= f < E['burst']


def shield_form(f):
    return ramp(f, E['shield_start'], E['shield_full'], smooth) * \
        (1 - ramp(f, E['shield_fade_start'], E['shield_fade_end']))


def shield_center(f):
    """Center of the shield cap (world)."""
    return DEF + np.array([0.0, 0.98 - shield_push(f), 1.42])


def frame_seconds(f):
    return (f - 1) / FPS


def flash_curve(f, f0, attack=1, decay=10):
    if f < f0 - attack:
        return 0.0
    if f < f0:
        return (f - (f0 - attack)) / attack
    return math.exp(-(f - f0) / decay)
