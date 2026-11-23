"""Per-frame procedural FX (registered as a frame_change_pre handler at render time).

Every system is a pure function of (continuous) time so frames can be rendered in
any order and motion blur sub-frames are consistent. Topology (point / edge
counts) is constant per system; hidden elements just get radius 0.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
import numpy as np

import timeline as T
from timeline import E, ramp, clamp
import anim

MAG = np.array([1.0, 0.10, 0.72])
VIO = np.array([0.55, 0.12, 1.0])
WHM = np.array([1.0, 0.78, 0.95])
CYA = np.array([0.0, 0.62, 1.0])
WHC = np.array([0.80, 0.97, 1.0])
EMB = np.array([1.0, 0.42, 0.18])

R = np.random.default_rng(1234)
FPS = T.FPS


def _cache_orb_path():
    fs = np.arange(0, T.F_END + 3, dtype=float)
    pos = np.array([T.orb_pos(int(f)) for f in fs])
    rad = np.array([T.orb_radius(int(f)) for f in fs])
    return fs, pos, rad


_OF, _OP, _OR = _cache_orb_path()


def orb_pos_c(f):
    """Continuous (interpolated) orb position."""
    f = np.clip(f, 0, T.F_END + 1)
    i = np.floor(f).astype(int)
    k = f - i
    i2 = np.minimum(i + 1, len(_OF) - 1)
    if np.ndim(f) == 0:
        return _OP[i] * (1 - k) + _OP[i2] * k
    return _OP[i] * (1 - k)[:, None] + _OP[i2] * k[:, None]


def orb_rad_c(f):
    f = float(np.clip(f, 0, T.F_END + 1))
    i = int(f)
    k = f - i
    return _OR[i] * (1 - k) + _OR[min(i + 1, len(_OR) - 1)] * k


# ----------------------------------------------------------------------------
# mesh writers
# ----------------------------------------------------------------------------
def _attr(me, name, typ):
    a = me.attributes.get(name)
    if a is None or a.data_type != typ or a.domain != 'POINT':
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(name, typ, 'POINT')
    return a


def write_points(ob, P, rad, col, emit, edges=None):
    me = ob.data
    n = len(P)
    if len(me.vertices) != n or (edges is not None and len(me.edges) != len(edges)):
        me.clear_geometry()
        me.vertices.add(n)
        if edges is not None and len(edges):
            me.edges.add(len(edges))
            me.edges.foreach_set('vertices', np.asarray(edges, dtype=np.int32).ravel())
    me.vertices.foreach_set('co', np.asarray(P, dtype=np.float32).ravel())
    _attr(me, 'radius', 'FLOAT').data.foreach_set('value', np.asarray(rad, dtype=np.float32))
    c4 = np.ones((n, 4), dtype=np.float32)
    c4[:, :3] = col
    _attr(me, 'col', 'FLOAT_COLOR').data.foreach_set('color', c4.ravel())
    _attr(me, 'emit', 'FLOAT').data.foreach_set('value', np.asarray(emit, dtype=np.float32))
    me.update()


def chain_edges(n_chains, n_pts):
    e = []
    for c in range(n_chains):
        b = c * n_pts
        e.extend((b + i, b + i + 1) for i in range(n_pts - 1))
    return np.array(e, dtype=np.int32)


def hash01(x):
    return np.modf(np.sin(x * 12.9898 + 78.233) * 43758.5453)[0] % 1.0


# ----------------------------------------------------------------------------
# 1. gathering particles (spiral into the orb)
# ----------------------------------------------------------------------------
NG = 1100
G_dir = R.normal(size=(NG, 3))
G_dir /= np.linalg.norm(G_dir, axis=1)[:, None]
G_dir[:, 2] = np.abs(G_dir[:, 2]) * 0.8 - 0.15
G_r0 = R.uniform(1.2, 4.2, NG)
G_per = R.uniform(1.4, 3.0, NG) * FPS
G_ph = R.uniform(0, 1, NG)
G_swirl = R.uniform(2.0, 5.0, NG) * np.where(R.random(NG) < 0.85, 1, -1)
G_act = R.uniform(0, 1, NG)
G_size = R.uniform(0.0025, 0.008, NG)
G_tint = R.uniform(0, 1, NG)


def sys_gather(f):
    if f < E['release']:
        tgt = T._wiz_hold(int(f)) if f < E['orb_birth'] else orb_pos_c(f)
    else:
        tgt = orb_pos_c(f)
    level = ramp(f, E['gather_start'], E['gather_start'] + 60) * (0.25 + 0.45 * T.charge(int(f)))
    level *= 1 - ramp(f, E['windup_end'], E['release'])
    u = np.mod((f - E['gather_start']) / G_per + G_ph, 1.0)
    rr = G_r0 * (1 - u) ** 1.6
    ang = G_swirl * u ** 1.5
    ca, sa = np.cos(ang), np.sin(ang)
    d = G_dir.copy()
    x = d[:, 0] * ca - d[:, 1] * sa
    y = d[:, 0] * sa + d[:, 1] * ca
    off = np.stack([x, y, d[:, 2]], 1) * rr[:, None]
    P = tgt + off
    fade_in = np.clip(u / 0.15, 0, 1)
    near = np.clip(1 - rr / 0.6, 0, 1)
    on = (G_act < level).astype(float)
    rad = G_size * fade_in * (1 - 0.6 * near) * on
    col = MAG[None] * (1 - near[:, None]) + WHM[None] * near[:, None]
    col = col * (1 - 0.4 * G_tint[:, None]) + VIO[None] * 0.4 * G_tint[:, None]
    emit = (2.0 + 9 * near) * fade_in * on
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 2. sparks orbiting the orb
# ----------------------------------------------------------------------------
NO = 320
O_ax = R.normal(size=(NO, 3))
O_ax /= np.linalg.norm(O_ax, axis=1)[:, None]
O_ref = np.cross(O_ax, R.normal(size=(NO, 3)))
O_ref /= np.linalg.norm(O_ref, axis=1)[:, None]
O_ref2 = np.cross(O_ax, O_ref)
O_rf = R.uniform(1.25, 2.4, NO)
O_w = R.uniform(0.12, 0.35, NO) * np.where(R.random(NO) < 0.5, 1, -1)
O_ph = R.uniform(0, 6.28, NO)
O_sz = R.uniform(0.002, 0.005, NO)
O_act = R.uniform(0, 1, NO)


def sys_orbsparks(f):
    c = orb_pos_c(f)
    r = orb_rad_c(f)
    vis = 1.0 if (E['orb_birth'] <= f < E['burst']) else 0.0
    level = vis * (0.3 + 0.7 * min(1, T.charge(int(f)) + (1 if f >= E['release'] else 0)))
    a = O_ph + O_w * f
    P = c + (O_ref * np.cos(a)[:, None] + O_ref2 * np.sin(a)[:, None]) * (O_rf * r)[:, None]
    flick = 0.5 + 0.5 * np.sin(f * 1.3 + O_ph * 7)
    on = (O_act < level).astype(float)
    rad = O_sz * (0.4 + 0.6 * flick) * on * min(1.0, r / 0.1)
    col = MAG[None] * 0.6 + WHM[None] * 0.4 * flick[:, None]
    emit = (4 + 8 * flick) * on
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 3. electric arcs
# ----------------------------------------------------------------------------
NA, NAP = 12, 18
A_edges = chain_edges(NA, NAP)


def _jagged(p0, p1, seed, amp, n=NAP):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, n)
    base = p0[None] + (p1 - p0)[None] * t[:, None]
    d = p1 - p0
    L = np.linalg.norm(d) + 1e-9
    side = np.cross(d / L, np.array([0.3, 0.2, 0.93]))
    side /= np.linalg.norm(side) + 1e-9
    up = np.cross(d / L, side)
    env = np.sin(np.pi * t)
    off = np.zeros((n, 3))
    for octave, (k, s) in enumerate(((3, 1.0), (7, 0.45), (15, 0.22))):
        ph = rng.uniform(0, 6.28, 2)
        w = rng.normal(size=(n, 2)) * 0.25
        off += (side[None] * (np.sin(t * k + ph[0])[:, None] + w[:, :1]) +
                up[None] * (np.cos(t * k * 1.3 + ph[1])[:, None] + w[:, 1:])) * s
    return base + off * (amp * L * env)[:, None]


def sys_arcs(f):
    fi = int(f)
    epoch = fi // 2
    P = np.zeros((NA * NAP, 3))
    rad = np.zeros(NA * NAP)
    col = np.tile(MAG, (NA * NAP, 1))
    emit = np.zeros(NA * NAP)
    c = orb_pos_c(f)
    r = orb_rad_c(f)
    P[:] = c
    pose = anim._sched(f, anim.WIZ_SEG)
    hands = [np.asarray(pose[s][0]) for s in ('L', 'R')]
    for a in range(NA):
        rng = np.random.default_rng(epoch * 131 + a * 7)
        sl = slice(a * NAP, (a + 1) * NAP)
        p0 = p1 = None
        color = MAG
        wid = 0.006
        e = 0.0
        if E['arcs_start'] <= f < E['release'] and r > 0.05:
            lvl = T.charge(fi)
            if rng.random() < 0.25 + 0.6 * lvl:
                n = rng.normal(size=3)
                n /= np.linalg.norm(n)
                p0 = c + n * r * 0.95
                kind = rng.random()
                if kind < 0.35 and hands:
                    p1 = hands[a % len(hands)] + rng.normal(size=3) * 0.04
                elif kind < 0.6:
                    g = np.array(T.WIZ) + np.array([rng.uniform(-1.8, 1.8), rng.uniform(-1.8, 1.2), 0.02])
                    p1 = g
                else:
                    p1 = c + n * r * rng.uniform(2.0, 3.4) + rng.normal(size=3) * 0.2
                wid = 0.004 + 0.008 * lvl
                e = 10 + 25 * lvl
        elif E['release'] <= f < E['impact'] and r > 0.05 and a < 4:
            if rng.random() < 0.7:
                n = rng.normal(size=3)
                n /= np.linalg.norm(n)
                p0 = c + n * r
                p1 = c + n * r * rng.uniform(1.8, 2.8)
                wid, e = 0.006, 25
        elif E['impact'] <= f < E['burst'] + 2:
            if rng.random() < 0.85:
                ang = rng.uniform(0, 2 * np.pi)
                rr = rng.uniform(0.35, 0.9)
                sc = T.shield_center(fi)
                p0 = c + np.array([0, -r * 0.5, 0]) + rng.normal(size=3) * 0.05
                x, z = rr * np.cos(ang), rr * np.sin(ang)
                p1 = sc + np.array([x, -(2.1 - math.sqrt(max(2.1 ** 2 - x * x - z * z, 0))) + 0.02, z])
                color = WHC if a % 2 else MAG
                wid, e = 0.007, 30
        if p0 is None:
            continue
        pts = _jagged(p0, p1, epoch * 977 + a, 0.12)
        P[sl] = pts
        t = np.linspace(0, 1, NAP)
        rad[sl] = wid * (0.6 + 0.4 * np.sin(np.pi * t))
        col[sl] = color * 0.5 + (WHM if color is MAG else WHC) * 0.5
        emit[sl] = e
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 4. projectile trail (three strands)
# ----------------------------------------------------------------------------
NT, NTP = 3, 64
T_edges = chain_edges(NT, NTP)


def sys_trail(f):
    P = np.zeros((NT * NTP, 3))
    rad = np.zeros(NT * NTP)
    col = np.tile(MAG, (NT * NTP, 1))
    emit = np.zeros(NT * NTP)
    c = orb_pos_c(f)
    P[:] = c
    if not (E['release'] <= f < E['impact'] + 10):
        return P, rad, col, emit
    k = np.arange(NTP)
    back = f - k * 0.42
    back = np.maximum(back, E['release'])
    pts = orb_pos_c(back)
    life = np.clip((f - back) / 0.42 / NTP, 0, 1)
    taper = (1 - k / (NTP - 1)) ** 1.3
    fade_end = 1 - ramp(f, E['impact'], E['impact'] + 10)
    r0 = 0.34
    for s in range(NT):
        sl = slice(s * NTP, (s + 1) * NTP)
        if s == 0:
            P[sl] = pts
            rad[sl] = r0 * 0.55 * taper * fade_end
            col[sl] = MAG[None] * 0.7 + VIO[None] * 0.3
            emit[sl] = 4 * taper
        else:
            d = np.gradient(pts, axis=0)
            d /= np.linalg.norm(d, axis=1)[:, None] + 1e-9
            side = np.cross(d, np.array([0, 0, 1.0]))
            side /= np.linalg.norm(side, axis=1)[:, None] + 1e-9
            up = np.cross(side, d)
            ang = back * 0.55 + s * np.pi
            rr = r0 * (0.9 + 0.8 * k / NTP)
            P[sl] = pts + (side * np.cos(ang)[:, None] + up * np.sin(ang)[:, None]) * rr[:, None]
            rad[sl] = 0.018 * taper * fade_end
            col[sl] = WHM[None] * 0.6 + MAG[None] * 0.4
            emit[sl] = 25 * taper
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 5. impact / struggle / burst sparks (2-point streaks)
# ----------------------------------------------------------------------------
NS = 700
S_birth = np.concatenate([
    np.full(140, E['impact']) + R.uniform(0, 2, 140),
    R.uniform(E['impact'] + 2, E['burst'], 360),
    np.full(200, E['burst']) + R.uniform(0, 3, 200)])
S_is_burst = np.arange(NS) >= 500
S_ang = R.uniform(0, 2 * np.pi, NS)
S_spd = np.where(S_is_burst, R.uniform(4, 14, NS), R.uniform(2.5, 9, NS))
S_out = np.where(S_is_burst, R.uniform(-0.5, 1.0, NS), R.uniform(0.2, 1.3, NS))
S_up = R.uniform(-0.2, 1.0, NS)
S_life = R.uniform(0.35, 1.2, NS) * FPS
S_cyan = R.random(NS) < 0.45
S_w = R.uniform(0.003, 0.007, NS)


def _spark_pos(i_mask, age_s):
    origin = T.IMPACT_POS + np.array([0.0, 0.18, 0.0])
    o = np.tile(origin, (len(age_s), 1))
    o[:, 1] -= np.array([T.shield_push(int(b)) for b in S_birth[i_mask]])
    tang = np.stack([np.cos(S_ang[i_mask]), np.zeros(len(age_s)), np.sin(S_ang[i_mask])], 1)
    v = tang * S_spd[i_mask, None] + np.array([0, 1.0, 0]) * (S_out[i_mask] * S_spd[i_mask] * 0.5)[:, None]
    v[:, 2] += S_up[i_mask] * 2.0
    drag = 1.6
    tt = age_s
    disp = v * ((1 - np.exp(-drag * tt)) / drag)[:, None]
    disp[:, 2] -= 0.5 * 9.81 * tt ** 2 * 0.8
    p = o + disp
    p[:, 2] = np.maximum(p[:, 2], 0.01)
    return p


def sys_sparks(f):
    P = np.zeros((NS * 2, 3))
    rad = np.zeros(NS * 2)
    col = np.zeros((NS * 2, 3))
    emit = np.zeros(NS * 2)
    age = (f - S_birth)
    alive = (age >= 0) & (age < S_life)
    idx = np.nonzero(alive)[0]
    P[:] = T.IMPACT_POS
    if len(idx) == 0:
        return P, rad, col, emit
    a_s = age[idx] / FPS
    p1 = _spark_pos(idx, a_s)
    p0 = _spark_pos(idx, np.maximum(a_s - 0.03, 0))
    life_k = age[idx] / S_life[idx]
    P[idx * 2] = p0
    P[idx * 2 + 1] = p1
    w = S_w[idx] * (1 - life_k) ** 0.5
    rad[idx * 2] = w * 0.6
    rad[idx * 2 + 1] = w
    c = np.where(S_cyan[idx, None], CYA[None] * 0.5 + WHC[None] * 0.5, MAG[None] * 0.5 + WHM[None] * 0.5)
    hot = np.clip(1 - life_k * 2.5, 0, 1)[:, None]
    c = c * (1 - hot) + np.array([1, 1, 1.0])[None] * hot
    col[idx * 2] = c
    col[idx * 2 + 1] = c
    e = 16 * (1 - life_k) ** 1.5 + 3
    emit[idx * 2] = e
    emit[idx * 2 + 1] = e
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 6. deflected fragments flying into the stones
# ----------------------------------------------------------------------------
def fragment_specs():
    rng = np.random.default_rng(77)
    start = T.IMPACT_POS + np.array([0.0, 0.25 - T.shield_push(E['burst']), 0.0])
    targets = [np.array(p) for p in (
        (-6.2, -9.4, 1.8), (7.4, -8.6, 2.1), (-10.6, -3.0, 2.6), (10.9, -2.4, 1.2),
        (-4.0, 2.2, 0.02), (5.0, 0.5, 0.02), (-1.5, -12.5, 3.4))]
    specs = []
    for i, tg in enumerate(targets):
        dur = rng.uniform(0.35, 0.7) * FPS
        delay = rng.uniform(0, 4)
        lift = rng.uniform(0.8, 2.6)
        specs.append(dict(start=start, end=tg, dur=dur, t0=E['burst'] + delay, lift=lift))
    return specs


FRAG = fragment_specs()
NF, NFP = len(FRAG), 20
NFS = 26          # hit sparks per fragment
F_edges = np.concatenate([chain_edges(NF, NFP),
                          chain_edges(NF * NFS, 2) + NF * NFP])
FS_dir = R.normal(size=(NF, NFS, 3))
FS_dir[..., 2] = np.abs(FS_dir[..., 2]) + 0.3
FS_dir /= np.linalg.norm(FS_dir, axis=2)[..., None]
FS_spd = R.uniform(2, 7, (NF, NFS))
FS_life = R.uniform(0.3, 0.8, (NF, NFS)) * FPS


def _frag_pos(sp, u):
    u = np.clip(u, 0, 1)
    s, e = sp['start'], sp['end']
    ctrl = (s + e) * 0.5 + np.array([0, 0, sp['lift']])
    return ((1 - u) ** 2)[:, None] * s + (2 * (1 - u) * u)[:, None] * ctrl + (u ** 2)[:, None] * e


def sys_fragments(f):
    n_tot = NF * NFP + NF * NFS * 2
    P = np.zeros((n_tot, 3))
    rad = np.zeros(n_tot)
    col = np.tile(MAG, (n_tot, 1))
    emit = np.zeros(n_tot)
    P[:] = FRAG[0]['start']
    for i, sp in enumerate(FRAG):
        sl = slice(i * NFP, (i + 1) * NFP)
        tt = f - sp['t0']
        if -1 < tt < sp['dur'] + 6:
            k = np.arange(NFP)
            us = (tt - k * 0.5) / sp['dur']
            P[sl] = _frag_pos(sp, us)
            alive = (us >= 0) & (us <= 1.0)
            tail = (1 - k / NFP) ** 1.2
            rad[sl] = 0.03 * tail * alive
            col[sl] = MAG[None] * 0.5 + WHM[None] * 0.5 * tail[:, None]
            emit[sl] = 25 * tail * alive
        # hit sparks
        th = f - (sp['t0'] + sp['dur'])
        base = NF * NFP + i * NFS * 2
        if th >= 0:
            age = th
            alive = age < FS_life[i]
            a_s = age / FPS
            for j, ts in enumerate((max(a_s - 0.03, 0), a_s)):
                v = FS_dir[i] * FS_spd[i][:, None]
                d = v * ((1 - np.exp(-2 * ts)) / 2)
                d[:, 2] -= 0.5 * 9.81 * ts * ts * 0.7
                p = sp['end'] + d
                p[:, 2] = np.maximum(p[:, 2], 0.01)
                P[base + j:base + NFS * 2:2] = p
                kk = np.clip(age / FS_life[i], 0, 1)
                rad[base + j:base + NFS * 2:2] = 0.006 * (1 - kk) * alive
                emit[base + j:base + NFS * 2:2] = (25 * (1 - kk) + 4) * alive
                col[base + j:base + NFS * 2:2] = WHM * 0.6 + MAG * 0.4
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 7. ambient embers
# ----------------------------------------------------------------------------
NE = 650
E_p0 = np.stack([R.uniform(-9, 9, NE), R.uniform(-14, 13, NE), R.uniform(-0.5, 5.5, NE)], 1)
E_spd = R.uniform(0.15, 0.45, NE)
E_ph = R.uniform(0, 6.28, NE)
E_sz = R.uniform(0.0025, 0.007, NE)
E_kind = R.random(NE)


def sys_embers(f):
    t = f / FPS
    z = np.mod(E_p0[:, 2] + E_spd * t + 0.5, 6.5) - 0.5
    x = E_p0[:, 0] + 0.35 * np.sin(t * 0.6 + E_ph) + 0.25 * t
    y = E_p0[:, 1] + 0.30 * np.cos(t * 0.5 + E_ph * 1.3)
    # pulled toward the wizard while he charges
    c = T.charge(int(f))
    pull = c * 0.35
    W = np.array(T.WIZ) + np.array([0, -0.4, 1.6])
    P = np.stack([x, y, z], 1)
    P = P + (W - P) * pull * np.exp(-np.linalg.norm(P - W, axis=1) / 6)[:, None]
    fade = np.clip(z / 0.6, 0, 1) * np.clip((6.0 - z) / 1.0, 0, 1)
    tw = 0.6 + 0.4 * np.sin(t * 3.0 + E_ph * 5)
    magic = E_kind < (0.3 + 0.5 * c)
    col = np.where(magic[:, None], MAG[None] * 0.8 + VIO[None] * 0.2, EMB[None])
    after = T.flash_curve(f, E['burst'], 2, 120)
    rad = E_sz * fade * (0.7 + 0.3 * tw)
    emit = (1.5 + 4 * c + 4 * after) * tw * fade
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 8. dust motes / 9. debris
# ----------------------------------------------------------------------------
NM = 420
M_ang = R.uniform(0, 2 * np.pi, NM)
M_spd = R.uniform(1.0, 4.5, NM)
M_h = R.uniform(0.02, 0.6, NM)
M_ev = R.integers(0, 3, NM)       # 0 = release (wizard), 1 = impact, 2 = burst
M_sz = R.uniform(0.006, 0.02, NM)


def sys_motes(f):
    centers = [np.array([T.WIZ[0], T.WIZ[1] - 0.3, 0.0]),
               np.array([0, T.IMPACT_POS[1] + 0.3, 0.0]),
               np.array([0, T.IMPACT_POS[1] + 0.3 - T.shield_push(E['burst']), 0.0])]
    t0s = np.array([E['release'], E['impact'], E['burst']])[M_ev]
    age = (f - t0s) / FPS
    alive = (age >= 0) & (age < 2.5)
    a = np.maximum(age, 0)
    C = np.array(centers)[M_ev]
    dist = M_spd * (1 - np.exp(-1.6 * a)) / 1.6 + 0.2
    P = C + np.stack([np.cos(M_ang) * dist, np.sin(M_ang) * dist, M_h * (1 - np.exp(-2 * a)) + 0.03 * a], 1)
    k = np.clip(a / 2.5, 0, 1)
    rad = M_sz * alive * (1 - k)
    col = np.where((M_ev == 1)[:, None], CYA[None] * 0.4 + np.array([0.5, 0.45, 0.5])[None],
                   MAG[None] * 0.4 + np.array([0.5, 0.42, 0.45])[None])
    emit = 1.6 * (1 - k) ** 2 * alive
    return P, rad, col, emit


ND = 160
D_ang = R.uniform(0, 2 * np.pi, ND)
D_v = R.uniform(1.5, 5.0, ND)
D_vz = R.uniform(2.0, 5.5, ND)
D_ev = R.integers(0, 3, ND)
D_sz = R.uniform(0.012, 0.035, ND)


def sys_debris(f):
    centers = np.array([[T.WIZ[0], T.WIZ[1] - 0.3, 0.02],
                        [0, T.IMPACT_POS[1] + 0.2, 0.02],
                        [0, T.IMPACT_POS[1] + 0.2 - T.shield_push(E['burst']), 0.02]])
    t0s = np.array([E['release'], E['impact'], E['burst']])[D_ev]
    a = np.maximum((f - t0s) / FPS, 0)
    alive = f >= t0s
    vz = D_vz * np.where(D_ev == 1, 0.6, 1.0)
    tf = 2 * vz / 9.81
    ta = np.minimum(a, tf)
    z = vz * ta - 0.5 * 9.81 * ta ** 2
    horiz = D_v * ta
    P = centers[D_ev] + np.stack([np.cos(D_ang) * horiz, np.sin(D_ang) * horiz, np.maximum(z, 0)], 1)
    rad = D_sz * alive
    col = np.tile(np.array([0.05, 0.05, 0.05]), (ND, 1))
    emit = 6 * np.exp(-a * 3) * alive
    return P, rad, col, emit


# ----------------------------------------------------------------------------
# 10. shield dissolve bits  11. palm flame
# ----------------------------------------------------------------------------
NH = 360
H_x = R.uniform(-0.9, 0.9, NH)
H_z = R.uniform(-0.9, 0.9, NH)
_m = H_x ** 2 + H_z ** 2 < 0.92 ** 2
H_x, H_z = np.where(_m, H_x, H_x * 0.5), np.where(_m, H_z, H_z * 0.5)
H_t0 = R.uniform(0, 1, NH)
H_v = R.normal(size=(NH, 3)) * 0.25 + np.array([0, 0.1, 0.55])
H_sz = R.uniform(0.008, 0.022, NH)


def sys_hexbits(f):
    sc = T.shield_center(int(f))
    P = np.zeros((NH, 3))
    rad = np.zeros(NH)
    col = np.tile(CYA, (NH, 1))
    emit = np.zeros(NH)
    # formation: bits converge onto the shield
    form_t = (f - E['shield_start'] + 12) / 40.0
    diss = (f - E['shield_fade_start']) / (E['shield_fade_end'] - E['shield_fade_start'])
    base = sc + np.stack([H_x, -(2.1 - np.sqrt(np.maximum(2.1 ** 2 - H_x ** 2 - H_z ** 2, 0))), H_z], 1)
    if 0 <= form_t < 1:
        k = np.clip(form_t * 1.6 - H_t0 * 0.6, 0, 1)
        P = base + (1 - k)[:, None] ** 2 * (H_v * 6 + np.array([0, -1.5, 0]))
        rad = H_sz * 0.6 * (k > 0) * (1 - k * 0.7)
        emit = 15 * (1 - k) * (k > 0)
        col = np.tile(WHC, (NH, 1))
    elif diss >= 0:
        u = np.clip(diss * 1.5 - H_t0 * 0.5, 0, None)
        t = u * 3.0
        P = base + H_v * t[:, None] + np.array([0, 0, 0.3]) * t[:, None] ** 2
        alive = (u > 0) & (u < 1.4)
        rad = H_sz * alive * np.clip(1.4 - u, 0, 1)
        emit = 10 * alive * np.clip(1.4 - u, 0, 1)
    else:
        P[:] = base
    return P, rad, col, emit


NP = 220
P_ph = R.uniform(0, 1, NP)
P_r = R.uniform(0, 1, NP)
P_a = R.uniform(0, 2 * np.pi, NP)
P_sz = R.uniform(0.004, 0.012, NP)


def sys_flame(f):
    palm = np.asarray(anim._sched(f, anim.WIZ_SEG)['R'][0])
    palm = palm + np.array([0.0, -0.09, 0.05])
    lvl = ramp(f, 1318, 1345) * (1 + 0.6 * T.flash_curve(f, E['eyes_flare'], 3, 25))
    u = np.mod(f / 26.0 + P_ph, 1.0)
    rr = 0.035 * (1 - u) * P_r
    z = u * 0.20
    sway = 0.015 * np.sin(f * 0.4 + P_ph * 9) * u
    P = palm + np.stack([np.cos(P_a) * rr + sway, np.sin(P_a) * rr, z], 1)
    rad = P_sz * (1 - u) * lvl
    col = WHM[None] * (1 - u)[:, None] + MAG[None] * u[:, None]
    emit = 20 * (1 - u) ** 1.3 * lvl
    return P, rad, col, emit


# ----------------------------------------------------------------------------
SYSTEMS = [
    ('FX_gather', sys_gather, None),
    ('FX_orbsparks', sys_orbsparks, None),
    ('FX_arcs', sys_arcs, A_edges),
    ('FX_trail', sys_trail, T_edges),
    ('FX_sparks', sys_sparks, chain_edges(NS, 2)),
    ('FX_fragments', sys_fragments, F_edges),
    ('FX_embers', sys_embers, None),
    ('FX_motes', sys_motes, None),
    ('FX_debris', sys_debris, None),
    ('FX_hexbits', sys_hexbits, None),
    ('FX_flame', sys_flame, None),
]


def update(scene, depsgraph=None):
    f = scene.frame_current + scene.frame_subframe
    for name, fn, edges in SYSTEMS:
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        try:
            P, rad, col, emit = fn(f)
            write_points(ob, P, rad, col, emit, edges)
        except Exception as ex:  # never let one system kill the frame
            import traceback
            print('FX ERROR', name, f, ex)
            traceback.print_exc()


def register():
    hs = bpy.app.handlers.frame_change_pre
    for h in list(hs):
        if getattr(h, '__name__', '') == 'update' and getattr(h, '__module__', '') == __name__:
            hs.remove(h)
    hs.append(update)
    update(bpy.context.scene)
