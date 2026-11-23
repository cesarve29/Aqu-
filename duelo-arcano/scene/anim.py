"""Choreography: keyframes for both characters, driven by timeline.py."""
import math
import bpy
import numpy as np
from mathutils import Vector

import timeline as T
from timeline import E, ramp, smooth, smoother, lerp, clamp
from characters import key_hand, key_bone_rot

STEP = 2   # key every N frames for procedural motion


def _n(v):
    v = np.asarray(v, dtype=float)
    return v / (np.linalg.norm(v) + 1e-9)


def _blend(poses_weights):
    """poses_weights: list of (w, pose) with pose = (pos, f, n) per side dict."""
    tot = sum(w for w, _ in poses_weights)
    out = {}
    for side in ('L', 'R'):
        p = sum(w * np.asarray(pz[side][0]) for w, pz in poses_weights) / tot
        f = _n(sum(w * _n(pz[side][1]) for w, pz in poses_weights))
        n = _n(sum(w * _n(pz[side][2]) for w, pz in poses_weights))
        out[side] = (p, f, n)
    return out


def _sched(f, segments):
    """segments: list of (f0, f1, poseA, poseB). Returns blended pose."""
    for f0, f1, a, b in segments:
        if f < f1 or (f0, f1) == segments[-1][:2]:
            k = smoother(clamp((f - f0) / max(1, f1 - f0)))
            if a is b:
                return a(f)
            return _blend([(1 - k + 1e-6, a(f)), (k + 1e-6, b(f))])
    return segments[-1][3](f)


# ----------------------------------------------------------------------------
# Wizard
# ----------------------------------------------------------------------------
W = T.WIZ


def wiz_idle(f):
    b = 0.006 * math.sin(f * 0.09)
    return {'L': (W + [0.265, 0.04, 1.00 + b], (0.05, -0.15, -1), (-1, 0.2, 0)),
            'R': (W + [-0.265, 0.04, 1.00 + b], (-0.05, -0.15, -1), (1, 0.2, 0))}


def _orb_c(f):
    if f < E['orb_birth']:
        return T._wiz_hold(f), 0.0
    return T.orb_pos(f), T.orb_radius(f)


def wiz_cradle(f):
    c, r = _orb_c(f)
    g = r + 0.115 + 0.01 * math.sin(f * 0.21)
    tw = 0.012 * math.sin(f * 0.7)          # trembling fingers of power
    return {'L': (c + [g, 0.08, -0.035 + tw], (-0.4, -1, 0.25), (-1, 0, 0.1)),
            'R': (c + [-g, 0.08, -0.035 - tw], (0.4, -1, 0.25), (1, 0, 0.1))}


def wiz_overhead(f):
    c, r = _orb_c(f)
    g = r + 0.10
    tw = 0.015 * math.sin(f * 0.9)
    return {'L': (c + [g, 0.06, -0.13 + tw], (-0.35, -0.25, 1), (-1, 0, 0.25)),
            'R': (c + [-g, 0.06, -0.13 - tw], (0.35, -0.25, 1), (1, 0, 0.25))}


def wiz_windup(f):
    c, r = _orb_c(f)
    g = r + 0.08
    return {'L': (W + [0.21, -0.50, 1.52], (0.0, -0.35, 1), (0.1, -1, 0)),   # aims at the guardian
            'R': (c + [-g * 0.6, 0.12, -0.10], (0.2, -0.6, 0.8), (0.6, -0.6, 0))}


def wiz_thrust(f):
    rec = 0.05 * T.flash_curve(f, E['release'] + 2, 1, 8)
    return {'L': (W + [0.14, -0.56 + rec, 1.62], (0.1, -0.25, 1), (0, -1, 0)),
            'R': (W + [-0.14, -0.56 + rec, 1.62], (-0.1, -0.25, 1), (0, -1, 0))}


def wiz_post(f):
    b = 0.006 * math.sin(f * 0.08)
    return {'L': (W + [0.27, -0.12, 1.06 + b], (0.1, -0.6, -1), (-0.8, 0, -0.3)),
            'R': (W + [-0.27, -0.12, 1.06 + b], (-0.1, -0.6, -1), (0.8, 0, -0.3))}


def wiz_final(f):
    p = wiz_post(f)
    b = 0.004 * math.sin(f * 0.3)
    p['R'] = (W + [-0.21, -0.38, 1.34 + b], (-0.25, -1, 0.15), (0, 0.1, 1))   # palm up
    return p


WIZ_SEG = [
    (1, E['arms_up_start'], wiz_idle, wiz_idle),
    (E['arms_up_start'], E['arms_up_end'], wiz_idle, wiz_cradle),
    (E['arms_up_end'], E['lift_start'], wiz_cradle, wiz_cradle),
    (E['lift_start'], E['lift_end'], wiz_cradle, wiz_overhead),
    (E['lift_end'], E['windup_start'], wiz_overhead, wiz_overhead),
    (E['windup_start'], E['windup_end'] - 6, wiz_overhead, wiz_windup),
    (E['windup_end'] - 6, E['windup_end'], wiz_windup, wiz_windup),
    (E['windup_end'], E['release'] - 1, wiz_windup, wiz_thrust),
    (E['release'] - 1, 990, wiz_thrust, wiz_thrust),
    (990, 1120, wiz_thrust, wiz_post),
    (1120, 1290, wiz_post, wiz_post),
    (1290, 1350, wiz_post, wiz_final),
    (1350, T.F_END + 1, wiz_final, wiz_final),
]


def animate_wizard(rig, ctr, mats, parts, wind):
    for f in range(1, T.F_END + 2, STEP):
        pose = _sched(f, WIZ_SEG)
        for side in ('L', 'R'):
            p, fd, nd = pose[side]
            key_hand(rig, ctr, side, f, p, fd, nd)
    # thrust needs crisp keys around the release
    for f in range(E['windup_end'] - 4, E['release'] + 6):
        pose = _sched(f, WIZ_SEG)
        for side in ('L', 'R'):
            key_hand(rig, ctr, side, f, *pose[side])

    # spine / chest / neck: (x = lean forward, y = twist, z = side bend)
    K = {
        'spine': [(1, (0.10, 0, 0)), (140, (0.10, 0, 0)), (180, (0.03, 0, 0)), (336, (0.06, 0, 0)),
                  (560, (0.05, 0, 0)), (650, (-0.07, 0, 0)), (800, (-0.08, 0, 0)),
                  (850, (-0.02, 0.22, 0.04)), (862, (0.0, 0.26, 0.05)), (872, (0.16, -0.10, 0)),
                  (884, (0.02, -0.05, 0)), (990, (0.06, 0, 0)), (1120, (0.12, 0, 0)),
                  (1250, (0.03, 0, 0)), (1440, (0.03, 0, 0))],
        'chest': [(1, (0.12, 0, 0)), (140, (0.12, 0, 0)), (180, (0.0, 0, 0)), (336, (0.06, 0, 0)),
                  (560, (0.05, 0, 0)), (650, (-0.12, 0, 0)), (800, (-0.14, 0, 0)),
                  (850, (-0.04, 0.25, 0.05)), (862, (-0.02, 0.30, 0.05)), (872, (0.20, -0.12, 0)),
                  (884, (0.0, -0.06, 0)), (990, (0.06, 0, 0)), (1120, (0.10, 0, 0)),
                  (1250, (0.0, 0, 0)), (1440, (0.0, 0, 0))],
        'neck': [(1, (0.30, 0, 0)), (140, (0.30, 0, 0)), (185, (0.0, 0, 0)), (1440, (0.0, 0, 0))],
    }
    for bone, keys in K.items():
        for f, e in keys:
            key_bone_rot(rig, bone, f, e)
    # breathing on top: small chest scale is avoided; use hips micro-motion
    for f in range(1, T.F_END + 1, 12):
        key_bone_rot(rig, 'hips', f, (0.012 * math.sin(f * 0.05), 0, 0.01 * math.sin(f * 0.031)))

    # head look target
    look = ctr['look']
    for f in range(1, T.F_END + 1, STEP):
        low = np.array([0.0, 2.5, 0.0])
        de = T.DEF + [0, -T.shield_push(f), 1.65]
        k = ramp(f, E['eyes_on'] - 10, E['eyes_on'] + 30)
        p = low * (1 - k) + de * k
        if E['orb_birth'] < f < E['release']:
            ko = 0.35 * ramp(f, E['lift_start'], E['lift_end']) * (1 - ramp(f, E['windup_end'], E['release']))
            p = p * (1 - ko) + T.orb_pos(f) * ko
        look.location = Vector(p)
        look.keyframe_insert('location', frame=f)

    # recoil of the whole body at release
    for f, y in ((E['release'] - 2, 0.0), (E['release'] + 4, 0.07), (E['release'] + 30, 0.03)):
        rig.pose.bones['root'].location = (0, 0, -y)      # root bone local -Z == world +Y (backwards)
        rig.pose.bones['root'].keyframe_insert('location', frame=f)

    # materials driven by the charge
    _key_material_values(mats, parts, wizard=True)
    _key_wind(wind, parts, wizard=True)


# ----------------------------------------------------------------------------
# Guardian
# ----------------------------------------------------------------------------
_GM = {}


def _g_matrix(rig):
    from mathutils import Matrix
    return (Matrix.Translation(rig.location) @ rig.rotation_euler.to_matrix().to_4x4() @
            Matrix.Diagonal((*rig.scale, 1.0)))


def g_world(rig, local):
    return np.array(_g_matrix(rig) @ Vector(local))


def g_dir(rig, d):
    return np.array(rig.matrix_world.to_3x3().normalized() @ Vector(d))


def guardian_poses(rig):
    def W_(l):
        return lambda: g_world(rig, l)

    def idle(f):
        b = 0.005 * math.sin(f * 0.1 + 1)
        return {'L': ((0.25, -0.07, 1.02 + b), (0.05, -0.3, -1), (-1, 0, 0)),
                'R': ((-0.27, 0.02, 1.0 + b), (-0.05, -0.1, -1), (1, 0, 0))}

    def ready(f):
        b = 0.005 * math.sin(f * 0.1 + 1)
        return {'L': ((0.24, -0.22, 1.15 + b), (0.1, -0.8, -0.5), (-0.8, 0, -0.3)),
                'R': ((-0.27, 0.0, 1.0 + b), (-0.05, -0.1, -1), (1, 0, 0))}

    def cast(f):
        sh = 0.0
        if f > E['impact']:
            sh = 0.012 * (1 - ramp(f, E['burst'], E['burst'] + 20))
        j = sh * math.sin(f * 2.7)
        return {'L': ((0.06 + j, -0.56, 1.46 + j), (0.0, -0.15, 1), (0, -1, 0)),
                'R': ((-0.26, 0.0, 1.02), (-0.05, -0.1, -1), (1, 0, 0))}

    def brace(f):
        p = cast(f)
        j = 0.0
        if f > E['impact']:
            j = 0.01 * math.sin(f * 3.3) * (1 - ramp(f, E['burst'], E['burst'] + 20))
        p['R'] = ((-0.04 + j, -0.44, 1.33 + j), (0.35, -0.35, 1), (0.1, -1, 0))
        return p

    def lower(f):
        b = 0.005 * math.sin(f * 0.1 + 1)
        return {'L': ((0.22, -0.20, 1.12 + b), (0.0, -0.7, -0.7), (-0.9, 0, -0.2)),
                'R': ((-0.27, -0.02, 1.0 + b), (-0.05, -0.1, -1), (1, 0, 0))}

    return idle, ready, cast, brace, lower


def animate_guardian(rig, ctr, mats, parts, wind):
    idle, ready, cast, brace, lower = guardian_poses(rig)
    seg = [
        (1, 600, idle, idle),
        (600, 680, idle, ready),
        (680, E['def_raise_start'], ready, ready),
        (E['def_raise_start'], E['def_raise_end'], ready, cast),
        (E['def_raise_end'], 922, cast, cast),
        (922, 944, cast, brace),
        (944, E['shield_fade_start'], brace, brace),
        (E['shield_fade_start'], E['shield_fade_end'], brace, lower),
        (E['shield_fade_end'], T.F_END + 1, lower, lower),
    ]
    base_loc = Vector(T.DEF)
    for f in range(1, T.F_END + 2, STEP):
        rig.location = base_loc + Vector((0, -T.shield_push(f), 0))
        rig.keyframe_insert('location', frame=f)
    for f in range(1, T.F_END + 2, STEP):
        rig.location = base_loc + Vector((0, -T.shield_push(f), 0))
        pose = _sched(f, seg)
        for side in ('L', 'R'):
            p, fd, nd = pose[side]
            key_hand(rig, ctr, side, f, g_world(rig, p), g_dir(rig, fd), g_dir(rig, nd))

    K = {
        'spine': [(1, (0.02, 0, 0)), (880, (0.02, 0, 0)), (904, (0.08, 0, 0)), (950, (0.10, 0, 0)),
                  (956, (-0.06, 0, 0)), (975, (0.14, 0, 0)), (1030, (0.18, 0, 0.03)),
                  (1060, (0.22, 0, -0.02)), (1092, (0.24, 0, 0)), (1100, (0.0, 0, 0)),
                  (1185, (0.06, 0, 0)), (1300, (0.03, 0, 0))],
        'chest': [(1, (0.0, 0, 0)), (880, (0.0, 0, 0)), (904, (0.10, 0.12, 0)), (950, (0.10, 0.15, 0)),
                  (956, (-0.10, 0.18, 0)), (975, (0.15, 0.15, 0)), (1092, (0.22, 0.12, 0)),
                  (1100, (-0.02, 0.05, 0)), (1185, (0.04, 0, 0)), (1300, (0.0, 0, 0))],
    }
    for bone, keys in K.items():
        for f, e in keys:
            key_bone_rot(rig, bone, f, e)
    look = ctr['look']
    for f in range(1, T.F_END + 1, STEP):
        wiz = T.WIZ + [0, 0, 1.85]
        p = wiz
        if E['release'] - 4 <= f < E['burst']:
            k = ramp(f, E['release'] - 4, E['release'] + 8)
            p = wiz * (1 - k) + T.orb_pos(f) * k
        elif f >= E['burst']:
            k = ramp(f, E['burst'] + 30, E['burst'] + 90)
            p = (T.IMPACT_POS + [2.5, 0, 0.8]) * (1 - k) + wiz * k
        look.location = Vector(p)
        look.keyframe_insert('location', frame=f)
    _key_material_values(mats, parts, wizard=False)
    _key_wind(wind, parts, wizard=False)


# ----------------------------------------------------------------------------
def _setval(mat, node, frame, value):
    s = mat.node_tree.nodes[node].outputs[0]
    s.default_value = value
    s.keyframe_insert('default_value', frame=frame)


def _key_material_values(mats, parts, wizard):
    for f in range(1, T.F_END + 1, 3):
        if wizard:
            c = T.charge(f)
            on = ramp(f, E['runes_start'], E['runes_end'])
            flare = T.flash_curve(f, E['eyes_on'], 2, 18) * 45 + T.flash_curve(f, E['release'], 1, 10) * 30 \
                + T.flash_curve(f, E['eyes_flare'], 3, 25) * 60
            eye = (ramp(f, E['eyes_on'] - 2, E['eyes_on'] + 2) * (16 + 10 * c) + flare) * \
                (0.9 + 0.1 * math.sin(f * 1.7))
            _setval(mats['eyes'], 'strength', f, eye)
            for mk in ('cloth', 'cloth2', 'hood', 'collar'):
                _setval(mats[mk], 'trim', f, 0.6 + on * 4.0 + c * 9.0)
                _setval(mats[mk], 'rim', f, 0.3 + on * 0.6 + c * 2.0)
            _setval(mats['skin'], 'veins', f, 12.0 * c ** 1.5 + T.flash_curve(f, E['release'], 1, 12) * 20)
        else:
            sf = T.shield_form(f)
            hit = T.flash_curve(f, E['impact'], 1, 20) + T.flash_curve(f, E['burst'], 1, 15)
            _setval(mats['eyes'], 'strength', f, 6 + 14 * sf + 20 * hit)
            for mk in ('cloth', 'cloth2', 'hood'):
                _setval(mats[mk], 'trim', f, 2.0 + 6.0 * sf + 10 * hit)
                _setval(mats[mk], 'rim', f, 0.25 + 0.8 * sf + 1.5 * hit)


def _key_wind(wind, parts, wizard):
    """Scroll the flutter texture and scale its strength with the action."""
    pos = 0.0
    for f in range(1, T.F_END + 2, 4):
        if wizard:
            gust = 0.4 + 2.2 * T.charge(f) + 1.5 * T.flash_curve(f, E['release'], 1, 20)
        else:
            gust = 0.4 + 2.5 * (T.flash_curve(f, E['impact'], 1, 40) + T.flash_curve(f, E['burst'], 1, 30)) \
                + (1.2 if E['impact'] < f < E['burst'] else 0.0)
        pos += 0.012 * 4 * gust
        wind.location = (pos * 0.7, pos * 0.4, -pos)
        wind.keyframe_insert('location', frame=f)
        for name, ob in parts.items():
            if isinstance(ob, list):
                continue
            m = ob.modifiers.get('flutter')
            if m:
                base = 0.045 if 'robe' in name else 0.025
                m.strength = base * (0.6 + 0.5 * gust)
                m.keyframe_insert('strength', frame=f)
