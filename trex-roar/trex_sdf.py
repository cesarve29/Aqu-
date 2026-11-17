"""Procedural T-Rex body built as a signed distance field (numpy) and meshed
with marching cubes.  Pure numpy/scipy/skimage -- no bpy in here.

Axes: X = left/right, -Y = forward (snout), +Z = up, metres, ground at z=0.
The model is symmetric in rest pose so only x>=0 is evaluated and mirrored.
Rest pose has the jaw already open (JAW_OPEN) so the mouth interior is real
geometry; the rig closes / opens it further.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from skimage import measure

F = np.float32
VOX = 0.016

# ----------------------------------------------------------------- landmarks
HEAD_PITCH = np.radians(12.0)
JAW_OPEN = np.radians(30.0)

def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

HEAD_SCALE = np.array([1.14, 1.05, 1.20])     # x, y, z scale of the head block
HS_MIN = 1.05
N0 = np.array([0, -3.05, 3.45]); N1 = np.array([0, -3.52, 4.02])
N2 = np.array([0, -3.95, 4.50]); N3 = np.array([0, -4.25, 4.76])
RH = rot_x(HEAD_PITCH)                       # head local -> world
JAW_PIVOT = N3 - RH @ (np.array([0, 0.25, 0.33]) * HEAD_SCALE)
RJ = RH @ rot_x(JAW_OPEN)                    # jaw local (closed coords) -> world

HIP = np.array([0.56, -0.10, 3.15]); KNEE = np.array([0.76, -1.00, 2.12])
ANKLE = np.array([0.72, -0.25, 1.02]); BALL = np.array([0.72, -0.62, 0.18])
TOE_MID = np.array([0.72, -1.46, 0.10]); TOE_IN = np.array([0.38, -1.25, 0.10])
TOE_OUT = np.array([1.05, -1.25, 0.10])
HALLUX_A = np.array([0.62, -0.48, 0.44]); HALLUX_B = np.array([0.44, -0.54, 0.13])
SHOULDER = np.array([0.60, -2.80, 2.66]); ELBOW = np.array([0.68, -2.62, 2.24])
WRIST = np.array([0.63, -2.98, 2.06])
FINGER1 = np.array([0.56, -3.15, 1.95]); FINGER2 = np.array([0.68, -3.16, 1.97])

# body loft stations (torso + tail)            y, halfW, top, bottom
BODY = np.array([
    [-3.40, 0.32, 3.72, 3.02], [-3.00, 0.60, 3.95, 2.52], [-2.50, 0.80, 4.08, 2.16],
    [-1.80, 0.88, 4.13, 2.00], [-1.00, 0.85, 4.13, 2.00], [-0.30, 0.76, 4.10, 2.24],
    [0.40, 0.63, 4.02, 2.68], [1.20, 0.47, 3.90, 2.92], [2.20, 0.34, 3.74, 3.02],
    [3.40, 0.23, 3.54, 3.04], [4.80, 0.13, 3.35, 3.05], [6.20, 0.065, 3.23, 3.08],
    [7.30, 0.02, 3.16, 3.12]])
# head stations (head local coords, jaw hinge at origin, forward = -y, unscaled)
#                 y, halfW, top, bottom, taper (top narrower; <0: bottom narrower)
UPPER = np.array([
    [-1.50, 0.05, 0.215, 0.11, 0.20], [-1.46, 0.135, 0.28, 0.06, 0.30], [-1.38, 0.215, 0.37, -0.02, 0.40], [-1.22, 0.255, 0.44, -0.06, 0.45],
    [-1.00, 0.275, 0.50, -0.085, 0.50], [-0.75, 0.305, 0.57, -0.08, 0.50], [-0.52, 0.36, 0.66, -0.05, 0.36],
    [-0.38, 0.44, 0.69, -0.03, 0.22], [-0.20, 0.475, 0.66, -0.02, 0.16], [0.00, 0.47, 0.64, 0.00, 0.15],
    [0.18, 0.42, 0.60, 0.04, 0.20], [0.30, 0.28, 0.48, 0.14, 0.30]])
LOWER = np.array([
    [-1.37, 0.09, -0.07, -0.18, -0.3], [-1.28, 0.15, -0.06, -0.26, -0.3], [-1.10, 0.19, -0.075, -0.28, -0.3],
    [-0.85, 0.225, -0.09, -0.31, -0.3], [-0.55, 0.28, -0.08, -0.36, -0.3], [-0.25, 0.36, -0.05, -0.40, -0.3],
    [0.05, 0.40, -0.02, -0.37, -0.3], [0.16, 0.33, -0.02, -0.25, -0.3]])
TONGUE = np.array([
    [-1.04, 0.03, -0.115, -0.17, 0], [-0.92, 0.075, -0.09, -0.21, 0], [-0.60, 0.115, -0.085, -0.24, 0],
    [-0.30, 0.15, -0.085, -0.25, 0], [-0.05, 0.14, -0.11, -0.25, 0]])
EYE_C = np.array([0.335, -0.43, 0.47]); EYE_R = 0.056
RIM_IN_U = 0.075          # gum/lip thickness of upper jaw
RIM_IN_L = 0.055

def st_interp(st, col, y):
    return PchipInterpolator(st[:, 0], st[:, col])(np.clip(y, st[0, 0], st[-1, 0]))

def head_to_world(p, jaw=False):
    """head/jaw local point(s) -> world (rest pose)."""
    R = RJ if jaw else RH
    return JAW_PIVOT + (np.atleast_2d(p) * HEAD_SCALE) @ R.T

def head_dir_to_world(v, jaw=False):
    R = RJ if jaw else RH
    w = (np.atleast_2d(v) * HEAD_SCALE) @ R.T
    return w / np.linalg.norm(w, axis=1, keepdims=True)

def body_axis(y):
    """centre line z and half height of the torso/tail loft at y."""
    t = np.interp(y, BODY[:, 0], BODY[:, 2]); b = np.interp(y, BODY[:, 0], BODY[:, 3])
    return 0.5 * (t + b), 0.5 * (t - b)

# ---------------------------------------------------------------- primitives
def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)

def smax(a, b, k):
    return -smin(-a, -b, k)

def capsule(X, Y, Z, a, b, r1, r2, flat=(1, 1, 1)):
    """tapered capsule a->b, optionally squashed per axis about the segment."""
    fx, fy, fz = flat
    px = (X - a[0]) / fx; py = (Y - a[1]) / fy; pz = (Z - a[2]) / fz
    bx = (b[0] - a[0]) / fx; by = (b[1] - a[1]) / fy; bz = (b[2] - a[2]) / fz
    l2 = bx * bx + by * by + bz * bz
    t = np.clip((px * bx + py * by + pz * bz) / l2, 0, 1)
    d = np.sqrt((px - bx * t) ** 2 + (py - by * t) ** 2 + (pz - bz * t) ** 2)
    return (d - (r1 + (r2 - r1) * t)) * min(fx, fy, fz)

def ellipsoid(X, Y, Z, c, r):
    k0 = np.sqrt(((X - c[0]) / r[0]) ** 2 + ((Y - c[1]) / r[1]) ** 2 + ((Z - c[2]) / r[2]) ** 2)
    return (k0 - 1.0) * min(r)

def loft(X, Y, Z, st, rf=0.8, y0=None, y1=None):
    """rounded-box cross-section (in x,z) swept along y through stations.
    optional 5th station column tapers the width towards the top (or bottom)."""
    ys = st[:, 0]; yc = np.clip(Y, ys[0], ys[-1])
    w = np.maximum(PchipInterpolator(ys, st[:, 1])(yc), 0.01)
    t = PchipInterpolator(ys, st[:, 2])(yc); b = PchipInterpolator(ys, st[:, 3])(yc)
    zc = 0.5 * (t + b); h = np.maximum(0.5 * (t - b), 0.01)
    fac = 1.0
    if st.shape[1] > 4 and np.any(st[:, 4] != 0):
        tp = np.interp(yc, ys, st[:, 4])
        u = np.clip((Z - b) / (2 * h), 0, 1)
        fac = np.where(tp >= 0, 1 - tp * u, 1 + tp * (1 - u))
    r = rf * np.minimum(w, h)
    qx = np.abs(X) / fac - (w - r); qz = np.abs(Z - zc) - (h - r)
    d2 = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - r
    d2 = d2 * np.minimum(fac, 1.0)
    ya = ys[0] if y0 is None else y0; yb = ys[-1] if y1 is None else y1
    dy = np.maximum(ya - Y, Y - yb)
    return np.hypot(np.maximum(d2, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(d2, dy), 0)

def to_local(X, Y, Z, R, o, sc=1.0):
    """world -> local for rotation R (local->world, about X) and origin o."""
    py = Y - o[1]; pz = Z - o[2]
    sc = np.ones(3) * sc
    return (X / sc[0], (R[1, 1] * py + R[2, 1] * pz) / sc[1], (R[1, 2] * py + R[2, 2] * pz) / sc[2])

def wobble(X, Y, Z, f, seed=0.0):
    """cheap smooth pseudo noise in [-1,1] (sum of rotated sines)."""
    a = np.sin(X * 1.31 * f + 1.7 + seed) * np.sin(Y * 1.07 * f + 0.3 + seed * 2) * np.sin(Z * 1.19 * f + 4.1)
    b = np.sin((X + Y) * 0.83 * f + 2.2 + seed) * np.sin((Y - Z) * 0.91 * f + 5.3) * np.sin((Z + X) * 0.77 * f + 0.9)
    return 0.6 * a + 0.4 * b

# -------------------------------------------------------------------- groups
# every group: fn(X, Y, Z) with X already folded (>=0), plus a world bbox.

def g_axial(X, Y, Z):
    d = loft(X, Y, Z, BODY, rf=0.86)
    zc, h = body_axis(Y)
    ridge = np.hypot(X / 0.9, (Z - (zc + h - 0.04)) / 1.0) - (0.052 + 0.016 * np.sin(Y * 2 * np.pi / 0.23))
    ridge = np.maximum(ridge, np.maximum(-3.0 - Y, Y - 5.6))
    d = smin(d, ridge, 0.06)
    ribs = np.sin(Y * 2 * np.pi / 0.27 + Z * 1.6)
    mask = np.clip((Y + 2.9) / 0.4, 0, 1) * np.clip((-0.7 - Y) / 0.4, 0, 1) * np.clip((3.55 - Z) / 0.4, 0, 1) * np.clip((Z - 2.3) / 0.3, 0, 1)
    d = d - 0.012 * ribs * mask
    d = smin(d, ellipsoid(X, Y, Z, (0.45, -0.25, 3.62), (0.36, 0.9, 0.38)), 0.25)       # hip crest
    d = smin(d, ellipsoid(X, Y, Z, (0.56, -2.65, 3.05), (0.30, 0.50, 0.55)), 0.28)      # shoulder girdle
    d = smin(d, ellipsoid(X, Y, Z, (0.0, -0.55, 2.02), (0.20, 0.42, 0.22)), 0.2)        # pubic boot
    return d

def g_neck(X, Y, Z):
    fl = (0.86, 1, 1)
    d = capsule(X, Y, Z, N0, N1, 0.70, 0.56, fl)
    d = smin(d, capsule(X, Y, Z, N1, N2, 0.56, 0.47, fl), 0.15)
    d = smin(d, capsule(X, Y, Z, N2, N3, 0.47, 0.42, fl), 0.15)
    d = smin(d, capsule(X, Y, Z, (0, -3.15, 2.92), (0, -4.22, 4.02), 0.52, 0.28, (0.8, 1, 1)), 0.2)   # throat
    s_ = (Y * -0.67 + Z * 0.74)
    d = d - 0.013 * np.sin(s_ * 2 * np.pi / 0.21 + 1.3 * np.sin(Z * 4 + X * 3)) * np.clip((Z - 3.2) / 0.5, 0, 1)
    for i in range(10):
        t = (i + 0.5) / 10
        c = N0 + (N3 - N0) * t + np.array([0, 0.36, 0.40]) * (0.66 - 0.26 * t) / 0.54
        d = smin(d, ellipsoid(X, Y, Z, c, (0.04, 0.07, 0.05)), 0.06)
    return d

def _cav(xl, yl, zl, st, rim, up):
    c = st.copy(); c[:, 4] = 0
    back = np.clip((st[:, 0] + 0.45) / 0.35, 0, 1) * 0.05          # thicker cheeks at the back
    c[:, 1] = np.maximum(st[:, 1] - rim - back, 0.02)
    if up:    # carve from just below the rim up to the palate vault
        rimz = st[:, 3].copy(); c[:, 3] = rimz - 0.035; c[:, 2] = rimz + 0.13 + 0.05 * np.clip((st[:, 0] + 1.3) / 0.6, 0, 1)
        return loft(xl, yl, zl, c, rf=0.7, y0=st[0, 0] + 0.085, y1=0.10)
    rimz = st[:, 2].copy(); c[:, 2] = rimz + 0.035; c[:, 3] = rimz - 0.15
    return loft(xl, yl, zl, c, rf=0.7, y0=st[0, 0] + 0.07, y1=0.08)

def g_head(X, Y, Z):
    xl, yl, zl = to_local(X, Y, Z, RH, JAW_PIVOT, HEAD_SCALE)
    d = loft(xl, yl, zl, UPPER, rf=0.6)
    # brow ridge (lacrimal horn) sloping down towards the snout, postorbital + cheek bosses
    d = smin(d, capsule(xl, yl, zl, (0.235, -0.68, 0.545), (0.325, -0.36, 0.665), 0.04, 0.075), 0.09)
    d = smin(d, ellipsoid(xl, yl, zl, (0.39, -0.17, 0.57), (0.085, 0.13, 0.10)), 0.09)
    d = smin(d, ellipsoid(xl, yl, zl, (0.405, -0.30, 0.14), (0.07, 0.17, 0.085)), 0.09)
    d = smin(d, capsule(xl, yl, zl, (0.0, 0.05, 0.63), (0.0, 0.26, 0.52), 0.07, 0.06), 0.08)     # nuchal crest
    for i in range(9):                                                                          # rugose nasals
        y = -1.30 + i * 0.095
        top = float(st_interp(UPPER, 2, y))
        d = smin(d, ellipsoid(xl, yl, zl, (0.035 + 0.025 * (i % 2), y, top - 0.012), (0.055, 0.055, 0.04)), 0.045)
    d = smin(d, ellipsoid(xl, yl, zl, (0.12, -1.35, 0.27), (0.06, 0.085, 0.06)), 0.06)        # nostril rim
    # skull fenestrae read as shallow hollows in the face
    d = smax(d, -ellipsoid(xl, yl, zl, (0.40, -0.80, 0.30), (0.10, 0.20, 0.13)), 0.10)
    d = smax(d, -ellipsoid(xl, yl, zl, (0.52, -0.02, 0.38), (0.07, 0.12, 0.15)), 0.09)
    # jaw-closing muscle bridging to the lower jaw at the mouth corner
    d = smin(d, capsule(xl, yl, zl, (0.375, -0.03, 0.22), (0.37, -0.10, -0.26), 0.105, 0.085), 0.08)
    return d * HS_MIN

def g_jaw(X, Y, Z):
    xl, yl, zl = to_local(X, Y, Z, RJ, JAW_PIVOT, HEAD_SCALE)
    d = loft(xl, yl, zl, LOWER, rf=0.6)
    d = smin(d, ellipsoid(xl, yl, zl, (0.0, -1.22, -0.21), (0.13, 0.14, 0.08)), 0.08)   # chin
    d = smin(d, ellipsoid(xl, yl, zl, (0.33, -0.12, -0.24), (0.08, 0.2, 0.13)), 0.08)   # jaw angle
    return d * HS_MIN

def g_tongue(X, Y, Z):
    xl, yl, zl = to_local(X, Y, Z, RJ, JAW_PIVOT, HEAD_SCALE)
    d = loft(xl, yl, zl, TONGUE, rf=0.9)
    d = d + 0.012 * np.exp(-(xl / 0.025) ** 2) * np.clip((-0.2 - yl) / 0.2, 0, 1)        # median groove
    return d * HS_MIN

def carve_mouth(X, Y, Z):
    """signed distance of the mouth cavity volume (negative inside)."""
    xu, yu, zu = to_local(X, Y, Z, RH, JAW_PIVOT, HEAD_SCALE)
    xj, yj, zj = to_local(X, Y, Z, RJ, JAW_PIVOT, HEAD_SCALE)
    cu = _cav(xu, yu, zu, UPPER, RIM_IN_U, True)
    cl = _cav(xj, yj, zj, LOWER, RIM_IN_L, False)
    gul = capsule(xu, yu, zu, (0, -0.40, -0.10), (0, 0.34, -0.20), 0.21, 0.13, (1.25, 1, 1))   # gullet
    return smin(smin(cu, cl, 0.04), gul, 0.06) * HS_MIN

def _fit_eye():
    """push the eye centre so the ball sits just inside the skull surface."""
    xs = np.linspace(0.15, 0.6, 400)
    o = head_to_world(np.stack([xs, np.full_like(xs, EYE_C[1]), np.full_like(xs, EYE_C[2])], 1))
    d = g_head(o[:, 0], o[:, 1], o[:, 2])
    surf = xs[np.argmax(d > 0)]
    EYE_C[0] = surf - EYE_R * 0.62

def carve_face(X, Y, Z):
    xl, yl, zl = to_local(X, Y, Z, RH, JAW_PIVOT, HEAD_SCALE)
    eye = ellipsoid(xl, yl, zl, EYE_C + np.array([0.04, 0.0, 0.0]), (0.075, 0.088, 0.066))
    nos = capsule(xl, yl, zl, (0.175, -1.375, 0.28), (0.08, -1.22, 0.25), 0.034, 0.02)
    ear = ellipsoid(xl, yl, zl, (0.49, 0.12, 0.30), (0.05, 0.03, 0.05))
    return np.minimum(np.minimum(eye, nos), ear) * HS_MIN

def g_thigh(X, Y, Z):
    d = capsule(X, Y, Z, HIP, KNEE, 0.66, 0.37, (0.78, 1, 1))
    d = smin(d, capsule(X, Y, Z, HIP + [0, 0.45, 0.1], KNEE + [0, 0.34, 0.30], 0.54, 0.30, (0.78, 1, 1)), 0.2)
    return d

def g_shin(X, Y, Z):
    d = capsule(X, Y, Z, KNEE, ANKLE, 0.36, 0.19, (0.85, 1, 1))
    mid = 0.5 * (KNEE + ANKLE)
    d = smin(d, capsule(X, Y, Z, KNEE + [0, 0.20, -0.12], mid + [0, 0.14, 0], 0.32, 0.14, (0.85, 1, 1)), 0.12)
    d = smin(d, ellipsoid(X, Y, Z, KNEE + [0, -0.07, 0.02], (0.20, 0.24, 0.24)), 0.08)
    return d

def g_meta(X, Y, Z):
    d = capsule(X, Y, Z, ANKLE, BALL, 0.195, 0.20, (0.9, 1, 1))
    d = smin(d, ellipsoid(X, Y, Z, ANKLE + [0, 0.06, 0], (0.20, 0.24, 0.22)), 0.06)
    d = smin(d, capsule(X, Y, Z, HALLUX_A, HALLUX_B, 0.065, 0.045), 0.05)
    return d

def g_toes(X, Y, Z):
    d = ellipsoid(X, Y, Z, BALL + [0, -0.05, -0.03], (0.29, 0.29, 0.17))
    for tip, r in ((TOE_MID, 0.15), (TOE_IN, 0.125), (TOE_OUT, 0.125)):
        d = smin(d, capsule(X, Y, Z, BALL + [0, 0, -0.04], tip, r, r * 0.66), 0.06)
        for t in (0.45, 0.78):                         # knuckle pads
            c = BALL + (tip - BALL) * t
            d = smin(d, ellipsoid(X, Y, Z, c + [0, 0, 0.025], (r * 0.95, r * 0.95, r * 0.92)), 0.03)
    return np.maximum(d, -(Z - 0.004))                 # flat sole on the ground

def g_uarm(X, Y, Z):
    return capsule(X, Y, Z, SHOULDER, ELBOW, 0.16, 0.10)

def g_farm(X, Y, Z):
    d = capsule(X, Y, Z, ELBOW, WRIST, 0.095, 0.065)
    d = smin(d, capsule(X, Y, Z, WRIST, FINGER1, 0.047, 0.03), 0.03)
    d = smin(d, capsule(X, Y, Z, WRIST, FINGER2, 0.047, 0.03), 0.03)
    return d

def _bb(pts, pad):
    p = np.array(pts, dtype=float)
    return p.min(0) - pad, p.max(0) + pad

def _head_bb(R, st, pad):
    c = []
    for y in (st[0, 0], st[-1, 0] + 0.35):
        for z in (st[:, 3].min() - 0.1, st[:, 2].max() + 0.1):
            c.append(JAW_PIVOT + R @ np.array([0, y, z]))
    c = [JAW_PIVOT + (p - JAW_PIVOT) * 1.2 for p in c]
    lo, hi = _bb(c, pad); lo[0] = 0; hi[0] = 0.66
    return lo, hi

_fit_eye()
# name, fn, bbox(lo,hi), union smoothness k, skin blend tau
GROUPS = [
    ("axial", g_axial, (np.array([0, -3.6, 1.7]), np.array([1.05, 7.45, 4.35])), 0.0, 0.10),
    ("neck", g_neck, _bb([N0, N3, (0, -3.15, 2.95)], 0.8), 0.30, 0.16),
    ("thigh", g_thigh, _bb([HIP, KNEE, HIP + [0, 0.45, 0.1]], 0.8), 0.22, 0.16),
    ("shin", g_shin, _bb([KNEE, ANKLE], 0.5), 0.10, 0.10),
    ("meta", g_meta, _bb([ANKLE, BALL, HALLUX_B], 0.32), 0.07, 0.07),
    ("toes", g_toes, _bb([BALL, TOE_MID, TOE_IN, TOE_OUT], 0.34), 0.06, 0.07),
    ("uarm", g_uarm, _bb([SHOULDER, ELBOW], 0.24), 0.10, 0.08),
    ("farm", g_farm, _bb([ELBOW, WRIST, FINGER1, FINGER2], 0.14), 0.04, 0.05),
    ("head", g_head, _head_bb(RH, UPPER, 0.25), 0.12, 0.07),
    ("jaw", g_jaw, _head_bb(RJ, LOWER, 0.22), 0.07, 0.045),
]
MOUTH_BB = (np.minimum(_head_bb(RH, UPPER, 0.1)[0], _head_bb(RJ, LOWER, 0.1)[0]),
            np.maximum(_head_bb(RH, UPPER, 0.1)[1], _head_bb(RJ, LOWER, 0.1)[1]))
TONGUE_BB = _head_bb(RJ, TONGUE, 0.12)


def build(vox=VOX, verbose=True):
    lo = np.array([0.0, -6.5, -0.10]); hi = np.array([1.5, 7.5, 5.75])
    gx = np.arange(0, hi[0] + vox, vox, dtype=F)
    gy = np.arange(lo[1], hi[1] + vox, vox, dtype=F)
    gz = np.arange(lo[2], hi[2] + vox, vox, dtype=F)
    D = np.full((len(gx), len(gy), len(gz)), 10.0, dtype=F)

    def region(blo, bhi, pad):
        i0 = np.searchsorted(gx, max(blo[0] - pad, 0.0)); i1 = np.searchsorted(gx, bhi[0] + pad)
        j0 = np.searchsorted(gy, blo[1] - pad); j1 = np.searchsorted(gy, bhi[1] + pad)
        k0 = np.searchsorted(gz, blo[2] - pad); k1 = np.searchsorted(gz, bhi[2] + pad)
        sl = (slice(max(i0 - 1, 0), i1 + 1), slice(max(j0 - 1, 0), j1 + 1), slice(max(k0 - 1, 0), k1 + 1))
        X = gx[sl[0]][:, None, None]; Y = gy[sl[1]][None, :, None]; Z = gz[sl[2]][None, None, :]
        return sl, X, Y, Z

    for name, fn, (blo, bhi), k, _tau in GROUPS:
        sl, X, Y, Z = region(blo, bhi, k + 2 * vox)
        d = fn(X, Y, Z).astype(F)
        D[sl] = smin(D[sl], d, k)
        if verbose:
            print("  sdf", name, D[sl].shape, flush=True)
    sl, X, Y, Z = region(*MOUTH_BB, 0.05)
    D[sl] = smax(D[sl], -carve_mouth(X, Y, Z).astype(F), 0.025)
    D[sl] = smax(D[sl], -carve_face(X, Y, Z).astype(F), 0.02)
    sl, X, Y, Z = region(*TONGUE_BB, 0.06)
    D[sl] = smin(D[sl], g_tongue(X, Y, Z).astype(F), 0.035)
    # organic irregularity everywhere (kept small near the head)
    X = gx[:, None, None]; Y = gy[None, :, None]; Z = gz[None, None, :]
    amp = 0.012 * np.clip((Y + 4.6) / 1.0, 0.25, 1.0) * np.clip(Z / 0.8, 0.2, 1)
    near = np.abs(D) < 0.2
    D -= (amp * (wobble(X, Y, Z, 5.0) + 0.5 * wobble(X, Y, Z, 11.0, 3.0))).astype(F) * near
    # skin folds / wrinkles (ridged noise), finer and fainter on the head
    k = np.clip((Y + 4.4) / 0.8, 0.45, 1.0)
    fold = (1 - np.abs(wobble(X * 0.6, Y * 1.5, Z, 21.0, 7.0))) ** 2 * 0.0075 + (1 - np.abs(wobble(X, Y * 0.7, Z * 1.4, 52.0, 2.0))) ** 2 * 0.0042
    D -= (fold * k).astype(F) * near

    full = np.concatenate([D[:0:-1], D], axis=0)
    del D
    verts, faces, normals, _ = measure.marching_cubes(full, level=0.0, spacing=(vox, vox, vox))
    verts = verts + np.array([-(len(gx) - 1) * vox, lo[1], lo[2]])
    if verbose:
        print("  mesh", len(verts), "verts", len(faces), "tris", flush=True)
    return verts.astype(F), faces.astype(np.int32), (-normals).astype(F)


def vertex_data(verts):
    """per-vertex group distances + masks, evaluated on the folded field."""
    X = np.abs(verts[:, 0]).astype(np.float64); Y = verts[:, 1].astype(np.float64); Z = verts[:, 2].astype(np.float64)
    out = {}
    for name, fn, (blo, bhi), k, tau in GROUPS:
        d = np.full(len(verts), 5.0)
        m = (X >= blo[0] - 0.4) & (X <= bhi[0] + 0.4) & (Y >= blo[1] - 0.4) & (Y <= bhi[1] + 0.4) & (Z >= blo[2] - 0.4) & (Z <= bhi[2] + 0.4)
        d[m] = fn(X[m], Y[m], Z[m])
        out["d_" + name] = d.astype(F)
    m = (Y < JAW_PIVOT[1] + 0.9) & (Z > 3.0)
    cm = np.full(len(verts), 5.0); tg = np.full(len(verts), 5.0)
    cm[m] = carve_mouth(X[m], Y[m], Z[m]); tg[m] = g_tongue(X[m], Y[m], Z[m])
    tongue = np.clip(1.0 - (tg - 0.006) / 0.02, 0, 1)
    # only surfaces that were carved *into* the head count as mouth lining (never the outer throat skin)
    dmin = np.minimum(np.minimum(out["d_head"], out["d_jaw"]), out["d_neck"])
    inner = np.clip((-0.006 - dmin) / 0.03, 0, 1)
    out["mouth"] = np.maximum(np.clip(1.0 - (cm - 0.004) / 0.03, 0, 1) * inner, tongue).astype(F)
    out["tongue"] = tongue.astype(F)
    return out


if __name__ == "__main__":
    import sys, time
    t = time.time()
    v, f, n = build()
    vd = vertex_data(v)
    np.savez(sys.argv[1] if len(sys.argv) > 1 else "trex_mesh.npz", verts=v, faces=f, normals=n, **vd)
    print("done", time.time() - t)
